"""Custom exception classes for the application."""


class NuChoateLeagueError(Exception):
    """Base exception for all application errors."""
    pass


class APIError(NuChoateLeagueError):
    """Exception raised for API-related errors."""
    
    def __init__(self, message: str, status_code: int = None, url: str = None):
        super().__init__(message)
        self.status_code = status_code
        self.url = url


class DataValidationError(NuChoateLeagueError):
    """Exception raised for data validation errors."""
    pass


class FileOperationError(NuChoateLeagueError):
    """Exception raised for file operation errors."""
    pass


class ConfigurationError(NuChoateLeagueError):
    """Exception raised for configuration errors."""
    pass

