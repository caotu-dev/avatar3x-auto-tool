"""Weighted totals and a footer that reserves space in both window modes."""
import unittest

from tests import test_mini_mode
from ui.mission_progress import mission_totals


class MissionTotalsTests(unittest.TestCase):
    def test_weighted_example_and_surplus_clamping(self):
        targets = [{'current': 27, 'required': 30}, {'current': 30, 'required': 30},
                   {'current': 24, 'required': 50}]
        self.assertEqual(mission_totals(targets), (81, 110))
        targets[0]['current'] = 100
        self.assertEqual(mission_totals(targets), (84, 110))
        self.assertEqual(mission_totals([]), (0, 0))
        self.assertEqual(mission_totals([{'current': -3, 'required': 10}]), (0, 10))


class MissionFooterTests(unittest.TestCase):
    setUp = test_mini_mode.MiniModeTests.setUp
    tearDown = test_mini_mode.MiniModeTests.tearDown
    targets = test_mini_mode.MiniModeTests.targets

    def test_animation_preserves_totals_and_stops_when_hidden_complete_or_destroyed(self):
        self.root.attributes('-alpha',0);self.root.deiconify();self.root.update()
        footer=self.app.mission_progress
        footer.set_targets([{'current':3,'required':10}]);self.root.update()
        self.assertEqual(len(footer._frames),6)
        summary=footer.summary.get();job=footer._animation_job
        self.assertIsNotNone(job)
        footer.set_targets([{'current':3,'required':10}])
        self.assertEqual(footer._animation_job,job)
        items=footer.canvas.find_all()
        self.root.after(150,self.root.quit);self.root.mainloop()
        self.assertNotEqual(footer._phase,0)
        self.assertEqual(footer.summary.get(),summary)
        self.assertEqual((footer.completed,footer.required),(3,10))
        self.assertEqual(footer.canvas.find_all(),items)
        self.root.withdraw();self.root.update()
        self.assertIsNone(footer._animation_job)
        self.root.deiconify();self.root.update()
        self.assertIsNotNone(footer._animation_job)
        footer.set_targets([{'current':10,'required':10}])
        self.assertIsNone(footer._animation_job)
        self.assertEqual(len(footer._frames),1)
        footer.set_targets([{'current':0,'required':0}])
        self.assertFalse(footer._frames)
        self.assertIsNone(footer._animation_job)
        footer.set_targets([{'current':1,'required':2}]);job=footer._animation_job
        footer.destroy()
        self.assertIsNone(footer._animation_job)
        self.assertNotIn(job,self.root.tk.call('after','info'))

    def test_footer_values_completion_and_free_fishing(self):
        targets = self.targets()[:3]
        for target, current, required in zip(targets, (27, 30, 24), (30, 30, 50)):
            target.update(current=current, required=required)
        data = {'targets': targets, 'counts': {}}
        self.app.render_progress(data)
        footer = self.app.mission_progress
        self.assertEqual(footer.summary.get(), '81 / 110 cá • 73,6%')
        for target in targets:
            target['current'] = target['required'] + 5
        self.app.render_progress(data)
        self.assertEqual(footer.summary.get(), '110 / 110 cá • 100%')
        self.app.render_progress({'targets': [], 'counts': {'cua': 100}})
        self.assertEqual(footer.summary.get(), '—  Chưa đặt mục tiêu')
        self.assertEqual(footer.required, 0)

    def test_footer_does_not_cover_any_of_thirteen_rows(self):
        from fishing.catch import SPECIES
        self.root.attributes('-alpha', 0)
        self.root.deiconify()
        self.root.geometry('1024x720')
        targets = [{'species': species, 'name': name, 'current': 1, 'required': 10}
                   for species, name in SPECIES.items()]
        self.app.render_progress({'targets': targets, 'counts': {}})
        for mini in (False, True, False):
            if self.app.mini_mode != mini:
                self.app.toggle_mini()
            self.root.update()
            self.app.resize_workspace()
            self.root.update()
            footer, table = self.app.mission_progress, self.app.table
            self.assertTrue(footer.winfo_ismapped())
            self.assertGreaterEqual(footer.winfo_rooty(), table.winfo_rooty() + table.winfo_height())
            last = table.bbox(table.get_children()[-1])
            self.assertTrue(last)
            self.assertLessEqual(last[1] + last[3], table.winfo_height())
            self.assertEqual(self.app.workspace_scrollbar.winfo_manager(), 'pack' if self.app.content.winfo_reqheight() > self.app.workspace_canvas.winfo_height()+2 else '')
            self.assertLessEqual(len(footer.canvas.find_all()), 185)
            signature = footer._draw_signature
            items = footer.canvas.find_all()
            footer.set_targets(targets)
            footer.draw()
            self.assertEqual(footer._draw_signature, signature)
            self.assertEqual(footer.canvas.find_all(), items)


if __name__ == '__main__':
    unittest.main()
