#!/usr/bin/env python3
"""
集成监控系统 Dashboard
聚合来自多个监控服务的数据，提供统一的监控视图
端口: 18223
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from flask import Flask, jsonify, render_template_string, request
import requests

app = Flask(__name__)

# 监控服务配置
MONITOR_SERVICES = {
    "alert_history": {"port": 18217, "health": "/health", "stats": "/api/stats/enhanced"},
    "scheduler_perf": {"port": 18218, "health": "/api/health", "stats": "/api/performance"},
    "task_monitor": {"port": 18219, "health": "/api/health", "stats": "/api/stats"},
}


def fetch_service_data(service_name, endpoint, timeout=3):
    """获取服务数据"""
    try:
        service = MONITOR_SERVICES.get(service_name)
        if not service:
            return None
        url = f"http://localhost:{service['port']}{endpoint}"
        response = requests.get(url, timeout=timeout)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        pass
    return None


def get_all_health_status():
    """获取所有服务健康状态"""
    status = {}
    for name, config in MONITOR_SERVICES.items():
        data = fetch_service_data(name, config["health"])
        status[name] = {
            "port": config["port"],
            "status": "healthy" if data else "unhealthy",
            "data": data
        }
    return status


def get_integrated_stats():
    """获取集成统计数据"""
    stats = {
        "alerts": {},
        "scheduler": {},
        "tasks": {}
    }
    
    # 获取告警数据
    alert_data = fetch_service_data("alert_history", "/api/stats/enhanced")
    if alert_data:
        stats["alerts"] = {
            "total": sum(alert_data.get("hourly_stats", {}).values()),
            "by_level": alert_data.get("by_level", {}),
            "by_service": alert_data.get("by_service", {}),
            "by_channel": alert_data.get("by_channel", {}),
            "recent_count": len(alert_data.get("recent", []))
        }
    
    # 获取调度器性能数据
    perf_data = fetch_service_data("scheduler_perf", "/api/performance")
    if perf_data:
        metrics = perf_data.get("metrics", {})
        stats["scheduler"] = {
            "score": metrics.get("performance_score", 0),
            "metrics": metrics,
            "recommendations": perf_data.get("recommendations", [])
        }
    
    # 获取任务监控数据
    task_data = fetch_service_data("task_monitor", "/api/stats")
    if task_data:
        stats["tasks"] = {
            "total": task_data.get("summary", {}).get("total_executions", 0),
            "success": task_data.get("summary", {}).get("success_count", 0),
            "fail": task_data.get("summary", {}).get("fail_count", 0),
            "avg_duration": task_data.get("summary", {}).get("avg_duration_ms", 0),
            "task_stats": task_data.get("task_stats", [])
        }
    
    return stats


# HTML Dashboard 模板
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>奥创集成监控系统</title>
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
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            margin-bottom: 30px;
        }
        .header h1 { font-size: 2.5em; margin-bottom: 10px; }
        .header .subtitle { color: #888; font-size: 0.9em; }
        .status-bar {
            display: flex;
            justify-content: center;
            gap: 30px;
            flex-wrap: wrap;
            margin-bottom: 40px;
        }
        .status-item {
            background: rgba(255,255,255,0.05);
            padding: 20px 30px;
            border-radius: 12px;
            text-align: center;
            min-width: 150px;
        }
        .status-item .label { color: #888; font-size: 0.85em; margin-bottom: 8px; }
        .status-item .value { font-size: 1.8em; font-weight: bold; }
        .status-item .port { color: #666; font-size: 0.75em; margin-top: 5px; }
        .healthy { color: #00d26a; }
        .unhealthy { color: #f93e3e; }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .card {
            background: rgba(255,255,255,0.03);
            border-radius: 16px;
            padding: 25px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        .card h2 {
            font-size: 1.2em;
            margin-bottom: 20px;
            padding-bottom: 15px;
            border-bottom: 1px solid rgba(255,255,255,0.1);
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .card h2 .icon { font-size: 1.4em; }
        
        .metric { margin-bottom: 15px; }
        .metric .label { color: #888; font-size: 0.85em; margin-bottom: 5px; }
        .metric .value { font-size: 1.4em; font-weight: 600; }
        
        .progress-bar {
            height: 8px;
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 8px;
        }
        .progress-bar .fill {
            height: 100%;
            border-radius: 4px;
            transition: width 0.5s ease;
        }
        .progress-high { background: #00d26a; }
        .progress-mid { background: #f0ad4e; }
        .progress-low { background: #f93e3e; }
        
        .stat-row {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
        }
        .stat-row:last-child { border: none; }
        .stat-row .label { color: #888; }
        .stat-row .value { font-weight: 600; }
        
        .task-item {
            background: rgba(255,255,255,0.02);
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        .task-item .name { font-weight: 600; margin-bottom: 8px; }
        .task-item .stats { display: flex; gap: 20px; font-size: 0.85em; color: #888; }
        
        .recommendation {
            background: rgba(255,193,7,0.1);
            border-left: 3px solid #ffc107;
            padding: 12px;
            margin-bottom: 10px;
            border-radius: 0 8px 8px 0;
            font-size: 0.9em;
        }
        
        .alert-item {
            padding: 8px 12px;
            background: rgba(255,255,255,0.02);
            border-radius: 6px;
            margin-bottom: 8px;
            font-size: 0.85em;
        }
        .alert-level-warning { border-left: 3px solid #ffc107; }
        .alert-level-error { border-left: 3px solid #f93e3e; }
        .alert-level-info { border-left: 3px solid #17a2b8; }
        
        .footer {
            text-align: center;
            padding: 20px;
            color: #666;
            font-size: 0.8em;
        }
        .refresh-btn {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            color: white;
            padding: 12px 30px;
            border-radius: 25px;
            cursor: pointer;
            font-size: 1em;
            margin-bottom: 20px;
        }
        .refresh-btn:hover { opacity: 0.9; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🦞 奥创集成监控系统</h1>
        <div class="subtitle">Integrated Monitoring Dashboard | 第150世</div>
    </div>
    
    <div style="text-align:center;">
        <button class="refresh-btn" onclick="location.reload()">🔄 刷新数据</button>
    </div>
    
    <div class="status-bar">
        <div class="status-item">
            <div class="label">告警服务 (18217)</div>
            <div class="value {{'healthy' if health.alert_history.status=='healthy' else 'unhealthy'}}">
                {{health.alert_history.status}}
            </div>
            <div class="port">端口: 18217</div>
        </div>
        <div class="status-item">
            <div class="label">调度器性能 (18218)</div>
            <div class="value {{'healthy' if health.scheduler_perf.status=='healthy' else 'unhealthy'}}">
                {{health.scheduler_perf.status}}
            </div>
            <div class="port">端口: 18218</div>
        </div>
        <div class="status-item">
            <div class="label">任务监控 (18219)</div>
            <div class="value {{'healthy' if health.task_monitor.status=='healthy' else 'unhealthy'}}">
                {{health.task_monitor.status}}
            </div>
            <div class="port">端口: 18219</div>
        </div>
        <div class="status-item">
            <div class="label">Dashboard</div>
            <div class="value healthy">running</div>
            <div class="port">端口: 18223</div>
        </div>
    </div>
    
    <div class="grid">
        <!-- 任务统计卡片 -->
        <div class="card">
            <h2><span class="icon">📋</span> 任务执行统计</h2>
            <div class="metric">
                <div class="label">总执行次数</div>
                <div class="value">{{stats.tasks.total}}</div>
            </div>
            <div class="metric">
                <div class="label">成功率</div>
                <div class="value {% if stats.tasks.total > 0 and (stats.tasks.success/stats.tasks.total) > 0.8 %}healthy{% else %}unhealthy{% endif %}">
                    {% if stats.tasks.total > 0 %}{{ "%.1f"|format(stats.tasks.success/stats.tasks.total*100) }}%{% else %}N/A{% endif %}
                </div>
            </div>
            <div class="metric">
                <div class="label">平均执行时间</div>
                <div class="value">{{ "%.1f"|format(stats.tasks.avg_duration) }}ms</div>
            </div>
            <div class="stat-row">
                <span class="label">成功</span>
                <span class="value healthy">{{stats.tasks.success}}</span>
            </div>
            <div class="stat-row">
                <span class="label">失败</span>
                <span class="value unhealthy">{{stats.tasks.fail}}</span>
            </div>
        </div>
        
        <!-- 调度器性能卡片 -->
        <div class="card">
            <h2><span class="icon">⚡</span> 调度器性能</h2>
            <div class="metric">
                <div class="label">性能得分</div>
                <div class="value {% if stats.scheduler.score >= 80 %}healthy{% elif stats.scheduler.score >= 50 %}unhealthy{% endif %}">
                    {{stats.scheduler.score}}
                </div>
                <div class="progress-bar">
                    <div class="fill {% if stats.scheduler.score >= 80 %}progress-high{% elif stats.scheduler.score >= 50 %}progress-mid{% else %}progress-low{% endif %}" 
                         style="width: {{stats.scheduler.score}}%"></div>
                </div>
            </div>
            {% if stats.scheduler.recommendations %}
            <div class="label" style="margin-top:15px;">优化建议</div>
            {% for rec in stats.scheduler.recommendations[:2] %}
            <div class="recommendation">{{rec}}</div>
            {% endfor %}
            {% endif %}
        </div>
        
        <!-- 告警统计卡片 -->
        <div class="card">
            <h2><span class="icon">🚨</span> 告警统计</h2>
            <div class="metric">
                <div class="label">总告警数</div>
                <div class="value">{{stats.alerts.total}}</div>
            </div>
            <div class="stat-row">
                <span class="label">Warning</span>
                <span class="value" style="color:#ffc107;">{{stats.alerts.by_level.warning}}</span>
            </div>
            <div class="stat-row">
                <span class="label">Error</span>
                <span class="value" style="color:#f93e3e;">{{stats.alerts.by_level.error}}</span>
            </div>
            <div class="stat-row">
                <span class="label">Info</span>
                <span class="value" style="color:#17a2b8;">{{stats.alerts.by_level.info}}</span>
            </div>
            <div class="stat-row">
                <span class="label">最近告警</span>
                <span class="value">{{stats.alerts.recent_count}}</span>
            </div>
        </div>
        
        <!-- 服务分布卡片 -->
        <div class="card">
            <h2><span class="icon">🖥️</span> 按服务分布</h2>
            {% if stats.alerts.by_service %}
            {% for service, count in stats.alerts.by_service.items() %}
            <div class="stat-row">
                <span class="label">{{service}}</span>
                <span class="value">{{count}}</span>
            </div>
            {% endfor %}
            {% else %}
            <div class="stat-row"><span class="label">暂无数据</span></div>
            {% endif %}
        </div>
    </div>
    
    <!-- 任务详情 -->
    <div class="card" style="margin-bottom:20px;">
        <h2><span class="icon">📝</span> 任务详情</h2>
        {% if stats.tasks.task_stats %}
        {% for task in stats.tasks.task_stats %}
        <div class="task-item">
            <div class="name">{{task.task_name}} ({{task.task_id}})</div>
            <div class="stats">
                <span>总执行: {{task.total_runs}}</span>
                <span>成功: {{task.success_runs}}</span>
                <span>失败: {{task.fail_runs}}</span>
                <span>平均: {{ "%.1f"|format(task.avg_duration_ms) }}ms</span>
            </div>
        </div>
        {% endfor %}
        {% else %}
        <div class="stat-row"><span class="label">暂无任务数据</span></div>
        {% endif %}
    </div>
    
    <div class="footer">
        <p>奥创集成监控系统 v1.0 | 最后更新: {{update_time}}</p>
    </div>
</body>
</html>
'''


@app.route('/')
def index():
    """Dashboard主页"""
    health = get_all_health_status()
    stats = get_integrated_stats()
    return render_template_string(
        DASHBOARD_TEMPLATE,
        health=health,
        stats=stats,
        update_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    )


@app.route('/api/integrated')
def api_integrated():
    """获取集成数据API"""
    health = get_all_health_status()
    stats = get_integrated_stats()
    return jsonify({
        "timestamp": datetime.now().isoformat(),
        "services": health,
        "stats": stats
    })


@app.route('/api/health')
def health():
    """健康检查"""
    health_status = get_all_health_status()
    all_healthy = all(s.get("status") == "healthy" for s in health_status.values())
    return jsonify({
        "port": 18223,
        "service": "integrated-monitor-dashboard",
        "status": "healthy" if all_healthy else "degraded",
        "services": health_status,
        "timestamp": datetime.now().isoformat()
    })


if __name__ == '__main__':
    print("=" * 50)
    print("🦞 奥创集成监控系统 Dashboard")
    print("=" * 50)
    print("端口: 18223")
    print("访问: http://localhost:18220")
    print("=" * 50)
    app.run(host='0.0.0.0', port=18223, debug=False)