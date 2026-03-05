#!/usr/bin/env python3
"""
Agent任务队列与负载均衡统一API服务
==================================
整合任务队列 + 负载均衡 + 健康监控

端口: 18128
"""

import json
import time
import uuid
import threading
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, jsonify, request
from collections import defaultdict
from dataclasses import dataclass, asdict
from enum import Enum
import heapq

app = Flask(__name__)

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
class QueuedTask:
    id: str
    name: str
    payload: dict
    priority: int = 1
    status: str = "pending"
    agent_id: str = None
    created_at: str = None
    started_at: str = None
    completed_at: str = None
    result: dict = None
    error: str = None
    retry_count: int = 0
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class AgentNode:
    id: str
    name: str
    status: str = "idle"
    current_task_id: str = None
    capabilities: list = None
    load: float = 0.0
    max_concurrent: int = 3
    last_heartbeat: str = None
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    
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
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute('''CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, payload TEXT,
            priority INTEGER DEFAULT 1, status TEXT DEFAULT 'pending',
            agent_id TEXT, created_at TEXT, started_at TEXT, completed_at TEXT,
            result TEXT, error TEXT, retry_count INTEGER DEFAULT 0
        )''')
        
        c.execute('''CREATE TABLE IF NOT EXISTS agents (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, status TEXT DEFAULT 'idle',
            current_task_id TEXT, capabilities TEXT, load REAL DEFAULT 0.0,
            max_concurrent INTEGER DEFAULT 3, last_heartbeat TEXT,
            cpu_usage REAL DEFAULT 0.0, memory_usage REAL DEFAULT 0.0
        )''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_tasks_priority ON tasks(priority DESC)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_agents_status ON agents(status)')
        
        conn.commit()
        conn.close()
    
    def get_connection(self):
        return sqlite3.connect(self.db_path)
    
    def add_task(self, task: QueuedTask) -> QueuedTask:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT INTO tasks (id, name, payload, priority, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)''',
            (task.id, task.name, json.dumps(task.payload), task.priority, 
             task.status, task.created_at))
        conn.commit()
        conn.close()
        return task
    
    def get_task(self, task_id: str) -> QueuedTask:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM tasks WHERE id = ?', (task_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return QueuedTask(
                id=row[0], name=row[1], payload=json.loads(row[2]) if row[2] else {},
                priority=row[3], status=row[4], agent_id=row[5],
                created_at=row[6], started_at=row[7], completed_at=row[8],
                result=json.loads(row[9]) if row[9] else None,
                error=row[10], retry_count=row[11]
            )
        return None
    
    def get_pending_tasks(self, limit: int = 100) -> list:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT * FROM tasks WHERE status = 'pending' 
            ORDER BY priority DESC, created_at ASC LIMIT ?''', (limit,))
        rows = c.fetchall()
        conn.close()
        return [QueuedTask(
            id=r[0], name=r[1], payload=json.loads(r[2]) if r[2] else {},
            priority=r[3], status=r[4], agent_id=r[5], created_at=r[6],
            started_at=r[7], completed_at=r[8], result=json.loads(r[9]) if r[9] else None,
            error=r[10], retry_count=r[11]
        ) for r in rows]
    
    def update_task(self, task: QueuedTask):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE tasks SET status=?, agent_id=?, started_at=?, 
            completed_at=?, result=?, error=?, retry_count=? WHERE id=?''',
            (task.status, task.agent_id, task.started_at, task.completed_at,
             json.dumps(task.result) if task.result else None,
             task.error, task.retry_count, task.id))
        conn.commit()
        conn.close()
    
    def get_task_stats(self) -> dict:
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
    
    def register_agent(self, agent: AgentNode) -> AgentNode:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''INSERT OR REPLACE INTO agents 
            (id, name, status, capabilities, load, max_concurrent, last_heartbeat, cpu_usage, memory_usage)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (agent.id, agent.name, agent.status, json.dumps(agent.capabilities),
             agent.load, agent.max_concurrent, agent.last_heartbeat, 
             agent.cpu_usage, agent.memory_usage))
        conn.commit()
        conn.close()
        return agent
    
    def get_agent(self, agent_id: str) -> AgentNode:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM agents WHERE id = ?', (agent_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return AgentNode(
                id=row[0], name=row[1], status=row[2], current_task_id=row[3],
                capabilities=json.loads(row[4]) if row[4] else [],
                load=row[5], max_concurrent=row[6], last_heartbeat=row[7],
                cpu_usage=row[8], memory_usage=row[9]
            )
        return None
    
    def get_idle_agents(self) -> list:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''SELECT * FROM agents WHERE status = 'idle' 
            AND load < 1.0 ORDER BY load ASC''')
        rows = c.fetchall()
        conn.close()
        return [AgentNode(
            id=r[0], name=r[1], status=r[2], current_task_id=r[3],
            capabilities=json.loads(r[4]) if r[4] else [],
            load=r[5], max_concurrent=r[6], last_heartbeat=r[7],
            cpu_usage=r[8], memory_usage=r[9]
        ) for r in rows]
    
    def get_all_agents(self) -> list:
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('SELECT * FROM agents')
        rows = c.fetchall()
        conn.close()
        return [AgentNode(
            id=r[0], name=r[1], status=r[2], current_task_id=r[3],
            capabilities=json.loads(r[4]) if r[4] else [],
            load=r[5], max_concurrent=r[6], last_heartbeat=r[7],
            cpu_usage=r[8], memory_usage=r[9]
        ) for r in rows]
    
    def update_agent(self, agent: AgentNode):
        conn = self.get_connection()
        c = conn.cursor()
        c.execute('''UPDATE agents SET status=?, current_task_id=?, 
            load=?, last_heartbeat=?, cpu_usage=?, memory_usage=? WHERE id=?''',
            (agent.status, agent.current_task_id, agent.load, agent.last_heartbeat,
             agent.cpu_usage, agent.memory_usage, agent.id))
        conn.commit()
        conn.close()
    
    def get_agent_stats(self) -> dict:
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

# ============ 负载均衡策略 ============

class LoadBalancer:
    """智能负载均衡器"""
    
    STRATEGIES = {
        'least_load': '最小负载',
        'round_robin': '轮询',
        'capability_match': '能力匹配',
        'weighted': '加权',
        'health_based': '健康加权'
    }
    
    def __init__(self, db: QueueDatabase, strategy: str = 'least_load'):
        self.db = db
        self.strategy = strategy
        self._round_robin_index = 0
    
    def select_agent(self, task: QueuedTask = None) -> AgentNode:
        """选择最佳Agent"""
        idle_agents = self.db.get_idle_agents()
        
        if not idle_agents:
            return None
        
        strategy = self.strategy
        
        # 检查任务所需能力
        required_cap = task.payload.get('required_capability') if task and task.payload else None
        
        if strategy == 'least_load':
            return min(idle_agents, key=lambda a: a.load)
        
        elif strategy == 'round_robin':
            agent = idle_agents[self._round_robin_index % len(idle_agents)]
            self._round_robin_index += 1
            return agent
        
        elif strategy == 'capability_match':
            if required_cap:
                capable = [a for a in idle_agents if required_cap in a.capabilities]
                if capable:
                    return min(capable, key=lambda a: a.load)
                return None
            return min(idle_agents, key=lambda a: a.load)
        
        elif strategy == 'weighted':
            total_weight = sum(a.max_concurrent for a in idle_agents)
            import random
            r = random.uniform(0, total_weight)
            cumulative = 0
            for a in idle_agents:
                cumulative += a.max_concurrent
                if r <= cumulative:
                    return a
            return idle_agents[-1]
        
        elif strategy == 'health_based':
            # 综合健康评分
            def health_score(a):
                load_score = 1 - a.load
                cpu_score = 1 - (a.cpu_usage / 100) if a.cpu_usage else 1
                mem_score = 1 - (a.memory_usage / 100) if a.memory_usage else 1
                return (load_score * 0.5 + cpu_score * 0.3 + mem_score * 0.2)
            return max(idle_agents, key=health_score)
        
        return idle_agents[0]
    
    def distribute_task(self, task: QueuedTask) -> tuple:
        """分发任务给Agent"""
        agent = self.select_agent(task)
        if not agent:
            return None, None
        
        # 更新状态
        task.agent_id = agent.id
        task.status = "running"
        task.started_at = datetime.now().isoformat()
        
        agent.status = "busy"
        agent.current_task_id = task.id
        agent.load = min(1.0, agent.load + (1.0 / agent.max_concurrent))
        
        self.db.update_task(task)
        self.db.update_agent(agent)
        
        return task, agent

# ============ 队列管理器 ============

class TaskQueueManager:
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/agents/data/task_queue.db"):
        import os
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.db = QueueDatabase(db_path)
        self.lb = LoadBalancer(self.db)
    
    def enqueue(self, name: str, payload: dict = None, priority: int = 1) -> QueuedTask:
        """添加任务"""
        task = QueuedTask(
            id=str(uuid.uuid4()),
            name=name,
            payload=payload or {},
            priority=priority
        )
        return self.db.add_task(task)
    
    def auto_distribute(self, max_tasks: int = 20) -> dict:
        """自动分发任务"""
        pending = self.db.get_pending_tasks(max_tasks)
        distributed = 0
        failed = 0
        
        for task in pending:
            task, agent = self.lb.distribute_task(task)
            if task:
                distributed += 1
            else:
                failed += 1
        
        return {"distributed": distributed, "failed": failed, "pending": len(pending)}
    
    def register_agent(self, agent_id: str, name: str, capabilities: list = None, 
                       max_concurrent: int = 3) -> AgentNode:
        """注册Agent"""
        agent = AgentNode(
            id=agent_id,
            name=name,
            capabilities=capabilities or [],
            max_concurrent=max_concurrent
        )
        return self.db.register_agent(agent)
    
    def heartbeat(self, agent_id: str, cpu: float = 0, mem: float = 0):
        """Agent心跳"""
        agent = self.db.get_agent(agent_id)
        if agent:
            agent.last_heartbeat = datetime.now().isoformat()
            agent.cpu_usage = cpu
            agent.memory_usage = mem
            if agent.status == "offline":
                agent.status = "idle"
            self.db.update_agent(agent)
    
    def complete_task(self, task_id: str, result: dict = None, error: str = None):
        """完成任务"""
        task = self.db.get_task(task_id)
        if not task:
            return
        
        task.status = "completed" if not error else "failed"
        task.completed_at = datetime.now().isoformat()
        task.result = result
        task.error = error
        
        self.db.update_task(task)
        
        if task.agent_id:
            agent = self.db.get_agent(task.agent_id)
            if agent:
                agent.status = "idle"
                agent.current_task_id = None
                agent.load = max(0, agent.load - (1.0 / agent.max_concurrent))
                self.db.update_agent(agent)
    
    def get_summary(self) -> dict:
        """获取系统摘要"""
        return {
            "tasks": self.db.get_task_stats(),
            "agents": self.db.get_agent_stats(),
            "strategy": self.lb.strategy,
            "strategies": self.lb.STRATEGIES,
            "pending_tasks": [
                {"id": t.id, "name": t.name, "priority": t.priority, "created_at": t.created_at}
                for t in self.db.get_pending_tasks(10)
            ],
            "idle_agents": [
                {"id": a.id, "name": a.name, "load": round(a.load, 2), "capabilities": a.capabilities}
                for a in self.db.get_idle_agents()
            ]
        }

# ============ Flask API ============

queue_mgr = TaskQueueManager()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy", 
        "service": "agent-task-queue-api",
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/summary', methods=['GET'])
def summary():
    return jsonify(queue_mgr.get_summary())

@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    return jsonify({"strategy": queue_mgr.lb.strategy, "available": queue_mgr.lb.STRATEGIES})

@app.route('/api/strategy', methods=['PUT'])
def set_strategy():
    data = request.json or {}
    strategy = data.get('strategy', 'least_load')
    if strategy in queue_mgr.lb.STRATEGIES:
        queue_mgr.lb.strategy = strategy
        return jsonify({"message": "Strategy updated", "strategy": strategy})
    return jsonify({"error": "Invalid strategy"}), 400

# ===== 任务API =====
@app.route('/api/tasks/enqueue', methods=['POST'])
def enqueue_task():
    data = request.json or {}
    task = queue_mgr.enqueue(
        name=data.get('name', 'unnamed'),
        payload=data.get('payload', {}),
        priority=data.get('priority', 1)
    )
    return jsonify({
        "task_id": task.id, 
        "status": task.status,
        "priority": task.priority,
        "created_at": task.created_at
    })

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    status = request.args.get('status')
    if status:
        tasks = [t for t in queue_mgr.db.get_pending_tasks(100) if t.status == status]
    else:
        tasks = queue_mgr.db.get_pending_tasks(100)
    return jsonify([{
        "id": t.id, "name": t.name, "priority": t.priority,
        "status": t.status, "agent_id": t.agent_id, "created_at": t.created_at
    } for t in tasks])

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    task = queue_mgr.db.get_task(task_id)
    if task:
        return jsonify(asdict(task))
    return jsonify({"error": "Not found"}), 404

@app.route('/api/tasks/<task_id>/complete', methods=['POST'])
def complete_task(task_id):
    data = request.json or {}
    queue_mgr.complete_task(task_id, data.get('result'), data.get('error'))
    return jsonify({"status": "completed", "task_id": task_id})

@app.route('/api/tasks/<task_id>/retry', methods=['POST'])
def retry_task(task_id):
    task = queue_mgr.db.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    task.status = "pending"
    task.retry_count += 1
    task.error = None
    queue_mgr.db.update_task(task)
    return jsonify({"status": "retried", "retry_count": task.retry_count})

# ===== Agent API =====
@app.route('/api/agents/register', methods=['POST'])
def register_agent():
    data = request.json or {}
    agent = queue_mgr.register_agent(
        agent_id=data.get('id', str(uuid.uuid4())),
        name=data.get('name', 'unknown'),
        capabilities=data.get('capabilities', []),
        max_concurrent=data.get('max_concurrent', 3)
    )
    return jsonify({"agent_id": agent.id, "name": agent.name, "status": "registered"})

@app.route('/api/agents', methods=['GET'])
def list_agents():
    agents = queue_mgr.db.get_all_agents()
    return jsonify([{
        "id": a.id, "name": a.name, "status": a.status,
        "load": round(a.load, 2), "capabilities": a.capabilities,
        "current_task_id": a.current_task_id, "max_concurrent": a.max_concurrent,
        "last_heartbeat": a.last_heartbeat
    } for a in agents])

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    agent = queue_mgr.db.get_agent(agent_id)
    if agent:
        return jsonify(asdict(agent))
    return jsonify({"error": "Agent not found"}), 404

@app.route('/api/agents/<agent_id>/heartbeat', methods=['POST'])
def agent_heartbeat(agent_id):
    data = request.json or {}
    queue_mgr.heartbeat(agent_id, data.get('cpu', 0), data.get('memory', 0))
    return jsonify({"status": "ok"})

@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def unregister_agent(agent_id):
    agent = queue_mgr.db.get_agent(agent_id)
    if agent:
        agent.status = "offline"
        queue_mgr.db.update_agent(agent)
        return jsonify({"status": "offline", "agent_id": agent_id})
    return jsonify({"error": "Agent not found"}), 404

# ===== 分发API =====
@app.route('/api/distribute', methods=['POST'])
def distribute():
    result = queue_mgr.auto_distribute()
    return jsonify(result)

# ===== 批量操作 =====
@app.route('/api/batch/enqueue', methods=['POST'])
def batch_enqueue():
    data = request.json or {}
    tasks = data.get('tasks', [])
    created = []
    for t in tasks:
        task = queue_mgr.enqueue(
            name=t.get('name', 'unnamed'),
            payload=t.get('payload', {}),
            priority=t.get('priority', 1)
        )
        created.append({"task_id": task.id, "name": task.name})
    return jsonify({"created": len(created), "tasks": created})

# 自动分发循环
def auto_distribute_loop():
    while True:
        time.sleep(5)
        try:
            queue_mgr.auto_distribute()
        except Exception as e:
            print(f"Auto distribute error: {e}")

if __name__ == '__main__':
    # 启动自动分发线程
    t = threading.Thread(target=auto_distribute_loop, daemon=True)
    t.start()
    
    print("🚀 Agent任务队列API启动: http://0.0.0.0:18128")
    print("📋 负载均衡策略: least_load, round_robin, capability_match, weighted, health_based")
    app.run(host='0.0.0.0', port=18128, debug=False, threaded=True)