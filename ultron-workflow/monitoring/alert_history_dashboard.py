#!/usr/bin/env python3
"""
告警历史展示Dashboard
端口: 18215
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import sqlite3

MONITORING_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
DB_FILE = MONITORING_DIR / "alert_integration.db"
ALERT_API = "http://localhost:18280"


class AlertHistoryDB:
    """告警历史数据库访问"""
    
    def __init__(self):
        pass
    
    def get_alert_history(self, limit=50, level=None, channel=None):
        """获取告警历史"""
        if not DB_FILE.exists():
            return []
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        query = "SELECT id, alert_id, level, message, channel, status, timestamp, response FROM alert_history"
        conditions = []
        params = []
        
        if level:
            conditions.append("level = ?")
            params.append(level)
        if channel:
            conditions.append("channel = ?")
            params.append(channel)
        
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        
        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)
        
        c.execute(query, params)
        rows = c.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            try:
                response = json.loads(row[7]) if row[7] else {}
            except:
                response = {}
            
            result.append({
                "id": row[0],
                "alert_id": row[1],
                "level": row[2],
                "message": row[3],
                "channel": row[4],
                "status": row[5],
                "timestamp": row[6],
                "response": response
            })
        
        return result
    
    def get_stats(self):
        """获取统计信息"""
        if not DB_FILE.exists():
            return {
                "total": 0,
                "by_level": {},
                "by_channel": {},
                "by_status": {}
            }
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 总数
        c.execute("SELECT COUNT(*) FROM alert_history")
        total = c.fetchone()[0]
        
        # 按级别统计
        c.execute("SELECT level, COUNT(*) FROM alert_history GROUP BY level")
        by_level = {r[0]: r[1] for r in c.fetchall()}
        
        # 按渠道统计
        c.execute("SELECT channel, COUNT(*) FROM alert_history GROUP BY channel")
        by_channel = {r[0]: r[1] for r in c.fetchall()}
        
        # 按状态统计
        c.execute("SELECT status, COUNT(*) FROM alert_history GROUP BY status")
        by_status = {r[0]: r[1] for r in c.fetchall()}
        
        conn.close()
        
        return {
            "total": total,
            "by_level": by_level,
            "by_channel": by_channel,
            "by_status": by_status
        }
    
    def get_recent_summary(self, hours=24):
        """获取最近N小时的摘要"""
        if not DB_FILE.exists():
            return []
        
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        c.execute('''SELECT 
            level, 
            message, 
            timestamp, 
            channel,
            status
            FROM alert_history 
            ORDER BY timestamp DESC 
            LIMIT 20''')
        
        rows = c.fetchall()
        conn.close()
        
        return [{
            "level": r[0],
            "message": r[1],
            "timestamp": r[2],
            "channel": r[3],
            "status": r[4]
        } for r in rows]


def generate_html(history_data, stats):
    """生成Dashboard HTML"""
    level_colors = {
        "info": "#3498db",
        "warning": "#f39c12", 
        "error": "#e74c3c",
        "critical": "#9b59b6"
    }
    
    status_colors = {
        "ok": "#27ae60",
        "error": "#e74c3c",
        "sent": "#3498db",
        "pending": "#f39c12"
    }
    
    rows = ""
    for item in history_data[:30]:
        level_color = level_colors.get(item["level"], "#95a5a6")
        status_color = status_colors.get(item["status"], "#95a5a6")
        
        ts = item.get("timestamp", "")
        if "T" in ts:
            ts = ts.replace("T", " ").split(".")[0]
        
        rows += f'''
        <tr>
            <td><span class="level-badge" style="background:{level_color}">{item["level"]}</span></td>
            <td>{item["message"]}</td>
            <td>{item["channel"]}</td>
            <td><span class="status-badge" style="background:{status_color}">{item["status"]}</span></td>
            <td>{ts}</td>
        </tr>'''
    
    # 统计卡片
    stats_cards = f'''
    <div class="stat-card">
        <div class="stat-value">{stats.get("total", 0)}</div>
        <div class="stat-label">总告警数</div>
    </div>'''
    
    for level, count in stats.get("by_level", {}).items():
        color = level_colors.get(level, "#95a5a6")
        stats_cards += f'''
    <div class="stat-card" style="border-left: 4px solid {color}">
        <div class="stat-value">{count}</div>
        <div class="stat-label">{level.upper()}</div>
    </div>'''
    
    html = f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>告警历史 - 奥创监控</title>
    <meta http-equiv="refresh" content="30">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #eee;
        }}
        .header {{
            background: rgba(0,0,0,0.3);
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}
        .header h1 {{ color: #00d4ff; font-size: 24px; }}
        .header .time {{ color: #888; font-size: 14px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
            gap: 15px;
            padding: 20px 30px;
        }}
        .stat-card {{
            background: rgba(255,255,255,0.05);
            padding: 20px;
            border-radius: 10px;
            text-align: center;
        }}
        .stat-value {{ font-size: 32px; font-weight: bold; color: #00d4ff; }}
        .stat-label {{ font-size: 12px; color: #888; margin-top: 5px; }}
        .container {{ padding: 20px 30px; }}
        .section-title {{
            font-size: 18px;
            margin-bottom: 15px;
            color: #00d4ff;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.03);
            border-radius: 10px;
            overflow: hidden;
        }}
        th, td {{ padding: 12px 15px; text-align: left; }}
        th {{
            background: rgba(0,212,255,0.1);
            color: #00d4ff;
            font-weight: 600;
            font-size: 13px;
        }}
        td {{ border-bottom: 1px solid rgba(255,255,255,0.05); font-size: 14px; }}
        tr:hover {{ background: rgba(255,255,255,0.03); }}
        .level-badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .status-badge {{
            padding: 3px 8px;
            border-radius: 4px;
            font-size: 11px;
        }}
        .empty {{
            text-align: center;
            padding: 40px;
            color: #666;
        }}
        .refresh-info {{
            text-align: center;
            padding: 15px;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🚨 告警历史</h1>
        <div class="time">最后更新: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    
    <div class="stats">
        {stats_cards}
    </div>
    
    <div class="container">
        <div class="section-title">📋 最近告警</div>
        <table>
            <thead>
                <tr>
                    <th>级别</th>
                    <th>消息</th>
                    <th>渠道</th>
                    <th>状态</th>
                    <th>时间</th>
                </tr>
            </thead>
            <tbody>
                {rows if rows else '<tr><td colspan="5" class="empty">暂无告警记录</td></tr>'}
            </tbody>
        </table>
        <div class="refresh-info">每30秒自动刷新</div>
    </div>
</body>
</html>'''
    return html


class AlertHistoryHandler(BaseHTTPRequestHandler):
    """API处理器"""
    
    db = AlertHistoryDB()
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
    
    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/health' or path == '/':
            self.send_json(200, {
                "status": "ok",
                "service": "alert-history-dashboard",
                "port": 18215,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/api/history':
            limit = int(urllib.parse.parse_qs(parsed.query).get('limit', [50])[0])
            level = urllib.parse.parse_qs(parsed.query).get('level', [None])[0]
            channel = urllib.parse.parse_qs(parsed.query).get('channel', [None])[0]
            
            history = self.db.get_alert_history(limit, level, channel)
            self.send_json(200, {"history": history, "count": len(history)})
        
        elif path == '/api/stats':
            stats = self.db.get_stats()
            self.send_json(200, stats)
        
        elif path == '/api/recent':
            recent = self.db.get_recent_summary(24)
            self.send_json(200, {"recent": recent})
        
        elif path == '/dashboard' or path == '/':
            history = self.db.get_alert_history(30)
            stats = self.db.get_stats()
            html = generate_html(history, stats)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))
        
        else:
            # 默认返回dashboard
            history = self.db.get_alert_history(30)
            stats = self.db.get_stats()
            html = generate_html(history, stats)
            
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(html.encode('utf-8'))


def start_server(port=18215):
    server = HTTPServer(('0.0.0.0', port), AlertHistoryHandler)
    print(f"🚨 告警历史Dashboard启动成功")
    print(f"   端口: {port}")
    print(f"   端点:")
    print(f"   - GET  /health        健康检查")
    print(f"   - GET  /api/history   告警历史API")
    print(f"   - GET  /api/stats     统计信息")
    print(f"   - GET  /api/recent    最近告警")
    print(f"   - GET  /dashboard     Dashboard页面")
    print(f"\n监听中...")
    server.serve_forever()


if __name__ == "__main__":
    start_server()