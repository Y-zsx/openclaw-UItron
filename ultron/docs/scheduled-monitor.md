# 定时监控调度器

## 功能概述

定时监控调度器是智能运维助手系统的核心组件，负责定期执行系统监控、检查告警条件并发送通知。

## 核心功能

1. **定期系统检查** - 每5分钟执行一次系统状态检查
2. **告警检测** - 根据预设阈值检测是否需要告警
3. **多渠道通知** - 支持控制台、文件、钉钉告警
4. **状态记录** - 记录检查次数、告警历史、指标数据

## 文件结构

- `ops/scheduled-monitor.py` - 定时监控调度器主程序
- `logs/scheduled-monitor.log` - 监控日志
- `logs/monitor-state.json` - 监控状态数据

## 使用方法

```bash
# 手动执行
cd /root/.openclaw/workspace/ultron
python3 ops/scheduled-monitor.py

# 通过cron自动执行
openclaw cron add --name ultron-scheduled-monitor --every 5m --message "定时监控调度" --session isolated
```

## 监控指标

- **load** - 系统负载 (阈值: > 0.8 警告, > 1.0 严重)
- **memory_pct** - 内存使用率 (阈值: > 80% 警告, > 90% 严重)
- **disk_pct** - 磁盘使用率 (阈值: > 85% 警告, > 95% 严重)
- **gateway_ok** - Gateway服务状态

## 状态数据

监控状态保存在 `logs/monitor-state.json`:

```json
{
  "last_check": "2026-03-05T14:55:17.729502",
  "last_alert": null,
  "check_count": 1,
  "alert_count": 0,
  "last_metrics": {...}
}
```

## 集成

- MonitorAgent - 系统监控代理
- AlertNotifier - 告警通知器 (Console/File/DingTalk)
- Cron - 定时任务调度