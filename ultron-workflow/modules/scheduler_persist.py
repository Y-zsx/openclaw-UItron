#!/usr/bin/env python3
"""
调度器持久化与恢复模块
确保调度器状态在重启后恢复
"""
import os, json, shutil
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
STATE_DIR = f'{WORKSPACE}/ultron-workflow/state'
BACKUP_DIR = f'{STATE_DIR}/backups'
PERSIST_FILE = f'{STATE_DIR}/scheduler_persist.json'

def ensure_dirs():
    """确保目录存在"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

def backup_state():
    """备份当前状态"""
    ensure_dirs()
    
    # 备份任务配置
    tasks_file = f'{WORKSPACE}/ultron-workflow/logs/scheduled_tasks.json'
    if os.path.exists(tasks_file):
        backup_file = f'{BACKUP_DIR}/tasks_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        shutil.copy2(tasks_file, backup_file)
        
        # 只保留最近5个备份
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('tasks_')])
        while len(backups) > 5:
            os.remove(f'{BACKUP_DIR}/{backups[0]}')
            backups.pop(0)
        
        return backup_file
    return None

def restore_state():
    """恢复最近的状态"""
    if not os.path.exists(BACKUP_DIR):
        return None
    
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('tasks_')])
    if not backups:
        return None
    
    latest = f'{BACKUP_DIR}/{backups[-1]}'
    tasks_file = f'{WORKSPACE}/ultron-workflow/logs/scheduled_tasks.json'
    
    shutil.copy2(latest, tasks_file)
    return latest

def save_persist_state(state_data):
    """保存持久化状态"""
    ensure_dirs()
    
    data = {
        'timestamp': datetime.now().isoformat(),
        'data': state_data
    }
    
    with open(PERSIST_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_persist_state():
    """加载持久化状态"""
    if os.path.exists(PERSIST_FILE):
        with open(PERSIST_FILE) as f:
            return json.load(f)
    return None

def get_recovery_status():
    """获取恢复状态"""
    ensure_dirs()
    
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('tasks_')])
    
    return {
        'backup_count': len(backups),
        'latest_backup': backups[-1] if backups else None,
        'persist_file_exists': os.path.exists(PERSIST_FILE),
        'persist_data': load_persist_state()
    }

if __name__ == '__main__':
    # 备份当前状态
    backup_file = backup_state()
    print(f'备份完成: {backup_file}')
    
    # 保存持久化状态
    state_data = {
        'last_incarnation': 139,
        'task': '添加调度器持久化与恢复机制',
        'status': 'running'
    }
    save_persist_state(state_data)
    print('持久化状态已保存')
    
    # 获取恢复状态
    status = get_recovery_status()
    print(f'恢复状态: {status}')
