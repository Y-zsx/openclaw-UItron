#!/usr/bin/env python3
"""
系统监控Dashboard增强模块
聚合多个数据源到统一Dashboard
"""
import os, json, subprocess, urllib.request
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DASHBOARD_DATA = f'{WORKSPACE}/ultron-workflow/logs/dashboard_data.json'

def get_gateway_status():
    """获取Gateway状态"""
    try:
        r = urllib.request.urlopen('http://localhost:18789/', timeout=5)
        return {'status': 'running', 'code': r.status}
    except:
        return {'status': 'down', 'code': 0}

def get_system_metrics():
    """获取系统指标"""
    metrics_file = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'
    if os.path.exists(metrics_file):
        with open(metrics_file) as f:
            data = json.load(f)
            if data:
                return data[-1].get('system', {})
    return {}

def get_health_status():
    """获取健康检查状态"""
    health_file = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
    if os.path.exists(health_file):
        with open(health_file) as f:
            return json.load(f)
    return {'summary': {'total': 0, 'healthy': 0, 'warning': 0}}

def get_task_stats():
    """获取任务统计"""
    tasks_file = f'{WORKSPACE}/ultron-workflow/logs/scheduled_tasks.json'
    if os.path.exists(tasks_file):
        with open(tasks_file) as f:
            return json.load(f)
    return {}

def get_cron_count():
    """获取Cron任务数量"""
    try:
        result = subprocess.run(
            ['openclaw', 'cron', 'list'],
            capture_output=True, text=True, timeout=10
        )
        count = sum(1 for line in result.stdout.splitlines() if 'ultron' in line.lower())
        return count
    except:
        return 0

def aggregate_dashboard_data():
    """聚合Dashboard数据"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'gateway': get_gateway_status(),
        'system': get_system_metrics(),
        'health': get_health_status(),
        'tasks': get_task_stats(),
        'cron_count': get_cron_count()
    }
    
    with open(DASHBOARD_DATA, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data

if __name__ == '__main__':
    data = aggregate_dashboard_data()
    
    print(f"Dashboard数据聚合完成:")
    print(f"  Gateway: {data['gateway']['status']}")
    print(f"  Cron任务: {data['cron_count']}个")
    print(f"  健康检查: {data['health']['summary']['total']}次")
    print(f"  任务调度: {len(data['tasks'])}个任务")
    
    load = data['system'].get('load', {})
    if load:
        print(f"  负载: 1m={load.get('1m')}, 5m={load.get('5m')}, 15m={load.get('15m')}")