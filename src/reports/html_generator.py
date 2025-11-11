"""Core HTML generation utility functions."""
from typing import Any, Optional


def escape_html(text: Any) -> str:
    """
    Escape HTML special characters.
    
    Args:
        text: Text to escape (will be converted to string)
        
    Returns:
        Escaped HTML string
    """
    if text is None:
        return ''
    
    text_str = str(text)
    return (text_str
            .replace('&', '&amp;')
            .replace('<', '&lt;')
            .replace('>', '&gt;')
            .replace('"', '&quot;')
            .replace("'", '&#x27;'))


def format_number(value: Optional[float], decimals: int = 2) -> str:
    """
    Format a number for display.
    
    Args:
        value: Number to format
        decimals: Number of decimal places
        
    Returns:
        Formatted number string
    """
    if value is None:
        return 'N/A'
    
    try:
        return f'{value:.{decimals}f}'
    except (ValueError, TypeError):
        return str(value)


def format_percentage(value: Optional[float], decimals: int = 1) -> str:
    """
    Format a percentage for display.
    
    Args:
        value: Percentage value (0-1 or 0-100)
        decimals: Number of decimal places
        
    Returns:
        Formatted percentage string
    """
    if value is None:
        return 'N/A'
    
    try:
        # If value is between 0 and 1, assume it's a decimal (0.7 = 70%)
        if 0 <= value <= 1:
            return f'{value * 100:.{decimals}f}%'
        # Otherwise assume it's already a percentage
        return f'{value:.{decimals}f}%'
    except (ValueError, TypeError):
        return str(value)


def format_record(wins: int, losses: int, ties: int = 0) -> str:
    """
    Format a win-loss record.
    
    Args:
        wins: Number of wins
        losses: Number of losses
        ties: Number of ties (default: 0)
        
    Returns:
        Formatted record string (e.g., "7-3-0" or "7-3")
    """
    if ties > 0:
        return f'{wins}-{losses}-{ties}'
    return f'{wins}-{losses}'

