#!/usr/bin/env python3
"""
告警历史数据增强服务
提供更丰富的告警统计和分析功能
端口: 18216
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import defaultdict

app = Flask(__name__)

DB_FILE = "/root/.openclaw/workspace/ultron/data/alerts.db"

def init_db():
    """初始化数据库"""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        level TEXT NOT NULL,
        channel TEXT NOT NULL,
        status TEXT NOT NULL,
        message TEXT,
        service TEXT,
        metric TEXT,
        value REAL,
        threshold REAL
    )''')
    conn.commit()
    conn.close()

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/api/stats/enhanced', methods=['GET'])
def enhanced_stats():
    """增强统计数据"""
    conn = get_db()
    c = conn.cursor()
    
    # 基础统计
    c.execute("SELECT COUNT(*) FROM alerts")
    total = c.fetchone()[0]
    
    # 按级别统计
    c.execute("SELECT level, COUNT(*) FROM alerts GROUP BY level")
    by_level = {row[0]: row[1] for row in c.fetchall()}
    
    # 按渠道统计
    c.execute("SELECT channel, COUNT(*) FROM alerts GROUP BY channel")
    by_channel = {row[0]: row[1] for row in c.fetchall()}
    
    # 按服务统计
    c.execute("SELECT service, COUNT(*) FROM alerts WHERE service IS NOT NULL GROUP BY service")
    by_service = {row[0]: row[1] for row in c.fetchall()}
    
    # 按指标统计
    c.execute("SELECT metric, COUNT(*) FROM alerts WHERE metric IS NOT NULL GROUP BY metric")
    by_metric = {row[0]: row[1] for row in c.fetchall()}
    
    # 今日统计
    today = datetime.now().strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ?", (f"{today}%",))
    today_count = c.fetchone()[0]
    
    # 昨日统计
    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ?", (f"{yesterday}%",))
    yesterday_count = c.fetchone()[0]
    
    # 本周统计
    week_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp >= ?", (week_ago,))
    week_count = c.fetchone()[0]
    
    # 成功率
    c.execute("SELECT COUNT(*) FROM alerts WHERE status = 'ok'")
    ok_count = c.fetchone()[0]
    success_rate = (ok_count / total * 100) if total > 0 else 100
    
    # 按小时统计（过去24小时）
    hour_stats = {}
    for i in range(24):
        hour = (datetime.now() - timedelta(hours=i)).strftime('%Y-%m-%d %H:00:00')
        hour_key = hour[:13]
        c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ?", (f"{hour}%",))
        hour_stats[hour_key] = c.fetchone()[0]
    
    # 最近告警列表
    c.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT 10")
    recent = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return jsonify({
        "status": "ok",
        "summary": {
            "total": total,
            "today": today_count,
            "yesterday": yesterday_count,
            "this_week": week_count,
            "success_rate": round(success_rate, 2)
        },
        "by_level": by_level,
        "by_channel": by_channel,
        "by_service": by_service,
        "by_metric": by_metric,
        "hourly_stats": hour_stats,
        "recent": recent,
        "updated_at": datetime.now().isoformat()
    })

@app.route('/api/analysis/trends', methods=['GET'])
def trend_analysis():
    """趋势分析"""
    conn = get_db()
    c = conn.cursor()
    
    days = request.args.get('days', 7, type=int)
    trends = []
    
    for i in range(days):
        date = (datetime.now() - timedelta(days=i)).strftime('%Y-%m-%d')
        c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ?", (f"{date}%",))
        count = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ? AND level = 'critical'", (f"{date}%",))
        critical = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM alerts WHERE timestamp LIKE ? AND level = 'warning'", (f"{date}%",))
        warning = c.fetchone()[0]
        
        trends.append({
            "date": date,
            "total": count,
            "critical": critical,
            "warning": warning
        })
    
    conn.close()
    
    return jsonify({
        "status": "ok",
        "trends": trends,
        "period_days": days
    })

@app.route('/api/analysis/services', methods=['GET'])
def service_analysis():
    """服务分析"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""SELECT service, 
        COUNT(*) as total,
        SUM(CASE WHEN level = 'critical' THEN 1 ELSE 0 END) as critical,
        SUM(CASE WHEN level = 'warning' THEN 1 ELSE 0 END) as warning,
        AVG(CASE WHEN value IS NOT NULL THEN value ELSE 0 END) as avg_value
        FROM alerts 
        WHERE service IS NOT NULL 
        GROUP BY service
        ORDER BY total DESC""")
    
    services = []
    for row in c.fetchall():
        services.append({
            "service": row[0],
            "total": row[1],
            "critical": row[2],
            "warning": row[3],
            "avg_value": round(row[4], 2) if row[4] else 0
        })
    
    conn.close()
    
    return jsonify({
        "status": "ok",
        "services": services
    })

@app.route('/api/export', methods=['GET'])
def export_data():
    """导出数据"""
    conn = get_db()
    c = conn.cursor()
    
    format_type = request.args.get('format', 'json')
    limit = request.args.get('limit', 1000, type=int)
    
    c.execute("SELECT * FROM alerts ORDER BY timestamp DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    data = [dict(row) for row in rows]
    
    conn.close()
    
    if format_type == 'csv':
        if not data:
            return "No data", 204
        headers = data[0].keys()
        csv_lines = [",".join(headers)]
        for row in data:
            csv_lines.append(",".join(str(row.get(h, "")) for h in headers))
        return "\n".join(csv_lines), 200, {'Content-Type': 'text/csv'}
    
    return jsonify({
        "status": "ok",
        "count": len(data),
        "data": data
    })

@app.route('/api/alerts', methods=['POST'])
def add_alert():
    """添加告警记录"""
    data = request.get_json()
    conn = get_db()
    c = conn.cursor()
    
    c.execute("""INSERT INTO alerts 
        (timestamp, level, channel, status, message, service, metric, value, threshold)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            data.get('timestamp', datetime.now().isoformat()),
            data.get('level', 'info'),
            data.get('channel', 'console'),
            data.get('status', 'ok'),
            data.get('message', ''),
            data.get('service'),
            data.get('metric'),
            data.get('value'),
            data.get('threshold')
        ))
    
    conn.commit()
    alert_id = c.lastrowid
    conn.close()
    
    return jsonify({
        "status": "ok",
        "alert_id": alert_id
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "alert-history-enhanced", "port": 18216})

if __name__ == '__main__':
    init_db()
    print("启动告警历史数据增强服务...")
    print(f"端口: 18216")
    print(f"数据库: {DB_FILE}")
    app.run(host='0.0.0.0', port=18216, debug=False)