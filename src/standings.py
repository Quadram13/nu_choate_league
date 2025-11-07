"""Standings calculator for cumulative weekly standings."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict


def _group_matchups_by_id(matchups: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Group matchups by matchup_id.
    
    Args:
        matchups: List of matchup dictionaries
        
    Returns:
        Dictionary mapping matchup_id to list of matchups
    """
    matchup_groups = defaultdict(list)
    for matchup in matchups:
        matchup_id = matchup.get('matchup_id')
        if matchup_id:
            matchup_groups[matchup_id].append(matchup)
    return matchup_groups


def _process_week_data(
    season_dir: Path,
    week: int,
    standings: Dict[int, Dict]
) -> None:
    """
    Process a single week's matchups and transactions, updating standings in place.
    
    Args:
        season_dir: Path to season directory
        week: Week number to process
        standings: Dictionary of standings to update (keyed by roster_id)
    """
    week_dir = season_dir / f"week_{week}"
    matchups_path = week_dir / "matchups.json"
    transactions_path = week_dir / "transactions.json"
    
    if not matchups_path.exists():
        return
    
    # Process matchups to update W-L and points
    with open(matchups_path, 'r') as f:
        matchups = json.load(f)
    
    # Group matchups by matchup_id
    matchup_groups = _group_matchups_by_id(matchups)
    
    # Determine wins/losses for each matchup
    for matchup_id, matchup_list in matchup_groups.items():
        if len(matchup_list) == 2:
            team1 = matchup_list[0]
            team2 = matchup_list[1]
            
            roster_id1 = team1.get('roster_id')
            roster_id2 = team2.get('roster_id')
            points1 = team1.get('points', 0.0)
            points2 = team2.get('points', 0.0)
            
            if roster_id1 and roster_id2:
                # Update points for and against
                standings[roster_id1]['pf'] += points1
                standings[roster_id1]['pa'] += points2
                standings[roster_id2]['pf'] += points2
                standings[roster_id2]['pa'] += points1
                
                # Update W-L record
                if points1 > points2:
                    standings[roster_id1]['wins'] += 1
                    standings[roster_id2]['losses'] += 1
                elif points2 > points1:
                    standings[roster_id1]['losses'] += 1
                    standings[roster_id2]['wins'] += 1
                else:
                    standings[roster_id1]['ties'] += 1
                    standings[roster_id2]['ties'] += 1
    
    # Process transactions to count them
    if transactions_path.exists():
        with open(transactions_path, 'r') as f:
            transactions = json.load(f)
        
        for transaction in transactions:
            # Only count complete transactions
            if transaction.get('status') == 'complete':
                roster_ids = transaction.get('roster_ids', [])
                for roster_id in roster_ids:
                    if roster_id in standings:
                        standings[roster_id]['transaction_count'] += 1


def _initialize_standings(rosters_map: Dict[int, Dict[str, str]]) -> Dict[int, Dict]:
    """
    Initialize standings dictionary for all rosters.
    
    Args:
        rosters_map: Roster ID to user info mapping
        
    Returns:
        Dictionary of standings keyed by roster_id
    """
    standings = {}
    for roster_id in rosters_map.keys():
        standings[roster_id] = {
            'roster_id': roster_id,
            'team_name': rosters_map[roster_id]['team_name'],
            'wins': 0,
            'losses': 0,
            'ties': 0,
            'pf': 0.0,  # Points for
            'pa': 0.0,  # Points against
            'transaction_count': 0
        }
    return standings


def standings_to_list(standings: Dict[int, Dict]) -> List[Dict]:
    """
    Convert standings dictionary to sorted list.
    
    Args:
        standings: Dictionary of standings keyed by roster_id
        
    Returns:
        List of standings dictionaries, sorted by win percentage (desc), then PF (desc)
    """
    standings_list = []
    for roster_id, stats in standings.items():
        total_games = stats['wins'] + stats['losses'] + stats['ties']
        if total_games > 0:
            win_pct = stats['wins'] / total_games
        else:
            win_pct = 0.0
        
        standings_list.append({
            'roster_id': roster_id,
            'team_name': stats['team_name'],
            'wins': stats['wins'],
            'losses': stats['losses'],
            'ties': stats['ties'],
            'win_pct': round(win_pct, 4),
            'pf': round(stats['pf'], 2),
            'pa': round(stats['pa'], 2),
            'transaction_count': stats['transaction_count']
        })
    
    # Sort by win percentage (desc), then PF (desc)
    standings_list.sort(key=lambda x: (x['win_pct'], x['pf']), reverse=True)
    
    return standings_list


def calculate_weekly_standings(
    season_dir: Path,
    week: int,
    rosters_map: Dict[int, Dict[str, str]],
    previous_standings: Optional[Dict[int, Dict]] = None
) -> List[Dict]:
    """
    Calculate cumulative standings up to and including the specified week.
    
    Args:
        season_dir: Path to season directory (e.g., src/unmunged/2024)
        week: Week number to calculate standings for
        rosters_map: Roster ID to user info mapping
        previous_standings: Optional previous standings dict to increment from
                          (should contain standings up to week-1)
        
    Returns:
        List of standings dictionaries, sorted by win percentage (desc), then PF (desc)
    """
    # Get standings dict (for caching) and convert to list
    standings_dict = calculate_weekly_standings_dict(
        season_dir, week, rosters_map, previous_standings
    )
    return standings_to_list(standings_dict)


def calculate_weekly_standings_dict(
    season_dir: Path,
    week: int,
    rosters_map: Dict[int, Dict[str, str]],
    previous_standings: Optional[Dict[int, Dict]] = None
) -> Dict[int, Dict]:
    """
    Calculate cumulative standings up to and including the specified week.
    Returns the standings dictionary (for caching) instead of a list.
    
    Args:
        season_dir: Path to season directory (e.g., src/unmunged/2024)
        week: Week number to calculate standings for
        rosters_map: Roster ID to user info mapping
        previous_standings: Optional previous standings dict to increment from
                          (should contain standings up to week-1)
        
    Returns:
        Dictionary of standings keyed by roster_id
    """
    # Initialize or copy previous standings
    if previous_standings is None:
        standings = _initialize_standings(rosters_map)
        # Process all weeks from 1 to week
        for w in range(1, week + 1):
            _process_week_data(season_dir, w, standings)
    else:
        # Deep copy previous standings to avoid mutating the original
        # Use dict comprehension for better performance
        standings = {
            roster_id: {
                'roster_id': stats['roster_id'],
                'team_name': stats['team_name'],
                'wins': stats['wins'],
                'losses': stats['losses'],
                'ties': stats['ties'],
                'pf': stats['pf'],
                'pa': stats['pa'],
                'transaction_count': stats['transaction_count']
            }
            for roster_id, stats in previous_standings.items()
        }
        # Process only the current week (previous_standings already has weeks 1 to week-1)
        _process_week_data(season_dir, week, standings)
    
    return standings


def get_matchup_results(matchups: List[Dict]) -> Dict[int, Tuple[int, int, float, float]]:
    """
    Get matchup results for a week.
    
    Args:
        matchups: List of matchup dictionaries
        
    Returns:
        Dictionary mapping roster_id to (opponent_roster_id, won, points, opponent_points)
    """
    # Reuse the existing grouping function instead of duplicating logic
    matchup_groups = _group_matchups_by_id(matchups)
    
    results = {}
    for matchup_id, matchup_list in matchup_groups.items():
        if len(matchup_list) == 2:
            team1 = matchup_list[0]
            team2 = matchup_list[1]
            
            roster_id1 = team1.get('roster_id')
            roster_id2 = team2.get('roster_id')
            points1 = team1.get('points', 0.0)
            points2 = team2.get('points', 0.0)
            
            if roster_id1 and roster_id2:
                # 1 = win, 0 = loss, -1 = tie
                if points1 > points2:
                    results[roster_id1] = (roster_id2, 1, points1, points2)
                    results[roster_id2] = (roster_id1, 0, points2, points1)
                elif points2 > points1:
                    results[roster_id1] = (roster_id2, 0, points1, points2)
                    results[roster_id2] = (roster_id1, 1, points2, points1)
                else:
                    results[roster_id1] = (roster_id2, -1, points1, points2)
                    results[roster_id2] = (roster_id1, -1, points2, points1)
    
    return results

