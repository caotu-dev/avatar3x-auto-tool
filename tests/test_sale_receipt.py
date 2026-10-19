"""Regression: center is visible briefly before the delayed sale receipt."""
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

import cv2

from fishing.travel import TravelController
from fishing.world import WorldDetector
from tests.test_bot import Clock
from tests.test_travel import ShopDevice


class DelayedSaleDevice(ShopDevice):
    def __init__(self, dropped=0, missing=False, stuck=False):
        super().__init__()
        self.dropped, self.missing, self.stuck = dropped, missing, stuck
        self.pending_frames = self.sale_taps = self.ok_taps = 0

    def screenshot(self):
        folder = Path(__file__).parent / 'fixtures'
        if self.state == 'sale_pending':
            self.pending_frames += 1
            if self.pending_frames <= 4 or self.missing:
                return cv2.imread(str(folder / 'center_right.png'))
            self.state = 'sale_receipt'
        if self.state == 'sale_receipt':
            return cv2.imread(str(folder / 'sale_success.png'))
        return super().screenshot()

    def tap(self, x, y):
        if self.state == 'shop_menu' and y > 300:
            self.sale_taps += 1
            self.state = 'sale_pending'
        elif self.state == 'sale_receipt':
            if abs(x - 798) > 5 or abs(y - 554) > 5:
                raise AssertionError('Must tap the detected receipt OK')
            self.ok_taps += 1
            if self.ok_taps > self.dropped and not self.stuck:
                self.state = 'center_right'
        else:
            super().tap(x, y)


class SaleReceiptTests(unittest.TestCase):
    def run_sale(self, device, buy=False):
        clock = Clock()
        events = []
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
            controller = TravelController(device, Path(folder), clock.read,
                                          lambda seconds: clock.sleep(max(1, seconds)),
                                          on_event=lambda name, details: events.append((name, device.state)))
            result = controller.sell_and_buy(sell=True, buy=buy)
        return result, events

    def test_real_reported_popup_has_detectable_ok(self):
        image = cv2.imread(str(Path(__file__).parent / 'fixtures/sale_success.png'))
        self.assertEqual(WorldDetector().match(image, 'ok').center, (798, 554))

    def test_delayed_popup_is_closed_before_sale_confirmation(self):
        device = DelayedSaleDevice()
        result, events = self.run_sale(device)
        self.assertEqual(result, 0)
        self.assertEqual((device.sale_taps, device.ok_taps), (1, 1))
        self.assertEqual([state for name, state in events if name == 'SALE_CONFIRMED'], ['center_right'])

    def test_dropped_ok_retries_dismissal_without_selling_twice(self):
        device = DelayedSaleDevice(dropped=1)
        _, events = self.run_sale(device)
        self.assertEqual((device.sale_taps, device.ok_taps), (1, 2))
        self.assertEqual(sum(name == 'SALE_CONFIRMED' for name, _ in events), 1)

    def test_buying_can_continue_after_delayed_sale(self):
        device = DelayedSaleDevice()
        result, _ = self.run_sale(device, buy=True)
        self.assertEqual((result, device.sale_taps, device.ok_taps, device.buy_count), (20, 1, 1, 1))

    def test_missing_or_stuck_receipt_never_confirms_sale_or_buys(self):
        for device in (DelayedSaleDevice(missing=True), DelayedSaleDevice(stuck=True)):
            with self.subTest(missing=device.missing):
                events = []
                clock = Clock()
                with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as folder, redirect_stdout(StringIO()):
                    controller = TravelController(device, Path(folder), clock.read,
                                                  lambda seconds: clock.sleep(max(1, seconds)),
                                                  on_event=lambda name, details: events.append(name))
                    with self.assertRaises(RuntimeError):
                        controller.sell_and_buy(sell=True, buy=True)
                self.assertNotIn('SALE_CONFIRMED', events)
                self.assertEqual(device.sale_taps, 1)
                self.assertLessEqual(device.ok_taps, 3)
                self.assertEqual(device.buy_count, 0)
