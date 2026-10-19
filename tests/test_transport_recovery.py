"""Offline/resource faults recover reads without ever replaying a payment/input."""
import subprocess
import threading
import unittest
from unittest.mock import Mock, patch

import cv2
import numpy as np

from adb.device import AdbDevice, AdbError
from ui.runner import BotWorker, ControlledDevice, Cancelled


class TransportRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.image = np.full((10, 20, 3), 80, np.uint8)
        self.png = cv2.imencode('.png', self.image)[1].tobytes()

    def response(self, error=None):
        return subprocess.CompletedProcess([], int(error is not None),
                                           b'' if error else self.png, error or b'')

    def test_raw_timeout_switches_to_png_and_stays_compressed(self):
        runner = Mock(side_effect=[subprocess.TimeoutExpired('screencap', 15),
                                   self.response(), self.response()])
        device = AdbDevice('test', runner=runner, fast_capture=True)
        with patch('adb.device.time.sleep'):
            np.testing.assert_array_equal(device.screenshot(), self.image)
        np.testing.assert_array_equal(device.screenshot(), self.image)
        self.assertEqual([c.args[0][-1] for c in runner.call_args_list], ['screencap', '-p', '-p'])
        self.assertFalse(device.fast_capture)

    def test_offline_protocol_reset_and_windows_resource_faults_recover(self):
        resource = OSError('Not enough memory resources')
        resource.winerror = 8
        for failure in (self.response(b'error: device offline'),
                        self.response(b'error: protocol fault (connection reset)'), resource):
            with self.subTest(failure=failure), patch('adb.device.time.sleep'):
                runner = Mock(side_effect=[failure, self.response()])
                device = AdbDevice('emulator-5554', runner=runner)
                np.testing.assert_array_equal(device.screenshot(), self.image)
                self.assertEqual(runner.call_count, 2)
                self.assertTrue(all(c.args[0][1:3] == ['-s', 'emulator-5554']
                                    for c in runner.call_args_list))

    def test_resource_failure_on_payment_is_not_retried(self):
        resource = OSError('Not enough memory resources')
        resource.winerror = 8
        runner = Mock(side_effect=resource)
        with self.assertRaises(AdbError):
            AdbDevice('test', runner=runner).type_number(50)
        self.assertEqual(runner.call_count, 1)

    def test_configuration_errors_are_not_retried(self):
        runner = Mock(side_effect=FileNotFoundError('adb.exe missing'))
        with self.assertRaises(AdbError):
            AdbDevice('test', runner=runner).screenshot()
        self.assertEqual(runner.call_count, 1)

    def test_waits_for_device_instead_of_spending_restart_budget(self):
        elapsed = [0.0]
        runner = Mock(side_effect=[self.response(b"device 'test' not found"),
                                   self.response(b'device offline'),
                                   subprocess.CompletedProcess([], 0, b'device\n', b'')])
        device = AdbDevice('test', runner=runner)
        device._size = (1600, 900)
        with patch('adb.device.time.monotonic', side_effect=lambda: elapsed[0]), \
             patch('adb.device.time.sleep', side_effect=lambda seconds: elapsed.__setitem__(0, elapsed[0]+seconds)):
            self.assertTrue(device.wait_connected(timeout=10))
        self.assertGreaterEqual(elapsed[0], 4)
        self.assertIsNone(device._size)
        self.assertTrue(all(c.args[0][-1] == 'get-state' and c.kwargs['timeout'] <= 3
                            for c in runner.call_args_list))

    def test_connection_wait_deadline_and_stop_are_bounded(self):
        elapsed = [0.0]
        runner = Mock(return_value=self.response(b'device offline'))
        device = AdbDevice('test', runner=runner)
        with patch('adb.device.time.monotonic', side_effect=lambda: elapsed[0]), \
             patch('adb.device.time.sleep', side_effect=lambda seconds: elapsed.__setitem__(0, elapsed[0]+seconds)):
            self.assertFalse(device.wait_connected(timeout=5))
        self.assertEqual(runner.call_count, 3)
        stop = threading.Event()
        def offline(*args, **kwargs):
            stop.set()
            return self.response(b'device offline')
        runner.side_effect = offline
        with self.assertRaises(Cancelled):
            ControlledDevice(device, stop).wait_connected()

    def test_transport_error_explanation_does_not_capture_or_ocr_again(self):
        worker = BotWorker.__new__(BotWorker)
        worker.device = Mock()
        reason = 'ADB chụp màn hình timeout sau 3 lần; đã dừng.'
        with patch('fishing.quest.read_ocr') as ocr:
            self.assertEqual(worker.explain_error(reason), reason)
        worker.device.screenshot.assert_not_called()
        ocr.assert_not_called()

    def test_resource_error_explanation_does_not_allocate_another_frame(self):
        worker = BotWorker.__new__(BotWorker)
        worker.device = Mock()
        reason = 'OpenCV: (-4:Insufficient memory) Failed to allocate 5200048 bytes'
        self.assertEqual(worker.explain_error(reason), reason)
        worker.device.screenshot.assert_not_called()

    def test_memory_recovery_releases_cache_and_remains_cancellable(self):
        from tests.test_dashboard_v3 import DashboardTests
        import tempfile
        with tempfile.TemporaryDirectory(dir='debug') as folder:
            worker = DashboardTests().worker(folder, auto_resume=True)
            worker.fishing_presentations = {'ca_ro': object()}
            worker.ready_for_next = ('ca_ro', object())
            worker.stop.wait = Mock(side_effect=lambda _: worker.stop.set())
            def checkpoint():
                if worker.stop.is_set():
                    raise Cancelled()
            worker.checkpoint = checkpoint
            with self.assertRaises(Cancelled):
                worker.recover_error(RuntimeError('WinError 1455: The paging file is too small'))
            self.assertEqual(worker.fishing_presentations, {})
            self.assertIsNone(worker.ready_for_next)
            worker.stop.wait.assert_called_once_with(5)

    def test_persistent_memory_pressure_stops_after_one_recovery_attempt(self):
        from tests.test_dashboard_v3 import DashboardTests
        import tempfile
        with tempfile.TemporaryDirectory(dir='debug') as folder:
            worker=DashboardTests().worker(folder,auto_resume=True,resume_limit=8)
            worker.stop.wait=Mock()
            worker.travel.center=Mock()
            worker.travel.wait=Mock(side_effect=MemoryError('Failed to allocate 11540008 bytes'))
            self.assertFalse(worker.recover_error(RuntimeError('OpenCV: Insufficient memory')))
            self.assertEqual(worker.data['auto_restarts'],1)
            worker.travel.wait.assert_called_once()
            worker.travel.center.assert_not_called()


if __name__ == '__main__':
    unittest.main()
