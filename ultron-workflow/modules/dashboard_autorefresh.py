#!/usr/bin/env python3
"""
Dashboard自动刷新调度器
定时更新Dashboard数据
"""
import os, json, subprocess, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/dashboard_autorefresh.log'
REFRESH_INTERVAL = 30  # 30秒刷新一次

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}
")
    print(msg)

def refresh_dashboard_data():
    """刷新Dashboard数据"""
    log('刷新Dashboard数据...')
    
    # 调用dashboard_aggregator
    result = subprocess.run(
        ['python3', f'{WORKSPACE}/ultron-workflow/modules/dashboard_aggregator.py'],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode == 0:
        log('Dashboard数据刷新成功')
        return True
    else:
        log(f'刷新失败: {result.stderr}')
        return False

def schedule_auto_refresh(count=10):
    """定时刷新"""
    log(f'开始自动刷新 (共{count}次)...')
    
    success = 0
    for i in range(count):
        if refresh_dashboard_data():
            success += 1
        time.sleep(REFRESH_INTERVAL)
    
    log(f'自动刷新完成: {success}/{count}次成功')
    return {'total': count, 'success': success}

if __name__ == '__main__':
    # 单次刷新测试
    refresh_dashboard_data()
    
    # 也可以运行定时刷新
    # schedule_auto_refresh(5)
