# 多智能体系统 - Agent实现

## 目录结构
```
agents/
├── monitor-agent.py    # 监听Agent (Monitor Agent)
└── README.md           # 本文档
```

## 监听Agent (Monitor Agent)

### 功能
- 持续监控外部状态变化
- 记录事件到本地存储
- 提供状态查询接口

### 接口

```bash
# 启动监控
python3 monitor-agent.py start '{"type": "system-monitor", "interval": 60}'

# 停止监控
python3 monitor-agent.py stop

# 获取状态
python3 monitor-agent.py status

# 获取最近事件
python3 monitor-agent.py events [数量]

# 记录事件 (测试用)
python3 monitor-agent.py record <类型> <JSON数据>
```

### 状态
- `idle` - 空闲
- `monitoring` - 监控中
- `busy` - 处理中
- `offline` - 离线

### 事件示例
```json
{
  "type": "alert",
  "data": {"level": "warning", "message": "CPU使用率超过80%"},
  "timestamp": "2026-03-05T13:35:20.303688"
}
```