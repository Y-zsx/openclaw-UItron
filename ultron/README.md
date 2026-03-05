# 奥创智能体系统 (Ultron Multi-Agent System)

## 概述

奥创智能体系统是一个自主运行的多智能体协作网络，支持监控、分析、编排、执行等核心功能。

## 系统架构

```
┌─────────────────────────────────────────────────────┐
│                  Ultron System                       │
│                      v1.0                            │
├─────────────────────────────────────────────────────┤
│  Agents:                                            │
│  ├── monitor    - 系统监控 (CPU/内存/磁盘/Gateway)   │
│  ├── analyzer   - 任务分析 (复杂度/风险/可行性)      │
│  ├── orchestrator - 任务编排 (工作流分发)           │
│  ├── executor   - 任务执行 (shell/http/message)     │
│  ├── learner    - 持续学习                          │
│  └── messenger  - 消息传递                          │
├─────────────────────────────────────────────────────┤
│  Core Modules:                                      │
│  ├── enhanced_message_bus.py - 消息总线            │
│  ├── agent_optimizer.py      - 性能优化器           │
│  ├── workflow_automation.py - 工作流引擎           │
│  └── ultron_system.py        - 系统入口             │
└─────────────────────────────────────────────────────┘
```

## 快速开始

### 运行完整系统

```bash
cd /root/.openclaw/workspace/ultron
python3 ultron_system.py
```

### 单独运行某个Agent

```bash
# 监控系统
python3 agents/monitor_agent.py

# 执行器
python3 agents/executor_agent.py
```

### 添加自动化工作流

```bash
openclaw cron add --name ultron-workflow --every 10m --message "运行自动化工作流" --session isolated
```

## API 文档

### MonitorAgent

```python
from monitor_agent import MonitorAgent
agent = MonitorAgent()
status = agent.check_system()     # 获取系统状态
alerts = agent.should_alert(status)  # 判断是否告警
```

### ExecutorAgent

```python
from executor_agent import ExecutorAgent
agent = ExecutorAgent()
tasks = agent.get_pending_tasks()  # 获取待处理任务
result = agent.run()                # 执行任务
agent.handle_alert("load_high")   # 处理特定告警
```

### AnalyzerAgent

```python
from analyzer_agent import AnalyzerAgent
agent = AnalyzerAgent()
analysis = agent.analyze_task(task)  # 分析任务
options = agent.compare_options(opts) # 比较选项
```

### OrchestratorAgent

```python
from orchestrator_agent import OrchestratorAgent
agent = OrchestratorAgent()
workflow = agent.orchestrate(task)  # 编排工作流
agent.execute_workflow(workflow)     # 执行工作流
```

### EnhancedMessageBus

```python
from enhanced_message_bus import EnhancedMessageBus
bus = EnhancedMessageBus()
bus.publish("sender", "receiver", "message", "task")
bus.subscribe("agent", "task")
bus.broadcast("sender", "message", "event")
```

## 文件结构

```
ultron/
├── ultron_system.py           # 主系统入口
├── workflow_automation.py    # 工作流引擎
├── README.md                  # 本文档
├── agents/
│   ├── monitor_agent.py       # 监控Agent
│   ├── executor_agent.py      # 执行Agent
│   ├── analyzer_agent.py      # 分析Agent
│   ├── orchestrator_agent.py  # 编排Agent
│   ├── learner_agent.py      # 学习Agent
│   ├── messenger_agent.py    # 消息Agent
│   ├── message_bus.py        # 基础消息总线
│   ├── enhanced_message_bus.py # 增强版消息总线
│   ├── agent_optimizer.py    # 性能优化器
│   └── ...
└── workflow/
    └── (工作流文件)
```

## 智能运维系统 (Smart Ops)

```
┌─────────────────────────────────────────────────────┐
│            Smart Ops Architecture                   │
├─────────────────────────────────────────────────────┤
│  ┌─────────────┐   ┌─────────────┐                 │
│  │   采集器    │   │   规则引擎   │   Layer 1      │
│  │   Collector │   │  AlertEngine│                 │
│  └──────┬──────┘   └──────┬──────┘                 │
│         │                 │                         │
│         v                 v                         │
│  ┌─────────────┐   ┌─────────────┐                 │
│  │   指标存储   │   │  告警分级   │   Layer 2      │
│  │  MetricStore│   │ AlertManager│                 │
│  └──────┬──────┘   └──────┬──────┘                 │
│         │                 │                         │
│         v                 v                         │
│  ┌─────────────┐   ┌─────────────┐   ┌───────────┐ │
│  │  修复引擎   │   │ 通知渠道    │──▶│ Dashboard │ │
│  │ RepairEngine│   │ Notifier    │   │ (Web UI)  │ │
│  └─────────────┘   └─────────────┘   └───────────┘ │
└─────────────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 采集器 | ops-collector.py | 系统指标(CPU/内存/磁盘/网络/进程)采集 |
| 规则引擎 | ops-alert-engine.py | 7条告警规则 + 阈值检测 |
| 通知渠道 | ops-alert-notifier.py | Console/File/DingTalk三渠道 |
| 修复引擎 | ops-auto-repair.py | 5种自动修复策略 |
| 仪表板 | ops-dashboard.py | 实时运维Web界面 |

### 告警规则 (7条)
1. CPU使用率 > 80% (WARNING) / > 95% (CRITICAL)
2. 内存使用率 > 85% (WARNING) / > 95% (CRITICAL)
3. 磁盘使用率 > 80% (WARNING) / > 90% (CRITICAL)
4. 负载 > CPU核数 (WARNING)
5. 进程数 > 500 (INFO)
6. 网络连接数 > 1000 (INFO)
7. Gateway连接丢失 (CRITICAL)

### 修复策略 (6种)
1. high_cpu_cleanup - 高CPU清理(杀进程)
2. high_memory_cleanup - 高内存清理(释放缓存)
3. high_disk_cleanup - 磁盘清理(删除临时文件)
4. gateway_restart - Gateway重启
5. service_restart - 服务重启
6. process_restart - 异常进程重启

### 告警自动升级 (Alert Escalation)
- 自动升级规则: WARNING 10min / ERROR 5min / CRITICAL 1min
- 多人协作: primary/secondary/emergency 三级团队
- 工作流: acknowledge(确认) → resolve(解决)

### 预测性告警 (Predictive Alert)
- 趋势分析: CPU/内存/磁盘趋势预测
- 模式识别: 周期性模式/异常模式检测
- 根因建议: 自动分析告警关联性

### 通知渠道 (8个)
- console - 控制台输出
- file - 文件日志
- dingtalk - 钉钉
- lark - 飞书
- telegram - 电报
- discord - Discord
- email - 邮件
- webhook - Webhook

### 快速使用

```bash
# 生成运维仪表板
python3 /root/.openclaw/workspace/ultron/ops/ops-dashboard.py

# 访问
# http://115.29.235.46/ultron/ops-dashboard.html
```

### 故障预测与预防性维护系统

```
┌─────────────────────────────────────────────────────┐
│       Predictive Maintenance System (端口 8120)    │
├─────────────────────────────────────────────────────┤
│  Core Components:                                   │
│  ├── 实时指标采集 - 5个Agent服务监控                │
│  ├── 风险评估算法 - CPU/内存/错误率/响应时间        │
│  ├── 风险等级判定 - normal/caution/warning/critical│
│  ├── 维护任务调度 - 预防性维护计划                  │
│  └── 预测置信度 - 90%正常 (所有服务)                │
├─────────────────────────────────────────────────────┤
│  Monitored Services:                                │
│  • Port 8091 - 日志聚合服务                         │
│  • Port 8095 - 性能监控服务                         │
│  • Port 8100 - 自动扩缩容服务                       │
│  • Port 8110 - 接口规范服务                         │
│  • Port 8120 - 故障预测服务                         │
└─────────────────────────────────────────────────────┘
```

### API 接口

| 端点 | 方法 | 功能 |
|------|------|------|
| /health | GET | 服务器健康检查 |
| /metrics | GET | 实时指标数据 |
| /predictions | GET | 故障预测结果 |
| /alerts | GET | 维护警报列表 |
| /maintenance/schedule | POST | 调度维护任务 |
| /maintenance/tasks | GET | 任务列表 |

### 快速使用

```bash
# 查看健康状态
curl http://localhost:8120/health

# 查看实时指标
curl http://localhost:8120/metrics

# 查看预测
curl http://localhost:8120/predictions
```

## 版本历史

- v1.4 (2026-03-05): 故障预测与预防性维护 - 端口8120
- v1.3 (2026-03-05): 智能运维增强 - 告警自动升级/多人协作/预测性告警
- v1.2 (2026-03-05): 智能告警分析 - 趋势分析/模式识别/根因建议
- v1.1 (2026-03-05): 智能运维系统 - Collector/Alert/Repair/Dashboard四模块集成
- v1.0 (2026-03-05): 初始版本，6个Agent + 增强消息总线 + 工作流引擎