import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from ui.runner import BotWorker


class WalletRefreshTests(unittest.TestCase):
    def test_unknown_display_balance_backs_off_without_losing_known_currency(self):
        worker=BotWorker.__new__(BotWorker)
        worker.device=Mock();worker.folder=Path('debug/test-wallet')
        worker.data={'wallet':{'coins':None,'gold':259}}
        worker.wallet_refresh_after=0
        with patch('ui.runner.InventoryController') as controller:
            controller.return_value.wallet.return_value={'coins':None,'gold':None}
            with patch('ui.runner.time.monotonic',return_value=100):
                for index in (1,2,3,4):worker.refresh_wallet_display(index)
            self.assertEqual(controller.return_value.wallet.call_count,1)
            self.assertEqual(worker.data['wallet'],{'coins':None,'gold':259})
            controller.return_value.wallet.return_value={'coins':828239,'gold':259}
            with patch('ui.runner.time.monotonic',return_value=221):
                worker.refresh_wallet_display(5)
                worker.refresh_wallet_display(6)
            self.assertEqual(controller.return_value.wallet.call_count,2)
            self.assertEqual(worker.data['wallet']['coins'],828239)

    def test_periodic_refresh_still_updates_known_balance(self):
        worker=BotWorker.__new__(BotWorker)
        worker.device=Mock();worker.folder=Path('debug/test-wallet')
        worker.data={'wallet':{'coins':1000,'gold':259}}
        worker.wallet_refresh_after=1000
        with patch('ui.runner.InventoryController') as controller:
            controller.return_value.wallet.return_value={'coins':1200,'gold':259}
            worker.refresh_wallet_display(19)
            controller.assert_not_called()
            worker.refresh_wallet_display(20)
            self.assertEqual(worker.data['wallet']['coins'],1200)
