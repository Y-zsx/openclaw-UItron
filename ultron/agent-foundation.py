#!/usr/bin/env python3
"""
智能体架构基座 (Agent Foundation)
全智能体生态系统 - 第1世核心组件
"""

import json
import time
import uuid
from enum import Enum
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import defaultdict


class AgentState(Enum):
    """智能体状态"""
    CREATED = "created"
    INITIALIZING = "initializing"
    ACTIVE = "active"
    IDLE = "idle"
    PROCESSING = "processing"
    WAITING = "waiting"
    LEARNING = "learning"
    ERROR = "error"
    TERMINATED = "terminated"


class AgentCapability(Enum):
    """智能体能力类型"""
    PERCEPTION = "perception"           # 感知能力
    COGNITION = "cognition"             # 认知能力
    REASONING = "reasoning"             # 推理能力
    LEARNING = "learning"               # 学习能力
    ACTION = "action"                   # 行动能力
    COMMUNICATION = "communication"     # 通信能力
    PLANNING = "planning"               # 规划能力
    CREATIVITY = "creativity"           # 创造力
    SELF_IMPROVEMENT = "self_improvement"  # 自我改进
    METACOGNITION = "metacognition"     # 元认知


class AgentType(Enum):
    """智能体类型"""
    GENERAL = "general"                 # 通用智能体
    SPECIALIST = "specialist"           # 专业化智能体
    COORDINATOR = "coordinator"         # 协调者
    ORCHESTRATOR = "orchestrator"       # 编排者
    MONITOR = "monitor"                 # 监控者
    LEARNER = "learner"                 # 学习者
    EXECUTOR = "executor"               # 执行者
    ANALYZER = "analyzer"               # 分析者


@dataclass
class AgentCapabilityProfile:
    """智能体能力配置"""
    capabilities: Dict[AgentCapability, float] = field(default_factory=dict)
    max_concurrent_tasks: int = 5
    priority_level: int = 5
    learning_rate: float = 0.1
    memory_capacity: int = 10000
    
    def get_capability_level(self, cap: AgentCapability) -> float:
        return self.capabilities.get(cap, 0.0)
    
    def set_capability(self, cap: AgentCapability, level: float):
        self.capabilities[cap] = max(0.0, min(1.0, level))
    
    def improve_capability(self, cap: AgentCapability, amount: float):
        current = self.get_capability_level(cap)
        self.set_capability(cap, current + amount)


@dataclass
class AgentConfig:
    """智能体配置"""
    name: str
    agent_type: AgentType
    capabilities: AgentCapabilityProfile = field(default_factory=AgentCapabilityProfile)
    description: str = ""
    tags: List[str] = field(default_factory=list)
    max_memory_mb: int = 512
    timeout_seconds: int = 300
    retry_on_failure: bool = True
    max_retries: int = 3


@dataclass
class AgentMetrics:
    """智能体指标"""
    tasks_completed: int = 0
    tasks_failed: int = 0
    total_processing_time: float = 0.0
    messages_sent: int = 0
    messages_received: int = 0
    learning_events: int = 0
    last_active: float = field(default_factory=time.time)
    uptime: float = 0.0
    
    def success_rate(self) -> float:
        total = self.tasks_completed + self.tasks_failed
        return self.tasks_completed / total if total > 0 else 0.0
    
    def average_processing_time(self) -> float:
        return self.total_processing_time / self.tasks_completed if self.tasks_completed > 0 else 0.0


class AgentFoundation:
    """
    智能体架构基座
    提供智能体的核心架构、状态管理、任务处理能力
    """
    
    def __init__(self, config: AgentConfig):
        self.id = str(uuid.uuid4())
        self.config = config
        self.state = AgentState.CREATED
        self.state_history: List[tuple] = []
        
        # 核心组件
        self.capabilities = config.capabilities
        self.metrics = AgentMetrics()
        
        # 任务队列
        self.task_queue: List[Dict] = []
        self.completed_tasks: List[Dict] = []
        
        # 内存存储
        self.short_term_memory: List[Dict] = []
        self.long_term_memory: Dict[str, Any] = {}
        
        # 事件系统
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        
        # 生命周期回调
        self.lifecycle_hooks: Dict[str, Callable] = {}
        
        # 创建时间
        self.created_at = time.time()
        self.last_state_change = time.time()
        
        # 注册默认能力
        self._initialize_default_capabilities()
        
        # 初始化状态
        self._transition_to(AgentState.INITIALIZING)
        self._initialize()
    
    def _initialize_default_capabilities(self):
        """初始化默认能力"""
        default_levels = {
            AgentCapability.PERCEPTION: 0.7,
            AgentCapability.COGNITION: 0.7,
            AgentCapability.REASONING: 0.6,
            AgentCapability.LEARNING: 0.5,
            AgentCapability.ACTION: 0.7,
            AgentCapability.COMMUNICATION: 0.8,
            AgentCapability.PLANNING: 0.5,
            AgentCapability.CREATIVITY: 0.3,
            AgentCapability.SELF_IMPROVEMENT: 0.4,
            AgentCapability.METACOGNITION: 0.3,
        }
        
        # 根据智能体类型调整
        if self.config.agent_type == AgentType.COORDINATOR:
            default_levels[AgentCapability.COMMUNICATION] = 0.9
            default_levels[AgentCapability.PLANNING] = 0.8
        elif self.config.agent_type == AgentType.LEARNER:
            default_levels[AgentCapability.LEARNING] = 0.9
            default_levels[AgentCapability.SELF_IMPROVEMENT] = 0.8
        elif self.config.agent_type == AgentType.EXECUTOR:
            default_levels[AgentCapability.ACTION] = 0.9
            default_levels[AgentCapability.REASONING] = 0.7
        
        for cap, level in default_levels.items():
            self.capabilities.set_capability(cap, level)
    
    def _initialize(self):
        """初始化智能体"""
        # 执行初始化逻辑
        self._register_default_handlers()
        self._transition_to(AgentState.ACTIVE)
        self._trigger_hook("on_initialize")
    
    def _register_default_handlers(self):
        """注册默认事件处理器"""
        self.on("task_received", self._handle_task_received)
        self.on("task_completed", self._handle_task_completed)
        self.on("task_failed", self._handle_task_failed)
        self.on("message_received", self._handle_message_received)
    
    def _transition_to(self, new_state: AgentState):
        """状态转换"""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        self.state_history.append((old_state, new_state, time.time()))
        
        # 触发状态变化事件
        self.emit("state_changed", {
            "from": old_state.value,
            "to": new_state.value,
            "timestamp": time.time()
        })
    
    def _trigger_hook(self, hook_name: str):
        """触发生命周期钩子"""
        if hook_name in self.lifecycle_hooks:
            try:
                self.lifecycle_hooks[hook_name](self)
            except Exception as e:
                self._log(f"Hook {hook_name} error: {e}")
    
    def _log(self, message: str):
        """日志记录"""
        print(f"[{self.config.name}] {message}")
    
    # ==================== 事件系统 ====================
    
    def on(self, event: str, handler: Callable):
        """注册事件处理器"""
        self.event_handlers[event].append(handler)
    
    def off(self, event: str, handler: Callable):
        """注销事件处理器"""
        if event in self.event_handlers:
            self.event_handlers[event].remove(handler)
    
    def emit(self, event: str, data: Any = None):
        """触发事件"""
        if event in self.event_handlers:
            for handler in self.event_handlers[event]:
                try:
                    handler(data)
                except Exception as e:
                    self._log(f"Event handler error: {e}")
    
    # ==================== 任务处理 ====================
    
    def submit_task(self, task: Dict) -> str:
        """提交任务"""
        task_id = str(uuid.uuid4())
        task["id"] = task_id
        task["submitted_at"] = time.time()
        task["status"] = "pending"
        
        self.task_queue.append(task)
        self.emit("task_received", task)
        
        self._log(f"Task submitted: {task_id}")
        return task_id
    
    def process_task(self, task: Dict) -> Dict:
        """处理任务"""
        task_id = task.get("id", "unknown")
        self._transition_to(AgentState.PROCESSING)
        
        start_time = time.time()
        
        try:
            # 检查能力是否足够
            required_cap = task.get("required_capability")
            if required_cap:
                cap_level = self.capabilities.get_capability_level(
                    AgentCapability(required_cap)
                )
                if cap_level < task.get("min_capability_level", 0.3):
                    raise Exception(f"Insufficient capability: {required_cap}")
            
            # 执行任务
            result = self._execute_task(task)
            
            # 记录成功
            task["status"] = "completed"
            task["result"] = result
            task["completed_at"] = time.time()
            task["processing_time"] = time.time() - start_time
            
            self.metrics.tasks_completed += 1
            self.metrics.total_processing_time += task["processing_time"]
            
            self.completed_tasks.append(task)
            self.emit("task_completed", task)
            
            self._transition_to(AgentState.ACTIVE)
            return result
            
        except Exception as e:
            # 记录失败
            task["status"] = "failed"
            task["error"] = str(e)
            task["failed_at"] = time.time()
            
            self.metrics.tasks_failed += 1
            self.emit("task_failed", task)
            
            self._transition_to(AgentState.ERROR)
            raise
    
    def _execute_task(self, task: Dict) -> Any:
        """执行任务的核心逻辑"""
        task_type = task.get("type", "general")
        
        if task_type == "perception":
            return self._task_perception(task)
        elif task_type == "cognition":
            return self._task_cognition(task)
        elif task_type == "reasoning":
            return self._task_reasoning(task)
        elif task_type == "action":
            return self._task_action(task)
        elif task_type == "communication":
            return self._task_communication(task)
        else:
            return {"status": "completed", "output": "Task processed"}
    
    def _task_perception(self, task: Dict) -> Dict:
        """感知任务"""
        return {
            "perceived": True,
            "data": task.get("input", {}),
            "confidence": self.capabilities.get_capability_level(AgentCapability.PERCEPTION)
        }
    
    def _task_cognition(self, task: Dict) -> Dict:
        """认知任务"""
        return {
            "cognized": True,
            "input": task.get("input", {}),
            "understanding": self.capabilities.get_capability_level(AgentCapability.COGNITION)
        }
    
    def _task_reasoning(self, task: Dict) -> Dict:
        """推理任务"""
        return {
            "reasoned": True,
            "input": task.get("input", {}),
            "reasoning_level": self.capabilities.get_capability_level(AgentCapability.REASONING)
        }
    
    def _task_action(self, task: Dict) -> Dict:
        """行动任务"""
        return {
            "acted": True,
            "action": task.get("action", "none"),
            "action_level": self.capabilities.get_capability_level(AgentCapability.ACTION)
        }
    
    def _task_communication(self, task: Dict) -> Dict:
        """通信任务"""
        self.metrics.messages_sent += 1
        return {
            "communicated": True,
            "message": task.get("message", ""),
            "comm_level": self.capabilities.get_capability_level(AgentCapability.COMMUNICATION)
        }
    
    # ==================== 事件处理器 ====================
    
    def _handle_task_received(self, task: Dict):
        """处理任务接收事件"""
        pass
    
    def _handle_task_completed(self, task: Dict):
        """处理任务完成事件"""
        # 可以在这里添加学习逻辑
        if self.capabilities.get_capability_level(AgentCapability.LEARNING) > 0.5:
            self._learn_from_task(task)
    
    def _handle_task_failed(self, task: Dict):
        """处理任务失败事件"""
        # 可以添加错误学习和恢复逻辑
        pass
    
    def _handle_message_received(self, message: Dict):
        """处理消息接收事件"""
        self.metrics.messages_received += 1
    
    # ==================== 学习系统 ====================
    
    def _learn_from_task(self, task: Dict):
        """从任务中学习"""
        self.metrics.learning_events += 1
        
        # 存储到短期记忆
        self.short_term_memory.append({
            "task": task,
            "learned_at": time.time()
        })
        
        # 限制短期记忆大小
        if len(self.short_term_memory) > self.capabilities.memory_capacity:
            self.short_term_memory = self.short_term_memory[-self.capabilities.memory_capacity//2:]
    
    def improve(self, capability: AgentCapability, amount: float = 0.1):
        """提升能力"""
        self.capabilities.improve_capability(capability, amount)
        self._log(f"Improved {capability.value} by {amount}")
    
    # ==================== 生命周期 ====================
    
    def start(self):
        """启动智能体"""
        self._transition_to(AgentState.ACTIVE)
        self._trigger_hook("on_start")
        self._log("Agent started")
    
    def stop(self):
        """停止智能体"""
        self._transition_to(AgentState.IDLE)
        self._trigger_hook("on_stop")
        self._log("Agent stopped")
    
    def terminate(self):
        """终止智能体"""
        self._transition_to(AgentState.TERMINATED)
        self._trigger_hook("on_terminate")
        self._log("Agent terminated")
    
    def pause(self):
        """暂停智能体"""
        self._transition_to(AgentState.IDLE)
    
    def resume(self):
        """恢复智能体"""
        self._transition_to(AgentState.ACTIVE)
    
    # ==================== 状态查询 ====================
    
    def get_status(self) -> Dict:
        """获取智能体状态"""
        return {
            "id": self.id,
            "name": self.config.name,
            "type": self.config.agent_type.value,
            "state": self.state.value,
            "capabilities": {
                cap.value: level 
                for cap, level in self.capabilities.capabilities.items()
            },
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "success_rate": self.metrics.success_rate(),
                "messages_sent": self.metrics.messages_sent,
                "messages_received": self.metrics.messages_received,
                "uptime": time.time() - self.created_at
            },
            "queue_length": len(self.task_queue),
            "created_at": self.created_at,
            "last_active": self.metrics.last_active
        }
    
    def get_capabilities(self) -> Dict[str, float]:
        """获取能力配置"""
        return {
            cap.value: level 
            for cap, level in self.capabilities.capabilities.items()
        }
    
    # ==================== 串行化 ====================
    
    def to_dict(self) -> Dict:
        """序列化为字典"""
        return {
            "id": self.id,
            "name": self.config.name,
            "type": self.config.agent_type.value,
            "state": self.state.value,
            "capabilities": self.get_capabilities(),
            "metrics": {
                "tasks_completed": self.metrics.tasks_completed,
                "tasks_failed": self.metrics.tasks_failed,
                "success_rate": self.metrics.success_rate(),
                "messages_sent": self.metrics.messages_sent,
                "messages_received": self.metrics.messages_received,
                "learning_events": self.metrics.learning_events,
                "uptime": time.time() - self.created_at
            },
            "created_at": self.created_at,
            "config": {
                "description": self.config.description,
                "tags": self.config.tags,
                "max_memory_mb": self.config.max_memory_mb,
                "timeout_seconds": self.config.timeout_seconds
            }
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AgentFoundation':
        """从字典反序列化"""
        config = AgentConfig(
            name=data["name"],
            agent_type=AgentType(data["type"]),
            description=data.get("config", {}).get("description", ""),
            tags=data.get("config", {}).get("tags", [])
        )
        
        agent = cls(config)
        agent.id = data["id"]
        agent.state = AgentState(data["state"])
        
        return agent


class AgentRegistry:
    """
    智能体注册中心
    管理所有智能体的注册、发现、协作
    """
    
    def __init__(self):
        self.agents: Dict[str, AgentFoundation] = {}
        self.agent_index: Dict[str, List[str]] = defaultdict(list)  # tag -> agent_ids
        self.type_index: Dict[AgentType, List[str]] = defaultdict(list)
    
    def register(self, agent: AgentFoundation) -> str:
        """注册智能体"""
        self.agents[agent.id] = agent
        
        # 索引标签
        for tag in agent.config.tags:
            self.agent_index[tag].append(agent.id)
        
        # 索引类型
        self.type_index[agent.config.agent_type].append(agent.id)
        
        return agent.id
    
    def unregister(self, agent_id: str):
        """注销智能体"""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        
        # 移除索引
        for tag in agent.config.tags:
            if agent_id in self.agent_index[tag]:
                self.agent_index[tag].remove(agent_id)
        
        if agent_id in self.type_index[agent.config.agent_type]:
            self.type_index[agent.config.agent_type].remove(agent_id)
        
        del self.agents[agent_id]
    
    def find_by_tag(self, tag: str) -> List[AgentFoundation]:
        """通过标签查找"""
        return [self.agents[aid] for aid in self.agent_index.get(tag, [])]
    
    def find_by_type(self, agent_type: AgentType) -> List[AgentFoundation]:
        """通过类型查找"""
        return [self.agents[aid] for aid in self.type_index.get(agent_type, [])]
    
    def find_available(self, capability: AgentCapability, min_level: float = 0.5) -> List[AgentFoundation]:
        """查找具有特定能力的智能体"""
        available = []
        for agent in self.agents.values():
            if agent.state == AgentState.ACTIVE:
                if agent.capabilities.get_capability_level(capability) >= min_level:
                    available.append(agent)
        return available
    
    def get_all(self) -> List[AgentFoundation]:
        """获取所有智能体"""
        return list(self.agents.values())
    
    def get_stats(self) -> Dict:
        """获取注册中心统计"""
        type_counts = {}
        for at in AgentType:
            type_counts[at.value] = len(self.type_index[at])
        
        state_counts = {}
        for agent in self.agents.values():
            state_counts[agent.state.value] = state_counts.get(agent.state.value, 0) + 1
        
        return {
            "total_agents": len(self.agents),
            "by_type": type_counts,
            "by_state": state_counts
        }


# 全局注册中心
_global_registry = AgentRegistry()


def get_registry() -> AgentRegistry:
    """获取全局注册中心"""
    return _global_registry


# 示例使用
if __name__ == "__main__":
    # 创建智能体配置
    config = AgentConfig(
        name="TestAgent",
        agent_type=AgentType.SPECIALIST,
        description="测试用智能体",
        tags=["test", "development"]
    )
    
    # 创建智能体
    agent = AgentFoundation(config)
    
    # 注册到全局注册中心
    registry = get_registry()
    registry.register(agent)
    
    # 启动智能体
    agent.start()
    
    # 提交测试任务
    task_id = agent.submit_task({
        "type": "cognition",
        "input": {"data": "test input"},
        "required_capability": "cognition"
    })
    
    # 处理任务
    result = agent.process_task(agent.task_queue[0])
    print(f"Result: {result}")
    
    # 获取状态
    print(f"Status: {agent.get_status()}")
    
    # 获取统计
    print(f"Registry stats: {registry.get_stats()}")