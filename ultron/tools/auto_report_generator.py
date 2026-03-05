#!/usr/bin/env python3
"""
自动化报告生成器 - Auto Report Generator
智能运维助手系统的核心组件，自动生成运维日报/周报/月报
"""
import json
import os
import sys
import time
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

# 配置
SCRIPT_DIR = Path(__file__).parent
WORKSPACE = Path("/root/.openclaw/workspace")
REPORTS_DIR = WORKSPACE / "ultron" / "reports"
ALERTS_DB = WORKSPACE / "ultron" / "data" / "alerts.db"
SYSTEM_DB = WORKSPACE / "ultron" / "data" / "system_metrics.db"

# 确保目录存在
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def get_system_health():
    """获取系统健康状态"""
    try:
        # CPU
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
        
        # 内存
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            mem_total = int([l for l in meminfo.split('\n') if 'MemTotal' in l][0].split()[1])
            mem_available = int([l for l in meminfo.split('\n') if 'MemAvailable' in l][0].split()[1])
            mem_used = mem_total - mem_available
            mem_percent = round(mem_used / mem_total * 100, 1)
        
        # 磁盘
        import subprocess
        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_parts = disk_result.stdout.split('\n')[1].split()
        disk_used = disk_parts[2]
        disk_percent = disk_parts[4]
        
        return {
            "load": load,
            "memory_percent": mem_percent,
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "cpu_count": os.cpu_count() or 4
        }
    except Exception as e:
        return {"error": str(e)}

def get_service_status():
    """获取服务状态"""
    services = [
        ("Gateway", 18789),
        ("Agent注册", 8100),
        ("Agent规范", 8110),
        ("Agent预测", 8120),
        ("健康监控", 18090),
        ("日志聚合", 18091),
        ("协作监控", 18093),
    ]
    
    import socket
    result = {}
    for name, port in services:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            r = sock.connect_ex(('127.0.0.1', port))
            result[name] = "✅ 运行中" if r == 0 else "❌ 停止"
        except:
            result[name] = "❌ 错误"
        finally:
            sock.close()
    
    return result

def get_alert_stats(hours=24):
    """获取告警统计"""
    alerts_db = Path(ALERTS_DB)
    if not alerts_db.exists():
        return {"total": 0, "critical": 0, "error": 0, "warning": 0, "info": 0}
    
    try:
        conn = sqlite3.connect(str(alerts_db))
        cursor = conn.cursor()
        
        # 获取过去N小时的告警
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(
            "SELECT severity, COUNT(*) FROM alerts WHERE created_at >= ? GROUP BY severity",
            (since,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        stats = {"total": 0, "critical": 0, "error": 0, "warning": 0, "info": 0}
        for severity, count in rows:
            stats[severity.lower()] = count
            stats["total"] += count
        
        return stats
    except Exception as e:
        return {"error": str(e)}

def get_recent_alerts(hours=24, limit=10):
    """获取最近告警"""
    alerts_db = Path(ALERTS_DB)
    if not alerts_db.exists():
        return []
    
    try:
        conn = sqlite3.connect(str(alerts_db))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(
            "SELECT id, severity, title, message, created_at FROM alerts WHERE created_at >= ? ORDER BY created_at DESC LIMIT ?",
            (since, limit)
        )
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": r[0],
                "severity": r[1],
                "title": r[2],
                "message": r[3],
                "created_at": r[4]
            }
            for r in rows
        ]
    except:
        return []

def generate_daily_report():
    """生成日报"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_date = datetime.now().strftime('%Y年%m月%d日')
    
    # 收集数据
    health = get_system_health()
    services = get_service_status()
    alert_stats = get_alert_stats(24)
    recent_alerts = get_recent_alerts(24, 5)
    
    # 构建报告
    report = f"""# 📊 智能运维日报 - {report_date}

## 🖥️ 系统健康状态

| 指标 | 状态 |
|------|------|
| CPU负载 | {health.get('load', ['N/A'])[0]} (1min) |
| 内存使用 | {health.get('memory_percent', 'N/A')}% |
| 磁盘使用 | {health.get('disk_used', 'N/A')} ({health.get('disk_percent', 'N/A')}) |

## 🔧 服务状态

"""
    for name, status in services.items():
        report += f"- **{name}**: {status}\n"
    
    report += f"""
## 🚨 告警统计 (过去24小时)

| 级别 | 数量 |
|------|------|
| 🔴 Critical | {alert_stats.get('critical', 0)} |
| 🟠 Error | {alert_stats.get('error', 0)} |
| 🟡 Warning | {alert_stats.get('warning', 0)} |
| 🔵 Info | {alert_stats.get('info', 0)} |
| **总计** | **{alert_stats.get('total', 0)}** |

"""
    
    if recent_alerts:
        report += "## 📝 最近告警\n\n"
        for alert in recent_alerts:
            emoji = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(alert['severity'], "⚪")
            report += f"- {emoji} **{alert['severity'].upper()}**: {alert['title']} - {alert['created_at']}\n"
    
    report += f"""
---
*报告生成时间: {timestamp}*
*🤖 奥创智能运维助手*
"""
    
    return report, {
        "date": report_date,
        "timestamp": timestamp,
        "health": health,
        "services": services,
        "alert_stats": alert_stats,
        "recent_alerts": recent_alerts
    }

def save_report(report_text, metadata, report_type="daily"):
    """保存报告到文件"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"{report_type}_{timestamp}"
    
    # 保存文本格式
    txt_path = REPORTS_DIR / f"{filename}.txt"
    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(report_text)
    
    # 保存JSON格式
    json_path = REPORTS_DIR / f"{filename}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump({
            "report": report_text,
            "metadata": metadata
        }, f, ensure_ascii=False, indent=2)
    
    return str(txt_path), str(json_path)

def main():
    import argparse
    parser = argparse.ArgumentParser(description='自动化报告生成器')
    parser.add_argument('--type', choices=['daily', 'weekly', 'monthly'], default='daily', help='报告类型')
    parser.add_argument('--hours', type=int, default=24, help='统计小时数')
    parser.add_argument('--save-only', action='store_true', help='仅保存不打印')
    args = parser.parse_args()
    
    print("=" * 60)
    print("📊 自动化报告生成器")
    print("=" * 60)
    
    if args.type == 'daily':
        report_text, metadata = generate_daily_report()
    else:
        report_text, metadata = generate_daily_report()  # 暂只支持日报
    
    # 保存报告
    txt_path, json_path = save_report(report_text, metadata, args.type)
    print(f"✅ 报告已保存:")
    print(f"   - 文本: {txt_path}")
    print(f"   - JSON: {json_path}")
    
    if not args.save_only:
        print("\n" + "=" * 60)
        print("📄 报告内容:")
        print("=" * 60)
        print(report_text)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())