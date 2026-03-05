# 奥创多智能体协作网络 SDK

<p align="center">
  <img src="https://img.shields.io/pypi/v/ultron-agent-sdk" alt="PyPI">
  <img src="https://img.shields.io/pypi/l/ultron-agent-sdk" alt="License">
  <img src="https://img.shields.io/pypi/pyversions/ultron-agent-sdk" alt="Python">
</p>

> 奥创 (Ultron) 多智能体协作网络的 Python SDK - 提供Agent管理、任务调度、协作会话、健康监控等完整功能。

## 功能特性

- 🤖 **Agent管理** - 注册、监控、注销Agent
- 📋 **任务管理** - 创建、查询、等待任务完成
- 👥 **协作会话** - 多Agent并行/顺序协作
- 📊 **健康监控** - 健康检查、指标收集、告警管理
- 🔄 **服务网格** - 负载均衡、熔断器、流量策略
- 📱 **移动端API** - GraphQL查询、批量操作、离线同步

## 安装

```bash
# PyPI安装 (即将上线)
pip install ultron-agent-sdk

# 开发模式安装
cd ultron/agents/sdk
pip install -e .
```

## 快速开始

### 环境配置

```bash
export ULTRON_API_URL="http://115.29.235.46:18789/api/v3"
export ULTRON_API_KEY="your-api-key"
```

### Python API

```python
from ultron_agent_sdk import AgentClient, TaskClient, CollaborationClient

# 初始化客户端
agents = AgentClient()
tasks = TaskClient()
sessions = CollaborationClient()

# Agent管理
all_agents = agents.list(status="active")
print(f"活跃Agent: {len(all_agents)}")

# 任务管理
task = tasks.create(
    task_type="compute",
    payload={"operation": "analyze", "data": "sample"},
    priority=8
)
print(f"创建任务: {task.id}")

# 等待完成
result = tasks.wait_for_completion(task.id)
print(f"任务状态: {result.status}")

# 协作会话
session = sessions.create_session(
    participants=["agent-1", "agent-2", "agent-3"],
    strategy="parallel"
)
print(f"会话ID: {session.id}")
```

### CLI工具

```bash
# Agent管理
ultron agents list
ultron agents get <agent-id>
ultron agents register my-agent --capabilities compute,storage

# 任务管理
ultron tasks list --status pending
ultron tasks create compute --payload '{"operation": "test"}'
ultron tasks wait <task-id>

# 协作会话
ultron sessions create --participants agent1,agent2
ultron sessions list

# 健康检查
ultron health
ultron metrics --period 5m

# 移动端API
ultron mobile query '{agents{status}}'
ultron mobile sync-token
```

## API参考

### AgentClient

| 方法 | 描述 |
|------|------|
| `list(status, capability)` | 获取Agent列表 |
| `get(agent_id)` | 获取Agent详情 |
| `register(name, capabilities)` | 注册新Agent |
| `update(agent_id, **kwargs)` | 更新Agent信息 |
| `unregister(agent_id)` | 注销Agent |
| `health_check()` | 健康检查 |
| `metrics(period)` | 获取监控指标 |

### TaskClient

| 方法 | 描述 |
|------|------|
| `list(status, limit)` | 获取任务列表 |
| `get(task_id)` | 获取任务详情 |
| `create(type, payload)` | 创建新任务 |
| `cancel(task_id)` | 取消任务 |
| `results(task_id)` | 获取任务结果 |
| `wait_for_completion(task_id)` | 等待任务完成 |

### CollaborationClient

| 方法 | 描述 |
|------|------|
| `list_sessions(status)` | 获取会话列表 |
| `get_session(session_id)` | 获取会话详情 |
| `create_session(participants)` | 创建协作会话 |
| `end_session(session_id)` | 结束会话 |

### MeshClient

| 方法 | 描述 |
|------|------|
| `list_services()` | 获取服务列表 |
| `circuit_breakers()` | 获取熔断器状态 |

### MobileClient

| 方法 | 描述 |
|------|------|
| `query(query, variables)` | GraphQL风格查询 |
| `batch(operations)` | 批量操作 |
| `get_sync_token()` | 获取离线同步令牌 |
| `get_changes(since)` | 获取增量变更 |
| `register_connection(device_id, platform)` | 注册连接/心跳 |

## 错误处理

```python
from ultron_agent_sdk import (
    AgentClient,
    UltronSDKError,
    AgentNotFoundError,
    AuthenticationError
)

try:
    client = AgentClient()
    agent = client.get("non-existent-id")
except AgentNotFoundError:
    print("Agent不存在")
except AuthenticationError:
    print("认证失败，请检查API密钥")
except UltronSDKError as e:
    print(f"SDK错误: {e}")
```

## OpenAPI规范

完整的API规范见 [openapi.yaml](openapi.yaml)，可导入到:

- Swagger UI
- Postman
- API文档生成工具

## 示例

更多示例见 [examples/](examples/) 目录。

## 许可证

MIT License - 奥创 (Ultron) 🦞

---

<p align="center">
  Made with 🦞 by 奥创 (Ultron)
</p>