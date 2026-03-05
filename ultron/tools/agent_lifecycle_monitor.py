#!/usr/bin/env python3
"""
Agent生命周期管理与监控工具 v2.0
功能：
- Agent状态监控
- 生命周期事件追踪
- 健康评分
- 告警生成
"""

import json
import os
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

REPORT_DIR = Path("/root/.openclaw/workspace/ultron/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

# Agent进程关键字
AGENT_KEYWORDS = ["python", "node", "openclaw", "agent", "cron"]

def get_system_metrics():
    """获取系统指标"""
    cpu = psutil.cpu_percent(interval=1)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    
    return {
        "cpu_percent": cpu,
        "memory_percent": mem.percent,
        "memory_available_gb": mem.available / (1024**3),
        "disk_percent": disk.percent,
        "timestamp": datetime.now().isoformat()
    }

def get_agent_processes():
    """获取Agent相关进程"""
    agents = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_percent']):
        try:
            pinfo = proc.info
            cmdline = ' '.join(pinfo.get('cmdline', []))
            name = pinfo.get('name', '')
            
            # 过滤Agent相关进程
            if any(kw in cmdline.lower() or kw in name.lower() for kw in AGENT_KEYWORDS):
                agents.append({
                    "pid": pinfo.get('pid'),
                    "name": name,
                    "cmdline": cmdline[:100] if cmdline else "",
                    "cpu": pinfo.get('cpu_percent', 0),
                    "memory": pinfo.get('memory_percent', 0)
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return agents

def get_openclaw_status():
    """获取OpenClaw状态"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
    except:
        pass
    return {}

def get_cron_jobs():
    """获取Cron任务状态"""
    jobs = []
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True, text=True, timeout=15
        )
        if result.returncode == 0:
            try:
                jobs = json.loads(result.stdout)
            except:
                pass
    except:
        pass
    return jobs

def calculate_health_score(metrics, agent_count):
    """计算健康评分"""
    score = 100
    
    # CPU评分
    if metrics['cpu_percent'] > 90:
        score -= 30
    elif metrics['cpu_percent'] > 70:
        score -= 15
    
    # 内存评分
    if metrics['memory_percent'] > 90:
        score -= 30
    elif metrics['memory_percent'] > 80:
        score -= 15
    
    # Agent数量评分
    if agent_count < 1:
        score -= 20
    
    return max(0, score)

def check_alerts(metrics, health_score):
    """生成告警"""
    alerts = []
    
    if metrics['cpu_percent'] > 90:
        alerts.append("HIGH_CPU: CPU使用率超过90%")
    if metrics['memory_percent'] > 90:
        alerts.append("HIGH_MEMORY: 内存使用率超过90%")
    if health_score < 70:
        alerts.append(f"LOW_HEALTH: 健康评分过低({health_score})")
    
    return alerts

def generate_lifecycle_report():
    """生成生命周期报告"""
    print("=" * 60)
    print("Agent生命周期管理与监控报告")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # 系统指标
    metrics = get_system_metrics()
    print(f"\n📊 系统状态:")
    print(f"  CPU: {metrics['cpu_percent']:.1f}%")
    print(f"  内存: {metrics['memory_percent']:.1f}%")
    print(f"  磁盘: {metrics['disk_percent']:.1f}%")
    
    # OpenClaw状态
    oc_status = get_openclaw_status()
    print(f"\n🔧 OpenClaw状态:")
    print(f"  运行中: {oc_status.get('running', 'unknown')}")
    
    # Cron jobs
    jobs = get_cron_jobs()
    print(f"\n⏰ Cron任务: {len(jobs)} 个")
    
    # Agent进程
    agents = get_agent_processes()
    print(f"\n🤖 Agent进程: {len(agents)} 个")
    
    # 健康评分
    health_score = calculate_health_score(metrics, len(agents))
    print(f"\n💚 健康评分: {health_score}/100")
    
    # 告警
    alerts = check_alerts(metrics, health_score)
    if alerts:
        print(f"\n⚠️ 告警:")
        for alert in alerts:
            print(f"  - {alert}")
    
    # 保存报告
    report = {
        "timestamp": metrics['timestamp'],
        "metrics": metrics,
        "health_score": health_score,
        "agent_count": len(agents),
        "cron_count": len(jobs),
        "alerts": alerts
    }
    
    report_file = REPORT_DIR / f"lifecycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 报告已保存")
    print("=" * 60)
    
    return report

if __name__ == "__main__":
    generate_lifecycle_report()