#!/usr/bin/env python3
"""
Agent任务队列与负载均衡系统
实现任务排队、负载均衡、健康检查、自动分发
"""

import asyncio
import json
import uuid
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
from flask import Flask, jsonify, request
from collections import defaultdict
import heapq

# ============ 数据模型 ============

class TaskStatus(Enum):
    PENDING = "pending"
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
    payload: Dict[str, Any]
    priority: int = 1
    status: str = "pending"
    agent_id: Optional[str] = None
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class Agent:
    id: str
    name: str
    status: str = "idle"  # idle, busy, offline
    current_task_id: Optional[str] = None
    capabilities: List[str] = None
    load: float = 0.0  # 0-1
    max_concurrent: int = 1
    last_heartbeat: str = None
    
    def __post_init__(self):
        if self.capabilities is None:
            self.capabilities = []
        if self.last_heartbeat is None:
            self.last_heartbeat = datetime.now().isoformat()

# ============ 数据库 ============

class QueueDatabase:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 任务表
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            payload TEXT,
            priority INTEGER DEFAULT 1,
            status TEXT DEFAULT 'pending',
            agent_id TEXT,
            created_at TEXT,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            retry_count INTEGER DEFAULT 0
        )''')
        
        # Agent表
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'idle',
            current_task_id TEXT,
            capabilities TEXT,
            load REAL DEFAULT 0.0,
            max_concurrent INTEGER DEFAULT 1,
            last_heartbeat TEXT
        )''')
        
        # 索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    # ===== 任务操作 =====
    def add_task(self, task: Task) -> Task:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO tasks (id, name, payload, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (task.id, task.name, json.dumps(task.payload), task.priority, 
             task.status, task.created_at))
        conn.commit()
        conn.close()
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return Task(
                id=row[0], name=row[1], payload=json.loads(row[2]) if row[2] else {},
                priority=row[3], status=row[4], agent_id=row[5],
                created_at=row[6], started_at=row[7], completed_at=row[8],
                result=json.loads(row[9]) if row[9] else None,
                error=row[10], retry_count=row[11]
            )
        return None
    
    def get_pending_tasks(self, limit: int = 100) -> List[Task]:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT * FROM tasks WHERE status = 'pending' 
            ORDER BY priority DESC, created_at ASC LIMIT ?''', (limit,))
        rows = c.fetchall()
        conn.close()
        return [Task(
            id=row[0], name=row[1], payload=json.loads(row[2]) if row[2] else {},
            priority=row[3], status=row[4], agent_id=row[5],
            created_at=row[6], started_at=row[7], completed_at=row[8],
            result=json.loads(row[9]) if row[9] else None,
            error=row[10], retry_count=row[11]
        ) for row in rows]
    
    def update_task(self, task: Task):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE tasks SET status=?, agent_id=?, started_at=?, 
            completed_at=?, result=?, error=?, retry_count=? WHERE id=?''',
            (task.status, task.agent_id, task.started_at, task.completed_at,
             json.dumps(task.result) if task.result else None,
             task.error, task.retry_count, task.id))
        conn.commit()
        conn.close()
    
    def get_task_stats(self) -> Dict:
        conn = self.get_connection()
        c = conn.cursor()
        stats = {}
        for status in ['pending', 'running', 'completed', 'failed', 'cancelled']:
            c.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', (status,))
            stats[status] = c.fetchone()[0]
        c.execute('SELECT COUNT(*) FROM tasks')
        stats['total'] = c.fetchone()[0]
        conn.close()
        return stats
    
    # ===== Agent操作 =====
    def register_agent(self, agent: Agent) -> Agent:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO agents 
            (id, name, status, capabilities, load, max_concurrent, last_heartbeat)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (agent.id, agent.name, agent.status, json.dumps(agent.capabilities),
             agent.load, agent.max_concurrent, agent.last_heartbeat))
        conn.commit()
        conn.close()
        return agent
    
    def get_agent(self, agent_id: str) -> Optional[Agent]:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return Agent(
                id=row[0], name=row[1], status=row[2], current_task_id=row[3],
                capabilities=json.loads(row[4]) if row[4] else [],
                load=row[5], max_concurrent=row[6], last_heartbeat=row[7]
            )
        return None
    
    def get_idle_agents(self) -> List[Agent]:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT * FROM agents WHERE status = 'idle' 
            AND load < 1.0 ORDER BY load ASC''')
        rows = c.fetchall()
        conn.close()
        return [Agent(
            id=row[0], name=row[1], status=row[2], current_task_id=row[3],
            capabilities=json.loads(row[4]) if row[4] else [],
            load=row[5], max_concurrent=row[6], last_heartbeat=row[7]
        ) for row in rows]
    
    def get_all_agents(self) -> List[Agent]:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM agents')
        rows = c.fetchall()
        conn.close()
        return [Agent(
            id=row[0], name=row[1], status=row[2], current_task_id=row[3],
            capabilities=json.loads(row[4]) if row[4] else [],
            load=row[5], max_concurrent=row[6], last_heartbeat=row[7]
        ) for row in rows]
    
    def update_agent(self, agent: Agent):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE agents SET status=?, current_task_id=?, 
            load=?, last_heartbeat=? WHERE id=?''',
            (agent.status, agent.current_task_id, agent.load,
             agent.last_heartbeat, agent.id))
        conn.commit()
        conn.close()
    
    def get_agent_stats(self) -> Dict:
        conn = self.get_connection()
        c = conn.cursor()
        stats = {}
        for status in ['idle', 'busy', 'offline']:
            c.execute('SELECT COUNT(*) FROM agents WHERE status = ?', (status,))
            stats[status] = c.fetchone()[0]
        c.execute('SELECT AVG(load) FROM agents WHERE status != "offline"')
        avg_load = c.fetchone()[0] or 0
        stats['avg_load'] = round(avg_load, 2)
        stats['total'] = stats['idle'] + stats['busy']
        conn.close()
        return stats

# ============ 负载均衡器 ============

class LoadBalancer:
    """负载均衡器 - 多种策略"""
    
    def __init__(self, db: QueueDatabase):
        self.db = db
    
    def select_agent(self, task: Task, strategy: str = "least_load") -> Optional[Agent]:
        """选择最佳Agent"""
        idle_agents = self.db.get_idle_agents()
        
        if not idle_agents:
            return None
        
        # 根据策略选择
        if strategy == "least_load":
            return min(idle_agents, key=lambda a: a.load)
        elif strategy == "round_robin":
            return idle_agents[0]  # 简单轮询
        elif strategy == "capability_match":
            # 匹配能力的最低负载
            capable = [a for a in idle_agents 
                      if not task.payload.get('required_capability') 
                      or task.payload.get('required_capability') in a.capabilities]
            if capable:
                return min(capable, key=lambda a: a.load)
            return None
        else:
            return idle_agents[0]
    
    def distribute_task(self, task: Task) -> Optional[Agent]:
        """分发任务"""
        agent = self.select_agent(task)
        if not agent:
            return None
        
        # 更新状态
        task.agent_id = agent.id
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        
        agent.status = "busy"
        agent.current_task_id = task.id
        agent.load = min(1.0, (agent.load + 0.3))  # 增加负载
        
        self.db.update_task(task)
        self.db.update_agent(agent)
        
        return agent

# ============ 队列管理器 ============

class TaskQueue:
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/agents/queue/data/queue.db"):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = QueueDatabase(db_path)
        self.lb = LoadBalancer(self.db)
        self.loop_task = None
    
    def enqueue(self, name: str, payload: Dict = None, priority: int = 1) -> Task:
        """添加任务到队列"""
        task = Task(
            id=str(uuid.uuid4()),
            name=name,
            payload=payload or {},
            priority=priority
        )
        return self.db.add_task(task)
    
    def dequeue(self, task_id: str) -> Optional[Task]:
        """手动领取任务"""
        task = self.db.get_task(task_id)
        if not task or task.status != "pending":
            return None
        
        agent = self.lb.select_agent(task)
        if not agent:
            return None
        
        return self._assign_task(task, agent)
    
    def _assign_task(self, task: Task, agent: Agent) -> Task:
        """分配任务给Agent"""
        task.agent_id = agent.id
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        
        agent.status = "busy"
        agent.current_task_id = task.id
        agent.load = min(1.0, agent.load + 0.3)
        
        self.db.update_task(task)
        self.db.update_agent(agent)
        
        return task
    
    def complete_task(self, task_id: str, result: Dict = None, error: str = None):
        """完成任务"""
        task = self.db.get_task(task_id)
        if not task:
            return
        
        task.status = "completed" if not error else "failed"
        task.completed_at = datetime.now().isoformat()
        task.result = result
        task.error = error
        
        self.db.update_task(task)
        
        # 释放Agent
        if task.agent_id:
            agent = self.db.get_agent(task.agent_id)
            if agent:
                agent.status = "idle"
                agent.current_task_id = None
                agent.load = max(0, agent.load - 0.3)
                self.db.update_agent(agent)
    
    def auto_distribute(self, max_tasks: int = 10):
        """自动分发任务"""
        pending = self.db.get_pending_tasks(max_tasks)
        distributed = 0
        
        for task in pending:
            if self.lb.distribute_task(task):
                distributed += 1
        
        return distributed
    
    def register_agent(self, agent_id: str, name: str, capabilities: List[str] = None, 
                       max_concurrent: int = 1) -> Agent:
        """注册Agent"""
        agent = Agent(
            id=agent_id,
            name=name,
            capabilities=capabilities or [],
            max_concurrent=max_concurrent
        )
        return self.db.register_agent(agent)
    
    def heartbeat(self, agent_id: str):
        """Agent心跳"""
        agent = self.db.get_agent(agent_id)
        if agent:
            agent.last_heartbeat = datetime.now().isoformat()
            if agent.status == "offline":
                agent.status = "idle"
            self.db.update_agent(agent)
    
    def get_summary(self) -> Dict:
        """获取队列摘要"""
        return {
            "tasks": self.db.get_task_stats(),
            "agents": self.db.get_agent_stats(),
            "pending_tasks": [
                {"id": t.id, "name": t.name, "priority": t.priority, 
                 "created_at": t.created_at}
                for t in self.db.get_pending_tasks(10)
            ],
            "idle_agents": [
                {"id": a.id, "name": a.name, "load": a.load}
                for a in self.db.get_idle_agents()
            ]
        }

# ============ Flask API ============

app = Flask(__name__)
queue = TaskQueue()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "task-queue"})

@app.route('/api/queue/summary', methods=['GET'])
def summary():
    return jsonify(queue.get_summary())

@app.route('/api/queue/enqueue', methods=['POST'])
def enqueue():
    data = request.json or {}
    task = queue.enqueue(
        name=data.get('name', 'unnamed'),
        payload=data.get('payload', {}),
        priority=data.get('priority', 1)
    )
    return jsonify({"task_id": task.id, "status": task.status})

@app.route('/api/queue/dequeue/<task_id>', methods=['POST'])
def dequeue(task_id):
    task = queue.dequeue(task_id)
    if task:
        return jsonify({"task_id": task.id, "agent_id": task.agent_id, "status": task.status})
    return jsonify({"error": "Task not available"}), 400

@app.route('/api/queue/complete/<task_id>', methods=['POST'])
def complete(task_id):
    data = request.json or {}
    queue.complete_task(task_id, data.get('result'), data.get('error'))
    return jsonify({"status": "completed"})

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    status = request.args.get('status')
    if status:
        tasks = [t for t in queue.db.get_pending_tasks(100) if t.status == status]
    else:
        tasks = queue.db.get_pending_tasks(100)
    return jsonify([{
        "id": t.id, "name": t.name, "priority": t.priority,
        "status": t.status, "agent_id": t.agent_id, "created_at": t.created_at
    } for t in tasks])

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = queue.db.get_task(task_id)
    if task:
        return jsonify(asdict(task))
    return jsonify({"error": "Not found"}), 404

@app.route('/api/agents', methods=['GET'])
def list_agents():
    agents = queue.db.get_all_agents()
    return jsonify([{
        "id": a.id, "name": a.name, "status": a.status,
        "load": a.load, "capabilities": a.capabilities,
        "current_task_id": a.current_task_id
    } for a in agents])

@app.route('/api/agents', methods=['POST'])
def register_agent():
    data = request.json or {}
    agent = queue.register_agent(
        agent_id=data.get('id', str(uuid.uuid4())),
        name=data.get('name', 'unknown'),
        capabilities=data.get('capabilities', []),
        max_concurrent=data.get('max_concurrent', 1)
    )
    return jsonify({"agent_id": agent.id, "status": "registered"})

@app.route('/api/agents/<agent_id>/heartbeat', methods=['POST'])
def agent_heartbeat(agent_id):
    queue.heartbeat(agent_id)
    return jsonify({"status": "ok"})

@app.route('/api/distribute', methods=['POST'])
def distribute():
    count = queue.auto_distribute()
    return jsonify({"distributed": count})

# 自动分发线程
def auto_distribute_loop():
    while True:
        time.sleep(5)  # 每5秒检查一次
        try:
            queue.auto_distribute()
        except Exception as e:
            print(f"Auto distribute error: {e}")

if __name__ == '__main__':
    import os
    os.makedirs("/root/.openclaw/workspace/ultron/agents/queue/data", exist_ok=True)
    
    # 启动自动分发线程
    t = threading.Thread(target=auto_distribute_loop, daemon=True)
    t.start()
    
    app.run(host='0.0.0.0', port=18099, debug=False)