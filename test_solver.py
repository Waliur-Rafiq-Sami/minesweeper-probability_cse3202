import unittest
from unittest.mock import patch

from scraper import _format_risk_percent
from solver import (
    MinesweeperAgent,
    _find_solution,
    _propagate_constraints,
    analyze_board,
)


class AnalyzeBoardTests(unittest.TestCase):
    def test_risk_display_does_not_round_uncertain_cells_to_certain(self):
        self.assertEqual(_format_risk_percent(0.48), "48%")
        self.assertEqual(_format_risk_percent(0.0), "0%")
        self.assertEqual(_format_risk_percent(1.0), "100%")
        self.assertEqual(_format_risk_percent(0.999), "99%")
        self.assertEqual(_format_risk_percent(0.001), "1%")

    def test_only_exact_certainties_are_safe_or_mines(self):
        analysis = analyze_board([[-1, 1, -1]])

        self.assertEqual(analysis["safe_moves"], set())
        self.assertEqual(analysis["mines"], set())
        self.assertEqual(
            analysis["risk_by_cell"],
            {(0, 0): 0.5, (0, 2): 0.5},
        )

    def test_direct_certainty_survives_probability_search_limit(self):
        with patch("solver.MAX_SEARCH_NODES", 0):
            analysis = analyze_board([[1, -1]])

        self.assertEqual(analysis["mines"], {(0, 1)})
        self.assertEqual(analysis["risk_by_cell"], {(0, 1): 1.0})

    def test_subset_constraints_prove_certain_mines(self):
        mines, safe, _, inconsistent = _propagate_constraints(
            [
                (((0, 0), (0, 1)), 1),
                (((0, 0), (0, 1), (0, 2)), 2),
            ],
            set(),
            set(),
        )

        self.assertFalse(inconsistent)
        self.assertIn((0, 2), mines)
        self.assertEqual(safe, set())

    def test_overlapping_wall_clues_prove_end_mines_and_middle_safe(self):
        upper = (13, 21)
        middle = (14, 21)
        lower = (15, 21)
        mines, safe, _, inconsistent = _propagate_constraints(
            [
                ((upper, middle), 1),
                ((upper, middle, lower), 2),
                ((middle, lower), 1),
            ],
            set(),
            set(),
        )

        self.assertFalse(inconsistent)
        self.assertEqual(mines, {upper, lower})
        self.assertEqual(safe, {middle})

    def test_solution_search_proves_cells_forced_by_combined_clues(self):
        cells = {(0, col) for col in range(4)}
        constraints = [
            (((0, 1), (0, 2), (0, 3)), 1),
            (((0, 0), (0, 2), (0, 3)), 1),
            (((0, 0), (0, 1), (0, 3)), 2),
            (((0, 0), (0, 1), (0, 2)), 2),
        ]

        found, solution = _find_solution(cells, constraints)

        self.assertTrue(found)
        self.assertEqual(
            solution,
            {(0, 0): 1, (0, 1): 1, (0, 2): 0, (0, 3): 0},
        )
        for cell, value in solution.items():
            alternative, _ = _find_solution(
                cells,
                constraints,
                {cell: 1 - value},
            )
            self.assertFalse(alternative)

    def test_inconsistent_clues_do_not_leave_partial_certainties(self):
        analysis = analyze_board([[0, -1, 1]])

        self.assertEqual(analysis["safe_moves"], set())
        self.assertEqual(analysis["mines"], set())
        self.assertEqual(analysis["risk_by_cell"], {(0, 1): 0.99})

    def test_only_reports_hidden_cells_adjacent_to_open_clues(self):
        analysis = analyze_board([[-1, 1, -1, -1, -1]])

        self.assertEqual(
            analysis["risk_by_cell"],
            {(0, 0): 0.5, (0, 2): 0.5},
        )

    def test_recomputes_facts_after_reset_with_same_open_cell_count(self):
        agent = MinesweeperAgent()
        previous_board = agent.update([[0, -1]])
        self.assertEqual(previous_board["safe_moves"], {(0, 1)})

        restarted_board = agent.update([[1, -1]])

        self.assertEqual(restarted_board["safe_moves"], set())
        self.assertEqual(restarted_board["mines"], {(0, 1)})
        self.assertEqual(restarted_board["risk_by_cell"], {(0, 1): 1.0})

    def test_trivial_single_cell_clues_detect_100_percent_mines(self):
        # 16x30 grid: (5, 17) has clue 1 with only one hidden neighbor at (5, 18)
        board = [[-1] * 30 for _ in range(16)]
        for r in (4, 5, 6):
            for c in (16, 17, 18):
                if (r, c) != (5, 18):
                    board[r][c] = 1 if (r, c) in [(4, 17), (4, 18), (6, 17), (6, 18)] else 0
        board[5][17] = 1
        analysis = analyze_board(board)
        self.assertIn((5, 18), analysis["mines"])
        self.assertEqual(analysis["risk_by_cell"][(5, 18)], 1.0)

    def test_near_certain_float_probabilities_map_to_safe_and_mines(self):
        board = [[-1, 1, -1]]
        with patch("solver._enumerate_component", return_value={(0, 0): 0.9995, (0, 2): 0.0005}):
            analysis = analyze_board(board)
            self.assertIn((0, 0), analysis["mines"])
            self.assertEqual(analysis["risk_by_cell"][(0, 0)], 1.0)
            self.assertIn((0, 2), analysis["safe_moves"])
            self.assertEqual(analysis["risk_by_cell"][(0, 2)], 0.0)

    def test_local_estimate_keeps_direct_force_despite_invalid_neighbor_clue(self):
        from solver import _local_estimate
        board = [
            [1, "F", 0],
            [1, -1, 2],
            [0, -1, -1],
        ]
        risk = _local_estimate((1, 1), board, 3, 3, {(0, 1)}, set())
        self.assertEqual(risk, 0.0)

    def test_local_estimate_keeps_conflicting_direct_forces_uncertain(self):
        from solver import _local_estimate
        risk = _local_estimate((0, 1), [[0, -1, 1]], 1, 3, set(), set())
        self.assertEqual(risk, 0.99)

    def test_unresolved_component_preserves_direct_single_cell_proofs(self):
        with patch(
            "solver._propagate_constraints",
            return_value=(set(), set(), [], True),
        ):
            mine_analysis = analyze_board([[1, -1]])
            safe_analysis = analyze_board([[0, -1]])

        self.assertEqual(mine_analysis["mines"], {(0, 1)})
        self.assertEqual(mine_analysis["risk_by_cell"], {(0, 1): 1.0})
        self.assertEqual(safe_analysis["safe_moves"], {(0, 1)})
        self.assertEqual(safe_analysis["risk_by_cell"], {(0, 1): 0.0})

    def test_analysis_omits_non_frontier_cells_even_with_total_mines(self):
        board = [
            [1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
            [-1, -1, -1, -1, -1],
        ]
        analysis = analyze_board(board, total_mines=1)

        self.assertEqual(
            set(analysis["risk_by_cell"]),
            {(0, 1), (1, 0), (1, 1)},
        )
        self.assertEqual(analysis["safe_moves"], set())
        self.assertEqual(analysis["mines"], set())
        self.assertIn(analysis["best_move"], {(0, 1), (1, 0), (1, 1)})

    def test_board_without_clues_has_no_frontier_recommendations(self):
        analysis = analyze_board([[-1, -1], [-1, -1]], total_mines=1)

        self.assertEqual(analysis["risk_by_cell"], {})
        self.assertEqual(analysis["safe_moves"], set())
        self.assertEqual(analysis["mines"], set())
        self.assertIsNone(analysis["best_move"])

    def test_total_mines_proves_all_remaining_cells_safe_or_mines(self):
        all_safe = analyze_board([[0, -1], [-1, -1]], total_mines=0)
        all_mines = analyze_board([[3, -1], [-1, -1]], total_mines=3)

        self.assertEqual(all_safe["safe_moves"], {(0, 1), (1, 0), (1, 1)})
        self.assertEqual(
            all_safe["risk_by_cell"],
            {(0, 1): 0.0, (1, 0): 0.0, (1, 1): 0.0},
        )
        self.assertEqual(all_mines["mines"], {(0, 1), (1, 0), (1, 1)})
        self.assertEqual(
            all_mines["risk_by_cell"],
            {(0, 1): 1.0, (1, 0): 1.0, (1, 1): 1.0},
        )

    def test_global_extremes_do_not_override_clue_constraints(self):
        board = [[1, -1], [-1, -1]]

        no_mines = analyze_board(board, total_mines=0)
        all_mines = analyze_board(board, total_mines=3)

        self.assertEqual(set(no_mines["risk_by_cell"].values()), {1 / 3})
        self.assertEqual(set(all_mines["risk_by_cell"].values()), {1 / 3})

    def test_total_mines_counts_flags_and_clue_proven_mines_once(self):
        analysis = analyze_board(
            [
                [0, -1, -1],
                [-1, -1, -1],
                [-1, -1, "F"],
            ],
            total_mines=1,
        )

        self.assertEqual(analysis["mines"], set())
        self.assertEqual(analysis["safe_moves"], {(0, 1), (1, 0), (1, 1)})
        self.assertEqual(
            analysis["risk_by_cell"],
            {(0, 1): 0.0, (1, 0): 0.0, (1, 1): 0.0},
        )

    def test_agent_reanalyzes_unchanged_board_when_mine_count_changes(self):
        agent = MinesweeperAgent()

        safe_analysis = agent.update([[-1, -1]], total_mines=0)
        uncertain_analysis = agent.update([[-1, -1]], total_mines=1)

        self.assertIsNot(safe_analysis, uncertain_analysis)

    def test_unresolved_cell_is_not_falsely_marked_safe(self):
        # Cell (0, 1) is uncertain (could be a mine for the 2)
        # Even if adjacent clue 1 has a flag neighbor, (0, 1) must NOT be safe!
        board = [
            ["F", 1, -1, 2, -1],
        ]
        analysis = analyze_board(board)
        # (0, 2) cannot be proven safe because of the 2
        self.assertNotIn((0, 2), analysis["safe_moves"])
        if (0, 2) in analysis["risk_by_cell"]:
            self.assertGreater(analysis["risk_by_cell"][(0, 2)], 0.001)

    def test_component_contradiction_does_not_wipe_out_independent_deductions(self):
        # Component 1 (left): contradictory clues 0 and 1 touching (0, 1)
        # Component 2 (right): trivial clue 1 at (0, 8) with only neighbor (0, 9)
        board = [[0, -1, 1, 0, 0, 0, 0, 0, 1, -1]]
        analysis = analyze_board(board)
        # (0, 9) is an independent guaranteed mine
        self.assertIn((0, 9), analysis["mines"])
        self.assertEqual(analysis["risk_by_cell"][(0, 9)], 1.0)
        # (0, 1) is contradictory, so not safe and not mine
        self.assertNotIn((0, 1), analysis["safe_moves"])
        self.assertNotIn((0, 1), analysis["mines"])


if __name__ == "__main__":
    unittest.main()
