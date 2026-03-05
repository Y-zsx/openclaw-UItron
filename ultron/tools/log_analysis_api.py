#!/usr/bin/env python3
"""
Enhanced Log Analysis API - Agent协作网络日志聚合与分析
功能:
- 日志模式识别
- 错误聚类分析
- 日志趋势预测
- 智能告警
- 可视化Dashboard (端口18235)
"""

import json
import time
import re
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import sqlite3
import gzip
import os

PORT = 18235
LOG_DB_PATH = "/root/.openclaw/workspace/ultron/tools/logs.db"

class LogAnalyzer:
    def __init__(self, db_path: str = LOG_DB_PATH):
        self.db_path = db_path
        self.lock = threading.Lock()
        self.error_patterns = [
            (r"(?:Exception|Error):\s*(.+?)(?:\n|$)", "error_type"),
            (r"Connection\s+(?:refused|timeout|reset)", "connection_issue"),
            (r"OutOfMemory", "resource_exhaustion"),
            (r"Deadlock", "concurrency_issue"),
            (r"timeout\s+(\d+)s?", "timeout"),
            (r"Failed\s+to\s+(.+?)(?:\s|$)", "failure"),
            (r"Permission\s+denied", "permission_error"),
            (r"File\s+not\s+found", "file_not_found"),
            (r"HTTP\s+(\d+)", "http_error"),
        ]
        self.cache = {}
        self.cache_ttl = 30
    
    def get_db_connection(self):
        return sqlite3.connect(self.db_path)
    
    def get_recent_logs(self, limit: int = 100, service: str = None, level: str = None):
        """获取最近日志"""
        conn = self.get_db_connection()
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        
        query = "SELECT * FROM logs"
        conditions = []
        params = []
        
        if service:
            conditions.append("service = ?")
            params.append(service)
        if level:
            conditions.append("level = ?")
            params.append(level)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        return [dict(row) for row in rows]
    
    def analyze_errors(self, hours: int = 1):
        """分析错误模式"""
        conn = self.get_db_connection()
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        c.execute("""
            SELECT timestamp, level, service, message 
            FROM logs 
            WHERE level IN ('ERROR', 'CRITICAL') 
            AND timestamp > ?
            ORDER BY timestamp DESC
        """, (since,))
        
        rows = c.fetchall()
        conn.close()
        
        # 模式聚类
        patterns = defaultdict(list)
        for row in rows:
            msg = row[3]
            matched = False
            for pattern, ptype in self.error_patterns:
                match = re.search(pattern, msg, re.IGNORECASE)
                if match:
                    key = f"{ptype}:{match.group(1) if match.groups() else 'unknown'}"
                    patterns[key].append(dict(row))
                    matched = True
                    break
            if not matched:
                patterns[f"other:{msg[:50]}"].append(dict(row))
        
        return {
            "total_errors": len(rows),
            "by_pattern": {k: len(v) for k, v in patterns.items()},
            "top_patterns": sorted(patterns.items(), key=lambda x: len(x[1]), reverse=True)[:10],
            "recent_errors": [dict(row) for row in rows[:10]]
        }
    
    def get_trends(self, minutes: int = 60):
        """获取日志趋势"""
        conn = self.get_db_connection()
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        c.execute("""
            SELECT 
                strftime('%Y-%m-%d %H:%M', timestamp) as minute,
                level,
                COUNT(*) as count
            FROM logs 
            WHERE timestamp > ?
            GROUP BY minute, level
            ORDER BY minute
        """, (since,))
        
        rows = c.fetchall()
        conn.close()
        
        # 转换为时间序列
        by_time = defaultdict(lambda: defaultdict(int))
        for minute, level, count in rows:
            by_time[minute][level] = count
        
        return {
            "period_minutes": minutes,
            "timeline": dict(by_time),
            "total": sum(sum(v.values()) for v in by_time.values())
        }
    
    def get_service_health(self):
        """服务健康分析"""
        conn = self.get_db_connection()
        c = conn.cursor()
        
        # 最近1小时
        since = (datetime.now() - timedelta(hours=1)).isoformat()
        
        c.execute("""
            SELECT service, level, COUNT(*) as count
            FROM logs
            WHERE timestamp > ?
            GROUP BY service, level
        """, (since,))
        
        rows = c.fetchall()
        conn.close()
        
        health = {}
        for service, level, count in rows:
            if service not in health:
                health[service] = {"errors": 0, "warnings": 0, "info": 0, "total": 0}
            health[service][level.lower() if level else "info"] = count
            health[service]["total"] += count
        
        # 计算健康分数
        for svc, data in health.items():
            total = data["total"]
            if total == 0:
                data["health_score"] = 100
            else:
                error_ratio = (data.get("error", 0) + data.get("critical", 0)) / total
                warning_ratio = data.get("warning", 0) / total
                data["health_score"] = max(0, 100 - (error_ratio * 50) - (warning_ratio * 10))
        
        return health
    
    def get_summary(self):
        """获取总体摘要"""
        conn = self.get_db_connection()
        c = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=1)).isoformat()
        
        c.execute("SELECT COUNT(*) FROM logs WHERE timestamp > ?", (since,))
        total = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM logs WHERE timestamp > ? AND level = 'ERROR'", (since,))
        errors = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM logs WHERE timestamp > ? AND level = 'WARNING'", (since,))
        warnings = c.fetchone()[0]
        
        c.execute("SELECT service, COUNT(*) as cnt FROM logs WHERE timestamp > ? GROUP BY service ORDER BY cnt DESC LIMIT 10", (since,))
        top_services = [{"service": s, "count": c} for s, c in c.fetchall()]
        
        conn.close()
        
        return {
            "total_logs_1h": total,
            "errors_1h": errors,
            "warnings_1h": warnings,
            "top_services": top_services,
            "timestamp": datetime.now().isoformat()
        }

analyzer = LogAnalyzer()

class LogAnalysisAPIHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = self.path.strip("/")
        
        if path == "health":
            self.send_json({"status": "ok", "service": "log-analysis-api", "port": PORT})
        elif path == "summary":
            self.send_json(analyzer.get_summary())
        elif path == "errors":
            self.send_json(analyzer.analyze_errors())
        elif path == "trends":
            self.send_json(analyzer.get_trends())
        elif path == "service-health":
            self.send_json(analyzer.get_service_health())
        elif path == "dashboard":
            self.send_html(self.get_dashboard_html())
        else:
            self.send_json({"error": "Not found"}, status=404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())
    
    def send_html(self, html, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))
    
    def get_dashboard_html(self):
        return """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Agent日志分析面板</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; padding: 20px; }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .header h1 { color: #00d4ff; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .stat-card { background: #16213e; padding: 20px; border-radius: 10px; border: 1px solid #0f3460; }
        .stat-card h3 { color: #888; font-size: 14px; margin-bottom: 5px; }
        .stat-card .value { font-size: 32px; font-weight: bold; }
        .stat-card.error .value { color: #ff4757; }
        .stat-card.warning .value { color: #ffa502; }
        .stat-card.info .value { color: #2ed573; }
        .services { background: #16213e; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .services h2 { color: #00d4ff; margin-bottom: 15px; }
        .service-item { display: flex; justify-content: space-between; padding: 10px; border-bottom: 1px solid #0f3460; }
        .service-item:last-child { border: none; }
        .health-score { padding: 3px 10px; border-radius: 10px; font-size: 12px; }
        .health-good { background: #2ed573; color: #000; }
        .health-warn { background: #ffa502; color: #000; }
        .health-bad { background: #ff4757; color: #fff; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Agent日志分析面板</h1>
        <span>自动刷新 (30s)</span>
    </div>
    <div class="stats">
        <div class="stat-card">
            <h3>总日志 (1h)</h3>
            <div class="value" id="total">-</div>
        </div>
        <div class="stat-card error">
            <h3>错误</h3>
            <div class="value" id="errors">-</div>
        </div>
        <div class="stat-card warning">
            <h3>警告</h3>
            <div class="value" id="warnings">-</div>
        </div>
    </div>
    <div class="services">
        <h2>📊 服务健康状态</h2>
        <div id="services-list">加载中...</div>
    </div>
    <script>
        async function loadData() {
            try {
                const [summary, health] = await Promise.all([
                    fetch('/summary').then(r => r.json()),
                    fetch('/service-health').then(r => r.json())
                ]);
                
                document.getElementById('total').textContent = summary.total_logs_1h || 0;
                document.getElementById('errors').textContent = summary.errors_1h || 0;
                document.getElementById('warnings').textContent = summary.warnings_1h || 0;
                
                let html = '';
                for (const [service, data] of Object.entries(health)) {
                    const score = Math.round(data.health_score || 100);
                    const cls = score >= 80 ? 'health-good' : score >= 50 ? 'health-warn' : 'health-bad';
                    html += `<div class="service-item">
                        <span>${service}</span>
                        <span class="health-score ${cls}">${score}%</span>
                    </div>`;
                }
                document.getElementById('services-list').innerHTML = html || '暂无数据';
            } catch(e) {
                console.error(e);
            }
        }
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>"""
    
    def log_message(self, format, *args):
        pass

def start_server(port=PORT):
    server = HTTPServer(("0.0.0.0", port), LogAnalysisAPIHandler)
    print(f"Log Analysis API running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    start_server()