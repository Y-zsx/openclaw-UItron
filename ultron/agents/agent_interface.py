#!/usr/bin/env python3
"""
Agent接口规范 (Agent Interface Specification)
第13世: 定义Agent接口规范

本模块定义Agent的标准接口，确保不同Agent之间的互操作性。
包含：基类定义、消息协议、能力声明、生命周期、健康检查等核心接口。
"""

import asyncio
import json
import uuid
import time
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable, Union
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("agent-interface")


# ==================== 枚举定义 ====================

class AgentStatus(Enum):
    """Agent状态"""
    INITIALIZING = "initializing"      # 初始化中
    IDLE = "idle"                      # 空闲
    PROCESSING = "processing"          # 处理中
    BUSY = "busy"                      # 忙碌
    ERROR = "error"                    # 错误
    SHUTTING_DOWN = "shutting_down"    # 关闭中


class MessageType(Enum):
    """消息类型"""
    # 生命周期
    INITIALIZE = "initialize"
    START = "start"
    STOP = "stop"
    HEALTH_CHECK = "health_check"
    
    # 任务相关
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_RESULT = "task_result"
    TASK_PROGRESS = "task_progress"
    TASK_CANCEL = "task_cancel"
    
    # 协作相关
    COLLABORATE = "collaborate"
    COLLABORATE_RESULT = "collaborate_result"
    BROADCAST = "broadcast"
    
    # 错误相关
    ERROR = "error"
    ERROR_RECOVERY = "error_recovery"


class CapabilityType(Enum):
    """能力类型（扩展版）"""
    # 核心能力
    MONITOR = "monitor"           # 监控
    EXECUTE = "execute"           # 执行
    ANALYZE = "analyze"           # 分析
    LEARN = "learn"               # 学习
    COMMUNICATE = "communicate"   # 通信
    ORCHESTRATE = "orchestrate"   # 编排
    NOTIFY = "notify"             # 通知
    
    # 扩展能力
    SECURE = "secure"             # 安全
    REPAIR = "repair"             # 修复
    PLAN = "plan"                 # 规划
    REASON = "reason"             # 推理
    CREATE = "create"             # 创建
    VALIDATE = "validate"         # 验证
    OPTIMIZE = "optimize"         # 优化
    BACKUP = "backup"             # 备份


# ==================== 数据结构 ====================

@dataclass
class AgentMetadata:
    """Agent元数据"""
    agent_id: str
    name: str
    version: str = "1.0.0"
    description: str = ""
    author: str = ""
    capabilities: List[str] = field(default_factory=list)
    config: Dict = field(default_factory=dict)
    tags: List[str] = field(default_factory=list)


@dataclass
class HealthStatus:
    """健康状态"""
    healthy: bool = True
    status: AgentStatus = AgentStatus.IDLE
    uptime: float = 0.0
    load: float = 0.0
    memory_usage: float = 0.0
    cpu_usage: float = 0.0
    active_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    last_error: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class TaskRequest:
    """任务请求"""
    request_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: str = ""
    description: str = ""
    payload: Dict = field(default_factory=dict)
    context: Dict = field(default_factory=dict)
    timeout: int = 300
    priority: int = 5
    required_capabilities: List[str] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)


@dataclass
class TaskResponse:
    """任务响应"""
    request_id: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AgentMessage(ABC):
    """Agent消息基类"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: MessageType = MessageType.TASK_REQUEST
    sender_id: str = ""
    receiver_id: str = ""
    correlation_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    ttl: int = 300  # 消息生存时间(秒)


@dataclass
class TaskMessage(AgentMessage):
    """任务消息"""
    request: Optional[TaskRequest] = None
    response: Optional[TaskResponse] = None


@dataclass
class CollaborationMessage(AgentMessage):
    """协作消息"""
    action: str = ""
    target_capability: Optional[str] = None
    payload: Dict = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)


# ==================== Agent接口定义 ====================

class IAgent(ABC):
    """
    Agent基础接口
    
    所有Agent必须实现此接口定义的方法。
    接口分为以下几类：
    - 生命周期: initialize, start, stop, restart
    - 任务处理: execute, cancel, get_status
    - 协作: collaborate, broadcast, receive_message
    - 健康: health_check, get_metrics
    - 能力: get_capabilities, supports_capability
    """
    
    @abstractmethod
    def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化Agent
        
        Args:
            config: 配置字典
            
        Returns:
            bool: 初始化是否成功
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动Agent
        
        Returns:
            bool: 启动是否成功
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止Agent
        
        Returns:
            bool: 停止是否成功
        """
        pass
    
    @abstractmethod
    async def execute(self, request: TaskRequest) -> TaskResponse:
        """
        执行任务
        
        Args:
            request: 任务请求
            
        Returns:
            TaskResponse: 任务响应
        """
        pass
    
    @abstractmethod
    def get_metadata(self) -> AgentMetadata:
        """
        获取Agent元数据
        
        Returns:
            AgentMetadata: Agent元数据
        """
        pass
    
    @abstractmethod
    def get_health(self) -> HealthStatus:
        """
        获取健康状态
        
        Returns:
            HealthStatus: 健康状态
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> List[CapabilityType]:
        """
        获取Agent能力列表
        
        Returns:
            List[CapabilityType]: 能力列表
        """
        pass
    
    def supports_capability(self, capability: CapabilityType) -> bool:
        """检查是否支持指定能力"""
        return capability in self.get_capabilities()
    
    async def restart(self) -> bool:
        """重启Agent"""
        await self.stop()
        return await self.start()
    
    async def cancel(self, request_id: str) -> bool:
        """取消任务（可选实现）"""
        return False
    
    async def collaborate(self, message: CollaborationMessage) -> Dict:
        """
        协作处理（可选实现）
        
        Args:
            message: 协作消息
            
        Returns:
            Dict: 协作结果
        """
        return {"status": "not_implemented"}
    
    async def receive_message(self, message: AgentMessage) -> None:
        """
        接收消息（可选实现）
        
        Args:
            message: Agent消息
        """
        pass
    
    def get_metrics(self) -> Dict:
        """获取指标（可选实现）"""
        health = self.get_health()
        return {
            "uptime": health.uptime,
            "load": health.load,
            "active_tasks": health.active_tasks,
            "completed_tasks": health.completed_tasks,
            "failed_tasks": health.failed_tasks
        }


class ICollaborativeAgent(IAgent):
    """
    协作Agent接口
    
    扩展IAgent接口，增加协作相关方法。
    """
    
    @abstractmethod
    async def on_collaborate_request(self, message: CollaborationMessage) -> Dict:
        """处理协作请求"""
        pass
    
    @abstractmethod
    async def on_collaborate_result(self, message: CollaborationMessage) -> None:
        """处理协作结果"""
        pass
    
    @abstractmethod
    def get_collaboration_handlers(self) -> Dict[str, Callable]:
        """获取协作处理器"""
        pass
    
    @abstractmethod
    async def broadcast(self, message: Dict, exclude: List[str] = None) -> None:
        """广播消息"""
        pass


class IStatefulAgent(IAgent):
    """
    有状态Agent接口
    
    扩展IAgent接口，增加状态管理相关方法。
    """
    
    @abstractmethod
    def get_state(self) -> Dict:
        """获取当前状态"""
        pass
    
    @abstractmethod
    def set_state(self, state: Dict) -> None:
        """设置状态"""
        pass
    
    @abstractmethod
    def save_state(self, path: str) -> bool:
        """保存状态到文件"""
        pass
    
    @abstractmethod
    def load_state(self, path: str) -> bool:
        """从文件加载状态"""
        pass


# ==================== Agent基类实现 ====================

class BaseAgent(IAgent):
    """
    Agent基类
    
    提供通用的Agent实现，所有具体Agent可以继承此类。
    """
    
    def __init__(self, agent_id: str, name: str, capabilities: List[CapabilityType]):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities
        self.config: Dict = {}
        self.status = AgentStatus.INITIALIZING
        self._start_time: float = 0
        self._tasks: Dict[str, TaskRequest] = {}
        self._completed_tasks: int = 0
        self._failed_tasks: int = 0
        self._last_error: Optional[str] = None
    
    def initialize(self, config: Dict[str, Any]) -> bool:
        """初始化Agent"""
        try:
            self.config = config
            self.status = AgentStatus.IDLE
            logger.info(f"Agent {self.name} 初始化完成")
            return True
        except Exception as e:
            logger.error(f"Agent {self.name} 初始化失败: {e}")
            self.status = AgentStatus.ERROR
            self._last_error = str(e)
            return False
    
    async def start(self) -> bool:
        """启动Agent"""
        try:
            self.status = AgentStatus.IDLE
            self._start_time = time.time()
            logger.info(f"Agent {self.name} 已启动")
            return True
        except Exception as e:
            logger.error(f"Agent {self.name} 启动失败: {e}")
            self.status = AgentStatus.ERROR
            self._last_error = str(e)
            return False
    
    async def stop(self) -> bool:
        """停止Agent"""
        try:
            self.status = AgentStatus.SHUTTING_DOWN
            # 等待处理中的任务完成（可选）
            await asyncio.sleep(0.5)
            self.status = AgentStatus.IDLE
            logger.info(f"Agent {self.name} 已停止")
            return True
        except Exception as e:
            logger.error(f"Agent {self.name} 停止失败: {e}")
            return False
    
    async def execute(self, request: TaskRequest) -> TaskResponse:
        """执行任务（子类需要重写）"""
        self.status = AgentStatus.PROCESSING
        try:
            # 默认实现：子类应重写此方法
            result = await self._default_execute(request)
            self._completed_tasks += 1
            self.status = AgentStatus.IDLE
            return TaskResponse(
                request_id=request.request_id,
                success=True,
                result=result
            )
        except Exception as e:
            self._failed_tasks += 1
            self._last_error = str(e)
            self.status = AgentStatus.ERROR
            return TaskResponse(
                request_id=request.request_id,
                success=False,
                error=str(e)
            )
    
    async def _default_execute(self, request: TaskRequest) -> Any:
        """默认执行逻辑（可重写）"""
        return {"status": "executed", "agent": self.name}
    
    def get_metadata(self) -> AgentMetadata:
        """获取元数据"""
        return AgentMetadata(
            agent_id=self.agent_id,
            name=self.name,
            version="1.0.0",
            capabilities=[c.value for c in self.capabilities],
            config=self.config
        )
    
    def get_health(self) -> HealthStatus:
        """获取健康状态"""
        uptime = time.time() - self._start_time if self._start_time > 0 else 0
        return HealthStatus(
            healthy=self.status != AgentStatus.ERROR,
            status=self.status,
            uptime=uptime,
            active_tasks=len(self._tasks),
            completed_tasks=self._completed_tasks,
            failed_tasks=self._failed_tasks,
            last_error=self._last_error
        )
    
    def get_capabilities(self) -> List[CapabilityType]:
        """获取能力列表"""
        return self.capabilities


class CollaborativeAgent(BaseAgent, ICollaborativeAgent):
    """
    协作Agent基类
    
    支持协作的Agent基类。
    """
    
    def __init__(self, agent_id: str, name: str, capabilities: List[CapabilityType]):
        super().__init__(agent_id, name, capabilities)
        self._collaborators: Dict[str, 'CollaborativeAgent'] = {}
        self._message_queue: asyncio.Queue = asyncio.Queue()
    
    async def on_collaborate_request(self, message: CollaborationMessage) -> Dict:
        """处理协作请求"""
        return {"status": "acknowledged", "message_id": message.message_id}
    
    async def on_collaborate_result(self, message: CollaborationMessage) -> None:
        """处理协作结果"""
        logger.info(f"收到协作结果: {message.message_id}")
    
    def get_collaboration_handlers(self) -> Dict[str, Callable]:
        """获取协作处理器"""
        return {
            "on_collaborate_request": self.on_collaborate_request,
            "on_collaborate_result": self.on_collaborate_result
        }
    
    async def broadcast(self, message: Dict, exclude: List[str] = None) -> None:
        """广播消息到所有协作者"""
        exclude = exclude or []
        for collaborator_id, collaborator in self._collaborators.items():
            if collaborator_id not in exclude:
                await collaborator.receive_message(CollaborationMessage(
                    message_type=MessageType.BROADCAST,
                    sender_id=self.agent_id,
                    receiver_id=collaborator_id,
                    payload=message
                ))
    
    def add_collaborator(self, agent: 'CollaborativeAgent') -> None:
        """添加协作者"""
        self._collaborators[agent.agent_id] = agent
        logger.info(f"添加协作者: {agent.name}")


# ==================== 消息协议工具 ====================

class MessageProtocol:
    """消息协议工具类"""
    
    @staticmethod
    def create_task_message(sender: str, receiver: str, 
                           request: TaskRequest) -> TaskMessage:
        """创建任务消息"""
        return TaskMessage(
            message_type=MessageType.TASK_REQUEST,
            sender_id=sender,
            receiver_id=receiver,
            request=request
        )
    
    @staticmethod
    def create_response_message(sender: str, receiver: str,
                               response: TaskResponse,
                               correlation_id: str = None) -> TaskMessage:
        """创建响应消息"""
        return TaskMessage(
            message_type=MessageType.TASK_RESPONSE,
            sender_id=sender,
            receiver_id=receiver,
            correlation_id=correlation_id,
            response=response
        )
    
    @staticmethod
    def create_collaboration_message(sender: str, receiver: str,
                                    action: str, payload: Dict,
                                    correlation_id: str = None) -> CollaborationMessage:
        """创建协作消息"""
        return CollaborationMessage(
            message_type=MessageType.COLLABORATE,
            sender_id=sender,
            receiver_id=receiver,
            action=action,
            payload=payload,
            correlation_id=correlation_id
        )
    
    @staticmethod
    def validate_message(message: AgentMessage) -> bool:
        """验证消息格式"""
        if not message.sender_id or not message.receiver_id:
            return False
        if not isinstance(message.message_type, MessageType):
            return False
        return True
    
    @staticmethod
    def serialize_message(message: AgentMessage) -> str:
        """序列化消息为JSON"""
        data = {
            "message_id": message.message_id,
            "message_type": message.message_type.value,
            "sender_id": message.sender_id,
            "receiver_id": message.receiver_id,
            "correlation_id": message.correlation_id,
            "timestamp": message.timestamp,
            "ttl": message.ttl
        }
        
        if isinstance(message, TaskMessage):
            if message.request:
                data["request"] = {
                    "request_id": message.request.request_id,
                    "task_type": message.request.task_type,
                    "description": message.request.description,
                    "payload": message.request.payload,
                    "timeout": message.request.timeout,
                    "priority": message.request.priority
                }
            if message.response:
                data["response"] = {
                    "request_id": message.response.request_id,
                    "success": message.response.success,
                    "result": message.response.result,
                    "error": message.response.error
                }
        
        elif isinstance(message, CollaborationMessage):
            data["action"] = message.action
            data["payload"] = message.payload
            data["target_capability"] = message.target_capability
        
        return json.dumps(data, ensure_ascii=False)
    
    @staticmethod
    def deserialize_message(json_str: str) -> AgentMessage:
        """从JSON反序列化消息"""
        data = json.loads(json_str)
        
        msg_type = MessageType(data.get("message_type", "task_request"))
        
        if msg_type in [MessageType.TASK_REQUEST, MessageType.TASK_RESPONSE]:
            message = TaskMessage(
                message_id=data.get("message_id", str(uuid.uuid4())),
                message_type=msg_type,
                sender_id=data.get("sender_id", ""),
                receiver_id=data.get("receiver_id", ""),
                correlation_id=data.get("correlation_id")
            )
            
            if "request" in data and msg_type == MessageType.TASK_REQUEST:
                req_data = data["request"]
                message.request = TaskRequest(
                    request_id=req_data.get("request_id", ""),
                    task_type=req_data.get("task_type", ""),
                    description=req_data.get("description", ""),
                    payload=req_data.get("payload", {}),
                    timeout=req_data.get("timeout", 300),
                    priority=req_data.get("priority", 5)
                )
            
            if "response" in data and msg_type == MessageType.TASK_RESPONSE:
                resp_data = data["response"]
                message.response = TaskResponse(
                    request_id=resp_data.get("request_id", ""),
                    success=resp_data.get("success", False),
                    result=resp_data.get("result"),
                    error=resp_data.get("error")
                )
            
            return message
        
        elif msg_type == MessageType.COLLABORATE:
            return CollaborationMessage(
                message_id=data.get("message_id", str(uuid.uuid4())),
                message_type=msg_type,
                sender_id=data.get("sender_id", ""),
                receiver_id=data.get("receiver_id", ""),
                action=data.get("action", ""),
                payload=data.get("payload", {}),
                correlation_id=data.get("correlation_id")
            )
        
        # 默认消息类型
        return AgentMessage(
            message_id=data.get("message_id", str(uuid.uuid4())),
            message_type=msg_type,
            sender_id=data.get("sender_id", ""),
            receiver_id=data.get("receiver_id", "")
        )


# ==================== 示例：具体Agent实现 ====================

class MonitorAgent(CollaborativeAgent):
    """监控Agent示例"""
    
    def __init__(self):
        super().__init__(
            agent_id="monitor-agent",
            name="监控系统代理",
            capabilities=[CapabilityType.MONITOR, CapabilityType.NOTIFY]
        )
    
    async def execute(self, request: TaskRequest) -> TaskResponse:
        """执行监控任务"""
        logger.info(f"MonitorAgent 执行任务: {request.task_type}")
        
        # 模拟监控逻辑
        await asyncio.sleep(0.1)
        
        result = {
            "status": "monitored",
            "metrics": {
                "cpu": 45.2,
                "memory": 62.8,
                "disk": 38.5,
                "network": 120.5
            },
            "timestamp": time.time()
        }
        
        return TaskResponse(
            request_id=request.request_id,
            success=True,
            result=result
        )


class ExecutorAgent(CollaborativeAgent):
    """执行Agent示例"""
    
    def __init__(self):
        super().__init__(
            agent_id="executor-agent",
            name="执行系统代理",
            capabilities=[CapabilityType.EXECUTE, CapabilityType.REPAIR]
        )
    
    async def execute(self, request: TaskRequest) -> TaskResponse:
        """执行任务"""
        logger.info(f"ExecutorAgent 执行任务: {request.task_type}")
        
        task_type = request.task_type
        
        if task_type == "shell":
            # 执行shell命令
            command = request.payload.get("command", "")
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            return TaskResponse(
                request_id=request.request_id,
                success=proc.returncode == 0,
                result={
                    "stdout": stdout.decode(),
                    "stderr": stderr.decode(),
                    "returncode": proc.returncode
                }
            )
        
        elif task_type == "repair":
            # 执行修复
            target = request.payload.get("target", "")
            logger.info(f"执行修复: {target}")
            
            return TaskResponse(
                request_id=request.request_id,
                success=True,
                result={"status": "repaired", "target": target}
            )
        
        # 默认执行
        return TaskResponse(
            request_id=request.request_id,
            success=True,
            result={"status": "executed", "task_type": task_type}
        )


# ==================== 工厂类 ====================

class AgentFactory:
    """Agent工厂类"""
    
    _agents: Dict[str, IAgent] = {}
    _registry: Dict[str, type] = {}
    
    @classmethod
    def register(cls, agent_type: str, agent_class: type):
        """注册Agent类型"""
        cls._registry[agent_type] = agent_class
        logger.info(f"注册Agent类型: {agent_type}")
    
    @classmethod
    def create(cls, agent_type: str, config: Dict = None) -> IAgent:
        """创建Agent实例"""
        if agent_type not in cls._registry:
            raise ValueError(f"未知的Agent类型: {agent_type}")
        
        agent = cls._registry[agent_type]()
        if config:
            agent.initialize(config)
        
        cls._agents[agent.agent_id] = agent
        return agent
    
    @classmethod
    def get(cls, agent_id: str) -> Optional[IAgent]:
        """获取Agent实例"""
        return cls._agents.get(agent_id)
    
    @classmethod
    def list_agents(cls) -> List[IAgent]:
        """列出所有Agent"""
        return list(cls._agents.values())
    
    @classmethod
    def get_by_capability(cls, capability: CapabilityType) -> List[IAgent]:
        """按能力查找Agent"""
        return [
            agent for agent in cls._agents.values()
            if agent.supports_capability(capability)
        ]


# 注册默认Agent类型
AgentFactory.register("monitor", MonitorAgent)
AgentFactory.register("executor", ExecutorAgent)


# ==================== CLI工具 ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent接口规范工具")
    parser.add_argument("--action", choices=["create", "list", "test"],
                       default="list", help="操作")
    parser.add_argument("--type", help="Agent类型")
    parser.add_argument("--agent-id", help="Agent ID")
    parser.add_argument("--config", help="配置(JSON)")
    
    args = parser.parse_args()
    
    if args.action == "create":
        config = json.loads(args.config) if args.config else {}
        agent = AgentFactory.create(args.type, config)
        print(f"创建Agent: {agent.agent_id}")
        
        # 测试启动
        asyncio.run(agent.start())
        print(f"Agent状态: {agent.get_health().status.value}")
        
        asyncio.run(agent.stop())
    
    elif args.action == "list":
        agents = AgentFactory.list_agents()
        print(f"已注册Agent数量: {len(agents)}")
        for agent in agents:
            meta = agent.get_metadata()
            health = agent.get_health()
            print(f"- {meta.name} ({meta.agent_id}): {health.status.value}")
    
    elif args.action == "test":
        # 测试消息协议
        request = TaskRequest(
            task_type="monitor",
            description="测试任务",
            payload={"target": "localhost"}
        )
        
        msg = MessageProtocol.create_task_message(
            "test-sender", "test-receiver", request
        )
        
        serialized = MessageProtocol.serialize_message(msg)
        print("序列化消息:")
        print(serialized)
        
        deserialized = MessageProtocol.deserialize_message(serialized)
        print("\n反序列化成功!")
        print(f"消息类型: {deserialized.message_type.value}")
        print(f"发送者: {deserialized.sender_id}")


if __name__ == "__main__":
    main()