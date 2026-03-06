#!/usr/bin/env python3
"""
任务调度器守护进程
持续运行，定时执行各种运维任务
"""
import os
import sys
import json
import time
import signal
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/scheduler_daemon.log'
STATE_FILE = f'{WORKSPACE}/ultron-workflow/state/scheduler_daemon.json'

# 任务配置
TASKS = {
    'health_check': {
        'script': f'{WORKSPACE}/ultron-workflow/modules/cron_health_trigger.py',
        'interval': 300,  # 5分钟
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
    },
    'self_healer': {
        'script': f'{WORKSPACE}/ultron-workflow/modules/self_healer.py',
        'interval': 300,
        'last_run': None,
        'enabled': True
    }
}

running = True

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(f"[scheduler] {msg}")

def signal_handler(signum, frame):
    global running
    log("收到停止信号，正在关闭...")
    running = False

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'tasks': {}, 'start_time': datetime.now().isoformat()}

def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def should_run(task_name, task_config, state):
    if not task_config.get('enabled', True):
        return False
    
    tasks = state.get('tasks', {})
    last_run = tasks.get(task_name, {}).get('last_run')
    
    if not last_run:
        return True
    
    interval = task_config.get('interval', 300)
    try:
        last_time = datetime.fromisoformat(last_run)
        return (datetime.now() - last_time).total_seconds() >= interval
    except:
        return True

def run_task(task_name, task_config):
    log(f'执行任务: {task_name}')
    
    script = task_config.get('script')
    if not script or not os.path.exists(script):
        log(f'  脚本不存在: {script}')
        return False
    
    try:
        result = subprocess.run(
            ['python3', script],
            capture_output=True, text=True, timeout=60,
            cwd=WORKSPACE
        )
        log(f'  完成: returncode={result.returncode}')
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        log(f'  超时')
        return False
    except Exception as e:
        log(f'  错误: {e}')
        return False

def main():
    global running
    
    # 注册信号处理
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    log('任务调度器守护进程启动')
    
    state = load_state()
    state['start_time'] = datetime.now().isoformat()
    save_state(state)
    
    check_interval = 30  # 每30秒检查一次
    
    while running:
        try:
            tasks = state.setdefault('tasks', {})
            
            for task_name, task_config in TASKS.items():
                if should_run(task_name, task_config, state):
                    success = run_task(task_name, task_config)
                    
                    if task_name not in tasks:
                        tasks[task_name] = {}
                    
                    tasks[task_name]['last_run'] = datetime.now().isoformat()
                    tasks[task_name]['success'] = success
            
            # 保存状态
            state['last_check'] = datetime.now().isoformat()
            save_state(state)
            
            # 等待下次检查
            for _ in range(check_interval):
                if not running:
                    break
                time.sleep(1)
                
        except Exception as e:
            log(f'错误: {e}')
            time.sleep(5)
    
    log('任务调度器守护进程已停止')
    return 0

if __name__ == '__main__':
    sys.exit(main())