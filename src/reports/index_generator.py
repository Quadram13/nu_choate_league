"""Generate index pages for HTML reports."""
from pathlib import Path
from typing import List, Optional

from .html_generator import escape_html
from .templates import get_html_template, get_navigation


def generate_main_index(
    seasons: List[str],
    output_path: Path,
    all_time_available: bool = True
) -> None:
    """
    Generate main index page for HTML reports.
    
    Args:
        seasons: List of available season years
        output_path: Path to output HTML file
        all_time_available: Whether all-time stats are available
    """
    title = 'Nu Choate League - Reports'
    
    # Navigation
    nav = get_navigation()
    
    # Content
    content_parts = []
    content_parts.append('<h1>Nu Choate League Reports</h1>')
    content_parts.append('<p>Welcome to the Nu Choate League statistics and recap reports.</p>')
    
    # All-time stats link
    if all_time_available:
        content_parts.append('<h2>All-Time Statistics</h2>')
        content_parts.append('<ul class="season-list">')
        content_parts.append('<li>')
        content_parts.append('<a href="all_time/standings.html">All-Time Standings</a>')
        content_parts.append(' - Complete career statistics for all managers')
        content_parts.append('</li>')
        content_parts.append('<li>')
        content_parts.append('<a href="all_time/head_to_head.html">Head-to-Head Records</a>')
        content_parts.append(' - Matchup history between all teams')
        content_parts.append('</li>')
        content_parts.append('<li>')
        content_parts.append('<a href="all_time/weekly_high_scores.html">Weekly High Scores</a>')
        content_parts.append(' - Best weekly performances across all seasons')
        content_parts.append('</li>')
        content_parts.append('<li>')
        content_parts.append('<a href="all_time/player_high_scores.html">Player High Scores</a>')
        content_parts.append(' - Best individual player performances')
        content_parts.append('</li>')
        content_parts.append('</ul>')
    
    # Seasons list
    if seasons:
        content_parts.append('<h2>Seasons</h2>')
        content_parts.append('<ul class="season-list">')
        for season in sorted(seasons, reverse=True):
            content_parts.append('<li>')
            content_parts.append(f'<a href="{season}/index.html">{season} Season</a>')
            content_parts.append(' - View weekly recaps, standings, and postseason')
            content_parts.append('</li>')
        content_parts.append('</ul>')
    else:
        content_parts.append('<p>No seasons available.</p>')
    
    content = ''.join(content_parts)
    
    # Generate full HTML
    html = get_html_template(title, nav, content)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

