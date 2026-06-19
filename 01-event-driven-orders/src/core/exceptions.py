class DomainError(Exception):
    """Base exception for domain-level errors."""


class NotFoundError(DomainError):
    """Raised when a requested resource does not exist."""
