from pathlib import Path
from api_calls import call_api, save_json_to_file

# sleeper states to "use this call sparingly, as it is intended only to be 
# used once per day at most to keep your player IDs updated."


file_path = "src/unmunged/players.json"
players_url = "https://api.sleeper.app/v1/players/nfl"
players_data = call_api(players_url)
if players_data is None or isinstance(players_data, Exception):
    print("Error fetching players data")
    exit(1)
save_json_to_file(players_data, Path(file_path))
print(f"Players data saved to {file_path}")
