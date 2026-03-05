# Agent接口规范

## 概述
定义所有专业Agent的统一接口，确保主脑与Agent之间的通信一致性。

## 通用接口结构

### 1. 任务描述 (TaskDescriptor)
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

### 2. 任务结果 (TaskResult)
```json
{
  "task_id": "任务ID",
  "status": "success|failed|timeout",
  "output": {},
  "error": "错误信息",
  "duration_ms": 1500
}
```

### 3. Agent注册 (AgentRegistration)
```json
{
  "agent_id": "agent-xxx",
  "type": "monitor|execute|analyze|communicate",
  "capabilities": ["weather", "email", "calendar"],
  "status": "idle|busy|offline",
  "last_heartbeat": "时间戳"
}
```

## Agent类型定义

### 监听Agent (Monitor Agent)
- **职责**: 持续监控外部状态变化
- **接口**: 
  - `start_monitoring(config)` → stream events
  - `stop_monitoring()` → void
  - `get_status()` → AgentStatus

### 执行Agent (Executor Agent)
- **职责**: 执行具体操作任务
- **接口**:
  - `execute(task)` → TaskResult
  - `cancel(task_id)` → boolean
  - `get_queue()` → TaskList

### 分析Agent (Analyzer Agent)
- **职责**: 数据分析与决策建议
- **接口**:
  - `analyze(data)` → AnalysisResult
  - `recommend(context)` → Recommendation

### 通信Agent (Communicator Agent)
- **职责**: 消息路由与通知
- **接口**:
  - `send(target, message)` → DeliveryResult
  - `broadcast(message)` → BroadcastResult
  - `route(message)` → RouteResult

## 通信协议

### 主脑 → Agent
- 通过state.json写入任务
- 使用subagent spawn传递任务上下文

### Agent → 主脑
- 写入执行结果到memory/
- 更新state.json状态字段

## 错误处理
- 超时: 任务超过timeout未完成
- 失败: Agent返回failed状态
- 重试: 最多retry次，之后升级给主脑

## 实现优先级
1. 定义标准接口 (本世)
2. 监听Agent实现
3. 执行Agent实现