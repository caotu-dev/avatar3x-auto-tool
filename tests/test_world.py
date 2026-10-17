from pathlib import Path
import unittest

import cv2

from fishing.catch import CatchDetector, SPECIES
from fishing.detector import FishingDetector
from fishing.states import FishingState
from fishing.world import WorldDetector
from vision.layout import find_target_board


class WorldTests(unittest.TestCase):
    def test_shop_lettering_and_arrow_occluded_by_players(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shop_entrance_occluded.png'))
        world=WorldDetector();sign=world.match(image,'shop_sign')
        self.assertIsNotNone(sign)
        self.assertEqual((sign.center[0]-12,sign.center[1]+123),(1011,425))
        self.assertEqual(world.map_name(image),'center')

    def test_real_server_loading_and_exit_are_distinct(self):
        detector=FishingDetector(area='ca_noc')
        self.assertEqual(detector.detect(cv2.imread(str(Path(__file__).parent/'fixtures/loading_vi.png'))).state,FishingState.LOADING)
        prompt=detector.detect(cv2.imread(str(Path(__file__).parent/'fixtures/loading_exit.png')))
        self.assertEqual(prompt.state,FishingState.EXIT_CONFIRM)
        self.assertGreater(prompt.matches['exit_no'].center[0],800)

    def test_puffer_shifted_room_finds_visible_seats(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/puffer_shifted_room.png'))
        detection=FishingDetector(area='ca_noc').detect(image)
        self.assertEqual(detection.state,FishingState.IDLE)
        chairs=[m for k,m in detection.matches.items() if k.startswith('chair_')]
        self.assertGreaterEqual(len(chairs),2)
        self.assertTrue(all(600<m.center[0]<1000 for m in chairs))

    def test_shark_crowded_entry_uses_sea_on_both_sides(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/shark_crowded_entry.png"))
        self.assertEqual(WorldDetector().map_name(image), "ca_map")
        self.assertEqual(FishingDetector(area="ca_map").detect(image).state, FishingState.IDLE)

    def test_perch_crowd_can_hide_chairs_without_hiding_pond_layout(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/perch_crowded_entry.png"))
        self.assertEqual(WorldDetector().map_name(image), "ca_ro")
        self.assertEqual(FishingDetector().detect(image).state, FishingState.IDLE)

    def test_all_catalog_species_from_real_popups(self):
        for species in SPECIES:
            with self.subTest(species=species):
                fixture = Path(__file__).parent / "fixtures/fish" / f"{species}.png"
                if not fixture.exists():
                    fixture = Path(__file__).parent / "fixtures/dock" / f"fish_{species}.png"
                image = cv2.imread(str(fixture))
                self.assertIsNotNone(image)
                self.assertEqual(CatchDetector().detect(image).species, species)

    def test_puffer_idle_chairs_allow_entry(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/puffer_idle.png"))
        detection = FishingDetector(area="ca_noc").detect(image)
        self.assertEqual(detection.state, FishingState.IDLE)
        self.assertGreaterEqual(sum(name.startswith("chair_") for name in detection.matches), 2)
        crowded = cv2.imread(str(Path(__file__).parent / "fixtures/puffer_crowded_idle.png"))
        self.assertEqual(WorldDetector().map_name(crowded), "ca_noc")
        after_exit = cv2.imread(str(Path(__file__).parent / "fixtures/puffer_after_exit.png"))
        self.assertEqual(WorldDetector().map_name(after_exit), "ca_noc")
        self.assertEqual(FishingDetector(area="ca_noc").detect(after_exit).state, FishingState.IDLE)

    def test_puffer_name_cannot_be_perch(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/fish/ca_noc.png"))
        self.assertEqual(CatchDetector(area="ca_noc").detect(image).species, "ca_noc")
        self.assertIsNone(CatchDetector(area="ca_ro").detect(image).species)

    def test_shark_idle_and_occluded_timer(self):
        folder = Path(__file__).parent / "fixtures"
        idle = cv2.imread(str(folder / "shark_idle.png"))
        self.assertEqual(WorldDetector().map_name(idle), "ca_map")
        self.assertEqual(FishingDetector(area="ca_map").detect(idle).state, FishingState.IDLE)
        board = cv2.imread(str(folder / "shark_board.png"))
        self.assertEqual(FishingDetector(area="ca_map").detect(board).state, FishingState.FISHING)
        self.assertEqual(WorldDetector().map_name(board, require_menu=False), "ca_map")
        occluded = cv2.imread(str(folder / "shark_occluded_board.png"))
        self.assertEqual(FishingDetector(area="ca_map").detect(occluded).state, FishingState.FISHING)
        filled = cv2.imread(str(folder / "shark_three_filled.png"))
        self.assertEqual(FishingDetector(area="ca_map").detect(filled).state, FishingState.FISHING)

    def test_puffer_board_does_not_hide_scene(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/puffer_board.png"))
        self.assertEqual(FishingDetector(area="ca_noc").detect(image).state, FishingState.FISHING)
        self.assertEqual(len(find_target_board(image).centers), 5)

    def test_center_arrows_and_shop_are_distinct(self):
        image = cv2.imread(str(Path(__file__).parent / "fixtures/center_right.png"))
        detector = WorldDetector()
        self.assertEqual(detector.map_name(image), "center")
        points = detector.arrows(image)
        self.assertTrue(any(x > 1400 and 540 < y < 660 for x, y in points))
        self.assertTrue(any(280 < y < 360 for x, y in points))
        self.assertFalse(detector.match(image, "purchase20"))
