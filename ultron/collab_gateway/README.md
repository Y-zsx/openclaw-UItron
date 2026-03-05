# Agent协作网络API网关

提供RESTful API统一接口，集成注册、任务、健康检查、消息传递。

## 功能

- **Agent管理**: 注册、注销、心跳、状态更新
- **任务队列**: 提交、状态跟踪、完成/失败/取消
- **消息传递**: Agent间消息发送和接收
- **健康检查**: 实时系统健康状态
- **指标统计**: 请求计数、性能指标

## 快速开始

### 启动网关

```bash
python collab_api_gateway.py
```

默认监听 `http://0.0.0.0:8089`

### 使用CLI

```bash
# 健康检查
python gateway_cli.py health

# 注册Agent
python gateway_cli.py register agent-001 --capabilities code analysis

# 列出Agent
python gateway_cli.py agents

# 提交任务
python gateway_cli.py submit analysis --payload '{"data": "test"}' --priority 8

# 获取消息
python gateway_cli.py messages agent-001

# 查看指标
python gateway_cli.py metrics
```

### 使用Python客户端

```python
from gateway_client import create_client

client = create_client("http://localhost:8089")

# 注册Agent
client.register_agent("agent-001", ["code", "analysis"])

# 发送心跳
client.heartbeat("agent-001", status="active", health_score=95.0)

# 提交任务
result = client.submit_task("analysis", {"query": "test"}, priority=5)

# 获取消息
messages = client.get_messages("agent-001", unread_only=True)
```

## API端点

### 健康检查
- `GET /health` - 系统健康状态
- `GET /metrics` - 系统指标

### Agent管理
- `GET /agents` - 列出Agent
- `POST /agents` - 注册Agent
- `GET /agents/<id>` - 获取Agent详情
- `DELETE /agents/<id>` - 注销Agent
- `POST /agents/<id>/heartbeat` - 心跳
- `PUT /agents/<id>/status` - 更新状态

### 任务管理
- `GET /tasks` - 列出任务
- `POST /tasks` - 提交任务
- `GET /tasks/<id>` - 获取任务详情
- `PUT /tasks/<id>/status` - 更新状态
- `POST /tasks/<id>/cancel` - 取消任务
- `GET /tasks/pending` - 待处理任务

### 消息传递
- `GET /messages/<agent_id>` - 获取消息
- `POST /messages` - 发送消息
- `POST /messages/<agent_id>/<msg_id>/read` - 标记已读

## 状态枚举

### Agent状态
- `unknown` - 未知
- `registered` - 已注册
- `active` - 活跃
- `idle` - 空闲
- `busy` - 忙碌
- `unhealthy` - 不健康
- `offline` - 离线

### 任务状态
- `pending` - 待处理
- `running` - 运行中
- `completed` - 已完成
- `failed` - 失败
- `cancelled` - 已取消

## 与其他系统集成

```python
# 与健康检查系统集成
from agent_health_monitor import HealthChecker
from gateway_client import create_local_client

# 在健康检查回调中注册Agent
def on_health_check(agent_id, result):
    client = create_local_client()
    client.heartbeat(agent_id, 
                     status="active" if result["healthy"] else "unhealthy",
                     health_score=result.get("health_score", 0))

# 与任务调度集成
def submit_task_to_gateway(task_type, payload):
    client = create_client()
    result = client.submit_task(task_type, payload)
    return result.get("task_id")
```