"""Data collection functions for all-time statistics."""
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

from constants import DEFAULT_PLAYOFF_WEEK_START
from mappers import load_users_map, load_rosters_map
from utils.matchup_utils import group_matchups_by_id
from utils.json_utils import load_json
from utils.logging_utils import get_logger

logger = get_logger('stats.data_collector')


def process_week_matchups(
    matchups: List[Dict],
    roster_to_user: Dict[int, str],
    year: str,
    week: int
) -> Tuple[Dict[str, List[Dict]], float]:
    """
    Process matchups for a week and return game data by user_id and weekly median.
    
    Returns:
        Tuple of (games_by_user, weekly_median_score)
    """
    games_by_user = defaultdict(list)
    all_scores = []
    
    # Group matchups by matchup_id
    matchup_groups = group_matchups_by_id(matchups)
    
    for matchup_id, matchup_list in matchup_groups.items():
        if len(matchup_list) == 2:
            team1 = matchup_list[0]
            team2 = matchup_list[1]
            
            roster_id1 = team1.get('roster_id')
            roster_id2 = team2.get('roster_id')
            points1 = team1.get('points', 0.0)
            points2 = team2.get('points', 0.0)
            
            if roster_id1 and roster_id2:
                user_id1 = roster_to_user.get(roster_id1)
                user_id2 = roster_to_user.get(roster_id2)
                
                if user_id1 and user_id2:
                    all_scores.append(points1)
                    all_scores.append(points2)
                    
                    # Determine winner
                    won1 = points1 > points2
                    won2 = points2 > points1
                    margin1 = points1 - points2
                    margin2 = points2 - points1
                    
                    # Store game data for user1
                    games_by_user[user_id1].append({
                        'year': year,
                        'week': week,
                        'points': points1,
                        'opponent_points': points2,
                        'won': won1,
                        'margin': margin1,
                        'opponent_user_id': user_id2
                    })
                    
                    # Store game data for user2
                    games_by_user[user_id2].append({
                        'year': year,
                        'week': week,
                        'points': points2,
                        'opponent_points': points1,
                        'won': won2,
                        'margin': margin2,
                        'opponent_user_id': user_id1
                    })
    
    # Calculate weekly median
    weekly_median = statistics.median(all_scores) if all_scores else 0.0
    
    return games_by_user, weekly_median


def collect_all_season_data(unmunged_dir: Path) -> Tuple[Dict[str, Dict], Dict[str, str]]:
    """
    Collect all game data across all seasons.
    
    Returns:
        Tuple of (stats_by_user, user_id_to_display_name)
        stats_by_user: Dict mapping user_id to dict of aggregated stats
        user_id_to_display_name: Dict mapping user_id to display_name
    """
    stats_by_user = defaultdict(lambda: {
        'seasons': set(),
        'games': [],
        'all_scores': [],
        'weeks_above_median': 0,
        'total_weeks': 0,
        'lucky_wins': 0,
        'unlucky_losses': 0,
        'top_score_weeks': 0,
        'low_score_weeks': 0
    })
    user_id_to_display_name = {}
    
    # Get all season directories
    season_dirs = sorted([
        item for item in unmunged_dir.iterdir()
        if item.is_dir() and item.name.isdigit() and (item / "league_info.json").exists()
    ])
    
    for season_dir in season_dirs:
        year = season_dir.name
        logger.info(f"Processing season {year}...")
        
        # Load league info to get playoff week start
        league_info_path = season_dir / "league_info.json"
        if not league_info_path.exists():
            logger.warning(f"  No league_info.json found, skipping")
            continue
        
        league_info = load_json(league_info_path)
        if league_info is None:
            continue
        
        playoff_week_start = league_info.get('settings', {}).get(
            'playoff_week_start', DEFAULT_PLAYOFF_WEEK_START
        )
        
        # Load users and rosters
        users_path = season_dir / "users.json"
        rosters_path = season_dir / "rosters.json"
        
        if not users_path.exists() or not rosters_path.exists():
            logger.warning(f"  Missing users.json or rosters.json, skipping")
            continue
        
        users_map = load_users_map(users_path)
        rosters_map = load_rosters_map(rosters_path, users_map)
        
        # Map roster_id to user_id (owner_id)
        roster_to_user = {}
        rosters_data = load_json(rosters_path)
        if rosters_data is None:
            continue
        
        for roster in rosters_data:
            roster_id = roster.get('roster_id')
            owner_id = roster.get('owner_id')
            if roster_id is not None and owner_id:
                roster_to_user[roster_id] = owner_id
                # Store display_name mapping
                if owner_id in users_map:
                    user_id_to_display_name[owner_id] = users_map[owner_id].get('display_name', owner_id)
                stats_by_user[owner_id]['seasons'].add(year)
        
        # Process regular season weeks only
        for week in range(1, playoff_week_start):
            week_dir = season_dir / f"week_{week}"
            matchups_path = week_dir / "matchups.json"
            
            if not matchups_path.exists():
                continue
            
            matchups = load_json(matchups_path)
            if matchups is None:
                continue
            
            games_by_user, weekly_median = process_week_matchups(
                matchups, roster_to_user, year, week
            )
            
            # Update stats for each user
            for user_id, games in games_by_user.items():
                for game in games:
                    stats_by_user[user_id]['games'].append(game)
                    stats_by_user[user_id]['all_scores'].append(game['points'])
                    stats_by_user[user_id]['total_weeks'] += 1
                    
                    # Check if above median for median win %
                    if game['points'] > weekly_median:
                        stats_by_user[user_id]['weeks_above_median'] += 1
    
    return stats_by_user, user_id_to_display_name

