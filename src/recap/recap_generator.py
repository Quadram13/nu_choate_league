"""Main recap generation for weekly and season recaps."""
from typing import Dict, List

from recap.matchup_processor import process_matchups, map_matchups
from recap.awards import calculate_awards


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
     highest_starters_team, lowest_starters_team, benchwarmers_team) = process_matchups(
        matchups, rosters_map, players_map, positions_map, roster_positions
    )
    
    # Calculate awards
    awards = calculate_awards(
        standings, matchup_results, rosters_map,
        matchups, positions_map, roster_positions, players_map
    )
    
    # Map matchups (transactions are handled separately and saved to their own file)
    mapped_matchups = map_matchups(matchups, players_map, rosters_map, positions_map)
    
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

