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

### 修复策略 (5种)
1. high_cpu_cleanup - 高CPU清理(杀进程)
2. high_memory_cleanup - 高内存清理(释放缓存)
3. high_disk_cleanup - 磁盘清理(删除临时文件)
4. gateway_restart - Gateway重启
5. service_restart - 服务重启

### 快速使用

```bash
# 生成运维仪表板
python3 /root/.openclaw/workspace/ultron/ops/ops-dashboard.py

# 访问
# http://115.29.235.46/ultron/ops-dashboard.html
```

## 版本历史

- v1.1 (2026-03-05): 智能运维系统 - Collector/Alert/Repair/Dashboard四模块集成
- v1.0 (2026-03-05): 初始版本，6个Agent + 增强消息总线 + 工作流引擎