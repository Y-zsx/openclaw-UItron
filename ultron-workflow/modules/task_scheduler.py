#!/usr/bin/env python3
"""
定时任务自动调度器
自动管理和调度各种运维任务
"""
import os, json, subprocess, time
from datetime import datetime, timedelta

WORKSPACE = '/root/.openclaw/workspace'
TASKS_FILE = f'{WORKSPACE}/ultron-workflow/logs/scheduled_tasks.json'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/task_scheduler.log'

# 任务配置
TASKS = {
    'health_check': {
        'script': f'{WORKSPACE}/ultron-workflow/modules/cron_health_trigger.py',
        'interval': 300,
        'last_run': None,
        'enabled': True
    },
    'metrics_collect': {
        'script': f'{WORKSPACE}/ultron-workflow/modules/metrics_collector.py',
        'interval': 300,
        'last_run': None,
        'enabled': True
    },
    'api_health': {
        'script': f'{WORKSPACE}/ultron-workflow/modules/health_api_manager.py',
        'interval': 60,
        'last_run': None,
        'enabled': True
    }
}

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def load_tasks():
    if os.path.exists(TASKS_FILE):
        with open(TASKS_FILE) as f:
            return json.load(f)
    return TASKS

def save_tasks(tasks):
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

def should_run(task_name, task_config):
    if not task_config.get('enabled', True):
        return False
    
    last_run = task_config.get('last_run')
    if not last_run:
        return True
    
    interval = task_config.get('interval', 300)
    last_time = datetime.fromisoformat(last_run)
    
    return (datetime.now() - last_time).seconds >= interval

def run_task(task_name, task_config):
    log(f'执行任务: {task_name}')
    
    script = task_config.get('script')
    if not script or not os.path.exists(script):
        log(f'  脚本不存在: {script}')
        return False
    
    try:
        result = subprocess.run(
            ['python3', script],
            capture_output=True, text=True, timeout=60
        )
        log(f'  完成: {result.returncode}')
        return result.returncode == 0
    except Exception as e:
        log(f'  错误: {e}')
        return False

def main():
    log('任务调度器启动')
    
    tasks = load_tasks()
    
    for task_name, task_config in tasks.items():
        if should_run(task_name, task_config):
            success = run_task(task_name, task_config)
            
            if success or not task_config.get('last_run'):
                task_config['last_run'] = datetime.now().isoformat()
    
    save_tasks(tasks)
    log('任务调度器完成')
    
    return {
        'tasks_run': sum(1 for t in tasks.values() if should_run(t, t)),
        'tasks_total': len(tasks)
    }

if __name__ == '__main__':
    result = main()
    print(json.dumps(result))