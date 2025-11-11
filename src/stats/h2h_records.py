"""Head-to-head record building functions."""
from collections import defaultdict
from typing import Dict, Tuple


def build_head_to_head_records(stats_by_user: Dict[str, Dict]) -> Dict[str, Dict[str, Tuple[int, int]]]:
    """
    Build head-to-head records between all managers.
    
    Returns:
        Dict mapping user_id1 to dict mapping user_id2 to (wins, losses) tuple
        where wins is user_id1's wins against user_id2
    """
    h2h_records = defaultdict(lambda: defaultdict(lambda: [0, 0]))  # [wins, losses]
    
    for user_id, user_data in stats_by_user.items():
        for game in user_data.get('games', []):
            opponent_id = game.get('opponent_user_id')
            if opponent_id:
                if game.get('won'):
                    h2h_records[user_id][opponent_id][0] += 1  # win
                else:
                    h2h_records[user_id][opponent_id][1] += 1  # loss
    
    # Convert to tuples
    result = {}
    for user_id, opponents in h2h_records.items():
        result[user_id] = {
            opp_id: (wins, losses)
            for opp_id, (wins, losses) in opponents.items()
        }
    
    return result

