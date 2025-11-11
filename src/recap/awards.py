"""Awards calculation for weekly recaps."""
from typing import Dict, List

from recap.team_builder import _calculate_optimal_lineup_score


def calculate_awards(
    standings: List[Dict],
    matchup_results: Dict[int, Dict],
    rosters_map: Dict[int, Dict[str, str]],
    matchups: List[Dict],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str]
) -> Dict:
    """
    Calculate all weekly awards.
    
    Args:
        standings: List of standings dictionaries
        matchup_results: Dictionary mapping roster_id to matchup result
        rosters_map: Roster ID to user info mapping
        matchups: List of matchup dictionaries
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions
        players_map: Player ID to name mapping
        
    Returns:
        Dictionary containing all awards
    """
    # Most/least efficient manager (based on points left on bench)
    most_efficient = None
    least_efficient = None
    least_points_left = float('inf')
    most_points_left = float('-inf')
    
    # Calculate points left on bench for each team
    for matchup in matchups:
        roster_id = matchup.get('roster_id')
        actual_score = sum(matchup.get('starters_points', []))
        optimal_score = _calculate_optimal_lineup_score(
            matchup, positions_map, roster_positions, players_map
        )
        points_left_on_bench = optimal_score - actual_score
        
        # Find most efficient (least points left on bench)
        if points_left_on_bench < least_points_left:
            least_points_left = points_left_on_bench
            most_efficient = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'actual_score': actual_score,
                'optimal_score': optimal_score
            }
        
        # Find least efficient (most points left on bench)
        if points_left_on_bench > most_points_left:
            most_points_left = points_left_on_bench
            least_efficient = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'actual_score': actual_score,
                'optimal_score': optimal_score
            }
    
    # Highest points in loss, lowest points in win
    highest_pts_loss = None
    lowest_pts_win = None
    highest_loss_pts = float('-inf')
    lowest_win_pts = float('inf')
    
    for roster_id, result in matchup_results.items():
        if not result['won'] and result['points'] > highest_loss_pts:
            highest_loss_pts = result['points']
            highest_pts_loss = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'points': result['points'],
                'opponent_points': result['opponent_points']
            }
        if result['won'] and result['points'] < lowest_win_pts:
            lowest_win_pts = result['points']
            lowest_pts_win = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'points': result['points'],
                'opponent_points': result['opponent_points']
            }
    
    # Largest/smallest winning margin
    largest_margin = None
    smallest_margin = None
    largest_margin_val = float('-inf')
    smallest_margin_val = float('inf')
    
    for roster_id, result in matchup_results.items():
        if result['won']:
            margin = result['margin']
            if margin > largest_margin_val:
                largest_margin_val = margin
                largest_margin = {
                    'roster_id': roster_id,
                    'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                    'margin': margin,
                    'points': result['points'],
                    'opponent_points': result['opponent_points']
                }
            if margin < smallest_margin_val:
                smallest_margin_val = margin
                smallest_margin = {
                    'roster_id': roster_id,
                    'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                    'margin': margin,
                    'points': result['points'],
                    'opponent_points': result['opponent_points']
                }
    
    return {
        'most_efficient_manager': most_efficient,
        'least_efficient_manager': least_efficient,
        'highest_points_in_loss': highest_pts_loss,
        'lowest_points_in_win': lowest_pts_win,
        'largest_winning_margin': largest_margin,
        'smallest_winning_margin': smallest_margin
    }

