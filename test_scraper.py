import unittest
from unittest.mock import patch

from scraper import MinesweeperScraper


class CellStateParsingTests(unittest.TestCase):
    def test_prefers_visible_open_clue_over_hidden_cell_type(self):
        self.assertEqual(
            MinesweeperScraper._cell_value("square open1 hdd_type3"),
            1,
        )

    def test_open_zero_is_not_treated_as_hidden(self):
        self.assertEqual(MinesweeperScraper._cell_value("square open0 blank"), 0)

    def test_closed_cell_remains_hidden_even_with_type_metadata(self):
        self.assertEqual(
            MinesweeperScraper._cell_value("square hdd_closed hdd_type1"),
            -1,
        )

    def test_flags_are_recognized_before_other_class_metadata(self):
        self.assertEqual(
            MinesweeperScraper._cell_value("square hdd_flag hdd_type1"),
            "F",
        )

    def test_game_over_bomb_classes_are_not_treated_as_flags_or_hidden(self):
        for class_name in (
            "square bombdeath",
            "square bombmisflagged flagged",
            "square bombrevealed",
        ):
            with self.subTest(class_name=class_name):
                self.assertEqual(MinesweeperScraper._cell_value(class_name), "X")

    def test_correctly_flagged_bomb_remains_a_flag(self):
        self.assertEqual(
            MinesweeperScraper._cell_value("square bombflagged"),
            "F",
        )

    def test_unflagged_covered_blank_is_unrevealed(self):
        self.assertEqual(MinesweeperScraper._cell_value("square blank"), -1)
        self.assertEqual(MinesweeperScraper._cell_value("blank"), -1)

    def test_get_dimensions_handles_transposed_ids(self):
        # 30 unique rows and 16 unique cols should be transposed to 16x30
        cell_ids = [f"{r}_{c}" for r in range(1, 31) for c in range(1, 17)]
        rows, cols = MinesweeperScraper._get_dimensions_from_ids(cell_ids)
        self.assertEqual((rows, cols), (16, 30))

    def test_parses_remaining_mine_counter_digits_and_negative_values(self):
        self.assertEqual(
            MinesweeperScraper._parse_mine_counter(["time1", "time2", "time3"]),
            123,
        )
        self.assertEqual(
            MinesweeperScraper._parse_mine_counter(["time-", "time0", "time2"]),
            -2,
        )
        self.assertIsNone(
            MinesweeperScraper._parse_mine_counter(["time1", "invalid", "time3"])
        )

    def test_stable_signature_waits_for_two_matching_reads(self):
        scraper = object.__new__(MinesweeperScraper)
        with patch.object(
            scraper,
            "get_board_signature",
            side_effect=["updating", "updated", "updated"],
        ), patch("scraper.time.sleep"):
            self.assertEqual(scraper.get_stable_board_signature(), "updated")

    def test_board_signature_tracks_face_game_over_state(self):
        class FakeDriver:
            script = ""

            def execute_script(self, script):
                self.script = script
                return "signature"

        scraper = object.__new__(MinesweeperScraper)
        scraper.driver = FakeDriver()

        scraper.get_board_signature()

        self.assertIn("document.getElementById('face')", scraper.driver.script)
        self.assertIn("mines_ones", scraper.driver.script)


class OverlayRenderingTests(unittest.TestCase):
    def test_highlight_uses_top_left_bars_and_clears_stale_tiles(self):
        class FakeDriver:
            script = ""

            def execute_script(self, script, *arguments):
                self.script = script
                return {"available": True, "element": None}

        scraper = object.__new__(MinesweeperScraper)
        scraper.driver = FakeDriver()
        scraper.highlight_cells(risk_by_cell={(0, 0): 0.5})

        self.assertIn(
            "cell.style.boxShadow = 'inset 3px 0 0 0 ' + color "
            "+ ', inset 0 3px 0 0 ' + color;",
            scraper.driver.script,
        )
        self.assertIn("data-minesweeper-ai-marker", scraper.driver.script)
        self.assertIn("cell.style.backgroundImage = ''", scraper.driver.script)
        self.assertIn("cell.style.boxShadow = ''", scraper.driver.script)
        self.assertIn("cell.style.outline = ''", scraper.driver.script)
        self.assertIn("cell.style.border = ''", scraper.driver.script)
        self.assertIn("bombmisflagged", scraper.driver.script)
        self.assertIn("GAME OVER - highlights cleared", scraper.driver.script)
        self.assertIn("risk <= 0.001", scraper.driver.script)
        self.assertIn("risk >= 0.999", scraper.driver.script)
        self.assertNotIn("inset 0 0 0 2px", scraper.driver.script)
        self.assertNotIn("border-radius:50%", scraper.driver.script)


if __name__ == "__main__":
    unittest.main()
