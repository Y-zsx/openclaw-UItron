#!/usr/bin/env python3
"""
增强版监控指标收集器
收集更多系统指标用于Dashboard展示
"""
import os, json, subprocess, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
METRICS_FILE = f'{WORKSPACE}/ultron-workflow/logs/enhanced_metrics.json'

def get_system_metrics():
    """获取系统指标"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'system': {},
        'services': {},
        'network': {}
    }
    
    # 1. 系统负载
    try:
        with open('/proc/loadavg') as f:
            load = f.read().split()[:3]
            metrics['system']['load'] = {
                '1m': float(load[0]),
                '5m': float(load[1]),
                '15m': float(load[2])
            }
    except:
        pass
    
    # 2. 内存
    try:
        with open('/proc/meminfo') as f:
            mem = {}
            for line in f:
                if 'MemTotal' in line:
                    mem['total'] = int(line.split()[1]) // 1024
                elif 'MemAvailable' in line:
                    mem['available'] = int(line.split()[1]) // 1024
            if mem:
                mem['used'] = mem['total'] - mem['available']
                mem['percent'] = round(mem['used'] / mem['total'] * 100, 1)
                metrics['system']['memory'] = mem
    except:
        pass
    
    # 3. 磁盘
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        parts = result.stdout.split('\n')[-1].split()
        metrics['system']['disk'] = {
            'total': parts[1],
            'used': parts[2],
            'percent': parts[4]
        }
    except:
        pass
    
    # 4. Gateway进程
    try:
        result = subprocess.run(['pgrep', '-f', 'openclaw'], capture_output=True, timeout=5)
        metrics['system']['gateway_processes'] = len(result.stdout.split()) if result.stdout else 0
    except:
        pass
    
    # 5. 核心服务检查
    services = {
        'gateway': 'http://localhost:18789/',
        'status_panel': 'http://localhost:8889/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/'
    }
    
    for name, url in services.items():
        try:
            result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '3', url],
                capture_output=True, timeout=5
            )
            status = result.stdout.decode().strip()
            metrics['services'][name] = 'healthy' if status == '200' else f'error_{status}'
        except:
            metrics['services'][name] = 'unreachable'
    
    # 6. 网络连接统计
    try:
        result = subprocess.run(['ss', '-tun'], capture_output=True, timeout=5)
        lines = result.stdout.decode().split('\n')
        metrics['network']['connections'] = len(lines) - 2
    except:
        pass
    
    return metrics

def save_metrics(metrics):
    """保存指标"""
    os.makedirs(os.path.dirname(METRICS_FILE), exist_ok=True)
    
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
    metrics = get_system_metrics()
    save_metrics(metrics)
    print(json.dumps(metrics, indent=2))