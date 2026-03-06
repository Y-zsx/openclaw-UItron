#!/usr/bin/env python3
"""
智能决策引擎增强版 Dashboard
端口: 18256
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
import sqlite3

DB_PATH = "/root/.openclaw/workspace/ultron-workflow/decision_engine/enhanced_decisions.db"

html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>智能决策引擎增强版</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
            padding: 20px;
        }
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 { font-size: 28px; }
        .version { background: #667eea; padding: 5px 15px; border-radius: 20px; font-size: 14px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            text-align: center;
        }
        .stat-value { font-size: 36px; font-weight: bold; margin: 10px 0; }
        .stat-label { font-size: 14px; opacity: 0.8; }
        .chart-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-box {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
        }
        .chart-box h3 { margin-bottom: 15px; font-size: 18px; }
        table {
            width: 100%;
            border-collapse: collapse;
            background: rgba(255,255,255,0.05);
            border-radius: 10px;
            overflow: hidden;
        }
        th, td { padding: 15px; text-align: left; border-bottom: 1px solid rgba(255,255,255,0.1); }
        th { background: rgba(255,255,255,0.1); font-weight: 600; }
        .high { color: #ff6b6b; }
        .medium { color: #feca57; }
        .low { color: #48dbfb; }
        .btn {
            background: #667eea;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            color: white;
            cursor: pointer;
            margin: 5px;
        }
        .btn:hover { background: #5568d3; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🧠 智能决策引擎增强版</h1>
        <span class="version">v3.0 - 第175世</span>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-label">总决策数</div>
            <div class="stat-value">{total_decisions}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">已执行决策</div>
            <div class="stat-value">{executed_decisions}</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">执行成功率</div>
            <div class="stat-value">{execution_rate}%</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">待处理建议</div>
            <div class="stat-value">{pending_suggestions}</div>
        </div>
    </div>
    
    <div class="chart-container">
        <div class="chart-box">
            <h3>📊 决策类型分布</h3>
            <canvas id="typeChart"></canvas>
        </div>
        <div class="chart-box">
            <h3>📈 置信度分布</h3>
            <canvas id="confidenceChart"></canvas>
        </div>
    </div>
    
    <div class="chart-box">
        <h3>📋 最近决策记录</h3>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>类型</th>
                    <th>决策</th>
                    <th>置信度</th>
                    <th>风险等级</th>
                    <th>执行状态</th>
                    <th>时间</th>
                </tr>
            </thead>
            <tbody>
                {decision_rows}
            </tbody>
        </table>
    </div>
    
    <div style="margin-top: 30px;">
        <button class="btn" onclick="location.reload()">🔄 刷新</button>
        <button class="btn" onclick="window.open('http://localhost:18255/api/optimize', '_blank')">🔧 生成优化建议</button>
    </div>

    <script>
        new Chart(document.getElementById('typeChart'), {{
            type: 'doughnut',
            data: {{
                labels: {type_labels},
                datasets: [{{
                    data: {type_data},
                    backgroundColor: ['#667eea', '#48dbfb', '#ff6b6b', '#feca57', '#1dd1a1']
                }}]
            }}
        }});
        
        new Chart(document.getElementById('confidenceChart'), {{
            type: 'bar',
            data: {{
                labels: ['高(>80%)', '中(50-80%)', '低(<50%)'],
                datasets: [{{
                    label: '决策数',
                    data: {confidence_data},
                    backgroundColor: ['#1dd1a1', '#feca57', '#ff6b6b']
                }}]
            }},
            options: {{ scales: {{ y: {{ beginAtZero: true }} }} }}
        }});
        
        setTimeout(() => location.reload(), 30000);
    </script>
</body>
</html>'''

def get_stats():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM decision_history")
    total = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM decision_history WHERE executed = 1")
    executed = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM optimization_suggestions WHERE accepted = 0")
    pending = c.fetchone()[0]
    
    c.execute("SELECT decision_type, COUNT(*) FROM decision_history GROUP BY decision_type")
    type_dist = c.fetchall()
    
    c.execute("""SELECT 
        CASE 
            WHEN confidence > 80 THEN 'high'
            WHEN confidence >= 50 THEN 'medium'
            ELSE 'low'
        END as level,
        COUNT(*) FROM decision_history GROUP BY level""")
    conf_dist = c.fetchall()
    
    c.execute("SELECT * FROM decision_history ORDER BY created_at DESC LIMIT 10")
    recent = c.fetchall()
    
    conn.close()
    
    return {
        "total": total,
        "executed": executed,
        "rate": round(executed/total*100, 1) if total > 0 else 0,
        "pending": pending,
        "type_dist": type_dist,
        "conf_dist": conf_dist,
        "recent": recent
    }

class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"service": "decision-enhanced-dashboard", "status": "ok"}).encode())
            return
        
        stats = get_stats()
        
        type_labels = json.dumps([t[0] for t in stats["type_dist"]] or ["无数据"])
        type_data = json.dumps([t[1] for t in stats["type_dist"]] or [0])
        
        conf_data = [0, 0, 0]
        for c in stats["conf_dist"]:
            if c[0] == "high": conf_data[0] = c[1]
            elif c[0] == "medium": conf_data[1] = c[1]
            else: conf_data[2] = c[1]
        confidence_data = json.dumps(conf_data)
        
        rows = []
        for r in stats["recent"]:
            level_class = "high" if r[4] >= 7 else "medium" if r[4] >= 4 else "low"
            exec_status = "✅" if r[5] else "⏳"
            rows.append(f'''<tr>
                <td>{r[0]}</td>
                <td>{r[1]}</td>
                <td>{r[3]}</td>
                <td>{r[4]}%</td>
                <td class="{level_class}">{r[4]}</td>
                <td>{exec_status}</td>
                <td>{r[7]}</td>
            </tr>''')
        
        html = html_template.format(
            total_decisions=stats["total"],
            executed_decisions=stats["executed"],
            execution_rate=stats["rate"],
            pending_suggestions=stats["pending"],
            type_labels=type_labels,
            type_data=type_data,
            confidence_data=confidence_data,
            decision_rows="".join(rows) if rows else "<tr><td colspan='7'>暂无决策记录</td></tr>"
        )
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode())

if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 18256), DashboardHandler)
    print("Decision Enhanced Dashboard running on port 18256")
    server.serve_forever()