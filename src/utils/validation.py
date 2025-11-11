"""Validation utilities for data processing."""
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.exceptions import DataValidationError


def validate_path(path: Path, must_exist: bool = False, must_be_file: bool = False, must_be_dir: bool = False) -> None:
    """
    Validate a file path.
    
    Args:
        path: Path to validate
        must_exist: If True, path must exist
        must_be_file: If True, path must be a file
        must_be_dir: If True, path must be a directory
        
    Raises:
        DataValidationError: If validation fails
    """
    if must_exist and not path.exists():
        raise DataValidationError(f"Path does not exist: {path}")
    
    if must_be_file and not path.is_file():
        raise DataValidationError(f"Path is not a file: {path}")
    
    if must_be_dir and not path.is_dir():
        raise DataValidationError(f"Path is not a directory: {path}")


def validate_dict(data: Any, name: str = "data", required_keys: Optional[List[str]] = None) -> Dict:
    """
    Validate that data is a dictionary and contains required keys.
    
    Args:
        data: Data to validate
        name: Name of the data for error messages
        required_keys: List of required keys
        
    Returns:
        Validated dictionary
        
    Raises:
        DataValidationError: If validation fails
    """
    if not isinstance(data, dict):
        raise DataValidationError(f"{name} must be a dictionary, got {type(data).__name__}")
    
    if required_keys:
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            raise DataValidationError(f"{name} missing required keys: {missing_keys}")
    
    return data


def validate_list(data: Any, name: str = "data", min_length: Optional[int] = None) -> List:
    """
    Validate that data is a list.
    
    Args:
        data: Data to validate
        name: Name of the data for error messages
        min_length: Minimum required length
        
    Returns:
        Validated list
        
    Raises:
        DataValidationError: If validation fails
    """
    if not isinstance(data, list):
        raise DataValidationError(f"{name} must be a list, got {type(data).__name__}")
    
    if min_length is not None and len(data) < min_length:
        raise DataValidationError(f"{name} must have at least {min_length} items, got {len(data)}")
    
    return data


def validate_not_none(value: Any, name: str = "value") -> Any:
    """
    Validate that a value is not None.
    
    Args:
        value: Value to validate
        name: Name of the value for error messages
        
    Returns:
        Validated value
        
    Raises:
        DataValidationError: If value is None
    """
    if value is None:
        raise DataValidationError(f"{name} cannot be None")
    return value


def validate_season_year(year: str) -> str:
    """
    Validate that a season year is a valid 4-digit year string.
    
    Args:
        year: Year string to validate
        
    Returns:
        Validated year string
        
    Raises:
        DataValidationError: If year is invalid
    """
    if not isinstance(year, str):
        raise DataValidationError(f"Season year must be a string, got {type(year).__name__}")
    
    if not year.isdigit() or len(year) != 4:
        raise DataValidationError(f"Season year must be a 4-digit string, got '{year}'")
    
    year_int = int(year)
    if year_int < 2000 or year_int > 2100:
        raise DataValidationError(f"Season year must be between 2000 and 2100, got {year_int}")
    
    return year

