from collections.abc import Iterable

Cell = tuple[int, int]
Board = list[list[int | str]]


def _neighbors(row: int, col: int, rows: int, cols: int) -> Iterable[Cell]:
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if not row_delta and not col_delta:
                continue
            neighbor_row = row + row_delta
            neighbor_col = col + col_delta
            if 0 <= neighbor_row < rows and 0 <= neighbor_col < cols:
                yield neighbor_row, neighbor_col


def analyze_board(
    board: Board,
    known_mines: Iterable[Cell] = (),
    known_safe: Iterable[Cell] = (),
) -> dict[str, object]:
    """Find provably safe cells and mines from the currently visible board."""
    if not board or not board[0]:
        raise ValueError("Board must not be empty")

    rows = len(board)
    cols = len(board[0])
    if any(len(row) != cols for row in board):
        raise ValueError("Board rows must have the same length")

    flagged = {
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if board[row][col] == "F"
    }
    known_mine_cells = set(flagged) | set(known_mines)
    known_safe_cells = set(known_safe) - known_mine_cells

    while True:
        changed = False
        for row in range(rows):
            for col in range(cols):
                value = board[row][col]
                if not isinstance(value, int) or value < 0:
                    continue

                neighbors = set(_neighbors(row, col, rows, cols))
                hidden = {
                    cell
                    for cell in neighbors
                    if board[cell[0]][cell[1]] == -1
                    and cell not in known_mine_cells
                    and cell not in known_safe_cells
                }
                remaining_mines = value - len(neighbors & known_mine_cells)
                if remaining_mines < 0 or remaining_mines > len(hidden):
                    continue
                if remaining_mines == 0:
                    new_safe = hidden - known_safe_cells
                    if new_safe:
                        known_safe_cells.update(new_safe)
                        changed = True
                elif remaining_mines == len(hidden):
                    new_mines = hidden - known_mine_cells
                    if new_mines:
                        known_mine_cells.update(new_mines)
                        changed = True
        if not changed:
            break

    safe_moves = known_safe_cells - flagged
    deduced_mines = known_mine_cells - flagged
    hidden_cells = {
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if board[row][col] == -1
    }
    candidates = hidden_cells - known_mine_cells
    risk_by_cell: dict[Cell, float] = {}
    for row, col in candidates:
        risks = []
        for clue_row, clue_col in _neighbors(row, col, rows, cols):
            clue = board[clue_row][clue_col]
            if not isinstance(clue, int) or clue < 0:
                continue
            clue_neighbors = set(_neighbors(clue_row, clue_col, rows, cols))
            unknown = {
                cell
                for cell in clue_neighbors
                if board[cell[0]][cell[1]] == -1 and cell not in known_mine_cells
            }
            if (row, col) in unknown:
                remaining = clue - len(clue_neighbors & known_mine_cells)
                if unknown:
                    risks.append(max(0.0, min(1.0, remaining / len(unknown))))
        risk_by_cell[(row, col)] = max(risks) if risks else 1.0

    best_move = min(
        safe_moves or candidates,
        key=lambda cell: (0 if cell in safe_moves else 1, risk_by_cell.get(cell, 1.0), cell),
        default=None,
    )
    return {
        "safe_moves": safe_moves,
        "mines": deduced_mines,
        "best_move": best_move,
        "best_move_safe": best_move in safe_moves,
        "best_move_risk": risk_by_cell.get(best_move, 1.0) if best_move else None,
    }


class MinesweeperAgent:
    """Stateful wrapper that avoids re-solving unchanged board states."""

    def __init__(self):
        self.previous_board: tuple[tuple[int | str, ...], ...] | None = None
        self.confirmed_mines: set[Cell] = set()
        self.confirmed_safe: set[Cell] = set()
        self.ai_flags: set[Cell] = set()
        self._cached_analysis: dict[str, object] | None = None

    def update(self, board: Board) -> dict[str, object]:
        board_snapshot = tuple(tuple(row) for row in board)
        current_flags = {
            (row, col)
            for row, values in enumerate(board)
            for col, value in enumerate(values)
            if value == "F"
        }
        hidden_cells = {
            (row, col)
            for row, values in enumerate(board)
            for col, value in enumerate(values)
            if value == -1
        }

        if self._is_new_game(board_snapshot):
            self.confirmed_mines.clear()
            self.confirmed_safe.clear()
            self.ai_flags.clear()
            self._cached_analysis = None

        self.ai_flags &= current_flags
        self.confirmed_mines = (self.confirmed_mines & hidden_cells) | current_flags
        self.confirmed_safe &= hidden_cells

        if board_snapshot == self.previous_board and self._cached_analysis is not None:
            return self._cached_analysis

        analysis = analyze_board(
            board,
            known_mines=self.confirmed_mines,
            known_safe=self.confirmed_safe,
        )
        self.confirmed_mines.update(analysis["mines"])
        self.confirmed_safe.update(analysis["safe_moves"])
        self.confirmed_safe -= self.confirmed_mines
        analysis["flags"] = current_flags
        analysis["user_flags"] = current_flags - self.ai_flags
        analysis["ai_flags"] = current_flags & self.ai_flags
        analysis["mines_to_flag"] = self.confirmed_mines - current_flags
        self.previous_board = board_snapshot
        self._cached_analysis = analysis
        return analysis

    def mark_ai_flags(self, cells: Iterable[Cell]):
        self.ai_flags.update(cells)
    
    def _is_new_game(self, board_snapshot):
        if self.previous_board is None:
            return True
        previous_open = sum(
            value != -1 and value != "F"
            for row in self.previous_board
            for value in row
        )
        current_open = sum(
            value != -1 and value != "F"
            for row in board_snapshot
            for value in row
        )
        return current_open < previous_open 