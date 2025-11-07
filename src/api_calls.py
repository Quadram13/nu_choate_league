import requests
import json
from pathlib import Path
from typing import Optional, Tuple


# try not to spam api calls, as sleeper warns that you may be ip-blocked if you do.


curr_leagueid = '1251998020954763264'

def call_api(url: str) -> Optional[dict]:
    # http api get, return json
    try:
        response = requests.get(url)
        response.raise_for_status()
        return response.json()
    except (requests.exceptions.HTTPError, requests.exceptions.RequestException, json.JSONDecodeError) as e:
        return e

def save_json_to_file(data: dict, output_path: Path) -> None:
    # sep from get_and_save bc of peepeepoopoo league_info get
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(data, f, indent=4)

def get_and_save_api_data(url: str, output_path: Path) -> bool:
    # this part may be refactored when implementing data munging
    data = call_api(url)
    if data is None or isinstance(data, Exception):
        return False
    save_json_to_file(data, output_path)
    return True


def save_league_info(league_id: str) -> Optional[Tuple[str, bool, Optional[str]]]:
    # func called for each indiv season
    base_league_url = f"https://api.sleeper.app/v1/league/{league_id}"
    league_info = call_api(base_league_url)
    if league_info is None or isinstance(league_info, Exception):
        return None

    season = league_info.get('season')
    latest_week = league_info.get('settings', {}).get('last_scored_leg', 0)
    previous_league_id = league_info.get('previous_league_id')
    draft_id = league_info.get('draft_id')

    output_dir = Path(f"src/unmunged/{season}")
    output_dir.mkdir(parents=True, exist_ok=True)
    save_json_to_file(league_info, output_dir / "league_info.json")
    # ^aforementioned peepeepoopoo block

    # single files per season
    static_endpoints = [
        ("/rosters", 'rosters.json'),
        ("/users", 'users.json'),
        ("/winners_bracket", 'playoffs_winnersbracket.json'),
        ("/losers_bracket", 'playoffs_losersbracket.json'),
        ("/drafts", 'draft.json')
    ]

    for endpoint_suffix, filename in static_endpoints:
        url = f"{base_league_url}{endpoint_suffix}"
        output_path = output_dir / filename
        if not get_and_save_api_data(url, output_path):
            return None

    # bandage for handling draft picks bc the sleeper api is a silly goose
    drafts_path = output_dir / "draft.json"
    if drafts_path.exists():
        with open(drafts_path, 'r') as f:
            drafts = json.load(f)
        
        for draft in drafts:
            draft_id = draft.get('draft_id')
            if draft_id:
                picks_url = f"https://api.sleeper.app/v1/draft/{draft_id}/picks"
                picks_data = call_api(picks_url)
                if picks_data is not None and not isinstance(picks_data, Exception):
                    draft['picks'] = picks_data
                else:
                    draft['picks'] = []
        
        save_json_to_file(drafts, drafts_path)


    # files for each week in season
    weekly_endpoints = [
        ("/matchups", 'matchups.json'),
        ("/transactions", 'transactions.json')
    ]
    
    for week in range(1, latest_week + 1):
        week_dir = output_dir / f"week_{week}"
        for endpoint_suffix, filename in weekly_endpoints:
            url = f"{base_league_url}{endpoint_suffix}/{week}"
            output_path = week_dir / filename
            if not get_and_save_api_data(url, output_path):
                return None

    # kinda silly since we've only used sleeper for 2 years, but whatever
    has_previous_league = previous_league_id is not None
    return season, has_previous_league, previous_league_id

def get_all_seasons(latest_leagueid: str) -> None:
    #traverse thru all seasons of league
    result = save_league_info(latest_leagueid)
    if result is None:
        return
    
    season, has_previous_league, previous_league_id = result
    print(f"Season: {season}, Has previous league: {has_previous_league}, Previous league id: {previous_league_id}")
    
    while has_previous_league and previous_league_id:
        result = save_league_info(previous_league_id)
        if result is None:
            break
        season, has_previous_league, previous_league_id = result
        print(f"Season: {season}, Has previous league: {has_previous_league}, Previous league id: {previous_league_id}")

def main() -> None:

    get_all_seasons(curr_leagueid)


if __name__ == '__main__':
    main()