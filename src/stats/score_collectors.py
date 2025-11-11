"""Score collection functions for high scores."""
from pathlib import Path
from typing import Dict, List

from utils.json_utils import load_json
from utils.logging_utils import get_logger

logger = get_logger('stats.score_collectors')


def collect_weekly_high_scores(munged_dir: Path) -> List[Dict]:
    """
    Collect all weekly team scores across all seasons (regular season and postseason).
    
    Returns:
        List of dicts with keys: points, year, week, team_name
    """
    weekly_scores = []
    
    # Get all season directories
    season_dirs = sorted([
        item for item in munged_dir.iterdir()
        if item.is_dir() and item.name.isdigit()
    ])
    
    for season_dir in season_dirs:
        year = season_dir.name
        
        # Process regular season weeks
        regular_season_dir = season_dir / "regular_season"
        if regular_season_dir.exists():
            for week_dir in sorted(regular_season_dir.iterdir()):
                if not week_dir.is_dir() or not week_dir.name.startswith("week_"):
                    continue
                
                recap_path = week_dir / "recap.json"
                if not recap_path.exists():
                    continue
                
                try:
                    recap_data = load_json(recap_path)
                    if recap_data is None:
                        continue
                    
                    matchups = recap_data.get('matchups', [])
                    for matchup in matchups:
                        points = matchup.get('points', 0.0)
                        team_name = matchup.get('team_name', 'Unknown')
                        week_num = int(week_dir.name.replace('week_', ''))
                        
                        weekly_scores.append({
                            'points': points,
                            'year': year,
                            'week': week_num,
                            'team_name': team_name
                        })
                except Exception as e:
                    logger.error(f"  Error processing {recap_path}: {e}")
                    continue
        
        # Process postseason weeks
        postseason_dir = season_dir / "postseason"
        if postseason_dir.exists():
            # Process week_N_recap.json files
            for recap_file in sorted(postseason_dir.glob("week_*_recap.json")):
                try:
                    # Extract week number from filename (e.g., "week_15_recap.json" -> 15)
                    week_str = recap_file.stem.replace('week_', '').replace('_recap', '')
                    week_num = int(week_str)
                    
                    recap_data = load_json(recap_file)
                    if recap_data is None:
                        continue
                    
                    matchups = recap_data.get('matchups', [])
                    for matchup in matchups:
                        points = matchup.get('points', 0.0)
                        team_name = matchup.get('team_name', 'Unknown')
                        
                        weekly_scores.append({
                            'points': points,
                            'year': year,
                            'week': week_num,
                            'team_name': team_name
                        })
                except Exception as e:
                    logger.error(f"  Error processing {recap_file}: {e}")
                    continue
    
    return weekly_scores


def collect_player_high_scores(munged_dir: Path) -> List[Dict]:
    """
    Collect all individual player scores across all seasons (regular season and postseason).
    
    Returns:
        List of dicts with keys: points, year, week, player_name, team_name
    """
    player_scores = []
    
    # Get all season directories
    season_dirs = sorted([
        item for item in munged_dir.iterdir()
        if item.is_dir() and item.name.isdigit()
    ])
    
    for season_dir in season_dirs:
        year = season_dir.name
        
        # Process regular season weeks
        regular_season_dir = season_dir / "regular_season"
        if regular_season_dir.exists():
            for week_dir in sorted(regular_season_dir.iterdir()):
                if not week_dir.is_dir() or not week_dir.name.startswith("week_"):
                    continue
                
                recap_path = week_dir / "recap.json"
                if not recap_path.exists():
                    continue
                
                try:
                    recap_data = load_json(recap_path)
                    if recap_data is None:
                        continue
                    
                    matchups = recap_data.get('matchups', [])
                    for matchup in matchups:
                        team_name = matchup.get('team_name', 'Unknown')
                        week_num = int(week_dir.name.replace('week_', ''))
                        
                        # Process starters
                        starters = matchup.get('starters', [])
                        for player in starters:
                            points = player.get('points', 0.0)
                            player_name = player.get('player_name', 'Unknown')
                            
                            player_scores.append({
                                'points': points,
                                'year': year,
                                'week': week_num,
                                'player_name': player_name,
                                'team_name': team_name
                            })
                        
                        # Process bench players
                        bench = matchup.get('bench', [])
                        for player in bench:
                            points = player.get('points', 0.0)
                            player_name = player.get('player_name', 'Unknown')
                            
                            player_scores.append({
                                'points': points,
                                'year': year,
                                'week': week_num,
                                'player_name': player_name,
                                'team_name': team_name
                            })
                except Exception as e:
                    logger.error(f"  Error processing {recap_path}: {e}")
                    continue
        
        # Process postseason weeks
        postseason_dir = season_dir / "postseason"
        if postseason_dir.exists():
            # Process week_N_recap.json files
            for recap_file in sorted(postseason_dir.glob("week_*_recap.json")):
                try:
                    # Extract week number from filename (e.g., "week_15_recap.json" -> 15)
                    week_str = recap_file.stem.replace('week_', '').replace('_recap', '')
                    week_num = int(week_str)
                    
                    recap_data = load_json(recap_file)
                    if recap_data is None:
                        continue
                    
                    matchups = recap_data.get('matchups', [])
                    for matchup in matchups:
                        team_name = matchup.get('team_name', 'Unknown')
                        
                        # Process starters
                        starters = matchup.get('starters', [])
                        for player in starters:
                            points = player.get('points', 0.0)
                            player_name = player.get('player_name', 'Unknown')
                            
                            player_scores.append({
                                'points': points,
                                'year': year,
                                'week': week_num,
                                'player_name': player_name,
                                'team_name': team_name
                            })
                        
                        # Process bench players
                        bench = matchup.get('bench', [])
                        for player in bench:
                            points = player.get('points', 0.0)
                            player_name = player.get('player_name', 'Unknown')
                            
                            player_scores.append({
                                'points': points,
                                'year': year,
                                'week': week_num,
                                'player_name': player_name,
                                'team_name': team_name
                            })
                except Exception as e:
                    logger.error(f"  Error processing {recap_file}: {e}")
                    continue
    
    return player_scores

