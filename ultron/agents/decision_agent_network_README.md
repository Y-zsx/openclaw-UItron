# 决策Agent协作网络 (Decision Agent Network)

## 概述

**端口**: 18150

决策Agent协作网络将决策引擎与多Agent系统集成，实现智能协作决策。

## 核心功能

- **Agent注册与管理**: 支持动态注册和注销决策Agent
- **能力匹配**: 根据任务需求自动匹配合适的Agent
- **任务分发**: 自动将任务分发给具有相应能力的Agent
- **协作执行**: 支持多Agent协同完成任务

## API端点

### Agent管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/agents/register | 注册Agent |
| DELETE | /api/agents/{agent_id} | 注销Agent |
| GET | /api/agents | 列出所有Agent |
| GET | /api/agents/find?capability=xxx | 按能力查找Agent |

### 任务管理

| 方法 | 路径 | 描述 |
|------|------|------|
| POST | /api/tasks | 创建协作任务 |
| POST | /api/tasks/{task_id}/assign | 分配任务给Agent |
| POST | /api/tasks/{task_id}/complete | 完成任务 |
| GET | /api/tasks/{task_id} | 获取任务状态 |
| GET | /api/tasks | 列出任务 |
| GET | /api/tasks/history | 获取任务历史 |

### 状态监控

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | /api/network/status | 网络状态 |
| GET | /api/stats | 统计信息 |
| GET | /health | 健康检查 |

## 内置Agent

| Agent ID | 名称 | 能力 |
|----------|------|------|
| decision-monitor | 决策监控Agent | monitoring, decision_monitoring |
| decision-executor | 决策执行Agent | execution, action_execution |
| decision-analyzer | 决策分析Agent | analysis, decision_analysis |
| decision-notifier | 决策通知Agent | notification, alerting |

## 使用示例

### 1. 创建协作任务

```bash
curl -X POST http://localhost:18150/api/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "decision_id": "dec-001",
    "task_type": "execute_action",
    "required_capabilities": ["execution"]
  }'
```

响应:
```json
{
  "task_id": "b7e652ba",
  "assigned_agents": ["decision-executor"],
  "status": "created"
}
```

### 2. 查看网络状态

```bash
curl http://localhost:18150/api/network/status
```

### 3. 查找具有特定能力的Agent

```bash
curl "http://localhost:18150/api/agents/find?capability=execution"
```

## 与决策引擎集成

决策Agent网络与决策引擎(端口18120)集成工作流程:

1. 决策引擎做出决策
2. 协作网络接收决策ID和任务需求
3. 自动匹配具有相应能力的Agent
4. 分配任务给Agent执行
5. 收集执行结果并反馈给决策引擎

## 统计指标

- `total_tasks`: 总会话数
- `completed_tasks`: 已完成任务数
- `failed_tasks`: 失败任务数
- `agents_count`: 注册的Agent数量