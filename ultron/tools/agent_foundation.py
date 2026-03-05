#!/usr/bin/env python3
"""
Agent Foundation Module - Agent基础模块定义
为生命周期管理提供基础抽象
"""

from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime


class AgentType(Enum):
    """Agent类型枚举"""
    MONITOR = "monitor"
    EXECUTOR = "executor"
    ANALYZER = "analyzer"
    ORCHESTRATOR = "orchestrator"
    LEARNER = "learner"
    CORE = "core"
    WORKER = "worker"
    GATEWAY = "gateway"
    SPECIALIST = "specialist"
    GENERALIST = "generalist"


class AgentState(Enum):
    """Agent状态枚举"""
    CREATED = "created"
    INITIALIZING = "initializing"
    RUNNING = "running"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    PROCESSING = "processing"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    RECOVERING = "recovering"
    ERROR = "error"
    STOPPED = "stopped"
    FAILED = "failed"
    TERMINATED = "terminated"


class AgentCapability(Enum):
    """Agent能力枚举"""
    REASONING = "reasoning"
    EXECUTION = "execution"
    MONITORING = "monitoring"
    LEARNING = "learning"
    ORCHESTRATION = "orchestration"
    ANALYSIS = "analysis"
    COMMUNICATION = "communication"
    PERSISTENCE = "persistence"


@dataclass
class AgentConfig:
    """Agent配置"""
    agent_id: str = ""
    name: str = ""
    agent_type: AgentType = AgentType.WORKER
    capabilities: List[AgentCapability] = field(default_factory=list)
    endpoint: str = ""
    description: str = ""
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    max_retries: int = 3
    timeout: int = 30
    health_check_interval: int = 60


@dataclass
class AgentFoundation:
    """Agent基础类"""
    config: AgentConfig
    state: AgentState = AgentState.CREATED
    health_score: float = 100.0
    start_time: Optional[datetime] = None
    last_check: Optional[datetime] = None
    failures: int = 0
    consecutive_failures: int = 0
    recovery_attempts: int = 0
    
    def __post_init__(self):
        self.capabilities = self.config.capabilities
        self.endpoint = self.config.endpoint
        # 兼容属性
        if not self.config.agent_id and hasattr(self, 'id'):
            self.config.agent_id = self.id
    
    @property
    def id(self) -> str:
        return self.config.agent_id
    
    @property
    def name(self) -> str:
        return self.config.name
    
    def _initialize(self):
        """初始化Agent"""
        self.state = AgentState.INITIALIZING
        self.health_score = 100.0
        
    def _activate(self):
        """激活Agent"""
        self.state = AgentState.ACTIVE
        self.start_time = datetime.now()
    
    @property
    def metrics(self) -> Dict[str, Any]:
        """返回Agent指标"""
        return {
            "health_score": self.health_score,
            "failures": self.failures,
            "consecutive_failures": self.consecutive_failures,
            "recovery_attempts": self.recovery_attempts,
            "state": self.state.value,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "tasks_pending": 0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
        }
    
    def update_metrics(self, **kwargs):
        """更新指标"""
        for k, v in kwargs.items():
            if k in self.metrics:
                self.metrics[k] = v
    
    def submit_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """提交任务"""
        self.state = AgentState.BUSY
        return {"status": "accepted", "task_id": task.get("type", "unknown")}
        
    def start(self):
        """启动Agent"""
        self.state = AgentState.RUNNING
        self.start_time = datetime.now()
        self.health_score = 100.0
        
    def stop(self):
        """停止Agent"""
        self.state = AgentState.STOPPED
        
    def fail(self, error: str):
        """标记Agent失败"""
        self.failures += 1
        self.consecutive_failures += 1
        self.state = AgentState.FAILED
        self.health_score = max(0, self.health_score - 20)
        
    def recover(self):
        """恢复Agent"""
        self.consecutive_failures = 0
        self.recovery_attempts += 1
        self.state = AgentState.RUNNING
        self.health_score = min(100, self.health_score + 10)
        
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "agent_id": self.config.agent_id,
            "name": self.config.name,
            "type": self.config.agent_type.value,
            "state": self.state.value,
            "health_score": self.health_score,
            "capabilities": [c.value for c in self.capabilities],
            "endpoint": self.endpoint,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "failures": self.failures,
            "consecutive_failures": self.consecutive_failures,
        }


class AgentRegistry:
    """Agent注册表"""
    _instance = None
    _agents: Dict[str, AgentFoundation] = {}
    
    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, agent: AgentFoundation):
        self._agents[agent.config.agent_id] = agent
        
    def unregister(self, agent_id: str):
        if agent_id in self._agents:
            del self._agents[agent_id]
            
    def get(self, agent_id: str) -> Optional[AgentFoundation]:
        return self._agents.get(agent_id)
    
    def list_all(self) -> List[AgentFoundation]:
        return list(self._agents.values())
    
    def list_by_type(self, agent_type: AgentType) -> List[AgentFoundation]:
        return [a for a in self._agents.values() if a.config.agent_type == agent_type]
    
    def list_by_state(self, state: AgentState) -> List[AgentFoundation]:
        return [a for a in self._agents.values() if a.state == state]


def get_registry() -> AgentRegistry:
    """获取Agent注册表实例"""
    return AgentRegistry.get_instance()