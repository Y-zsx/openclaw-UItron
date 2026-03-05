#!/usr/bin/env python3
"""
Agent协作工作流引擎与状态管理
第59世: 实现工作流状态持久化、恢复、监控

核心功能:
- WorkflowStateManager: 工作流状态持久化与管理
- WorkflowRecovery: 工作流故障恢复机制
- WorkflowMonitor: 工作流执行监控与统计
"""

import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import logging

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(AGENTS_DIR, "workflow_state.db")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("workflow-state-manager")


class WorkflowStatus(Enum):
    """工作流状态"""
    CREATED = "created"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RECOVERING = "recovering"


class TaskState(Enum):
    """任务状态"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


@dataclass
class WorkflowState:
    """工作流状态"""
    workflow_id: str
    name: str
    status: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    current_task: Optional[str] = None
    progress: float = 0.0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    context: Dict = field(default_factory=dict)
    metadata: Dict = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class TaskStateRecord:
    """任务状态记录"""
    task_id: str
    workflow_id: str
    name: str
    state: str
    attempts: int = 0
    max_attempts: int = 3
    timeout: float = 60.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)


class WorkflowStateManager:
    """工作流状态管理器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or DB_PATH
        self._lock = threading.Lock()
        self._init_database()
        self._callbacks: Dict[str, List[Callable]] = {
            "workflow_created": [],
            "workflow_started": [],
            "workflow_completed": [],
            "workflow_failed": [],
            "task_started": [],
            "task_completed": [],
            "task_failed": [],
            "workflow_paused": [],
            "workflow_resumed": [],
        }
    
    def _init_database(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 工作流表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflows (
                workflow_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                current_task TEXT,
                progress REAL DEFAULT 0.0,
                total_tasks INTEGER DEFAULT 0,
                completed_tasks INTEGER DEFAULT 0,
                failed_tasks INTEGER DEFAULT 0,
                context TEXT,
                metadata TEXT,
                error TEXT
            )
        """)
        
        # 任务状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_states (
                task_id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                name TEXT NOT NULL,
                state TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 3,
                timeout REAL DEFAULT 60.0,
                started_at TEXT,
                completed_at TEXT,
                result TEXT,
                error TEXT,
                dependencies TEXT,
                FOREIGN KEY (workflow_id) REFERENCES workflows(workflow_id)
            )
        """)
        
        # 工作流历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                duration REAL,
                tasks_total INTEGER,
                tasks_completed INTEGER,
                tasks_failed INTEGER
            )
        """)
        
        # 事件日志表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS workflow_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workflow_id TEXT NOT NULL,
                task_id TEXT,
                event_type TEXT NOT NULL,
                event_data TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        logger.info(f"工作流状态数据库初始化完成: {self.db_path}")
    
    # ========== 工作流状态管理 ==========
    
    def create_workflow(self, name: str, workflow_id: str = None, 
                        context: Dict = None, metadata: Dict = None) -> str:
        """创建工作流"""
        with self._lock:
            workflow_id = workflow_id or str(uuid.uuid4())
            now = datetime.now().isoformat()
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO workflows (workflow_id, name, status, created_at, 
                                     context, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (workflow_id, name, WorkflowStatus.CREATED.value, now,
                  json.dumps(context or {}), json.dumps(metadata or {})))
            
            conn.commit()
            conn.close()
            
            self._emit_event("workflow_created", {"workflow_id": workflow_id, "name": name})
            logger.info(f"创建工作流: {workflow_id} - {name}")
            return workflow_id
    
    def start_workflow(self, workflow_id: str) -> bool:
        """启动工作流"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE workflows SET status = ?, started_at = ?
                WHERE workflow_id = ?
            """, (WorkflowStatus.RUNNING.value, datetime.now().isoformat(), workflow_id))
            
            conn.commit()
            conn.close()
            
            self._emit_event("workflow_started", {"workflow_id": workflow_id})
            logger.info(f"启动工作流: {workflow_id}")
            return True
    
    def complete_workflow(self, workflow_id: str, error: str = None) -> bool:
        """完成工作流"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            status = WorkflowStatus.FAILED.value if error else WorkflowStatus.COMPLETED.value
            now = datetime.now().isoformat()
            
            cursor.execute("""
                SELECT started_at, total_tasks, completed_tasks, failed_tasks 
                FROM workflows WHERE workflow_id = ?
            """, (workflow_id,))
            row = cursor.fetchone()
            
            if row:
                started_at, total, completed, failed = row
                progress = 100.0 if total > 0 else (completed / total * 100 if total > 0 else 0)
                
                cursor.execute("""
                    UPDATE workflows SET status = ?, completed_at = ?, 
                                        progress = ?, error = ?
                    WHERE workflow_id = ?
                """, (status, now, progress, error, workflow_id))
                
                # 记录到历史
                duration = None
                if started_at:
                    duration = (datetime.fromisoformat(now) - 
                               datetime.fromisoformat(started_at)).total_seconds()
                
                cursor.execute("""
                    INSERT INTO workflow_history 
                    (workflow_id, name, status, created_at, completed_at, 
                     duration, tasks_total, tasks_completed, tasks_failed)
                    SELECT workflow_id, name, ?, created_at, ?, ?, total_tasks, 
                           completed_tasks, failed_tasks
                    FROM workflows WHERE workflow_id = ?
                """, (status, now, duration, workflow_id))
            
            conn.commit()
            conn.close()
            
            event = "workflow_failed" if error else "workflow_completed"
            self._emit_event(event, {"workflow_id": workflow_id, "error": error})
            logger.info(f"{'失败' if error else '完成'}工作流: {workflow_id}")
            return True
    
    def pause_workflow(self, workflow_id: str) -> bool:
        """暂停工作流"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE workflows SET status = ?
                WHERE workflow_id = ?
            """, (WorkflowStatus.PAUSED.value, workflow_id))
            
            conn.commit()
            conn.close()
            
            self._emit_event("workflow_paused", {"workflow_id": workflow_id})
            logger.info(f"暂停工作流: {workflow_id}")
            return True
    
    def resume_workflow(self, workflow_id: str) -> bool:
        """恢复工作流"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE workflows SET status = ?
                WHERE workflow_id = ?
            """, (WorkflowStatus.RUNNING.value, workflow_id))
            
            conn.commit()
            conn.close()
            
            self._emit_event("workflow_resumed", {"workflow_id": workflow_id})
            logger.info(f"恢复工作流: {workflow_id}")
            return True
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        return self.complete_workflow(workflow_id, error="Cancelled by user")
    
    # ========== 任务状态管理 ==========
    
    def add_task(self, workflow_id: str, task_id: str, name: str,
                 dependencies: List[str] = None, timeout: float = 60.0,
                 max_attempts: int = 3) -> bool:
        """添加任务"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO task_states 
                (task_id, workflow_id, name, state, dependencies, timeout, max_attempts)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, workflow_id, name, TaskState.PENDING.value,
                  json.dumps(dependencies or []), timeout, max_attempts))
            
            # 更新工作流任务数
            cursor.execute("""
                UPDATE workflows SET total_tasks = total_tasks + 1
                WHERE workflow_id = ?
            """, (workflow_id,))
            
            conn.commit()
            conn.close()
            
            logger.info(f"添加任务: {task_id} -> {workflow_id}")
            return True
    
    def start_task(self, workflow_id: str, task_id: str) -> bool:
        """开始任务"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            cursor.execute("""
                UPDATE task_states SET state = ?, started_at = ?, attempts = attempts + 1
                WHERE task_id = ? AND workflow_id = ?
            """, (TaskState.RUNNING.value, now, task_id, workflow_id))
            
            cursor.execute("""
                UPDATE workflows SET current_task = ?
                WHERE workflow_id = ?
            """, (task_id, workflow_id))
            
            conn.commit()
            conn.close()
            
            self._emit_event("task_started", {"workflow_id": workflow_id, "task_id": task_id})
            return True
    
    def complete_task(self, workflow_id: str, task_id: str, 
                      result: Dict = None, error: str = None) -> bool:
        """完成任务"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            now = datetime.now().isoformat()
            state = TaskState.FAILED.value if error else TaskState.COMPLETED.value
            
            cursor.execute("""
                UPDATE task_states SET state = ?, completed_at = ?, result = ?, error = ?
                WHERE task_id = ? AND workflow_id = ?
            """, (state, now, json.dumps(result), error, task_id, workflow_id))
            
            # 更新工作流统计
            if error:
                cursor.execute("""
                    UPDATE workflows SET failed_tasks = failed_tasks + 1
                    WHERE workflow_id = ?
                """, (workflow_id,))
            else:
                cursor.execute("""
                    UPDATE workflows SET completed_tasks = completed_tasks + 1,
                                        progress = (completed_tasks + 1.0) / total_tasks * 100
                    WHERE workflow_id = ?
                """, (workflow_id,))
            
            conn.commit()
            conn.close()
            
            event = "task_failed" if error else "task_completed"
            self._emit_event(event, {"workflow_id": workflow_id, "task_id": task_id, "error": error})
            return True
    
    def block_task(self, workflow_id: str, task_id: str) -> bool:
        """阻塞任务"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                UPDATE task_states SET state = ?
                WHERE task_id = ? AND workflow_id = ?
            """, (TaskState.BLOCKED.value, task_id, workflow_id))
            
            conn.commit()
            conn.close()
            return True
    
    def unblock_tasks(self, workflow_id: str, completed_task_id: str) -> List[str]:
        """解除依赖该任务的其他任务的阻塞"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 查找依赖该任务的任务
            cursor.execute("""
                SELECT task_id FROM task_states 
                WHERE workflow_id = ? AND state = ? AND dependencies LIKE ?
            """, (workflow_id, TaskState.BLOCKED.value, f'%"{completed_task_id}"%'))
            
            blocked_tasks = [row[0] for row in cursor.fetchall()]
            
            # 解除阻塞
            for task_id in blocked_tasks:
                cursor.execute("""
                    UPDATE task_states SET state = ?
                    WHERE task_id = ? AND workflow_id = ?
                """, (TaskState.READY.value, task_id, workflow_id))
            
            conn.commit()
            conn.close()
            
            return blocked_tasks
    
    # ========== 查询接口 ==========
    
    def get_workflow_state(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM workflows WHERE workflow_id = ?", (workflow_id,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['context'] = json.loads(result.get('context', '{}'))
            result['metadata'] = json.loads(result.get('metadata', '{}'))
        else:
            result = None
        
        conn.close()
        return result
    
    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM task_states WHERE task_id = ?", (task_id,))
        row = cursor.fetchone()
        
        if row:
            result = dict(row)
            result['dependencies'] = json.loads(result.get('dependencies', '[]'))
            result['result'] = json.loads(result.get('result', 'null'))
        else:
            result = None
        
        conn.close()
        return result
    
    def list_workflows(self, status: str = None, limit: int = 50) -> List[Dict]:
        """列出工作流"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if status:
            cursor.execute("""
                SELECT * FROM workflows WHERE status = ? 
                ORDER BY created_at DESC LIMIT ?
            """, (status, limit))
        else:
            cursor.execute("""
                SELECT * FROM workflows ORDER BY created_at DESC LIMIT ?
            """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def list_tasks(self, workflow_id: str) -> List[Dict]:
        """列出工作流中的任务"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM task_states WHERE workflow_id = ? ORDER BY task_id
        """, (workflow_id,))
        
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result['dependencies'] = json.loads(result.get('dependencies', '[]'))
            result['result'] = json.loads(result.get('result') or 'null')
            results.append(result)
        
        conn.close()
        return results
    
    def get_workflow_history(self, limit: int = 50) -> List[Dict]:
        """获取工作流历史"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM workflow_history ORDER BY completed_at DESC LIMIT ?
        """, (limit,))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    # ========== 工作流恢复 ==========
    
    def get_recoverable_workflows(self) -> List[Dict]:
        """获取可恢复的工作流"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM workflows 
            WHERE status IN (?, ?, ?)
            ORDER BY started_at DESC
        """, (WorkflowStatus.RUNNING.value, WorkflowStatus.PAUSED.value, 
              WorkflowStatus.RECOVERING.value))
        
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def recover_workflow(self, workflow_id: str) -> bool:
        """恢复工作流"""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # 标记为恢复中
            cursor.execute("""
                UPDATE workflows SET status = ?
                WHERE workflow_id = ?
            """, (WorkflowStatus.RECOVERING.value, workflow_id))
            
            # 重置超时任务
            cursor.execute("""
                UPDATE task_states SET state = ?
                WHERE workflow_id = ? AND state = ? 
                AND attempts < max_attempts
            """, (TaskState.READY.value, workflow_id, TaskState.RUNNING.value))
            
            conn.commit()
            conn.close()
            
            logger.info(f"恢复工作流: {workflow_id}")
            return True
    
    # ========== 统计与监控 ==========
    
    def get_statistics(self) -> Dict:
        """获取工作流统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        stats = {}
        
        # 工作流统计
        cursor.execute("""
            SELECT status, COUNT(*) as count FROM workflows GROUP BY status
        """)
        stats['workflows_by_status'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 任务统计
        cursor.execute("""
            SELECT state, COUNT(*) as count FROM task_states GROUP BY state
        """)
        stats['tasks_by_state'] = {row[0]: row[1] for row in cursor.fetchall()}
        
        # 成功率
        cursor.execute("""
            SELECT COUNT(*) FROM workflows WHERE status = ?
        """, (WorkflowStatus.COMPLETED.value,))
        completed = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT COUNT(*) FROM workflows 
            WHERE status IN (?, ?)
        """, (WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value))
        total = cursor.fetchone()[0]
        
        stats['success_rate'] = (completed / total * 100) if total > 0 else 0
        
        # 平均执行时间
        cursor.execute("""
            SELECT AVG(duration) FROM workflow_history WHERE duration IS NOT NULL
        """)
        stats['avg_duration'] = cursor.fetchone()[0] or 0
        
        conn.close()
        return stats
    
    # ========== 事件系统 ==========
    
    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    def _emit_event(self, event: str, data: Dict):
        """触发事件"""
        # 记录到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO workflow_events (workflow_id, event_type, event_data, timestamp)
            VALUES (?, ?, ?, ?)
        """, (data.get('workflow_id'), event, json.dumps(data),
              datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        # 调用回调
        for callback in self._callbacks.get(event, []):
            try:
                callback(data)
            except Exception as e:
                logger.error(f"事件回调失败: {e}")
    
    def get_events(self, workflow_id: str = None, limit: int = 100) -> List[Dict]:
        """获取事件日志"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        if workflow_id:
            cursor.execute("""
                SELECT * FROM workflow_events 
                WHERE workflow_id = ? ORDER BY timestamp DESC LIMIT ?
            """, (workflow_id, limit))
        else:
            cursor.execute("""
                SELECT * FROM workflow_events ORDER BY timestamp DESC LIMIT ?
            """, (limit,))
        
        results = []
        for row in cursor.fetchall():
            result = dict(row)
            result['event_data'] = json.loads(result.get('event_data', '{}'))
            results.append(result)
        
        conn.close()
        return results
    
    # ========== 清理 ==========
    
    def cleanup_old_workflows(self, days: int = 30) -> int:
        """清理旧工作流"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        # 删除已完成的工作流
        cursor.execute("""
            DELETE FROM workflows 
            WHERE status IN (?, ?) AND completed_at < ?
        """, (WorkflowStatus.COMPLETED.value, WorkflowStatus.FAILED.value, cutoff))
        
        deleted = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        logger.info(f"清理了 {deleted} 个旧工作流")
        return deleted


class WorkflowRecovery:
    """工作流故障恢复"""
    
    def __init__(self, state_manager: WorkflowStateManager):
        self.state_manager = state_manager
        self._recovery_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, task_type: str, handler: Callable):
        """注册恢复处理器"""
        self._recovery_handlers[task_type] = handler
    
    def auto_recover(self, workflow_id: str) -> Dict:
        """自动恢复工作流"""
        state = self.state_manager.get_workflow_state(workflow_id)
        if not state:
            return {"error": "工作流不存在"}
        
        # 恢复工作流状态
        self.state_manager.recover_workflow(workflow_id)
        
        # 查找失败的任务并重试
        tasks = self.state_manager.list_tasks(workflow_id)
        retry_tasks = []
        
        for task in tasks:
            if task['state'] == TaskState.FAILED.value and task['attempts'] < task['max_attempts']:
                retry_tasks.append(task)
                # 重置为就绪状态
                conn = sqlite3.connect(self.state_manager.db_path)
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE task_states SET state = ? WHERE task_id = ?
                """, (TaskState.READY.value, task['task_id']))
                conn.commit()
                conn.close()
        
        self.state_manager.resume_workflow(workflow_id)
        
        return {
            "workflow_id": workflow_id,
            "status": "recovered",
            "retry_tasks": len(retry_tasks)
        }


class WorkflowMonitor:
    """工作流监控"""
    
    def __init__(self, state_manager: WorkflowStateManager):
        self.state_manager = state_manager
        self._monitors: List[Callable] = []
    
    def add_monitor(self, monitor: Callable):
        """添加监控回调"""
        self._monitors.append(monitor)
    
    def get_active_workflows(self) -> List[Dict]:
        """获取活跃工作流"""
        return self.state_manager.list_workflows(WorkflowStatus.RUNNING.value)
    
    def get_workflow_health(self, workflow_id: str) -> Dict:
        """获取工作流健康状态"""
        state = self.state_manager.get_workflow_state(workflow_id)
        if not state:
            return {"error": "Not found"}
        
        tasks = self.state_manager.list_tasks(workflow_id)
        
        health_score = 100
        if state['total_tasks'] > 0:
            health_score = (state['completed_tasks'] / state['total_tasks']) * 100
        
        issues = []
        if state['status'] == WorkflowStatus.FAILED.value:
            issues.append("工作流失败")
        if state['failed_tasks'] > 0:
            issues.append(f"{state['failed_tasks']} 个任务失败")
        
        blocked = [t for t in tasks if t['state'] == TaskState.BLOCKED.value]
        if blocked:
            issues.append(f"{len(blocked)} 个任务被阻塞")
        
        return {
            "workflow_id": workflow_id,
            "health_score": health_score,
            "status": state['status'],
            "progress": state['progress'],
            "issues": issues,
            "tasks": {
                "total": state['total_tasks'],
                "completed": state['completed_tasks'],
                "failed": state['failed_tasks'],
                "blocked": len(blocked)
            }
        }


if __name__ == "__main__":
    # 测试
    manager = WorkflowStateManager()
    
    # 创建工作流
    wf_id = manager.create_workflow("测试工作流", context={"test": True})
    
    # 添加任务
    manager.add_task(wf_id, "task1", "初始化")
    manager.add_task(wf_id, "task2", "处理", dependencies=["task1"])
    manager.add_task(wf_id, "task3", "输出", dependencies=["task2"])
    
    # 启动工作流
    manager.start_workflow(wf_id)
    
    # 模拟任务执行
    manager.start_task(wf_id, "task1")
    manager.complete_task(wf_id, "task1", {"result": "ok"})
    
    manager.start_task(wf_id, "task2")
    manager.complete_task(wf_id, "task2", {"result": "done"})
    
    manager.start_task(wf_id, "task3")
    manager.complete_task(wf_id, "task3", {"result": "success"})
    
    # 完成工作流
    manager.complete_workflow(wf_id)
    
    # 获取统计
    print(manager.get_statistics())