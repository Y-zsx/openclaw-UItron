"""SDK数据模型"""
# 模型已在client.py中通过dataclass定义
# 此文件用于向后兼容和导入

from .client import (
    Agent,
    Task,
    TaskResult,
    Session,
    HealthStatus,
    AgentStatus,
    TaskStatus
)

__all__ = [
    "Agent",
    "Task", 
    "TaskResult",
    "Session",
    "HealthStatus",
    "AgentStatus",
    "TaskStatus"
]