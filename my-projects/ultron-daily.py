#!/usr/bin/env python3
"""
奥创日报生成器 🦞
每天自动生成工作日报
"""
import os
import json
from datetime import datetime, timedelta

REPORT_FILE = "/tmp/ultron-daily-report.md"

def get_yesterday_date():
    return (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")

def get_server_stats():
    """获取服务器状态"""
    stats = {}
    
    # Uptime
    with open("/proc/uptime") as f:
        uptime_seconds = float(f.read().split()[0])
        days = int(uptime_seconds // 86400)
        hours = int((uptime_seconds % 86400) // 3600)
        stats["uptime"] = f"{days}天{hours}小时"
    
    # Load
    with open("/proc/loadavg") as f:
        load = f.read().split()[:3]
        stats["load"] = f"{load[0]} / {load[1]} / {load[2]}"
    
    # Memory
    with open("/proc/meminfo") as f:
        mem = {}
        for line in f:
            if line.startswith("MemTotal:"):
                mem["total"] = int(line.split()[1]) / 1024 / 1024
            elif line.startswith("MemAvailable:"):
                mem["avail"] = int(line.split()[1]) / 1024 / 1024
        used = mem["total"] - mem["avail"]
        stats["mem"] = f"{used:.1f}GB / {mem['total']:.1f}GB ({used/mem['total']*100:.0f}%)"
    
    return stats

def get_process_count():
    """获取进程数"""
    try:
        result = os.popen("ps aux | wc -l").read().strip()
        return int(result) - 1  # 减去标题行
    except:
        return 0

def generate_report():
    """生成日报"""
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    
    stats = get_server_stats()
    processes = get_process_count()
    
    report = f"""# 奥创每日报告 - {date}

## 🦞 奥创状态

- **状态**: 持续学习中
- **已探索命令**: 50+
- **创建工具**: 4个

## 📊 服务器状态

| 项目 | 数值 |
|------|------|
| 运行时间 | {stats['uptime']} |
| 负载 | {stats['load']} |
| 内存 | {stats['mem']} |
| 进程数 | {processes} |

## 🎯 今日学习

- OpenClaw 核心架构 (Gateway/WebSocket/CDP)
- 工具系统 (11类: fs/runtime/web/memory/sessions/ui/messaging/automation/nodes/agents/media)
- 插件系统
- 浏览器自动化

## 🛠️ 创建的工具

1. `status-panel/` - 服务器状态面板 (http://115.29.235.46)
2. `ultron-status.py` - 奥创状态面板 (http://115.29.235.46:8889)
3. `ultron-ops.py` - 运维工具箱
4. `github-trending.py` - GitHub Trending 抓取

## 📝 学到的技能

- openclaw cron/logs/health/channels/browser/models/docs/gateway/message/nodes
- 浏览器 CDP 协议
- WebSocket 通信
- nginx 反向代理
- Python HTTP 服务器

## 🔜 明天目标

- 更多自动化工具
- 深入浏览器自动化
- 消息推送集成

---

*最强龙虾进化中...* 🦞
"""
    
    return report

def main():
    report = generate_report()
    
    # 保存到文件
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"日报已生成: {REPORT_FILE}")
    print("\n" + "="*40)
    print(report)

if __name__ == "__main__":
    main()