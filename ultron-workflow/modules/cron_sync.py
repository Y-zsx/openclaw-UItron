#!/usr/bin/env python3
"""
Cron自动同步模块
将调度器与OpenClaw Cron系统同步
"""
import os, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
SYNC_FILE = f'{WORKSPACE}/ultron-workflow/logs/cron_sync.json'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/cron_sync.log'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def get_active_crons():
    """获取活跃的Cron任务"""
    try:
        result = subprocess.run(
            ['openclaw', 'cron', 'list'],
            capture_output=True, text=True, timeout=30
        )
        
        crons = []
        for line in result.stdout.split('\n'):
            if 'ultron' in line.lower():
                crons.append(line.strip())
        
        return crons
    except Exception as e:
        log(f'获取Cron失败: {e}')
        return []

def sync_scheduler():
    """同步调度器"""
    log('开始Cron同步...')
    
    # 获取活跃Cron
    crons = get_active_crons()
    log(f'发现 {len(crons)} 个相关Cron任务')
    
    # 读取调度器状态
    tasks_file = f'{WORKSPACE}/ultron-workflow/logs/scheduled_tasks.json'
    tasks = {}
    if os.path.exists(tasks_file):
        with open(tasks_file) as f:
            tasks = json.load(f)
    
    # 同步状态
    sync_data = {
        'last_sync': datetime.now().isoformat(),
        'scheduler_tasks': len(tasks),
        'cron_tasks': len(crons),
        'crons': crons[:10]
    }
    
    with open(SYNC_FILE, 'w') as f:
        json.dump(sync_data, f, indent=2)
    
    log(f'同步完成: {len(tasks)} 调度任务, {len(crons)} Cron任务')
    return sync_data

if __name__ == '__main__':
    result = sync_scheduler()
    print(json.dumps(result, indent=2))