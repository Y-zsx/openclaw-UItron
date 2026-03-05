# Agent模块

## 目录结构

```
agents/
├── agent_lifecycle_manager.py   # Agent生命周期管理器 (第35世新增)
├── agent_executor.py            # Agent执行器 (第34世)
├── task_executor_integration.py # 任务执行集成
├── orchestrator_agent.py        # 编排Agent
├── monitor_agent.py             # 监控Agent
├── executor_agent.py            # 执行Agent
├── analyzer_agent.py            # 分析Agent
├── conflict_resolver.py         # 冲突解决
├── efficiency_analyzer.py       # 效率分析
├── task_dispatcher.py           # 任务分发
├── task_scheduler.py            # 任务调度
└── message_bus.py               # 消息总线
```

## Agent生命周期管理器

**文件**: `agent_lifecycle_manager.py`

### 功能

- **注册/注销**: 管理Agent元数据
- **启动/停止/重启**: 完整的生命周期控制
- **状态监控**: 实时跟踪运行状态
- **健康检查**: 自动评估健康度
- **自动恢复**: 低健康度自动重启

### 核心类

```python
from agent_lifecycle_manager import (
    AgentLifecycleManager,
    AgentMetadata,
    AgentStatus,
    AgentState,
    AgentType
)
```

### 使用示例

```python
# 创建管理器
mgr = AgentLifecycleManager()

# 注册Agent
mgr.register_agent(AgentMetadata(
    name="my-agent",
    agent_type=AgentType.PYTHON,
    script_path="/path/to/agent.py",
    auto_restart=True,
    max_restarts=3
))

# 启动
mgr.start_agent("my-agent")

# 获取状态
status = mgr.get_agent_status("my-agent")
print(f"状态: {status.state.value}")

# 停止
mgr.stop_agent("my-agent")

# 启动监控
mgr.start_monitoring()  # 自动健康检查和恢复
```

### 状态流转

```
REGISTERED → STARTING → RUNNING → STOPPING → STOPPED
                    ↓          ↓
                  FAILED   RECOVERING
```

## Agent执行器

**文件**: `agent_executor.py`

负责实际执行任务，支持多种执行类型:
- SHELL: Shell命令
- PYTHON: Python代码
- FUNCTION: 预定义函数
- API: API调用

详见 [agent_executor.py](agent_executor.py)