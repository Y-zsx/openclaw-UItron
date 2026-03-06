# 奥创自动化运维脚本集合

## 概述

这是一个统一的自动化运维脚本管理平台，集合了奥创系统中的所有运维脚本，提供分类、搜索、运行、健康检查等功能。

## 目录结构

```
ultron/automation/
├── ops_runner.py       # 主入口脚本
├── quick_health.py     # 快速健康检查
├── batch_ops.py        # 批量运维操作
├── README.md           # 本文件
└── ops_report.json     # 报告输出
```

## 快速开始

### 1. 列出所有脚本分类

```bash
cd /root/.openclaw/workspace/ultron/automation
python ops_runner.py list
```

### 2. 查看特定分类

```bash
python ops_runner.py list health      # 健康监控
python ops_runner.py list monitor     # Agent监控
python ops_runner.py list alert       # 告警系统
python ops_runner.py list scaling     # 弹性伸缩
```

### 3. 检查脚本状态

```bash
python ops_runner.py check
```

### 4. 快速健康检查

```bash
python quick_health.py
# 或
python ops_runner.py health
```

### 5. 搜索脚本

```bash
python ops_runner.py search health
```

### 6. 运行脚本

```bash
python ops_runner.py run agent_health_integration.py
```

### 7. 生成报告

```bash
python ops_runner.py report
```

## 批量运维

### 查看所有服务状态

```bash
python batch_ops.py status-all
```

### 启动所有服务

```bash
python batch_ops.py start-all
```

### 停止所有服务

```bash
python batch_ops.py stop-all
```

### 管理单个服务

```bash
python batch_ops.py start health-api
python batch_ops.py stop health-api
python batch_ops.py restart health-api
python batch_ops.py status health-api
```

## 脚本分类

| 分类ID | 名称 | 说明 |
|--------|------|------|
| health | 健康监控 | 系统健康检查和监控 |
| monitor | Agent监控 | Agent状态监控和告警 |
| alert | 告警系统 | 告警分析和通知 |
| scaling | 弹性伸缩 | 资源调度和伸缩 |
| self_healing | 自愈系统 | 系统自愈和自动修复 |
| collaboration | 协作系统 | Agent协作和网络 |
| reporting | 报表系统 | 报告生成和推送 |
| logs | 日志系统 | 日志聚合和分析 |
| self_improvement | 自我进化 | 自我优化和学习 |
| capability | 能力系统 | 能力评估和扩展 |
| deployment | 部署管理 | 部署和生命周期 |
| tracing | 分布式追踪 | 分布式追踪和分析 |
| tasks | 任务管理 | 任务调度和重试 |

## 关键端口

| 端口 | 服务 | 说明 |
|------|------|------|
| 18210 | Agent健康API | 健康监控主服务 |
| 18227 | 自愈API | 系统自愈服务 |
| 18228 | 集成测试API | 系统集成测试 |
| 18225 | 系统摘要API | 系统状态摘要 |
| 18229 | 调度器日志分析 | 日志分析服务 |

## 常用运维命令

```bash
# 一键健康检查
python quick_health.py

# 查看服务状态
python batch_ops.py status-all

# 重启健康API
python batch_ops.py restart health-api

# 查看所有健康监控脚本
python ops_runner.py list health

# 生成运维报告
python ops_runner.py report
```