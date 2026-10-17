from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

from .detector import FishingDetector
from .states import FishingState
from vision.layout import find_target_board


@dataclass(frozen=True)
class DragMatch:
    source_index: int
    target_index: int
    source: tuple[int, int]
    target: tuple[int, int]
    confidence: float
    margin: float
    completed: bool


@dataclass(frozen=True)
class SolvePlan:
    matches: tuple[DragMatch, ...]
    safe: bool
    reason: str


class FishingSolver:
    """Chỉ lập kế hoạch từ ảnh; không có quyền gửi input ADB."""

    def __init__(self, detector: FishingDetector | None = None):
        self.detector = detector or FishingDetector()
        self._source_key: bytes | None = None
        self._variants: list[list[NDArray[np.uint8]]] = []
        self._scores: dict[bytes, list[float]] = {}
        self._similar_sources: dict[tuple[int, int], float] = {}
        self._best_variants: dict[bytes, list[int]] = {}
        self._refined: set[bytes] = set()
        self._fine_variants: dict[tuple[int, int, int], list[NDArray[np.uint8]]] = {}
        self._precise_scores: dict[bytes, list[float]] = {}

    @staticmethod
    def completed(screen: NDArray[np.uint8], target: tuple[int, int]) -> bool:
        x, y = target
        value = cv2.cvtColor(screen[y - 35:y + 35, x - 35:x + 35], cv2.COLOR_BGR2HSV)[:, :, 2]
        return float(np.mean(value)) > 160

    def retry_match(self, before: NDArray[np.uint8], screen: NDArray[np.uint8],
                    pending: DragMatch) -> bool:
        """Chỉ thử lại khi ô và nguồn chưa đổi, cùng cặp ghép vẫn đủ chắc."""
        for x, y in (pending.target, pending.source):
            old = before[y - 32:y + 32, x - 32:x + 32]
            new = screen[y - 32:y + 32, x - 32:x + 32]
            if old.shape != (64, 64, 3) or new.shape != old.shape:
                return False
            if float(np.mean(cv2.absdiff(old, new))) > 3:
                return False
        plan = self.plan(screen)
        return plan.safe and any(
            m.target == pending.target and m.source == pending.source and not m.completed
            for m in plan.matches)

    def _shape_scores(self, target: NDArray[np.uint8],
                      templates: list[NDArray[np.uint8]], refine: bool = False,
                      precise: bool = False) -> list[float]:
        key = target.tobytes()
        if precise and key in self._precise_scores:
            return self._precise_scores[key]
        scores = self._scores.get(key)
        if scores is None:
            responses = [[float(cv2.minMaxLoc(cv2.matchTemplate(
                target, template, cv2.TM_CCOEFF_NORMED))[1]) for template in rotations]
                         for rotations in self._variants]
            best_variants = [int(np.argmax(response)) for response in responses]
            scores = [response[best] for response, best in zip(responses, best_variants)]
            if len(self._scores) >= 128:
                self._scores.clear()
                self._best_variants.clear()
                self._refined.clear()
                self._precise_scores.clear()
            self._scores[key] = scores
            self._best_variants[key] = best_variants
        if refine and (precise or key not in self._refined):
            refined = []
            step = 2 if precise else 5
            for index, best in enumerate(self._best_variants[key]):
                angle = -180 + (best // 3) * 15
                variant_key = (index, angle, step)
                variants = self._fine_variants.get(variant_key)
                if variants is None:
                    # Persistent GUI solvers span many rounds. Keep refinement
                    # images below ~8 MB rather than every source/angle seen.
                    if len(self._fine_variants) >= 20:
                        del self._fine_variants[next(iter(self._fine_variants))]
                    variants = [cv2.warpAffine(templates[index],
                                cv2.getRotationMatrix2D((42, 42), degrees, scale), (84, 84))
                                for degrees in range(angle - 10, angle + 11, step)
                                for scale in (.85, .90, .95, 1.0, 1.05)]
                    self._fine_variants[variant_key] = variants
                refined.append(max(scores[index], max(float(cv2.minMaxLoc(
                    cv2.matchTemplate(target, variant, cv2.TM_CCOEFF_NORMED))[1])
                    for variant in variants)))
            scores = refined
            if precise:
                self._precise_scores[key] = scores
            else:
                self._scores[key] = scores
                self._refined.add(key)
        return scores

    def _score_target(self, target: NDArray[np.uint8], templates: list[NDArray[np.uint8]],
                      color_scores: list[float], precise: bool = False) -> list[float]:
        shape_scores = self._shape_scores(target, templates, refine=precise, precise=precise)
        scores = [.7 * shape + .3 * color for shape, color in zip(shape_scores, color_scores)]
        ranking = np.argsort(scores)
        if scores[int(ranking[-1])] - scores[int(ranking[-2])] < .10:
            shape_scores = self._shape_scores(target, templates, refine=True, precise=precise)
            scores = [.7 * shape + .3 * color for shape, color in zip(shape_scores, color_scores)]
        best_two = np.argsort(scores)[-2:]
        first, second = map(int, best_two)
        if (abs(scores[first] - scores[second]) < .10
                and abs(color_scores[first] - color_scores[second]) > .30):
            # Khi cùng glyph nhưng khác màu, không để sai số xoay lấn át màu.
            pair = tuple(sorted((first, second)))
            similarity = self._similar_sources.get(pair)
            if similarity is None:
                source_target = np.pad(templates[pair[1]], 8)
                similarity = max(float(cv2.minMaxLoc(cv2.matchTemplate(
                    source_target, variant, cv2.TM_CCOEFF_NORMED))[1])
                    for variant in self._variants[pair[0]])
                self._similar_sources[pair] = similarity
            if similarity >= .75:
                scores = [.5 * shape + .5 * color
                          for shape, color in zip(shape_scores, color_scores)]
        ranking = np.argsort(scores)
        best, runner_up = int(ranking[-1]), int(ranking[-2])
        shape_ranking = np.argsort(shape_scores)
        # Màu gần nhau không được lấn át hai glyph khác hẳn (ví dụ cá/vương miện).
        if (scores[best] - scores[runner_up] < .10
                and best == int(shape_ranking[-1]) and shape_scores[best] >= .65
                and shape_scores[best] - shape_scores[int(shape_ranking[-2])] >= .12):
            pair = tuple(sorted((best, runner_up)))
            similarity = self._similar_sources.get(pair)
            if similarity is None:
                source_target = np.pad(templates[pair[1]], 8)
                similarity = max(float(cv2.minMaxLoc(cv2.matchTemplate(
                    source_target, variant, cv2.TM_CCOEFF_NORMED))[1])
                    for variant in self._variants[pair[0]])
                self._similar_sources[pair] = similarity
            if similarity < .70:
                scores = [.9 * shape + .1 * color
                          for shape, color in zip(shape_scores, color_scores)]
        return scores

    def plan(self, screen: NDArray[np.uint8]) -> SolvePlan:
        return self.plan_after_detection(screen, self.detector.detect(screen))

    def validate_match(self, screen, detection, chosen: DragMatch) -> bool:
        """A fresh guard must confirm the same pair, not only the fishing scene."""
        plan = self.plan_after_detection(screen, detection)
        return plan.safe and any(
            match.target_index == chosen.target_index
            and match.source_index == chosen.source_index
            and match.source == chosen.source and match.target == chosen.target
            and not match.completed for match in plan.matches)

    def plan_after_detection(self, screen: NDArray[np.uint8], detection) -> SolvePlan:
        """Dùng kết quả nhận diện của chính frame này từ vòng bot, tránh đo lại toàn màn hình."""
        if detection.state is not FishingState.FISHING or not detection.scene_confirmed:
            return SolvePlan((), False, "Không phải màn hình kéo hình")
        board = find_target_board(screen)
        if board is None:
            return SolvePlan((), False, "Không đo được bảng hình hoặc bảng đang chuyển cảnh")
        sources = [(1469, 132 + 127 * index) for index in range(6)]
        # Only the source/target patches participate in matching. Converting
        # animated scenery over the entire viewport wasted work each frame.
        source_patches = [cv2.cvtColor(screen[y - 42:y + 42, x - 42:x + 42],
                                      cv2.COLOR_BGR2HSV) for x, y in sources]
        templates = [((patch[:, :, 1] < 30) & (patch[:, :, 2] > 220)).astype(np.uint8) * 255
                     for patch in source_patches]
        yy, xx = np.ogrid[:84, :84]
        circle = (xx - 42) ** 2 + (yy - 42) ** 2 <= 38 ** 2
        for template in templates:
            template[~circle] = 0
        if any(np.count_nonzero(template) < 40 for template in templates):
            return SolvePlan((), False, "Có hình nguồn bị che hoặc đang di chuyển")
        # Rotation templates depend on glyph masks, not the animated scenery
        # underneath the translucent source panel. Colors are measured afresh.
        source_key = b"".join(template.tobytes() for template in templates)
        if source_key != self._source_key:
            self._source_key = source_key
            self._scores.clear()
            self._similar_sources.clear()
            self._best_variants.clear()
            self._refined.clear()
            self._fine_variants.clear()
            self._precise_scores.clear()
            self._variants = []
            for template in templates:
                rotations = []
                for angle in range(-180, 180, 15):
                    for scale in (.85, .95, 1.05):
                        matrix = cv2.getRotationMatrix2D((42, 42), angle, scale)
                        rotations.append(cv2.warpAffine(template, matrix, (84, 84)))
                self._variants.append(rotations)
        def color_histogram(patch) -> NDArray[np.float32]:
            mask = ((patch[:, :, 1] > 35) & (patch[:, :, 2] > 40) & circle).astype(np.uint8) * 255
            halves = []
            # Giữ thứ tự màu trên/dưới: histogram toàn ô làm mất thông tin này.
            for rows in (slice(0, 42), slice(42, 84)):
                histogram = cv2.calcHist([patch[rows]], [0], mask[rows], [18], [0, 180]).ravel()
                halves.append(histogram / max(float(np.linalg.norm(histogram)), 1.0))
            return np.concatenate(halves) / np.sqrt(2.0)
        source_colors = [color_histogram(patch) for patch in source_patches]
        matches = []
        for index, (x, y) in enumerate(board.centers):
            patch = cv2.cvtColor(screen[y - 50:y + 50, x - 50:x + 50], cv2.COLOR_BGR2HSV)
            # White glyphs retain low saturation even under the dark overlay.
            target = ((patch[:, :, 1] < 45) & (patch[:, :, 2] > 100)).astype(np.uint8) * 255
            target_color = color_histogram(patch[8:92, 8:92])
            color_scores = [float(np.dot(target_color, color)) for color in source_colors]
            scores = self._score_target(target, templates, color_scores)
            ranking = np.argsort(scores)
            best = int(ranking[-1])
            if scores[best] < .65 or scores[best] - scores[int(ranking[-2])] < .10:
                # Kiểm tra lại ô khó với phần trắng thuần, loại nền pastel/nét chéo.
                # Giữ cách tách cũ cho ô đã chắc; hai cách phải chọn cùng nguồn.
                strict_target = ((patch[:, :, 1] < 30) & (patch[:, :, 2] > 100)).astype(np.uint8) * 255
                strict_scores = self._score_target(strict_target, templates, color_scores)
                strict_ranking = np.argsort(strict_scores)
                if (int(strict_ranking[-1]) == best and strict_scores[best] >= .65
                        and strict_scores[best] - strict_scores[int(strict_ranking[-2])] >= .10):
                    scores, ranking = strict_scores, strict_ranking
                else:
                    # Chỉ đo 2° khi hai bước trên vẫn chưa đủ chắc; cache riêng
                    # để không thay đổi điểm của những ô đã được chấp nhận.
                    for candidate in (target, strict_target):
                        precise_scores = self._score_target(candidate, templates, color_scores, precise=True)
                        precise_ranking = np.argsort(precise_scores)
                        if (int(precise_ranking[-1]) == best and precise_scores[best] >= .65
                                and precise_scores[best] - precise_scores[int(precise_ranking[-2])] >= .10):
                            scores, ranking = precise_scores, precise_ranking
                            break
            source_index = int(ranking[-1])
            confidence = scores[source_index]
            margin = confidence - scores[int(ranking[-2])]
            completed = self.completed(screen, (x, y))
            matches.append(DragMatch(source_index, index, sources[source_index],
                                     (x, y), confidence, margin, completed))
        # confidence là điểm tương đồng, không phải xác suất kéo thành công.
        safe = all(match.confidence >= .65 and match.margin >= .10 for match in matches)
        uncertain = [f"T{match.target_index + 1} ({match.confidence:.2f}, biên {match.margin:.2f})"
                     for match in matches if match.confidence < .65 or match.margin < .10]
        return SolvePlan(tuple(matches), safe,
                         "Ghép đủ ô" if safe else "Có ô chưa đủ độ tin cậy: " + ", ".join(uncertain))
