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

    def __init__(self, difficulty_url="https://minesweeperonline.com/"):
        print("[*] Initializing Chrome WebDriver...")
        options = webdriver.ChromeOptions()
        self.driver = webdriver.Chrome(options=options)
        
        self.driver.get(difficulty_url)
        time.sleep(2)
        self._raise_if_blocked()

    def _raise_if_blocked(self):
        page_text = f"{self.driver.title}\n{self.driver.page_source}".lower()
        blocked_markers = (
            "your ip address has been blocked",
            "account blocked",
            "access denied",
        )
        if any(marker in page_text for marker in blocked_markers):
            raise SiteBlockedError(
                "Minesweeper Online has blocked this IP or account. "
                "Stop automation and contact the site's official support team."
            )

    def get_board_matrix(self):
        self._raise_if_blocked()
        try:
            cell_elements = self._get_cell_elements()
            
            if not cell_elements:
                print("[-] Error: Could not find cells on the page.")
                return None

            rows, cols = self._get_dimensions(cell_elements)
            if len(cell_elements) != rows * cols:
                print(f"[-] Error: Incomplete board ({len(cell_elements)} cells for {rows}x{cols}).")
                return None

            board_matrix = []
            cell_idx = 0

            for r in range(rows):
                row_data = []
                for c in range(cols):
                    element = cell_elements[cell_idx]
                    class_tokens = set((element.get_attribute("class") or "").split())

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
                    
                    cell_idx += 1
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
        match = re.fullmatch(r"(\d+)_(\d+)", element.get_attribute("id") or "")
        return tuple(int(value) for value in match.groups()) if match else (0, 0)

    def _get_dimensions(self, cells):
        coordinates = []
        for cell in cells:
            match = re.fullmatch(r"(\d+)_(\d+)", cell.get_attribute("id") or "")
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

    def highlight_cells(self, safe_cells=(), mine_cells=(), recommended=None):
        try:
            cells = self._get_cell_elements()
            if not cells:
                print("[-] Could not highlight cells: board is not available.")
                return
            rows, cols = self._get_dimensions(cells)
            safe_cells = set(safe_cells)
            mine_cells = set(mine_cells)
            for row in range(rows):
                for col in range(cols):
                    element = cells[row * cols + col]
                    self.driver.execute_script(
                        "arguments[0].removeAttribute('data-minesweeper-ai-highlight');"
                        "arguments[0].style.outline='';arguments[0].style.boxShadow='';",
                        element,
                    )
                    cell = (row, col)
                    if cell == recommended:
                        color, label = "#fdd835", "recommended"
                    elif cell in mine_cells:
                        color, label = "#e53935", "mine"
                    elif cell in safe_cells:
                        color, label = "#43a047", "safe"
                    else:
                        continue
                    self.driver.execute_script(
                        "arguments[0].setAttribute('data-minesweeper-ai-highlight', arguments[1]);"
                        "arguments[0].style.outline='3px solid ' + arguments[2];"
                        "arguments[0].style.boxShadow='0 0 8px ' + arguments[2];",
                        element, label, color,
                    )
            summary = (
                f"RED: {len(mine_cells)} mine(s) | "
                f"GREEN: {len(safe_cells)} safe | "
                f"YELLOW: {'ready' if recommended is not None else 'none'}"
            )
            self.driver.execute_script(
                "let panel = document.getElementById('minesweeper-ai-panel');"
                "if (!panel) {"
                "panel = document.createElement('div'); panel.id = 'minesweeper-ai-panel';"
                "panel.innerHTML = '<strong data-role=title>MINESWEEPER AI</strong>'"
                "+ '<span data-role=summary></span>'"
                "+ '<span data-role=hint>Make your move manually. AI guidance only.</span>'"
                "+ '<span data-role=legend>RED = mine | GREEN = safe | YELLOW = best</span>';"
                "document.body.appendChild(panel); }"
                "panel.querySelector('[data-role=summary]').textContent = arguments[0];"
                "panel.style.cssText = 'position:fixed;z-index:2147483647;left:0;right:0;bottom:0;"
                "background:#111;color:#fff;padding:10px 14px;font:14px monospace;"
                "border-top:3px solid #777;box-sizing:border-box;display:flex;gap:18px;"
                "align-items:center;flex-wrap:wrap;';"
                "panel.querySelector('[data-role=title]').style.cssText = 'font-weight:bold;';"
                "panel.querySelector('[data-role=summary]').style.cssText = 'flex:1;';"
                "panel.querySelector('[data-role=hint]').style.cssText = 'color:#bbb;';"
                "panel.querySelector('[data-role=legend]').style.cssText = 'color:#ddd;';",
                summary,
            )
            if recommended is not None:
                ActionChains(self.driver).move_to_element(self._get_cell(*recommended)).perform()
        except Exception as e:
            print(f"[-] Could not highlight cells: {e}")

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass