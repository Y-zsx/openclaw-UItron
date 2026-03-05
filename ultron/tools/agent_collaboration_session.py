#!/usr/bin/env python3
"""
Agent Collaboration Session Manager - 协作会话管理器
管理复杂多Agent工作流的会话生命周期
支持会话状态跟踪、检查点、回滚和超时处理
"""
import json
import time
import uuid
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import threading

DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
DATA_DIR.mkdir(exist_ok=True)
SESSION_DB = DATA_DIR / "collaboration_sessions.json"

class SessionStatus(Enum):
    """会话状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"

class TaskStatus(Enum):
    """任务状态"""
    WAITING = "waiting"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class TaskCheckpoint:
    """任务检查点"""
    task_id: str
    agent_id: str
    status: str
    progress: float
    output: Optional[Dict] = None
    error: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class SessionTask:
    """会话任务"""
    task_id: str
    agent_id: Optional[str]
    capabilities: List[str]
    action: str
    params: Dict
    status: str = "waiting"
    progress: float = 0.0
    output: Optional[Dict] = None
    error: Optional[str] = None
    dependencies: List[str] = field(default_factory=list)
    retries: int = 0
    max_retries: int = 3
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    checkpoints: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

@dataclass
class CollaborationSession:
    """协作会话"""
    session_id: str
    name: str
    description: str
    status: str
    created_at: str
    updated_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    timeout: int = 3600  # 超时时间(秒)
    tasks: List[Dict] = field(default_factory=list)
    participants: List[str] = field(default_factory=list)
    results: Dict = field(default_factory=dict)
    checkpoints: List[Dict] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

class CollaborationSessionManager:
    """协作会话管理器"""
    
    def __init__(self):
        self.sessions: Dict[str, CollaborationSession] = {}
        self._lock = threading.RLock()
        self._load_sessions()
    
    def _load_sessions(self):
        """加载会话"""
        if SESSION_DB.exists():
            try:
                with open(SESSION_DB) as f:
                    data = json.load(f)
                    for s in data.get("sessions", []):
                        self.sessions[s["session_id"]] = CollaborationSession(**s)
            except Exception as e:
                print(f"加载会话失败: {e}")
    
    def _save_sessions(self):
        """保存会话"""
        with self._lock:
            data = {
                "sessions": [s.to_dict() for s in self.sessions.values()],
                "last_updated": datetime.now().isoformat()
            }
            with open(SESSION_DB, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
    
    def create_session(self, name: str, description: str = "", 
                      timeout: int = 3600, participants: List[str] = None) -> str:
        """创建协作会话"""
        session_id = f"session_{uuid.uuid4().hex[:12]}"
        
        session = CollaborationSession(
            session_id=session_id,
            name=name,
            description=description,
            status=SessionStatus.PENDING.value,
            created_at=datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
            timeout=timeout,
            participants=participants or []
        )
        
        self.sessions[session_id] = session
        self._save_sessions()
        
        return session_id
    
    def add_task(self, session_id: str, agent_id: str, action: str,
                 params: Dict, capabilities: List[str] = None,
                 dependencies: List[str] = None) -> Optional[str]:
        """添加任务到会话"""
        if session_id not in self.sessions:
            return None
        
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        
        task = SessionTask(
            task_id=task_id,
            agent_id=agent_id,
            capabilities=capabilities or [],
            action=action,
            params=params,
            dependencies=dependencies or []
        )
        
        session = self.sessions[session_id]
        session.tasks.append(task.to_dict())
        session.updated_at = datetime.now().isoformat()
        
        # 添加参与者
        if agent_id and agent_id not in session.participants:
            session.participants.append(agent_id)
        
        self._save_sessions()
        
        return task_id
    
    def start_session(self, session_id: str) -> Dict:
        """启动会话"""
        if session_id not in self.sessions:
            return {"status": "error", "reason": "Session not found"}
        
        session = self.sessions[session_id]
        
        if session.status not in [SessionStatus.PENDING.value, SessionStatus.PAUSED.value]:
            return {"status": "error", "reason": f"Cannot start session in {session.status} state"}
        
        session.status = SessionStatus.RUNNING.value
        session.started_at = datetime.now().isoformat()
        session.updated_at = datetime.now().isoformat()
        
        # 标记可运行的任务
        for task in session.tasks:
            if not task.get("dependencies") or self._can_run_task(session, task["task_id"]):
                task["status"] = TaskStatus.RUNNING.value
                task["started_at"] = datetime.now().isoformat()
        
        self._save_sessions()
        
        return {"status": "started", "session_id": session_id}
    
    def _can_run_task(self, session: CollaborationSession, task_id: str) -> bool:
        """检查任务是否可以运行"""
        for task in session.tasks:
            if task["task_id"] == task_id:
                deps = task.get("dependencies", [])
                for dep_id in deps:
                    dep_task = next((t for t in session.tasks if t["task_id"] == dep_id), None)
                    if not dep_task or dep_task["status"] != TaskStatus.COMPLETED.value:
                        return False
                return True
        return False
    
    def complete_task(self, session_id: str, task_id: str, 
                     output: Dict = None, error: str = None) -> Dict:
        """完成任务"""
        if session_id not in self.sessions:
            return {"status": "error", "reason": "Session not found"}
        
        session = self.sessions[session_id]
        
        for task in session.tasks:
            if task["task_id"] == task_id:
                if error:
                    task["status"] = TaskStatus.FAILED.value
                    task["error"] = error
                    task["retries"] = task.get("retries", 0) + 1
                    
                    # 重试逻辑
                    if task["retries"] < task.get("max_retries", 3):
                        task["status"] = TaskStatus.RUNNING.value
                        return {"status": "retry", "task_id": task_id}
                else:
                    task["status"] = TaskStatus.COMPLETED.value
                    task["output"] = output or {}
                    task["completed_at"] = datetime.now().isoformat()
                    task["progress"] = 100.0
                    
                    # 保存结果
                    session.results[task_id] = output or {}
                
                task["updated_at"] = datetime.now().isoformat()
                break
        
        # 检查是否所有任务完成
        self._check_session_completion(session_id)
        self._save_sessions()
        
        return {"status": "completed", "task_id": task_id}
    
    def _check_session_completion(self, session_id: str):
        """检查会话是否完成"""
        session = self.sessions[session_id]
        
        if not session.tasks:
            return
        
        all_completed = all(
            t["status"] in [TaskStatus.COMPLETED.value, TaskStatus.SKIPPED.value]
            for t in session.tasks
        )
        
        any_failed = any(
            t["status"] == TaskStatus.FAILED.value and 
            t.get("retries", 0) >= t.get("max_retries", 3)
            for t in session.tasks
        )
        
        if all_completed:
            session.status = SessionStatus.COMPLETED.value
            session.completed_at = datetime.now().isoformat()
        elif any_failed:
            session.status = SessionStatus.FAILED.value
            session.completed_at = datetime.now().isoformat()
    
    def create_checkpoint(self, session_id: str, name: str = None) -> Optional[str]:
        """创建检查点"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        checkpoint_id = f"cp_{uuid.uuid4().hex[:8]}"
        
        checkpoint = {
            "checkpoint_id": checkpoint_id,
            "name": name or f"Checkpoint {len(session.checkpoints) + 1}",
            "created_at": datetime.now().isoformat(),
            "tasks_snapshot": [t.copy() for t in session.tasks],
            "results_snapshot": session.results.copy()
        }
        
        session.checkpoints.append(checkpoint)
        session.updated_at = datetime.now().isoformat()
        self._save_sessions()
        
        return checkpoint_id
    
    def rollback_to_checkpoint(self, session_id: str, checkpoint_id: str) -> Dict:
        """回滚到检查点"""
        if session_id not in self.sessions:
            return {"status": "error", "reason": "Session not found"}
        
        session = self.sessions[session_id]
        
        checkpoint = next((cp for cp in session.checkpoints 
                         if cp["checkpoint_id"] == checkpoint_id), None)
        
        if not checkpoint:
            return {"status": "error", "reason": "Checkpoint not found"}
        
        # 恢复状态
        session.tasks = checkpoint["tasks_snapshot"]
        session.results = checkpoint["results_snapshot"]
        
        # 标记为运行中
        session.status = SessionStatus.RUNNING.value
        session.updated_at = datetime.now().isoformat()
        
        self._save_sessions()
        
        return {"status": "rolled_back", "checkpoint_id": checkpoint_id}
    
    def pause_session(self, session_id: str) -> Dict:
        """暂停会话"""
        if session_id not in self.sessions:
            return {"status": "error", "reason": "Session not found"}
        
        session = self.sessions[session_id]
        
        if session.status != SessionStatus.RUNNING.value:
            return {"status": "error", "reason": f"Cannot pause session in {session.status} state"}
        
        session.status = SessionStatus.PAUSED.value
        session.updated_at = datetime.now().isoformat()
        
        self._save_sessions()
        
        return {"status": "paused", "session_id": session_id}
    
    def cancel_session(self, session_id: str) -> Dict:
        """取消会话"""
        if session_id not in self.sessions:
            return {"status": "error", "reason": "Session not found"}
        
        session = self.sessions[session_id]
        session.status = SessionStatus.CANCELLED.value
        session.completed_at = datetime.now().isoformat()
        session.updated_at = datetime.now().isoformat()
        
        self._save_sessions()
        
        return {"status": "cancelled", "session_id": session_id}
    
    def get_session_status(self, session_id: str) -> Optional[Dict]:
        """获取会话状态"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # 计算进度
        if session.tasks:
            completed = sum(1 for t in session.tasks if t["status"] == TaskStatus.COMPLETED.value)
            progress = (completed / len(session.tasks)) * 100
        else:
            progress = 0
        
        # 检查超时
        if session.started_at:
            elapsed = (datetime.now() - datetime.fromisoformat(session.started_at)).total_seconds()
            if elapsed > session.timeout and session.status == SessionStatus.RUNNING.value:
                session.status = SessionStatus.TIMEOUT.value
                session.completed_at = datetime.now().isoformat()
        
        return {
            "session_id": session.session_id,
            "name": session.name,
            "status": session.status,
            "progress": progress,
            "tasks": {
                "total": len(session.tasks),
                "completed": sum(1 for t in session.tasks if t["status"] == TaskStatus.COMPLETED.value),
                "failed": sum(1 for t in session.tasks if t["status"] == TaskStatus.FAILED.value),
                "running": sum(1 for t in session.tasks if t["status"] == TaskStatus.RUNNING.value),
            },
            "participants": session.participants,
            "created_at": session.created_at,
            "started_at": session.started_at,
            "completed_at": session.completed_at,
            "results": session.results
        }
    
    def list_sessions(self, status: str = None) -> List[Dict]:
        """列出所有会话"""
        sessions = []
        for session in self.sessions.values():
            if status and session.status != status:
                continue
            sessions.append({
                "session_id": session.session_id,
                "name": session.name,
                "status": session.status,
                "task_count": len(session.tasks),
                "created_at": session.created_at
            })
        return sessions
    
    def get_session_results(self, session_id: str) -> Optional[Dict]:
        """获取会话结果"""
        if session_id not in self.sessions:
            return None
        return self.sessions[session_id].results


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent Collaboration Session Manager")
    parser.add_argument("command", choices=["create", "add-task", "start", "complete-task",
                                            "checkpoint", "rollback", "pause", "cancel",
                                            "status", "list", "results"],
                       help="Command to execute")
    parser.add_argument("--session", help="Session ID")
    parser.add_argument("--name", help="Session/Task name")
    parser.add_argument("--description", help="Session description")
    parser.add_argument("--timeout", type=int, default=3600, help="Session timeout (seconds)")
    parser.add_argument("--participants", nargs="+", help="Participants")
    parser.add_argument("--agent", help="Agent ID")
    parser.add_argument("--action", help="Action to perform")
    parser.add_argument("--params", type=json.loads, default={}, help="Action params as JSON")
    parser.add_argument("--capabilities", nargs="+", help="Required capabilities")
    parser.add_argument("--depends", nargs="+", help="Task dependencies")
    parser.add_argument("--output", type=json.loads, default=None, help="Task output as JSON")
    parser.add_argument("--error", help="Task error message")
    parser.add_argument("--checkpoint", help="Checkpoint ID")
    
    args = parser.parse_args()
    manager = CollaborationSessionManager()
    
    if args.command == "create":
        if not args.name:
            print("Error: --name required")
            return
        session_id = manager.create_session(args.name, args.description or "", 
                                           args.timeout, args.participants)
        print(json.dumps({"status": "created", "session_id": session_id}, indent=2))
    
    elif args.command == "add-task":
        if not args.session or not args.action:
            print("Error: --session and --action required")
            return
        task_id = manager.add_task(args.session, args.agent, args.action, args.params,
                                   args.capabilities, args.depends)
        if task_id:
            print(json.dumps({"status": "added", "task_id": task_id}, indent=2))
        else:
            print(json.dumps({"status": "error", "reason": "Failed to add task"}, indent=2))
    
    elif args.command == "start":
        if not args.session:
            print("Error: --session required")
            return
        result = manager.start_session(args.session)
        print(json.dumps(result, indent=2))
    
    elif args.command == "complete-task":
        if not args.session or not args.name:
            print("Error: --session and --name (task_id) required")
            return
        result = manager.complete_task(args.session, args.name, args.output, args.error)
        print(json.dumps(result, indent=2))
    
    elif args.command == "checkpoint":
        if not args.session:
            print("Error: --session required")
            return
        cp_id = manager.create_checkpoint(args.session, args.name)
        if cp_id:
            print(json.dumps({"status": "created", "checkpoint_id": cp_id}, indent=2))
        else:
            print(json.dumps({"status": "error"}, indent=2))
    
    elif args.command == "rollback":
        if not args.session or not args.checkpoint:
            print("Error: --session and --checkpoint required")
            return
        result = manager.rollback_to_checkpoint(args.session, args.checkpoint)
        print(json.dumps(result, indent=2))
    
    elif args.command == "pause":
        if not args.session:
            print("Error: --session required")
            return
        result = manager.pause_session(args.session)
        print(json.dumps(result, indent=2))
    
    elif args.command == "cancel":
        if not args.session:
            print("Error: --session required")
            return
        result = manager.cancel_session(args.session)
        print(json.dumps(result, indent=2))
    
    elif args.command == "status":
        if not args.session:
            print("Error: --session required")
            return
        result = manager.get_session_status(args.session)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result 
              else json.dumps({"status": "not found"}, indent=2))
    
    elif args.command == "list":
        sessions = manager.list_sessions()
        print(json.dumps(sessions, indent=2, ensure_ascii=False))
    
    elif args.command == "results":
        if not args.session:
            print("Error: --session required")
            return
        result = manager.get_session_results(args.session)
        print(json.dumps(result, indent=2, ensure_ascii=False) if result
              else json.dumps({"status": "not found"}, indent=2))


if __name__ == "__main__":
    main()