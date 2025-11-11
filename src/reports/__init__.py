"""HTML report generation package for league statistics and recaps."""

from .html_generator import escape_html, format_number
from .weekly_report import generate_weekly_html
from .season_report import generate_season_index
from .all_time_report import generate_all_time_html, generate_all_all_time_reports
from .index_generator import generate_main_index

__all__ = [
    'escape_html',
    'format_number',
    'generate_weekly_html',
    'generate_season_index',
    'generate_all_time_html',
    'generate_all_all_time_reports',
    'generate_main_index',
]

