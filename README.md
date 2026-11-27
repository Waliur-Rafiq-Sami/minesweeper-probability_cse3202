# Minesweeper AI

A browser-connected Minesweeper analysis assistant. The project reads the visible board from Chrome, applies deterministic Minesweeper constraint reasoning, and displays guidance directly on the board.

The assistant is intentionally **passive**: it does not click cells, place flags, enter values, or control the game. The user makes every move manually. The AI only reads the current board, calculates guidance, and draws red, green, and yellow top-left corner markers on frontier cells.

## What AI Is Used?

This project does **not** use an external LLM, OpenAI model, cloud model, neural network, or generative AI API.

The main AI component is the local `MinesweeperAgent` in [solver.py](solver.py). It is a deterministic constraint-solving agent designed specifically for Minesweeper.

### Agent capabilities

The agent:

- Reads opened number clues, hidden cells, and flags.
- Examines the eight neighboring cells around every clue.
- Deduces guaranteed mines.
- Deduces guaranteed-safe cells.
- Reuses cached analysis when the board has not changed.
- Selects a best candidate when no guaranteed-safe move exists.
- Calculates cell risks from clue-consistent assignments.
- Uses the game's remaining-mine counter to constrain unresolved frontier cells.
- Recomputes deductions from the current board after every change.

### Why an LLM is not used

An LLM would be slower, less predictable, and unnecessary for this problem. Minesweeper clues are structured numeric constraints, so a deterministic solver is faster, reproducible, offline-capable, and safer. The solver never invents a move from language-model guesswork.

## Main Features

- Chrome browser integration through Selenium.
- Supports the current Minesweeper Online board DOM.
- Detects visible square cells and ignores hidden board padding.
- Supports dynamically detected board dimensions.
- Parses hidden, open-number, empty, and flagged cells.
- Passive red, green, and yellow board guidance.
- Bottom browser monitor showing AI progress.
- No action buttons and no terminal command controls.
- No automatic flagging or clicking.
- Detects manual user moves without requiring terminal input.
- Prints useful progress and board information in the terminal.
- Handles stale Selenium elements caused by fast board redraws.
- Detects access restrictions and reports them clearly.
- Includes an offline solver demonstration.

## Project Files

### `main.py`

Application entry point and runtime coordinator.

Responsibilities:

- Selects online or offline mode.
- Creates the `MinesweeperScraper` and `MinesweeperAgent`.
- Runs the passive monitoring loop.
- Detects when the board changes.
- Requests fresh analysis after a user move.
- Prints board dimensions, hidden-cell count, flags, and color counts.
- Shuts down Chrome cleanly with `Ctrl+C`.

The online loop checks the board signature approximately every 0.15 seconds. It does not re-solve unchanged boards because `MinesweeperAgent` caches the last analysis.

### `scraper.py`

Browser and board-DOM integration layer.

Responsibilities:

- Starts Chrome WebDriver.
- Opens `https://minesweeperonline.com/`.
- Detects access-block pages.
- Finds visible board cells.
- Converts DOM classes into a board matrix.
- Reads the visible remaining-mine counter.
- Reads board state and updates all cell highlights in batched browser operations to reduce Selenium round trips.
- Waits for the board and mine counter to stabilize before analyzing changes.
- Clears markers on opened, flagged, or game-over cells.
- Calculates board dimensions from cell IDs when available.
- Creates the bottom browser monitor.
- Draws and clears red, green, and yellow top-left L-bracket markers.
- Computes a lightweight board signature for change detection.
- Retries once when Selenium reports a stale element during a board redraw.
- Closes the browser safely.

The scraper still contains low-level click and flag helper methods for browser integration compatibility, but the current application does not call them. The active online workflow is passive.

### `solver.py`

Local Minesweeper reasoning engine.

Important components:

- `_neighbors(...)`: yields valid neighboring coordinates.
- `analyze_board(...)`: performs constraint deduction and risk scoring.
- `MinesweeperAgent`: maintains state and caches repeated analyses.

### `requirements.txt`

Contains the Selenium dependency:

```text
selenium>=4.15.0
```

### `README.md`

This documentation.

## Board Representation

The scraper converts the web page into a two-dimensional matrix.

| Matrix value    | Meaning                            |
| --------------- | ---------------------------------- |
| `-1`            | Hidden cell                        |
| `0`             | Open empty cell                    |
| `1` through `8` | Open numbered clue                 |
| `"F"`           | Flagged cell detected on the board |

The solver uses row and column coordinates in zero-based form. For example, `(2, 5)` means row 2 and column 5.

The matrix values are used internally by the solver. The risk panel displays hidden cell coordinates in zero-based row, column order.

## Color Meaning

The browser draws top-left L-bracket markers on frontier cells after every stable board update.

### Red

A red cell is a cell the solver has deduced to be a mine based on the visible clues and known flags.

The AI does not place the flag. The user must right-click or flag it manually in the game.

### Green

A green cell has exactly 0% mine risk according to the current clue constraints.

The AI does not open the cell. The user must click it manually.

### Yellow

Only hidden cells adjacent to an opened clue are highlighted. Yellow cells in that group have a mine risk greater than 0% and less than 100%; the panel lists those cells' row, column, and risk percentage. Unopened cells elsewhere on the board are left uncolored.

The monitor and terminal make this distinction explicit:

- `GREEN`: 0% mine risk.
- `RED`: 100% mine risk.
- `YELLOW`: uncertain risk, with the percentage shown beside the cell coordinate.

Exact risks are calculated by enumerating clue-consistent assignments within each connected group of hidden cells. Only hidden cells adjacent to opened clues are reported; deep interior cells are left uncolored. The remaining-mine counter can prove unresolved frontier cells safe or mined. If a group's search exceeds the safety limit or its clues are inconsistent, unresolved values are estimates and are deliberately kept between 1% and 99%; direct clue deductions are retained unless direct clues conflict.

## Browser Monitor

The monitor is injected into the game page and fixed to the bottom of the browser window.

It displays:

- `MINESWEEPER AI`
- Number of red mine candidates.
- Number of green safe candidates.
- Risk percentages for hidden cells adjacent to open clues, formatted as `cell [row,col] risk = N%`.
- A short instruction that the user makes moves manually.
- A color legend.

It does not contain:

- Red, green, yellow, clear, or quit buttons.
- Cell values.
- Automatic-action controls.
- Terminal-command controls.

To stop the program, use `Ctrl+C` in the terminal. The `finally` block closes Chrome.

## Requirements

- Windows PowerShell.
- Python 3.10 or newer recommended.
- Google Chrome installed.
- A working ChromeDriver compatible with the installed Chrome version. Selenium Manager normally resolves this automatically with current Selenium versions.
- Internet access for the online website.
- The project virtual environment created at `venv`.

## Installation

Open PowerShell in the project directory:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If the virtual environment does not exist, create it first:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## Running Online Mode

Start the browser assistant:

```powershell
.\venv\Scripts\Activate.ps1
python main.py
```

The program will:

1. Start Chrome.
2. Open Minesweeper Online.
3. Read the initial board.
4. Add the bottom AI monitor.
5. Print the initial state in the terminal.
6. Wait for the user to play manually in Chrome.
7. Detect the changed board.
8. Recalculate the AI guidance.
9. Refresh the red, green, and yellow markers.
10. Print the new progress information in the terminal.

No Enter key or command input is required after startup.

## Running Offline Mode

Run the built-in solver demonstration without opening Chrome or accessing the network:

```powershell
.\venv\Scripts\python.exe main.py --offline
```

The offline demonstration uses the board defined as `OFFLINE_BOARD` in `main.py` and prints the detected safe moves, known mines, and best move.

## Terminal Output

The terminal reports meaningful state changes, including:

- Browser initialization.
- Site access restrictions.
- Board dimensions.
- Number of flags currently detected.
- Number of hidden cells.
- Number of red mine candidates.
- Number of green safe candidates.
- Number of uncertain yellow cells and the best move's status.
- Board parsing failures.
- Selenium stale-element retries.
- Shutdown messages.

The terminal is for monitoring. It is not used to submit moves or enter cell values.

## Solver Method

The solver first propagates direct clue and subset deductions, then enumerates assignments that satisfy each connected group of hidden cells. This preserves certain mines and safe cells even when a large group reaches the search limit. A cell is green only when every valid assignment makes it safe, and red only when every valid assignment makes it a mine. Other adjacent hidden cells are yellow, with their mine risk shown in the panel. Cells not adjacent to open clues stay uncolored.

## Memory and Caching

The project uses in-process agent memory through `MinesweeperAgent`.

It caches:

- The previous board snapshot.
- AI flag tracking state for compatibility.
- The last analysis result.

When the board matrix is unchanged, the cached analysis is returned instead of running the solver again. This reduces unnecessary work while the user is thinking.

When the board changes, the agent recomputes deductions from the current clues instead of carrying safe or mine claims across board states. This avoids stale deductions surviving a restart where the number of open cells stays the same.

## Safety Model

The application is advisory only.

It does not:

- Click a cell for the user.
- Flag a cell for the user.
- Remove a user flag.
- Enter a board value.
- Guess on behalf of the user.
- Send game moves to a remote AI service.

The user remains responsible for every move. Red, green, and yellow are recommendations generated from the currently visible board state.

## Limitations

- The solver can only reason from visible clues and detected flags.
- Some boards do not contain a mathematically guaranteed safe move.
- The remaining-mine counter constrains global certainty, but probabilities across multiple frontier components are not jointly enumerated.
- Interior cells that do not touch an opened clue are not scored or highlighted.
- Very large or inconsistent connected clue groups can exceed exact analysis; unresolved cells are shown with estimated risk and remain yellow, while unconflicted direct clue proofs are retained.
- A user flag is trusted as a mine input.
- Website DOM changes may require selector updates in `scraper.py`.
- Website access restrictions cannot be bypassed by this project.
- The project depends on Selenium and a compatible Chrome environment.

## Troubleshooting

### Chrome does not open

Verify that the virtual environment is active and Selenium is installed:

```powershell
.\venv\Scripts\python.exe -m pip show selenium
```

Then retry:

```powershell
.\venv\Scripts\python.exe main.py
```

### The browser opens but no cells are detected

Confirm that:

- The Minesweeper page finished loading.
- The game board is visible.
- Chrome is not showing an access-denied page.
- The website has not changed its DOM structure.

The scraper currently checks these selectors:

- `#game .square`
- `#game .cell`
- `.cell`

### The AI shows no red, green, or yellow cells

This can be normal when:

- The board is still completely hidden.
- No clue has been opened yet.
- No guaranteed deduction is available.
- The board has ended or restarted.
- The user has not made a move after the initial scan.

Open a cell manually, then wait for the monitor and terminal to update.

### The monitor is not visible

Check the bottom edge of the Chrome window. The monitor is injected into the game page and uses a fixed bottom position. Refresh the page and restart the program if the website replaced the page DOM.

### The terminal reports a blocked site

The application detects common access-block messages and stops. Resolve the restriction through the website's official support process. Do not attempt to bypass access controls.

### How do I stop the assistant?

Press `Ctrl+C` in the terminal. Chrome is closed by the program's cleanup logic.

## Development Notes

The architecture is intentionally divided into three layers:

```text
main.py
  Runtime coordination and passive monitoring
        |
        v
scraper.py
  Selenium browser access and visual overlays
        |
        v
solver.py
  Deterministic Minesweeper reasoning and cached agent state
```

This separation allows the solver to be tested offline without Chrome and keeps browser-specific behavior out of the reasoning engine.

## License and Website Use

This project is intended for personal, authorized use. Respect the target website's terms, access rules, and rate limits. The application does not attempt to bypass site restrictions.
