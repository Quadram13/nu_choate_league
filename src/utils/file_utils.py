"""Utility functions for file operations."""
from pathlib import Path
from typing import List


def ensure_directory(dir_path: Path) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        dir_path: Path to directory
        
    Returns:
        Path object for the directory
        
    Raises:
        OSError: If directory cannot be created
    """
    dir_path.mkdir(parents=True, exist_ok=True)
    return dir_path


def get_season_directories(base_dir: Path) -> List[Path]:
    """
    Get all valid season directories from a base directory.
    
    Args:
        base_dir: Base directory containing season folders
        
    Returns:
        List of Path objects for valid season directories (sorted)
    """
    if not base_dir.exists():
        return []
    
    season_dirs = []
    for item in base_dir.iterdir():
        if item.is_dir() and item.name.isdigit():
            # Check if it has league_info.json to confirm it's a valid season
            if (item / "league_info.json").exists():
                season_dirs.append(item)
    
    return sorted(season_dirs, reverse=True)

