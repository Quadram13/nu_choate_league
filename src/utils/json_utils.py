"""Utility functions for JSON operations."""
import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_json(file_path: Path) -> Optional[Dict]:
    """
    Load JSON data from a file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Loaded JSON data as dictionary, or None if file doesn't exist or error occurs
        
    Raises:
        json.JSONDecodeError: If JSON is invalid
        IOError: If file cannot be read
    """
    if not file_path.exists():
        return None
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        raise e


def save_json(data: Any, output_path: Path, indent: int = 2) -> None:
    """
    Save data to a JSON file.
    
    Args:
        data: Data to save (must be JSON serializable)
        output_path: Path to output file
        indent: Number of spaces for indentation (default: 2)
        
    Raises:
        IOError: If file cannot be written
        TypeError: If data is not JSON serializable
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)

