#!/usr/bin/env python3
"""
Agent服务编排引擎
端口: 18102
功能: 多Agent协作编排、任务调度、事件驱动执行
"""

import json
import time
import uuid
import asyncio
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from collections import defaultdict
import sqlite3

class OrchestrationStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

class AgentCapability(Enum):
    EXECUTION = "execution"          # 执行任务
    MONITORING = "monitoring"        # 监控
    ANALYSIS = "analysis"            # 分析
    COMMUNICATION = "communication"  # 通信
    ORCHESTRATION = "orchestration"  # 编排
    LEARNING = "learning"            # 学习

@dataclass
class AgentSpec:
    id: str
    name: str
    capabilities: List[str]
    endpoint: str
    status: str = "offline"
    metadata: Dict = field(default_factory=dict)

@dataclass
class OrchestrationTask:
    id: str
    orchestration_id: str
    agent_id: str
    action: str
    params: Dict
    depends_on: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None

@dataclass
class Orchestration:
    id: str
    name: str
    description: str
    agents: List[str]  # Agent IDs
    tasks: List[OrchestrationTask]
    status: OrchestrationStatus = OrchestrationStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    ended_at: Optional[str] = None
    result: Optional[Dict] = None


class AgentRegistry:
    """Agent注册表"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
        self.lock = threading.Lock()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                capabilities TEXT NOT NULL,
                endpoint TEXT NOT NULL,
                status TEXT DEFAULT 'offline',
                metadata TEXT,
                last_seen TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def register(self, agent: AgentSpec) -> bool:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                INSERT OR REPLACE INTO agents (id, name, capabilities, endpoint, status, metadata, last_seen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (agent.id, agent.name, json.dumps(agent.capabilities), agent.endpoint,
                  agent.status, json.dumps(agent.metadata), datetime.now().isoformat()))
            conn.commit()
            conn.close()
        return True
    
    def unregister(self, agent_id: str) -> bool:
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM agents WHERE id = ?", (agent_id,))
            conn.commit()
            conn.close()
        return True
    
    def get(self, agent_id: str) -> Optional[AgentSpec]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM agents WHERE id = ?", (agent_id,))
        row = cur.fetchone()
        conn.close()
        
        if row:
            return AgentSpec(
                id=row["id"],
                name=row["name"],
                capabilities=json.loads(row["capabilities"]),
                endpoint=row["endpoint"],
                status=row["status"],
                metadata=json.loads(row["metadata"] or "{}")
            )
        return None
    
    def list_all(self) -> List[AgentSpec]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute("SELECT * FROM agents ORDER BY last_seen DESC")
        rows = cur.fetchall()
        conn.close()
        
        return [
            AgentSpec(
                id=row["id"],
                name=row["name"],
                capabilities=json.loads(row["capabilities"]),
                endpoint=row["endpoint"],
                status=row["status"],
                metadata=json.loads(row["metadata"] or "{}")
            )
            for row in rows
        ]
    
    def find_by_capability(self, capability: str) -> List[AgentSpec]:
        all_agents = self.list_all()
        return [a for a in all_agents if capability in a.capabilities]
    
    def update_status(self, agent_id: str, status: str):
        with self.lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("UPDATE agents SET status = ?, last_seen = ? WHERE id = ?",
                        (status, datetime.now().isoformat(), agent_id))
            conn.commit()
            conn.close()


class OrchestrationEngine:
    """编排引擎"""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.registry = AgentRegistry(db_path)
        self.orchestrations: Dict[str, Orchestration] = {}
        self.task_handlers: Dict[str, Callable] = {}
        self.lock = threading.Lock()
        self._init_db()
        self._register_default_handlers()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orchestrations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                agents TEXT NOT NULL,
                tasks TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                result TEXT,
                created_at TEXT,
                started_at TEXT,
                ended_at TEXT
            )
        """)
        conn.commit()
        conn.close()
    
    def _register_default_handlers(self):
        """注册默认任务处理器"""
        
        def http_handler(params: Dict) -> Dict:
            import urllib.request
            try:
                url = params.get("url", "")
                method = params.get("method", "GET")
                data = params.get("data")
                
                req = urllib.request.Request(url, method=method)
                if data:
                    req.data = json.dumps(data).encode()
                    req.add_header("Content-Type", "application/json")
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return {
                        "success": True,
                        "status": resp.status,
                        "body": resp.read().decode("utf-8")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        def shell_handler(params: Dict) -> Dict:
            import subprocess
            try:
                cmd = params.get("command", "")
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=300)
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        def agent_handler(params: Dict) -> Dict:
            """Agent间通信处理器"""
            try:
                target_agent = params.get("agent_id")
                action = params.get("action")
                payload = params.get("payload", {})
                
                agent = self.registry.get(target_agent)
                if not agent:
                    return {"success": False, "error": f"Agent {target_agent} not found"}
                
                # 通过HTTP调用目标Agent
                import urllib.request
                url = f"{agent.endpoint}/api/execute"
                req = urllib.request.Request(url, method="POST")
                req.data = json.dumps({"action": action, "payload": payload}).encode()
                req.add_header("Content-Type", "application/json")
                
                with urllib.request.urlopen(req, timeout=30) as resp:
                    return {
                        "success": True,
                        "status": resp.status,
                        "response": resp.read().decode("utf-8")
                    }
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        self.task_handlers["http"] = http_handler
        self.task_handlers["shell"] = shell_handler
        self.task_handlers["agent"] = agent_handler
    
    def register_agent(self, agent: AgentSpec) -> bool:
        """注册Agent"""
        return self.registry.register(agent)
    
    def discover_agents(self) -> List[AgentSpec]:
        """自动发现可用Agent"""
        discovered = []
        
        # 从健康检测服务获取Agent信息
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:18101/api/health/agents")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for agent_data in data.get("agents", []):
                    agent = AgentSpec(
                        id=agent_data.get("id", ""),
                        name=agent_data.get("name", ""),
                        capabilities=agent_data.get("capabilities", []),
                        endpoint=agent_data.get("endpoint", ""),
                        status=agent_data.get("status", "unknown")
                    )
                    discovered.append(agent)
        except:
            pass
        
        # 从任务队列服务获取Agent信息
        try:
            import urllib.request
            req = urllib.request.Request("http://localhost:18099/api/agents")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                for agent_data in data.get("agents", []):
                    if not any(a.id == agent_data.get("id") for a in discovered):
                        agent = AgentSpec(
                            id=agent_data.get("id", ""),
                            name=agent_data.get("name", ""),
                            capabilities=agent_data.get("capabilities", []),
                            endpoint=agent_data.get("endpoint", ""),
                            status=agent_data.get("status", "unknown")
                        )
                        discovered.append(agent)
        except:
            pass
        
        return discovered
    
    def create_orchestration(self, name: str, description: str, 
                            agents: List[str], tasks: List[Dict]) -> str:
        """创建编排"""
        orch_id = f"orch_{uuid.uuid4().hex[:8]}"
        
        task_objects = []
        for t in tasks:
            task = OrchestrationTask(
                id=f"task_{uuid.uuid4().hex[:6]}",
                orchestration_id=orch_id,
                agent_id=t.get("agent_id", ""),
                action=t.get("action", "shell"),
                params=t.get("params", {}),
                depends_on=t.get("depends_on", [])
            )
            task_objects.append(task)
        
        orchestration = Orchestration(
            id=orch_id,
            name=name,
            description=description,
            agents=agents,
            tasks=task_objects
        )
        
        with self.lock:
            self.orchestrations[orch_id] = orchestration
        
        return orch_id
    
    def get_ready_tasks(self, orchestration: Orchestration) -> List[OrchestrationTask]:
        """获取就绪任务"""
        ready = []
        completed_ids = {t.id for t in orchestration.tasks if t.status == "completed"}
        
        for task in orchestration.tasks:
            if task.status == "pending":
                deps_met = all(dep in completed_ids for dep in task.depends_on)
                if deps_met:
                    ready.append(task)
        
        return ready
    
    def execute_task(self, task: OrchestrationTask) -> Dict:
        """执行单个任务"""
        task.status = "running"
        task.start_time = datetime.now().isoformat()
        
        handler = self.task_handlers.get(task.action, self.task_handlers["shell"])
        
        try:
            result = handler(task.params)
            if result.get("success", False):
                task.status = "completed"
                task.result = result
            else:
                task.status = "failed"
                task.error = result.get("error", "Unknown error")
        except Exception as e:
            task.error = str(e)
            task.status = "failed"
        
        task.end_time = datetime.now().isoformat()
        return asdict(task)
    
    def run_orchestration(self, orch_id: str) -> Dict:
        """运行编排"""
        with self.lock:
            orchestration = self.orchestrations.get(orch_id)
            if not orchestration:
                return {"success": False, "error": "Orchestration not found"}
            
            if orchestration.status != OrchestrationStatus.PENDING:
                return {"success": False, "error": f"Orchestration already {orchestration.status.value}"}
        
        orchestration.status = OrchestrationStatus.RUNNING
        orchestration.started_at = datetime.now().isoformat()
        
        while True:
            ready_tasks = self.get_ready_tasks(orchestration)
            
            if not ready_tasks:
                failed = [t for t in orchestration.tasks if t.status == "failed"]
                if failed:
                    orchestration.status = OrchestrationStatus.FAILED
                    orchestration.ended_at = datetime.now().isoformat()
                    return {"success": False, "failed_tasks": [t.id for t in failed]}
                
                completed = all(t.status == "completed" for t in orchestration.tasks)
                if completed:
                    orchestration.status = OrchestrationStatus.COMPLETED
                    orchestration.ended_at = datetime.now().isoformat()
                    orchestration.result = {
                        "tasks_completed": len(orchestration.tasks),
                        "duration_seconds": (
                            datetime.fromisoformat(orchestration.ended_at) - 
                            datetime.fromisoformat(orchestration.started_at)
                        ).total_seconds()
                    }
                    return {"success": True, "result": orchestration.result}
                
                break
            
            for task in ready_tasks:
                self.execute_task(task)
        
        return {"success": False, "error": "Orchestration deadlocked"}
    
    def get_status(self, orch_id: str) -> Optional[Dict]:
        """获取编排状态"""
        with self.lock:
            orch = self.orchestrations.get(orch_id)
            if not orch:
                return None
            
            return {
                "id": orch.id,
                "name": orch.name,
                "description": orch.description,
                "agents": orch.agents,
                "status": orch.status.value,
                "created_at": orch.created_at,
                "started_at": orch.started_at,
                "ended_at": orch.ended_at,
                "tasks": [
                    {
                        "id": t.id,
                        "agent_id": t.agent_id,
                        "action": t.action,
                        "status": t.status,
                        "result": t.result,
                        "error": t.error
                    }
                    for t in orch.tasks
                ],
                "result": orch.result
            }
    
    def list_orchestrations(self) -> List[Dict]:
        """列出所有编排"""
        with self.lock:
            return [
                {
                    "id": o.id,
                    "name": o.name,
                    "status": o.status.value,
                    "created_at": o.created_at,
                    "tasks_count": len(o.tasks),
                    "completed": sum(1 for t in o.tasks if t.status == "completed")
                }
                for o in self.orchestrations.values()
            ]


# 全局引擎实例
_engine = None
_lock = threading.Lock()

def get_engine() -> OrchestrationEngine:
    global _engine
    with _lock:
        if _engine is None:
            _engine = OrchestrationEngine("/tmp/orchestrator.db")
        return _engine