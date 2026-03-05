#!/usr/bin/env python3
"""
自动化报告生成器增强版 - Auto Report API Server
智能运维助手系统的报告服务组件
提供HTTP API用于获取报告和触发生成
"""
import json
import os
import sqlite3
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver

# 配置
SCRIPT_DIR = Path(__file__).parent
WORKSPACE = Path("/root/.openclaw/workspace")
REPORTS_DIR = WORKSPACE / "ultron" / "reports"
DATA_DIR = WORKSPACE / "ultron" / "data"
ALERTS_DB = DATA_DIR / "alerts.db"
SYSTEM_DB = DATA_DIR / "system_metrics.db"
LOG_DB = WORKSPACE / "ultron" / "tools" / "logs.db"

# 确保目录存在
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18190

# ========== 数据收集函数 ==========

def get_system_health():
    """获取系统健康状态"""
    try:
        with open('/proc/loadavg', 'r') as f:
            load = f.read().split()[:3]
        
        with open('/proc/meminfo', 'r') as f:
            meminfo = f.read()
            mem_total = int([l for l in meminfo.split('\n') if 'MemTotal' in l][0].split()[1])
            mem_available = int([l for l in meminfo.split('\n') if 'MemAvailable' in l][0].split()[1])
            mem_used = mem_total - mem_available
            mem_percent = round(mem_used / mem_total * 100, 1)
        
        import subprocess
        disk_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        disk_parts = disk_result.stdout.split('\n')[1].split()
        disk_used = disk_parts[2]
        disk_percent = disk_parts[4]
        
        # 网络统计
        net_result = subprocess.run(['cat', '/proc/net/dev'], capture_output=True, text=True)
        lines = net_result.stdout.split('\n')[2:10]
        total_rx = total_tx = 0
        for line in lines:
            parts = line.split()
            if len(parts) > 9:
                total_rx += int(parts[1])
                total_tx += int(parts[9])
        
        return {
            "load": load,
            "load_1m": float(load[0]),
            "load_5m": float(load[1]),
            "load_15m": float(load[2]),
            "memory_percent": mem_percent,
            "memory_used_mb": round(mem_used / 1024, 1),
            "memory_total_mb": round(mem_total / 1024, 1),
            "disk_used": disk_used,
            "disk_percent": disk_percent,
            "cpu_count": os.cpu_count() or 4,
            "network_rx_mb": round(total_rx / 1024 / 1024, 2),
            "network_tx_mb": round(total_tx / 1024 / 1024, 2)
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
        ("监控告警", 18146),
        ("日志分析", 18147),
        ("自动扩缩容", 18160),
        ("负载均衡", 18161),
        ("故障预测", 18170),
        ("自动治愈", 18180),
    ]
    
    import socket
    result = {}
    for name, port in services:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        try:
            r = sock.connect_ex(('127.0.0.1', port))
            result[name] = {"status": "running" if r == 0 else "stopped", "port": port}
        except:
            result[name] = {"status": "error", "port": port}
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
    except:
        return {"error": "Failed to get alert stats"}

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

def get_log_stats(hours=24):
    """获取日志统计"""
    log_db = Path(LOG_DB)
    if not log_db.exists():
        return {"total": 0, "error": 0, "warning": 0, "info": 0}
    
    try:
        conn = sqlite3.connect(str(log_db))
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')
        
        cursor.execute(
            "SELECT level, COUNT(*) FROM logs WHERE timestamp >= ? GROUP BY level",
            (since,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        stats = {"total": 0, "error": 0, "warning": 0, "info": 0}
        for level, count in rows:
            stats[level.lower()] = count
            stats["total"] += count
        
        return stats
    except:
        return {"error": "Failed to get log stats"}

def get_trend_analysis(hours=24):
    """获取趋势分析数据"""
    # 简化版趋势分析 - 基于历史数据分析
    health = get_system_health()
    
    # 计算健康评分
    score = 100
    
    # CPU负载扣分
    if health.get('load_1m', 0) > health.get('cpu_count', 4) * 0.7:
        score -= 20
    elif health.get('load_1m', 0) > health.get('cpu_count', 4) * 0.5:
        score -= 10
    
    # 内存扣分
    if health.get('memory_percent', 0) > 90:
        score -= 20
    elif health.get('memory_percent', 0) > 80:
        score -= 10
    
    # 磁盘扣分
    disk_pct = health.get('disk_percent', '0%')
    try:
        disk_pct_val = int(disk_pct.rstrip('%'))
        if disk_pct_val > 90:
            score -= 20
        elif disk_pct_val > 80:
            score -= 10
    except:
        pass
    
    # 服务状态扣分
    services = get_service_status()
    stopped_count = sum(1 for s in services.values() if s.get('status') == 'stopped')
    score -= stopped_count * 5
    
    # 告警扣分
    alerts = get_alert_stats(hours)
    score -= alerts.get('critical', 0) * 10
    score -= alerts.get('error', 0) * 5
    score -= alerts.get('warning', 0) * 2
    
    score = max(0, score)
    
    # 趋势判断
    if score >= 80:
        trend = "📈 上升"
        status = "healthy"
    elif score >= 50:
        trend = "➡️ 平稳"
        status = "warning"
    else:
        trend = "📉 下降"
        status = "critical"
    
    return {
        "health_score": score,
        "trend": trend,
        "status": status,
        "factors": {
            "cpu_load": health.get('load_1m', 0),
            "memory_percent": health.get('memory_percent', 0),
            "disk_percent": health.get('disk_percent', '0%'),
            "stopped_services": stopped_count,
            "alerts_24h": alerts.get('total', 0)
        }
    }

def generate_daily_report():
    """生成日报"""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    report_date = datetime.now().strftime('%Y年%m月%d日')
    
    # 收集数据
    health = get_system_health()
    services = get_service_status()
    alert_stats = get_alert_stats(24)
    recent_alerts = get_recent_alerts(24, 5)
    log_stats = get_log_stats(24)
    trend = get_trend_analysis()
    
    running_count = sum(1 for s in services.values() if s.get('status') == 'running')
    total_count = len(services)
    
    # 构建报告
    report = f"""# 📊 智能运维日报 - {report_date}

## 📈 整体状态

| 指标 | 值 |
|------|-----|
| 健康评分 | **{trend['health_score']}** {trend['trend']} |
| 服务状态 | {running_count}/{total_count} 运行中 |
| 告警数量 | {alert_stats.get('total', 0)} (24h) |
| 日志数量 | {log_stats.get('total', 0)} (24h) |

## 🖥️ 系统资源

| 指标 | 值 |
|------|-----|
| CPU负载 | {health.get('load_1m', 'N/A')} (1m) / {health.get('load_5m', 'N/A')} (5m) / {health.get('load_15m', 'N/A')} (15m) |
| 内存 | {health.get('memory_percent', 'N/A')}% ({health.get('memory_used_mb', 'N/A')}MB / {health.get('memory_total_mb', 'N/A')}MB) |
| 磁盘 | {health.get('disk_used', 'N/A')} ({health.get('disk_percent', 'N/A')}) |
| 网络 | ↓{health.get('network_rx_mb', 'N/A')}MB ↑{health.get('network_tx_mb', 'N/A')}MB |

## 🔧 服务状态

| 服务 | 状态 | 端口 |
|------|------|------|
"""
    
    for name, info in services.items():
        status_icon = "✅" if info.get('status') == 'running' else "❌"
        report += f"| {name} | {status_icon} {info.get('status')} | {info.get('port')} |\n"
    
    report += f"""
## 🚨 告警统计 (过去24小时)

| 级别 | 数量 |
|------|------|
| 🔴 Critical | {alert_stats.get('critical', 0)} |
| 🟠 Error | {alert_stats.get('error', 0)} |
| 🟡 Warning | {alert_stats.get('warning', 0)} |
| 🔵 Info | {alert_stats.get('info', 0)} |
| **总计** | **{alert_stats.get('total', 0)}** |

## 📝 日志统计 (过去24小时)

| 级别 | 数量 |
|------|------|
| 🔴 Error | {log_stats.get('error', 0)} |
| 🟡 Warning | {log_stats.get('warning', 0)} |
| 🔵 Info | {log_stats.get('info', 0)} |
| **总计** | **{log_stats.get('total', 0)}** |

"""
    
    if recent_alerts:
        report += "## ⚠️ 最近告警\n\n"
        for alert in recent_alerts:
            emoji = {"critical": "🔴", "error": "🟠", "warning": "🟡", "info": "🔵"}.get(alert['severity'], "⚪")
            report += f"- {emoji} **{alert['severity'].upper()}**: {alert['title']}\n"
    
    report += f"""
---
*报告生成时间: {timestamp}*
*🤖 奥创智能运维助手 v2.0*
"""
    
    metadata = {
        "date": report_date,
        "timestamp": timestamp,
        "health": health,
        "services": services,
        "alert_stats": alert_stats,
        "log_stats": log_stats,
        "trend": trend,
        "recent_alerts": recent_alerts
    }
    
    return report, metadata

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
    
    # 更新latest链接
    latest_txt = REPORTS_DIR / "latest.txt"
    latest_json = REPORTS_DIR / "latest.json"
    
    try:
        if latest_txt.exists():
            latest_txt.unlink()
        if latest_json.exists():
            latest_json.unlink()
        latest_txt.symlink_to(txt_path.name)
        latest_json.symlink_to(json_path.name)
    except:
        pass
    
    return str(txt_path), str(json_path)

# ========== HTTP API ==========

class ReportAPIHandler(BaseHTTPRequestHandler):
    """HTTP请求处理"""
    
    def log_message(self, format, *args):
        pass  # 禁用默认日志
    
    def send_json(self, data, status=200):
        """发送JSON响应"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        """处理GET请求"""
        path = self.path.strip('/')
        
        if path == '' or path == 'index':
            # 首页 - 显示状态
            health = get_system_health()
            services = get_service_status()
            alert_stats = get_alert_stats(24)
            trend = get_trend_analysis()
            
            self.send_json({
                "service": "Auto Report API",
                "version": "2.0",
                "port": PORT,
                "status": "running",
                "health": health,
                "services_running": sum(1 for s in services.values() if s.get('status') == 'running'),
                "services_total": len(services),
                "alerts_24h": alert_stats.get('total', 0),
                "health_score": trend['health_score'],
                "endpoints": {
                    "/": "This info",
                    "/health": "System health",
                    "/services": "Service status",
                    "/alerts": "Alert statistics",
                    "/trend": "Trend analysis",
                    "/report": "Generate and get daily report",
                    "/reports": "List recent reports"
                }
            })
        
        elif path == 'health':
            self.send_json(get_system_health())
        
        elif path == 'services':
            self.send_json(get_service_status())
        
        elif path == 'alerts':
            self.send_json(get_alert_stats(24))
        
        elif path == 'trend':
            self.send_json(get_trend_analysis())
        
        elif path == 'report':
            # 生成并返回报告
            report_text, metadata = generate_daily_report()
            txt_path, json_path = save_report(report_text, metadata, "daily")
            self.send_json({
                "success": True,
                "report": report_text,
                "saved_to": txt_path
            })
        
        elif path == 'reports':
            # 列出最近报告
            reports = []
            for f in sorted(REPORTS_DIR.glob("daily_*.txt"), reverse=True)[:10]:
                reports.append({
                    "name": f.name,
                    "size": f.stat().st_size,
                    "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                })
            self.send_json({"reports": reports})
        
        elif path.startswith('report/'):
            # 获取特定报告
            filename = path.split('/')[-1]
            report_path = REPORTS_DIR / filename
            if report_path.exists():
                with open(report_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.send_json({"content": content})
            else:
                self.send_json({"error": "Report not found"}, 404)
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        """处理POST请求"""
        path = self.path.strip('/')
        
        if path == 'generate':
            # 生成报告
            report_text, metadata = generate_daily_report()
            txt_path, json_path = save_report(report_text, metadata, "daily")
            self.send_json({
                "success": True,
                "timestamp": metadata['timestamp'],
                "txt_path": txt_path,
                "json_path": json_path
            })
        else:
            self.send_json({"error": "Not found"}, 404)


def start_server():
    """启动HTTP服务器"""
    server = HTTPServer(('0.0.0.0', PORT), ReportAPIHandler)
    print(f"📊 Auto Report API Server running on port {PORT}")
    print(f"   - Health: http://localhost:{PORT}/health")
    print(f"   - Services: http://localhost:{PORT}/services")
    print(f"   - Alerts: http://localhost:{PORT}/alerts")
    print(f"   - Trend: http://localhost:{PORT}/trend")
    print(f"   - Generate Report: http://localhost:{PORT}/report")
    server.serve_forever()


def main():
    global PORT
    import argparse
    parser = argparse.ArgumentParser(description='自动化报告API服务')
    parser.add_argument('--port', type=int, default=PORT, help='服务端口')
    args = parser.parse_args()
    
    PORT = args.port
    
    print("=" * 60)
    print("📊 自动化报告API服务")
    print("=" * 60)
    
    start_server()


if __name__ == "__main__":
    main()