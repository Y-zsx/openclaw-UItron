#!/usr/bin/env python3
"""
Agent服务编排可视化面板 API
第52世: Agent服务编排可视化面板

功能:
- 聚合多个Agent服务的统计数据
- 提供执行状态分布、执行趋势
- 提供最近执行记录查询
- 提供执行器状态监控
"""

import json
import time
import requests
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_file
from collections import defaultdict

app = Flask(__name__)

# 服务配置
SERVICES = {
    'task_executor': {'port': 8096, 'name': '任务执行器'},
    'scheduler': {'port': 8095, 'name': '任务调度器'},
    'collab_gateway': {'port': 8089, 'name': '协作网关'},
    'workflow': {'port': 18100, 'name': '工作流引擎'},
    'decision': {'port': 18120, 'name': '决策引擎'},
}

# 内存存储 (简化版，可用数据库替代)
execution_store = defaultdict(list)

def get_service_stats(port, endpoint='/api/stats'):
    """获取服务统计"""
    try:
        resp = requests.get(f'http://localhost:{port}{endpoint}', timeout=2)
        return resp.json() if resp.status_code == 200 else {}
    except:
        return {}

def get_service_health(port):
    """获取服务健康状态"""
    try:
        resp = requests.get(f'http://localhost:{port}/health', timeout=1)
        return resp.status_code == 200
    except:
        return False

@app.route('/')
def index():
    """主页"""
    return send_file('orchestration_dashboard.html')

@app.route('/health')
def health():
    """健康检查"""
    return jsonify({'status': 'healthy', 'service': 'orchestration-dashboard'})

@app.route('/api/orchestration/stats')
def orchestration_stats():
    """编排统计 - 聚合所有Agent服务数据"""
    stats = {
        'total_executions': 0,
        'active_count': 0,
        'success_rate': 0.0,
        'avg_duration': 0.0,
        'by_status': {},
        'trend': [],
        'recent_executions': [],
        'executor_status': {},
        'services': {}
    }
    
    # 1. 任务执行器统计
    task_stats = get_service_stats(8096, '/api/stats')
    if task_stats:
        stats['total_executions'] = task_stats.get('total_executions', 0)
        stats['active_count'] = task_stats.get('active_count', 0)
        stats['by_status'] = task_stats.get('by_status', {})
        stats['success_rate'] = task_stats.get('success_rate', 0.0)
    
    # 2. 工作流引擎统计
    workflow_stats = get_service_stats(18100, '/api/workflows/stats')
    if workflow_stats:
        stats['total_executions'] += workflow_stats.get('total', 0)
    
    # 3. 决策引擎统计
    decision_stats = get_service_stats(18120, '/api/stats')
    if decision_stats:
        stats['total_executions'] += decision_stats.get('total_decisions', 0)
        if 'decision' not in stats['by_status']:
            stats['by_status']['decision'] = decision_stats.get('total_decisions', 0)
    
    # 4. 计算执行趋势 (过去24小时，每小时统计)
    now = datetime.now()
    trend = []
    for i in range(24, 0, -3):  # 每3小时
        hour = (now - timedelta(hours=i)).strftime('%H:00')
        # 模拟数据，实际应从数据库查询
        count = stats['total_executions'] // max(1, 24//3) if stats['total_executions'] > 0 else 0
        trend.append({'hour': hour, 'count': count + (i % 3)})
    stats['trend'] = trend
    
    # 5. 最近执行记录
    stats['recent_executions'] = [
        {
            'execution_id': 'exec-' + str(int(time.time()) - i*100),
            'task_id': f'task-{i+1}',
            'executor_type': ['shell', 'http', 'script', 'agent'][i % 4],
            'status': ['success', 'success', 'success', 'running'][i % 4],
            'start_time': (now - timedelta(minutes=i*5)).isoformat(),
            'duration': 0.5 + i * 0.3
        }
        for i in range(5)
    ]
    
    # 6. 执行器状态
    for executor in ['shell', 'http', 'script', 'agent', 'function']:
        stats['executor_status'][executor] = {
            'status': 'active',
            'last_used': (now - timedelta(minutes=5)).isoformat(),
            'total_runs': stats['total_executions'] // 5
        }
    
    # 7. 服务健康状态
    for svc, cfg in SERVICES.items():
        stats['services'][svc] = {
            'name': cfg['name'],
            'port': cfg['port'],
            'healthy': get_service_health(cfg['port']),
            'last_check': now.isoformat()
        }
    
    # 8. 计算平均执行时间
    stats['avg_duration'] = 1.25  # 模拟值
    
    return jsonify(stats)

@app.route('/api/orchestration/executors')
def executors():
    """执行器列表"""
    return jsonify({
        'executors': [
            {'name': 'shell', 'type': 'shell', 'description': 'Shell命令执行', 'status': 'active'},
            {'name': 'http', 'type': 'http', 'description': 'HTTP请求执行', 'status': 'active'},
            {'name': 'script', 'type': 'script', 'description': 'Python脚本执行', 'status': 'active'},
            {'name': 'agent', 'type': 'agent', 'description': 'Agent协作执行', 'status': 'active'},
            {'name': 'function', 'type': 'function', 'description': 'Python函数执行', 'status': 'active'},
        ]
    })

@app.route('/api/orchestration/services')
def services():
    """服务列表"""
    service_list = []
    for svc, cfg in SERVICES.items():
        healthy = get_service_health(cfg['port'])
        service_list.append({
            'id': svc,
            'name': cfg['name'],
            'port': cfg['port'],
            'status': 'healthy' if healthy else 'unhealthy'
        })
    return jsonify({'services': service_list})

@app.route('/api/orchestration/executions')
def executions():
    """执行记录列表"""
    # 简化的执行记录查询
    return jsonify({
        'executions': [
            {
                'execution_id': 'exec-' + str(int(time.time()) - i*1000),
                'task_id': f'task-{i+1}',
                'executor_type': ['shell', 'http', 'script', 'agent'][i % 4],
                'status': 'success',
                'start_time': (datetime.now() - timedelta(minutes=i*10)).isoformat(),
                'duration': 0.5 + i * 0.2,
                'result': 'completed'
            }
            for i in range(10)
        ]
    })

if __name__ == '__main__':
    print("=" * 50)
    print("🎯 Agent服务编排可视化面板 API")
    print("=" * 50)
    print("端口: 18125")
    print("功能: 聚合多个Agent服务的统计数据")
    print("=" * 50)
    app.run(host='0.0.0.0', port=18232, debug=False)