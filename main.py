import argparse
import time
from scraper import MinesweeperScraper, SiteBlockedError
from solver import MinesweeperAgent


RUN_MODE = "online"
SAFE_MODE = True
OFFLINE_BOARD = [
    [1, "F", 1],
    [1, -1, 1],
    [0, 0, 0],
]


def run_offline():
    """Run the solver without making any network or browser requests."""
    agent = MinesweeperAgent()
    analysis = agent.update(OFFLINE_BOARD)
    print("--- Offline Board ---")
    for row in OFFLINE_BOARD:
        print(row)
    print(f"[AI] Guaranteed safe moves: {sorted(analysis['safe_moves'])}")
    print(f"[AI] Guaranteed mines: {sorted(analysis['mines'])}")
    print(f"[AI] Best move: {analysis['best_move']}")


def run_online():
    scraper = None
    try:
        scraper = MinesweeperScraper("https://minesweeperonline.com/")
        agent = MinesweeperAgent()

        print("[+] Browser opened successfully.")
        print("[*] Make moves manually in the browser; the AI only displays guidance.")

        def read_and_show():
            board = scraper.get_board_matrix()
            if board is None:
                return None
            analysis = agent.update(board)
            safe_moves = set(analysis["safe_moves"])
            mines = set(analysis["mines_to_flag"])
            best_move = analysis["best_move"]
            scraper.highlight_cells(
                safe_moves,
                mines,
                best_move,
                recommended_safe=analysis["best_move_safe"],
                recommended_risk=analysis["best_move_risk"],
            )
            if best_move is None:
                yellow_status = "none"
            elif analysis["best_move_safe"]:
                yellow_status = "PROVABLE SAFE"
            else:
                yellow_status = f"UNCERTAIN, mine risk={analysis['best_move_risk']:.0%}"
            print(
                f"[AI] Ready: red={len(mines)} mine(s), green={len(safe_moves)} safe move(s), "
                f"yellow={yellow_status}"
            )
            print(
                f"[AI] Board {len(board)}x{len(board[0])}: "
                f"flags={len(analysis['flags'])}, hidden={sum(value == -1 for row in board for value in row)}"
            )
            return analysis

        analysis = read_and_show()
        if analysis is None:
            print("[-] The board could not be read. Refresh the game and restart the program.")
            return

        last_signature = scraper.get_board_signature()
        while True:
            current_signature = scraper.get_board_signature()
            if current_signature != last_signature:
                analysis = read_and_show()
                last_signature = current_signature
                if analysis is None:
                    print("[-] The board is no longer available. Restart after refreshing the game.")
                    return
            time.sleep(0.15)
            
    except SiteBlockedError as error:
        print(f"[-] {error}")
        print("[-] Automation stopped. Resolve the restriction through the website's official support process.")
    except KeyboardInterrupt:
        print("\n[*] Shutting down scraper...")
    finally:
        if scraper is not None:
            scraper.close()

def main():
    parser = argparse.ArgumentParser(description="Run the Minesweeper AI assistant.")
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument("--online", action="store_true", help="Use the browser scraper.")
    mode_group.add_argument("--offline", action="store_true", help="Run the solver on the built-in test board.")
    args = parser.parse_args()
    mode = "offline" if args.offline else "online"

    if mode == "offline":
        run_offline()
    elif mode == "online":
        run_online()
    else:
        raise ValueError("RUN_MODE must be 'offline' or 'online'")


if __name__ == "__main__":
    main()