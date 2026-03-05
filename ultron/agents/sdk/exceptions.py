"""Ultron SDK Exceptions"""


class UltronSDKError(Exception):
    """Base exception for Ultron SDK"""
    pass


class AgentNotFoundError(UltronSDKError):
    """Agent not found"""
    pass


class TaskNotFoundError(UltronSDKError):
    """Task not found"""
    pass


class AuthenticationError(UltronSDKError):
    """Authentication failed"""
    pass


class APIError(UltronSDKError):
    """API returned an error"""
    pass


class ConnectionError(UltronSDKError):
    """Connection failed"""
    pass


class TimeoutError(UltronSDKError):
    """Request timeout"""
    pass