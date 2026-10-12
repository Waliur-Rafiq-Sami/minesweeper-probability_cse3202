# Minesweeper AI

A browser-connected Minesweeper analysis assistant. The project reads the visible board from Chrome, applies deterministic Minesweeper constraint reasoning, and displays guidance directly on the board.

The assistant is intentionally **passive**: it does not click cells, place flags, enter values, or control the game. The user makes every move manually. The AI only reads the current board, calculates guidance, and draws red, green, and yellow outlines.

## What AI Is Used?

This project does **not** use an external LLM, OpenAI model, cloud model, neural network, or generative AI API.

The main AI component is the local `MinesweeperAgent` in [solver.py](solver.py). It is a deterministic constraint-solving agent designed specifically for Minesweeper.

### Agent capabilities

The agent:

- Reads opened number clues, hidden cells, and flags.
- Examines the eight neighboring cells around every clue.
- Deduces guaranteed mines.
- Deduces guaranteed-safe cells.
- Tracks confirmed mines and safe cells between board updates.
- Reuses cached analysis when the board has not changed.
- Selects a best candidate when no guaranteed-safe move exists.
- Estimates a local risk for uncertain candidates.
- Resets its internal game knowledge when it detects a new or restarted board.

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
- Calculates board dimensions from cell IDs when available.
- Creates the bottom browser monitor.
- Draws and clears red, green, and yellow outlines.
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

The matrix is used internally by the solver. The browser monitor does not display these values or coordinates to the user.

## Color Meaning

The browser draws outlines around cells after every meaningful board update.

### Red

A red cell is a cell the solver has deduced to be a mine based on the visible clues and known flags.

The AI does not place the flag. The user must right-click or flag it manually in the game.

### Green

A green cell is a cell the solver has deduced to be safe based on the visible clues.

The AI does not open the cell. The user must click it manually.

### Yellow

The yellow cell is the solver's best current recommendation.

Yellow can represent a guaranteed-safe recommendation when one exists. If no guaranteed-safe move exists, it can represent the lowest-risk candidate available from the local clue information. The user decides whether to play it.

## Browser Monitor

The monitor is injected into the game page and fixed to the bottom of the browser window.

It displays:

- `MINESWEEPER AI`
- Number of red mine candidates.
- Number of green safe candidates.
- Whether a yellow recommendation exists.
- A short instruction that the user makes moves manually.
- A color legend.

It does not contain:

- Red, green, yellow, clear, or quit buttons.
- Cell values.
- Cell coordinates.
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
9. Refresh the red, green, and yellow outlines.
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
- Whether the yellow recommendation is guaranteed safe or uncertain.
- Board parsing failures.
- Selenium stale-element retries.
- Shutdown messages.

The terminal is for monitoring. It is not used to submit moves or enter cell values.

## Solver Method

For each open clue, the agent calculates:

1. All neighboring coordinates.
2. Which neighbors are hidden.
3. Which neighbors are already known mines.
4. The remaining mine count.
5. Whether the remaining count proves all hidden neighbors safe.
6. Whether the remaining count proves all hidden neighbors mines.

The deduction rules are:

- Remaining mines equal `0`: all remaining hidden neighbors are safe.
- Remaining mines equal the number of hidden neighbors: all hidden neighbors are mines.

The agent repeats these deductions until no new facts can be found.

If no guaranteed-safe move is available, the agent calculates a local risk estimate for candidate hidden cells. It then selects the lowest-risk candidate using deterministic ordering.

## Memory and Caching

The project uses in-process agent memory through `MinesweeperAgent`.

It remembers:

- The previous board snapshot.
- Confirmed mine coordinates.
- Confirmed safe coordinates.
- AI flag tracking state for compatibility.
- The last analysis result.

When the board matrix is unchanged, the cached analysis is returned instead of running the solver again. This reduces unnecessary work while the user is thinking.

When the board changes, the agent updates its state. If the number of open cells decreases, it treats the situation as a new or restarted game and clears stale deductions.

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
- Risk estimates are local and are not a complete global probability model.
- A yellow recommendation may be uncertain when no safe move can be proven.
- A user flag is trusted as a mine input.
- Changing or restarting the board can invalidate earlier deductions; the agent attempts to detect this and reset.
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
