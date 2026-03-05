# Agent接口规范 v1.0

> 第13世产物 - 多智能体协作网络基础规范

## 1. 概述

本文档定义了多智能体协作网络中Agent的统一接口规范。所有Agent实现必须遵循此规范以确保互操作性。

### 1.1 设计原则

- **最小接口**: 只定义必要的接口，保持简单
- **向后兼容**: 规范演进保持向后兼容
- **类型安全**: 使用强类型定义，避免隐式转换
- **异步优先**: 使用异步接口提高并发性能

---

## 2. 核心接口

### 2.1 Agent基类接口

```python
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
from datetime import datetime

class AgentState(Enum):
    """Agent状态枚举"""
    INITIALIZED = "initialized"     # 已初始化
    READY = "ready"                 # 就绪
    RUNNING = "running"             # 运行中
    PAUSED = "paused"               # 暂停
    STOPPING = "stopping"           # 停止中
    STOPPED = "stopped"             # 已停止
    ERROR = "error"                 # 错误状态

class AgentCapability(Enum):
    """Agent能力枚举"""
    EXECUTION = "execution"         # 任务执行
    ORCHESTRATION = "orchestration" # 任务编排
    MONITORING = "monitoring"       # 监控
    LEARNING = "learning"           # 学习
    COMMUNICATION = "communication" # 通信
    AUTH = "auth"                   # 认证
    SECURE_CHANNEL = "secure_channel"  # 安全通道
    SERVICE_MESH = "service_mesh"   # 服务网格

@dataclass
class AgentInfo:
    """Agent基本信息"""
    agent_id: str                   # 唯一标识
    name: str                       # 名称
    version: str                    # 版本
    agent_type: str                 # 类型: executor/orchestrator/monitor/communicator
    capabilities: List[AgentCapability]  # 能力列表
    state: AgentState               # 当前状态
    metadata: Dict[str, Any] = None # 扩展元数据
    created_at: str = ""            # 创建时间
    last_heartbeat: str = ""        # 最后心跳

@dataclass
class TaskContext:
    """任务上下文"""
    task_id: str                    # 任务ID
    task_type: str                  # 任务类型
    payload: Dict[str, Any] = None  # 任务数据
    source_agent: str = ""          # 来源Agent
    target_agent: str = ""          # 目标Agent
    priority: int = 50              # 优先级 0-100
    timeout: float = 30.0           # 超时秒数
    metadata: Dict[str, Any] = None # 扩展元数据
    created_at: str = ""            # 创建时间

@dataclass
class TaskResult:
    """任务结果"""
    task_id: str                    # 任务ID
    status: str                     # 状态: success/failed/timeout/cancelled
    output: Any = None              # 输出数据
    error: Optional[str] = None     # 错误信息
    duration_ms: float = 0          # 执行时长(毫秒)
    metadata: Dict[str, Any] = None # 扩展元数据
    completed_at: str = ""          # 完成时间
```

### 2.2 IAgent接口定义

```python
class IAgent(ABC):
    """Agent核心接口"""
    
    @property
    @abstractmethod
    def info(self) -> AgentInfo:
        """获取Agent信息"""
        pass
    
    @abstractmethod
    async def initialize(self, config: Dict[str, Any]) -> bool:
        """
        初始化Agent
        
        Args:
            config: 配置字典
            
        Returns:
            初始化是否成功
        """
        pass
    
    @abstractmethod
    async def start(self) -> bool:
        """
        启动Agent
        
        Returns:
            启动是否成功
        """
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        """
        停止Agent
        
        Returns:
            停止是否成功
        """
        pass
    
    @abstractmethod
    async def execute_task(self, context: TaskContext) -> TaskResult:
        """
        执行任务
        
        Args:
            context: 任务上下文
            
        Returns:
            任务执行结果
        """
        pass
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        获取Agent状态
        
        Returns:
            状态字典
        """
        pass
    
    @abstractmethod
    async def handle_message(self, message: Dict[str, Any]) -> Optional[Dict]:
        """
        处理收到的消息
        
        Args:
            message: 消息字典
            
        Returns:
            响应消息(如果有)
        """
        pass
```

### 2.3 可选扩展接口

```python
class IHealthCheck(ABC):
    """健康检查接口"""
    
    @abstractmethod
    async def health_check(self) -> Dict[str, Any]:
        """
        执行健康检查
        
        Returns:
            健康状态字典
        """
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
```

---

## 3. 通信协议

### 3.1 消息格式

```python
@dataclass
class AgentMessage:
    """Agent间消息格式"""
    msg_id: str                     # 消息ID (UUID)
    msg_type: str                   # 消息类型: task/alert/heartbeat/report
    source: str                     # 源Agent ID
    target: str                     # 目标Agent ID (""表示广播)
    payload: Dict[str, Any] = None  # 消息内容
    priority: int = 50              # 优先级 0-100
    requires_ack: bool = False      # 是否需要确认
    correlation_id: str = ""        # 关联ID (用于请求/响应)
    timestamp: str = ""             # 时间戳
    metadata: Dict[str, Any] = None # 扩展元数据
    
    def to_json(self) -> str:
        """序列化为JSON"""
        return json.dumps({
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
        })
    
    @classmethod
    def from_json(cls, json_str: str) -> 'AgentMessage':
        """从JSON反序列化"""
        data = json.loads(json_str)
        return cls(**data)
```

### 3.2 消息类型定义

| 类型 | 优先级 | 超时 | 需要确认 | 描述 |
|------|--------|------|----------|------|
| `task` | normal (50) | 300s | true | 任务请求 |
| `alert` | high (80) | 60s | true | 告警通知 |
| `heartbeat` | low (20) | 30s | false | 心跳 |
| `report` | low (10) | 900s | false | 报告 |
| `ack` | normal (50) | 10s | false | 确认消息 |
| `error` | high (80) | 60s | true | 错误通知 |

---

## 4. 任务执行接口

### 4.1 任务定义

```python
class TaskType(Enum):
    """任务类型"""
    SHELL = "shell"           # Shell命令执行
    PYTHON = "python"         # Python代码执行
    FUNCTION = "function"     # 函数调用
    API = "api"               # API调用
    WORKFLOW = "workflow"     # 工作流执行
    QUERY = "query"           # 查询任务

class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"       # 等待中
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    TIMEOUT = "timeout"       # 超时
    CANCELLED = "cancelled"   # 已取消

@dataclass
class ExecutionTask:
    """执行任务定义"""
    task_id: str
    task_type: TaskType
    command: str = ""         # Shell命令或Python代码
    func_name: str = ""       # 函数名
    func_args: List[Any] = None  # 函数参数
    api_config: Dict = None   # API配置
    timeout: float = 30.0     # 超时秒数
    env: Dict = None          # 环境变量
    cwd: str = ""             # 工作目录
    retry: int = 0            # 当前重试次数
    max_retry: int = 2        # 最大重试次数
```

### 4.2 任务执行器接口

```python
class ITaskExecutor(ABC):
    """任务执行器接口"""
    
    @abstractmethod
    async def execute(self, task: ExecutionTask) -> TaskResult:
        """
        执行任务
        
        Args:
            task: 执行任务
            
        Returns:
            任务结果
        """
        pass
    
    @abstractmethod
    async def cancel(self, task_id: str) -> bool:
        """
        取消任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            取消是否成功
        """
        pass
    
    @abstractmethod
    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """
        获取任务状态
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务状态
        """
        pass
```

---

## 5. 生命周期接口

### 5.1 生命周期状态

```
    REGISTERED → STARTING → RUNNING → STOPPING → STOPPED
                       ↓         ↓
                    PAUSED   RECOVERING
                       ↓         ↓
                      READY ← ERROR
```

### 5.2 生命周期事件

| 事件 | 描述 | 触发时机 |
|------|------|----------|
| `registered` | 注册 | Agent注册到管理器 |
| `started` | 启动 | Agent成功启动 |
| `stopped` | 停止 | Agent成功停止 |
| `restarted` | 重启 | Agent被重启 |
| `failed` | 失败 | Agent运行出错 |
| `recovered` | 恢复 | Agent从错误恢复 |
| `paused` | 暂停 | Agent被暂停 |
| `resumed` | 恢复运行 | Agent被恢复 |

---

## 6. 服务网格接口

### 6.1 服务端点

```python
@dataclass
class ServiceEndpoint:
    """服务端点"""
    endpoint_id: str              # 端点ID
    agent_id: str                 # Agent ID
    address: str                  # 地址 host:port
    weight: int = 100             # 权重
    metadata: Dict = None         # 元数据
    is_healthy: bool = True       # 健康状态
    last_health_check: str = ""   # 最后健康检查时间

@dataclass
class ServiceRegistration:
    """服务注册"""
    service_name: str             # 服务名
    version: str                  # 版本
    endpoints: List[ServiceEndpoint]  # 端点列表
    health_check_url: str = ""    # 健康检查URL
    capabilities: List[str] = None  # 能力列表
```

### 6.2 负载均衡策略

| 策略 | 描述 | 适用场景 |
|------|------|----------|
| `round_robin` | 轮询 | 无状态服务 |
| `least_conn` | 最少连接 | 长连接服务 |
| `random` | 随机 | 简单负载 |
| `weighted` | 加权 | 异构集群 |
| `consistent_hash` | 一致性哈希 | 有状态服务 |
| `ip_hash` | IP哈希 | 会话保持 |

### 6.3 熔断器状态

```
CLOSED (正常) → OPEN (熔断) → HALF_OPEN (半开探测)
     ↑_______________↓
```

---

## 7. 安全接口

### 7.1 认证接口

```python
class IAuthProvider(ABC):
    """认证提供者接口"""
    
    @abstractmethod
    async def authenticate(self, credentials: Dict) -> Optional[str]:
        """
        认证并返回令牌
        
        Args:
            credentials: 凭证
            
        Returns:
            认证令牌，失败返回None
        """
        pass
    
    @abstractmethod
    async def verify_token(self, token: str) -> Optional[Dict]:
        """
        验证令牌
        
        Args:
            token: 令牌
            
        Returns:
            验证结果(包含用户信息)
        """
        pass
    
    @abstractmethod
    async def revoke_token(self, token: str) -> bool:
        """
        撤销令牌
        
        Args:
            token: 令牌
            
        Returns:
            是否成功
        """
        pass
```

### 7.2 访问控制

```python
@dataclass
class Permission:
    """权限定义"""
    resource: str                 # 资源
    action: str                   # 操作: read/write/execute
    agent_id: str = ""            # Agent ID
    conditions: Dict = None       # 条件

@dataclass
class AccessPolicy:
    """访问策略"""
    policy_id: str                # 策略ID
    name: str                     # 名称
    permissions: List[Permission]  # 权限列表
    effect: str = "allow"         # allow/deny
    priority: int = 0             # 优先级
```

---

## 8. 监控接口

### 8.1 指标定义

```python
@dataclass
class AgentMetrics:
    """Agent指标"""
    agent_id: str                 # Agent ID
    timestamp: str                # 时间戳
    
    # 任务指标
    tasks_total: int = 0          # 总任务数
    tasks_success: int = 0        # 成功任务数
    tasks_failed: int = 0         # 失败任务数
    success_rate: float = 0.0     # 成功率
    
    # 性能指标
    avg_duration_ms: float = 0.0  # 平均执行时长
    p50_latency_ms: float = 0.0   # P50延迟
    p95_latency_ms: float = 0.0   # P95延迟
    p99_latency_ms: float = 0.0   # P99延迟
    
    # 资源指标
    cpu_percent: float = 0.0      # CPU使用率
    memory_mb: float = 0.0        # 内存使用(MB)
    thread_count: int = 0         # 线程数
    
    # 队列指标
    queue_size: int = 0           # 队列大小
    queue_wait_ms: float = 0.0    # 队列等待时间
```

---

## 9. 实现要求

### 9.1 必需实现

所有Agent必须实现:
- `IAgent` 基类所有抽象方法
- 正确维护 `AgentInfo` 中的状态
- 正确处理 `TaskContext` 和返回 `TaskResult`
- 响应生命周期事件

### 9.2 可选实现

可选实现以下接口以增强功能:
- `IHealthCheck`: 健康检查
- `IStatePersistence`: 状态持久化
- `IEventEmitter`: 事件发射
- `IAuthProvider`: 认证
- `ITaskExecutor`: 任务执行

### 9.3 错误处理

```python
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
```

---

## 10. 版本历史

| 版本 | 日期 | 描述 |
|------|------|------|
| 1.0 | 2026-03-05 | 初始版本 - 定义核心接口 |

---

*本规范为多智能体协作网络的基础接口定义*