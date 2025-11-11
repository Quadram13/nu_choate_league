"""Team building logic for optimal and lowest scoring teams."""
from typing import Dict, List, Optional

from constants import (
    FLEX_ELIGIBLE_POSITIONS,
    POSITION_DEF,
    POSITION_FLEX,
    POSITION_K,
    POSITION_QB,
    POSITION_RB,
    POSITION_TE,
    POSITION_WR
)
from utils.json_utils import load_json
from pathlib import Path


def load_player_positions(players_path: Path) -> Dict[str, List[str]]:
    """
    Load player fantasy positions mapping.
    
    Args:
        players_path: Path to players.json
        
    Returns:
        Dictionary mapping player_id to list of fantasy positions
    """
    players_data = load_json(players_path)
    if players_data is None:
        return {}
    
    positions_map = {}
    for player_id, player_info in players_data.items():
        if player_info and isinstance(player_info, dict):
            fantasy_positions = player_info.get('fantasy_positions', [])
            if fantasy_positions:
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

