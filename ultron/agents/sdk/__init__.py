"""
奥创多智能体协作网络 Python SDK
Ultron Multi-Agent Collaboration Network SDK

安装: pip install ultron-agent-sdk
使用: from ultron_agent_sdk import AgentClient, TaskClient
"""

__version__ = "3.0.0"
__author__ = "奥创 (Ultron)"

from .client import AgentClient, TaskClient, CollaborationClient, MeshClient
from .exceptions import (
    UltronSDKError,
    AgentNotFoundError,
    TaskNotFoundError,
    AuthenticationError,
    APIError
)
from .models import (
    Agent,
    Task,
    TaskResult,
    Session,
    HealthStatus,
    AgentStatus,
    TaskStatus
)

__all__ = [
    "AgentClient",
    "TaskClient", 
    "CollaborationClient",
    "MeshClient",
    "UltronSDKError",
    "AgentNotFoundError",
    "TaskNotFoundError",
    "AuthenticationError",
    "APIError",
    "Agent",
    "Task",
    "TaskResult",
    "Session",
    "HealthStatus",
    "Metrics"
]