"""Statistics calculation functions."""
import statistics
from pathlib import Path
from typing import Dict, List

from constants import DEFAULT_PLAYOFF_WEEK_START
from mappers import load_users_map, load_rosters_map
from utils.matchup_utils import group_matchups_by_id
from utils.json_utils import load_json


def calculate_manager_stats(
    user_id: str,
    games: List[Dict],
    all_scores: List[float],
    weeks_above_median: int,
    total_weeks: int,
    seasons: set
) -> Dict:
    """Calculate all statistics for a manager."""
    if not games:
        return None
    
    wins = sum(1 for g in games if g['won'])
    losses = sum(1 for g in games if not g['won'])
    games_played = len(games)
    
    total_pf = sum(g['points'] for g in games)
    total_pa = sum(g['opponent_points'] for g in games)
    avg_pf = total_pf / games_played if games_played > 0 else 0.0
    avg_pa = total_pa / games_played if games_played > 0 else 0.0
    
    margins = [g['margin'] for g in games]
    avg_margin = statistics.mean(margins) if margins else 0.0
    
    win_margins = [g['margin'] for g in games if g['won']]
    loss_margins = [g['margin'] for g in games if not g['won']]
    avg_win_margin = statistics.mean(win_margins) if win_margins else 0.0
    avg_loss_margin = statistics.mean(loss_margins) if loss_margins else 0.0
    
    # High/Low scores with year/week
    high_score_game = max(games, key=lambda g: g['points'])
    low_score_game = min(games, key=lambda g: g['points'])
    high_score = (high_score_game['points'], high_score_game['year'], high_score_game['week'])
    low_score = (low_score_game['points'], low_score_game['year'], low_score_game['week'])
    
    # Largest/Smallest wins
    wins_only = [g for g in games if g['won']]
    if wins_only:
        largest_win = max(wins_only, key=lambda g: g['margin'])
        smallest_win = min(wins_only, key=lambda g: g['margin'])
        largest_win_data = (largest_win['margin'], largest_win['year'], largest_win['week'])
        smallest_win_data = (smallest_win['margin'], smallest_win['year'], smallest_win['week'])
    else:
        largest_win_data = (0.0, "", 0)
        smallest_win_data = (0.0, "", 0)
    
    # Largest/Smallest losses
    losses_only = [g for g in games if not g['won']]
    if losses_only:
        largest_loss = min(losses_only, key=lambda g: g['margin'])  # Most negative
        smallest_loss = max(losses_only, key=lambda g: g['margin'])  # Least negative
        largest_loss_data = (largest_loss['margin'], largest_loss['year'], largest_loss['week'])
        smallest_loss_data = (smallest_loss['margin'], smallest_loss['year'], smallest_loss['week'])
    else:
        largest_loss_data = (0.0, "", 0)
        smallest_loss_data = (0.0, "", 0)
    
    # Median Win % - percentage of weeks where team scored above weekly median
    median_win_pct = (weeks_above_median / total_weeks * 100) if total_weeks > 0 else 0.0
    
    # Points StDev
    points_stdev = statistics.stdev(all_scores) if len(all_scores) > 1 else 0.0
    
    return {
        'user_id': user_id,
        'seasons': len(seasons),
        'games_played': games_played,
        'wins': wins,
        'losses': losses,
        'win_pct': (wins / games_played * 100) if games_played > 0 else 0.0,
        'total_pf': total_pf,
        'avg_pf': avg_pf,
        'total_pa': total_pa,
        'avg_pa': avg_pa,
        'avg_margin': avg_margin,
        'avg_win_margin': avg_win_margin,
        'avg_loss_margin': avg_loss_margin,
        'high_score': high_score,
        'low_score': low_score,
        'largest_win': largest_win_data,
        'smallest_win': smallest_win_data,
        'largest_loss': largest_loss_data,
        'smallest_loss': smallest_loss_data,
        'median_win_pct': median_win_pct,
        'points_stdev': points_stdev,
        'games': games,  # Keep for calculating lucky/unlucky and top/low weeks
        'all_scores': all_scores
    }


def calculate_lucky_unlucky_and_extremes(
    stats_by_user: Dict[str, Dict],
    unmunged_dir: Path
) -> None:
    """
    Calculate lucky wins, unlucky losses, and top/low score weeks.
    This requires re-processing to get weekly medians and league-wide extremes.
    """
    
    # Re-process to get weekly medians and league extremes
    season_dirs = sorted([
        item for item in unmunged_dir.iterdir()
        if item.is_dir() and item.name.isdigit() and (item / "league_info.json").exists()
    ])
    
    for season_dir in season_dirs:
        year = season_dir.name
        
        league_info_path = season_dir / "league_info.json"
        if not league_info_path.exists():
            continue
        
        league_info = load_json(league_info_path)
        if league_info is None:
            continue
        
        playoff_week_start = league_info.get('settings', {}).get(
            'playoff_week_start', DEFAULT_PLAYOFF_WEEK_START
        )
        
        users_path = season_dir / "users.json"
        rosters_path = season_dir / "rosters.json"
        
        if not users_path.exists() or not rosters_path.exists():
            continue
        
        users_map = load_users_map(users_path)
        rosters_map = load_rosters_map(rosters_path, users_map)
        
        roster_to_user = {}
        rosters_data = load_json(rosters_path)
        if rosters_data is None:
            continue
        
        for roster in rosters_data:
            roster_id = roster.get('roster_id')
            owner_id = roster.get('owner_id')
            if roster_id and owner_id:
                roster_to_user[roster_id] = owner_id
        
        # Process each week
        for week in range(1, playoff_week_start):
            week_dir = season_dir / f"week_{week}"
            matchups_path = week_dir / "matchups.json"
            
            if not matchups_path.exists():
                continue
            
            matchups = load_json(matchups_path)
            if matchups is None:
                continue
            
            # Get all scores for this week
            all_week_scores = []
            user_scores = {}  # user_id -> (points, won, game_data)
            
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
                            all_week_scores.append(points1)
                            all_week_scores.append(points2)
                            
                            won1 = points1 > points2
                            won2 = points2 > points1
                            
                            user_scores[user_id1] = (points1, won1, {
                                'year': year, 'week': week, 'points': points1,
                                'won': won1, 'opponent_points': points2
                            })
                            user_scores[user_id2] = (points2, won2, {
                                'year': year, 'week': week, 'points': points2,
                                'won': won2, 'opponent_points': points1
                            })
            
            if not all_week_scores:
                continue
            
            weekly_median = statistics.median(all_week_scores)
            week_max = max(all_week_scores)
            week_min = min(all_week_scores)
            
            # Update stats for each user
            for user_id, (points, won, game_data) in user_scores.items():
                if user_id not in stats_by_user:
                    continue
                
                # Lucky win: won but scored below median
                if won and points < weekly_median:
                    stats_by_user[user_id]['lucky_wins'] += 1
                
                # Unlucky loss: lost but scored above median
                if not won and points > weekly_median:
                    stats_by_user[user_id]['unlucky_losses'] += 1
                
                # Top score week
                if points == week_max:
                    stats_by_user[user_id]['top_score_weeks'] += 1
                
                # Low score week
                if points == week_min:
                    stats_by_user[user_id]['low_score_weeks'] += 1

