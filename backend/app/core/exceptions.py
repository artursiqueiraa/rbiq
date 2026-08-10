class IqoLabError(Exception):
    """Base exception for all IQO Strategy Lab application errors."""


class DatabaseUnavailableError(IqoLabError):
    """Raised when the database cannot be reached."""
