"""CSV generation functions for all-time statistics."""
import csv
from pathlib import Path
from typing import Dict

from stats.data_collector import collect_all_season_data
from stats.statistics_calculator import (
    calculate_manager_stats,
    calculate_lucky_unlucky_and_extremes
)
from stats.h2h_records import build_head_to_head_records
from stats.score_collectors import (
    collect_weekly_high_scores,
    collect_player_high_scores
)
from utils.logging_utils import get_logger

logger = get_logger('stats.csv_generators')


def generate_all_time_standings_csv(unmunged_dir: Path, output_path: Path) -> None:
    """
    Generate all-time standings CSV file.
    
    Args:
        unmunged_dir: Path to unmunged directory (e.g., src/data/unmunged)
        output_path: Path to output CSV file (e.g., src/data/munged/all_time/standings.csv)
    """
    logger.info("Collecting all-time statistics...")
    stats_by_user, user_id_to_display_name = collect_all_season_data(unmunged_dir)
    
    logger.info("Calculating lucky/unlucky and extreme weeks...")
    calculate_lucky_unlucky_and_extremes(stats_by_user, unmunged_dir)
    
    logger.info("Calculating manager statistics...")
    manager_stats = []
    
    for user_id, user_data in stats_by_user.items():
        stats = calculate_manager_stats(
            user_id,
            user_data['games'],
            user_data['all_scores'],
            user_data['weeks_above_median'],
            user_data['total_weeks'],
            user_data['seasons']
        )
        
        if stats:
            # Add lucky/unlucky and extremes
            stats['lucky_wins'] = user_data.get('lucky_wins', 0)
            stats['unlucky_losses'] = user_data.get('unlucky_losses', 0)
            stats['top_score_weeks'] = user_data.get('top_score_weeks', 0)
            stats['low_score_weeks'] = user_data.get('low_score_weeks', 0)
            stats['display_name'] = user_id_to_display_name.get(user_id, user_id)
            manager_stats.append(stats)
    
    # Sort by win percentage (desc), then total PF (desc)
    manager_stats.sort(key=lambda x: (x['win_pct'], x['total_pf']), reverse=True)
    
    # Write CSV
    logger.info(f"Writing CSV to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow([
            '#', 'Manager', 'Seasons', 'Games Played', 'H2H Record (W-L)', 'H2H Win %',
            'Total PF', 'Avg PF', 'Total PA', 'Avg PA', 'Avg Margin',
            'Avg Win Margin', 'Avg Loss Margin', 'High Score', 'Low Score',
            'Largest Win', 'Smallest Win', 'Largest Loss', 'Smallest Loss',
            'Median Win %', 'Unlucky Losses', 'Lucky Wins',
            'Points StDev', 'Top Score Weeks', 'Low Score Weeks'
        ])
        
        # Write data rows
        for idx, stats in enumerate(manager_stats, 1):
            h2h_record = f"{stats['wins']}-{stats['losses']}"
            
            high_score_str = f"{stats['high_score'][0]:.2f} ({stats['high_score'][1]} Wk{stats['high_score'][2]})"
            low_score_str = f"{stats['low_score'][0]:.2f} ({stats['low_score'][1]} Wk{stats['low_score'][2]})"
            
            largest_win_str = f"{stats['largest_win'][0]:.2f} ({stats['largest_win'][1]} Wk{stats['largest_win'][2]})" if stats['largest_win'][1] else "0.00 ()"
            smallest_win_str = f"{stats['smallest_win'][0]:.2f} ({stats['smallest_win'][1]} Wk{stats['smallest_win'][2]})" if stats['smallest_win'][1] else "0.00 ()"
            
            largest_loss_str = f"{stats['largest_loss'][0]:.2f} ({stats['largest_loss'][1]} Wk{stats['largest_loss'][2]})" if stats['largest_loss'][1] else "0.00 ()"
            smallest_loss_str = f"{stats['smallest_loss'][0]:.2f} ({stats['smallest_loss'][1]} Wk{stats['smallest_loss'][2]})" if stats['smallest_loss'][1] else "0.00 ()"
            
            writer.writerow([
                idx,
                stats['display_name'],
                stats['seasons'],
                stats['games_played'],
                h2h_record,
                f"{stats['win_pct']:.1f}%",
                f"{stats['total_pf']:.2f}",
                f"{stats['avg_pf']:.2f}",
                f"{stats['total_pa']:.2f}",
                f"{stats['avg_pa']:.2f}",
                f"{stats['avg_margin']:.2f}",
                f"{stats['avg_win_margin']:.2f}",
                f"{stats['avg_loss_margin']:.2f}",
                high_score_str,
                low_score_str,
                largest_win_str,
                smallest_win_str,
                largest_loss_str,
                smallest_loss_str,
                f"{stats['median_win_pct']:.1f}%",
                stats['unlucky_losses'],
                stats['lucky_wins'],
                f"{stats['points_stdev']:.2f}",
                stats['top_score_weeks'],
                stats['low_score_weeks']
            ])
    
    logger.info(f"All-time standings CSV generated successfully!")


def generate_head_to_head_csv(
    unmunged_dir: Path,
    output_path: Path
) -> None:
    """
    Generate head-to-head record matrix CSV file.
    
    Args:
        unmunged_dir: Path to unmunged directory (e.g., src/data/unmunged)
        output_path: Path to output CSV file (e.g., src/data/munged/all_time/head_to_head.csv)
    """
    logger.info("Collecting all-time statistics for head-to-head records...")
    stats_by_user, user_id_to_display_name = collect_all_season_data(unmunged_dir)
    
    logger.info("Building head-to-head records...")
    h2h_records = build_head_to_head_records(stats_by_user)
    
    # Get all unique user IDs, sorted by display name
    all_user_ids = sorted(
        set(stats_by_user.keys()),
        key=lambda uid: user_id_to_display_name.get(uid, uid)
    )
    
    # Write CSV
    logger.info(f"Writing head-to-head CSV to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header row
        header = [''] + [user_id_to_display_name.get(uid, uid) for uid in all_user_ids]
        writer.writerow(header)
        
        # Write data rows
        for row_user_id in all_user_ids:
            row_name = user_id_to_display_name.get(row_user_id, row_user_id)
            row_data = [row_name]
            
            for col_user_id in all_user_ids:
                if row_user_id == col_user_id:
                    # Diagonal: no self-competition
                    row_data.append('—')
                else:
                    # Get head-to-head record
                    wins, losses = h2h_records.get(row_user_id, {}).get(col_user_id, (0, 0))
                    row_data.append(f"{wins}-{losses}")
            
            writer.writerow(row_data)
    
    logger.info(f"Head-to-head CSV generated successfully!")


def generate_weekly_high_scores_csv(munged_dir: Path, output_path: Path) -> None:
    """
    Generate CSV file with top 10 all-time weekly high scores.
    
    Args:
        munged_dir: Path to munged directory (e.g., src/data/munged)
        output_path: Path to output CSV file
    """
    logger.info("Collecting all weekly high scores...")
    weekly_scores = collect_weekly_high_scores(munged_dir)
    
    # Sort by points descending and take top 10
    weekly_scores.sort(key=lambda x: x['points'], reverse=True)
    top_10 = weekly_scores[:10]
    
    # Write CSV
    logger.info(f"Writing weekly high scores CSV to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['#', 'Points', 'Year', 'Week', 'Team'])
        
        # Write data rows
        for idx, score in enumerate(top_10, 1):
            writer.writerow([
                idx,
                f"{score['points']:.2f}",
                score['year'],
                score['week'],
                score['team_name']
            ])
    
    logger.info(f"Weekly high scores CSV generated successfully!")


def generate_player_high_scores_csv(munged_dir: Path, output_path: Path) -> None:
    """
    Generate CSV file with top 10 all-time player high scores.
    
    Args:
        munged_dir: Path to munged directory (e.g., src/data/munged)
        output_path: Path to output CSV file
    """
    logger.info("Collecting all player high scores...")
    player_scores = collect_player_high_scores(munged_dir)
    
    # Sort by points descending and take top 10
    player_scores.sort(key=lambda x: x['points'], reverse=True)
    top_10 = player_scores[:10]
    
    # Write CSV
    logger.info(f"Writing player high scores CSV to {output_path}...")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Write header
        writer.writerow(['#', 'Points', 'Player', 'Year', 'Week', 'Team'])
        
        # Write data rows
        for idx, score in enumerate(top_10, 1):
            writer.writerow([
                idx,
                f"{score['points']:.2f}",
                score['player_name'],
                score['year'],
                score['week'],
                score['team_name']
            ])
    
    logger.info(f"Player high scores CSV generated successfully!")

