"""Utility functions for matchup processing."""
from collections import defaultdict
from typing import Dict, List


def group_matchups_by_id(matchups: List[Dict]) -> Dict[int, List[Dict]]:
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

