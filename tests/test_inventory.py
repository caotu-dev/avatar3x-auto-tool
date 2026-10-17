"""Preparation safety and recognition from observed game inventory."""
import copy
import tempfile
import tkinter as tk
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import Mock, patch, call
import numpy as np
import cv2
from fishing.inventory import TICKETS, number, item_kind, ticket_info, ensure_funds, InventoryController, wallet_number
from ui.runner import BotWorker, Options, Cancelled
from gui import App

class InventoryTests(unittest.TestCase):
    def test_snakehead_confirmation_observed_ocr_and_exact_price(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/loc_ticket_confirmation.png'))
        with tempfile.TemporaryDirectory(dir='debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            reader.text=Mock(return_value=['Vé Cäu Cå L6c (5 Ngäy) vdi giå 10000 xu?'])
            self.assertTrue(reader.ticket_confirmation(image,'ca_noc'))
            self.assertFalse(reader.ticket_confirmation(image,'ca_ro'))
            reader.text.return_value=['Vé Cäu Cå L6c (5 Ngäy) vdi giå 1000 xu?']
            changed=image.copy();changed[380:422,950:1085]=255
            self.assertFalse(reader.ticket_confirmation(changed,'ca_noc'))

    def test_snakehead_visual_confirmation_without_ocr(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/loc_ticket_confirmation.png'))
        with tempfile.TemporaryDirectory(dir='debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            reader.text=Mock(return_value=[])
            self.assertTrue(reader.ticket_confirmation(image,'ca_noc'))
            reader.text.assert_not_called()
            for bounds in [(490,380,705,422),(950,380,1085,422),(780,470,820,528)]:
                changed=image.copy();x,y,r,b=bounds;changed[y:b,x:r]=255
                self.assertFalse(reader.ticket_confirmation(changed,'ca_noc'))

    def test_observed_snakehead_title_preserves_product_identity(self):
        self.assertEqual(item_kind(['Vé Cäu Cå Låc', '10.000xu']), ('ticket','ca_noc'))
        self.assertEqual(item_kind(['Vé Câu Cá Rô']), ('ticket','ca_ro'))
        self.assertEqual(item_kind(['Vé Câu Cá Mập']), ('ticket','ca_map'))
        self.assertEqual(item_kind(['Cå Låc', 'Mua']), (None,None))

    def test_shark_confirmation_survives_observed_ocr_errors(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_ticket_confirmation.png'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            reader.text=Mock(return_value=['Vé Cäu Cé M$p (2 Ngäy) vdi gié 2 luqng?'])
            self.assertTrue(reader.ticket_confirmation(image,'ca_map'))
            self.assertFalse(reader.ticket_confirmation(image,'ca_ro'))
            reader.device.screenshot.return_value=image
            self.assertEqual(reader.payment_point('gold'),(662,619))

    def test_shark_confirmation_rejects_changed_price_or_quantity(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_ticket_confirmation.png'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            reader.text=Mock(return_value=['Cé M$p 2 luqng'])
            for bounds in [(970,380,1000,424),(780,470,820,528)]:
                changed=image.copy();x,y,r,b=bounds;changed[y:b,x:r]=255
                self.assertFalse(reader.ticket_confirmation(changed,'ca_map'))

    def test_shark_receipt_identity_requires_visible_product(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/shark_ticket_confirmation.png'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            self.assertTrue(reader.ticket_identity(image,['Vé Cäu Cé M$p'],'ca_map'))
            self.assertFalse(reader.ticket_identity(np.full_like(image,255),['Vé Cäu Cé M$p'],'ca_map'))

    def test_locked_gold_delimits_spendable_gold_on_local_crop(self):
        image=cv2.imread(str(Path(__file__).parent/'fixtures/worm_selected.png'))
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            gold=reader.match(image,'gold_night_symbol')
            self.assertIsNotNone(gold)
            offset=gold.x+gold.width
            locked=reader.match(image[:,offset:],'gold_locked_symbol')
            self.assertIsNotNone(locked)
            self.assertGreater(locked.x,0)
            image=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/wallet_split.png'))
            gold=reader.match(image,'gold_symbol')
            self.assertIsNotNone(gold)
            locked=reader.match(image[:,gold.x+gold.width:],'gold_locked_day_symbol')
            self.assertIsNotNone(locked)

    def test_wallet_rejects_joined_or_malformed_thousands(self):
        self.assertIsNone(wallet_number(['11167232'],'coin'))
        self.assertIsNone(wallet_number(['1.167232'],'coin'))
        self.assertEqual(wallet_number(['1,167.232'],'coin'),1167232)
        self.assertEqual(wallet_number(['264'],'gold'),264)

    def test_dock_empty_buys_only_dock_bait_when_ecological_has_stock(self):
        with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder);state=self.observation(bait=23);state['bait_stocks']['dock']=0
            controller.return_value.chest.return_value=state
            controller.return_value.wallet.return_value=state['wallet']
            def purchase(quantity,wallet):
                worker.shop_event('DOCK_PURCHASE_CONFIRMED',{'quantity':quantity});return quantity
            controller.return_value.buy_dock_bait.side_effect=purchase
            worker.prepare_area('dock')
            controller.return_value.buy_dock_bait.assert_called_once()
            worker.travel.sell_and_buy.assert_not_called()
            self.assertEqual(worker.data['bait_remaining'],23)
            self.assertEqual(worker.data['bait_stocks']['dock'],50)

    def test_ecological_empty_never_uses_existing_dock_bait(self):
        with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder);state=self.observation(bait=0);state['bait_stocks']['dock']=31
            controller.return_value.chest.return_value=state;controller.return_value.wallet.return_value=state['wallet']
            def purchase(**kwargs):
                worker.shop_event('PURCHASE_CONFIRMED',{'quantity':50});return 50
            worker.travel.sell_and_buy.side_effect=purchase
            worker.prepare_area('ca_ro')
            controller.return_value.buy_dock_bait.assert_not_called()
            self.assertEqual(worker.data['bait_remaining'],50)
            self.assertEqual(worker.data['bait_stocks']['dock'],31)

    def test_empty_bait_with_auto_buy_disabled_never_purchases(self):
        from dataclasses import replace
        with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder);worker.options=replace(worker.options,buy=False)
            controller.return_value.chest.return_value=self.observation(bait=0)
            with self.assertRaisesRegex(RuntimeError,'Mồi Trùng'):worker.prepare_area('ca_ro')
            worker.travel.sell_and_buy.assert_not_called();controller.return_value.buy_dock_bait.assert_not_called()

    def test_dock_missing_bait_at_seat_refills_instead_of_changing_rooms(self):
        with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.DockController') as controller:
            worker=self.make_worker(folder);worker.data['bait_remaining']=23;worker.prepare_area=Mock()
            controller.return_value.check.side_effect=[{'status':'OUT_OF_BAIT'},{'status':'READY'}]
            worker.go('dock')
            worker.prepare_area.assert_called_once_with('dock')
            worker.travel.leave_chair.assert_called_once_with('dock')
            self.assertEqual(worker.data['bait_remaining'],23)
            self.assertEqual(worker.data['bait_stocks']['dock'],0)

    def test_dock_still_missing_after_refill_does_not_buy_again(self):
        with tempfile.TemporaryDirectory(dir='debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.DockController') as controller:
            worker=self.make_worker(folder);worker.prepare_area=Mock()
            controller.return_value.check.return_value={'status':'OUT_OF_BAIT'}
            with self.assertRaisesRegex(RuntimeError,'không mua lặp'):worker.go('dock')
            worker.prepare_area.assert_called_once()

    def test_numbers_and_item_names(self):
        self.assertEqual(number('1.614.861'),1614861)
        self.assertEqual(number('264'),264)
        for value in ('', '?', '12 xu', '-1', '1x2'):
            self.assertIsNone(number(value))
        self.assertEqual(item_kind(['VÉ CÂU CÁ LÓC']),('ticket','ca_noc'))
        self.assertEqual(item_kind(['Mồi Câu Cá Trâm']),('bait','dock'))
        self.assertEqual(item_kind(['Mồi Trùng']),('bait','ecological'))
        self.assertEqual(item_kind(['Gỗ']), (None,None))

    def test_observed_ticket_is_active_even_when_date_is_missing_or_today(self):
        today=date(2026,10,11)
        self.assertEqual(ticket_info(['1 3-1 0-2026'],today),{'status':'active','expires_on':'2026-10-13'})
        self.assertEqual(ticket_info(['10-10-2026'],today)['status'],'active')
        self.assertEqual(ticket_info(['11-10-2026'],today)['status'],'active')
        self.assertEqual(ticket_info(['31-02-2026'],today),{'status':'active','expires_on':None})
        self.assertEqual(ticket_info([],today),{'status':'active','expires_on':None})

    def test_currency_is_not_interchangeable(self):
        with self.assertRaisesRegex(RuntimeError,'Không đủ lượng'):
            ensure_funds({'coins':1000000,'gold':1},'gold',2)
        with self.assertRaisesRegex(RuntimeError,'Chưa xác định'):
            ensure_funds({'coins':None},'coins',1000)
        ensure_funds({'coins':12000},'coins',12000)

    def make_worker(self, folder, auto=()):
        worker=BotWorker(Options(free=True,area='ca_ro',auto_tickets=auto,buy=True),Mock(),Mock())
        worker.device.device.screenshot.return_value=np.zeros((900,1600,3),np.uint8)
        worker.travel=Mock()
        worker.travel.world.map_name.return_value='center'
        return worker

    def observation(self, status='active', bait=5):
        return {'tickets':{key:{'status':status,'expires_on':'2099-10-13' if status=='active' else None} for key in TICKETS},
                'bait_stocks':{'ecological':bait,'dock':1},'wallet':{'coins':100000,'gold':264},'scan_complete':True}

    def test_missing_disabled_ticket_stops_before_fishing_or_purchase(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder, patch('ui.runner.ROOT',Path(folder)), patch('ui.runner.MapNavigator'), patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder)
            controller.return_value.chest.return_value=self.observation('missing')
            with self.assertRaisesRegex(RuntimeError,'Bật tự mua'):
                worker.prepare_area('ca_ro')
            controller.return_value.buy_ticket.assert_not_called()
            self.assertIsNone(worker.started)

    def test_enabled_ticket_purchase_uses_start_scan_and_receipt(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder, patch('ui.runner.ROOT',Path(folder)), patch('ui.runner.MapNavigator'), patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder,('ca_ro',))
            controller.return_value.chest.return_value=self.observation('missing')
            controller.return_value.buy_ticket.return_value=self.observation()
            worker.prepare_area('ca_ro')
            controller.return_value.buy_ticket.assert_called_once()
            self.assertEqual(controller.return_value.buy_ticket.call_args.args,('ca_ro',{'coins':100000,'gold':264}))
            self.assertTrue(controller.return_value.buy_ticket.call_args.kwargs['observation']['scan_complete'])
            controller.return_value.chest.assert_called_once()
            self.assertFalse(worker.data['preparing'])
            self.assertIsNotNone(worker.started)

    def test_unreadable_inventory_never_triggers_buy(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder, patch('ui.runner.ROOT',Path(folder)), patch('ui.runner.MapNavigator'), patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder,('ca_ro',))
            controller.return_value.chest.return_value=self.observation('unknown')
            with self.assertRaisesRegex(RuntimeError,'Chưa xác định'):
                worker.prepare_area('ca_ro')
            controller.return_value.buy_ticket.assert_not_called()

    def test_partial_scan_with_known_required_ticket_and_bait_can_continue(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder,('ca_ro',))
            state=self.observation();state['scan_complete']=False
            controller.return_value.chest.return_value=state
            worker.prepare_area('ca_ro')
            controller.return_value.buy_ticket.assert_not_called()
            self.assertIsNotNone(worker.started)

    def test_dock_result_decrements_only_dock_bait(self):
        from fishing.bot import TrialResult
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)):
            worker=self.make_worker(folder)
            worker.data['bait_remaining']=5
            worker.data['bait_stocks']['dock']=50
            worker.record(TrialResult('SUCCESS','ok',1,4,4,'ca_chep','Cá chép',1,'dock',True))
            self.assertEqual(worker.data['bait_remaining'],5)
            self.assertEqual(worker.data['bait_stocks']['dock'],49)
            self.assertEqual(worker.data['counts'],{'ca_chep':1})

    def test_dock_ready_enters_without_old_unverified_gate(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.DockController') as controller:
            worker=self.make_worker(folder)
            controller.return_value.check.return_value={'status':'READY','reason':'ready'}
            worker.go('dock')
            controller.return_value.check.assert_called_once()

    def test_no_bait_updates_from_receipt_without_second_scan(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder, patch('ui.runner.ROOT',Path(folder)), patch('ui.runner.MapNavigator'), patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder)
            controller.return_value.chest.return_value=self.observation(bait=0)
            controller.return_value.wallet.return_value={'coins':99000,'gold':264}
            def purchase(**kwargs):
                worker.shop_event('PURCHASE_PENDING',{'quantity':50})
                worker.shop_event('PURCHASE_CONFIRMED',{'quantity':50,'coins':1000})
                return 50
            worker.travel.sell_and_buy.side_effect=purchase
            worker.prepare_area('ca_ro')
            worker.travel.sell_and_buy.assert_called_once_with(sell=False,buy=True,quantity=50)
            self.assertEqual(worker.data['bait_remaining'],50)
            self.assertEqual(worker.data['wallet']['coins'],99000)
            controller.return_value.chest.assert_called_once()

    def test_multiple_areas_reuse_start_inventory(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder)
            controller.return_value.chest.return_value=self.observation()
            worker.prepare_area('ca_ro');worker.prepare_area('ca_noc');worker.prepare_area('dock')
            controller.return_value.chest.assert_called_once()
            controller.return_value.buy_ticket.assert_not_called()

    def test_cached_owned_ticket_never_scans_or_pays(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            device=Mock();reader=InventoryController(device,Path(folder))
            reader.chest=Mock(side_effect=AssertionError('No repeat chest scan'))
            state=self.observation()
            self.assertEqual(reader.buy_ticket('dock',state['wallet'],observation=state),state)
            device.tap.assert_not_called()

    def test_ticket_receipt_returns_updated_cache_without_rescan(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            reader=InventoryController(Mock(),Path(folder))
            reader.chest=Mock(side_effect=AssertionError('No repeat scan'))
            reader.open_shop=Mock();reader.button=Mock();reader.tap=Mock();reader.event=Mock()
            reader.wait=Mock(return_value=Mock(center=(459,396)))
            def text(image,bounds,name):
                if name=='ticket_shop':return ['Vé câu cá rô','1000 xu']
                if name=='ticket_confirmation':return ['Vé câu cá rô','1000 xu']
                return ['Mua Vé câu cá rô thành công','14-10-2026']
            reader.text=Mock(side_effect=text)
            reader.wallet=Mock(return_value={'coins':100000,'gold':260})
            reader.payment_point=Mock(return_value=(663,620))
            state=self.observation('missing')
            result=reader.buy_ticket('ca_ro',state['wallet'],observation=state)
            self.assertEqual(result['tickets']['ca_ro'],{'status':'active','expires_on':'2026-10-14'})
            self.assertEqual(result['wallet'],{'coins':99000,'gold':260})
            self.assertEqual(state['tickets']['ca_ro']['status'],'missing')
            reader.chest.assert_not_called()
            self.assertEqual(reader.event.call_args_list[-1].args[0],'TICKET_PURCHASE_CONFIRMED')
            self.assertEqual(reader.event.call_args_list[-1].kwargs['wallet']['coins'],99000)

    def test_dock_bait_receipt_updates_stock_without_rescan(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)),patch('ui.runner.MapNavigator'),patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder)
            state=self.observation();state['bait_stocks']['dock']=0
            controller.return_value.chest.return_value=state
            controller.return_value.wallet.return_value={'coins':97500,'gold':264}
            def purchase(quantity,wallet):
                worker.shop_event('PURCHASE_PENDING',{'quantity':quantity})
                worker.shop_event('DOCK_PURCHASE_CONFIRMED',{'quantity':quantity})
                return quantity
            controller.return_value.buy_dock_bait.side_effect=purchase
            worker.prepare_area('dock')
            self.assertEqual(worker.data['bait_stocks']['dock'],50)
            self.assertEqual(worker.data['bait_purchased'],50)
            controller.return_value.chest.assert_called_once()

    def test_ticket_receipt_is_persisted_before_cleanup_disconnect(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder,patch('ui.runner.ROOT',Path(folder)):
            worker=self.make_worker(folder)
            worker.data['purchase_pending']=True
            worker.shop_event('TICKET_PURCHASE_CONFIRMED',{'ticket':'ca_ro','wallet':{'coins':99000,'gold':264}})
            self.assertEqual(worker.data['tickets']['ca_ro']['status'],'active')
            self.assertFalse(worker.data['purchase_pending'])
            self.assertEqual(worker.data['wallet']['coins'],99000)

    def test_no_money_never_buys_bait(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder, patch('ui.runner.ROOT',Path(folder)), patch('ui.runner.MapNavigator'), patch('ui.runner.InventoryController') as controller:
            worker=self.make_worker(folder)
            state=self.observation(bait=0);state['wallet']['coins']=999
            controller.return_value.chest.return_value=state
            with self.assertRaisesRegex(RuntimeError,'Không đủ xu'):
                worker.prepare_area('ca_ro')
            worker.travel.sell_and_buy.assert_not_called()

    def test_pending_ticket_is_persisted_and_only_receipt_clears_it(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder,patch('ui.runner.ROOT',Path(folder)):
            worker=self.make_worker(folder)
            worker.shop_event('TICKET_PURCHASE_PENDING',{'ticket':'ca_ro'})
            self.assertTrue(worker.data['purchase_pending'])
            worker.apply_inventory(self.observation())
            self.assertTrue(worker.data['purchase_pending'])
            worker.shop_event('TICKET_PURCHASE_CONFIRMED',{'ticket':'ca_ro'})
            self.assertFalse(worker.data['purchase_pending'])

    def test_purchase_insufficient_money_sends_no_inputs(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder:
            device=Mock();controller=InventoryController(device,Path(folder))
            with self.assertRaisesRegex(RuntimeError,'Không đủ lượng'):
                controller.buy_ticket('ca_map',{'gold':1})
            device.tap.assert_not_called()

    def test_owned_ticket_is_not_bought_even_by_direct_purchase_call(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            device=Mock();controller=InventoryController(device,Path(folder))
            state=self.observation();controller.chest=Mock(return_value=state)
            self.assertEqual(controller.buy_ticket('dock',state['wallet']),state)
            device.tap.assert_not_called()
            controller.chest.assert_called_once()

    def test_gold_ticket_rechecks_spendable_shop_balance_before_buy(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(Mock(),Path(folder))
            controller.chest=Mock(return_value=self.observation('missing'))
            controller.open_shop=Mock();controller.button=Mock();controller.tap=Mock()
            controller.wait=Mock(return_value=Mock(center=(700,400)))
            controller.text=Mock(return_value=['Vé câu cá mập'])
            controller.wallet=Mock(return_value={'coins':100000,'gold':1})
            with self.assertRaisesRegex(RuntimeError,'Không đủ lượng'):
                controller.buy_ticket('ca_map',{'gold':264})
            controller.wallet.assert_called_once()
            self.assertFalse(any(call.args[0]=='buy' for call in controller.button.call_args_list))

    def test_live_stack_font_reads_single_and_multiple_digits(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(Mock(),Path(folder))
            image=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/live_bottom.png'))
            for col,expected in enumerate((1,10,4,6,195)):
                crop=image[371:403,460+136*col+60:460+136*col+122]
                self.assertEqual(controller.stack_number(crop),expected)
            self.assertIsNone(controller.stack_number(np.zeros((32,62,3),np.uint8)))

    def test_ui_settings_money_ticket_and_preparation_timer(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/"debug") as folder,patch('gui.ROOT',Path(folder)):
            root=tk.Tk();root.withdraw()
            try:
                app=App(root)
                app.show_settings();dialog=app.settings_popup
                dialog.draft['ca_map'].set(True);dialog.save()
                self.assertTrue(app.auto_tickets['ca_map'].get())
                app.show_settings();dialog=app.settings_popup
                dialog.draft['ca_map'].set(False);dialog.cancel()
                self.assertTrue(app.auto_tickets['ca_map'].get())
                data=self.observation();data.update(targets=[],counts={},casts=0,bites=0,misses=0,bait_purchased=0)
                app.messages.put(('progress',data));app.messages.put(('preparation','Đang quét rương…'));app.poll()
                self.assertIsNone(app.timer_started)
                self.assertEqual(app.wallet_values['coins'].get(),'100.000')
                self.assertIn('13-10-2099',app.ticket_values['Vé câu cá rô'].get())
                self.assertTrue(app.preparation_popup.winfo_exists())
                app.messages.put(('prepared',None));app.poll()
                self.assertIsNotNone(app.timer_started)
                self.assertIsNone(app.preparation_popup)
                data['unclassified_results']=1
                app.messages.put(('progress',data));app.poll()
                self.assertEqual(app.metric_values['misses'].get(),'0')
            finally:
                root.destroy()

    def test_grid_scan_handles_selected_white_cells_and_bottom_detection(self):
        base=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/chest_bottom.png'))
        class Device:
            selected=None
            closed=False
            def screenshot(self):
                if self.closed:return np.zeros_like(base)
                image=base.copy()
                if self.selected:
                    col,row=self.selected
                    x,y=460+col*136,(360,497,634)[row]
                    cv2.rectangle(image,(x,y),(x+124,y+124),(0,175,255),4)
                return image
            def tap(self,x,y):
                if x>1450:self.closed=True;return
                self.selected=((x-460)//136,min(range(3),key=lambda row:abs(y-(360,497,634)[row]-62)))
            def swipe(self,*args):pass
        device=Device()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(device,Path(folder),sleep=lambda _:None)
            controller.wallet=Mock(return_value={'coins':1614861,'gold':264})
            def text(image,bounds,name):
                if name.startswith('bait_count'):return ['1']
                if device.selected==(1,1):return ['Vé câu cá lóc','13-10-2026']
                if device.selected==(2,1):return ['Vé câu bến tàu','13-10-2026']
                if device.selected==(1,2):return ['Mồi Câu Cá Trâm']
                return ['Đá quý']
            controller.text=text
            result=controller.chest()
            self.assertTrue(result['scan_complete'])
            self.assertEqual(result['tickets']['ca_noc']['expires_on'],'2026-10-13')
            self.assertEqual(result['tickets']['dock']['expires_on'],'2026-10-13')
            self.assertEqual(result['tickets']['ca_ro']['status'],'missing')
            self.assertEqual(result['bait_stocks'],{'ecological':0,'dock':1})
            self.assertEqual(result['wallet']['gold'],264)
            self.assertTrue(device.closed)

    def test_world_sky_is_not_chest_title(self):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(Mock(),Path(folder))
            screen=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/world.png'))
            self.assertIsNone(controller.match(screen,'chest_title'))

    def test_dropped_first_chest_selection_retries_same_slot(self):
        base=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/chest_bottom.png'))
        selected=base.copy()
        cv2.rectangle(selected,(596,497),(720,621),(0,175,255),4)
        device=Mock()
        device.screenshot.side_effect=[base]*3+[selected]
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(device,Path(folder),sleep=lambda _:None)
            result=controller.select_chest_cell(596,497,125,125)
        self.assertIsNotNone(result)
        self.assertEqual(device.tap.call_args_list,[call(658,559)]*2)

    def test_unconfirmed_selection_stays_unreadable_and_is_bounded(self):
        base=cv2.imread(str(Path(__file__).parent/'fixtures/inventory/chest_bottom.png'))
        device=Mock();device.screenshot.return_value=base
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'debug') as folder:
            controller=InventoryController(device,Path(folder),sleep=lambda _:None)
            self.assertIsNone(controller.select_chest_cell(596,497,125,125))
        self.assertEqual(device.tap.call_count,3)
