"""Generate HTML reports for season summaries."""
from pathlib import Path
from typing import Dict, List, Optional

from .html_generator import escape_html, format_number, format_percentage, format_record
from .templates import get_html_template, get_navigation, get_breadcrumb
from .bracket_generator import generate_simple_bracket
from utils.json_utils import load_json


def generate_draft_section(draft_data: Dict) -> str:
    """
    Generate HTML section for draft results.
    
    Args:
        draft_data: Draft data dictionary with team names as keys
        
    Returns:
        HTML string for draft section
    """
    html = ['<h2>Draft Results</h2>']
    html.append('<div class="draft-container">')
    
    # Sort teams by draft position
    teams = sorted(
        draft_data.items(),
        key=lambda x: x[1].get('draft_position', 999)
    )
    
    for team_name, team_data in teams:
        draft_pos = team_data.get('draft_position', 0)
        picks = team_data.get('picks', [])
        
        html.append('<div class="draft-team">')
        html.append(f'<h3>{escape_html(team_name)} - Pick #{draft_pos}</h3>')
        html.append('<table class="draft-picks-table">')
        html.append('<thead><tr>')
        html.append('<th>Round</th>')
        html.append('<th>Pick</th>')
        html.append('<th>Player</th>')
        html.append('<th>Position</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for pick in picks:
            round_num = pick.get('round', 0)
            pick_no = pick.get('pick_no', 0)
            player_name = escape_html(pick.get('player_name', 'Unknown'))
            position = escape_html(pick.get('position', ''))
            
            html.append('<tr>')
            html.append(f'<td>{round_num}</td>')
            html.append(f'<td>{pick_no}</td>')
            html.append(f'<td><strong>{player_name}</strong></td>')
            html.append(f'<td>{position}</td>')
            html.append('</tr>')
        
        html.append('</tbody>')
        html.append('</table>')
        html.append('</div>')
    
    html.append('</div>')
    return ''.join(html)


def generate_season_index(
    season: str,
    munged_dir: Path,
    output_path: Path,
    weeks: Optional[List[int]] = None,
    draft_data: Optional[Dict] = None
) -> None:
    """
    Generate HTML page for season overview.
    
    Args:
        season: Season year (e.g., "2024")
        munged_dir: Path to munged data directory
        output_path: Path to output HTML file
        weeks: List of week numbers (if None, will be auto-detected)
        draft_data: Draft data dictionary (optional)
    """
    title = f'{season} Season Overview'
    
    # Navigation
    nav = get_navigation(season=season)
    breadcrumb = get_breadcrumb(season=season)
    
    # Content
    content_parts = [breadcrumb]
    content_parts.append(f'<h1>{season} Season</h1>')
    
    # Draft Results (if available)
    if draft_data:
        content_parts.append(generate_draft_section(draft_data))
    
    # Load final standings
    reg_season_path = munged_dir / season / "regular_season" / "reg_season_recap.json"
    if reg_season_path.exists():
        reg_season_data = load_json(reg_season_path)
        if reg_season_data and reg_season_data.get('standings'):
            standings = reg_season_data.get('standings', [])
            content_parts.append('<h2>Final Standings</h2>')
            content_parts.append('<table class="standings-table">')
            content_parts.append('<thead><tr>')
            content_parts.append('<th class="rank">Rank</th>')
            content_parts.append('<th>Team</th>')
            content_parts.append('<th>Record</th>')
            content_parts.append('<th>Win %</th>')
            content_parts.append('<th>PF</th>')
            content_parts.append('<th>PA</th>')
            content_parts.append('</tr></thead>')
            content_parts.append('<tbody>')
            
            for rank, team in enumerate(standings, 1):
                team_name = escape_html(team.get('team_name', 'Unknown'))
                wins = team.get('wins', 0)
                losses = team.get('losses', 0)
                ties = team.get('ties', 0)
                win_pct = team.get('win_pct', 0)
                pf = team.get('pf', 0)
                pa = team.get('pa', 0)
                
                content_parts.append('<tr>')
                content_parts.append(f'<td class="rank">{rank}</td>')
                content_parts.append(f'<td><strong>{team_name}</strong></td>')
                content_parts.append(f'<td>{format_record(wins, losses, ties)}</td>')
                content_parts.append(f'<td>{format_percentage(win_pct)}</td>')
                content_parts.append(f'<td>{format_number(pf)}</td>')
                content_parts.append(f'<td>{format_number(pa)}</td>')
                content_parts.append('</tr>')
            
            content_parts.append('</tbody>')
            content_parts.append('</table>')
    
    # Week links
    if weeks is None:
        # Auto-detect weeks
        season_dir = munged_dir / season / "regular_season"
        if season_dir.exists():
            weeks = []
            for item in season_dir.iterdir():
                if item.is_dir() and item.name.startswith('week_'):
                    try:
                        week_num = int(item.name.split('_')[1])
                        weeks.append(week_num)
                    except (ValueError, IndexError):
                        continue
            weeks.sort()
    
    if weeks:
        content_parts.append('<h2>Weekly Recaps</h2>')
        content_parts.append('<div class="week-links">')
        for week in weeks:
            content_parts.append(f'<a href="week_{week}.html" class="week-link">Week {week}</a>')
        content_parts.append('</div>')
    
    # Postseason link
    postseason_path = munged_dir / season / "postseason" / "postseason_recap.json"
    if postseason_path.exists():
        content_parts.append('<h2>Postseason</h2>')
        content_parts.append('<p><a href="postseason.html" class="week-link">View Playoff Bracket</a></p>')
    
    content = ''.join(content_parts)
    
    # Generate full HTML
    html = get_html_template(title, nav, content)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_postseason_html(
    postseason_data: Dict,
    season: str,
    output_path: Path
) -> None:
    """
    Generate HTML page for postseason bracket.
    
    Args:
        postseason_data: Postseason recap data dictionary
        season: Season year
        output_path: Path to output HTML file
    """
    title = f'{season} Season - Postseason'
    
    # Navigation
    nav = get_navigation(season=season)
    breadcrumb = get_breadcrumb(season=season)
    
    # Content
    content_parts = [breadcrumb]
    content_parts.append(f'<h1>{season} Postseason</h1>')
    
    # Winners bracket - visual bracket
    winners_bracket = postseason_data.get('winners_bracket', [])
    if winners_bracket:
        content_parts.append(generate_simple_bracket(winners_bracket, "Winners Bracket"))
    
    # Losers bracket - visual bracket
    losers_bracket = postseason_data.get('losers_bracket', [])
    if losers_bracket:
        content_parts.append(generate_simple_bracket(losers_bracket, "Losers Bracket"))
    
    content = ''.join(content_parts)
    
    # Generate full HTML
    html = get_html_template(title, nav, content)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

