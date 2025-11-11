"""Generate HTML reports for all-time statistics."""
import csv
from pathlib import Path
from typing import List

from .html_generator import escape_html
from .templates import get_html_template, get_navigation, get_breadcrumb


def csv_to_html_table(csv_path: Path, max_rows: int = None) -> str:
    """
    Convert CSV file to HTML table.
    
    Args:
        csv_path: Path to CSV file
        max_rows: Maximum number of rows to display (None for all)
        
    Returns:
        HTML table string
    """
    if not csv_path.exists():
        return '<p>Data file not found.</p>'
    
    html = ['<table>']
    
    try:
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            if header:
                html.append('<thead><tr>')
                for col in header:
                    # Remove # prefix if present
                    col_name = col.lstrip('#')
                    html.append(f'<th>{escape_html(col_name)}</th>')
                html.append('</tr></thead>')
                html.append('<tbody>')
                
                row_count = 0
                for row in reader:
                    if max_rows and row_count >= max_rows:
                        break
                    
                    html.append('<tr>')
                    for cell in row:
                        html.append(f'<td>{escape_html(cell)}</td>')
                    html.append('</tr>')
                    row_count += 1
                
                html.append('</tbody>')
    except Exception as e:
        return f'<p>Error reading CSV file: {escape_html(str(e))}</p>'
    
    html.append('</table>')
    return ''.join(html)


def generate_all_time_html(
    csv_path: Path,
    output_path: Path,
    report_type: str,
    title: str = None
) -> None:
    """
    Generate HTML page for all-time statistics.
    
    Args:
        csv_path: Path to CSV file
        output_path: Path to output HTML file
        report_type: Type of report (e.g., 'standings', 'head_to_head', etc.)
        title: Custom title (if None, will be generated from report_type)
    """
    if title is None:
        title_map = {
            'standings': 'All-Time Standings',
            'head_to_head': 'All-Time Head-to-Head Records',
            'weekly_high_scores': 'Weekly High Scores',
            'player_high_scores': 'Player High Scores'
        }
        title = title_map.get(report_type, 'All-Time Statistics')
    
    full_title = f'{title} - All-Time Stats'
    
    # Navigation - all-time pages are in a subdirectory
    nav = get_navigation(in_subdirectory=True)
    breadcrumb = get_breadcrumb(in_subdirectory=True)
    
    # Content
    content_parts = [breadcrumb]
    content_parts.append(f'<h1>{title}</h1>')
    
    # Generate table from CSV
    table_html = csv_to_html_table(csv_path)
    content_parts.append(table_html)
    
    content = ''.join(content_parts)
    
    # Generate full HTML
    html = get_html_template(full_title, nav, content)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)


def generate_all_all_time_reports(munged_dir: Path, reports_dir: Path) -> None:
    """
    Generate all all-time statistics HTML reports.
    
    Args:
        munged_dir: Path to munged data directory
        reports_dir: Path to reports output directory
    """
    all_time_dir = munged_dir / "all_time"
    all_time_reports_dir = reports_dir / "all_time"
    
    if not all_time_dir.exists():
        return
    
    # Standings
    standings_csv = all_time_dir / "standings.csv"
    if standings_csv.exists():
        generate_all_time_html(
            standings_csv,
            all_time_reports_dir / "standings.html",
            'standings'
        )
    
    # Head-to-Head
    h2h_csv = all_time_dir / "head_to_head.csv"
    if h2h_csv.exists():
        generate_all_time_html(
            h2h_csv,
            all_time_reports_dir / "head_to_head.html",
            'head_to_head'
        )
    
    # Weekly High Scores
    weekly_high_csv = all_time_dir / "weekly_high_scores.csv"
    if weekly_high_csv.exists():
        generate_all_time_html(
            weekly_high_csv,
            all_time_reports_dir / "weekly_high_scores.html",
            'weekly_high_scores'
        )
    
    # Player High Scores
    player_high_csv = all_time_dir / "player_high_scores.csv"
    if player_high_csv.exists():
        generate_all_time_html(
            player_high_csv,
            all_time_reports_dir / "player_high_scores.html",
            'player_high_scores'
        )

