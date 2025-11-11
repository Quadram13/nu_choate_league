"""Generate visual bracket displays for postseason."""
from typing import Dict, List, Optional

from .html_generator import escape_html


def resolve_team_name(matchup: Dict, matchup_map: Dict[int, Dict], bracket: List[Dict]) -> str:
    """
    Resolve team name from matchup dependencies.
    
    Args:
        matchup: Current matchup dictionary
        matchup_map: Map of matchup_id to matchup data
        bracket: Full bracket list
        
    Returns:
        Team name string
    """
    # Direct team name
    if matchup.get('t1_team_name') and matchup['t1_team_name'] != 'Team None':
        return matchup.get('t1_team_name', 'TBD')
    
    # Check if team comes from another matchup
    t1_from = matchup.get('t1_from', {})
    if t1_from:
        # Get winner or loser from referenced matchup
        ref_matchup_id = t1_from.get('w') or t1_from.get('l')
        if ref_matchup_id:
            ref_matchup = matchup_map.get(ref_matchup_id)
            if ref_matchup:
                if 'w' in t1_from:
                    return ref_matchup.get('winner_team_name', 'TBD')
                else:
                    return ref_matchup.get('loser_team_name', 'TBD')
    
    return 'TBD'


def organize_bracket_by_round(bracket: List[Dict]) -> Dict[int, List[Dict]]:
    """
    Organize bracket matchups by round number.
    
    Args:
        bracket: List of matchup dictionaries
        
    Returns:
        Dictionary mapping round number to list of matchups
    """
    rounds = {}
    matchup_map = {m.get('m'): m for m in bracket if m.get('m')}
    
    for matchup in bracket:
        round_num = matchup.get('r')
        if round_num:
            if round_num not in rounds:
                rounds[round_num] = []
            rounds[round_num].append(matchup)
    
    # Sort matchups within each round by matchup ID
    for round_num in rounds:
        rounds[round_num].sort(key=lambda m: m.get('m', 0))
    
    return rounds


def generate_visual_bracket(bracket: List[Dict], bracket_name: str = "Bracket") -> str:
    """
    Generate visual bracket HTML similar to tournament bracket style.
    
    Args:
        bracket: List of matchup dictionaries
        bracket_name: Name of the bracket (e.g., "Winners Bracket")
        
    Returns:
        HTML string for the visual bracket
    """
    if not bracket:
        return f'<p>No {bracket_name.lower()} data available.</p>'
    
    # Organize by rounds
    rounds = organize_bracket_by_round(bracket)
    matchup_map = {m.get('m'): m for m in bracket if m.get('m')}
    
    if not rounds:
        return f'<p>No {bracket_name.lower()} data available.</p>'
    
    html = [f'<h2>{bracket_name}</h2>']
    html.append('<div class="bracket-container">')
    html.append('<div class="bracket-wrapper">')
    
    # Get max round number
    max_round = max(rounds.keys())
    
    # Generate each round
    for round_num in sorted(rounds.keys()):
        round_matchups = rounds[round_num]
        is_final = round_num == max_round
        
        html.append('<div class="bracket-round">')
        
        # Round label
        if is_final:
            html.append('<div class="bracket-round-label">🏆 FINAL</div>')
        else:
            html.append(f'<div class="bracket-round-label">Round {round_num}</div>')
        
        # Generate matchups for this round
        for matchup in round_matchups:
            html.append('<div class="bracket-matchup">')
            
            # Team 1
            team1_name = matchup.get('t1_team_name', 'TBD')
            if not team1_name or team1_name == 'Team None':
                team1_name = resolve_team_name(matchup, matchup_map, bracket)
            
            winner_name = matchup.get('winner_team_name', '')
            is_winner1 = winner_name and team1_name == winner_name
            
            team1_class = 'winner' if is_winner1 else ('tbd' if team1_name == 'TBD' else '')
            final_class = 'bracket-final' if is_final else ''
            
            html.append(f'<div class="bracket-team {team1_class} {final_class}">')
            html.append(escape_html(team1_name))
            html.append('</div>')
            
            # Team 2 (if exists)
            team2_name = matchup.get('t2_team_name', 'TBD')
            if not team2_name or team2_name == 'Team None':
                t2_from = matchup.get('t2_from', {})
                if t2_from:
                    ref_matchup_id = t2_from.get('w') or t2_from.get('l')
                    if ref_matchup_id:
                        ref_matchup = matchup_map.get(ref_matchup_id)
                        if ref_matchup:
                            if 'w' in t2_from:
                                team2_name = ref_matchup.get('winner_team_name', 'TBD')
                            else:
                                team2_name = ref_matchup.get('loser_team_name', 'TBD')
            
            if team2_name and team2_name != 'Team None':
                is_winner2 = winner_name and team2_name == winner_name
                team2_class = 'winner' if is_winner2 else ('tbd' if team2_name == 'TBD' else '')
                
                html.append(f'<div class="bracket-team {team2_class} {final_class}">')
                html.append(escape_html(team2_name))
                html.append('</div>')
            
            html.append('</div>')  # End matchup
        
        html.append('</div>')  # End round
    
    html.append('</div>')  # End wrapper
    html.append('</div>')  # End container
    
    return ''.join(html)


def get_team_from_matchup(matchup: Dict, matchup_map: Dict[int, Dict], bracket: List[Dict], is_team1: bool = True) -> str:
    """
    Get team name from matchup, resolving dependencies.
    
    Args:
        matchup: Current matchup dictionary
        matchup_map: Map of matchup_id to matchup data
        bracket: Full bracket list
        is_team1: Whether to get team1 (True) or team2 (False)
        
    Returns:
        Team name string
    """
    if is_team1:
        team_name = matchup.get('t1_team_name', 'TBD')
        if not team_name or team_name == 'Team None':
            team_name = resolve_team_name(matchup, matchup_map, bracket)
        return team_name
    else:
        team_name = matchup.get('t2_team_name', 'TBD')
        if not team_name or team_name == 'Team None':
            t2_from = matchup.get('t2_from', {})
            if t2_from:
                ref_matchup_id = t2_from.get('w') or t2_from.get('l')
                if ref_matchup_id:
                    ref_matchup = matchup_map.get(ref_matchup_id)
                    if ref_matchup:
                        if 'w' in t2_from:
                            team_name = ref_matchup.get('winner_team_name', 'TBD')
                        else:
                            team_name = ref_matchup.get('loser_team_name', 'TBD')
        return team_name


def generate_simple_bracket(bracket: List[Dict], bracket_name: str = "Bracket") -> str:
    """
    Generate a tournament-style visual bracket display.
    
    Args:
        bracket: List of matchup dictionaries
        bracket_name: Name of the bracket
        
    Returns:
        HTML string for the bracket
    """
    if not bracket:
        return f'<p>No {bracket_name.lower()} data available.</p>'
    
    rounds = organize_bracket_by_round(bracket)
    matchup_map = {m.get('m'): m for m in bracket if m.get('m')}
    
    if not rounds:
        return f'<p>No {bracket_name.lower()} data available.</p>'
    
    html = [f'<h2>{bracket_name}</h2>']
    html.append('<div class="bracket-container">')
    html.append('<div class="bracket-wrapper">')
    
    max_round = max(rounds.keys())
    
    # Generate each round from left to right
    for round_num in sorted(rounds.keys()):
        round_matchups = rounds[round_num]
        is_final = round_num == max_round
        
        html.append('<div class="bracket-round">')
        html.append(f'<div class="bracket-round-label">{"🏆 FINAL" if is_final else f"Round {round_num}"}</div>')
        
        for matchup in round_matchups:
            html.append('<div class="bracket-matchup">')
            
            # Team 1
            team1_name = get_team_from_matchup(matchup, matchup_map, bracket, is_team1=True)
            winner_name = matchup.get('winner_team_name', '')
            is_winner1 = winner_name and team1_name == winner_name
            
            team1_class = 'winner' if is_winner1 else ('tbd' if team1_name == 'TBD' else '')
            final_class = 'bracket-final' if is_final else ''
            
            html.append(f'<div class="bracket-team {team1_class} {final_class}">')
            html.append(escape_html(team1_name))
            html.append('</div>')
            
            # Team 2 (if exists)
            team2_name = get_team_from_matchup(matchup, matchup_map, bracket, is_team1=False)
            if team2_name and team2_name != 'Team None':
                is_winner2 = winner_name and team2_name == winner_name
                team2_class = 'winner' if is_winner2 else ('tbd' if team2_name == 'TBD' else '')
                
                html.append(f'<div class="bracket-team {team2_class} {final_class}">')
                html.append(escape_html(team2_name))
                html.append('</div>')
            
            html.append('</div>')  # End matchup
        
        html.append('</div>')  # End round
    
    html.append('</div>')  # End wrapper
    html.append('</div>')  # End container
    
    return ''.join(html)

