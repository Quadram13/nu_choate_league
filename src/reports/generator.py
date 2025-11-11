"""Main HTML report generator that orchestrates all report generation."""
from pathlib import Path
from typing import List, Optional

from constants import MUNGED_DIR, REPORTS_DIR
from reports import (
    generate_weekly_html,
    generate_season_index,
    generate_main_index,
    generate_all_all_time_reports
)
from reports.season_report import generate_postseason_html
from utils.json_utils import load_json
from utils.logging_utils import get_logger

logger = get_logger('reports')


def generate_all_reports() -> None:
    """
    Generate all HTML reports for all available seasons.
    """
    munged_dir = Path(MUNGED_DIR)
    reports_dir = Path(REPORTS_DIR)
    
    if not munged_dir.exists():
        logger.error(f"Munged directory not found: {munged_dir}")
        return
    
    logger.info("Starting HTML report generation...")
    
    # Find all seasons
    seasons = []
    for item in munged_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            seasons.append(item.name)
    
    if not seasons:
        logger.warning("No seasons found in munged directory")
        return
    
    logger.info(f"Found {len(seasons)} season(s): {', '.join(sorted(seasons))}")
    
    # Generate all-time reports
    logger.info("Generating all-time statistics reports...")
    generate_all_all_time_reports(munged_dir, reports_dir)
    
    # Generate reports for each season
    for season in sorted(seasons):
        logger.info(f"Generating reports for {season} season...")
        season_munged = munged_dir / season
        season_reports = reports_dir / season
        
        # Find all weeks
        regular_season_dir = season_munged / "regular_season"
        weeks = []
        if regular_season_dir.exists():
            for item in regular_season_dir.iterdir():
                if item.is_dir() and item.name.startswith('week_'):
                    try:
                        week_num = int(item.name.split('_')[1])
                        weeks.append(week_num)
                    except (ValueError, IndexError):
                        continue
            weeks.sort()
        
        # Load draft data (for season index)
        draft_data = None
        draft_path = season_munged / "draft.json"
        if draft_path.exists():
            draft_data = load_json(draft_path)
        
        # Generate weekly reports
        for week in weeks:
            week_dir = regular_season_dir / f"week_{week}"
            recap_path = week_dir / "recap.json"
            
            if recap_path.exists():
                recap_data = load_json(recap_path)
                if recap_data:
                    prev_week = weeks[weeks.index(week) - 1] if week in weeks and weeks.index(week) > 0 else None
                    next_week = weeks[weeks.index(week) + 1] if week in weeks and weeks.index(week) < len(weeks) - 1 else None
                    
                    # Load transactions for this week
                    transactions = None
                    transactions_path = week_dir / "transactions.json"
                    if transactions_path.exists():
                        transactions = load_json(transactions_path)
                    
                    output_path = season_reports / f"week_{week}.html"
                    generate_weekly_html(
                        recap_data,
                        week,
                        season,
                        output_path,
                        prev_week=prev_week,
                        next_week=next_week,
                        transactions=transactions
                    )
                    logger.info(f"  Generated week {week} report")
        
        # Generate season index
        season_index_path = season_reports / "index.html"
        generate_season_index(season, munged_dir, season_index_path, weeks=weeks, draft_data=draft_data)
        logger.info(f"  Generated season index")
        
        # Generate postseason report
        postseason_path = season_munged / "postseason" / "postseason_recap.json"
        if postseason_path.exists():
            postseason_data = load_json(postseason_path)
            if postseason_data:
                postseason_output = season_reports / "postseason.html"
                generate_postseason_html(postseason_data, season, postseason_output)
                logger.info(f"  Generated postseason report")
    
    # Generate main index
    all_time_dir = munged_dir / "all_time"
    all_time_available = all_time_dir.exists() and any(all_time_dir.glob("*.csv"))
    
    main_index_path = reports_dir / "index.html"
    generate_main_index(seasons, main_index_path, all_time_available=all_time_available)
    logger.info("Generated main index page")
    
    logger.info(f"HTML reports generated successfully in {reports_dir}")

