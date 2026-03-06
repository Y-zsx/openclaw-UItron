#!/usr/bin/env python3
"""
Agent任务调度与队列管理系统
功能:
  - 任务优先级管理
  - 任务依赖管理
  - 任务超时与重试策略
  - 调度可视化Dashboard
  - 队列监控API
"""

import json
import os
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from enum import IntEnum

# 配置路径
AGENT_DIR = Path(__file__).parent
QUEUE_MANAGER_DIR = Path(__file__).parent
QUEUE_STATE_FILE = QUEUE_MANAGER_DIR / "queue-manager-state.json"
QUEUE_DATA_FILE = QUEUE_MANAGER_DIR / "queue-data.json"
PRIORITY_CONFIG_FILE = QUEUE_MANAGER_DIR / "priority-config.json"

class Priority(IntEnum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5

class TaskStatus:
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

def load_queue_state():
    """加载队列管理器状态"""
    if QUEUE_STATE_FILE.exists():
        with open(QUEUE_STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "status": "running",
        "last_heartbeat": datetime.now().isoformat(),
        "last_update": datetime.now().isoformat(),
        "stats": {
            "total_tasks": 0,
            "completed_tasks": 0,
            "failed_tasks": 0,
            "running_tasks": 0,
            "pending_tasks": 0
        }
    }

def save_queue_state(state):
    """保存队列管理器状态"""
    state["last_heartbeat"] = datetime.now().isoformat()
    state["last_update"] = datetime.now().isoformat()
    with open(QUEUE_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_queue_data():
    """加载队列数据"""
    if QUEUE_DATA_FILE.exists():
        with open(QUEUE_DATA_FILE, 'r') as f:
            return json.load(f)
    return {
        "tasks": {},
        "waiting": [],
        "ready": [],
        "running": [],
        "completed": [],
        "failed": [],
        "dependencies": {}
    }

def save_queue_data(data):
    """保存队列数据"""
    with open(QUEUE_DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_priority_config():
    """加载优先级配置"""
    if PRIORITY_CONFIG_FILE.exists():
        with open(PRIORITY_CONFIG_FILE, 'r') as f:
            return json.load(f)
    # 默认配置
    default = {
        "priorities": {
            "critical": 1,
            "high": 2,
            "normal": 3,
            "low": 4,
            "background": 5
        },
        "retry_policy": {
            "max_retries": 3,
            "retry_delay": 5,
            "backoff_multiplier": 2,
            "timeout_default": 300
        },
        "scheduling": {
            "max_concurrent": 5,
            "queue_check_interval": 1
        }
    }
    with open(PRIORITY_CONFIG_FILE, 'w') as f:
        json.dump(default, f, indent=2)
    return default

def create_task(task_def: Dict) -> str:
    """创建新任务"""
    queue_data = load_queue_data()
    priority_config = load_priority_config()
    
    task_id = task_def.get("task_id", str(uuid.uuid4()))
    
    # 解析优先级
    priority = task_def.get("priority", "normal")
    if isinstance(priority, str):
        priority = priority_config["priorities"].get(priority, 3)
    
    # 解析超时
    timeout = task_def.get("timeout", priority_config["retry_policy"]["timeout_default"])
    
    # 解析重试
    max_retries = task_def.get("max_retries", priority_config["retry_policy"]["max_retries"])
    
    task = {
        "task_id": task_id,
        "name": task_def.get("name", f"task-{task_id[:8]}"),
        "type": task_def.get("type", "execute"),
        "payload": task_def.get("payload", {}),
        "priority": priority,
        "status": TaskStatus.PENDING,
        "created_at": datetime.now().isoformat(),
        "started_at": None,
        "completed_at": None,
        "timeout": timeout,
        "max_retries": max_retries,
        "retry_count": 0,
        "dependencies": task_def.get("dependencies", []),
        "result": None,
        "error": None,
        "metadata": task_def.get("metadata", {})
    }
    
    queue_data["tasks"][task_id] = task
    
    # 处理依赖
    if task["dependencies"]:
        queue_data["dependencies"][task_id] = task["dependencies"]
        queue_data["waiting"].append(task_id)
    else:
        queue_data["ready"].append(task_id)
    
    # 按优先级排序
    queue_data["ready"].sort(key=lambda tid: queue_data["tasks"][tid]["priority"])
    
    save_queue_data(queue_data)
    
    # 更新统计
    state = load_queue_state()
    state["stats"]["total_tasks"] += 1
    state["stats"]["pending_tasks"] = len(queue_data["ready"]) + len(queue_data["waiting"])
    save_queue_state(state)
    
    return task_id

def check_dependencies(task_id: str) -> bool:
    """检查任务依赖是否满足"""
    queue_data = load_queue_data()
    deps = queue_data["dependencies"].get(task_id, [])
    
    for dep_id in deps:
        task = queue_data["tasks"].get(dep_id)
        if not task or task["status"] != TaskStatus.COMPLETED:
            return False
    
    return True

def get_next_task() -> Optional[Dict]:
    """获取下一个可执行任务"""
    queue_data = load_queue_data()
    priority_config = load_priority_config()
    
    # 移动已就绪的任务
    waiting = queue_data["waiting"][:]
    for task_id in waiting:
        if check_dependencies(task_id):
            queue_data["waiting"].remove(task_id)
            if task_id not in queue_data["ready"]:
                queue_data["ready"].append(task_id)
    
    # 按优先级排序
    queue_data["ready"].sort(key=lambda tid: queue_data["tasks"][tid]["priority"])
    
    if not queue_data["ready"]:
        return None
    
    # 获取最高优先级任务
    task_id = queue_data["ready"].pop(0)
    task = queue_data["tasks"][task_id]
    
    # 检查并发限制
    max_concurrent = priority_config["scheduling"]["max_concurrent"]
    if len(queue_data["running"]) >= max_concurrent:
        queue_data["ready"].insert(0, task_id)
        return None
    
    # 启动任务
    task["status"] = TaskStatus.RUNNING
    task["started_at"] = datetime.now().isoformat()
    queue_data["running"].append(task_id)
    
    save_queue_data(queue_data)
    
    return task

def complete_task(task_id: str, result: Any = None, error: str = None):
    """完成任务"""
    queue_data = load_queue_data()
    state = load_queue_state()
    
    task = queue_data["tasks"].get(task_id)
    if not task:
        return
    
    if error:
        # 失败处理
        task["retry_count"] += 1
        if task["retry_count"] < task["max_retries"]:
            # 重试
            task["status"] = TaskStatus.PENDING
            task["error"] = error
            queue_data["ready"].append(task_id)
        else:
            # 最终失败
            task["status"] = TaskStatus.FAILED
            task["error"] = error
            queue_data["failed"].append(task_id)
            state["stats"]["failed_tasks"] += 1
    else:
        # 成功完成
        task["status"] = TaskStatus.COMPLETED
        task["completed_at"] = datetime.now().isoformat()
        task["result"] = result
        queue_data["completed"].append(task_id)
        state["stats"]["completed_tasks"] += 1
    
    # 从运行中移除
    if task_id in queue_data["running"]:
        queue_data["running"].remove(task_id)
    
    save_queue_data(queue_data)
    
    state["stats"]["running_tasks"] = len(queue_data["running"])
    state["stats"]["pending_tasks"] = len(queue_data["ready"]) + len(queue_data["waiting"])
    save_queue_state(state)

def cancel_task(task_id: str) -> bool:
    """取消任务"""
    queue_data = load_queue_data()
    
    task = queue_data["tasks"].get(task_id)
    if not task:
        return False
    
    if task["status"] == TaskStatus.RUNNING:
        return False  # 运行中的任务无法取消
    
    task["status"] = TaskStatus.CANCELLED
    
    # 从队列中移除
    for queue in [queue_data["ready"], queue_data["waiting"]]:
        if task_id in queue:
            queue.remove(task_id)
    
    save_queue_data(queue_data)
    return True

def get_queue_status() -> Dict:
    """获取队列状态"""
    queue_data = load_queue_data()
    queue_state = load_queue_state()
    priority_config = load_priority_config()
    
    return {
        "status": queue_state["status"],
        "stats": queue_state["stats"],
        "config": {
            "max_concurrent": priority_config["scheduling"]["max_concurrent"],
            "default_timeout": priority_config["retry_policy"]["timeout_default"],
            "max_retries": priority_config["retry_policy"]["max_retries"]
        },
        "queues": {
            "waiting": len(queue_data["waiting"]),
            "ready": len(queue_data["ready"]),
            "running": len(queue_data["running"]),
            "completed": len(queue_data["completed"]),
            "failed": len(queue_data["failed"])
        }
    }

def get_task_detail(task_id: str) -> Optional[Dict]:
    """获取任务详情"""
    queue_data = load_queue_data()
    return queue_data["tasks"].get(task_id)

def get_tasks_by_status(status: str, limit: int = 50) -> List[Dict]:
    """按状态获取任务列表"""
    queue_data = load_queue_data()
    
    status_map = {
        "pending": queue_data["ready"],
        "running": queue_data["running"],
        "completed": queue_data["completed"],
        "failed": queue_data["failed"]
    }
    
    task_ids = status_map.get(status, [])[-limit:]
    return [queue_data["tasks"][tid] for tid in task_ids if tid in queue_data["tasks"]]

def update_config(config: Dict):
    """更新配置"""
    priority_config = load_priority_config()
    priority_config.update(config)
    with open(PRIORITY_CONFIG_FILE, 'w') as f:
        json.dump(priority_config, f, indent=2)

def get_stats_summary(hours: int = 24) -> Dict:
    """获取统计摘要"""
    queue_data = load_queue_data()
    queue_state = load_queue_state()
    
    # 计算平均执行时间
    completed_tasks = [queue_data["tasks"][tid] for tid in queue_data["completed"] 
                       if tid in queue_data["tasks"]]
    
    durations = []
    for task in completed_tasks:
        if task["started_at"] and task.get("completed_at"):
            start = datetime.fromisoformat(task["started_at"])
            end = datetime.fromisoformat(task["completed_at"])
            durations.append((end - start).total_seconds())
    
    avg_duration = sum(durations) / len(durations) if durations else 0
    
    return {
        "total_tasks": queue_state["stats"]["total_tasks"],
        "completed": queue_state["stats"]["completed_tasks"],
        "failed": queue_state["stats"]["failed_tasks"],
        "running": queue_state["stats"]["running_tasks"],
        "pending": queue_state["stats"]["pending_tasks"],
        "success_rate": (queue_state["stats"]["completed_tasks"] / 
                         max(1, queue_state["stats"]["total_tasks"]) * 100),
        "avg_duration_seconds": avg_duration,
        "as_of": datetime.now().isoformat()
    }

def main():
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: queue_manager.py <command> [args...]"}))
        return
    
    cmd = sys.argv[1]
    
    if cmd == "create":
        task_def = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        task_id = create_task(task_def)
        print(json.dumps({"task_id": task_id, "status": "created"}))
        
    elif cmd == "next":
        task = get_next_task()
        print(json.dumps(task if task else {"status": "no_task"}))
        
    elif cmd == "complete":
        task_id = sys.argv[2] if len(sys.argv) > 2 else ""
        result = json.loads(sys.argv[3]) if len(sys.argv) > 3 else None
        error = sys.argv[4] if len(sys.argv) > 4 else None
        complete_task(task_id, result, error)
        print(json.dumps({"task_id": task_id, "status": "completed"}))
        
    elif cmd == "cancel":
        task_id = sys.argv[2] if len(sys.argv) > 2 else ""
        success = cancel_task(task_id)
        print(json.dumps({"success": success}))
        
    elif cmd == "status":
        print(json.dumps(get_queue_status()))
        
    elif cmd == "stats":
        print(json.dumps(get_stats_summary()))
        
    elif cmd == "task":
        task_id = sys.argv[2] if len(sys.argv) > 2 else ""
        print(json.dumps(get_task_detail(task_id) or {"error": "not_found"}))
        
    elif cmd == "list":
        status = sys.argv[2] if len(sys.argv) > 2 else "pending"
        limit = int(sys.argv[3]) if len(sys.argv) > 3 else 50
        print(json.dumps(get_tasks_by_status(status, limit)))
        
    elif cmd == "config":
        action = sys.argv[2] if len(sys.argv) > 2 else "get"
        if action == "get":
            print(json.dumps(load_priority_config()))
        else:
            config = json.loads(sys.argv[3]) if len(sys.argv) > 3 else {}
            update_config(config)
            print(json.dumps({"status": "updated"}))
        
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))

if __name__ == "__main__":
    main()