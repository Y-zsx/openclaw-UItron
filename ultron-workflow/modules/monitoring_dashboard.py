#!/usr/bin/env python3
"""
系统监控仪表板增强
聚合多个数据源到统一Dashboard展示
"""
import os, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
DASHBOARD_FILE = f'{WORKSPACE}/ultron-workflow/logs/monitoring_dashboard.json'

def get_system_info():
    """获取系统信息"""
    info = {'timestamp': datetime.now().isoformat()}
    
    # 负载
    try:
        with open('/proc/loadavg') as f:
            load = f.read().split()[:3]
            info['load'] = {'1m': load[0], '5m': load[1], '15m': load[2]}
    except:
        pass
    
    # 内存
    try:
        with open('/proc/meminfo') as f:
            for line in f:
                if 'MemTotal' in line:
                    info['memory_total'] = int(line.split()[1]) // 1024
                elif 'MemAvailable' in line:
                    info['memory_available'] = int(line.split()[1]) // 1024
    except:
        pass
    
    return info

def get_services_status():
    """获取服务状态"""
    services = {
        'gateway': 'http://localhost:18789/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/',
        'collab_api': 'http://localhost:8105/health'
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

def get_task_stats():
    """获取任务统计"""
    queue_file = f'{WORKSPACE}/ultron-workflow/logs/task_queue.json'
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            return json.load(f)
    return None

def aggregate_dashboard():
    """聚合Dashboard数据"""
    data = {
        'timestamp': datetime.now().isoformat(),
        'system': get_system_info(),
        'services': get_services_status(),
        'tasks': get_task_stats()
    }
    
    with open(DASHBOARD_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    
    return data

if __name__ == '__main__':
    data = aggregate_dashboard()
    
    print(f"监控仪表板数据:")
    print(f"  系统: {data.get('system', {}).get('load', {})}")
    print(f"  服务: {data.get('services', {})}")
    
    healthy = sum(1 for v in data.get('services', {}).values() if v)
    total = len(data.get('services', {}))
    print(f"  服务健康: {healthy}/{total}")
