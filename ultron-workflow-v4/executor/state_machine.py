"""
状态机 (State Machine)
========================
管理任务执行状态和转换。

状态:
  pending -> ready -> running -> done
                \-> waiting_retry -> running
                      \
                       -> failed
"""

import json
from pathlib import Path
from datetime import datetime
from enum import Enum


class TaskState(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    WAITING_RETRY = "waiting_retry"


class StateMachine:
    """任务状态机"""
    
    def __init__(self, state_file: str, max_retries: int = 3):
        self.state_file = Path(state_file)
        self.max_retries = max_retries
        self.states = {}
        self._load()
    
    def _load(self):
        if self.state_file.exists():
            with open(self.state_file) as f:
                self.states = json.load(f)
    
    def _save(self):
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.states, f, indent=2)
    
    def create_task(self, task_id: str, task_type: str, metadata: dict = None):
        """创建新任务"""
        self.states[task_id] = {
            "id": task_id,
            "type": task_type,
            "status": TaskState.PENDING.value,
            "created_at": datetime.now().isoformat(),
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "retry_count": 0,
            "metadata": metadata or {}
        }
        self._save()
    
    def transition(self, task_id: str, new_state: TaskState, result: str = None, error: str = None):
        """状态转换"""
        if task_id not in self.states:
            return False
        
        old_state = self.states[task_id]["status"]
        self.states[task_id]["status"] = new_state.value
        
        if new_state == TaskState.RUNNING:
            self.states[task_id]["started_at"] = datetime.now().isoformat()
        
        if new_state in [TaskState.DONE, TaskState.FAILED]:
            self.states[task_id]["completed_at"] = datetime.now().isoformat()
            self.states[task_id]["result"] = result
            self.states[task_id]["error"] = error
        
        if new_state == TaskState.FAILED:
            self.states[task_id]["retry_count"] += 1
        
        self._save()
        print(f"[StateMachine] {task_id}: {old_state} -> {new_state.value}")
        return True
    
    def can_retry(self, task_id: str) -> bool:
        """检查是否可以重试"""
        if task_id not in self.states:
            return False
        return self.states[task_id]["retry_count"] < self.max_retries
    
    def get_task(self, task_id: str) -> dict:
        """获取任务状态"""
        return self.states.get(task_id)
    
    def get_tasks_by_status(self, status: TaskState) -> list:
        """获取指定状态的所有任务"""
        return [t for t in self.states.values() if t["status"] == status.value]
    
    def get_pending_count(self) -> int:
        """获取待执行任务数"""
        return len(self.get_tasks_by_status(TaskState.PENDING)) + \
               len(self.get_tasks_by_status(TaskState.READY))
    
    def clear_completed(self, before_days: int = 7):
        """清理已完成任务"""
        cutoff = datetime.now().timestamp() - before_days * 86400
        to_remove = []
        
        for task_id, task in self.states.items():
            if task["status"] in [TaskState.DONE.value, TaskState.FAILED.value]:
                if task.get("completed_at"):
                    completed_ts = datetime.fromisoformat(task["completed_at"]).timestamp()
                    if completed_ts < cutoff:
                        to_remove.append(task_id)
        
        for task_id in to_remove:
            del self.states[task_id]
        
        if to_remove:
            self._save()
            print(f"[StateMachine] 清理了 {len(to_remove)} 个已完成任务")


if __name__ == "__main__":
    # 测试
    sm = StateMachine("/tmp/state_machine.json")
    
    # 创建任务
    sm.create_task("task_1", "monitor", {"target": "website"})
    
    # 状态转换
    sm.transition("task_1", TaskState.READY)
    sm.transition("task_1", TaskState.RUNNING)
    sm.transition("task_1", TaskState.DONE, result="一切正常")
    
    print("任务状态:", sm.get_task("task_1"))