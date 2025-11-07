"""Mapping module for converting IDs to human-readable names."""
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def load_players_data(players_path: Path) -> Dict:
    """
    Load players.json data once.
    
    Args:
        players_path: Path to players.json file
        
    Returns:
        Raw players data dictionary
    """
    with open(players_path, 'r') as f:
        return json.load(f)


def load_players_map(players_path: Path) -> Dict[str, str]:
    """
    Load player ID to player name mapping from players.json.
    
    Args:
        players_path: Path to players.json file
        
    Returns:
        Dictionary mapping player ID (str) to player full_name (str)
    """
    players_data = load_players_data(players_path)
    
    players_map = {}
    for player_id, player_info in players_data.items():
        if player_info and isinstance(player_info, dict):
            full_name = player_info.get('full_name')
            if full_name:
                players_map[player_id] = full_name
    
    return players_map


def load_players_maps(players_path: Path) -> Tuple[Dict[str, str], Dict[str, List[str]]]:
    """
    Load both players_map and positions_map from players.json in a single pass.
    
    Args:
        players_path: Path to players.json file
        
    Returns:
        Tuple of (players_map, positions_map)
        - players_map: Dictionary mapping player ID to player full_name
        - positions_map: Dictionary mapping player ID to list of fantasy positions
    """
    players_data = load_players_data(players_path)
    
    players_map = {}
    positions_map = {}
    
    for player_id, player_info in players_data.items():
        if player_info and isinstance(player_info, dict):
            full_name = player_info.get('full_name')
            if full_name:
                players_map[player_id] = full_name
            
            fantasy_positions = player_info.get('fantasy_positions', [])
            if fantasy_positions:
                positions_map[player_id] = fantasy_positions
    
    return players_map, positions_map


def load_users_map(users_path: Path) -> Dict[str, Dict[str, str]]:
    """
    Load user ID to user info mapping from users.json.
    
    Args:
        users_path: Path to users.json file
        
    Returns:
        Dictionary mapping user ID (str) to dict with 'team_name' and 'display_name'
    """
    with open(users_path, 'r') as f:
        users_data = json.load(f)
    
    users_map = {}
    for user in users_data:
        user_id = user.get('user_id')
        if not user_id:
            continue
        
        display_name = user.get('display_name', '')
        metadata = user.get('metadata', {})
        team_name = metadata.get('team_name')
        
        # Use team_name if available, otherwise "Team {display_name}"
        if team_name:
            final_team_name = team_name
        else:
            final_team_name = f"Team {display_name}"
        
        users_map[user_id] = {
            'team_name': final_team_name,
            'display_name': display_name
        }
    
    return users_map


def load_rosters_map(rosters_path: Path, users_map: Dict[str, Dict[str, str]]) -> Dict[int, Dict[str, str]]:
    """
    Load roster ID to user info mapping from rosters.json.
    
    Args:
        rosters_path: Path to rosters.json file
        users_map: User ID to user info mapping from load_users_map
        
    Returns:
        Dictionary mapping roster_id (int) to user info dict with 'team_name' and 'display_name'
    """
    with open(rosters_path, 'r') as f:
        rosters_data = json.load(f)
    
    rosters_map = {}
    for roster in rosters_data:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        
        if roster_id is None or not owner_id:
            continue
        
        # Look up user info by owner_id
        user_info = users_map.get(owner_id)
        if user_info:
            rosters_map[roster_id] = user_info.copy()
        else:
            # Fallback if owner_id not found
            rosters_map[roster_id] = {
                'team_name': f"Team {owner_id}",
                'display_name': owner_id
            }
    
    return rosters_map


def get_player_name(player_id: str, players_map: Dict[str, str]) -> str:
    """
    Get player name from player ID.
    
    Args:
        player_id: Player ID (may be numeric string or team abbreviation)
        players_map: Player ID to name mapping
        
    Returns:
        Player name or team abbreviation if not found
    """
    # Team abbreviations (DEF) are kept as-is
    if player_id in players_map:
        return players_map[player_id]
    # If not found, return the ID (likely a team abbreviation like "BAL", "CIN")
    return player_id


def get_team_name(roster_id: int, rosters_map: Dict[int, Dict[str, str]]) -> str:
    """
    Get team name from roster ID.
    
    Args:
        roster_id: Roster ID
        rosters_map: Roster ID to user info mapping
        
    Returns:
        Team name or fallback string if not found
    """
    roster_info = rosters_map.get(roster_id)
    if roster_info:
        return roster_info.get('team_name', f"Team {roster_id}")
    return f"Team {roster_id}"


def get_user_name(user_id: str, users_map: Dict[str, Dict[str, str]]) -> str:
    """
    Get team name from user ID.
    
    Args:
        user_id: User ID
        users_map: User ID to user info mapping
        
    Returns:
        Team name or fallback string if not found
    """
    user_info = users_map.get(user_id)
    if user_info:
        return user_info.get('team_name', f"Team {user_id}")
    return f"Team {user_id}"

