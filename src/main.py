import sys
from pathlib import Path

from api_calls import get_all_seasons, curr_leagueid, call_api, save_json_to_file
from data_processor import process_season

GOAT = 7

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
            "4. Exit", "="*60]
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
        file_path = Path("src/unmunged/players.json")
        players_data = call_api("https://api.sleeper.app/v1/players/nfl")
        if players_data is None or isinstance(players_data, Exception):
            return print("Error fetching players data")
        save_json_to_file(players_data, file_path)
        print(f"Players data saved to {file_path}")
    except Exception as e:
        print(f"\nError importing player data: {e}")

def process_data():
    print("\n[3] Process/munge data for season(s)...")
    unmunged_dir = Path("src/unmunged")
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
            munged_dir = Path("src/munged")
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
        process_season(year, unmunged_dir, Path("src/munged"))
    except KeyboardInterrupt:
        print("\n\nCancelled by user.")
    except Exception as e:
        print(f"\nError processing data: {e}")

def main():
    """Main menu loop."""
    menu_options = {'1': fetch_league_data, '2': import_player_data, '3': process_data}
    while True:
        print_menu()
        try:
            choice = input("\nSelect an option (1-4): ").strip()
            if choice == '4':
                sys.exit(0)
            elif choice in menu_options:
                menu_options[choice]()
            else:
                print(f"\nInvalid option: {choice}. Please select 1-4.")
        except KeyboardInterrupt:
            print("\n\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"\nUnexpected error: {e}")
        input("\nPress Enter to continue...")


if __name__ == "__main__":
    main()

