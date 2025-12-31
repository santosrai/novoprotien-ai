"""Custom exceptions for the application."""


class ApplicationError(Exception):
    """Base exception for application errors."""
    pass


class AgentError(ApplicationError):
    """Exception raised for agent-related errors."""
    pass


class ToolError(ApplicationError):
    """Exception raised for tool execution errors."""
    pass


class DomainError(ApplicationError):
    """Exception raised for domain logic errors."""
    pass

