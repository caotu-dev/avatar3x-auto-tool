import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import cv2
import numpy as np

from fishing.reconnect import ContinueScreen, ReconnectController


FIXTURES = Path(__file__).parent / 'fixtures'


class FastReconnectTests(unittest.TestCase):
    def test_login_guard_normalizes_only_once(self):
        image = cv2.imread(str(FIXTURES / 'navigation/world.png'))
        reader = ContinueScreen()
        with patch('fishing.reconnect.cv2.resize', wraps=cv2.resize) as resize:
            self.assertIsNone(reader.detect(image))
        self.assertEqual(resize.call_count, 1)

    def test_both_login_layouts_keep_correct_clicks_at_scaled_sizes(self):
        reader = ContinueScreen()
        for filename in ('reconnect/continue.png', 'login_logo_hearts.png'):
            original = cv2.imread(str(FIXTURES / filename))
            for width, height in ((825, 466), (1600, 900)):
                with self.subTest(filename=filename, width=width):
                    image = cv2.resize(original, (width, height))
                    point = reader.detect(image)
                    self.assertIsNotNone(point)
                    self.assertLess(abs(point[0] - 340 * width / 825), 5)
                    self.assertLess(abs(point[1] - 291 * height / 466), 5)

    def test_login_artwork_outside_login_region_is_not_actionable(self):
        reader = ContinueScreen()
        image = np.zeros((466, 825, 3), dtype=np.uint8)
        h, w = reader.logo.shape[:2]
        image[300:300 + h, 10:10 + w] = reader.logo
        h, w = reader.button.shape[:2]
        image[270:270 + h, 274:274 + w] = reader.button
        self.assertIsNone(reader.detect(image))

    def controller(self, device, folder):
        clock = [0.0]
        controller = ReconnectController(
            device, Path(folder), clock=lambda: clock[0],
            sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
        controller.event = Mock()
        return controller

    def test_verified_long_cooldown_preserves_reconnect_budget(self):
        device = Mock()
        frames = iter(['login'] * 2 + ['cooldown'] * 350 + ['login'] * 2 + ['world'] * 2)
        device.screenshot.side_effect = lambda: next(frames)
        reader = Mock()
        reader.blocked.side_effect = lambda image: image == 'cooldown'
        reader.detect.side_effect = lambda image: (659, 562) if image == 'login' else None
        with tempfile.TemporaryDirectory(dir=FIXTURES.parents[1] / 'debug') as folder:
            result = self.controller(device, folder).recover(
                reader, lambda image: image == 'world', timeout=4)
        self.assertEqual(result, {'status': 'READY', 'attempts': 2})
        self.assertEqual(device.tap.call_count, 2)

    def test_unknown_frames_still_timeout_after_a_cooldown(self):
        device = Mock()
        frames = iter(['cooldown'] * 25)
        device.screenshot.side_effect = lambda: next(frames, 'unknown')
        reader = Mock()
        reader.blocked.side_effect = lambda image: image == 'cooldown'
        reader.detect.return_value = None
        with tempfile.TemporaryDirectory(dir=FIXTURES.parents[1] / 'debug') as folder:
            with self.assertRaisesRegex(RuntimeError, 'sau 0 lần'):
                self.controller(device, folder).recover(
                    reader, lambda image: False, timeout=2)
        device.tap.assert_not_called()
        self.assertLess(device.screenshot.call_count, 40)


if __name__ == '__main__':
    unittest.main()
