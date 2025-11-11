"""Matchup processing and mapping functions."""
from typing import Dict, List, Tuple

from utils.matchup_utils import group_matchups_by_id
from recap.team_builder import (
    build_optimal_team,
    build_lowest_team,
    _build_benchwarmers_team
)


def process_matchups(
    matchups: List[Dict],
    rosters_map: Dict[int, Dict[str, str]],
    players_map: Dict[str, str],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str]
) -> Tuple[Dict[int, Dict], Dict[int, Dict], Dict, Dict, Dict, Dict]:
    """
    Process matchups and extract matchup data, team stats, and optimal teams.
    
    Args:
        matchups: List of matchup dictionaries
        rosters_map: Roster ID to user info mapping
        players_map: Player ID to name mapping
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions
        
    Returns:
        Tuple of (matchup_by_roster, matchup_results, highest_team, lowest_team,
                 highest_starters_team, lowest_starters_team, benchwarmers_team)
    """
    matchup_by_roster = {}
    matchup_results = {}
    
    # Group matchups by matchup_id to determine winners/losers
    matchup_groups = group_matchups_by_id(matchups)
    
    for matchup_id, matchup_list in matchup_groups.items():
        if len(matchup_list) == 2:
            team1 = matchup_list[0]
            team2 = matchup_list[1]
            
            roster_id1 = team1.get('roster_id')
            roster_id2 = team2.get('roster_id')
            points1 = team1.get('points', 0.0)
            points2 = team2.get('points', 0.0)
            
            matchup_by_roster[roster_id1] = team1
            matchup_by_roster[roster_id2] = team2
            
            matchup_results[roster_id1] = {
                'opponent_roster_id': roster_id2,
                'points': points1,
                'opponent_points': points2,
                'won': points1 > points2,
                'margin': points1 - points2
            }
            matchup_results[roster_id2] = {
                'opponent_roster_id': roster_id1,
                'points': points2,
                'opponent_points': points1,
                'won': points2 > points1,
                'margin': points2 - points1
            }
    
    # Find highest/lowest scoring teams
    highest_team = None
    lowest_team = None
    highest_points = float('-inf')
    lowest_points = float('inf')
    
    for roster_id, matchup in matchup_by_roster.items():
        points = matchup.get('points', 0.0)
        if points > highest_points:
            highest_points = points
            highest_team = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'points': points
            }
        if points < lowest_points:
            lowest_points = points
            lowest_team = {
                'roster_id': roster_id,
                'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
                'points': points
            }
    
    # Build optimal teams for highest/lowest scoring starters
    all_players_points = {}
    all_starters = set()
    
    for matchup in matchups:
        players_points = matchup.get('players_points', {})
        starters = matchup.get('starters', [])
        
        for player_id, points in players_points.items():
            if player_id not in all_players_points or points > all_players_points[player_id]:
                all_players_points[player_id] = points
        
        all_starters.update(starters)
    
    highest_starters_team = build_optimal_team(
        all_players_points,
        [],
        positions_map,
        roster_positions,
        players_map
    )
    
    # For lowest scoring starters, build team from lowest scoring players at each position
    # Only consider players who were actually starters
    starter_players_points = {}
    for matchup in matchups:
        players_points = matchup.get('players_points', {})
        starters = set(matchup.get('starters', []))
        
        for player_id in starters:
            points = players_points.get(player_id, 0.0)
            # Keep the lowest score if player started in multiple matchups
            if player_id not in starter_players_points or points < starter_players_points[player_id]:
                starter_players_points[player_id] = points
    
    # Build lowest scoring team (reverse logic - find minimums instead of maximums)
    lowest_starters_team = build_lowest_team(
        starter_players_points,
        positions_map,
        roster_positions,
        players_map
    )
    
    # Build benchwarmers team (bench players who scored higher than at least one starter at their position)
    benchwarmers_team = _build_benchwarmers_team(
        matchups, positions_map, roster_positions, players_map
    )
    
    return matchup_by_roster, matchup_results, highest_team, lowest_team, highest_starters_team, lowest_starters_team, benchwarmers_team


def map_matchups(
    matchups: List[Dict],
    players_map: Dict[str, str],
    rosters_map: Dict[int, Dict[str, str]],
    positions_map: Dict[str, List[str]]
) -> List[Dict]:
    """
    Map matchup data to include human-readable names.
    
    Args:
        matchups: List of matchup dictionaries
        players_map: Player ID to name mapping
        rosters_map: Roster ID to user info mapping
        positions_map: Player ID to fantasy positions mapping
        
    Returns:
        List of mapped matchup dictionaries
    """
    mapped_matchups = []
    for matchup in matchups:
        roster_id = matchup.get('roster_id')
        starters = set(matchup.get('starters', []))
        all_players = set(matchup.get('players', []))
        bench_players = all_players - starters
        players_points = matchup.get('players_points', {})
        
        mapped_matchup = {
            'roster_id': roster_id,
            'team_name': rosters_map.get(roster_id, {}).get('team_name', f'Team {roster_id}'),
            'points': matchup.get('points', 0.0),
            'matchup_id': matchup.get('matchup_id'),
            'starters': [
                {
                    'player_id': pid,
                    'player_name': players_map.get(pid, pid),
                    'points': players_points.get(pid, 0.0),
                    'positions': positions_map.get(pid, [])
                }
                for pid in matchup.get('starters', [])
            ],
            'bench': [
                {
                    'player_id': pid,
                    'player_name': players_map.get(pid, pid),
                    'points': players_points.get(pid, 0.0),
                    'positions': positions_map.get(pid, [])
                }
                for pid in sorted(bench_players)  # Sort for consistent ordering
            ],
            'starters_points': matchup.get('starters_points', [])
        }
        mapped_matchups.append(mapped_matchup)
    return mapped_matchups

