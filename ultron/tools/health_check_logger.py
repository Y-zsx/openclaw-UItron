#!/usr/bin/env python3
"""
健康检查日志存储系统
将健康检查结果存储到SQLite数据库，支持历史查询和趋势分析
"""
import sqlite3
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

DB_PATH = Path("/root/.openclaw/workspace/ultron/data/health_check_logs.db")

def init_db():
    """初始化数据库"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    # 健康检查记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_checks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            service_name TEXT NOT NULL,
            port INTEGER,
            port_status INTEGER,
            http_status INTEGER,
            latency_ms REAL,
            status TEXT,
            details TEXT
        )
    ''')
    
    # 服务可用性汇总表（每小时）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS hourly_availability (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            hour TEXT NOT NULL,
            service_name TEXT NOT NULL,
            total_checks INTEGER,
            healthy_checks INTEGER,
            avg_latency_ms REAL,
            uptime_percent REAL,
            UNIQUE(hour, service_name)
        )
    ''')
    
    # 告警记录表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            service_name TEXT NOT NULL,
            alert_type TEXT,
            message TEXT,
            resolved INTEGER DEFAULT 0,
            resolved_at TEXT
        )
    ''')
    
    # 创建索引
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hc_timestamp ON health_checks(timestamp)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_hc_service ON health_checks(service_name)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_ha_timestamp ON health_alerts(timestamp)')
    
    conn.commit()
    return conn

def log_health_check(service_name, port, port_status, http_status, latency_ms, details=None):
    """记录健康检查结果"""
    conn = init_db()
    cursor = conn.cursor()
    
    timestamp = datetime.now().isoformat()
    status = "healthy" if port_status and http_status == 200 else "unhealthy"
    
    cursor.execute('''
        INSERT INTO health_checks 
        (timestamp, service_name, port, port_status, http_status, latency_ms, status, details)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (timestamp, service_name, port, port_status, http_status, latency_ms, status, json.dumps(details) if details else None))
    
    conn.commit()
    conn.close()

def get_service_availability(service_name, hours=24):
    """获取服务可用性统计"""
    conn = init_db()
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency,
            MIN(latency_ms) as min_latency,
            MAX(latency_ms) as max_latency
        FROM health_checks
        WHERE service_name = ? AND timestamp >= ?
    ''', (service_name, since))
    
    row = cursor.fetchone()
    conn.close()
    
    if row and row[0] > 0:
        total, healthy, avg_lat, min_lat, max_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        return {
            "service": service_name,
            "total_checks": total,
            "healthy_checks": healthy,
            "unhealthy_checks": total - healthy,
            "uptime_percent": round(uptime, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0,
            "min_latency_ms": round(min_lat, 2) if min_lat else 0,
            "max_latency_ms": round(max_lat, 2) if max_lat else 0
        }
    return None

def get_all_services_availability(hours=24):
    """获取所有服务的可用性统计"""
    conn = init_db()
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT 
            service_name,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency
        FROM health_checks
        WHERE timestamp >= ?
        GROUP BY service_name
    ''', (since,))
    
    results = []
    for row in cursor.fetchall():
        service, total, healthy, avg_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        results.append({
            "service": service,
            "total_checks": total,
            "healthy_checks": healthy,
            "uptime_percent": round(uptime, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0
        })
    
    conn.close()
    return results

def get_health_trend(service_name, days=7):
    """获取健康趋势数据（用于图表）"""
    conn = init_db()
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(days=days)).isoformat()
    
    # 按小时聚合
    cursor.execute('''
        SELECT 
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency
        FROM health_checks
        WHERE service_name = ? AND timestamp >= ?
        GROUP BY hour
        ORDER BY hour
    ''', (service_name, since))
    
    trend = []
    for row in cursor.fetchall():
        hour, total, healthy, avg_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        trend.append({
            "hour": hour,
            "uptime_percent": round(uptime, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0
        })
    
    conn.close()
    return trend

def get_unhealthy_events(hours=24):
    """获取不健康事件"""
    conn = init_db()
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT timestamp, service_name, port_status, http_status, latency_ms, details
        FROM health_checks
        WHERE status = 'unhealthy' AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT 50
    ''', (since,))
    
    events = []
    for row in cursor.fetchall():
        events.append({
            "timestamp": row[0],
            "service": row[1],
            "port_status": row[2],
            "http_status": row[3],
            "latency_ms": row[4],
            "details": json.loads(row[5]) if row[5] else {}
        })
    
    conn.close()
    return events

def log_alert(service_name, alert_type, message):
    """记录健康告警"""
    conn = init_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO health_alerts (timestamp, service_name, alert_type, message)
        VALUES (?, ?, ?, ?)
    ''', (datetime.now().isoformat(), service_name, alert_type, message))
    
    conn.commit()
    conn.close()

def resolve_alert(alert_id):
    """解决告警"""
    conn = init_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        UPDATE health_alerts 
        SET resolved = 1, resolved_at = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), alert_id))
    
    conn.commit()
    conn.close()

def get_active_alerts():
    """获取活跃告警"""
    conn = init_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, timestamp, service_name, alert_type, message
        FROM health_alerts
        WHERE resolved = 0
        ORDER BY timestamp DESC
    ''')
    
    alerts = []
    for row in cursor.fetchall():
        alerts.append({
            "id": row[0],
            "timestamp": row[1],
            "service": row[2],
            "type": row[3],
            "message": row[4]
        })
    
    conn.close()
    return alerts

def generate_health_summary(hours=24):
    """生成健康摘要报告"""
    availability = get_all_services_availability(hours)
    unhealthy_events = get_unhealthy_events(hours)
    active_alerts = get_active_alerts()
    
    total_services = len(availability)
    healthy_services = sum(1 for a in availability if a["uptime_percent"] >= 99)
    degraded_services = sum(1 for a in availability if 95 <= a["uptime_percent"] < 99)
    unhealthy_services = sum(1 for a in availability if a["uptime_percent"] < 95)
    
    overall_health_score = (healthy_services / total_services * 100) if total_services > 0 else 0
    
    return {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours,
        "total_services": total_services,
        "healthy_services": healthy_services,
        "degraded_services": degraded_services,
        "unhealthy_services": unhealthy_services,
        "overall_health_score": round(overall_health_score, 2),
        "services": availability,
        "recent_failures": len(unhealthy_events),
        "active_alerts": len(active_alerts)
    }

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='健康检查日志系统')
    parser.add_argument('--init', action='store_true', help='初始化数据库')
    parser.add_argument('--availability', action='store_true', help='查看可用性统计')
    parser.add_argument('--hours', type=int, default=24, help='统计小时数')
    parser.add_argument('--service', type=str, help='指定服务名')
    parser.add_argument('--summary', action='store_true', help='生成健康摘要')
    parser.add_argument('--trend', action='store_true', help='查看趋势数据')
    args = parser.parse_args()
    
    if args.init:
        init_db()
        print("✅ 数据库初始化完成")
    
    if args.availability:
        if args.service:
            result = get_service_availability(args.service, args.hours)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            results = get_all_services_availability(args.hours)
            print(json.dumps(results, indent=2, ensure_ascii=False))
    
    if args.summary:
        result = generate_health_summary(args.hours)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if args.trend and args.service:
        result = get_health_trend(args.service)
        print(json.dumps(result, indent=2, ensure_ascii=False))