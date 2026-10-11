"""Run a constraint-based Minesweeper player in a browser."""

from __future__ import annotations

import argparse
import os
import time

from scraper import Cell, MinesweeperScraper, UNKNOWN, FLAG, build_driver


def neighbours(board: list[list[Cell]], row: int, column: int):
    for row_offset in (-1, 0, 1):
        for column_offset in (-1, 0, 1):
            if not row_offset and not column_offset:
                continue
            next_row = row + row_offset
            next_column = column + column_offset
            if 0 <= next_row < len(board) and 0 <= next_column < len(board[0]):
                yield board[next_row][next_column]


def find_moves(board: list[list[Cell]]) -> tuple[set[Cell], set[Cell]]:
    """Return cells proven safe and cells proven to contain mines."""
    safe: set[Cell] = set()
    mines: set[Cell] = set()
    for row in board:
        for cell in row:
            if cell.value < 0:
                continue
            adjacent = list(neighbours(board, cell.row, cell.column))
            unknown = {item for item in adjacent if item.value == UNKNOWN}
            flagged = sum(item.value == FLAG for item in adjacent)
            remaining = cell.value - flagged
            if remaining == 0:
                safe.update(unknown)
            elif remaining == len(unknown):
                mines.update(unknown)
    safe.difference_update(mines)
    return safe, mines


def play(url: str, delay: float, headless: bool) -> None:
    driver = build_driver(headless)
    scraper = MinesweeperScraper(driver)
    try:
        driver.get(url)
        while True:
            board = scraper.read_board()
            safe, mines = find_moves(board)
            for cell in mines:
                scraper.flag(cell)
            if safe:
                for cell in safe:
                    scraper.click(cell)
                time.sleep(delay)
                continue
            if mines:
                time.sleep(delay)
                continue
            raise RuntimeError(
                "No provably safe move exists. Increase solver coverage or choose manually."
            )
    finally:
        driver.quit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url", nargs="?", default=os.getenv("MINESWEEPER_URL"))
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--headless", action="store_true")
    args = parser.parse_args()
    if not args.url:
        parser.error("provide a URL or set MINESWEEPER_URL")
    play(args.url, args.delay, args.headless)


if __name__ == "__main__":
    main()