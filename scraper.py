import time
import re
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


class SiteBlockedError(RuntimeError):
    """Raised when the target site denies access to the browser session."""


class MinesweeperScraper:
    _CELL_SELECTORS = ("#game .square", "#game .cell", ".cell")
    _BLOCKED_MARKERS = (
        "your ip address has been blocked",
        "account blocked",
        "access denied",
    )

    def __init__(self, difficulty_url="https://minesweeperonline.com/"):
        print("[*] Initializing Chrome WebDriver...")
        options = webdriver.ChromeOptions()
        self.driver = webdriver.Chrome(options=options)
        
        self.driver.get(difficulty_url)
        time.sleep(2)
        self._raise_if_blocked()

    def _raise_if_blocked(self):
        is_blocked = self.driver.execute_script(
            "const text = (document.title + '\\n' + "
            "(document.documentElement ? document.documentElement.outerHTML : '')).toLowerCase();"
            "return arguments[0].some(marker => text.includes(marker));",
            self._BLOCKED_MARKERS,
        )
        if is_blocked:
            raise SiteBlockedError(
                "Minesweeper Online has blocked this IP or account. "
                "Stop automation and contact the site's official support team."
            )

    def get_board_matrix(self):
        try:
            result = self.driver.execute_script(
                "const text = (document.title + '\\n' + "
                "(document.documentElement ? document.documentElement.outerHTML : '')).toLowerCase();"
                "if (arguments[1].some(marker => text.includes(marker))) "
                "return {blocked:true, cells:[]};"
                "for (const selector of arguments[0]) {"
                "const cells = Array.from(document.querySelectorAll(selector))"
                ".filter(cell => cell.getClientRects().length && "
                "getComputedStyle(cell).visibility !== 'hidden');"
                "if (cells.length) return {blocked:false, cells:cells.map(cell => [cell.id, cell.className])};"
                "} return {blocked:false, cells:[]};",
                self._CELL_SELECTORS,
                self._BLOCKED_MARKERS,
            )
            if result["blocked"]:
                raise SiteBlockedError(
                    "Minesweeper Online has blocked this IP or account. "
                    "Stop automation and contact the site's official support team."
                )
            cell_data = result["cells"]

            if not cell_data:
                print("[-] Error: Could not find cells on the page.")
                return None

            cell_data.sort(key=lambda cell: self._cell_id_sort_key(cell[0]))
            rows, cols = self._get_dimensions_from_ids(
                [cell_id for cell_id, _ in cell_data]
            )
            if len(cell_data) != rows * cols:
                print(f"[-] Error: Incomplete board ({len(cell_data)} cells for {rows}x{cols}).")
                return None

            board_matrix = []

            for r in range(rows):
                row_data = []
                for c in range(cols):
                    class_tokens = set((cell_data[r * cols + c][1] or "").split())

                    if {"bombflagged", "hdd_flag"} & class_tokens or "flag" in class_tokens:
                        row_data.append("F")
                    else:
                        type_token = next(
                            (token for token in class_tokens if token.startswith("hdd_type") or token.startswith("open")),
                            None,
                        )
                        match = re.search(r"([0-8])", type_token or "")
                        if type_token is None or "blank" in class_tokens or "hdd_closed" in class_tokens:
                            row_data.append(-1)
                        elif "open0" in class_tokens or type_token == "open0":
                            row_data.append(0)
                        elif match:
                            row_data.append(int(match.group(1)))
                        else:
                            row_data.append(-1)
                board_matrix.append(row_data)

            return board_matrix

        except StaleElementReferenceException:
            if getattr(self, "_retrying_board", False):
                print("[-] Board changed too quickly to read safely.")
                return None
            self._retrying_board = True
            try:
                return self.get_board_matrix()
            finally:
                self._retrying_board = False
        except SiteBlockedError:
            raise
        except Exception as e:
            print(f"[-] Error while parsing board DOM: {e}")
            return None

    def _get_cell_elements(self):
        for selector in self._CELL_SELECTORS:
            cells = [
                cell
                for cell in self.driver.find_elements(By.CSS_SELECTOR, selector)
                if cell.is_displayed()
            ]
            if cells:
                return sorted(cells, key=self._cell_sort_key)
        return []

    @staticmethod
    def _cell_sort_key(element):
        return MinesweeperScraper._cell_id_sort_key(element.get_attribute("id") or "")

    @staticmethod
    def _cell_id_sort_key(cell_id):
        match = re.fullmatch(r"(\d+)_(\d+)", cell_id or "")
        return tuple(int(value) for value in match.groups()) if match else (0, 0)

    def _get_dimensions(self, cells):
        return self._get_dimensions_from_ids(
            [cell.get_attribute("id") or "" for cell in cells]
        )

    @staticmethod
    def _get_dimensions_from_ids(cell_ids):
        coordinates = []
        for cell_id in cell_ids:
            match = re.fullmatch(r"(\d+)_(\d+)", cell_id)
            if match:
                coordinates.append(tuple(int(value) for value in match.groups()))

        if coordinates:
            rows = len({row for row, _ in coordinates})
            cols = len({col for _, col in coordinates})
            return rows, cols

        dimensions = {81: (9, 9), 256: (16, 16), 480: (16, 30), 576: (16, 36)}
        try:
            return dimensions[len(cells)]
        except KeyError as error:
            raise ValueError(f"Unsupported board size ({len(cells)} cells)") from error

    def _get_cell(self, row, col):
        cells = self._get_cell_elements()
        rows, cols = self._get_dimensions(cells)
        if not 0 <= row < rows or not 0 <= col < cols:
            raise ValueError(f"Cell ({row}, {col}) is outside the board")
        return cells[row * cols + col]

    def flag_cell(self, row, col):
        try:
            ActionChains(self.driver).context_click(self._get_cell(row, col)).perform()
            return True
        except Exception as e:
            print(f"[-] Could not flag cell ({row}, {col}): {e}")
            return False

    def click_cell(self, row, col):
        try:
            self._get_cell(row, col).click()
            return True
        except Exception as e:
            print(f"[-] Could not click cell ({row}, {col}): {e}")
            return False

    def get_board_signature(self):
        try:
            return self.driver.execute_script(
                "return Array.from(document.querySelectorAll('#game .square, #game .cell, .cell'))"
                ".filter(element => getComputedStyle(element).display !== 'none')"
                ".map(element => element.id + ':' + element.className).join('|');"
            )
        except Exception as e:
            print(f"[-] Could not read board status: {e}")
            return None

    def highlight_cells(
        self,
        safe_cells=(),
        mine_cells=(),
        recommended=None,
        recommended_safe=False,
        recommended_risk=None,
    ):
        try:
            safe_cells = set(safe_cells)
            mine_cells = set(mine_cells)
            if recommended is None:
                yellow_summary = "none"
            elif recommended_safe:
                yellow_summary = "PROVABLE SAFE"
            elif recommended_risk is None:
                yellow_summary = "UNCERTAIN"
            else:
                yellow_summary = f"UNCERTAIN | MINE RISK: {recommended_risk:.0%}"
            summary = (
                f"RED: {len(mine_cells)} mine(s) | "
                f"GREEN: {len(safe_cells)} safe | "
                f"YELLOW: {yellow_summary}"
            )
            recommended_element = self.driver.execute_script(
                "let cells = []; for (const selector of arguments[0]) {"
                "cells = Array.from(document.querySelectorAll(selector))"
                ".filter(cell => cell.getClientRects().length && "
                "getComputedStyle(cell).visibility !== 'hidden');"
                "if (cells.length) break;"
                "}"
                "if (!cells.length) return {available:false, element:null};"
                "const coordinates = cells.map(cell => {"
                "const match = /^(\\d+)_(\\d+)$/.exec(cell.id);"
                "return match ? [Number(match[1]), Number(match[2])] : [0, 0];"
                "});"
                "cells.sort((left, right) => {"
                "const a = /^(\\d+)_(\\d+)$/.exec(left.id);"
                "const b = /^(\\d+)_(\\d+)$/.exec(right.id);"
                "const ar = a ? Number(a[1]) : 0, ac = a ? Number(a[2]) : 0;"
                "const br = b ? Number(b[1]) : 0, bc = b ? Number(b[2]) : 0;"
                "return ar - br || ac - bc;"
                "});"
                "const valid = coordinates.filter(([row, col]) => row && col);"
                "let rows, cols;"
                "if (valid.length) {"
                "rows = new Set(valid.map(([row]) => row)).size;"
                "cols = new Set(valid.map(([, col]) => col)).size;"
                "} else {"
                "const dimensions = {81:[9,9], 256:[16,16], 480:[16,30], 576:[16,36]};"
                "if (!dimensions[cells.length]) throw new Error('Unsupported board size (' + cells.length + ' cells)');"
                "[rows, cols] = dimensions[cells.length];"
                "}"
                "if (cells.length !== rows * cols) throw new Error('Incomplete board (' + cells.length + ' cells for ' + rows + 'x' + cols + ')');"
                "const safe = new Set(arguments[1].map(([row, col]) => row + ',' + col));"
                "const mines = new Set(arguments[2].map(([row, col]) => row + ',' + col));"
                "const best = arguments[3]; let recommendedElement = null;"
                "cells.forEach((cell, index) => {"
                "cell.removeAttribute('data-minesweeper-ai-highlight');"
                "cell.style.outline = ''; cell.style.boxShadow = '';"
                "const key = Math.floor(index / cols) + ',' + (index % cols);"
                "let color, label;"
                "if (best && key === best[0] + ',' + best[1]) {"
                "color = '#fdd835'; label = 'recommended'; recommendedElement = cell;"
                "} else if (mines.has(key)) { color = '#e53935'; label = 'mine';"
                "} else if (safe.has(key)) { color = '#43a047'; label = 'safe'; }"
                "if (color) {"
                "cell.setAttribute('data-minesweeper-ai-highlight', label);"
                "cell.style.outline = '3px solid ' + color;"
                "cell.style.boxShadow = '0 0 8px ' + color;"
                "}"
                "});"
                "let panel = document.getElementById('minesweeper-ai-panel');"
                "if (!panel) {"
                "panel = document.createElement('div'); panel.id = 'minesweeper-ai-panel';"
                "panel.innerHTML = '<strong data-role=title>MINESWEEPER AI</strong>'"
                "+ '<span data-role=summary></span>'"
                "+ '<span data-role=hint>Make your move manually. AI guidance only.</span>'"
                "+ '<span data-role=legend>RED = mine | GREEN = safe | YELLOW = best</span>';"
                "document.body.appendChild(panel); }"
                "panel.querySelector('[data-role=summary]').textContent = arguments[4];"
                "panel.style.cssText = 'position:fixed;z-index:2147483647;left:0;right:0;bottom:0;"
                "background:#111;color:#fff;padding:10px 14px;font:14px monospace;"
                "border-top:3px solid #777;box-sizing:border-box;display:flex;gap:18px;"
                "align-items:center;flex-wrap:wrap;';"
                "panel.querySelector('[data-role=title]').style.cssText = 'font-weight:bold;';"
                "panel.querySelector('[data-role=summary]').style.cssText = 'flex:1;';"
                "panel.querySelector('[data-role=hint]').style.cssText = 'color:#bbb;';"
                "panel.querySelector('[data-role=legend]').style.cssText = 'color:#ddd;';"
                "return {available:true, element:recommendedElement};",
                self._CELL_SELECTORS,
                [list(cell) for cell in safe_cells],
                [list(cell) for cell in mine_cells],
                list(recommended) if recommended is not None else None,
                summary,
            )
            if not recommended_element["available"]:
                print("[-] Could not highlight cells: board is not available.")
                return
            recommended_element = recommended_element["element"]
            if recommended_element is not None:
                ActionChains(self.driver).move_to_element(recommended_element).perform()
        except Exception as e:
            print(f"[-] Could not highlight cells: {e}")

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass