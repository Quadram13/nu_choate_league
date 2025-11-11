"""Postseason processor for playoff brackets and recaps."""
import json
from pathlib import Path
from typing import Dict, List
from recap import generate_weekly_recap


def map_bracket(
    bracket_data: List[Dict],
    rosters_map: Dict[int, Dict[str, str]]
) -> List[Dict]:
    """
    Map bracket roster IDs to team names.
    
    Args:
        bracket_data: List of bracket matchup dictionaries
        rosters_map: Roster ID to user info mapping
        
    Returns:
        List of mapped bracket matchups
    """
    mapped_bracket = []
    for matchup in bracket_data:
        mapped_matchup = matchup.copy()
        
        # Map roster IDs to team names
        if 't1' in matchup:
            roster_id1 = matchup['t1']
            mapped_matchup['t1_roster_id'] = roster_id1
            mapped_matchup['t1_team_name'] = rosters_map.get(
                roster_id1, {}
            ).get('team_name', f'Team {roster_id1}')
        
        if 't2' in matchup:
            roster_id2 = matchup['t2']
            mapped_matchup['t2_roster_id'] = roster_id2
            mapped_matchup['t2_team_name'] = rosters_map.get(
                roster_id2, {}
            ).get('team_name', f'Team {roster_id2}')
        
        if 'w' in matchup:
            winner_id = matchup['w']
            mapped_matchup['winner_roster_id'] = winner_id
            mapped_matchup['winner_team_name'] = rosters_map.get(
                winner_id, {}
            ).get('team_name', f'Team {winner_id}')
        
        if 'l' in matchup:
            loser_id = matchup['l']
            mapped_matchup['loser_roster_id'] = loser_id
            mapped_matchup['loser_team_name'] = rosters_map.get(
                loser_id, {}
            ).get('team_name', f'Team {loser_id}')
        
        mapped_bracket.append(mapped_matchup)
    
    return mapped_bracket


def generate_postseason_recap(
    winners_bracket_path: Path,
    losers_bracket_path: Path,
    rosters_map: Dict[int, Dict[str, str]]
) -> Dict:
    """
    Generate complete postseason recap with full brackets.
    
    Args:
        winners_bracket_path: Path to winners bracket JSON
        losers_bracket_path: Path to losers bracket JSON
        rosters_map: Roster ID to user info mapping
        
    Returns:
        Dictionary containing postseason recap data
        
    Raises:
        FileNotFoundError: If bracket files don't exist
        json.JSONDecodeError: If JSON files are invalid
        IOError: If files cannot be read
    """
    with open(winners_bracket_path, 'r') as f:
        winners_bracket = json.load(f)
    
    with open(losers_bracket_path, 'r') as f:
        losers_bracket = json.load(f)
    
    mapped_winners = map_bracket(winners_bracket, rosters_map)
    mapped_losers = map_bracket(losers_bracket, rosters_map)
    
    return {
        'winners_bracket': mapped_winners,
        'losers_bracket': mapped_losers
    }


def generate_weekly_postseason_recap(
    matchups: List[Dict],
    transactions: List[Dict],
    standings: List[Dict],
    players_map: Dict[str, str],
    rosters_map: Dict[int, Dict[str, str]],
    positions_map: Dict[str, List[str]],
    roster_positions: List[str]
) -> Dict:
    """
    Generate weekly postseason recap (similar to regular season but without some awards).
    
    Args:
        matchups: List of matchup dictionaries
        transactions: List of transaction dictionaries
        standings: List of standings dictionaries (if applicable)
        players_map: Player ID to name mapping
        rosters_map: Roster ID to user info mapping
        positions_map: Player ID to fantasy positions mapping
        roster_positions: Roster position structure
        
    Returns:
        Dictionary containing weekly postseason recap data
    """
    # Use the same recap generator but simplified for postseason
    recap = generate_weekly_recap(
        matchups,
        transactions,
        standings if standings else [],
        players_map,
        rosters_map,
        positions_map,
        roster_positions
    )
    
    # Remove regular season specific awards for postseason
    # Keep only matchups (transactions are saved separately)
    return {
        'matchups': recap['matchups']
    }

