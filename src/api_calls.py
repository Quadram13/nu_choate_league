import requests
import json
import time
from pathlib import Path
from typing import Optional, Tuple

from constants import SLEEPER_API_BASE_URL, SLEEPER_PLAYERS_URL, UNMUNGED_DIR
from utils.exceptions import APIError, FileOperationError
from utils.logging_utils import get_logger

logger = get_logger('api_calls')

# try not to spam api calls, as sleeper warns that you may be ip-blocked if you do.

# Current league ID - update this if processing a different league
curr_leagueid = '1251998020954763264'

# API retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1  # seconds
MAX_RETRY_DELAY = 10  # seconds


def call_api(url: str, max_retries: int = MAX_RETRIES) -> Optional[dict]:
    """
    Make HTTP API GET request with retry logic and exponential backoff.
    
    Args:
        url: URL to request
        max_retries: Maximum number of retry attempts (default: 3)
        
    Returns:
        JSON response as dictionary, or None if all retries fail
        
    Raises:
        APIError: If API call fails after all retries
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            status_code = e.response.status_code if e.response else None
            last_exception = APIError(
                f"HTTP error {status_code} for {url}: {str(e)}",
                status_code=status_code,
                url=url
            )
            # Don't retry on 4xx errors (client errors)
            if status_code and 400 <= status_code < 500:
                logger.error(f"Client error {status_code} for {url}, not retrying")
                raise last_exception
        except requests.exceptions.RequestException as e:
            last_exception = APIError(f"Request error for {url}: {str(e)}", url=url)
        except json.JSONDecodeError as e:
            last_exception = APIError(f"JSON decode error for {url}: {str(e)}", url=url)
            # Don't retry on JSON decode errors
            raise last_exception
        except Exception as e:
            last_exception = APIError(f"Unexpected error for {url}: {str(e)}", url=url)
        
        # If we have retries left, wait before retrying
        if attempt < max_retries:
            delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
            logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries + 1}), retrying in {delay}s: {url}")
            time.sleep(delay)
        else:
            logger.error(f"API call failed after {max_retries + 1} attempts: {url}")
    
    # All retries exhausted
    raise last_exception

def save_json_to_file(data: dict, output_path: Path) -> None:
    """
    Save JSON data to file.
    
    Args:
        data: Dictionary to save as JSON
        output_path: Path to output file
        
    Raises:
        FileOperationError: If file cannot be written
    """
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except (IOError, OSError) as e:
        raise FileOperationError(f"Failed to save JSON to {output_path}: {str(e)}") from e

def get_and_save_api_data(url: str, output_path: Path) -> bool:
    """
    Fetch API data and save to file.
    
    Args:
        url: API URL to fetch
        output_path: Path to save the data
        
    Returns:
        True if successful, False otherwise
    """
    try:
        data = call_api(url)
        if data is None:
            logger.error(f"No data returned from {url}")
            return False
        save_json_to_file(data, output_path)
        return True
    except APIError as e:
        logger.error(f"API error fetching {url}: {e}")
        return False
    except FileOperationError as e:
        logger.error(f"File error saving {output_path}: {e}")
        return False


def save_league_info(league_id: str) -> Optional[Tuple[str, bool, Optional[str]]]:
    """
    Save league information for a given league ID.
    
    Args:
        league_id: Sleeper league ID
        
    Returns:
        Tuple of (season, has_previous_league, previous_league_id) or None if error
        
    Raises:
        APIError: If API calls fail
        DataValidationError: If required data is missing
    """
    from utils.exceptions import DataValidationError
    
    base_league_url = f"{SLEEPER_API_BASE_URL}/league/{league_id}"
    try:
        league_info = call_api(base_league_url)
    except APIError as e:
        logger.error(f"Failed to fetch league info for {league_id}: {e}")
        return None
    
    if league_info is None:
        logger.error(f"No league info returned for {league_id}")
        return None
    
    # Validate required fields
    season = league_info.get('season')
    if season is None:
        raise DataValidationError(f"Missing 'season' field in league info for {league_id}")
    
    latest_week = league_info.get('settings', {}).get('last_scored_leg', 0)
    previous_league_id = league_info.get('previous_league_id')
    draft_id = league_info.get('draft_id')

    output_dir = Path(f"{UNMUNGED_DIR}/{season}")
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

    # Handle draft picks (Sleeper API requires separate call for picks)
    drafts_path = output_dir / "draft.json"
    if drafts_path.exists():
        try:
            with open(drafts_path, 'r', encoding='utf-8') as f:
                drafts = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load drafts from {drafts_path}: {e}")
            raise FileOperationError(f"Failed to load drafts: {e}") from e
        
        for draft in drafts:
            draft_id = draft.get('draft_id')
            if draft_id:
                picks_url = f"{SLEEPER_API_BASE_URL}/draft/{draft_id}/picks"
                try:
                    picks_data = call_api(picks_url)
                    draft['picks'] = picks_data if picks_data is not None else []
                except APIError as e:
                    logger.warning(f"Failed to fetch picks for draft {draft_id}: {e}")
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
    """
    Traverse through all seasons of a league by following previous_league_id links.
    
    Args:
        latest_leagueid: The most recent league ID to start from
    """
    result = save_league_info(latest_leagueid)
    if result is None:
        logger.error(f"Failed to fetch initial league info for {latest_leagueid}")
        return
    
    season, has_previous_league, previous_league_id = result
    logger.info(f"Season: {season}, Has previous league: {has_previous_league}, Previous league id: {previous_league_id}")
    
    while has_previous_league and previous_league_id:
        result = save_league_info(previous_league_id)
        if result is None:
            logger.warning(f"Failed to fetch league info for previous league {previous_league_id}, stopping traversal")
            break
        season, has_previous_league, previous_league_id = result
        logger.info(f"Season: {season}, Has previous league: {has_previous_league}, Previous league id: {previous_league_id}")

def main() -> None:

    get_all_seasons(curr_leagueid)


if __name__ == '__main__':
    main()