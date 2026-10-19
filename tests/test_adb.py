import subprocess
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from adb import AdbDevice, AdbError
from adb.screenshot import decode_screenshot


class AdbTests(unittest.TestCase):
    def setUp(self):
        self.commands = []

        def runner(command, **kwargs):
            self.commands.append(command)
            output = b"Physical size: 1600x900\nOverride size: 800x450\n"
            return subprocess.CompletedProcess(command, 0, output, b"")

        self.device = AdbDevice("test-device", "custom-adb", runner=runner)

    def test_input_commands_and_override_resolution(self):
        self.device.tap(799, 449)
        self.assertEqual(self.commands[-1],
                         ["custom-adb", "-s", "test-device", "shell", "input", "tap", "799", "449"])
        self.device.swipe(0, 0, 799, 449, 300)
        self.assertEqual(self.commands[-1][-7:], ["input", "swipe", "0", "0", "799", "449", "300"])
        self.device.back()
        self.assertEqual(self.commands[-1][-4:], ["shell", "input", "keyevent", "4"])

    def test_invalid_input_sends_no_action(self):
        for point in ((800, 0), (-1, 0), (0, 450), (1.5, 0)):
            with self.assertRaises(ValueError):
                self.device.tap(*point)
        self.assertTrue(all("input" not in command for command in self.commands))
        with self.assertRaises(ValueError):
            self.device.swipe(0, 0, 1, 1, 0)

    def test_numeric_shop_input_is_device_scoped_and_validated(self):
        self.device.type_number(20)
        self.assertEqual(self.commands[-1],
                         ["custom-adb", "-s", "test-device", "shell", "input", "text", "20"])
        count = len(self.commands)
        for value in (0, -1, True, 1.5, "20"):
            with self.assertRaises(ValueError):
                self.device.type_number(value)
        self.assertEqual(len(self.commands), count)

    def test_adb_failure(self):
        def runner(command, **kwargs):
            return subprocess.CompletedProcess(command, 1, b"", b"device offline")
        with self.assertRaisesRegex(AdbError, "device offline"):
            AdbDevice("test", runner=runner).is_connected()

    def test_fresh_screenshot_avoids_extra_resolution_command(self):
        image = np.zeros((100, 200, 3), np.uint8)
        encoded = cv2.imencode('.png', image)[1].tobytes()
        commands = []
        def runner(command, **kwargs):
            commands.append(command)
            return subprocess.CompletedProcess(command, 0, encoded, b'')
        device = AdbDevice('test', runner=runner)
        device.screenshot()
        device.tap(199, 99)
        self.assertEqual(len(commands), 2)
        with self.assertRaises(ValueError):
            device.tap(200, 99)

    def test_png_round_trip_and_invalid_image(self):
        image = np.zeros((10, 20, 3), dtype=np.uint8)
        image[:, :] = (10, 20, 30)
        success, encoded = cv2.imencode(".png", image)
        self.assertTrue(success)
        np.testing.assert_array_equal(decode_screenshot(encoded.tobytes()), image)
        for data in (b"", b"invalid"):
            with self.assertRaises(ValueError):
                decode_screenshot(data)

    def test_screenshot_timeout_recovers_with_fresh_frame(self):
        image = np.full((10, 20, 3), 70, np.uint8)
        png = cv2.imencode('.png', image)[1].tobytes()
        runner = Mock(side_effect=[subprocess.TimeoutExpired('screencap', 15),
            subprocess.CompletedProcess([], 0, png, b'')])
        notify = Mock()
        with patch('adb.device.time.sleep'):
            device = AdbDevice('test', runner=runner)
            np.testing.assert_array_equal(device.screenshot(on_retry=notify), image)
        self.assertEqual(runner.call_count, 2)
        notify.assert_called_once_with(1, 2)
        self.assertTrue(all(c.args[0][-3:] == ['exec-out', 'screencap', '-p'] for c in runner.call_args_list))

    def test_persistent_screenshot_timeout_is_bounded(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired('screencap', 15))
        with patch('adb.device.time.sleep'), self.assertRaisesRegex(AdbError, 'sau 3 lần'):
            AdbDevice('test', runner=runner).screenshot()
        self.assertEqual(runner.call_count, 3)

    def test_cancel_after_timeout_prevents_retry(self):
        from ui.runner import ControlledDevice, Cancelled
        import threading
        stop = threading.Event()
        def runner(command, **kwargs):
            stop.set()
            raise subprocess.TimeoutExpired(command, 15)
        run = Mock(side_effect=runner)
        device = ControlledDevice(AdbDevice('test', runner=run), stop)
        with self.assertRaises(Cancelled):
            device.screenshot()
        self.assertEqual(run.call_count, 1)

    def test_timed_out_payment_input_is_never_retried(self):
        runner = Mock(side_effect=subprocess.TimeoutExpired('input', 15))
        with self.assertRaises(AdbError):
            AdbDevice('test', runner=runner).type_number(50)
        self.assertEqual(runner.call_count, 1)

    def test_offline_screenshot_retries_reads_without_input(self):
        runner = Mock(return_value=subprocess.CompletedProcess([], 1, b'', b'device offline'))
        with patch('adb.device.time.sleep'), self.assertRaisesRegex(AdbError, 'device offline'):
            AdbDevice('test', runner=runner).screenshot()
        self.assertEqual(runner.call_count, 3)
        self.assertTrue(all(c.args[0][-3:] == ['exec-out', 'screencap', '-p'] for c in runner.call_args_list))


if __name__ == "__main__":
    unittest.main()
