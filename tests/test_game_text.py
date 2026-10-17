import unittest
from fishing.quest import parse_quest
from vision.game_text import catalog_label


class GameTextTests(unittest.TestCase):
    def test_known_glyph_confusions_and_unknown_labels(self):
        catalog={'Cá ngựa':'seahorse','Cá lóc':'snakehead','Cá rô':'perch'}
        self.assertEqual(catalog_label('cé ngVa',catalog),'seahorse')
        self.assertEqual(catalog_label('ca l6c',catalog),'snakehead')
        self.assertIsNone(catalog_label('ca moi',catalog))
        self.assertIsNone(catalog_label('ro',catalog))
        self.assertIsNone(catalog_label('ca 0',{'ca o':1,'ca 0':2}))

    def test_catalog_never_changes_quantities_or_guesses_unknown_fish(self):
        with self.assertRaises(ValueError):
            parse_quest(['Nhiệm Vụ - 13','Câu 30 con cá ngựa - O/30'])
        task=parse_quest(['Nhiệm Vụ - 13','Câu 30 con cá mới - 0/30'])
        self.assertIsNone(task['targets'][0]['species'])
