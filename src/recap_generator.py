"""Recap generator for weekly and season recaps."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

from constants import (
    FLEX_ELIGIBLE_POSITIONS,
    POSITION_BN,
    POSITION_DEF,
    POSITION_FLEX,
    POSITION_K,
    POSITION_QB,
    POSITION_RB,
    POSITION_TE,
    POSITION_WR
)
from standings import _group_matchups_by_id


def load_player_positions(players_path: Path) -> Dict[str, List[str]]:
    """
    Load player fantasy positions mapping.
    
    Args:
        players_path: Path to players.json
        
    Returns:
        Dictionary mapping player_id to list of fantasy positions
    """
    with open(players_path, 'r') as f:
        players_data = json.load(f)
    
    positions_map = {}
    for player_id, player_info in players_data.items():
        if player_info and isinstance(player_info, dict):
            fantasy_positions = player_info.get('fantasy_positions', [])
            positions_map[player_id] = fantasy_positions
    
    return positions_map


def is_flex_eligible(player_id: str, positions_map: Dict[str, List[str]]) -> bool:
    """
    Check if a player is eligible for FLEX position (TE, RB, or WR).
    
    Args:
        player_id: Player ID
        positions_map: Player ID to fantasy positions mapping
        
    Returns:
        True if player is eligible for FLEX
    """
    # Team abbreviations (DEF) are not FLEX eligible
    if player_id not in positions_map:
        return False
    
    positions = positions_map[player_id]
    return any(pos in FLEX_ELIGIBLE_POSITIONS for pos in positions)


def _build_team(
    players_points: Dict[str, float],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str],
    reverse_sort: bool = True,
    starters: Optional[List[str]] = None,
    min_points: float = 0.0
) -> Dict[str, Optional[Dict]]:
    """
    Build a team based on roster structure from players, sorted by points.
    
    Args:
        players_points: Dictionary mapping player_id to points
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions (QB, RB, RB, WR, WR, TE, FLEX, FLEX, K, DEF)
        players_map: Player ID to name mapping
        reverse_sort: If True, sort descending (highest first), else ascending (lowest first)
        starters: Optional list of starter player IDs to exclude from consideration
        min_points: Minimum points threshold (default 0.0, set to >0 to filter out zero-scorers)
        
    Returns:
        Dictionary mapping position to player info dict (or None if no player)
    """
    # Filter players based on criteria
    available_players = {}
    for pid, pts in players_points.items():
        if starters and pid in starters:
            continue
        
        # Check if player is DEF (DEF players are in positions_map with fantasy_positions: ["DEF"])
        is_def = False
        if pid in positions_map:
            positions = positions_map[pid]
            is_def = POSITION_DEF in positions
        
        # For optimal team (when starters provided), exclude zero-scorers
        # For lowest team (no starters), include all players
        # Exception: Always include DEF players even with 0 points
        if starters is not None and pts <= 0 and not is_def:
            continue
        if pts < min_points and not is_def:
            continue
        available_players[pid] = pts
    
    # Separate players by position
    qbs = []
    rbs = []
    wrs = []
    tes = []
    ks = []
    defs = []
    flex_eligible = []
    
    for player_id, points in available_players.items():
        if player_id not in positions_map:
            # Fallback: player not in positions_map (shouldn't happen for DEF, but handle gracefully)
            continue
        
        positions = positions_map[player_id]
        player_info = {
            'player_id': player_id,
            'player_name': players_map.get(player_id, player_id),
            'points': points
        }
        
        if POSITION_DEF in positions:
            defs.append((player_id, points, player_info))
        if POSITION_QB in positions:
            qbs.append((player_id, points, player_info))
        if POSITION_RB in positions:
            rbs.append((player_id, points, player_info))
        if POSITION_WR in positions:
            wrs.append((player_id, points, player_info))
        if POSITION_TE in positions:
            tes.append((player_id, points, player_info))
        if POSITION_K in positions:
            ks.append((player_id, points, player_info))
        if is_flex_eligible(player_id, positions_map):
            flex_eligible.append((player_id, points, player_info))
    
    # Sort by points (direction depends on reverse_sort)
    qbs.sort(key=lambda x: x[1], reverse=reverse_sort)
    rbs.sort(key=lambda x: x[1], reverse=reverse_sort)
    wrs.sort(key=lambda x: x[1], reverse=reverse_sort)
    tes.sort(key=lambda x: x[1], reverse=reverse_sort)
    ks.sort(key=lambda x: x[1], reverse=reverse_sort)
    defs.sort(key=lambda x: x[1], reverse=reverse_sort)
    flex_eligible.sort(key=lambda x: x[1], reverse=reverse_sort)
    
    # Build team based on roster structure
    team = {}
    used_players = set()
    
    # Fill QB
    if roster_positions[0] == POSITION_QB and qbs:
        player_id, _, player_info = qbs[0]
        team[POSITION_QB] = player_info
        used_players.add(player_id)
    
    # Fill RB1, RB2
    rb_idx = 0
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_RB and rb_idx < len(rbs):
            player_id, _, player_info = rbs[rb_idx]
            if player_id not in used_players:
                team[f'{POSITION_RB}{rb_idx + 1}'] = player_info
                used_players.add(player_id)
                rb_idx += 1
    
    # Fill WR1, WR2
    wr_idx = 0
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_WR and wr_idx < len(wrs):
            player_id, _, player_info = wrs[wr_idx]
            if player_id not in used_players:
                team[f'{POSITION_WR}{wr_idx + 1}'] = player_info
                used_players.add(player_id)
                wr_idx += 1
    
    # Fill TE
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_TE and tes:
            player_id, _, player_info = tes[0]
            if player_id not in used_players:
                team[POSITION_TE] = player_info
                used_players.add(player_id)
            break
    
    # Fill FLEX positions (from remaining eligible players)
    flex_idx = 0
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_FLEX and flex_idx < 2:
            # Find next eligible flex player not already used
            for player_id, points, player_info in flex_eligible:
                if player_id not in used_players:
                    team[f'{POSITION_FLEX}{flex_idx + 1}'] = player_info
                    used_players.add(player_id)
                    flex_idx += 1
                    break
    
    # Fill K
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_K and ks:
            player_id, _, player_info = ks[0]
            if player_id not in used_players:
                team[POSITION_K] = player_info
                used_players.add(player_id)
            break
    
    # Fill DEF
    for i, pos in enumerate(roster_positions):
        if pos == POSITION_DEF and defs:
            player_id, _, player_info = defs[0]
            team[POSITION_DEF] = player_info
            used_players.add(player_id)
            break
    
    return team


def build_optimal_team(
    players_points: Dict[str, float],
    starters: List[str],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str]
) -> Dict[str, Optional[Dict]]:
    """
    Build an optimal team based on roster structure from the highest scoring players.
    
    Args:
        players_points: Dictionary mapping player_id to points
        starters: List of starter player IDs (to exclude from consideration)
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions (QB, RB, RB, WR, WR, TE, FLEX, FLEX, K, DEF)
        players_map: Player ID to name mapping
        
    Returns:
        Dictionary mapping position to player info dict (or None if no player)
    """
    return _build_team(
        players_points,
        positions_map,
        roster_positions,
        players_map,
        reverse_sort=True,
        starters=starters,
        min_points=0.0  # Only exclude zero-scorers if they're in starters
    )


def build_lowest_team(
    players_points: Dict[str, float],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str]
) -> Dict[str, Optional[Dict]]:
    """
    Build a team from the lowest scoring players at each position.
    
    Args:
        players_points: Dictionary mapping player_id to points
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions
        players_map: Player ID to name mapping
        
    Returns:
        Dictionary mapping position to player info dict (or None if no player)
    """
    return _build_team(
        players_points,
        positions_map,
        roster_positions,
        players_map,
        reverse_sort=False,
        starters=None,
        min_points=0.0  # Include all players, even zero-scorers
    )


def _calculate_optimal_lineup_score(
    matchup: Dict,
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str]
) -> float:
    """
    Calculate the optimal lineup score for a single team using all players from their roster.
    
    Args:
        matchup: Matchup dictionary containing players_points and all players
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions
        players_map: Player ID to name mapping
        
    Returns:
        Total points of the optimal lineup
    """
    # Build optimal team using all players (starters + bench)
    optimal_team = _build_team(
        matchup.get('players_points', {}),
        positions_map,
        roster_positions,
        players_map,
        reverse_sort=True,
        starters=None,  # Include all players
        min_points=0.0
    )
    
    # Sum up points from optimal team
    total_points = sum(
        player_info.get('points', 0.0)
        for player_info in optimal_team.values()
        if player_info is not None
    )
    
    return total_points


def _build_benchwarmers_team(
    matchups: List[Dict],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str],
    players_map: Dict[str, str]
) -> Dict[str, Optional[Dict]]:
    """
    Build benchwarmers team - only include bench players who scored higher than
    at least one starter at their position(s) on the same team.
    
    Args:
        matchups: List of matchup dictionaries
        positions_map: Player ID to fantasy positions mapping
        roster_positions: List of roster positions
        players_map: Player ID to name mapping
        
    Returns:
        Dictionary mapping position to player info dict (or None if no player)
    """
    benchwarmers_points = {}
    
    for matchup in matchups:
        players_points = matchup.get('players_points', {})
        starters = set(matchup.get('starters', []))
        all_players = set(matchup.get('players', []))
        bench_players = all_players - starters
        
        # Get starter points by position for comparison
        starter_points_by_pos = {
            POSITION_QB: [],
            POSITION_RB: [],
            POSITION_WR: [],
            POSITION_TE: [],
            POSITION_K: [],
            POSITION_DEF: []
        }
        
        for starter_id in starters:
            starter_points = players_points.get(starter_id, 0.0)
            if starter_id in positions_map:
                positions = positions_map[starter_id]
                for pos in positions:
                    if pos in starter_points_by_pos:
                        starter_points_by_pos[pos].append(starter_points)
        
        # Check each bench player
        for bench_id in bench_players:
            bench_points = players_points.get(bench_id, 0.0)
            if bench_id not in positions_map:
                continue
            
            positions = positions_map[bench_id]
            is_benchwarmer = False
            
            # Check if bench player scored higher than at least one starter at any of their positions
            for pos in positions:
                if pos in starter_points_by_pos:
                    pos_starter_points = starter_points_by_pos[pos]
                    if pos_starter_points and bench_points > min(pos_starter_points):
                        is_benchwarmer = True
                        break
            
            # Also check FLEX eligibility - bench player can replace FLEX starters
            # A FLEX-eligible bench player is a benchwarmer if they scored higher than
            # at least one FLEX-eligible starter (RB, WR, or TE)
            if not is_benchwarmer and is_flex_eligible(bench_id, positions_map):
                for flex_pos in [POSITION_RB, POSITION_WR, POSITION_TE]:
                    if flex_pos in starter_points_by_pos:
                        flex_starter_points = starter_points_by_pos[flex_pos]
                        if flex_starter_points and bench_points > min(flex_starter_points):
                            is_benchwarmer = True
                            break
            
            if is_benchwarmer:
                # Keep the highest score if player was benchwarmer in multiple matchups
                if bench_id not in benchwarmers_points or bench_points > benchwarmers_points[bench_id]:
                    benchwarmers_points[bench_id] = bench_points
    
    # Build team from benchwarmers using the same structure
    return _build_team(
        benchwarmers_points,
        positions_map,
        roster_positions,
        players_map,
        reverse_sort=True,
        starters=None,
        min_points=0.0
    )


def _process_matchups(
    matchups: List[Dict],
    rosters_map: Dict[int, Dict[str, str]],
    players_map: Dict[str, str],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str]
) -> Tuple[Dict[int, Dict], Dict[int, Dict], Dict, Dict, Dict, Dict]:
    """
    Process matchups and extract matchup data, team stats, and optimal teams.
    
    Returns:
        Tuple of (matchup_by_roster, matchup_results, highest_team, lowest_team,
                 highest_starters_team, lowest_starters_team, benchwarmers_team)
    """
    matchup_by_roster = {}
    matchup_results = {}
    
    # Group matchups by matchup_id to determine winners/losers
    matchup_groups = _group_matchups_by_id(matchups)
    
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


def map_transactions(
    transactions: List[Dict],
    players_map: Dict[str, str],
    rosters_map: Dict[int, Dict[str, str]]
) -> List[Dict]:
    """
    Map transaction data to include human-readable names.
    
    Args:
        transactions: List of transaction dictionaries
        players_map: Player ID to name mapping
        rosters_map: Roster ID to user info mapping
        
    Returns:
        List of mapped transaction dictionaries
    """
    mapped_transactions = []
    for transaction in transactions:
        mapped_trans = {
            'transaction_id': transaction.get('transaction_id'),
            'type': transaction.get('type'),
            'status': transaction.get('status'),
            'created': transaction.get('created'),
            'creator': transaction.get('creator'),
            'creator_team_name': rosters_map.get(
                transaction.get('roster_ids', [None])[0] if transaction.get('roster_ids') else None,
                {}
            ).get('team_name', 'Unknown') if transaction.get('roster_ids') else 'Unknown',
            'adds': {
                players_map.get(pid, pid): rid
                for pid, rid in transaction.get('adds', {}).items()
            } if transaction.get('adds') else {},
            'drops': {
                players_map.get(pid, pid): rid
                for pid, rid in transaction.get('drops', {}).items()
            } if transaction.get('drops') else {},
            'roster_ids': transaction.get('roster_ids', [])
        }
        mapped_transactions.append(mapped_trans)
    return mapped_transactions


def _map_matchups(
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


def _calculate_awards(
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


def generate_weekly_recap(
    matchups: List[Dict],
    transactions: List[Dict],
    standings: List[Dict],
    players_map: Dict[str, str],
    rosters_map: Dict[int, Dict[str, str]],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str]
) -> Dict:
    """
    Generate weekly recap with all stats and awards.
    
    Args:
        matchups: List of matchup dictionaries
        transactions: List of transaction dictionaries
        standings: List of standings dictionaries
        players_map: Player ID to name mapping
        rosters_map: Roster ID to user info mapping
        positions_map: Player ID to fantasy positions mapping
        roster_positions: Roster position structure
        
    Returns:
        Dictionary containing weekly recap data
    """
    # Process matchups to get all matchup data and team stats
    (matchup_by_roster, matchup_results, highest_team, lowest_team,
     highest_starters_team, lowest_starters_team, benchwarmers_team) = _process_matchups(
        matchups, rosters_map, players_map, positions_map, roster_positions
    )
    
    # Calculate awards
    awards = _calculate_awards(
        standings, matchup_results, rosters_map,
        matchups, positions_map, roster_positions, players_map
    )
    
    # Map matchups (transactions are handled separately and saved to their own file)
    mapped_matchups = _map_matchups(matchups, players_map, rosters_map, positions_map)
    
    return {
        'matchups': mapped_matchups,
        'standings': standings,
        'highest_scoring_team': highest_team,
        'lowest_scoring_team': lowest_team,
        'highest_scoring_starters': highest_starters_team,
        'lowest_scoring_starters': lowest_starters_team,
        'benchwarmers': benchwarmers_team,
        'awards': awards
    }

