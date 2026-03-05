#!/usr/bin/env python3
"""
Agent协作中心 - API服务
提供协作网络的统一API入口，管理Agent注册、任务分发、消息路由
集成任务执行引擎：支持Shell/Agent/API/工作流等执行类型
"""

import json
import time
import uuid
import logging
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum
from flask import Flask, request, jsonify, Response
from functools import wraps
from threading import Thread

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


class AgentStatus(Enum):
    """Agent状态"""
    REGISTERED = "registered"
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"
    UNHEALTHY = "unhealthy"


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    SCHEDULED = "scheduled"  # 定时任务，等待调度
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(Enum):
    """任务优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskExecutionEngine:
    """任务执行引擎 - 集成多种执行类型"""
    
    # 执行类型
    EXEC_TYPE_SHELL = "shell"
    EXEC_TYPE_AGENT = "agent"
    EXEC_TYPE_API = "api"
    EXEC_TYPE_WORKFLOW = "workflow"
    EXEC_TYPE_HTTP = "http"
    
    def __init__(self):
        self.workspace = "/root/.openclaw/workspace"
        self.execution_history: List[Dict] = []
        
    def execute(self, task_type: str, payload: Dict) -> Dict:
        """执行任务"""
        execution_id = str(uuid.uuid4())[:8]
        start_time = datetime.now().isoformat()
        
        result = {
            "execution_id": execution_id,
            "task_type": task_type,
            "payload": payload,
            "start_time": start_time,
            "status": "running"
        }
        
        try:
            if task_type == self.EXEC_TYPE_SHELL:
                result.update(self._execute_shell(payload))
            elif task_type == self.EXEC_TYPE_AGENT:
                result.update(self._execute_agent(payload))
            elif task_type == self.EXEC_TYPE_API:
                result.update(self._execute_api(payload))
            elif task_type == self.EXEC_TYPE_WORKFLOW:
                result.update(self._execute_workflow(payload))
            elif task_type == self.EXEC_TYPE_HTTP:
                result.update(self._execute_http(payload))
            else:
                result.update({
                    "status": "failed",
                    "error": f"未知执行类型: {task_type}"
                })
        except Exception as e:
            result.update({
                "status": "failed",
                "error": str(e)
            })
        
        result["end_time"] = datetime.now().isoformat()
        self.execution_history.append(result)
        return result
    
    def _execute_shell(self, payload: Dict) -> Dict:
        """执行Shell命令"""
        cmd = payload.get("command", "")
        timeout = payload.get("timeout", 300)
        cwd = payload.get("cwd", self.workspace)
        
        try:
            proc = subprocess.Popen(
                cmd, shell=True, stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, text=True, cwd=cwd
            )
            stdout, stderr = proc.communicate(timeout=timeout)
            return {
                "status": "completed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "stdout": stdout[:5000],
                "stderr": stderr[:2000]
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"status": "failed", "error": "命令执行超时"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _execute_agent(self, payload: Dict) -> Dict:
        """执行Agent任务"""
        task = payload.get("task", "")
        runtime = payload.get("runtime", "subagent")
        mode = payload.get("mode", "run")
        timeout = payload.get("timeout", 300)
        
        try:
            cmd = [
                "openclaw", "sessions", "spawn",
                "--runtime", runtime,
                "--mode", mode,
                "--timeoutSeconds", str(timeout),
                "--task", task
            ]
            proc = subprocess.Popen(
                cmd, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True,
                cwd=self.workspace
            )
            stdout, stderr = proc.communicate(timeout=timeout + 30)
            return {
                "status": "completed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "stdout": stdout[:5000],
                "stderr": stderr[:2000]
            }
        except subprocess.TimeoutExpired:
            proc.kill()
            return {"status": "failed", "error": "Agent执行超时"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _execute_api(self, payload: Dict) -> Dict:
        """调用API服务"""
        service = payload.get("service", "")
        endpoint = payload.get("endpoint", "")
        method = payload.get("method", "GET")
        data = payload.get("data", {})
        
        # 已知服务映射
        service_ports = {
            "workflow": "18100",
            "decision": "18120",
            "automation": "18128",
            "collab": "18150",
            "executor": "18210"
        }
        
        port = service_ports.get(service, "18000")
        url = f"http://localhost:{port}{endpoint}"
        
        try:
            if method == "GET":
                resp = requests.get(url, timeout=30)
            elif method == "POST":
                resp = requests.post(url, json=data, timeout=30)
            else:
                return {"status": "failed", "error": f"不支持的方法: {method}"}
            
            return {
                "status": "completed" if resp.status_code < 400 else "failed",
                "status_code": resp.status_code,
                "response": resp.text[:3000]
            }
        except requests.exceptions.Timeout:
            return {"status": "failed", "error": "API请求超时"}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _execute_workflow(self, payload: Dict) -> Dict:
        """执行工作流"""
        workflow_id = payload.get("workflow_id")
        params = payload.get("params", {})
        
        if not workflow_id:
            return {"status": "failed", "error": "需要指定workflow_id"}
        
        try:
            # 调用工作流引擎API
            resp = requests.post(
                f"http://localhost:18100/api/workflows/{workflow_id}/execute",
                json=params, timeout=60
            )
            return {
                "status": "completed" if resp.status_code < 400 else "failed",
                "status_code": resp.status_code,
                "response": resp.text[:3000]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def _execute_http(self, payload: Dict) -> Dict:
        """执行HTTP请求"""
        url = payload.get("url", "")
        method = payload.get("method", "GET")
        headers = payload.get("headers", {})
        body = payload.get("body")
        
        if not url:
            return {"status": "failed", "error": "需要指定url"}
        
        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=30)
            elif method == "POST":
                resp = requests.post(url, headers=headers, json=body, timeout=30)
            elif method == "PUT":
                resp = requests.put(url, headers=headers, json=body, timeout=30)
            elif method == "DELETE":
                resp = requests.delete(url, headers=headers, timeout=30)
            else:
                return {"status": "failed", "error": f"不支持的方法: {method}"}
            
            return {
                "status": "completed" if resp.status_code < 400 else "failed",
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "response": resp.text[:5000]
            }
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def get_execution_history(self, limit: int = 50) -> List[Dict]:
        """获取执行历史"""
        return self.execution_history[-limit:]


class CollaborationHub:
    """协作中心核心类"""
    
    def __init__(self):
        # Agent注册表
        self.agents: Dict[str, Dict] = {}
        
        # 协作链接
        self.collaboration_links: Dict[str, Dict] = {}
        
        # 任务队列 (优先级队列)
        self.tasks: Dict[str, Dict] = {}
        self.task_queue: List[str] = []
        self.priority_queue: Dict[int, List[str]] = {
            TaskPriority.LOW.value: [],
            TaskPriority.NORMAL.value: [],
            TaskPriority.HIGH.value: [],
            TaskPriority.CRITICAL.value: []
        }
        
        # 定时任务 (未来某个时间点执行)
        self.scheduled_tasks: Dict[str, Dict] = {}
        
        # 周期性任务 (cron-like)
        self.periodic_tasks: Dict[str, Dict] = {}
        
        # 任务依赖关系
        self.task_dependencies: Dict[str, List[str]] = {}
        
        # 任务重试配置
        self.task_retry_config: Dict[str, Dict] = {}
        
        # 消息交换记录
        self.message_log: List[Dict] = []
        
        # 任务执行引擎
        self.execution_engine = TaskExecutionEngine()
        
        # 指标
        self.metrics = {
            "total_requests": 0,
            "total_tasks": 0,
            "total_agents": 0,
            "total_messages": 0,
            "start_time": time.time()
        }
        
        logger.info("协作中心初始化完成")
    
    def register_agent(self, agent_id: str, name: str = None, 
                       capabilities: List[str] = None, 
                       metadata: Dict = None) -> Dict:
        """注册Agent"""
        timestamp = datetime.now().isoformat()
        
        self.agents[agent_id] = {
            "agent_id": agent_id,
            "name": name or agent_id,
            "capabilities": capabilities or [],
            "metadata": metadata or {},
            "status": AgentStatus.ACTIVE.value,
            "registered_at": timestamp,
            "last_heartbeat": timestamp,
            "tasks_completed": 0,
            "tasks_failed": 0,
            "collaborations": 0
        }
        
        self.metrics["total_agents"] = len(self.agents)
        
        # 建立与现有Agent的协作链接
        for existing_id in self.agents:
            if existing_id != agent_id:
                self._create_link(agent_id, existing_id)
        
        logger.info(f"Agent注册: {agent_id}, 已有{len(self.agents)}个Agent")
        return self.agents[agent_id]
    
    def _create_link(self, agent_a: str, agent_b: str) -> Dict:
        """创建协作链接"""
        link_id = f"{agent_a}<->{agent_b}"
        
        if link_id not in self.collaboration_links:
            self.collaboration_links[link_id] = {
                "link_id": link_id,
                "agent_a": agent_a,
                "agent_b": agent_b,
                "created_at": datetime.now().isoformat(),
                "messages_exchanged": 0,
                "tasks_coordinated": 0,
                "status": "active"
            }
        
        return self.collaboration_links[link_id]
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent信息"""
        return self.agents.get(agent_id)
    
    def list_agents(self, status: str = None) -> List[Dict]:
        """列出Agent"""
        agents = list(self.agents.values())
        if status:
            agents = [a for a in agents if a.get("status") == status]
        return agents
    
    def get_collaboration_links(self, agent_id: str = None) -> List[Dict]:
        """获取协作链接"""
        if agent_id:
            return [
                link for link in self.collaboration_links.values()
                if link["agent_a"] == agent_id or link["agent_b"] == agent_id
            ]
        return list(self.collaboration_links.values())
    
    def submit_task(self, task_id: str, agent_id: str, 
                    task_type: str, payload: Dict, 
                    priority: int = TaskPriority.NORMAL.value,
                    depends_on: List[str] = None,
                    retry_config: Dict = None) -> Dict:
        """提交任务"""
        timestamp = datetime.now().isoformat()
        
        task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
            "priority": priority,
            "status": TaskStatus.PENDING.value,
            "created_at": timestamp,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None,
            "retry_count": 0,
            "max_retries": retry_config.get("max_retries", 0) if retry_config else 0,
            "timeout": retry_config.get("timeout", 300) if retry_config else 300
        }
        
        self.tasks[task_id] = task
        
        # 处理依赖
        if depends_on:
            self.task_dependencies[task_id] = depends_on
            # 检查依赖是否都已完成
            if not self._check_dependencies_met(depends_on):
                task["status"] = TaskStatus.PENDING.value  # 等待依赖
            else:
                self._add_to_priority_queue(task_id, priority)
        else:
            self._add_to_priority_queue(task_id, priority)
        
        self.metrics["total_tasks"] += 1
        
        logger.info(f"任务提交: {task_id} -> {agent_id}, 优先级: {priority}")
        return task
    
    def _add_to_priority_queue(self, task_id: str, priority: int):
        """添加到优先级队列"""
        self.priority_queue[priority].append(task_id)
        self.task_queue.append(task_id)
    
    def _check_dependencies_met(self, depends_on: List[str]) -> bool:
        """检查依赖任务是否都已完成"""
        for dep_id in depends_on:
            if dep_id not in self.tasks:
                return False
            dep_task = self.tasks[dep_id]
            if dep_task["status"] not in [TaskStatus.COMPLETED.value, TaskStatus.CANCELLED.value]:
                return False
        return True
    
    def get_next_task(self) -> Optional[Dict]:
        """获取下一个待执行任务（按优先级）"""
        # 从高优先级到低优先级查找
        for priority in [TaskPriority.CRITICAL.value, TaskPriority.HIGH.value, 
                        TaskPriority.NORMAL.value, TaskPriority.LOW.value]:
            queue = self.priority_queue[priority]
            while queue:
                task_id = queue.pop(0)
                if task_id in self.tasks:
                    task = self.tasks[task_id]
                    # 检查依赖
                    if self._check_dependencies_met(self.task_dependencies.get(task_id, [])):
                        task["status"] = TaskStatus.RUNNING.value
                        task["started_at"] = datetime.now().isoformat()
                        return task
                    else:
                        # 依赖未满足，移到末尾
                        queue.append(task_id)
        return None
    
    def schedule_task(self, task_id: str, agent_id: str, 
                     task_type: str, payload: Dict,
                     schedule_time: str,  # ISO格式时间
                     priority: int = TaskPriority.NORMAL.value) -> Dict:
        """定时任务调度"""
        timestamp = datetime.now().isoformat()
        
        task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
            "priority": priority,
            "status": TaskStatus.SCHEDULED.value,
            "schedule_time": schedule_time,
            "created_at": timestamp,
            "started_at": None,
            "completed_at": None,
            "result": None,
            "error": None
        }
        
        self.scheduled_tasks[task_id] = task
        logger.info(f"定时任务创建: {task_id}, 计划执行时间: {schedule_time}")
        return task
    
    def schedule_periodic_task(self, task_id: str, agent_id: str,
                               task_type: str, payload: Dict,
                               interval_seconds: int,
                               cron_expression: str = None,
                               priority: int = TaskPriority.NORMAL.value) -> Dict:
        """创建周期性任务"""
        timestamp = datetime.now().isoformat()
        
        periodic_task = {
            "task_id": task_id,
            "agent_id": agent_id,
            "task_type": task_type,
            "payload": payload,
            "priority": priority,
            "interval_seconds": interval_seconds,
            "cron_expression": cron_expression,
            "status": "active",
            "created_at": timestamp,
            "last_run": None,
            "next_run": timestamp,
            "run_count": 0
        }
        
        self.periodic_tasks[task_id] = periodic_task
        logger.info(f"周期性任务创建: {task_id}, 间隔: {interval_seconds}秒")
        return periodic_task
    
    def trigger_periodic_task(self, task_id: str) -> Optional[Dict]:
        """触发周期性任务"""
        if task_id not in self.periodic_tasks:
            return None
        
        periodic = self.periodic_tasks[task_id]
        if periodic["status"] != "active":
            return None
        
        # 创建实际任务执行
        from datetime import timedelta
        import uuid
        
        actual_task_id = f"{task_id}-{uuid.uuid4().hex[:8]}"
        task = self.submit_task(
            actual_task_id,
            periodic["agent_id"],
            periodic["task_type"],
            periodic["payload"],
            periodic["priority"]
        )
        
        # 更新周期性任务状态
        periodic["last_run"] = datetime.now().isoformat()
        periodic["run_count"] += 1
        next_run_time = datetime.now() + timedelta(seconds=periodic["interval_seconds"])
        periodic["next_run"] = next_run_time.isoformat()
        
        logger.info(f"周期性任务触发: {task_id} -> {actual_task_id}")
        return task
    
    def check_scheduled_tasks(self) -> List[Dict]:
        """检查并执行到期的定时任务"""
        triggered = []
        now = datetime.now()
        
        for task_id, task in list(self.scheduled_tasks.items()):
            if task["status"] == TaskStatus.SCHEDULED.value:
                schedule_time = datetime.fromisoformat(task["schedule_time"])
                if schedule_time <= now:
                    # 转为待执行任务
                    task["status"] = TaskStatus.PENDING.value
                    self._add_to_priority_queue(task_id, task["priority"])
                    triggered.append(task)
                    logger.info(f"定时任务触发: {task_id}")
        
        return triggered
    
    def cancel_task(self, task_id: str) -> Optional[Dict]:
        """取消任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task["status"] in [TaskStatus.PENDING.value, TaskStatus.SCHEDULED.value]:
                task["status"] = TaskStatus.CANCELLED.value
                task["completed_at"] = datetime.now().isoformat()
                
                # 从队列中移除
                if task_id in self.task_queue:
                    self.task_queue.remove(task_id)
                for priority_queue in self.priority_queue.values():
                    if task_id in priority_queue:
                        priority_queue.remove(task_id)
                
                logger.info(f"任务已取消: {task_id}")
                return task
        
        if task_id in self.scheduled_tasks:
            task = self.scheduled_tasks[task_id]
            task["status"] = TaskStatus.CANCELLED.value
            logger.info(f"定时任务已取消: {task_id}")
            return task
        
        if task_id in self.periodic_tasks:
            task = self.periodic_tasks[task_id]
            task["status"] = "cancelled"
            logger.info(f"周期性任务已停止: {task_id}")
            return task
        
        return None
    
    def retry_failed_task(self, task_id: str) -> Optional[Dict]:
        """重试失败任务"""
        if task_id not in self.tasks:
            return None
        
        task = self.tasks[task_id]
        if task["status"] != TaskStatus.FAILED.value:
            return None
        
        if task["retry_count"] >= task["max_retries"]:
            logger.warning(f"任务重试次数超限: {task_id}")
            return None
        
        # 重置任务状态
        task["status"] = TaskStatus.PENDING.value
        task["retry_count"] += 1
        task["error"] = None
        task["result"] = None
        self._add_to_priority_queue(task_id, task["priority"])
        
        logger.info(f"任务重试: {task_id}, 尝试 {task['retry_count']}/{task['max_retries']}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str, status: str, 
                           result: Any = None, error: str = None) -> Optional[Dict]:
        """更新任务状态"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["status"] = status
            task["updated_at"] = datetime.now().isoformat()
            
            if status == TaskStatus.RUNNING.value:
                task["started_at"] = task.get("started_at") or datetime.now().isoformat()
            elif status in [TaskStatus.COMPLETED.value, TaskStatus.FAILED.value]:
                task["completed_at"] = datetime.now().isoformat()
                task["result"] = result
                task["error"] = error
                
                # 更新Agent统计
                agent_id = task.get("agent_id")
                if agent_id in self.agents:
                    if status == TaskStatus.COMPLETED.value:
                        self.agents[agent_id]["tasks_completed"] += 1
                    else:
                        self.agents[agent_id]["tasks_failed"] += 1
            
            return task
        return None
    
    def execute_task(self, task_id: str, task_type: str, payload: Dict,
                     async_mode: bool = False) -> Dict:
        """使用执行引擎执行任务"""
        if task_id in self.tasks:
            task = self.tasks[task_id]
            task["status"] = TaskStatus.RUNNING.value
            task["started_at"] = datetime.now().isoformat()
        
        if async_mode:
            # 异步执行
            thread = Thread(target=self._execute_task_async, 
                          args=(task_id, task_type, payload))
            thread.start()
            return {"task_id": task_id, "status": "async_started"}
        else:
            # 同步执行
            result = self.execution_engine.execute(task_type, payload)
            
            if task_id in self.tasks:
                self.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED.value if result.get("status") == "completed" 
                    else TaskStatus.FAILED.value,
                    result,
                    result.get("error")
                )
            
            return result
    
    def _execute_task_async(self, task_id: str, task_type: str, payload: Dict):
        """异步执行任务"""
        try:
            result = self.execution_engine.execute(task_type, payload)
            
            if task_id in self.tasks:
                self.update_task_status(
                    task_id,
                    TaskStatus.COMPLETED.value if result.get("status") == "completed" 
                    else TaskStatus.FAILED.value,
                    result,
                    result.get("error")
                )
        except Exception as e:
            logger.error(f"异步任务执行失败: {task_id} - {e}")
            if task_id in self.tasks:
                self.update_task_status(task_id, TaskStatus.FAILED.value, None, str(e))
    
    def get_execution_stats(self) -> Dict:
        """获取执行统计"""
        history = self.execution_engine.get_execution_history(100)
        
        total = len(history)
        completed = sum(1 for h in history if h.get("status") == "completed")
        failed = sum(1 for h in history if h.get("status") == "failed")
        
        return {
            "total": total,
            "completed": completed,
            "failed": failed,
            "running": sum(1 for h in history if h.get("status") == "running"),
            "success_rate": round(completed / total * 100, 2) if total > 0 else 0
        }
    
    def exchange_message(self, from_agent: str, to_agent: str, 
                         message: Dict) -> Dict:
        """消息交换"""
        timestamp = datetime.now().isoformat()
        
        msg_record = {
            "message_id": str(uuid.uuid4()),
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "timestamp": timestamp
        }
        
        self.message_log.append(msg_record)
        self.metrics["total_messages"] += 1
        
        # 更新协作链接统计
        link_id = f"{min(from_agent, to_agent)}<->{max(from_agent, to_agent)}"
        if link_id in self.collaboration_links:
            self.collaboration_links[link_id]["messages_exchanged"] += 1
        
        logger.info(f"消息: {from_agent} -> {to_agent}")
        return msg_record
    
    def get_messages(self, agent_id: str = None, limit: int = 100) -> List[Dict]:
        """获取消息记录"""
        messages = self.message_log
        if agent_id:
            messages = [
                m for m in messages 
                if m["from"] == agent_id or m["to"] == agent_id
            ]
        return messages[-limit:]
    
    def get_metrics(self) -> Dict:
        """获取协作中心指标"""
        uptime = time.time() - self.metrics["start_time"]
        return {
            **self.metrics,
            "uptime_seconds": uptime,
            "active_agents": len([a for a in self.agents.values() 
                                 if a["status"] == AgentStatus.ACTIVE.value]),
            "pending_tasks": len(self.task_queue),
            "total_links": len(self.collaboration_links)
        }
    
    def get_hub_status(self) -> Dict:
        """获取协作中心状态"""
        return {
            "hub_id": "ultron-collab-hub",
            "status": "running",
            "agents": {
                "total": len(self.agents),
                "active": len([a for a in self.agents.values() 
                              if a["status"] == AgentStatus.ACTIVE.value]),
                "idle": len([a for a in self.agents.values() 
                            if a["status"] == AgentStatus.IDLE.value]),
                "busy": len([a for a in self.agents.values() 
                            if a["status"] == AgentStatus.BUSY.value])
            },
            "tasks": {
                "total": len(self.tasks),
                "pending": len(self.task_queue),
                "running": len([t for t in self.tasks.values() 
                               if t["status"] == TaskStatus.RUNNING.value]),
                "completed": len([t for t in self.tasks.values() 
                                 if t["status"] == TaskStatus.COMPLETED.value]),
                "scheduled": len(self.scheduled_tasks),
                "periodic": len(self.periodic_tasks)
            },
            "collaboration": {
                "links": len(self.collaboration_links),
                "messages": len(self.message_log)
            },
            "metrics": self.get_metrics()
        }


# 全局协作中心实例
hub = CollaborationHub()


# ========== API路由 ==========

def json_response(f):
    """JSON响应装饰器"""
    @wraps(f)
    def wrapper(*args, **kwargs):
        try:
            hub.metrics["total_requests"] += 1
            result = f(*args, **kwargs)
            return jsonify(result)
        except Exception as e:
            logger.error(f"API错误: {e}")
            return jsonify({"error": str(e)}), 500
    return wrapper


@app.route('/health', methods=['GET'])
@json_response
def health():
    """健康检查"""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}


@app.route('/status', methods=['GET'])
@json_response
def get_status():
    """获取协作中心状态"""
    return hub.get_hub_status()


@app.route('/metrics', methods=['GET'])
@json_response
def get_metrics():
    """获取指标"""
    return hub.get_metrics()


# ========== Agent管理API ==========

@app.route('/agents', methods=['GET'])
@json_response
def list_agents():
    """列出所有Agent"""
    status = request.args.get('status')
    return {"agents": hub.list_agents(status)}


@app.route('/agents/<agent_id>', methods=['GET'])
@json_response
def get_agent(agent_id):
    """获取Agent信息"""
    agent = hub.get_agent(agent_id)
    if not agent:
        return {"error": "Agent不存在"}, 404
    return {"agent": agent}


@app.route('/agents', methods=['POST'])
@json_response
def register_agent():
    """注册Agent"""
    data = request.get_json() or {}
    agent_id = data.get("agent_id", str(uuid.uuid4()))
    name = data.get("name")
    capabilities = data.get("capabilities", [])
    metadata = data.get("metadata", {})
    
    agent = hub.register_agent(agent_id, name, capabilities, metadata)
    return {"agent": agent, "message": "注册成功"}


# ========== 协作链接API ==========

@app.route('/collaboration/links', methods=['GET'])
@json_response
def get_links():
    """获取协作链接"""
    agent_id = request.args.get('agent_id')
    return {"links": hub.get_collaboration_links(agent_id)}


# ========== 任务管理API ==========

@app.route('/tasks', methods=['GET'])
@json_response
def list_tasks():
    """列出任务"""
    status = request.args.get('status')
    tasks = list(hub.tasks.values())
    if status:
        tasks = [t for t in tasks if t.get("status") == status]
    return {"tasks": tasks}


@app.route('/tasks/<task_id>', methods=['GET'])
@json_response
def get_task(task_id):
    """获取任务"""
    task = hub.get_task(task_id)
    if not task:
        return {"error": "任务不存在"}, 404
    return {"task": task}


@app.route('/tasks', methods=['POST'])
@json_response
def submit_task():
    """提交任务"""
    data = request.get_json() or {}
    task_id = data.get("task_id", str(uuid.uuid4()))
    agent_id = data.get("agent_id")
    task_type = data.get("task_type", "generic")
    payload = data.get("payload", {})
    priority = data.get("priority", 1)
    depends_on = data.get("depends_on")
    retry_config = data.get("retry_config")
    
    if not agent_id:
        return {"error": "需要指定agent_id"}, 400
    
    task = hub.submit_task(task_id, agent_id, task_type, payload, priority, depends_on, retry_config)
    return {"task": task, "message": "任务提交成功"}


@app.route('/tasks/<task_id>/status', methods=['PUT'])
@json_response
def update_task_status(task_id):
    """更新任务状态"""
    data = request.get_json() or {}
    status = data.get("status")
    result = data.get("result")
    error = data.get("error")
    
    task = hub.update_task_status(task_id, status, result, error)
    if not task:
        return {"error": "任务不存在"}, 404
    return {"task": task}


@app.route('/tasks/next', methods=['GET'])
@json_response
def get_next_task():
    """获取下一个待执行任务（按优先级）"""
    task = hub.get_next_task()
    if not task:
        return {"task": None, "message": "没有待执行任务"}
    return {"task": task}


@app.route('/tasks/<task_id>/cancel', methods=['POST'])
@json_response
def cancel_task(task_id):
    """取消任务"""
    task = hub.cancel_task(task_id)
    if not task:
        return {"error": "任务不存在"}, 404
    return {"task": task, "message": "任务已取消"}


@app.route('/tasks/<task_id>/retry', methods=['POST'])
@json_response
def retry_task(task_id):
    """重试失败任务"""
    task = hub.retry_failed_task(task_id)
    if not task:
        return {"error": "任务不存在或无法重试"}, 404
    return {"task": task, "message": "任务已重试"}


# ========== 定时任务API ==========

@app.route('/tasks/scheduled', methods=['GET'])
@json_response
def list_scheduled_tasks():
    """列出定时任务"""
    return {"scheduled_tasks": list(hub.scheduled_tasks.values())}


@app.route('/tasks/scheduled', methods=['POST'])
@json_response
def create_scheduled_task():
    """创建定时任务"""
    data = request.get_json() or {}
    task_id = data.get("task_id", str(uuid.uuid4()))
    agent_id = data.get("agent_id")
    task_type = data.get("task_type", "scheduled")
    payload = data.get("payload", {})
    schedule_time = data.get("schedule_time")
    priority = data.get("priority", 1)
    
    if not agent_id or not schedule_time:
        return {"error": "需要指定agent_id和schedule_time"}, 400
    
    task = hub.schedule_task(task_id, agent_id, task_type, payload, schedule_time, priority)
    return {"task": task, "message": "定时任务创建成功"}


@app.route('/tasks/scheduled/check', methods=['POST'])
@json_response
def check_scheduled_tasks():
    """检查并触发到期的定时任务"""
    triggered = hub.check_scheduled_tasks()
    return {"triggered": triggered, "count": len(triggered)}


# ========== 周期性任务API ==========

@app.route('/tasks/periodic', methods=['GET'])
@json_response
def list_periodic_tasks():
    """列出周期性任务"""
    return {"periodic_tasks": list(hub.periodic_tasks.values())}


@app.route('/tasks/periodic', methods=['POST'])
@json_response
def create_periodic_task():
    """创建周期性任务"""
    data = request.get_json() or {}
    task_id = data.get("task_id")
    agent_id = data.get("agent_id")
    task_type = data.get("task_type", "periodic")
    payload = data.get("payload", {})
    interval_seconds = data.get("interval_seconds", 60)
    priority = data.get("priority", 1)
    
    if not task_id or not agent_id:
        return {"error": "需要指定task_id和agent_id"}, 400
    
    task = hub.schedule_periodic_task(
        task_id, agent_id, task_type, payload, 
        interval_seconds, priority=priority
    )
    return {"task": task, "message": "周期性任务创建成功"}


@app.route('/tasks/periodic/<task_id>/trigger', methods=['POST'])
@json_response
def trigger_periodic_task(task_id):
    """手动触发周期性任务"""
    task = hub.trigger_periodic_task(task_id)
    if not task:
        return {"error": "周期性任务不存在"}, 404
    return {"task": task, "message": "周期性任务已触发"}


@app.route('/tasks/periodic/<task_id>/stop', methods=['POST'])
@json_response
def stop_periodic_task(task_id):
    """停止周期性任务"""
    if task_id not in hub.periodic_tasks:
        return {"error": "周期性任务不存在"}, 404
    
    hub.periodic_tasks[task_id]["status"] = "stopped"
    return {"message": "周期性任务已停止"}


# ========== 消息API ==========

# ========== 任务执行API ==========

@app.route('/execute', methods=['POST'])
@json_response
def execute_task():
    """执行任务（同步/异步）"""
    data = request.get_json() or {}
    task_type = data.get("task_type", "shell")  # shell/agent/api/workflow/http
    payload = data.get("payload", {})
    task_id = data.get("task_id", str(uuid.uuid4()))
    async_mode = data.get("async", False)
    
    # 如果提供了task_id，先提交任务
    if task_id and task_id not in hub.tasks:
        agent_id = data.get("agent_id", "executor")
        hub.submit_task(task_id, agent_id, task_type, payload, data.get("priority", 1))
    
    result = hub.execute_task(task_id, task_type, payload, async_mode)
    return {"execution": result}


@app.route('/execute/types', methods=['GET'])
@json_response
def get_execution_types():
    """获取支持的执行类型"""
    return {
        "types": {
            "shell": "执行Shell命令",
            "agent": "触发Agent任务",
            "api": "调用内部API服务",
            "workflow": "执行工作流",
            "http": "发送HTTP请求"
        }
    }


@app.route('/execute/stats', methods=['GET'])
@json_response
def get_execution_stats():
    """获取执行统计"""
    return hub.get_execution_stats()


@app.route('/execute/history', methods=['GET'])
@json_response
def get_execution_history():
    """获取执行历史"""
    limit = int(request.args.get("limit", 50))
    history = hub.execution_engine.get_execution_history(limit)
    return {"history": history}


# ========== 消息API ==========

@app.route('/messages', methods=['GET'])
@json_response
def get_messages():
    """获取消息记录"""
    agent_id = request.args.get('agent_id')
    limit = int(request.args.get('limit', 100))
    return {"messages": hub.get_messages(agent_id, limit)}


@app.route('/messages', methods=['POST'])
@json_response
def send_message():
    """发送消息"""
    data = request.get_json() or {}
    from_agent = data.get("from")
    to_agent = data.get("to")
    message = data.get("message", {})
    
    if not from_agent or not to_agent:
        return {"error": "需要指定from和to"}, 400
    
    msg = hub.exchange_message(from_agent, to_agent, message)
    return {"message": msg, "message": "消息发送成功"}


# ========== 主入口 ==========

if __name__ == '__main__':
    # 初始化默认Agent
    default_agents = [
        {"agent_id": "ultron-core", "name": "奥创核心", 
         "capabilities": ["orchestration", "decision", "learning"]},
        {"agent_id": "health-agent", "name": "健康监控", 
         "capabilities": ["monitoring", "alerting", "healing"]},
        {"agent_id": "task-agent", "name": "任务调度", 
         "capabilities": ["scheduling", "execution", "tracking"]},
        {"agent_id": "log-agent", "name": "日志分析", 
         "capabilities": ["collection", "analysis", "reporting"]}
    ]
    
    for agent in default_agents:
        hub.register_agent(
            agent["agent_id"], 
            agent["name"], 
            agent["capabilities"],
            {"type": "system", "initialized": True}
        )
    
    logger.info(f"协作中心API服务启动，初始化{len(default_agents)}个Agent")
    app.run(host='0.0.0.0', port=8105, debug=False)