import time
import re
from selenium import webdriver
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException


def _format_risk_percent(risk):
    if risk == 0.0:
        return "0%"
    if risk == 1.0:
        return "100%"
    rounded = int(risk * 100 + 0.5)
    return f"{max(1, min(99, rounded))}%"


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

            grid_cells = [
                cell for cell in cell_data
                if re.fullmatch(r"(\d+)_(\d+)", cell[0] or "")
            ]
            if grid_cells:
                cell_data = grid_cells

            cell_data.sort(key=lambda cell: self._cell_id_sort_key(cell[0]))
            rows, cols = self._get_dimensions_from_ids(
                [cell_id for cell_id, _ in cell_data]
            )
            if len(cell_data) != rows * cols:
                print(f"[-] Error: Incomplete board ({len(cell_data)} cells for {rows}x{cols}).")
                return None

            coordinates = [
                self._cell_id_sort_key(cell[0])
                for cell in cell_data
                if self._cell_id_sort_key(cell[0]) != (0, 0)
            ]
            if len(coordinates) == len(cell_data) and coordinates:
                min_r = min(r for r, c in coordinates)
                min_c = min(c for r, c in coordinates)
                r_unique = len({r for r, c in coordinates})
                c_unique = len({c for r, c in coordinates})
                is_transposed = (r_unique > c_unique and (c_unique, r_unique) in [(16, 30), (16, 36)])

                board_matrix = [[-1] * cols for _ in range(rows)]
                for cell_id, class_name in cell_data:
                    raw_r, raw_c = self._cell_id_sort_key(cell_id)
                    if is_transposed:
                        r, c = raw_c - min_c, raw_r - min_r
                    else:
                        r, c = raw_r - min_r, raw_c - min_c
                    if 0 <= r < rows and 0 <= c < cols:
                        board_matrix[r][c] = self._cell_value(class_name)
                return board_matrix

            board_matrix = []

            for r in range(rows):
                row_data = []
                for c in range(cols):
                    row_data.append(
                        self._cell_value(cell_data[r * cols + c][1])
                    )
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

    @staticmethod
    def _cell_value(class_name):
        class_tokens = set((class_name or "").split())
        if {"bombdeath", "bombmisflagged", "bombrevealed"} & class_tokens:
            return "X"
        if {"bombflagged", "hdd_flag"} & class_tokens or "flag" in class_tokens or "flagged" in class_tokens:
            return "F"
        if "hdd_closed" in class_tokens or "closed" in class_tokens or "unopened" in class_tokens:
            return -1

        open_token = next(
            (token for token in class_tokens if re.fullmatch(r"open[0-8]", token)),
            None,
        )
        if open_token is not None:
            return int(open_token[-1])

        type_token = next(
            (token for token in class_tokens if re.fullmatch(r"hdd_type[0-8]", token)),
            None,
        )
        if type_token is not None:
            return int(type_token[-1])

        # Blank/covered cell on Minesweeper Online is "square blank"
        # If it has "blank" without open[0-8], it is UNREVEALED (-1), NOT empty (0)
        return -1

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
            if rows > cols and (cols, rows) in [(16, 30), (16, 36)]:
                return cols, rows
            return rows, cols

        dimensions = {81: (9, 9), 256: (16, 16), 480: (16, 30), 576: (16, 36)}
        try:
            return dimensions[len(cell_ids)]
        except KeyError as error:
            raise ValueError(f"Unsupported board size ({len(cell_ids)} cells)") from error

    def _get_cell(self, row, col):
        direct = self.driver.find_elements(By.ID, f"{row + 1}_{col + 1}")
        if direct and direct[0].is_displayed():
            return direct[0]
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
                "const cells = Array.from(document.querySelectorAll('#game .square, #game .cell, .cell'))"
                ".filter(element => getComputedStyle(element).display !== 'none')"
                ".map(element => element.id + ':' + element.className).join('|');"
                "const counter = ['mines_hundreds', 'mines_tens', 'mines_ones']"
                ".map(id => { const element = document.getElementById(id);"
                "return element ? element.className : ''; }).join('|');"
                "const face = document.getElementById('face') || document.querySelector('.face');"
                "return cells + '#' + counter + '#' + (face ? face.className : '');"
            )
        except Exception as e:
            print(f"[-] Could not read board status: {e}")
            return None

    def get_stable_board_signature(self, interval=0.06, max_checks=10):
        previous = self.get_board_signature()
        for _ in range(max_checks):
            time.sleep(interval)
            current = self.get_board_signature()
            if previous is not None and current == previous:
                return current
            previous = current
        return None

    @staticmethod
    def _parse_mine_counter(class_names):
        if not class_names or len(class_names) != 3:
            return None

        symbols = []
        for class_name in class_names:
            symbol = next(
                (
                    token[4:]
                    for token in (class_name or "").split()
                    if re.fullmatch(r"time(?:-|\d)", token)
                ),
                None,
            )
            if symbol is None:
                return None
            symbols.append(symbol)

        negative = symbols[0] == "-"
        if negative:
            symbols[0] = "0"
        sign = -1 if negative else 1
        return sign * int("".join(symbols))

    def get_remaining_mines(self):
        try:
            class_names = self.driver.execute_script(
                "return ['mines_hundreds', 'mines_tens', 'mines_ones'].map(id => {"
                "const element = document.getElementById(id);"
                "return element ? element.className : null;"
                "});"
            )
            remaining = self._parse_mine_counter(class_names)
            if remaining is None:
                print("[-] Could not parse the remaining-mine counter.")
            return remaining
        except Exception as e:
            print(f"[-] Could not read the remaining-mine counter: {e}")
            return None

    def highlight_cells(
        self,
        safe_cells=(),
        mine_cells=(),
        recommended=None,
        recommended_safe=False,
        recommended_risk=None,
        risk_by_cell=None,
    ):
        try:
            safe_cells = set(safe_cells)
            mine_cells = set(mine_cells)
            risks = dict(risk_by_cell or {})
            for cell in safe_cells:
                risks[cell] = 0.0
            for cell in mine_cells:
                risks[cell] = 1.0
            risk_entries = [
                [row, col, risk]
                for (row, col), risk in sorted(risks.items())
            ]
            risk_text = ",\n".join(
                f"cell [{row},{col}] risk = {_format_risk_percent(risk)}"
                for row, col, risk in risk_entries
            )
            uncertain_count = sum(0.001 < risk < 0.999 for _, _, risk in risk_entries)
            if recommended is None:
                yellow_summary = "none"
            elif recommended_safe:
                yellow_summary = "PROVABLE SAFE"
            elif recommended_risk is None:
                yellow_summary = "UNCERTAIN"
            else:
                yellow_summary = (
                    f"UNCERTAIN | MINE RISK: "
                    f"{_format_risk_percent(recommended_risk)}"
                )
            summary = (
                f"RED: {len(mine_cells)} mine(s) | "
                f"GREEN: {len(safe_cells)} safe | "
                f"YELLOW: {uncertain_count} uncertain | "
                f"BEST: {yellow_summary}"
            )
            recommended_element = self.driver.execute_script(
                "let cells = []; for (const selector of arguments[0]) {"
                "cells = Array.from(document.querySelectorAll(selector))"
                ".filter(cell => cell.getClientRects().length && "
                "getComputedStyle(cell).visibility !== 'hidden');"
                "if (cells.length) break;"
                "}"
                "if (!cells.length) return {available:false, element:null};"
                "const gridOnly = cells.filter(cell => /^(\\d+)_(\\d+)$/.test(cell.id));"
                "if (gridOnly.length) cells = gridOnly;"
                "const face = document.getElementById('face') || document.querySelector('.face');"
                "const faceState = face ? face.className : '';"
                "const faceOver = /(^|[\\s_-])(dead|win|lose)(?:$|[\\s_-])/i.test(faceState);"
                "const gameOverCells = new Set(['bombdeath', 'bombmisflagged', 'bombrevealed']);"
                "const gameOver = faceOver || cells.some(cell => "
                "cell.className.split(/\\s+/).some(token => gameOverCells.has(token)));"
                "const coordinates = [];"
                "for (const cell of cells) {"
                "const match = /^(\\d+)_(\\d+)$/.exec(cell.id);"
                "if (match) coordinates.push([Number(match[1]), Number(match[2])]);"
                "}"
                "let rows, cols, minRow = 0, minCol = 0, isTransposed = false;"
                "if (coordinates.length === cells.length && coordinates.length > 0) {"
                "const rSet = new Set(coordinates.map(([r]) => r));"
                "const cSet = new Set(coordinates.map(([, c]) => c));"
                "minRow = Math.min(...coordinates.map(([r]) => r));"
                "minCol = Math.min(...coordinates.map(([, c]) => c));"
                "rows = rSet.size; cols = cSet.size;"
                "if (rows > cols && (cells.length === 480 || cells.length === 576)) {"
                "isTransposed = true;"
                "const temp = rows; rows = cols; cols = temp;"
                "}"
                "} else {"
                "const dimensions = {81:[9,9], 256:[16,16], 480:[16,30], 576:[16,36]};"
                "if (!dimensions[cells.length]) throw new Error('Unsupported board size (' + cells.length + ' cells)');"
                "[rows, cols] = dimensions[cells.length];"
                "}"
                "if (cells.length !== rows * cols) throw new Error('Incomplete board (' + cells.length + ' cells for ' + rows + 'x' + cols + ')');"
                "const risks = new Map(arguments[1].map(([row, col, risk]) => [row + ',' + col, risk]));"
                "const best = arguments[2]; let recommendedElement = null;"
                "cells.forEach((cell, index) => {"
                "cell.removeAttribute('data-minesweeper-ai-highlight');"
                "const oldMarker = cell.querySelector('[data-minesweeper-ai-marker]');"
                "if (oldMarker) oldMarker.remove();"
                "cell.style.backgroundImage = ''; cell.style.boxShadow = '';"
                "cell.style.outline = ''; cell.style.border = '';"
                "cell.style.position = ''; cell.style.zIndex = '';"
                "const tokens = new Set(cell.className.split(/\\s+/));"
                "const revealed = Array.from(tokens).some(token => "
                "/^open/.test(token) || /^hdd_type/.test(token));"
                "const flagged = tokens.has('bombflagged') || tokens.has('hdd_flag') "
                "|| tokens.has('flag') || tokens.has('flagged');"
                "const ended = gameOver || Array.from(tokens).some(token => gameOverCells.has(token));"
                "if (ended || revealed || flagged) return;"
                "let key;"
                "const match = /^(\\d+)_(\\d+)$/.exec(cell.id);"
                "if (match && coordinates.length === cells.length) {"
                "const rawR = Number(match[1]), rawC = Number(match[2]);"
                "const r = isTransposed ? (rawC - minCol) : (rawR - minRow);"
                "const c = isTransposed ? (rawR - minRow) : (rawC - minCol);"
                "key = r + ',' + c;"
                "} else {"
                "key = Math.floor(index / cols) + ',' + (index % cols);"
                "}"
                "let color, label; const risk = risks.get(key);"
                "if (typeof risk === 'number') {"
                "if (risk <= 0.001) { color = '#43a047'; label = 'safe'; }"
                "else if (risk >= 0.999) { color = '#e53935'; label = 'mine'; }"
                "else { color = '#fdd835'; label = 'uncertain'; }"
                "}"
                "if (best && key === best[0] + ',' + best[1]) recommendedElement = cell;"
                "if (color) {"
                "cell.setAttribute('data-minesweeper-ai-highlight', label);"
                "cell.style.boxShadow = 'inset 3px 0 0 0 ' + color "
                "+ ', inset 0 3px 0 0 ' + color;"
                "}"
                "});"
                "let panel = document.getElementById('minesweeper-ai-panel');"
                "if (!panel) {"
                "panel = document.createElement('div'); panel.id = 'minesweeper-ai-panel';"
                "panel.innerHTML = '<strong data-role=title>MINESWEEPER AI</strong>'"
                "+ '<span data-role=summary></span>'"
                "+ '<span data-role=risks></span>'"
                "+ '<span data-role=hint>Make your move manually. AI guidance only.</span>'"
                "+ '<span data-role=legend>RED = 100% mine | GREEN = 0% risk | YELLOW = uncertain</span>';"
                "document.body.appendChild(panel); }"
                "panel.querySelector('[data-role=summary]').textContent = gameOver "
                "? 'GAME OVER - highlights cleared' : arguments[3];"
                "panel.querySelector('[data-role=risks]').textContent = gameOver ? '' : arguments[4];"
                "panel.style.cssText = 'position:fixed;z-index:2147483647;left:0;right:0;bottom:0;"
                "background:#111;color:#fff;padding:10px 14px;font:14px monospace;"
                "border-top:3px solid #777;box-sizing:border-box;display:flex;gap:18px;"
                "align-items:center;flex-wrap:wrap;';"
                "panel.querySelector('[data-role=title]').style.cssText = 'font-weight:bold;';"
                "panel.querySelector('[data-role=summary]').style.cssText = 'flex:1;';"
                "panel.querySelector('[data-role=risks]').style.cssText = 'flex-basis:100%;max-height:96px;"
                "overflow:auto;white-space:pre-wrap;color:#fdd835;';"
                "panel.querySelector('[data-role=hint]').style.cssText = 'color:#bbb;';"
                "panel.querySelector('[data-role=legend]').style.cssText = 'color:#ddd;';"
                "return {available:true, element:recommendedElement, gameOver:gameOver};",
                self._CELL_SELECTORS,
                risk_entries,
                list(recommended) if recommended is not None else None,
                summary,
                risk_text,
            )
            if not recommended_element["available"]:
                print("[-] Could not highlight cells: board is not available.")
                return
            if recommended_element.get("gameOver"):
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