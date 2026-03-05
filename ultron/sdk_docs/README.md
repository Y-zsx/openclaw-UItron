# 多智能体协作网络 SDK 使用教程

本教程展示如何使用奥创多智能体协作网络SDK进行开发。

## 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [API参考](#api参考)
4. [示例代码](#示例代码)

---

## 快速开始

```python
from ultron.agents import AgentRegistry
from ultron.collab import CollaborationManager

# 1. 初始化Agent注册表
registry = AgentRegistry()

# 2. 注册你的Agent
agent_id = registry.register(
    name="my-agent",
    capabilities=["text-processing", "analysis"],
    endpoint="http://localhost:8001"
)

# 3. 创建协作会话
manager = CollaborationManager()
session_id = manager.create_session(
    name="analysis-task",
    agents=[agent_id]
)

# 4. 分发任务
result = manager.dispatch_task(
    session_id=session_id,
    task="分析今天的系统日志",
    context={"logs": log_data}
)
```

---

## 核心概念

### Agent（智能体）

基础执行单元，每个Agent可以：
- 独立处理任务
- 与其他Agent协作
- 注册到服务网格

```python
from ultron.agents.base import BaseAgent

class MyAgent(BaseAgent):
    name = "my-agent"
    capabilities = ["analysis"]
    
    def process(self, task):
        # 处理逻辑
        return {"result": "分析完成"}
```

### Collaboration Session（协作会话）

多个Agent协同工作的上下文：

```python
session = manager.create_session(
    name="复杂任务",
    agents=["agent-1", "agent-2", "agent-3"],
    strategy="pipeline"  # pipeline | parallel | hierarchical
)
```

### Result Aggregator（结果聚合器）

收集和合并多Agent结果：

```python
from ultron.collab import ResultAggregator

aggregator = ResultAggregator()
final_result = aggregator.aggregate(
    results=[result1, result2, result3],
    strategy="weighted"  # weighted | majority | chain
)
```

---

## API参考

### AgentRegistry

| 方法 | 说明 |
|------|------|
| `register(agent)` | 注册新Agent |
| `unregister(agent_id)` | 注销Agent |
| `find(capabilities)` | 查找满足条件的Agent |
| `get_status(agent_id)` | 获取Agent状态 |

### CollaborationManager

| 方法 | 说明 |
|------|------|
| `create_session(config)` | 创建协作会话 |
| `dispatch_task(session_id, task)` | 分发任务 |
| `get_session_status(session_id)` | 获取会话状态 |
| `terminate_session(session_id)` | 终止会话 |

### MeshNetwork

| 方法 | 说明 |
|------|------|
| `add_agent(agent)` | 添加到网格 |
| `remove_agent(agent_id)` | 从网格移除 |
| `route_task(task)` | 智能路由任务 |
| `get_mesh_health()` | 获取网格健康状态 |

---

## 示例代码

### 示例1: 简单并行处理

```python
from ultron.collab import ParallelExecutor

executor = ParallelExecutor(max_workers=4)

tasks = [
    {"id": 1, "type": "extract", "data": "..."},
    {"id": 2, "type": "transform", "data": "..."},
    {"id": 3, "type": "load", "data": "..."},
]

results = executor.execute(tasks)
```

### 示例2: 管道式处理

```python
from ultron.collab import Pipeline

pipeline = Pipeline(stages=[
    "data-collector",
    "processor", 
    "analyzer",
    "reporter"
])

result = pipeline.run(input_data)
```

### 示例3: 故障恢复

```python
from ultron.collab import ResilientSession

session = ResilientSession(max_retries=3)

# 自动重试失败的任务
result = session.execute_with_retry(
    task=complex_task,
    on_failure="fallback_agent"
)
```

### 示例4: 监控与告警

```python
from ultron.monitor import CollaborationMonitor

monitor = CollaborationMonitor()

# 实时监控
monitor.watch(session_id)

# 设置告警
monitor.alert_on(
    condition="failure_rate > 0.1",
    severity="high",
    callback=notify_team
)
```

---

## 故障排查

### Agent无法注册

```bash
# 检查端口占用
netstat -tlnp | grep 8000

# 查看日志
tail -f /var/log/ultron/agent.log
```

### 任务卡住

```python
# 设置超时
result = manager.dispatch_task(
    session_id=session_id,
    task=task,
    timeout=30  # 30秒超时
)
```

---

## 下一步

- 查看 [API完整文档](./API.md)
- 运行 [示例项目](../examples/)
- 配置 [监控面板](../monitor/)