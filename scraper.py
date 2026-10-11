"""Browser access and board parsing for a Selenium Minesweeper client."""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement


UNKNOWN = -1
FLAG = -2


@dataclass(frozen=True)
class Cell:
    row: int
    column: int
    value: int
    element: WebElement


class MinesweeperScraper:
    """Read a Minesweeper board and click cells through Selenium.

    Sites differ in their markup, so the board and cell selectors are supplied
    through constructor arguments or the ``MINESWEEPER_*`` environment vars.
    Cells are expected to expose their state through a class, aria-label, or
    text value such as ``unopened``, ``flag``, or ``3``.
    """

    def __init__(
        self,
        driver: webdriver.Chrome,
        board_selector: str | None = None,
        cell_selector: str | None = None,
    ) -> None:
        self.driver = driver
        self.board_selector = board_selector or os.getenv(
            "MINESWEEPER_BOARD_SELECTOR", ".board"
        )
        self.cell_selector = cell_selector or os.getenv(
            "MINESWEEPER_CELL_SELECTOR", ".cell"
        )

    def read_board(self) -> list[list[Cell]]:
        board = self.driver.find_element(By.CSS_SELECTOR, self.board_selector)
        elements = board.find_elements(By.CSS_SELECTOR, self.cell_selector)
        if not elements:
            raise RuntimeError("No Minesweeper cells matched the configured selector")

        rows: dict[int, list[Cell]] = {}
        for index, element in enumerate(elements):
            row = self._coordinate(element, "row", index)
            column = self._coordinate(element, "col", index)
            rows.setdefault(row, []).append(
                Cell(row, column, self._state(element), element)
            )

        ordered_rows = []
        for row_number in sorted(rows):
            ordered_rows.append(sorted(rows[row_number], key=lambda cell: cell.column))
        width = len(ordered_rows[0])
        if any(len(row) != width for row in ordered_rows):
            raise RuntimeError("Parsed Minesweeper board has uneven rows")
        return ordered_rows

    def click(self, cell: Cell) -> None:
        cell.element.click()

    def flag(self, cell: Cell) -> None:
        self.driver.execute_script(
            "arguments[0].dispatchEvent(new MouseEvent('contextmenu', "
            "{bubbles: true, cancelable: true, button: 2}));",
            cell.element,
        )

    @staticmethod
    def _coordinate(element: WebElement, axis: str, fallback: int) -> int:
        for attribute in (f"data-{axis}", axis):
            value = element.get_attribute(attribute)
            if value is not None and value.isdigit():
                return int(value)
        return fallback

    @staticmethod
    def _state(element: WebElement) -> int:
        raw = " ".join(
            value or ""
            for value in (
                element.get_attribute("class"),
                element.get_attribute("aria-label"),
                element.text,
            )
        ).lower()
        if any(token in raw for token in ("flag", "marked")):
            return FLAG
        if any(token in raw for token in ("unknown", "hidden", "closed", "unopened")):
            return UNKNOWN
        match = re.search(r"\b([0-8])\b", raw)
        if match:
            return int(match.group(1))
        if any(token in raw for token in ("blank", "empty", "revealed", "open")):
            return 0
        raise ValueError(f"Could not determine cell state from: {raw!r}")


def build_driver(headless: bool = False) -> webdriver.Chrome:
    options = webdriver.ChromeOptions()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--window-size=1280,900")
    return webdriver.Chrome(options=options)