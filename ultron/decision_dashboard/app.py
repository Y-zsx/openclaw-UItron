#!/usr/bin/env python3
"""
决策可视化与统计分析Dashboard
为决策引擎提供可视化界面，展示决策历史、风险趋势、行动效果
"""

from flask import Flask, jsonify, render_template_string
import sqlite3
import os
from datetime import datetime, timedelta
from collections import defaultdict

app = Flask(__name__)
DB_PATH = "/root/.openclaw/workspace/ultron/decision_engine/decisions.db"

def get_db_connection():
    """获取数据库连接"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """初始化数据库表"""
    conn = get_db_connection()
    c = conn.cursor()
    
    # 创建决策表
    c.execute('''CREATE TABLE IF NOT EXISTS decisions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        context TEXT NOT NULL,
        decision TEXT NOT NULL,
        confidence REAL,
        risk_level INTEGER,
        auto_approved BOOLEAN,
        executed BOOLEAN,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 创建风险评估表
    c.execute('''CREATE TABLE IF NOT EXISTS risk_assessments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id INTEGER,
        system_impact REAL,
        data_loss REAL,
        service_outage REAL,
        recovery_difficulty REAL,
        overall_risk REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (decision_id) REFERENCES decisions(id)
    )''')
    
    # 创建行动记录表
    c.execute('''CREATE TABLE IF NOT EXISTS actions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_id INTEGER,
        action_type TEXT NOT NULL,
        target TEXT,
        command TEXT,
        status TEXT,
        result TEXT,
        executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (decision_id) REFERENCES decisions(id)
    )''')
    
    conn.commit()
    conn.close()

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>决策中心 Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }
        .header {
            background: rgba(0,0,0,0.3);
            padding: 20px 40px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        .header h1 { font-size: 28px; font-weight: 300; }
        .header .subtitle { color: #888; margin-top: 5px; }
        .container { padding: 30px 40px; }
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .stat-card .label { color: #888; font-size: 14px; }
        .stat-card .value { 
            font-size: 36px; 
            font-weight: bold; 
            margin-top: 10px;
            background: linear-gradient(90deg, #00d2ff, #3a7bd5);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        .charts-grid {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        .chart-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .chart-card h3 { margin-bottom: 20px; font-weight: 400; }
        .chart-card canvas { max-height: 250px; }
        .recent-decisions {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.1);
        }
        .recent-decisions h3 { margin-bottom: 20px; font-weight: 400; }
        table { width: 100%; border-collapse: collapse; }
        th, td { 
            padding: 12px; 
            text-align: left; 
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        th { color: #888; font-weight: 400; font-size: 14px; }
        .risk-high { color: #ff6b6b; }
        .risk-medium { color: #ffd93d; }
        .risk-low { color: #6bcb77; }
        .status-badge {
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
        }
        .status-success { background: rgba(107,203,119,0.2); color: #6bcb77; }
        .status-pending { background: rgba(255,217,61,0.2); color: #ffd93d; }
        .auto-badge {
            background: rgba(0,210,255,0.2);
            color: #00d2ff;
            padding: 2px 8px;
            border-radius: 10px;
            font-size: 11px;
            margin-left: 8px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🎯 决策中心 Dashboard</h1>
        <div class="subtitle">智能决策与自主行动系统</div>
    </div>
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">总决策数</div>
                <div class="value" id="total-decisions">-</div>
            </div>
            <div class="stat-card">
                <div class="label">今日决策</div>
                <div class="value" id="today-decisions">-</div>
            </div>
            <div class="stat-card">
                <div class="label">自动审批</div>
                <div class="value" id="auto-approved">-</div>
            </div>
            <div class="stat-card">
                <div class="label">已执行行动</div>
                <div class="value" id="executed-actions">-</div>
            </div>
        </div>
        
        <div class="charts-grid">
            <div class="chart-card">
                <h3>📊 决策趋势 (最近7天)</h3>
                <canvas id="decisionTrend"></canvas>
            </div>
            <div class="chart-card">
                <h3>⚠️ 风险等级分布</h3>
                <canvas id="riskDistribution"></canvas>
            </div>
            <div class="chart-card">
                <h3>🎯 行动类型分布</h3>
                <canvas id="actionType"></canvas>
            </div>
            <div class="chart-card">
                <h3>📈 风险趋势 (最近7天)</h3>
                <canvas id="riskTrend"></canvas>
            </div>
        </div>
        
        <div class="recent-decisions">
            <h3>📋 最近决策记录</h3>
            <table>
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>场景</th>
                        <th>决策</th>
                        <th>置信度</th>
                        <th>风险</th>
                        <th>自动审批</th>
                        <th>状态</th>
                        <th>时间</th>
                    </tr>
                </thead>
                <tbody id="decisions-table">
                </tbody>
            </table>
        </div>
    </div>
    
    <script>
        const stats = {{ stats | tojson }};
        const trendData = {{ trend_data | tojson }};
        const riskData = {{ risk_data | tojson }};
        const actionData = {{ action_data | tojson }};
        const recentDecisions = {{ recent_decisions | tojson }};
        
        // 更新统计卡片
        document.getElementById('total-decisions').textContent = stats.total;
        document.getElementById('today-decisions').textContent = stats.today;
        document.getElementById('auto-approved').textContent = stats.auto_approved;
        document.getElementById('executed-actions').textContent = stats.executed;
        
        // 决策趋势图
        new Chart(document.getElementById('decisionTrend'), {
            type: 'line',
            data: {
                labels: trendData.labels,
                datasets: [{
                    label: '决策数',
                    data: trendData.values,
                    borderColor: '#00d2ff',
                    backgroundColor: 'rgba(0,210,255,0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' } }
                }
            }
        });
        
        // 风险分布饼图
        new Chart(document.getElementById('riskDistribution'), {
            type: 'doughnut',
            data: {
                labels: ['低风险', '中风险', '高风险'],
                datasets: [{
                    data: [riskData.low, riskData.medium, riskData.high],
                    backgroundColor: ['#6bcb77', '#ffd93d', '#ff6b6b']
                }]
            },
            options: {
                plugins: { legend: { position: 'bottom' } }
            }
        });
        
        // 行动类型分布
        new Chart(document.getElementById('actionType'), {
            type: 'bar',
            data: {
                labels: Object.keys(actionData),
                datasets: [{
                    label: '次数',
                    data: Object.values(actionData),
                    backgroundColor: '#3a7bd5'
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' } }
                }
            }
        });
        
        // 风险趋势图
        new Chart(document.getElementById('riskTrend'), {
            type: 'line',
            data: {
                labels: trendData.labels,
                datasets: [{
                    label: '平均风险',
                    data: riskData.trend,
                    borderColor: '#ff6b6b',
                    backgroundColor: 'rgba(255,107,107,0.1)',
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                plugins: { legend: { display: false } },
                scales: {
                    x: { grid: { color: 'rgba(255,255,255,0.1)' } },
                    y: { grid: { color: 'rgba(255,255,255,0.1)' }, min: 0, max: 10 }
                }
            }
        });
        
        // 渲染最近决策表格
        const tbody = document.getElementById('decisions-table');
        recentDecisions.forEach(d => {
            const riskClass = d.risk_level >= 7 ? 'risk-high' : d.risk_level >= 4 ? 'risk-medium' : 'risk-low';
            const statusClass = d.executed ? 'status-success' : 'status-pending';
            const statusText = d.executed ? '已执行' : '待执行';
            const autoBadge = d.auto_approved ? '<span class="auto-badge">AUTO</span>' : '';
            tbody.innerHTML += `
                <tr>
                    <td>${d.id}</td>
                    <td>${d.context.substring(0, 30)}...</td>
                    <td>${d.decision}</td>
                    <td>${(d.confidence * 100).toFixed(0)}%</td>
                    <td class="${riskClass}">${d.risk_level}</td>
                    <td>${autoBadge}</td>
                    <td><span class="status-badge ${statusClass}">${statusText}</span></td>
                    <td>${new Date(d.created_at).toLocaleString()}</td>
                </tr>
            `;
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    """主页面"""
    conn = get_db_connection()
    
    # 统计信息
    stats = get_stats(conn)
    trend_data = get_trend_data(conn)
    risk_data = get_risk_data(conn)
    action_data = get_action_data(conn)
    recent_decisions = get_recent_decisions(conn)
    
    conn.close()
    
    return render_template_string(HTML_TEMPLATE,
        stats=stats,
        trend_data=trend_data,
        risk_data=risk_data,
        action_data=action_data,
        recent_decisions=recent_decisions
    )

def get_stats(conn):
    """获取统计信息"""
    c = conn.cursor()
    
    # 总决策数
    c.execute("SELECT COUNT(*) FROM decisions")
    total = c.fetchone()[0]
    
    # 今日决策
    today = datetime.now().date()
    c.execute("SELECT COUNT(*) FROM decisions WHERE DATE(created_at) = ?", (today,))
    today_count = c.fetchone()[0]
    
    # 自动审批
    c.execute("SELECT COUNT(*) FROM decisions WHERE auto_approved = 1")
    auto_approved = c.fetchone()[0]
    
    # 已执行行动
    c.execute("SELECT COUNT(*) FROM actions WHERE status = 'success'")
    executed = c.fetchone()[0]
    
    return {
        'total': total,
        'today': today_count,
        'auto_approved': auto_approved,
        'executed': executed
    }

def get_trend_data(conn):
    """获取决策趋势数据"""
    c = conn.cursor()
    
    labels = []
    values = []
    
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        labels.append(date.strftime('%m/%d'))
        c.execute("SELECT COUNT(*) FROM decisions WHERE DATE(created_at) = ?", (date,))
        values.append(c.fetchone()[0])
    
    return {'labels': labels, 'values': values}

def get_risk_data(conn):
    """获取风险数据"""
    c = conn.cursor()
    
    # 风险等级分布
    c.execute("SELECT risk_level, COUNT(*) FROM decisions GROUP BY risk_level")
    risk_dist = {0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0}
    for row in c.fetchall():
        risk_dist[row[0]] = row[1]
    
    low = sum(risk_dist[i] for i in range(0, 4))
    medium = sum(risk_dist[i] for i in range(4, 7))
    high = sum(risk_dist[i] for i in range(7, 11))
    
    # 风险趋势
    trend = []
    for i in range(6, -1, -1):
        date = (datetime.now() - timedelta(days=i)).date()
        c.execute("SELECT AVG(risk_level) FROM decisions WHERE DATE(created_at) = ?", (date,))
        avg = c.fetchone()[0] or 0
        trend.append(round(avg, 1))
    
    return {'low': low, 'medium': medium, 'high': high, 'trend': trend}

def get_action_data(conn):
    """获取行动类型数据"""
    c = conn.cursor()
    c.execute("SELECT action_type, COUNT(*) FROM actions GROUP BY action_type")
    return {row[0]: row[1] for row in c.fetchall()}

def get_recent_decisions(conn):
    """获取最近决策"""
    c = conn.cursor()
    c.execute("""
        SELECT id, context, decision, confidence, risk_level, auto_approved, executed, created_at 
        FROM decisions 
        ORDER BY created_at DESC 
        LIMIT 10
    """)
    return [dict(row) for row in c.fetchall()]

@app.route('/api/stats')
def api_stats():
    """API: 统计信息"""
    conn = get_db_connection()
    stats = get_stats(conn)
    conn.close()
    return jsonify(stats)

@app.route('/api/decisions')
def api_decisions():
    """API: 决策列表"""
    conn = get_db_connection()
    decisions = get_recent_decisions(conn)
    conn.close()
    return jsonify(decisions)

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'decision-dashboard'})

if __name__ == '__main__':
    init_db()
    print("🎯 决策Dashboard启动: http://0.0.0.0:18121")
    app.run(host='0.0.0.0', port=18121, debug=False)