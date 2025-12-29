"""Generate index pages for HTML reports."""
from pathlib import Path
from typing import List, Optional, Dict
import json

from .html_generator import escape_html, format_number
from .templates import get_html_template, get_navigation


def load_current_standings(munged_dir: Path) -> tuple[Optional[Dict], Optional[str], Optional[int]]:
    """
    Load current season standings data.
    
    Returns:
        Tuple of (standings_data, season, last_week) or (None, None, None) if not found
    """
    # Find most recent season
    seasons = sorted([d.name for d in munged_dir.iterdir() if d.is_dir() and d.name.isdigit()], reverse=True)
    
    if not seasons:
        return None, None, None
    
    current_season = seasons[0]
    reg_season_file = munged_dir / current_season / "regular_season" / "reg_season_recap.json"
    
    if not reg_season_file.exists():
        return None, None, None
    
    with open(reg_season_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Find last week of regular season
    reg_season_dir = munged_dir / current_season / "regular_season"
    weeks = sorted([int(d.name.split('_')[1]) for d in reg_season_dir.iterdir() 
                   if d.is_dir() and d.name.startswith('week_')])
    last_week = weeks[-1] if weeks else 14
    
    return data, current_season, last_week


def generate_standings_table(standings_data: Dict, season: str, last_week: int) -> str:
    """
    Generate HTML table for current standings.
    
    Args:
        standings_data: Standings data from reg_season_recap.json
        season: Current season year
        last_week: Last week of regular season
        
    Returns:
        HTML table string
    """
    html_parts = []
    
    html_parts.append(f'<h2>Current Standings (as of Week {last_week})</h2>')
    html_parts.append('<table class="standings-table">')
    html_parts.append('<thead>')
    html_parts.append('<tr>')
    html_parts.append('<th class="rank">Rank</th>')
    html_parts.append('<th>Team</th>')
    html_parts.append('<th>Record</th>')
    html_parts.append('<th>PF</th>')
    html_parts.append('<th>PA</th>')
    html_parts.append('</tr>')
    html_parts.append('</thead>')
    html_parts.append('<tbody>')
    
    standings = standings_data.get('standings', [])
    
    for rank, team in enumerate(standings, 1):
        team_name = escape_html(team.get('team_name', 'Unknown'))
        wins = team.get('wins', 0)
        losses = team.get('losses', 0)
        ties = team.get('ties', 0)
        pf = team.get('pf', 0)
        pa = team.get('pa', 0)
        
        # Format record
        if ties > 0:
            record = f"{wins}-{losses}-{ties}"
        else:
            record = f"{wins}-{losses}"
        
        html_parts.append('<tr>')
        html_parts.append(f'<td class="rank">{rank}</td>')
        html_parts.append(f'<td>{team_name}</td>')
        html_parts.append(f'<td>{record}</td>')
        html_parts.append(f'<td>{format_number(pf, 2)}</td>')
        html_parts.append(f'<td>{format_number(pa, 2)}</td>')
        html_parts.append('</tr>')
    
    html_parts.append('</tbody>')
    html_parts.append('</table>')
    
    return ''.join(html_parts)


def generate_main_index(
    seasons: List[str],
    output_path: Path,
    all_time_available: bool = True,
    munged_dir: Path = None
) -> None:
    """
    Generate main index page for HTML reports.
    
    Args:
        seasons: List of available season years
        output_path: Path to output HTML file
        all_time_available: Whether all-time stats are available
    """
    title = 'Nu Choate League Hub'
    
    # Navigation
    nav = get_navigation()
    
    # Content
    content_parts = []
    content_parts.append('<h1>Nu Choate League Hub</h1>')
    content_parts.append('<p>Welcome to the Nu Choate League</p>')
    
    # Load and display current standings if available
    if munged_dir:
        standings_data, current_season, last_week = load_current_standings(munged_dir)
        if standings_data and current_season:
            content_parts.append(generate_standings_table(standings_data, current_season, last_week))
            content_parts.append(f'<p style="margin-top: 20px;"><a href="{current_season}/index.html" class="week-link">View {current_season} Season Details →</a></p>')
    
    # Quick links section
    content_parts.append('<h2 style="margin-top: 40px;">Quick Links</h2>')
    content_parts.append('<div class="season-list">')
    
    if seasons:
        latest_season = sorted(seasons, reverse=True)[0]
        content_parts.append('<li>')
        content_parts.append(f'<a href="{latest_season}/index.html">Latest Season ({latest_season})</a>')
        content_parts.append(f'<p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 0.9em;">View weekly recaps, standings, and playoff bracket</p>')
        content_parts.append('</li>')
    
    if all_time_available:
        content_parts.append('<li>')
        content_parts.append('<a href="all_time/index.html">All-Time Statistics</a>')
        content_parts.append('<p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 0.9em;">Career records, head-to-head matchups, and historical data</p>')
        content_parts.append('</li>')
    
    content_parts.append('<li>')
    content_parts.append('<a href="seasons.html">Browse All Seasons</a>')
    content_parts.append('<p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 0.9em;">View reports from previous seasons</p>')
    content_parts.append('</li>')
    
    content_parts.append('</div>')
    
    content = ''.join(content_parts)
    
    # Generate full HTML (index is at root level)
    html = get_html_template(title, nav, content, in_subdirectory=False)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_seasons_index(
    seasons: List[str],
    output_path: Path
) -> None:
    """
    Generate seasons index page listing all available seasons.
    
    Args:
        seasons: List of available season years
        output_path: Path to output HTML file
    """
    title = 'Nu Choate League - Seasons'
    
    # Navigation
    nav = get_navigation()
    
    # Content
    content_parts = []
    content_parts.append('<h1>Seasons</h1>')
    content_parts.append('<p>Browse reports and statistics by season.</p>')
    
    # Seasons list
    if seasons:
        content_parts.append('<div class="season-list">')
        for season in sorted(seasons, reverse=True):
            content_parts.append('<li>')
            content_parts.append(f'<a href="{season}/index.html">{season} Season</a>')
            content_parts.append(f'<p style="margin: 5px 0 0 0; color: #9ca3af; font-size: 0.9em;">Weekly recaps, standings, draft results, and postseason bracket</p>')
            content_parts.append('</li>')
        content_parts.append('</div>')
    else:
        content_parts.append('<p>No seasons available.</p>')
    
    content = ''.join(content_parts)
    
    # Generate full HTML (seasons.html is at root level)
    html = get_html_template(title, nav, content, in_subdirectory=False)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

