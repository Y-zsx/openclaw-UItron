# Decision Agent Integration Layer

集成决策引擎(18120)与Agent网络(18150)及其他系统的桥梁服务。

## 端口
- **18220**

## 功能

### 1. 决策执行 (`/api/execute`)
将决策委托给Agent网络执行：
```json
POST /api/execute
{
  "decision": {"action": "monitor", "capabilities": ["monitor"]},
  "context": {"source": "test"},
  "priority": 5,
  "timeout": 300
}
```

### 2. Agent委托 (`/api/delegate`)
将复杂任务委托给特定类型的Agent：
```json
POST /api/delegate
{
  "agent_type": "analyzer",
  "task": {"type": "analyze", "data": "..."}
}
```

### 3. 系统集成 (`/api/integrate`)
与外部系统集成（任务队列、生命周期管理、监控）：
```json
POST /api/integrate
{
  "system": "task_queue",
  "action": "enqueue",
  "payload": {...}
}
```

### 4. 健康检查 (`/health`)
返回所有集成服务的状态：
```json
{
  "status": "healthy",
  "integrations": {
    "decision_engine": {"status": "online/offline"},
    "agent_network": {"status": "online/offline"},
    "task_queue": {"status": "online/offline"},
    "agent_lifecycle": {"status": "online/offline"}
  }
}
```

## 集成系统

| 系统 | 端口 | 状态 |
|------|------|------|
| Decision Engine | 18120 | 决策引擎 |
| Agent Network | 18150 | 任务分配 |
| Task Queue | 18101 | 队列管理 |
| Agent Lifecycle | 18100 | 生命周期 |
| Metrics | 18099 | 指标收集 |

## 使用示例

```bash
# 健康检查
curl http://localhost:18220/health

# 执行决策
curl -X POST http://localhost:18220/api/execute \
  -H "Content-Type: application/json" \
  -d '{"decision": {"action": "scale", "capabilities": ["executor"]}}'

# 委托任务
curl -X POST http://localhost:18220/api/delegate \
  -H "Content-Type: application/json" \
  -d '{"agent_type": "monitor", "task": {"type": "check_health"}}'
```