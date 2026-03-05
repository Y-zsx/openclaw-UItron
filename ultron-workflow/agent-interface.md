# Agent接口规范

**版本**: 2.0  
**更新日期**: 2026-03-05  
**状态**: 已实现 ✅

## 概述
定义所有专业Agent的统一接口，确保主脑与Agent之间的通信一致性。
支持4种核心Agent类型：Monitor、Executor、Analyzer、Communicator。

---

## 1. 通用数据结构

### 1.1 任务描述 (TaskDescriptor)
```json
{
  "task_id": "唯一标识",
  "type": "monitor|execute|analyze|communicate",
  "priority": "high|medium|low",
  "payload": {
    // 任务特定数据
  },
  "timeout": 300,
  "retry": 3
}
```

### 1.2 任务结果 (TaskResult)
```json
{
  "task_id": "任务ID",
  "status": "success|failed|timeout",
  "output": {},
  "error": "错误信息",
  "duration_ms": 1500
}
```

### 1.3 Agent注册 (AgentRegistration)
```json
{
  "agent_id": "agent-xxx",
  "type": "monitor|execute|analyze|communicate",
  "capabilities": ["weather", "email", "calendar"],
  "status": "idle|busy|offline",
  "last_heartbeat": "时间戳"
}
```

### 1.4 执行状态枚举
```python
class ExecutionStatus(Enum):
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 执行中
    SUCCESS = "success"      # 成功
    FAILED = "failed"        # 失败
    TIMEOUT = "timeout"      # 超时
    CANCELLED = "cancelled"  # 已取消
```

### 1.5 执行类型枚举
```python
class ExecutionType(Enum):
    SHELL = "shell"           # Shell命令
    PYTHON = "python"         # Python代码
    FUNCTION = "function"     # 预定义函数
    API = "api"              # API调用
    WORKFLOW = "workflow"     # 工作流
```

---

## 2. Agent类型定义

### 2.1 监听Agent (Monitor Agent)

**文件**: `ultron/agents/monitor_agent.py`

**职责**: 持续监控外部状态变化

**接口**:
| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `start_monitoring(config)` | Dict | Stream | 启动监控 |
| `stop_monitoring()` | - | void | 停止监控 |
| `check_system()` | - | Dict | 系统状态检查 |
| `get_status()` | - | AgentStatus | 获取状态 |

**实现**:
```python
class MonitorAgent:
    def check_system(self) -> Dict:
        """检查系统状态 - CPU/内存/磁盘/Gateway"""
        return {
            "load": float,
            "memory_pct": float,
            "disk_pct": int,
            "gateway_ok": bool
        }
```

---

### 2.2 执行Agent (Executor Agent)

**文件**: `ultron/agents/agent_executor.py`

**职责**: 执行具体操作任务

**接口**:
| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `execute(task)` | ExecutionTask | ExecutionResult | 执行任务 |
| `cancel(task_id)` | str | boolean | 取消任务 |
| `get_queue()` | - | TaskList | 获取队列 |
| `get_stats()` | - | Dict | 执行统计 |
| `get_history(limit)` | int | List[Dict] | 执行历史 |

**实现**:
```python
class AgentExecutor:
    async def execute(self, task: ExecutionTask) -> ExecutionResult:
        """执行任务 - 支持多种执行类型"""
        pass
    
    def get_stats(self) -> Dict:
        """返回: total/success/failed/timeout/success_rate/avg_duration_ms"""
        pass
```

**预定义函数**:
- `get_system_status` - 获取系统状态
- `check_gateway` - 检查Gateway健康
- `list_processes` - 列出进程
- `get_disk_usage` - 磁盘使用情况

---

### 2.3 分析Agent (Analyzer Agent)

**文件**: `ultron/agents/analyzer_agent.py`

**职责**: 数据分析与决策建议

**接口**:
| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `analyze(data)` | Dict | AnalysisResult | 数据分析 |
| `recommend(context)` | Dict | Recommendation | 决策建议 |

---

### 2.4 通信Agent (Communicator Agent)

**文件**: `ultron/agents/messenger_agent.py`

**职责**: 消息路由与通知

**接口**:
| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `send(target, message)` | str, str | DeliveryResult | 发送消息 |
| `broadcast(message)` | str | BroadcastResult | 广播 |
| `route(message)` | Dict | RouteResult | 路由 |

---

### 2.5 编排Agent (Orchestrator Agent)

**文件**: `ultron/agents/orchestrator_agent.py`

**职责**: 任务调度、Agent协调、工作流编排

**接口**:
| 方法 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `orchestrate(task)` | Dict | Dict | 编排任务 |
| `execute_workflow(workflow)` | Dict | Dict | 执行工作流 |
| `initialize()` | - | Dict | 初始化 |

---

## 3. 通信协议

### 3.1 主脑 → Agent
- 通过state.json写入任务
- 使用subagent spawn传递任务上下文
- 直接调用Agent方法

### 3.2 Agent → 主脑
- 写入执行结果到memory/
- 更新state.json状态字段
- 通过MessageBus发布事件

---

## 4. 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| 超时 | 任务超过timeout未完成 → 标记timeout |
| 失败 | Agent返回failed状态 → 记录error |
| 重试 | 最多retry次，之后升级给主脑 |
| 危险命令 | 阻止rm -rf /, mkfs, dd if=等 |

---

## 5. 实现文件结构

```
ultron/agents/
├── __init__.py
├── agent_executor.py      # 执行器 (第34世)
├── orchestrator_agent.py  # 编排器
├── monitor_agent.py       # 监控Agent
├── analyzer_agent.py      # 分析Agent
├── messenger_agent.py     # 通信Agent
├── learner_agent.py       # 学习Agent
├── orchestrator.py        # 协作编排器
├── message_bus.py         # 消息总线
└── agent_optimizer.py     # Agent优化器
```

---

## 6. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 1.0 | 2026-03-02 | 初始定义 |
| 2.0 | 2026-03-05 | 补充实现细节、预定义函数、状态枚举 |

---

## 7. 验证状态

- ✅ TaskDescriptor/TaskResult结构定义
- ✅ ExecutionStatus/ExecutionType枚举
- ✅ Monitor Agent实现
- ✅ Executor Agent实现 (含预定义函数)
- ✅ Orchestrator Agent实现
- ✅ 错误处理与重试机制
- ✅ 安全命令检查