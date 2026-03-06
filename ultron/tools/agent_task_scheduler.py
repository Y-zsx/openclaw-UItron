#!/usr/bin/env python3
"""
Agent自动任务调度系统
功能：
- 任务队列管理
- 智能任务分配
- 优先级调度
- 执行状态追踪
"""

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import uuid
import threading
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import sqlite3
from flask import Flask, request, jsonify
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

class TaskStatus(Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

@dataclass
class Task:
    id: str
    name: str
    description: str
    payload: Dict[str, Any]
    priority: int = TaskPriority.NORMAL.value
    status: str = TaskStatus.PENDING.value
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    scheduled_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    assigned_agent: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

@dataclass
class Agent:
    id: str
    name: str
    capabilities: List[str]
    status: str = "idle"  # idle, busy, offline
    current_task_id: Optional[str] = None
    load: float = 0.0  # 0-1
    registered_at: str = field(default_factory=lambda: datetime.now().isoformat())

# ==================== 调度器核心 ====================

class TaskScheduler:
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/data/task_scheduler.db"):
        self.db_path = db_path
        self.tasks: Dict[str, Task] = {}
        self.agents: Dict[str, Agent] = {}
        self.task_queue: List[str] = []  # 按优先级排序的任务ID队列
        self.executors: Dict[str, Callable] = {}  # 任务类型 -> 执行函数
        self.executor = ThreadPoolExecutor(max_workers=10)
        self._init_db()
        self._load_state()
    
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            data TEXT NOT NULL
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS task_history (
            id TEXT PRIMARY KEY,
            task_data TEXT,
            completed_at TEXT
        )''')
        
        conn.commit()
        conn.close()
    
    def _load_state(self):
        """加载状态"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute("SELECT id, data FROM tasks")
        for row in c.fetchall():
            task = Task(**json.loads(row[1]))
            if task.status not in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]:
                self.tasks[task.id] = task
        
        c.execute("SELECT id, data FROM agents")
        for row in c.fetchall():
            agent = Agent(**json.loads(row[1]))
            self.agents[agent.id] = agent
        
        conn.close()
    
    def _save_task(self, task: Task):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("REPLACE INTO tasks (id, data) VALUES (?, ?)", 
                  (task.id, json.dumps(asdict(task))))
        conn.commit()
        conn.close()
    
    def _save_agent(self, agent: Agent):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("REPLACE INTO agents (id, data) VALUES (?, ?)", 
                  (agent.id, json.dumps(asdict(agent))))
        conn.commit()
        conn.close()
    
    def register_executor(self, task_type: str, executor: Callable):
        """注册任务执行器"""
        self.executors[task_type] = executor
    
    # ==================== 任务管理 ====================
    
    def create_task(self, name: str, description: str, payload: Dict,
                    priority: int = TaskPriority.NORMAL.value,
                    scheduled_at: Optional[str] = None,
                    max_retries: int = 3) -> str:
        """创建新任务"""
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = Task(
            id=task_id,
            name=name,
            description=description,
            payload=payload,
            priority=priority,
            status=TaskStatus.PENDING.value,
            scheduled_at=scheduled_at,
            max_retries=max_retries
        )
        self.tasks[task_id] = task
        self._save_task(task)
        
        # 加入队列
        self._enqueue_task(task_id)
        
        logger.info(f"创建任务: {task_id} - {name}")
        return task_id
    
    def _enqueue_task(self, task_id: str):
        """将任务加入调度队列"""
        task = self.tasks.get(task_id)
        if not task:
            return
        
        task.status = TaskStatus.QUEUED.value
        self._save_task(task)
        
        # 按优先级插入
        inserted = False
        for i, tid in enumerate(self.task_queue):
            if self.tasks[tid].priority < task.priority:
                self.task_queue.insert(i, task_id)
                inserted = True
                break
        
        if not inserted:
            self.task_queue.append(task_id)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        task = self.tasks.get(task_id)
        return asdict(task) if task else None
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待执行任务"""
        return [asdict(t) for t in self.tasks.values() 
                if t.status == TaskStatus.QUEUED.value]
    
    def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if task.status in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]:
            return False
        
        task.status = TaskStatus.CANCELLED.value
        self._save_task(task)
        
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)
        
        return True
    
    # ==================== Agent管理 ====================
    
    def register_agent(self, agent_id: str, name: str, capabilities: List[str]) -> bool:
        """注册Agent"""
        if agent_id in self.agents:
            return False
        
        agent = Agent(id=agent_id, name=name, capabilities=capabilities)
        self.agents[agent_id] = agent
        self._save_agent(agent)
        
        logger.info(f"注册Agent: {agent_id} - {name}")
        return True
    
    def update_agent_status(self, agent_id: str, status: str, load: float = None):
        """更新Agent状态"""
        agent = self.agents.get(agent_id)
        if not agent:
            return False
        
        agent.status = status
        if load is not None:
            agent.load = load
        if status == "idle":
            agent.current_task_id = None
        
        self._save_agent(agent)
        return True
    
    def get_available_agents(self, required_capability: str = None) -> List[Dict]:
        """获取可用Agent"""
        available = []
        for agent in self.agents.values():
            if agent.status == "idle" and agent.load < 0.8:
                if required_capability is None or required_capability in agent.capabilities:
                    available.append(asdict(agent))
        
        # 按负载排序
        available.sort(key=lambda x: x['load'])
        return available
    
    # ==================== 调度逻辑 ====================
    
    def assign_task_to_agent(self, task_id: str, agent_id: str) -> bool:
        """分配任务给Agent"""
        task = self.tasks.get(task_id)
        agent = self.agents.get(agent_id)
        
        if not task or not agent:
            return False
        
        if agent.status != "idle":
            return False
        
        task.assigned_agent = agent_id
        task.status = TaskStatus.RUNNING.value
        task.started_at = datetime.now().isoformat()
        
        agent.status = "busy"
        agent.current_task_id = task_id
        agent.load = min(1.0, agent.load + 0.3)
        
        self._save_task(task)
        self._save_agent(agent)
        
        # 从队列移除
        if task_id in self.task_queue:
            self.task_queue.remove(task_id)
        
        return True
    
    def execute_task(self, task_id: str) -> Dict:
        """执行任务"""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "Task not found"}
        
        agent = self.agents.get(task.assigned_agent)
        
        try:
            task_type = task.payload.get("type", "default")
            executor = self.executors.get(task_type)
            
            if executor:
                result = executor(task.payload, agent)
            else:
                result = {"status": "executed", "message": f"No executor for type: {task_type}"}
            
            task.status = TaskStatus.COMPLETED.value
            task.completed_at = datetime.now().isoformat()
            task.result = result
            
            if agent:
                agent.status = "idle"
                agent.current_task_id = None
                agent.load = max(0, agent.load - 0.3)
                self._save_agent(agent)
            
            self._save_task(task)
            
            # 记录历史
            conn = sqlite3.connect(self.db_path)
            c = conn.cursor()
            c.execute("INSERT INTO task_history (id, task_data, completed_at) VALUES (?, ?, ?)",
                      (task.id, json.dumps(asdict(task)), task.completed_at))
            conn.commit()
            conn.close()
            
            logger.info(f"任务完成: {task_id}")
            return result
            
        except Exception as e:
            task.status = TaskStatus.FAILED.value
            task.error = str(e)
            task.retry_count += 1
            
            if agent:
                agent.status = "idle"
                agent.load = max(0, agent.load - 0.3)
                self._save_agent(agent)
            
            # 重试
            if task.retry_count < task.max_retries:
                task.status = TaskStatus.QUEUED.value
                logger.warning(f"任务失败，准备重试: {task_id}, 尝试 {task.retry_count}")
            else:
                logger.error(f"任务失败: {task_id}, 错误: {e}")
            
            self._save_task(task)
            return {"error": str(e)}
    
    def run_scheduler_loop(self):
        """调度循环"""
        while True:
            try:
                # 找到可用的任务和Agent
                while self.task_queue and self.get_available_agents():
                    task_id = self.task_queue[0]
                    task = self.tasks.get(task_id)
                    
                    if not task or task.status == TaskStatus.CANCELLED.value:
                        if task_id in self.task_queue:
                            self.task_queue.remove(task_id)
                        continue
                    
                    # 找最合适的Agent
                    required_cap = task.payload.get("required_capability")
                    available = self.get_available_agents(required_cap)
                    
                    if available:
                        agent = available[0]
                        if self.assign_task_to_agent(task_id, agent['id']):
                            # 使用线程池执行
                            self.executor.submit(self.execute_task, task_id)
                    
                    time.sleep(0.5)
                
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"调度循环错误: {e}")
                time.sleep(5)
    
    # ==================== 统计 ====================
    
    def get_stats(self) -> Dict:
        """获取调度统计"""
        total = len(self.tasks)
        pending = sum(1 for t in self.tasks.values() if t.status == TaskStatus.QUEUED.value)
        running = sum(1 for t in self.tasks.values() if t.status == TaskStatus.RUNNING.value)
        completed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.COMPLETED.value)
        failed = sum(1 for t in self.tasks.values() if t.status == TaskStatus.FAILED.value)
        
        agents_online = sum(1 for a in self.agents.values() if a.status != "offline")
        agents_idle = sum(1 for a in self.agents.values() if a.status == "idle")
        
        return {
            "tasks": {
                "total": total,
                "pending": pending,
                "running": running,
                "completed": completed,
                "failed": failed
            },
            "agents": {
                "total": len(self.agents),
                "online": agents_online,
                "idle": agents_idle,
                "busy": agents_online - agents_idle
            },
            "queue_size": len(self.task_queue)
        }


# ==================== Flask API ====================

app = Flask(__name__)
scheduler = TaskScheduler()

# 注册默认执行器
def default_executor(payload: Dict, agent: Optional[Agent]) -> Dict:
    """默认任务执行器"""
    time.sleep(1)  # 模拟执行
    return {
        "status": "success",
        "executed_by": agent.id if agent else "unknown",
        "payload": payload
    }

scheduler.register_executor("default", default_executor)
scheduler.register_executor("health_check", default_executor)
scheduler.register_executor("data_sync", default_executor)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "agent-task-scheduler"})

@app.route('/tasks', methods=['POST'])
def create_task():
    """创建任务"""
    data = request.json
    task_id = scheduler.create_task(
        name=data.get("name"),
        description=data.get("description", ""),
        payload=data.get("payload", {}),
        priority=data.get("priority", TaskPriority.NORMAL.value)
    )
    return jsonify({"task_id": task_id})

@app.route('/tasks', methods=['GET'])
def list_tasks():
    """列出所有任务"""
    status = request.args.get("status")
    if status:
        tasks = [asdict(t) for t in scheduler.tasks.values() if t.status == status]
    else:
        tasks = [asdict(t) for t in scheduler.tasks.values()]
    return jsonify({"tasks": tasks})

@app.route('/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    """获取任务详情"""
    task = scheduler.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task)

@app.route('/tasks/<task_id>/cancel', methods=['POST'])
def cancel_task(task_id):
    """取消任务"""
    success = scheduler.cancel_task(task_id)
    return jsonify({"success": success})

@app.route('/agents', methods=['POST'])
def register_agent():
    """注册Agent"""
    data = request.json
    success = scheduler.register_agent(
        agent_id=data.get("agent_id"),
        name=data.get("name"),
        capabilities=data.get("capabilities", [])
    )
    return jsonify({"success": success})

@app.route('/agents', methods=['GET'])
def list_agents():
    """列出所有Agent"""
    agents = [asdict(a) for a in scheduler.agents.values()]
    return jsonify({"agents": agents})

@app.route('/agents/<agent_id>/status', methods=['PUT'])
def update_agent(agent_id):
    """更新Agent状态"""
    data = request.json
    success = scheduler.update_agent_status(
        agent_id=agent_id,
        status=data.get("status"),
        load=data.get("load")
    )
    return jsonify({"success": success})

@app.route('/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    return jsonify(scheduler.get_stats())


if __name__ == '__main__':
    # 启动调度器线程
    scheduler_thread = threading.Thread(target=scheduler.run_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    # 启动Flask API
    app.run(host='0.0.0.0', port=18297, debug=False)