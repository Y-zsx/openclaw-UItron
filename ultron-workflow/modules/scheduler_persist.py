#!/usr/bin/env python3
"""
调度器持久化与恢复模块 V2
增强版：支持崩溃恢复、检查点、自动恢复
"""
import os, json, shutil, hashlib, threading
from datetime import datetime
from pathlib import Path

WORKSPACE = '/root/.openclaw/workspace'
STATE_DIR = f'{WORKSPACE}/ultron-workflow/state'
BACKUP_DIR = f'{STATE_DIR}/backups'
PERSIST_FILE = f'{STATE_DIR}/scheduler_persist.json'
CHECKPOINT_FILE = f'{WORKSPACE}/ultron-workflow/scheduler_checkpoint.json'
EXECUTION_LOG = f'{WORKSPACE}/ultron-workflow/logs/execution_history.json'

# 配置
MAX_BACKUPS = 10
CHECKPOINT_INTERVAL = 60  # 秒

_ensure_dirs_done = False
_lock = threading.Lock()

def ensure_dirs():
    """确保目录存在"""
    global _ensure_dirs_done
    if _ensure_dirs_done:
        return
    os.makedirs(BACKUP_DIR, exist_ok=True)
    os.makedirs(f'{WORKSPACE}/ultron-workflow/logs', exist_ok=True)
    _ensure_dirs_done = True

def compute_hash(data):
    """计算数据哈希用于验证"""
    return hashlib.md5(json.dumps(data, sort_keys=True).encode()).hexdigest()[:8]

def save_checkpoint(state_data, force=False):
    """保存检查点（带压缩和验证）"""
    with _lock:
        ensure_dirs()
        
        checkpoint = {
            'state': state_data,
            'timestamp': datetime.now().isoformat(),
            'hash': compute_hash(state_data)
        }
        
        with open(CHECKPOINT_FILE, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        return checkpoint

def load_checkpoint():
    """加载检查点"""
    if os.path.exists(CHECKPOINT_FILE):
        try:
            with open(CHECKPOINT_FILE) as f:
                return json.load(f)
        except:
            pass
    return None

def verify_checkpoint(checkpoint):
    """验证检查点完整性"""
    if not checkpoint or 'state' not in checkpoint:
        return False
    expected_hash = compute_hash(checkpoint['state'])
    return checkpoint.get('hash') == expected_hash

def save_execution_log(task_name, status, details=None):
    """保存任务执行日志"""
    ensure_dirs()
    
    log_entry = {
        'task': task_name,
        'status': status,
        'timestamp': datetime.now().isoformat(),
        'details': details or {}
    }
    
    # 读取现有日志
    logs = []
    if os.path.exists(EXECUTION_LOG):
        try:
            with open(EXECUTION_LOG) as f:
                logs = json.load(f)
        except:
            logs = []
    
    logs.append(log_entry)
    
    # 只保留最近100条
    if len(logs) > 100:
        logs = logs[-100:]
    
    with open(EXECUTION_LOG, 'w') as f:
        json.dump(logs, f, indent=2)

def get_execution_history(task_name=None, limit=10):
    """获取执行历史"""
    if not os.path.exists(EXECUTION_LOG):
        return []
    
    try:
        with open(EXECUTION_LOG) as f:
            logs = json.load(f)
        
        if task_name:
            logs = [l for l in logs if l.get('task') == task_name]
        
        return logs[-limit:]
    except:
        return []

def backup_state():
    """备份当前状态"""
    ensure_dirs()
    
    tasks_file = f'{WORKSPACE}/ultron-workflow/scheduler_state.json'
    if os.path.exists(tasks_file):
        backup_file = f'{BACKUP_DIR}/state_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
        shutil.copy2(tasks_file, backup_file)
        
        # 只保留最近MAX_BACKUPS个备份
        backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('state_')])
        while len(backups) > MAX_BACKUPS:
            os.remove(f'{BACKUP_DIR}/{backups[0]}')
            backups.pop(0)
        
        return backup_file
    return None

def restore_state(target_file=None):
    """恢复最近的状态"""
    ensure_dirs()
    
    if not os.path.exists(BACKUP_DIR):
        return None
    
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('state_')])
    if not backups:
        return None
    
    latest = target_file or f'{BACKUP_DIR}/{backups[-1]}'
    if not os.path.exists(latest):
        return None
    
    tasks_file = f'{WORKSPACE}/ultron-workflow/scheduler_state.json'
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

def check_crash_recovery_needed():
    """检查是否需要崩溃恢复"""
    checkpoint = load_checkpoint()
    if checkpoint and verify_checkpoint(checkpoint):
        state = checkpoint.get('state', {})
        last_save = state.get('last_save')
        
        if last_save:
            try:
                last_time = datetime.fromisoformat(last_save)
                # 如果超过5分钟没有保存检查点，可能需要恢复
                if (datetime.now() - last_time).total_seconds() > 300:
                    return True
            except:
                pass
    return False

def perform_recovery():
    """执行崩溃恢复"""
    print("[scheduler_persist] 检测到可能需要崩溃恢复")
    
    checkpoint = load_checkpoint()
    if checkpoint and verify_checkpoint(checkpoint):
        print(f"[scheduler_persist] 从检查点恢复: {checkpoint.get('timestamp')}")
        return checkpoint.get('state')
    
    # 尝试从备份恢复
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('state_')])
    if backups:
        latest = f'{BACKUP_DIR}/{backups[-1]}'
        print(f"[scheduler_persist] 从备份恢复: {latest}")
        try:
            with open(latest) as f:
                return json.load(f)
        except:
            pass
    
    return None

def get_recovery_status():
    """获取恢复状态"""
    ensure_dirs()
    
    backups = sorted([f for f in os.listdir(BACKUP_DIR) if f.startswith('state_')])
    checkpoint = load_checkpoint()
    
    return {
        'backup_count': len(backups),
        'latest_backup': backups[-1] if backups else None,
        'checkpoint_valid': verify_checkpoint(checkpoint) if checkpoint else False,
        'checkpoint_timestamp': checkpoint.get('timestamp') if checkpoint else None,
        'persist_file_exists': os.path.exists(PERSIST_FILE),
        'persist_data': load_persist_state(),
        'crash_recovery_needed': check_crash_recovery_needed()
    }

# 定时备份线程
class BackupThread(threading.Thread):
    def __init__(self, interval=300):
        super().__init__(daemon=True)
        self.interval = interval
        self.running = True
    
    def run(self):
        while self.running:
            try:
                backup_state()
                print(f"[scheduler_persist] 定时备份完成")
            except Exception as e:
                print(f"[scheduler_persist] 备份失败: {e}")
            for _ in range(self.interval):
                if not self.running:
                    break
                import time
                time.sleep(1)
    
    def stop(self):
        self.running = False

if __name__ == '__main__':
    # 测试持久化功能
    print("=== 调度器持久化与恢复机制 V2 ===\n")
    
    # 1. 保存检查点
    test_state = {
        'tasks': {'test': {'status': 'active'}},
        'last_save': datetime.now().isoformat(),
        'incarnation': 139
    }
    checkpoint = save_checkpoint(test_state)
    print(f"✓ 检查点已保存: {checkpoint['hash']}")
    
    # 2. 验证检查点
    loaded = load_checkpoint()
    print(f"✓ 检查点验证: {'通过' if verify_checkpoint(loaded) else '失败'}")
    
    # 3. 保存执行日志
    save_execution_log('test_task', 'success', {'duration': 1.5})
    print("✓ 执行日志已保存")
    
    # 4. 获取恢复状态
    status = get_recovery_status()
    print(f"✓ 恢复状态: {status['crash_recovery_needed']}")
    
    # 5. 测试崩溃恢复
    if check_crash_recovery_needed():
        recovered = perform_recovery()
        print(f"✓ 崩溃恢复: {'成功' if recovered else '失败'}")
    else:
        print("✓ 无需崩溃恢复")
    
    print("\n=== 调度器持久化与恢复机制 V2 测试完成 ===")
