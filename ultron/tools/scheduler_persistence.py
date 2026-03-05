#!/usr/bin/env python3
"""
调度器持久化与恢复机制
Scheduler Persistence and Recovery Mechanism

功能:
- 状态自动备份与恢复
- 执行进度持久化
- 崩溃恢复支持
- 状态版本管理
"""
import json
import os
import shutil
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

WORKSPACE = "/root/.openclaw/workspace"
SCHEDULER_STATE = f"{WORKSPACE}/ultron-workflow/scheduler_state.json"
SCHEDULER_BACKUP_DIR = f"{WORKSPACE}/ultron-workflow/backup"
SCHEDULER_CHECKPOINT = f"{WORKSPACE}/ultron-workflow/scheduler_checkpoint.json"
SCHEDULER_HISTORY = f"{WORKSPACE}/ultron-workflow/scheduler_history.json"


class SchedulerPersistence:
    """调度器持久化与恢复管理器"""
    
    def __init__(self):
        self.backup_dir = Path(SCHEDULER_BACKUP_DIR)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.max_backups = 10  # 最多保留10个备份
        self.checkpoint_interval = 60  # 每60秒保存检查点
        
    def get_state_hash(self, state: Dict) -> str:
        """计算状态哈希值"""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()[:8]
    
    def load_state(self) -> Dict:
        """加载状态，支持多种回退策略"""
        # 1. 尝试加载检查点
        if os.path.exists(SCHEDULER_CHECKPOINT):
            try:
                with open(SCHEDULER_CHECKPOINT, 'r') as f:
                    checkpoint = json.load(f)
                if self._validate_checkpoint(checkpoint):
                    print(f"   ✓ 从检查点恢复: {checkpoint.get('timestamp', 'unknown')}")
                    return checkpoint.get("state", {})
            except Exception as e:
                print(f"   ! 检查点加载失败: {e}")
        
        # 2. 尝试加载主状态
        if os.path.exists(SCHEDULER_STATE):
            try:
                with open(SCHEDULER_STATE, 'r') as f:
                    state = json.load(f)
                print(f"   ✓ 从主状态文件加载")
                return state
            except Exception as e:
                print(f"   ! 主状态加载失败: {e}")
        
        # 3. 尝试从备份恢复
        backup_state = self._load_latest_backup()
        if backup_state:
            print(f"   ✓ 从最新备份恢复")
            return backup_state
        
        # 4. 返回空状态
        return {
            "tasks": {},
            "last_scan": None,
            "adjustments": [],
            "checkpoints": [],
            "recovery_info": {"source": "empty", "timestamp": datetime.now().isoformat()}
        }
    
    def _load_latest_backup(self) -> Optional[Dict]:
        """加载最新的备份"""
        backups = sorted(self.backup_dir.glob("scheduler_state_*.bak"), 
                        key=lambda x: x.stat().st_mtime, reverse=True)
        for backup in backups:
            try:
                with open(backup, 'r') as f:
                    return json.load(f)
            except:
                continue
        return None
    
    def _validate_checkpoint(self, checkpoint: Dict) -> bool:
        """验证检查点有效性"""
        if not checkpoint.get("state"):
            return False
        
        # 检查时间戳不应太旧（超过1小时）
        try:
            ts = datetime.fromisoformat(checkpoint.get("timestamp", ""))
            age = (datetime.now() - ts).total_seconds()
            return age < 3600  # 1小时内有效
        except:
            return False
    
    def save_state(self, state: Dict, force_backup: bool = False):
        """保存状态，支持检查点和备份"""
        state["last_save"] = datetime.now().isoformat()
        
        # 1. 保存到主状态文件
        with open(SCHEDULER_STATE, 'w') as f:
            json.dump(state, f, indent=2)
        
        # 2. 定期保存检查点
        if force_backup or not os.path.exists(SCHEDULER_CHECKPOINT):
            with open(SCHEDULER_CHECKPOINT, 'w') as f:
                json.dump({
                    "state": state,
                    "timestamp": datetime.now().isoformat(),
                    "hash": self.get_state_hash(state)
                }, f, indent=2)
        
        # 3. 定期创建备份
        if force_backup or self._should_create_backup(state):
            self._create_backup(state)
        
        return True
    
    def _should_create_backup(self, state: Dict) -> bool:
        """判断是否需要创建备份"""
        # 检查是否存在备份
        if not os.path.exists(SCHEDULER_STATE):
            return True
        
        try:
            # 读取当前哈希
            current_hash = self.get_state_hash(state)
            
            # 检查是否与上次备份不同
            last_backup = self._get_latest_backup_info()
            if last_backup and last_backup.get("hash") != current_hash:
                return True
        except:
            pass
        
        return False
    
    def _get_latest_backup_info(self) -> Optional[Dict]:
        """获取最新备份信息"""
        backups = sorted(self.backup_dir.glob("scheduler_state_*.bak"),
                        key=lambda x: x.stat().st_mtime, reverse=True)
        if backups:
            try:
                with open(backups[0], 'r') as f:
                    data = json.load(f)
                    return {"hash": data.get("hash"), "time": data.get("timestamp")}
            except:
                pass
        return None
    
    def _create_backup(self, state: Dict):
        """创建状态备份"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"scheduler_state_{timestamp}.bak"
        
        backup_data = {
            "state": state,
            "timestamp": datetime.now().isoformat(),
            "hash": self.get_state_hash(state)
        }
        
        with open(backup_file, 'w') as f:
            json.dump(backup_data, f, indent=2)
        
        # 清理旧备份
        self._cleanup_old_backups()
        
        print(f"   ✓ 创建备份: {backup_file.name}")
    
    def _cleanup_old_backups(self):
        """清理旧备份"""
        backups = sorted(self.backup_dir.glob("scheduler_state_*.bak"),
                        key=lambda x: x.stat().st_mtime, reverse=True)
        
        for old_backup in backups[self.max_backups:]:
            old_backup.unlink()
            print(f"   - 删除旧备份: {old_backup.name}")
    
    def save_checkpoint(self, state: Dict, metadata: Dict = None):
        """保存执行检查点"""
        checkpoint = {
            "state": state,
            "timestamp": datetime.now().isoformat(),
            "hash": self.get_state_hash(state),
            "metadata": metadata or {}
        }
        
        with open(SCHEDULER_CHECKPOINT, 'w') as f:
            json.dump(checkpoint, f, indent=2)
        
        return True
    
    def record_execution(self, state: Dict, execution: Dict):
        """记录执行历史"""
        history_file = Path(SCHEDULER_HISTORY)
        
        # 加载或初始化历史
        if history_file.exists():
            try:
                with open(history_file, 'r') as f:
                    history = json.load(f)
            except:
                history = {"executions": []}
        else:
            history = {"executions": []}
        
        # 添加新执行记录
        history["executions"].append({
            "timestamp": datetime.now().isoformat(),
            "execution": execution,
            "state_hash": self.get_state_hash(state)
        })
        
        # 只保留最近100条记录
        history["executions"] = history["executions"][-100:]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
    
    def get_recovery_info(self) -> Dict:
        """获取恢复信息"""
        info = {
            "has_checkpoint": os.path.exists(SCHEDULER_CHECKPOINT),
            "has_main_state": os.path.exists(SCHEDULER_STATE),
            "backup_count": len(list(self.backup_dir.glob("scheduler_state_*.bak"))),
            "last_backup": None,
            "last_checkpoint": None
        }
        
        # 获取最新备份时间
        backups = sorted(self.backup_dir.glob("scheduler_state_*.bak"),
                        key=lambda x: x.stat().st_mtime, reverse=True)
        if backups:
            info["last_backup"] = datetime.fromtimestamp(backups[0].stat().st_mtime).isoformat()
        
        # 获取检查点时间
        if os.path.exists(SCHEDULER_CHECKPOINT):
            try:
                with open(SCHEDULER_CHECKPOINT, 'r') as f:
                    cp = json.load(f)
                    info["last_checkpoint"] = cp.get("timestamp")
            except:
                pass
        
        return info
    
    def recover_from_crash(self) -> Dict:
        """从崩溃中恢复"""
        print("\n🔄 执行崩溃恢复...")
        
        recovered_state = None
        recovery_source = "none"
        
        # 1. 尝试检查点恢复
        if os.path.exists(SCHEDULER_CHECKPOINT):
            try:
                with open(SCHEDULER_CHECKPOINT, 'r') as f:
                    checkpoint = json.load(f)
                if self._validate_checkpoint(checkpoint):
                    recovered_state = checkpoint.get("state", {})
                    recovery_source = "checkpoint"
            except Exception as e:
                print(f"   ! 检查点恢复失败: {e}")
        
        # 2. 尝试主状态恢复
        if not recovered_state and os.path.exists(SCHEDULER_STATE):
            try:
                with open(SCHEDULER_STATE, 'r') as f:
                    recovered_state = json.load(f)
                    recovery_source = "main_state"
            except Exception as e:
                print(f"   ! 主状态恢复失败: {e}")
        
        # 3. 尝试备份恢复
        if not recovered_state:
            recovered_state = self._load_latest_backup()
            if recovered_state:
                recovery_source = "backup"
        
        # 添加恢复元数据
        if recovered_state:
            recovered_state["recovery_info"] = {
                "source": recovery_source,
                "recovered_at": datetime.now().isoformat(),
                "was_crashed": True
            }
            print(f"   ✓ 恢复成功: 来自 {recovery_source}")
        
        return {
            "recovered": recovered_state is not None,
            "source": recovery_source,
            "state": recovered_state or {}
        }


# 独立函数供外部调用
def load_scheduler_state() -> Dict:
    """加载调度器状态"""
    persistence = SchedulerPersistence()
    return persistence.load_state()


def save_scheduler_state(state: Dict, force_backup: bool = False):
    """保存调度器状态"""
    persistence = SchedulerPersistence()
    return persistence.save_state(state, force_backup)


def recover_scheduler() -> Dict:
    """恢复调度器状态"""
    persistence = SchedulerPersistence()
    return persistence.recover_from_crash()


def get_scheduler_recovery_info() -> Dict:
    """获取调度器恢复信息"""
    persistence = SchedulerPersistence()
    return persistence.get_recovery_info()


if __name__ == "__main__":
    # 测试
    print("=== 调度器持久化机制测试 ===\n")
    
    persistence = SchedulerPersistence()
    
    # 1. 显示恢复信息
    print("📊 恢复信息:")
    info = persistence.get_recovery_info()
    for k, v in info.items():
        print(f"   {k}: {v}")
    
    # 2. 测试崩溃恢复
    print("\n🔄 测试崩溃恢复:")
    result = persistence.recover_from_crash()
    print(f"   恢复结果: {result}")
    
    # 3. 保存测试状态
    test_state = {
        "tasks": {"test_task": {"status": "active"}},
        "last_scan": datetime.now().isoformat(),
        "adjustments": [],
        "test_mode": True
    }
    print("\n💾 保存测试状态:")
    persistence.save_state(test_state, force_backup=True)
    
    print("\n✅ 测试完成")