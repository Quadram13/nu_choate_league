import sys
from pathlib import Path

from api_calls import get_all_seasons, curr_leagueid, call_api, save_json_to_file
from data_processor import process_season
from stats import (
    generate_all_time_standings_csv,
    generate_head_to_head_csv,
    generate_weekly_high_scores_csv,
    generate_player_high_scores_csv
)
from constants import GOAT, MUNGED_DIR, UNMUNGED_DIR

def confirm_action() -> bool:
    """
    there r only about 100 api calls each time the code is run, 
    and not sure if spamming the player import is actually a problem, but just in case...
    """
    try:
        return int(input("How many Super Bowl rings does Tom Brady have? ").strip()) == GOAT
    except ValueError:
        print("Please enter a number. Try again.")
        return False

def print_menu():
    menu = ["="*60, "  Nu Choate League - Data Processing Menu", "="*60,
            "1. Fetch league data from Sleeper API (api_calls)",
            "2. Import/update player data (playerimport)",
            "3. Process/munge data for season(s) (data_processor)",
            "4. Generate all-time standings CSV (all_time_stats)",
            "5. Generate HTML reports (reports)",
            "6. Copy reports to docs/ for GitHub Pages",
            "7. Exit", "="*60]
    print("\n".join(menu))

def fetch_league_data():
    print("\n[1] Fetching league data from Sleeper API...")
    print("Warning: This may make excessive API calls (see README for details).")
    if not confirm_action():
        return print("Cancelled.")
    try:
        get_all_seasons(curr_leagueid)
        print("\nLeague data fetch completed!")
    except Exception as e:
        print(f"\nError fetching league data: {e}")

def import_player_data():
    print("\n[2] Importing/updating player data...")
    print("Warning: Sleeper recommends using this call sparingly")
    print("(at most once per day to keep player IDs updated).")
    if not confirm_action():
        return print("Cancelled.")
    try:
        file_path = Path(f"{UNMUNGED_DIR}/players.json")
        from constants import SLEEPER_PLAYERS_URL
        players_data = call_api(SLEEPER_PLAYERS_URL)
        if players_data is None or isinstance(players_data, Exception):
            return print("Error fetching players data")
        save_json_to_file(players_data, file_path)
        print(f"Players data saved to {file_path}")
    except Exception as e:
        print(f"\nError importing player data: {e}")

def process_data():
    print("\n[3] Process/munge data for season(s)...")
    unmunged_dir = Path(UNMUNGED_DIR)
    if not unmunged_dir.exists():
        return print(f"Error: {unmunged_dir} directory not found")
    
    available_seasons = sorted(
        [item.name for item in unmunged_dir.iterdir()
         if item.is_dir() and item.name.isdigit() and (item / "league_info.json").exists()],
        reverse=True
    )
    if not available_seasons:
        return print("No seasons found in unmunged directory")
    
    print("\nAvailable seasons:")
    for i, season in enumerate(available_seasons, 1):
        print(f"  {i}. {season}")
    print(f"  {len(available_seasons) + 1}. All seasons")
    
    try:
        choice = input(f"\nSelect season (1-{len(available_seasons) + 1}), enter year, or 'all': ").strip().lower()
        
        # Check for "all" option
        if choice == 'all' or choice == str(len(available_seasons) + 1):
            print(f"\nProcessing all {len(available_seasons)} seasons...")
            munged_dir = Path(MUNGED_DIR)
            for year in available_seasons:
                print(f"\n{'='*60}")
                print(f"Processing season {year}...")
                print(f"{'='*60}")
                try:
                    process_season(year, unmunged_dir, munged_dir)
                except Exception as e:
                    print(f"Error processing season {year}: {e}")
                    print("Continuing with next season...")
            print(f"\nCompleted processing all seasons!")
            return
        
        # Handle single season selection
        choice_num = int(choice) if choice.isdigit() else None
        year = (available_seasons[choice_num - 1] if choice_num and 1 <= choice_num <= len(available_seasons)
                else choice if choice in available_seasons else None)
        if not year:
            return print(f"Invalid selection: {choice}")
        print(f"\nProcessing season {year}...")
        process_season(year, unmunged_dir, Path(MUNGED_DIR))
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\nError processing data: {e}")

def generate_standings():
    print("\n[4] Generating all-time standings CSV...")
    unmunged_dir = Path(UNMUNGED_DIR)
    munged_dir = Path(MUNGED_DIR)
    standings_path = Path(f"{MUNGED_DIR}/all_time/standings.csv")
    h2h_path = Path(f"{MUNGED_DIR}/all_time/head_to_head.csv")
    weekly_high_scores_path = Path(f"{MUNGED_DIR}/all_time/weekly_high_scores.csv")
    player_high_scores_path = Path(f"{MUNGED_DIR}/all_time/player_high_scores.csv")
    
    if not unmunged_dir.exists():
        return print(f"Error: {unmunged_dir} directory not found")
    
    if not munged_dir.exists():
        return print(f"Error: {munged_dir} directory not found")
    
    try:
        generate_all_time_standings_csv(unmunged_dir, standings_path)
        print(f"\nStandings CSV generated at {standings_path}")
        generate_head_to_head_csv(unmunged_dir, h2h_path)
        print(f"Head-to-head CSV generated at {h2h_path}")
        generate_weekly_high_scores_csv(munged_dir, weekly_high_scores_path)
        print(f"Weekly high scores CSV generated at {weekly_high_scores_path}")
        generate_player_high_scores_csv(munged_dir, player_high_scores_path)
        print(f"Player high scores CSV generated at {player_high_scores_path}")
    except Exception as e:
        print(f"\nError generating standings: {e}")

def generate_html_reports():
    print("\n[5] Generating HTML reports...")
    try:
        from reports.generator import generate_all_reports
        generate_all_reports()
        print("\nHTML reports generated successfully!")
        from constants import REPORTS_DIR
        print(f"Reports are available in: {REPORTS_DIR}")
    except Exception as e:
        print(f"\nError generating HTML reports: {e}")

def copy_to_docs():
    print("\n[6] Copying reports to docs/ for GitHub Pages...")
    try:
        import sys
        from pathlib import Path
        
        # Add root directory to path to import copy_reports_to_docs
        root_dir = Path(__file__).parent.parent
        if str(root_dir) not in sys.path:
            sys.path.insert(0, str(root_dir))
        
        from copy_reports_to_docs import copy_reports_to_docs
        if copy_reports_to_docs():
            print("\n✅ Reports copied successfully!")
            print("💡 Next steps:")
            print("   1. Commit and push the docs/ folder to GitHub")
            print("   2. Enable GitHub Pages in repository settings")
            print("   3. Select 'Deploy from a branch' -> 'main' -> '/docs'")
        else:
            print("\n❌ Failed to copy reports. Please generate reports first (option 5).")
    except Exception as e:
        print(f"\nError copying reports: {e}")
        import traceback
        traceback.print_exc()

def main():
    """Main menu loop."""
    menu_options = {
        '1': fetch_league_data, 
        '2': import_player_data, 
        '3': process_data, 
        '4': generate_standings, 
        '5': generate_html_reports,
        '6': copy_to_docs
    }
    while True:
        print_menu()
        try:
            choice = input("\nSelect an option (1-7): ").strip()
            if choice == '7':
                sys.exit(0)
            elif choice in menu_options:
                menu_options[choice]()
            else:
                print(f"\nInvalid option: {choice}. Please select 1-7.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"\nUnexpected error: {e}")
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

