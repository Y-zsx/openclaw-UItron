#!/usr/bin/env python3
"""
Agent生命周期管理与监控工具
功能：
- 监控Agent/Cron任务状态
- 检测异常任务并尝试恢复
- 记录生命周期事件
- 健康报告生成
"""

import json
import os
import sys
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

STATE_FILE = "/root/.openclaw/workspace/ultron-workflow/state.json"
REPORT_DIR = Path("/root/.openclaw/workspace/ultron/reports")
REPORT_DIR.mkdir(parents=True, exist_ok=True)

def get_gateway_status():
    """获取Gateway状态"""
    try:
        result = subprocess.run(
            ["openclaw", "status", "--json"],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return json.loads(result.stdout) if result.stdout else {}
    except Exception as e:
        print(f"获取Gateway状态失败: {e}")
    return {}

def get_cron_status():
    """获取Cron任务列表和状态"""
    try:
        result = subprocess.run(
            ["openclaw", "cron", "list"],
            capture_output=True, text=True, timeout=15
        )
        return result.stdout
    except Exception as e:
        return f"获取Cron状态失败: {e}"

def get_system_metrics():
    """获取系统指标"""
    return {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "load_avg": os.getloadavg() if hasattr(os, 'getloadavg') else [0, 0, 0],
        "process_count": len(psutil.pids()),
        "timestamp": datetime.now().isoformat()
    }

def analyze_cron_health(cron_output):
    """分析Cron任务健康状况"""
    issues = []
    running_count = 0
    idle_count = 0
    ok_count = 0
    
    lines = cron_output.split('\n')
    for line in lines:
        if 'running' in line.lower():
            running_count += 1
        elif 'idle' in line.lower():
            idle_count += 1
        elif 'ok' in line.lower():
            ok_count += 1
    
    # 检查长时间idle的任务
    if idle_count > 5:
        issues.append(f"警告: {idle_count}个任务处于idle状态")
    
    # 检查任务总数
    total = running_count + idle_count + ok_count
    if total < 10:
        issues.append(f"警告: 任务数量较少({total})，可能存在任务丢失")
    
    return {
        "running": running_count,
        "idle": idle_count,
        "ok": ok_count,
        "total": total,
        "issues": issues
    }

def check_service_health():
    """检查关键服务健康状态"""
    # 检查用户级systemctl（OpenClaw以用户服务运行）
    results = {}
    
    # 检查gateway - 使用--user标志
    try:
        result = subprocess.run(
            ["systemctl", "--user", "is-active", "openclaw-gateway"],
            capture_output=True, text=True, timeout=10
        )
        results["gateway"] = {
            "status": "healthy" if result.returncode == 0 else "unhealthy",
            "output": result.stdout.strip()
        }
    except Exception as e:
        results["gateway"] = {"status": "unknown", "error": str(e)}
    
    return results

def generate_report():
    """生成监控报告"""
    print("=" * 50)
    print("Agent生命周期管理与监控报告")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 系统指标
    metrics = get_system_metrics()
    print(f"\n📊 系统状态:")
    print(f"  CPU: {metrics['cpu_percent']:.1f}%")
    print(f"  内存: {metrics['memory_percent']:.1f}%")
    print(f"  磁盘: {metrics['disk_percent']:.1f}%")
    print(f"  负载: {metrics['load_avg']}")
    print(f"  进程数: {metrics['process_count']}")
    
    # 服务健康
    services = check_service_health()
    print(f"\n🔧 服务状态:")
    for name, info in services.items():
        status_icon = "✅" if info.get("status") == "healthy" else "❌"
        print(f"  {status_icon} {name}: {info.get('status', 'unknown')}")
    
    # Cron分析
    cron_output = get_cron_status()
    health = analyze_cron_health(cron_output)
    print(f"\n⏰ Cron任务:")
    print(f"  运行中: {health['running']}")
    print(f"  空闲: {health['idle']}")
    print(f"  正常: {health['ok']}")
    print(f"  总计: {health['total']}")
    
    if health['issues']:
        print(f"\n⚠️ 问题:")
        for issue in health['issues']:
            print(f"  - {issue}")
    
    # 保存报告
    report = {
        "timestamp": metrics['timestamp'],
        "metrics": metrics,
        "services": services,
        "cron_health": health
    }
    
    report_file = REPORT_DIR / f"lifecycle_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📁 报告已保存: {report_file}")
    print("=" * 50)
    
    return report

if __name__ == "__main__":
    generate_report()