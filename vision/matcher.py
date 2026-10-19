from dataclasses import dataclass

import cv2
import numpy as np
from numpy.typing import NDArray

# One bot worker processes frames sequentially. Avoid a native worker pool
# retaining a separate image workspace for every logical CPU on long runs.
cv2.setNumThreads(1)
RESPONSE_ROWS=384


@dataclass(frozen=True)
class ROI:
    x: float
    y: float
    width: float
    height: float

    def bounds(self, screen: NDArray[np.uint8]) -> tuple[int, int, int, int]:
        height, width = screen.shape[:2]
        return (round(self.x * width), round(self.y * height),
                round((self.x + self.width) * width),
                round((self.y + self.height) * height))


@dataclass(frozen=True)
class MatchResult:
    x: int
    y: int
    width: int
    height: int
    confidence: float

    @property
    def center(self) -> tuple[int, int]:
        return self.x + self.width // 2, self.y + self.height // 2


def find_template(screen: NDArray[np.uint8], template: NDArray[np.uint8],
                  threshold: float = 0.90, roi: ROI | None = None,
                  contrast_invariant: bool = False) -> MatchResult | None:
    x1, y1, x2, y2 = roi.bounds(screen) if roi else (0, 0, screen.shape[1], screen.shape[0])
    region = screen[y1:y2, x1:x2]
    height, width = template.shape[:2]
    if region.shape[0] < height or region.shape[1] < width:
        return None
    if contrast_invariant:
        def deviation(image):
            means,stds = cv2.meanStdDev(image)
            return float(np.sqrt(np.mean(stds**2)+np.var(means)))
        if deviation(template) < 1 or deviation(region) < 1:
            return None
    # Only retain a small response strip. The template overlap ensures every
    # possible placement is evaluated, including those crossing strip edges.
    method = cv2.TM_CCOEFF_NORMED if contrast_invariant else cv2.TM_SQDIFF_NORMED
    confidence, location = -float('inf'), (0,0)
    # Tiny repeated anchors need OpenCV's original global tie-breaking:
    # different FFT strip sizes can choose a different identical room sign.
    strip_rows = region.shape[0] if height <= 20 and width <= 64 else RESPONSE_ROWS
    try:
        confidence,location = _match_strips(region,template,method,contrast_invariant,strip_rows)
    except (cv2.error, MemoryError) as error:
        if isinstance(error,cv2.error) and error.code != -4:
            raise
        # Preserve normal scores/tie-breaking. Only allocation failure retries
        # with a smaller working set; never replay a game input here.
        if strip_rows <= 64:
            raise
        confidence,location = _match_strips(region,template,method,contrast_invariant,64)
    if not np.isfinite(confidence) or confidence < threshold:
        return None
    return MatchResult(x1 + location[0], y1 + location[1], width, height, confidence)


def _match_strips(region, template, method, contrast_invariant, strip_rows):
    height=template.shape[0]
    confidence,location=-float('inf'),(0,0)
    for top in range(0,region.shape[0]-height+1,strip_rows):
        bottom = min(region.shape[0],top+strip_rows+height-1)
        scores = cv2.matchTemplate(region[top:bottom],template,method)
        minimum,maximum,min_location,max_location = cv2.minMaxLoc(scores)
        score = maximum if contrast_invariant else 1.0-minimum
        point = max_location if contrast_invariant else min_location
        if np.isfinite(score) and score > confidence:
            confidence,location = score,(point[0],point[1]+top)
        del scores
    return confidence,location
