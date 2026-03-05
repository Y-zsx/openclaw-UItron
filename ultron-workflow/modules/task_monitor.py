#!/usr/bin/env python3
"""
任务执行监控和日志模块
监控任务执行状态并记录详细日志
"""
import os, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
MONITOR_LOG = f'{WORKSPACE}/ultron-workflow/logs/task_monitor.log'
METRICS_FILE = f'{WORKSPACE}/ultron-workflow/logs/task_metrics.json'

def log(msg):
    os.makedirs(os.path.dirname(MONITOR_LOG), exist_ok=True)
    with open(MONITOR_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def get_queue_metrics():
    queue_file = f'{WORKSPACE}/ultron-workflow/logs/task_queue.json'
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            return json.load(f)
    return None

def get_executor_status():
    services = {
        'gateway': 'http://localhost:18789/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/'
    }
    
    status = {}
    for name, url in services.items():
        try:
            r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '3', url],
                             capture_output=True, timeout=5)
            status[name] = r.stdout.decode().strip() == '200'
        except:
            status[name] = False
    
    return status

def get_task_metrics():
    queue = get_queue_metrics()
    
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'queue': {},
        'services': get_executor_status()
    }
    
    if queue:
        metrics['queue'] = {
            'pending': len(queue.get('pending', [])),
            'running': len(queue.get('running', [])),
            'completed': len(queue.get('completed', [])),
            'failed': len(queue.get('failed', []))
        }
        
        total = metrics['queue']['completed'] + metrics['queue']['failed']
        if total > 0:
            metrics['success_rate'] = round(metrics['queue']['completed'] / total * 100, 1)
        else:
            metrics['success_rate'] = 100.0
    
    return metrics

def save_metrics(metrics):
    history = []
    if os.path.exists(METRICS_FILE):
        with open(METRICS_FILE) as f:
            history = json.load(f)
    
    history.append(metrics)
    
    if len(history) > 100:
        history = history[-100:]
    
    with open(METRICS_FILE, 'w') as f:
        json.dump(history, f, indent=2)

if __name__ == '__main__':
    log('任务监控开始...')
    
    metrics = get_task_metrics()
    save_metrics(metrics)
    
    print(f"任务指标:")
    print(f"  队列: {metrics.get('queue', {})}")
    print(f"  服务: {metrics.get('services', {})}")
    print(f"  成功率: {metrics.get('success_rate', 0)}%")
    
    log('任务监控完成')