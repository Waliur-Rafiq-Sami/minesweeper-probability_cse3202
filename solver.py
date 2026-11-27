from collections.abc import Iterable

Cell = tuple[int, int]
Board = list[list[int | str]]
Constraint = tuple[tuple[Cell, ...], int]
MAX_SEARCH_NODES = 100_000
MAX_PROOF_SEARCH_NODES = 10_000
MAX_DERIVED_CONSTRAINTS = 2_000


def _neighbors(row: int, col: int, rows: int, cols: int) -> Iterable[Cell]:
    for row_delta in (-1, 0, 1):
        for col_delta in (-1, 0, 1):
            if not row_delta and not col_delta:
                continue
            neighbor_row = row + row_delta
            neighbor_col = col + col_delta
            if 0 <= neighbor_row < rows and 0 <= neighbor_col < cols:
                yield neighbor_row, neighbor_col


def _enumerate_component(
    cells: set[Cell],
    constraints: list[Constraint],
) -> dict[Cell, float] | None:
    """Return exact mine probabilities, or None when the search limit is reached."""
    constraints_by_cell = {
        cell: [
            index
            for index, (variables, _) in enumerate(constraints)
            if cell in variables
        ]
        for cell in cells
    }
    ordered_cells = sorted(
        cells,
        key=lambda cell: (-len(constraints_by_cell[cell]), cell),
    )
    remaining = [len(variables) for variables, _ in constraints]
    mine_counts = [0] * len(constraints)
    targets = [target for _, target in constraints]
    mine_totals = {cell: 0 for cell in cells}
    assignments = 0
    visited = 0
    exceeded_limit = False

    def search(index: int) -> None:
        nonlocal assignments, visited, exceeded_limit
        if exceeded_limit:
            return
        visited += 1
        if visited > MAX_SEARCH_NODES:
            exceeded_limit = True
            return
        if index == len(ordered_cells):
            assignments += 1
            for cell, value in assigned.items():
                mine_totals[cell] += value
            return

        cell = ordered_cells[index]
        for value in (0, 1):
            valid = True
            affected = constraints_by_cell[cell]
            for constraint_index in affected:
                remaining[constraint_index] -= 1
                mine_counts[constraint_index] += value
                target = targets[constraint_index]
                if (
                    mine_counts[constraint_index] > target
                    or mine_counts[constraint_index] + remaining[constraint_index] < target
                ):
                    valid = False

            assigned[cell] = value
            if valid:
                search(index + 1)
            del assigned[cell]

            for constraint_index in affected:
                remaining[constraint_index] += 1
                mine_counts[constraint_index] -= value
            if exceeded_limit:
                return

    assigned: dict[Cell, int] = {}
    search(0)
    if exceeded_limit:
        return None
    if not assignments:
        return {}
    return {
        cell: mine_totals[cell] / assignments
        for cell in cells
    }


def _find_solution(
    cells: set[Cell],
    constraints: list[Constraint],
    fixed: dict[Cell, int] | None = None,
) -> tuple[bool | None, dict[Cell, int] | None]:
    """Find one valid assignment; None status means the proof search hit its limit."""
    constraints_by_cell = {
        cell: [
            index
            for index, (variables, _) in enumerate(constraints)
            if cell in variables
        ]
        for cell in cells
    }
    visited = 0

    def search(assigned: dict[Cell, int]) -> tuple[bool | None, dict[Cell, int] | None]:
        nonlocal visited
        visited += 1
        if visited > MAX_PROOF_SEARCH_NODES:
            return None, None

        assignment = dict(assigned)
        while True:
            forced: dict[Cell, int] = {}
            for variables, target in constraints:
                assigned_mines = sum(assignment.get(cell, 0) for cell in variables)
                unassigned = [cell for cell in variables if cell not in assignment]
                if (
                    assigned_mines > target
                    or assigned_mines + len(unassigned) < target
                ):
                    return False, None
                if unassigned and (
                    assigned_mines == target
                    or assigned_mines + len(unassigned) == target
                ):
                    value = int(assigned_mines + len(unassigned) == target)
                    for cell in unassigned:
                        previous_value = forced.get(cell)
                        if previous_value is not None and previous_value != value:
                            return False, None
                        forced[cell] = value
            if not forced:
                break
            assignment.update(forced)

        if len(assignment) == len(cells):
            return True, assignment

        cell = max(
            (cell for cell in cells if cell not in assignment),
            key=lambda candidate: (len(constraints_by_cell[candidate]), candidate),
        )
        hit_limit = False
        for value in (0, 1):
            branch = dict(assignment)
            branch[cell] = value
            found, solution = search(branch)
            if found is True:
                return True, solution
            if found is None:
                hit_limit = True
        return (None, None) if hit_limit else (False, None)

    return search(fixed or {})


def _local_estimate(
    cell: Cell,
    board: Board,
    rows: int,
    cols: int,
    known_mines: set[Cell],
    known_safe: set[Cell],
) -> float:
    estimates = []
    direct_forces: set[int] = set()
    for clue_row, clue_col in _neighbors(cell[0], cell[1], rows, cols):
        clue = board[clue_row][clue_col]
        if not isinstance(clue, int) or isinstance(clue, bool) or clue < 0:
            continue
        neighbors = set(_neighbors(clue_row, clue_col, rows, cols))
        unknown = {
            neighbor
            for neighbor in neighbors
            if board[neighbor[0]][neighbor[1]] == -1
            and neighbor not in known_mines
            and neighbor not in known_safe
        }
        if cell in unknown and unknown:
            remaining = clue - len(neighbors & known_mines)
            if 0 <= remaining <= len(unknown) and remaining == 0:
                direct_forces.add(0)
            elif 0 <= remaining <= len(unknown) and remaining == len(unknown):
                direct_forces.add(1)
            if remaining <= 0:
                estimate = 0.01
            elif remaining >= len(unknown):
                estimate = 0.99
            else:
                estimate = remaining / len(unknown)
            estimates.append(max(0.01, min(0.99, estimate)))
    if len(direct_forces) == 1:
        return float(next(iter(direct_forces)))
    return max(estimates) if estimates else 0.5


def _propagate_constraints(
    constraints: list[Constraint],
    known_mines: set[Cell],
    known_safe: set[Cell],
) -> tuple[set[Cell], set[Cell], list[Constraint], bool]:
    mines = set(known_mines)
    safe = set(known_safe) - mines
    pending = constraints
    derived_count = 0

    while True:
        reduced: dict[frozenset[Cell], int] = {}
        forced_mines: set[Cell] = set()
        forced_safe: set[Cell] = set()
        for variables, target in pending:
            remaining_target = target - sum(cell in mines for cell in variables)
            remaining_variables = tuple(
                cell for cell in variables if cell not in mines and cell not in safe
            )
            if not 0 <= remaining_target <= len(remaining_variables):
                return mines, safe, [], True
            if remaining_target == 0:
                forced_safe.update(remaining_variables)
            elif remaining_target == len(remaining_variables):
                forced_mines.update(remaining_variables)
            elif remaining_variables:
                key = frozenset(remaining_variables)
                previous_target = reduced.get(key)
                if previous_target is not None and previous_target != remaining_target:
                    return mines, safe, [], True
                reduced[key] = remaining_target

        if forced_mines & (safe | forced_safe) or forced_safe & mines:
            return mines, safe, [], True

        new_mines = forced_mines - mines
        new_safe = forced_safe - safe
        if not new_mines and not new_safe:
            remaining_constraints = [
                (tuple(sorted(variables)), target)
                for variables, target in reduced.items()
            ]
            additions: dict[frozenset[Cell], int] = {}
            entries = list(reduced.items())
            for index, (left_variables, left_target) in enumerate(entries):
                for right_variables, right_target in entries[index + 1:]:
                    if left_variables < right_variables:
                        difference = right_variables - left_variables
                        difference_target = right_target - left_target
                    elif right_variables < left_variables:
                        difference = left_variables - right_variables
                        difference_target = left_target - right_target
                    else:
                        continue
                    if not 0 <= difference_target <= len(difference):
                        return mines, safe, [], True
                    if not difference:
                        continue
                    previous_target = reduced.get(difference)
                    if previous_target is not None and previous_target != difference_target:
                        return mines, safe, [], True
                    previous_target = additions.get(difference)
                    if previous_target is not None and previous_target != difference_target:
                        return mines, safe, [], True
                    if (
                        difference not in reduced
                        and difference not in additions
                        and derived_count + len(additions) < MAX_DERIVED_CONSTRAINTS
                    ):
                        additions[difference] = difference_target
            if not additions:
                return mines, safe, remaining_constraints, False
            derived_count += len(additions)
            pending = remaining_constraints + [
                (tuple(sorted(variables)), target)
                for variables, target in additions.items()
            ]
            continue

        mines.update(new_mines)
        safe.update(new_safe)
        pending = [
            (tuple(sorted(variables)), target)
            for variables, target in reduced.items()
        ]


def analyze_board(
    board: Board,
    known_mines: Iterable[Cell] = (),
    known_safe: Iterable[Cell] = (),
    total_mines: int | None = None,
) -> dict[str, object]:
    """Compute clue-consistent mine probabilities and certain cells."""
    if not board or not board[0]:
        raise ValueError("Board must not be empty")

    rows = len(board)
    cols = len(board[0])
    if any(len(row) != cols for row in board):
        raise ValueError("Board rows must have the same length")
    if total_mines is not None and (
        isinstance(total_mines, bool) or not isinstance(total_mines, int)
    ):
        raise TypeError("total_mines must be an integer or None")

    flagged = {
        (row, col)
        for row in range(rows)
        for col in range(cols)
        if board[row][col] == "F"
    }
    known_mine_cells = set(known_mines) | flagged
    known_safe_cells = set(known_safe) - known_mine_cells
    trusted_mines = set(known_mine_cells)
    trusted_safe = set(known_safe_cells)
    frontier_cells = {
        neighbor
        for row in range(rows)
        for col in range(cols)
        if isinstance(board[row][col], int)
        and not isinstance(board[row][col], bool)
        and board[row][col] >= 0
        for neighbor in _neighbors(row, col, rows, cols)
        if board[neighbor[0]][neighbor[1]] == -1
    }
    candidates = frontier_cells - known_mine_cells - known_safe_cells

    raw_constraints: list[Constraint] = []
    inconsistent_cells: set[Cell] = set()

    for row in range(rows):
        for col in range(cols):
            clue = board[row][col]
            if not isinstance(clue, int) or isinstance(clue, bool) or clue < 0:
                continue
            neighbors = set(_neighbors(row, col, rows, cols))
            unknown = tuple(sorted(
                cell
                for cell in neighbors
                if board[cell[0]][cell[1]] == -1
                and cell not in known_mine_cells
                and cell not in known_safe_cells
            ))
            remaining_mines = clue - len(neighbors & known_mine_cells)
            if remaining_mines < 0 or remaining_mines > len(unknown):
                inconsistent_cells.update(unknown)
                continue
            if unknown:
                raw_constraints.append((unknown, remaining_mines))
            elif remaining_mines:
                inconsistent_cells.update(neighbors & frontier_cells)

    constraints_by_cell: dict[Cell, list[int]] = {
        cell: [] for cell in frontier_cells
    }
    for index, (variables, _) in enumerate(raw_constraints):
        for cell in variables:
            constraints_by_cell.setdefault(cell, []).append(index)

    unvisited = {cell for cell in frontier_cells if constraints_by_cell.get(cell)}
    proven_mines = set(frontier_cells & known_mine_cells)
    proven_safe = set(frontier_cells & known_safe_cells)
    component_results: dict[Cell, float] = {}
    unresolved_components: set[Cell] = set(inconsistent_cells)

    while unvisited:
        start = min(unvisited)
        component_cells = {start}
        component_constraint_ids: set[int] = set()
        pending = [start]
        while pending:
            cell = pending.pop()
            unvisited.discard(cell)
            for constraint_id in constraints_by_cell.get(cell, []):
                if constraint_id in component_constraint_ids:
                    continue
                component_constraint_ids.add(constraint_id)
                variables = raw_constraints[constraint_id][0]
                for variable in variables:
                    if variable not in component_cells:
                        component_cells.add(variable)
                        pending.append(variable)

        comp_constraints = [
            raw_constraints[index] for index in sorted(component_constraint_ids)
        ]

        if component_cells & inconsistent_cells:
            unresolved_components.update(component_cells)
            continue

        comp_mines, comp_safe, reduced_constraints, comp_inconsistent = _propagate_constraints(
            comp_constraints,
            known_mine_cells & component_cells,
            known_safe_cells & component_cells,
        )

        if comp_inconsistent:
            unresolved_components.update(component_cells)
            continue

        proven_mines.update(comp_mines)
        proven_safe.update(comp_safe)

        remaining_cells = component_cells - comp_mines - comp_safe
        if not remaining_cells or not reduced_constraints:
            continue

        probabilities = _enumerate_component(
            remaining_cells,
            reduced_constraints,
        )
        if probabilities is None:
            found, solution = _find_solution(
                remaining_cells,
                reduced_constraints,
            )
            if found is False or found is None or solution is None:
                unresolved_components.update(remaining_cells)
                continue
            for cell, value in solution.items():
                alternative, _ = _find_solution(
                    remaining_cells,
                    reduced_constraints,
                    {cell: 1 - value},
                )
                if alternative is False:
                    component_results[cell] = float(value)
                else:
                    unresolved_components.add(cell)
        elif not probabilities:
            unresolved_components.update(remaining_cells)
            continue
        else:
            component_results.update(probabilities)

    risk_by_cell: dict[Cell, float] = {
        cell: 1.0 for cell in proven_mines
    }
    risk_by_cell.update({cell: 0.0 for cell in proven_safe})

    remaining_candidates = frontier_cells - proven_mines - proven_safe
    for cell in remaining_candidates:
        if cell in unresolved_components:
            risk_by_cell[cell] = _local_estimate(
                cell,
                board,
                rows,
                cols,
                proven_mines | known_mine_cells,
                proven_safe | known_safe_cells,
            )
        else:
            val = component_results.get(cell, 0.5)
            if val <= 0.001:
                risk_by_cell[cell] = 0.0
            elif val >= 0.999:
                risk_by_cell[cell] = 1.0
            else:
                risk_by_cell[cell] = val

    if total_mines is not None:
        unrevealed_cells = {
            (row, col)
            for row in range(rows)
            for col in range(cols)
            if board[row][col] == -1 and (row, col) not in flagged
        }
        certain_mines = flagged | {
            cell for cell, risk in risk_by_cell.items() if risk >= 0.999
        }
        certain_safe = {
            cell for cell, risk in risk_by_cell.items() if risk <= 0.001
        } - certain_mines
        globally_unresolved = unrevealed_cells - certain_mines - certain_safe
        unresolved_frontier = globally_unresolved & frontier_cells
        remaining_mines = total_mines - len(certain_mines)

        global_constraints_match = 0 <= remaining_mines <= len(globally_unresolved)
        if global_constraints_match and remaining_mines in (
            0,
            len(globally_unresolved),
        ):
            for variables, target in raw_constraints:
                unresolved_variables = set(variables) - certain_mines - certain_safe
                unresolved_target = target - sum(
                    cell in certain_mines for cell in variables
                )
                if (
                    not 0 <= unresolved_target <= len(unresolved_variables)
                    or (
                        remaining_mines == 0
                        and unresolved_target != 0
                    )
                    or (
                        remaining_mines == len(globally_unresolved)
                        and unresolved_target != len(unresolved_variables)
                    )
                ):
                    global_constraints_match = False
                    break

        if global_constraints_match:
            if remaining_mines == 0:
                risk_by_cell.update({cell: 0.0 for cell in unresolved_frontier})
            elif remaining_mines == len(globally_unresolved):
                risk_by_cell.update({cell: 1.0 for cell in unresolved_frontier})

    safe_moves = {
        cell for cell, risk in risk_by_cell.items()
        if risk <= 0.001 and cell not in flagged
    }
    deduced_mines = {
        cell for cell, risk in risk_by_cell.items()
        if risk >= 0.999 and cell not in flagged
    }
    possible_moves = {
        cell for cell, risk in risk_by_cell.items() if risk < 0.999
    }
    best_move = min(
        possible_moves,
        key=lambda cell: (risk_by_cell[cell] > 0.001, risk_by_cell[cell], cell),
        default=None,
    )
    return {
        "safe_moves": safe_moves,
        "mines": deduced_mines,
        "best_move": best_move,
        "best_move_safe": best_move is not None and risk_by_cell[best_move] <= 0.001,
        "best_move_risk": risk_by_cell.get(best_move) if best_move is not None else None,
        "risk_by_cell": risk_by_cell,
    }


class MinesweeperAgent:
    """Stateful wrapper that caches analysis for unchanged board states."""

    def __init__(self):
        self.previous_board: tuple[tuple[int | str, ...], ...] | None = None
        self.previous_total_mines: int | None = None
        self.ai_flags: set[Cell] = set()
        self._cached_analysis: dict[str, object] | None = None

    def update(
        self,
        board: Board,
        total_mines: int | None = None,
    ) -> dict[str, object]:
        board_snapshot = tuple(tuple(row) for row in board)
        current_flags = {
            (row, col)
            for row, values in enumerate(board)
            for col, value in enumerate(values)
            if value == "F"
        }
        self.ai_flags &= current_flags

        if (
            board_snapshot == self.previous_board
            and total_mines == self.previous_total_mines
            and self._cached_analysis is not None
        ):
            return self._cached_analysis

        analysis = analyze_board(board, total_mines=total_mines)
        analysis["flags"] = current_flags
        analysis["user_flags"] = current_flags - self.ai_flags
        analysis["ai_flags"] = current_flags & self.ai_flags
        analysis["mines_to_flag"] = analysis["mines"] - current_flags
        self.previous_board = board_snapshot
        self.previous_total_mines = total_mines
        self._cached_analysis = analysis
        return analysis

    def mark_ai_flags(self, cells: Iterable[Cell]):
        self.ai_flags.update(cells)
