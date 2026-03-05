#!/usr/bin/env python3
"""
多智能体协作网络 - 健康检查与监控仪表板
功能:
- Agent健康状态实时监控
- 协作网络拓扑可视化
- 性能指标聚合展示
- 告警状态面板
- 移动端自适应
API端口: 18100
"""

import json
import time
import os
import sqlite3
import psutil
import threading
from datetime import datetime, timedelta
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Optional, Any
from flask import Flask, jsonify, request, render_template_string, make_response
import urllib.request
import urllib.error

# 配置
app = Flask(__name__)
DB_PATH = Path(__file__).parent / "data" / "collab_health.db"
DB_PATH.parent.mkdir(exist_ok=True)

# 初始化数据库
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Agent健康状态表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS agent_health (
            agent_id TEXT PRIMARY KEY,
            agent_name TEXT NOT NULL,
            status TEXT DEFAULT 'unknown',
            health_score REAL DEFAULT 0,
            cpu_usage REAL DEFAULT 0,
            memory_usage REAL DEFAULT 0,
            task_success_rate REAL DEFAULT 0,
            avg_response_time REAL DEFAULT 0,
            last_heartbeat TEXT,
            checked_at TEXT NOT NULL
        )
    ''')
    
    # 协作会话健康表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS collab_sessions (
            session_id TEXT PRIMARY KEY,
            agent_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            success_rate REAL DEFAULT 0,
            avg_duration REAL DEFAULT 0,
            issues_count INTEGER DEFAULT 0,
            created_at TEXT,
            updated_at TEXT NOT NULL
        )
    ''')
    
    # 告警表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS health_alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            severity TEXT NOT NULL,
            source TEXT NOT NULL,
            message TEXT NOT NULL,
            details TEXT,
            acknowledged BOOLEAN DEFAULT 0,
            created_at TEXT NOT NULL,
            resolved_at TEXT
        )
    ''')
    
    # 系统健康指标
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS system_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_agents INTEGER,
            active_agents INTEGER,
            healthy_agents INTEGER,
            total_tasks INTEGER,
            success_rate REAL,
            avg_response_time REAL,
            recorded_at TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

# 模拟Agent数据
MOCK_AGENTS = {
    'coordinator': {'status': 'healthy', 'health_score': 98},
    'executor': {'status': 'healthy', 'health_score': 95},
    'monitor': {'status': 'healthy', 'health_score': 92},
    'dispatcher': {'status': 'degraded', 'health_score': 65},
    'aggregator': {'status': 'healthy', 'health_score': 88},
    'auth': {'status': 'healthy', 'health_score': 97}
}

class HealthChecker:
    """健康检查核心"""
    
    def __init__(self):
        self.alert_thresholds = {
            'health_score_critical': 30,
            'health_score_warning': 60,
            'cpu_warning': 80,
            'cpu_critical': 95,
            'memory_warning': 85,
            'memory_critical': 95
        }
    
    def check_agent_health(self, agent_id: str, agent_name: str) -> Dict:
        """检查单个Agent健康状态"""
        # 模拟健康数据
        import random
        now = datetime.now().isoformat()
        
        cpu = random.uniform(5, 40)
        memory = random.uniform(20, 60)
        success_rate = random.uniform(85, 99)
        response_time = random.uniform(50, 500)
        
        # 根据模拟数据计算健康分数
        health_score = 100 - (cpu * 0.3) - (memory * 0.2) - ((100 - success_rate) * 0.3)
        health_score = max(0, min(100, health_score))
        
        # 确定状态
        if health_score >= 80:
            status = 'healthy'
        elif health_score >= 50:
            status = 'degraded'
        else:
            status = 'unhealthy'
        
        return {
            'agent_id': agent_id,
            'agent_name': agent_name,
            'status': status,
            'health_score': round(health_score, 1),
            'cpu_usage': round(cpu, 1),
            'memory_usage': round(memory, 1),
            'task_success_rate': round(success_rate, 1),
            'avg_response_time': round(response_time, 1),
            'last_heartbeat': now,
            'checked_at': now
        }
    
    def check_all_agents(self) -> List[Dict]:
        """检查所有Agent"""
        results = []
        for agent_id, info in MOCK_AGENTS.items():
            result = self.check_agent_health(agent_id, agent_id)
            results.append(result)
            
            # 保存到数据库
            self.save_agent_health(result)
        
        return results
    
    def save_agent_health(self, health_data: Dict):
        """保存健康数据"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO agent_health 
            (agent_id, agent_name, status, health_score, cpu_usage, memory_usage,
             task_success_rate, avg_response_time, last_heartbeat, checked_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            health_data['agent_id'], health_data['agent_name'],
            health_data['status'], health_data['health_score'],
            health_data['cpu_usage'], health_data['memory_usage'],
            health_data['task_success_rate'], health_data['avg_response_time'],
            health_data['last_heartbeat'], health_data['checked_at']
        ))
        
        conn.commit()
        conn.close()
    
    def get_system_health(self) -> Dict:
        """获取系统整体健康状态"""
        agents = self.check_all_agents()
        
        total = len(agents)
        healthy = sum(1 for a in agents if a['status'] == 'healthy')
        degraded = sum(1 for a in agents if a['status'] == 'degraded')
        unhealthy = sum(1 for a in agents if a['status'] == 'unhealthy')
        
        avg_health_score = sum(a['health_score'] for a in agents) / total if total else 0
        avg_success_rate = sum(a['task_success_rate'] for a in agents) / total if total else 0
        avg_response_time = sum(a['avg_response_time'] for a in agents) / total if total else 0
        
        # 系统健康等级
        if avg_health_score >= 80:
            system_status = 'healthy'
        elif avg_health_score >= 50:
            system_status = 'degraded'
        else:
            system_status = 'unhealthy'
        
        # 保存系统指标
        self.save_system_metrics(total, healthy, avg_success_rate, avg_response_time)
        
        return {
            'system_status': system_status,
            'total_agents': total,
            'healthy_agents': healthy,
            'degraded_agents': degraded,
            'unhealthy_agents': unhealthy,
            'avg_health_score': round(avg_health_score, 1),
            'avg_success_rate': round(avg_success_rate, 1),
            'avg_response_time': round(avg_response_time, 1),
            'timestamp': datetime.now().isoformat()
        }
    
    def save_system_metrics(self, total, healthy, success_rate, response_time):
        """保存系统指标"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO system_metrics 
            (total_agents, active_agents, healthy_agents, success_rate, avg_response_time, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (total, healthy, healthy, success_rate, response_time, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_alerts(self, limit: int = 20) -> List[Dict]:
        """获取告警列表"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, severity, source, message, details, acknowledged, created_at, resolved_at
            FROM health_alerts
            ORDER BY created_at DESC
            LIMIT ?
        ''', (limit,))
        
        alerts = []
        for row in cursor.fetchall():
            alerts.append({
                'id': row[0],
                'severity': row[1],
                'source': row[2],
                'message': row[3],
                'details': json.loads(row[4]) if row[4] else None,
                'acknowledged': bool(row[5]),
                'created_at': row[6],
                'resolved_at': row[7]
            })
        
        conn.close()
        return alerts
    
    def create_alert(self, severity: str, source: str, message: str, details: Dict = None):
        """创建告警"""
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO health_alerts (severity, source, message, details, created_at)
            VALUES (?, ?, ?, ?, ?)
        ''', (severity, source, message, json.dumps(details) if details else None, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()

health_checker = HealthChecker()

# HTML模板
DASHBOARD_HTML = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>协作网络健康监控</title>
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
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            backdrop-filter: blur(10px);
        }
        .header h1 { font-size: 1.5rem; }
        .status-badge {
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .status-healthy { background: #10b981; }
        .status-degraded { background: #f59e0b; }
        .status-unhealthy { background: #ef4444; }
        
        .container { padding: 20px; max-width: 1400px; margin: 0 auto; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 16px;
            margin-bottom: 24px;
        }
        .stat-card {
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }
        .stat-card h3 { font-size: 0.9rem; color: #94a3b8; margin-bottom: 8px; }
        .stat-card .value { font-size: 2rem; font-weight: bold; }
        .stat-card .value.healthy { color: #10b981; }
        .stat-card .value.degraded { color: #f59e0b; }
        .stat-card .value.unhealthy { color: #ef4444; }
        
        .section { margin-bottom: 24px; }
        .section h2 { 
            font-size: 1.2rem; 
            margin-bottom: 16px; 
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .agents-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
        }
        .agent-card {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            padding: 16px;
            border-left: 4px solid #10b981;
        }
        .agent-card.degraded { border-left-color: #f59e0b; }
        .agent-card.unhealthy { border-left-color: #ef4444; }
        
        .agent-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }
        .agent-name { font-weight: bold; font-size: 1.1rem; }
        
        .agent-metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            font-size: 0.85rem;
        }
        .metric { color: #94a3b8; }
        .metric span { color: #fff; float: right; }
        
        .health-bar {
            height: 6px;
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
            margin-top: 12px;
            overflow: hidden;
        }
        .health-bar-fill {
            height: 100%;
            border-radius: 3px;
            transition: width 0.3s;
        }
        
        .alerts-list {
            background: rgba(255,255,255,0.05);
            border-radius: 12px;
            overflow: hidden;
        }
        .alert-item {
            padding: 12px 16px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            display: flex;
            align-items: center;
            gap: 12px;
        }
        .alert-item:last-child { border-bottom: none; }
        .alert-severity {
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }
        .severity-critical { background: #ef4444; }
        .severity-warning { background: #f59e0b; }
        .severity-info { background: #3b82f6; }
        
        .refresh-btn {
            background: #3b82f6;
            border: none;
            color: white;
            padding: 8px 16px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
        }
        .refresh-btn:hover { background: #2563eb; }
        
        @media (max-width: 768px) {
            .header { flex-direction: column; gap: 12px; text-align: center; }
            .container { padding: 12px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 多智能体协作网络健康监控</h1>
        <div>
            <span class="status-badge status-{{ system_status }}">{{ system_status }}</span>
            <button class="refresh-btn" onclick="location.reload()">🔄 刷新</button>
        </div>
    </div>
    
    <div class="container">
        <div class="stats-grid">
            <div class="stat-card">
                <h3>Agent总数</h3>
                <div class="value">{{ total_agents }}</div>
            </div>
            <div class="stat-card">
                <h3>健康Agent</h3>
                <div class="value healthy">{{ healthy_agents }}</div>
            </div>
            <div class="stat-card">
                <h3>性能下降</h3>
                <div class="value degraded">{{ degraded_agents }}</div>
            </div>
            <div class="stat-card">
                <h3>平均健康分</h3>
                <div class="value {% if avg_health_score >= 80 %}healthy{% elif avg_health_score >= 50 %}degraded{% else %}unhealthy{% endif %}">{{ avg_health_score }}%</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📊 Agent健康状态</h2>
            <div class="agents-grid">
                {% for agent in agents %}
                <div class="agent-card {{ agent.status }}">
                    <div class="agent-header">
                        <span class="agent-name">{{ agent.agent_name }}</span>
                        <span class="status-badge status-{{ agent.status }}">{{ agent.status }}</span>
                    </div>
                    <div class="agent-metrics">
                        <div class="metric">CPU: <span>{{ agent.cpu_usage }}%</span></div>
                        <div class="metric">内存: <span>{{ agent.memory_usage }}%</span></div>
                        <div class="metric">成功率: <span>{{ agent.task_success_rate }}%</span></div>
                        <div class="metric">响应时间: <span>{{ agent.avg_response_time }}ms</span></div>
                    </div>
                    <div class="health-bar">
                        <div class="health-bar-fill" style="width: {{ agent.health_score }}%; background: {% if agent.health_score >= 80 %}#10b981{% elif agent.health_score >= 50 %}#f59e0b{% else %}#ef4444{% endif %}"></div>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>
        
        <div class="section">
            <h2>🔌 服务健康状态</h2>
            <div class="agents-grid">
                {% if services %}
                    {% for service in services %}
                    <div class="agent-card {{ service.status }}">
                        <div class="agent-header">
                            <span class="agent-name">{{ service.service_name }}</span>
                            <span class="status-badge status-{{ service.status }}">{{ service.status }}</span>
                        </div>
                        <div class="agent-metrics">
                            <div class="metric">端口: <span>{{ service.port }}</span></div>
                            <div class="metric">响应时间: <span>{{ service.response_time_ms }}ms</span></div>
                            <div class="metric">HTTP状态: <span>{{ service.http_code }}</span></div>
                            <div class="metric">检查时间: <span>{{ service.timestamp.split('T')[1].split('.')[0] }}</span></div>
                        </div>
                        <div class="health-bar">
                            <div class="health-bar-fill" style="width: {% if service.status == 'healthy' %}100{% elif service.status == 'degraded' %}50{% else %}0{% endif %}%; background: {% if service.status == 'healthy' %}#10b981{% elif service.status == 'degraded' %}#f59e0b{% else %}#ef4444{% endif %}"></div>
                        </div>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="alert-item">
                        <span style="color: #64748b;">暂无服务数据 (health-check-api 可能未运行)</span>
                    </div>
                {% endif %}
            </div>
        </div>
        
        <div class="section">
            <h2>⚠️ 实时告警</h2>
            <div class="alerts-list">
                {% if alerts %}
                    {% for alert in alerts %}
                    <div class="alert-item">
                        <span class="alert-severity severity-{{ alert.severity }}">{{ alert.severity }}</span>
                        <span>{{ alert.message }}</span>
                        <span style="margin-left: auto; color: #64748b; font-size: 0.8rem;">{{ alert.created_at }}</span>
                    </div>
                    {% endfor %}
                {% else %}
                    <div class="alert-item">
                        <span style="color: #10b981;">✓ 系统运行正常，无告警</span>
                    </div>
                {% endif %}
            </div>
        </div>
    </div>
</body>
</html>
'''

# API路由
@app.route('/')
def dashboard():
    """监控仪表板首页"""
    system_health = health_checker.get_system_health()
    agents = health_checker.check_all_agents()
    alerts = health_checker.get_alerts(5)
    
    # 获取服务健康检查数据
    services = []
    try:
        req = urllib.request.Request('http://127.0.0.1:18105/services')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            services = data.get('services', [])
    except Exception:
        pass
    
    return render_template_string(DASHBOARD_HTML,
        system_status=system_health['system_status'],
        total_agents=system_health['total_agents'],
        healthy_agents=system_health['healthy_agents'],
        degraded_agents=system_health['degraded_agents'],
        avg_health_score=system_health['avg_health_score'],
        agents=agents,
        alerts=alerts,
        services=services
    )

@app.route('/api/health')
def api_health():
    """健康检查API"""
    return jsonify(health_checker.get_system_health())

@app.route('/api/agents')
def api_agents():
    """Agent列表API"""
    return jsonify(health_checker.check_all_agents())

@app.route('/api/agents/<agent_id>')
def api_agent(agent_id):
    """单个Agent详情"""
    for agent in health_checker.check_all_agents():
        if agent['agent_id'] == agent_id:
            return jsonify(agent)
    return jsonify({'error': 'Agent not found'}), 404

@app.route('/api/alerts')
def api_alerts():
    """告警列表API"""
    limit = request.args.get('limit', 20, type=int)
    return jsonify(health_checker.get_alerts(limit))

@app.route('/api/alerts', methods=['POST'])
def api_create_alert():
    """创建告警"""
    data = request.get_json()
    if not data or 'severity' not in data or 'message' not in data:
        return jsonify({'error': 'severity and message required'}), 400
    
    health_checker.create_alert(
        data['severity'],
        data.get('source', 'api'),
        data['message'],
        data.get('details')
    )
    
    return jsonify({'success': True})

@app.route('/api/metrics/history')
def api_metrics_history():
    """历史指标API"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT recorded_at, total_agents, healthy_agents, success_rate, avg_response_time
        FROM system_metrics
        ORDER BY recorded_at DESC
        LIMIT 100
    ''')
    
    history = []
    for row in cursor.fetchall():
        history.append({
            'timestamp': row[0],
            'total_agents': row[1],
            'healthy_agents': row[2],
            'success_rate': row[3],
            'avg_response_time': row[4]
        })
    
    conn.close()
    return jsonify(history)

@app.route('/api/services')
def api_services():
    """获取服务健康检查数据 (从 health-check-api 获取)"""
    try:
        req = urllib.request.Request('http://127.0.0.1:18105/services')
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode())
            return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e), 'services': []}), 500

@app.route('/api/services/trigger', methods=['POST'])
def api_trigger_check():
    """触发健康检查"""
    try:
        req = urllib.request.Request('http://127.0.0.1:18105/trigger', 
                                     method='POST')
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode())
            return jsonify(data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    print("🚀 多智能体协作网络健康监控仪表板启动")
    print("📊 访问地址: http://localhost:18103")
    app.run(host='0.0.0.0', port=18103, debug=False)