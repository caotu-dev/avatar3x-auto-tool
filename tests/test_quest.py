import unittest

from fishing.quest import parse_quest


class QuestTests(unittest.TestCase):
    def test_real_windows_ocr_and_completed_label(self):
        result = parse_quest([
            "Nhi$m vu hi$n tqi cia bqn lä nhi$m vu:Nhi$m Vu Tho Cäu - 11",
            "- Cäu 30 con cé lia thia - 0/30",
            "- Cäu 30 con cé chim - 7/30",
            "- Cäu 50 con cé ro -Xong", "Phin ThUdng:", "- 5000 xu"])
        self.assertEqual([(row["species"], row["current"], row["required"])
                          for row in result["targets"]],
                         [("ca_lia_thia", 0, 30), ("ca_chim", 7, 30), ("ca_ro", 50, 50)])
        self.assertEqual(result["targets"][0]["area"], "dock")
        self.assertFalse(result["completed"])
        self.assertFalse(result["claimed"])

    def test_invalid_progress_never_becomes_a_saved_task(self):
        for status in ("7/20", "31/30", "?/30"):
            with self.subTest(status=status), self.assertRaises(ValueError):
                parse_quest(["Nhiệm Vụ Thợ Câu - 11", f"Câu 30 con cá chim - {status}"])

    def test_unknown_fish_keeps_name_without_guessing_area(self):
        row = parse_quest(["Nhiệm Vụ Thợ Câu - 12", "Câu 2 con cá mới - 1/2"])["targets"][0]
        self.assertIsNone(row["species"])
        self.assertIsNone(row["area"])


if __name__ == "__main__":
    unittest.main()
