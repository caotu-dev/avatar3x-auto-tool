import tempfile
import unittest
from pathlib import Path

import cv2

from fishing.navigation import MapNavigator
from config.settings import ROOT


class NavigationTests(unittest.TestCase):
    def test_real_maps_and_exit_popup_are_distinct(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "debug") as folder:
            navigator = MapNavigator(object(), Path(folder))
            for name, expected in {"world": "world", "office": "administration",
                                   "office_exit": "administration", "pier": "dock",
                                   "suburb": "suburb", "entertainment": "entertainment",
                                   "fishing": "fishing", "beach": "beach"}.items():
                with self.subTest(name=name):
                    screen = cv2.imread(str(Path(__file__).parent / f"fixtures/navigation/{name}.png"))
                    self.assertEqual(navigator.location(screen), expected)

    def test_world_markers_distinguish_the_three_routes(self):
        with tempfile.TemporaryDirectory(dir=ROOT / "debug") as folder:
            navigator = MapNavigator(object(), Path(folder))
            screen = cv2.imread(str(Path(__file__).parent / "fixtures/navigation/world.png"))
            matches = [navigator.match(screen, name) for name in ("fishing", "entertainment", "suburb")]
            self.assertTrue(all(matches))
            self.assertEqual(len(set(match.center for match in matches)), 3)

    def test_fishing_marker_ripples_and_vertical_bobbing_from_failed_session(self):
        from types import SimpleNamespace
        screens = [cv2.imread(str(Path(__file__).parent / f'fixtures/navigation/{name}'))
                   for name in ('world_fishing_clear.png', 'world_fishing_ripple.png')]
        with tempfile.TemporaryDirectory(dir=ROOT / 'debug') as folder:
            clock = [0.0]
            def sleep(seconds):
                clock[0] += seconds
            frames = iter(screens)
            device = SimpleNamespace(screenshot=lambda: next(frames))
            navigator = MapNavigator(device, Path(folder), clock=lambda: clock[0], sleep=sleep)
            clear = navigator.match(screens[0], 'fishing')
            ripple = navigator.match(screens[1], 'fishing')
            self.assertEqual(clear.center, (863, 188))
            self.assertEqual(ripple.center, (863, 197))
            self.assertTrue(all(navigator.is_world(screen) for screen in screens))
            self.assertEqual(navigator.find_marker('fishing').center, ripple.center)
            self.assertIsNone(navigator.match(cv2.imread(str(Path(__file__).parent / 'fixtures/navigation/office.png')), 'fishing'))

    def test_retry_entry_only_on_confirmed_world(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        for still_world, failures, expected_taps, succeeds in [
                (True, 1, 2, True), (True, 3, 3, False), (False, 1, 1, False)]:
            with self.subTest(still_world=still_world, failures=failures):
                nav = object.__new__(MapNavigator)
                nav.device = SimpleNamespace(screenshot=lambda: object())
                nav.location = Mock(return_value='world')
                nav.open_world = Mock()
                nav.find_marker = Mock(return_value=SimpleNamespace(center=(863, 194)))
                nav.tap = Mock()
                nav.is_world = Mock(return_value=still_world)
                nav.event = Mock()
                nav.save_location = Mock()
                remaining = [failures]
                def wait(predicate, label, **kwargs):
                    if label == 'khu fishing' and remaining[0]:
                        remaining[0] -= 1
                        raise RuntimeError('entry timeout')
                    return True
                nav.wait = wait
                if succeeds:
                    nav.go_region('fishing')
                    nav.save_location.assert_called_once_with('fishing')
                else:
                    with self.assertRaises(RuntimeError):
                        nav.go_region('fishing')
                    nav.save_location.assert_not_called()
                self.assertEqual(nav.tap.call_count, expected_taps)


if __name__ == "__main__":
    unittest.main()
