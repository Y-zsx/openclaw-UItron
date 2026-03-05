#!/usr/bin/env python3
"""
奥创Agent接口规范 v1.0
========================
定义Agent服务的标准接口，确保多Agent系统的一致性和互操作性。

版本: 1.0
日期: 2026-03-05
"""

import json
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class AgentStatus(Enum):
    """Agent状态枚举"""
    STARTING = "starting"
    READY = "ready"
    BUSY = "busy"
    PROCESSING = "processing"
    IDLE = "idle"
    DEGRADED = "degraded"
    STOPPING = "stopping"
    STOPPED = "stopped"
    FAILED = "failed"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    URGENT = 4
    CRITICAL = 5


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


@dataclass
class AgentInfo:
    """Agent基本信息"""
    agent_id: str
    name: str
    version: str
    role: str  # primary, secondary, service
    capabilities: List[str]  # 支持的能力列表
    status: str
    metadata: Dict[str, Any]
    registered_at: float
    last_heartbeat: float


@dataclass
class HealthCheck:
    """健康检查结果"""
    healthy: bool
    checks: Dict[str, bool]
    details: Dict[str, Any]
    timestamp: float


@dataclass
class TaskRequest:
    """任务请求"""
    task_id: str
    task_type: str
    payload: Dict[str, Any]
    priority: int = TaskPriority.NORMAL.value
    timeout: int = 300  # 秒
    callback_url: Optional[str] = None
    metadata: Dict[str, Any] = None


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: str
    result: Any
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    duration_ms: Optional[int] = None


@dataclass
class AgentMetrics:
    """Agent性能指标"""
    agent_id: str
    timestamp: float
    request_count: int
    success_count: int
    error_count: int
    total_latency_ms: float
    min_latency_ms: float
    max_latency_ms: float
    avg_latency_ms: float
    queue_size: int
    active_tasks: int
    cpu_percent: float
    memory_percent: float


# ========== 核心接口定义 ==========

AGENT_API_SPEC = {
    "version": "1.0",
    "interfaces": {
        "registration": {
            "endpoint": "/agent/register",
            "method": "POST",
            "description": "Agent注册接口",
            "request": {
                "agent_id": "string (required)",
                "name": "string (required)",
                "version": "string (required)",
                "role": "string (required): primary|secondary|service",
                "capabilities": "array[string] (required)",
                "metadata": "object (optional)"
            },
            "response": {
                "success": "boolean",
                "agent_id": "string",
                "registered_at": "timestamp",
                "config": "object"
            }
        },
        "heartbeat": {
            "endpoint": "/agent/heartbeat",
            "method": "POST",
            "description": "Agent心跳接口",
            "request": {
                "agent_id": "string (required)",
                "status": "string (required)",
                "metrics": "object (optional)"
            },
            "response": {
                "success": "boolean",
                "timestamp": "timestamp",
                "commands": "array (optional)"
            }
        },
        "health": {
            "endpoint": "/agent/health",
            "method": "GET",
            "description": "健康检查接口",
            "request": {
                "agent_id": "string (required)"
            },
            "response": {
                "healthy": "boolean",
                "checks": "object",
                "details": "object",
                "timestamp": "timestamp"
            }
        },
        "task_submit": {
            "endpoint": "/task/submit",
            "method": "POST",
            "description": "提交任务接口",
            "request": {
                "task_id": "string (required)",
                "task_type": "string (required)",
                "payload": "object (required)",
                "priority": "int (optional, default 2)",
                "timeout": "int (optional, default 300)",
                "callback_url": "string (optional)",
                "metadata": "object (optional)"
            },
            "response": {
                "success": "boolean",
                "task_id": "string",
                "status": "string",
                "queued_at": "timestamp"
            }
        },
        "task_status": {
            "endpoint": "/task/status",
            "method": "GET",
            "description": "查询任务状态",
            "request": {
                "task_id": "string (required)"
            },
            "response": {
                "task_id": "string",
                "status": "string",
                "result": "any",
                "error": "string (optional)",
                "started_at": "timestamp",
                "completed_at": "timestamp",
                "duration_ms": "int"
            }
        },
        "task_cancel": {
            "endpoint": "/task/cancel",
            "method": "POST",
            "description": "取消任务",
            "request": {
                "task_id": "string (required)"
            },
            "response": {
                "success": "boolean",
                "task_id": "string",
                "cancelled_at": "timestamp"
            }
        },
        "metrics": {
            "endpoint": "/metrics",
            "method": "GET",
            "description": "获取Agent指标",
            "request": {
                "agent_id": "string (optional)",
                "time_range": "string (optional)"
            },
            "response": {
                "agents": "array[AgentMetrics]",
                "timestamp": "timestamp"
            }
        },
        "capabilities": {
            "endpoint": "/agent/capabilities",
            "method": "GET",
            "description": "获取Agent能力列表",
            "request": {
                "agent_id": "string (required)"
            },
            "response": {
                "agent_id": "string",
                "capabilities": "array[string]",
                "version": "string"
            }
        },
        "collaborate": {
            "endpoint": "/agent/collaborate",
            "method": "POST",
            "description": "Agent协作接口",
            "request": {
                "source_agent": "string (required)",
                "target_agent": "string (required)",
                "message_type": "string (required)",
                "message": "object (required)",
                "correlation_id": "string (optional)"
            },
            "response": {
                "success": "boolean",
                "correlation_id": "string",
                "response": "object"
            }
        }
    },
    "error_codes": {
        "E001": "无效的请求参数",
        "E002": "Agent未注册",
        "E003": "Agent已注册",
        "E004": "任务不存在",
        "E005": "任务超时",
        "E006": "Agent不可用",
        "E007": "能力不支持",
        "E008": "认证失败",
        "E009": "协作失败",
        "E010": "系统错误"
    }
}


class AgentInterfaceValidator:
    """Agent接口验证器"""
    
    @staticmethod
    def validate_registration(data: Dict) -> tuple[bool, Optional[str]]:
        """验证注册请求"""
        required = ["agent_id", "name", "version", "role", "capabilities"]
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
        if data["role"] not in ["primary", "secondary", "service"]:
            return False, "Invalid role"
        return True, None
    
    @staticmethod
    def validate_task_submit(data: Dict) -> tuple[bool, Optional[str]]:
        """验证任务提交"""
        required = ["task_id", "task_type", "payload"]
        for field in required:
            if field not in data:
                return False, f"Missing required field: {field}"
        return True, None
    
    @staticmethod
    def validate_health_check(data: Dict) -> tuple[bool, Optional[str]]:
        """验证健康检查"""
        if "agent_id" not in data:
            return False, "Missing agent_id"
        return True, None


def generate_task_id(agent_id: str) -> str:
    """生成任务ID"""
    return f"{agent_id}_{int(time.time() * 1000)}"


def create_success_response(data: Dict) -> Dict:
    """创建成功响应"""
    return {
        "success": True,
        "timestamp": time.time(),
        **data
    }


def create_error_response(error_code: str, message: str) -> Dict:
    """创建错误响应"""
    return {
        "success": False,
        "error_code": error_code,
        "error_message": message,
        "timestamp": time.time()
    }


if __name__ == "__main__":
    print("=" * 60)
    print("奥创Agent接口规范 v1.0")
    print("=" * 60)
    print(json.dumps(AGENT_API_SPEC, indent=2, ensure_ascii=False))