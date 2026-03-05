#!/usr/bin/env python3
"""
定时健康检查调度器
负责定时执行健康检查并触发告警
"""
import os, sys, json, time, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/health_scheduler.log'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def check_services():
    """检查关键服务状态"""
    checks = []
    
    # 1. Gateway
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:18789/'], 
                          capture_output=True, timeout=5)
        checks.append(('gateway', r.stdout.decode() == '200'))
    except:
        checks.append(('gateway', False))
    
    # 2. Chrome headless
    try:
        r = subprocess.run(['pgrep', '-f', 'chrome.*headless'], capture_output=True, timeout=5)
        checks.append(('chrome', r.returncode == 0))
    except:
        checks.append(('chrome', False))
    
    # 3. 状态面板
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:8889/'], 
                          capture_output=True, timeout=5)
        checks.append(('status_panel', r.stdout.decode() == '200'))
    except:
        checks.append(('status_panel', False))
    
    return checks

def run_health_check():
    """执行健康检查"""
    log('开始健康检查...')
    services = check_services()
    
    failed = [name for name, ok in services if not ok]
    healthy = len(services) - len(failed)
    total = len(services)
    
    if failed:
        log(f'WARNING: {len(failed)}个服务异常 - {failed}')
        return {'status': 'warning', 'healthy': healthy, 'total': total, 'failed': failed}
    else:
        log(f'OK: {healthy}/{total} 服务正常')
        return {'status': 'healthy', 'healthy': healthy, 'total': total}

if __name__ == '__main__':
    result = run_health_check()
    print(json.dumps(result))