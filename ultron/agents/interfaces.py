#!/usr/bin/env python3
"""
Agent接口定义 - 多智能体协作网络
第13世: 定义Agent接口规范

提供标准化的Agent接口定义，所有Agent实现必须遵循此规范
"""

import json
import asyncio
import uuid
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path

# ============================================================================
# 枚举定义
# ============================================================================

class AgentState(Enum):
    """Agent状态枚举"""
    INITIALIZED = "initialized"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


class AgentCapability(Enum):
    """Agent能力枚举"""
    EXECUTION = "execution"
    ORCHESTRATION = "orchestration"
    MONITORING = "monitoring"
    LEARNING = "learning"
    COMMUNICATION = "communication"
    AUTH = "auth"
    SECURE_CHANNEL = "secure_channel"
    SERVICE_MESH = "service_mesh"
    ACCESS_CONTROL = "access_control"


class TaskType(Enum):
    """任务类型"""
    SHELL = "shell"
    PYTHON = "python"
    FUNCTION = "function"
    API = "api"
    WORKFLOW = "workflow"
    QUERY = "query"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class MessageType(Enum):
    """消息类型"""
    TASK = "task"
    ALERT = "alert"
    HEARTBEAT = "heartbeat"
    REPORT = "report"
    ACK = "ack"
    ERROR = "error"


class LifecycleEvent(Enum):
    """生命周期事件"""
    REGISTERED = "registered"
    STARTED = "started"
    STOPPED = "stopped"
    RESTARTED = "restarted"
    FAILED = "failed"
    RECOVERED = "recovered"
    PAUSED = "paused"
    RESUMED = "resumed"
    HEALTH_CHECK_PASSED = "health_check_passed"
    HEALTH_CHECK_FAILED = "health_check_failed"


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class AgentInfo:
    """Agent基本信息"""
    agent_id: str
    name: str
    version: str = "1.0.0"
    agent_type: str = "generic"
    capabilities: List[str] = field(default_factory=list)
    state: str = "initialized"
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    last_heartbeat: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "version": self.version,
            "agent_type": self.agent_type,
            "capabilities": self.capabilities,
            "state": self.state,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_heartbeat": self.last_heartbeat
        }


@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str
    task_type: str = "generic"
    payload: Dict[str, Any] = field(default_factory=dict)
    source_agent: str = ""
    target_agent: str = ""
    priority: int = 50
    timeout: float = 30.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskContext':
        return cls(
            task_id=data.get("task_id", str(uuid.uuid4())),
            task_type=data.get("task_type", "generic"),
            payload=data.get("payload", {}),
            source_agent=data.get("source_agent", ""),
            target_agent=data.get("target_agent", ""),
            priority=data.get("priority", 50),
            timeout=data.get("timeout", 30.0),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", datetime.now().isoformat())
        )


@dataclass
class TaskResult:
    """任务结果"""
    task_id: str
    status: str  # success/failed/timeout/cancelled
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    completed_at: str = ""
    
    def __post_init__(self):
        if not self.completed_at:
            self.completed_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "metadata": self.metadata,
            "completed_at": self.completed_at
        }
    
    @property
    def is_success(self) -> bool:
        return self.status == "success"


@dataclass
class AgentMessage:
    """Agent间消息格式"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    msg_type: str = "task"
    source: str = ""
    target: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: int = 50
    requires_ack: bool = False
    correlation_id: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "msg_id": self.msg_id,
            "msg_type": self.msg_type,
            "source": self.source,
            "target": self.target,
            "payload": self.payload,
            "priority": self.priority,
            "requires_ack": self.requires_ack,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentMessage':
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        return cls.from_dict(json.loads(json_str))


@dataclass
class ServiceEndpoint:
    """服务端点"""
    endpoint_id: str
    agent_id: str
    address: str  # host:port
    weight: int = 100
    metadata: Dict = field(default_factory=dict)
    is_healthy: bool = True
    last_health_check: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "endpoint_id": self.endpoint_id,
            "agent_id": self.agent_id,
            "address": self.address,
            "weight": self.weight,
            "metadata": self.metadata,
            "is_healthy": self.is_healthy,
            "last_health_check": self.last_health_check
        }


@dataclass
class AgentMetrics:
    """Agent指标"""
    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    
    # 任务指标
    tasks_total: int = 0
    tasks_success: int = 0
    tasks_failed: int = 0
    success_rate: float = 0.0
    
    # 性能指标
    avg_duration_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    
    # 资源指标
    cpu_percent: float = 0.0
    memory_mb: float = 0.0
    thread_count: int = 0
    
    # 队列指标
    queue_size: int = 0
    queue_wait_ms: float = 0.0
    
    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "tasks_total": self.tasks_total,
            "tasks_success": self.tasks_success,
            "tasks_failed": self.tasks_failed,
            "success_rate": self.success_rate,
            "avg_duration_ms": self.avg_duration_ms,
            "p50_latency_ms": self.p50_latency_ms,
            "p95_latency_ms": self.p95_latency_ms,
            "p99_latency_ms": self.p99_latency_ms,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "thread_count": self.thread_count,
            "queue_size": self.queue_size,
            "queue_wait_ms": self.queue_wait_ms
        }


# ============================================================================
# 异常定义
# ============================================================================

class AgentError(Exception):
    """Agent基础异常"""
    pass


class AgentInitializationError(AgentError):
    """初始化错误"""
    pass


class AgentExecutionError(AgentError):
    """执行错误"""
    pass


class AgentTimeoutError(AgentError):
    """超时错误"""
    pass


class AgentNotFoundError(AgentError):
    """Agent未找到错误"""
    pass


class AgentStateError(AgentError):
    """状态错误"""
    pass


# ============================================================================
# 接口定义
# ============================================================================

class IAgent(ABC):
    """Agent核心接口"""
    
    @property
    @abstractmethod
    def info(self) -> AgentInfo:
        """获取Agent信息"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化Agent"""
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """启动Agent"""
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """停止Agent"""
        pass
    
    @abstractmethod
    async def execute_task(self, context: TaskContext) -> TaskResult:
        """执行任务"""
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        pass
    
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """处理收到的消息"""
        pass


class IHealthCheck(ABC):
    """健康检查接口"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """执行健康检查"""
        pass


class IStatePersistence(ABC):
    """状态持久化接口"""
    
    @abstractmethod
    async def save_state(self, state: Dict[str, Any]) -> bool:
        """保存状态"""
        pass
    
    @abstractmethod
    async def load_state(self) -> Optional[Dict[str, Any]]:
        """加载状态"""
        pass


class IEventEmitter(ABC):
    """事件发射器接口"""
    
    @abstractmethod
    async def emit(self, event_type: str, data: Dict[str, Any]) -> None:
        """发射事件"""
        pass
    
    @abstractmethod
    def on(self, event_type: str, handler: Callable) -> None:
        """注册事件处理器"""
        pass


class ITaskExecutor(ABC):
    """任务执行器接口"""
    
    @abstractmethod
    async def execute(self, task: Dict[str, Any]) -> TaskResult:
        """执行任务"""
        pass
    
    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[str]:
        """获取任务状态"""
        pass


class IAuthProvider(ABC):
    """认证提供者接口"""
    
    @abstractmethod
    async def authenticate(self, credentials: Dict) -> Optional[str]:
        """认证并返回令牌"""
        pass
    
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[Dict]:
        """验证令牌"""
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        pass


# ============================================================================
# 基类实现
# ============================================================================

class BaseAgent(IAgent):
    """Agent基类实现"""
    
    def __init__(self, agent_id: str, name: str, agent_type: str = "generic"):
        self._agent_id = agent_id
        self._name = name
        self._agent_type = agent_type
        self._state = AgentState.INITIALIZED
        self._config: Dict[str, Any] = {}
        self._metadata: Dict[str, Any] = {}
        self._capabilities: List[str] = []
        self._start_time: Optional[datetime] = None
    
    @property
    def info(self) -> AgentInfo:
        return AgentInfo(
            agent_id=self._agent_id,
            name=self._name,
            agent_type=self._agent_type,
            capabilities=self._capabilities,
            state=self._state.value,
            metadata=self._metadata,
            created_at=self._start_time.isoformat() if self._start_time else "",
            last_heartbeat=datetime.now().isoformat()
        )
    
    @property
    def state(self) -> AgentState:
        return self._state
    
    @state.setter
    def state(self, value: AgentState):
        self._state = value
    
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化Agent"""
        try:
            self._config = config
            self._metadata = config.get("metadata", {})
            self._capabilities = config.get("capabilities", [])
            self._state = AgentState.READY
            return True
        except Exception as e:
            self._state = AgentState.ERROR
            raise AgentInitializationError(f"初始化失败: {e}")
    
    async def start(self) -> bool:
        """启动Agent"""
        if self._state not in [AgentState.READY, AgentState.STOPPED]:
            raise AgentStateError(f"无法启动，当前状态: {self._state.value}")
        
        self._state = AgentState.RUNNING
        self._start_time = datetime.now()
        return True
    
    async def stop(self) -> bool:
        """停止Agent"""
        self._state = AgentState.STOPPING
        # 子类可以重写此方法进行清理
        self._state = AgentState.STOPPED
        return True
    
    async def execute_task(self, context: TaskContext) -> TaskResult:
        """执行任务 - 子类必须重写"""
        return TaskResult(
            task_id=context.task_id,
            status="failed",
            error="execute_task未实现"
        )
    
    async def get_status(self) -> Dict[str, Any]:
        """获取Agent状态"""
        return {
            "agent_id": self._agent_id,
            "name": self._name,
            "state": self._state.value,
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds() if self._start_time else 0,
            "metadata": self._metadata
        }
    
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """处理消息 - 子类可以重写"""
        return None
    
    def add_capability(self, capability: str):
        """添加能力"""
        if capability not in self._capabilities:
            self._capabilities.append(capability)


# ============================================================================
# 工具函数
# ============================================================================

def create_task_context(
    task_type: str,
    payload: Dict[str, Any],
    source_agent: str = "",
    target_agent: str = "",
    priority: int = 50,
    timeout: float = 30.0
) -> TaskContext:
    """创建任务上下文"""
    return TaskContext(
        task_id=str(uuid.uuid4()),
        task_type=task_type,
        payload=payload,
        source_agent=source_agent,
        target_agent=target_agent,
        priority=priority,
        timeout=timeout
    )


def create_agent_message(
    msg_type: str,
    source: str,
    target: str,
    payload: Dict[str, Any],
    priority: int = 50,
    requires_ack: bool = False,
    correlation_id: str = ""
) -> AgentMessage:
    """创建Agent消息"""
    return AgentMessage(
        msg_type=msg_type,
        source=source,
        target=target,
        payload=payload,
        priority=priority,
        requires_ack=requires_ack,
        correlation_id=correlation_id or str(uuid.uuid4())
    )


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    # 枚举
    "AgentState",
    "AgentCapability", 
    "TaskType",
    "TaskStatus",
    "MessageType",
    "LifecycleEvent",
    # 数据类
    "AgentInfo",
    "TaskContext",
    "TaskResult",
    "AgentMessage",
    "ServiceEndpoint",
    "AgentMetrics",
    # 异常
    "AgentError",
    "AgentInitializationError",
    "AgentExecutionError",
    "AgentTimeoutError",
    "AgentNotFoundError",
    "AgentStateError",
    # 接口
    "IAgent",
    "IHealthCheck",
    "IStatePersistence",
    "IEventEmitter",
    "ITaskExecutor",
    "IAuthProvider",
    # 基类
    "BaseAgent",
    # 工具函数
    "create_task_context",
    "create_agent_message",
]