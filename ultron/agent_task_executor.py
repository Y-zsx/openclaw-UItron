#!/usr/bin/env python3
"""
Agent任务执行器集成 - Agent Task Executor Integration
第52世: 实现Agent任务执行器集成

功能:
- 任务执行: 通过Agent执行具体任务
- 执行器管理: 多种执行器类型 (shell/http/script/function)
- 结果处理: 成功/失败回调，结果格式化
- 任务追踪: 执行状态实时跟踪
- 超时控制: 任务超时自动终止
"""

import json
import time
import uuid
import asyncio
import subprocess
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from flask import Flask, request, jsonify
import threading
import signal
import os

app = Flask(__name__)

# ============== 数据模型 ==============

class ExecutorType(Enum):
    """执行器类型"""
    SHELL = "shell"           # Shell命令
    HTTP = "http"             # HTTP请求
    SCRIPT = "script"         # Python脚本
    FUNCTION = "function"     # Python函数
    AGENT = "agent"           # Agent协作


class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


@dataclass
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    task_id: str
    executor_type: ExecutorType
    payload: Dict[str, Any]
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    progress: float = 0.0
    agent_id: Optional[str] = None


@dataclass
class TaskDefinition:
    """任务定义"""
    task_id: str
    name: str
    executor_type: ExecutorType
    description: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timeout: int = 300
    retry_count: int = 0
    max_retries: int = 3
    callback_url: Optional[str] = None
    on_success: Optional[Dict] = None
    on_failure: Optional[Dict] = None
    tags: List[str] = field(default_factory=list)


# ============== 执行器实现 ==============

class BaseExecutor:
    """执行器基类"""
    
    def __init__(self):
        self.name = "base"
    
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        raise NotImplementedError
    
    def validate_payload(self, payload: Dict, required_fields: List[str]) -> bool:
        return all(field in payload for field in required_fields)


class ShellExecutor(BaseExecutor):
    """Shell命令执行器"""
    
    def __init__(self):
        self.name = "shell"
        self.processes: Dict[str, subprocess.Popen] = {}
    
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        payload = context.payload
        command = payload.get("command", "")
        cwd = payload.get("cwd", "/root/.openclaw/workspace")
        env = payload.get("env", {})
        
        context.status = ExecutionStatus.RUNNING
        context.progress = 10.0
        
        try:
            # 构建环境变量
            full_env = os.environ.copy()
            full_env.update(env)
            
            # 执行命令
            process = subprocess.Popen(
                command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=cwd,
                env=full_env,
                text=True
            )
            
            self.processes[context.execution_id] = process
            context.progress = 30.0
            
            # 等待完成或超时
            timeout = context.payload.get("timeout", 300)
            try:
                stdout, stderr = process.communicate(timeout=timeout)
                context.stdout = stdout
                context.stderr = stderr
                context.progress = 80.0
                
                if process.returncode == 0:
                    context.status = ExecutionStatus.SUCCESS
                    context.result = {"exit_code": 0, "output": stdout}
                else:
                    context.status = ExecutionStatus.FAILED
                    context.result = {"exit_code": process.returncode, "output": stdout}
                    context.error = stderr
            except subprocess.TimeoutExpired:
                process.kill()
                context.status = ExecutionStatus.TIMEOUT
                context.error = f"Command timed out after {timeout} seconds"
                
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
        
        finally:
            if context.execution_id in self.processes:
                del self.processes[context.execution_id]
            context.end_time = datetime.now()
            context.progress = 100.0
        
        return context


class HttpExecutor(BaseExecutor):
    """HTTP请求执行器"""
    
    def __init__(self):
        self.name = "http"
    
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        payload = context.payload
        url = payload.get("url", "")
        method = payload.get("method", "GET").upper()
        headers = payload.get("headers", {})
        body = payload.get("body")
        timeout = payload.get("timeout", 30)
        
        context.status = ExecutionStatus.RUNNING
        context.progress = 20.0
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                json=body if isinstance(body, (dict, list)) else None,
                data=body if isinstance(body, str) else None,
                timeout=timeout
            )
            context.progress = 80.0
            
            context.result = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": response.text[:10000],  # 限制返回大小
                "elapsed": response.elapsed.total_seconds()
            }
            
            if 200 <= response.status_code < 300:
                context.status = ExecutionStatus.SUCCESS
            else:
                context.status = ExecutionStatus.FAILED
                context.error = f"HTTP {response.status_code}: {response.reason}"
                
        except requests.Timeout:
            context.status = ExecutionStatus.TIMEOUT
            context.error = f"Request timed out after {timeout} seconds"
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
        
        finally:
            context.end_time = datetime.now()
            context.progress = 100.0
        
        return context


class ScriptExecutor(BaseExecutor):
    """Python脚本执行器"""
    
    def __init__(self):
        self.name = "script"
        self.globals: Dict[str, Any] = {}
    
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        payload = context.payload
        script = payload.get("script", "")
        globals_dict = payload.get("globals", {})
        
        context.status = ExecutionStatus.RUNNING
        context.progress = 20.0
        
        try:
            # 合并全局变量
            self.globals.update(globals_dict)
            self.globals["context"] = context
            
            # 执行脚本
            exec_globals = {}
            exec(script, self.globals, exec_globals)
            
            context.progress = 80.0
            
            # 获取结果
            result = exec_globals.get("result", {"message": "Script executed"})
            context.result = result
            context.status = ExecutionStatus.SUCCESS
            
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = f"Script error: {str(e)}"
            context.stderr = str(e)
        
        finally:
            context.end_time = datetime.now()
            context.progress = 100.0
        
        return context


class AgentExecutor(BaseExecutor):
    """Agent协作执行器 - 通过Agent网络执行任务"""
    
    def __init__(self):
        self.name = "agent"
        self.scheduler_url = "http://localhost:8095"
    
    async def execute(self, context: ExecutionContext) -> ExecutionContext:
        payload = context.payload
        agent_id = payload.get("agent_id")
        task_type = payload.get("task_type", "execute")
        task_payload = payload.get("task_payload", {})
        
        context.status = ExecutionStatus.RUNNING
        context.progress = 20.0
        context.agent_id = agent_id
        
        try:
            # 调用调度器API创建任务
            scheduler_url = payload.get("scheduler_url", "http://localhost:8095")
            
            task_data = {
                "task_id": context.task_id,
                "name": f"Agent Task {context.task_id}",
                "task_type": task_type,
                "payload": task_payload,
                "required_capabilities": payload.get("capabilities", []),
                "priority": payload.get("priority", 5),
                "timeout": payload.get("timeout", 300)
            }
            
            response = requests.post(
                f"{scheduler_url}/api/tasks",
                json=task_data,
                timeout=10
            )
            
            context.progress = 50.0
            
            if response.status_code in (200, 201):
                task_result = response.json()
                context.result = task_result
                context.status = ExecutionStatus.SUCCESS
            else:
                context.status = ExecutionStatus.FAILED
                context.error = f"Scheduler error: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            context.status = ExecutionStatus.FAILED
            context.error = "Cannot connect to scheduler"
        except Exception as e:
            context.status = ExecutionStatus.FAILED
            context.error = str(e)
        
        finally:
            context.end_time = datetime.now()
            context.progress = 100.0
        
        return context


# ============== 任务执行器管理器 ==============

class TaskExecutorManager:
    """任务执行器管理器"""
    
    def __init__(self):
        self.executors: Dict[ExecutorType, BaseExecutor] = {
            ExecutorType.SHELL: ShellExecutor(),
            ExecutorType.HTTP: HttpExecutor(),
            ExecutorType.SCRIPT: ScriptExecutor(),
            ExecutorType.AGENT: AgentExecutor(),
        }
        self.executions: Dict[str, ExecutionContext] = {}
        self.task_definitions: Dict[str, TaskDefinition] = {}
        self.lock = threading.RLock()
        self.callbacks: List[Callable] = []
    
    def register_callback(self, callback: Callable):
        """注册回调函数"""
        self.callbacks.append(callback)
    
    async def execute_task(self, task: TaskDefinition) -> ExecutionContext:
        """执行任务"""
        with self.lock:
            execution_id = str(uuid.uuid4())
            context = ExecutionContext(
                execution_id=execution_id,
                task_id=task.task_id,
                executor_type=task.executor_type,
                payload=task.payload
            )
            self.executions[execution_id] = context
        
        # 获取执行器
        executor = self.executors.get(task.executor_type)
        if not executor:
            context.status = ExecutionStatus.FAILED
            context.error = f"Unknown executor type: {task.executor_type}"
            return context
        
        # 执行任务
        context = await executor.execute(context)
        
        # 执行回调
        for callback in self.callbacks:
            try:
                callback(context, task)
            except Exception as e:
                print(f"Callback error: {e}")
        
        # 处理重试
        if context.status == ExecutionStatus.FAILED and task.retry_count < task.max_retries:
            task.retry_count += 1
            context = await self.execute_task(task)
        
        # 回调URL
        if task.callback_url and context.status in (ExecutionStatus.SUCCESS, ExecutionStatus.FAILED):
            self._send_callback(task.callback_url, context, task)
        
        return context
    
    def _send_callback(self, url: str, context: ExecutionContext, task: TaskDefinition):
        """发送回调"""
        try:
            payload = {
                "execution_id": context.execution_id,
                "task_id": task.task_id,
                "status": context.status.value,
                "result": context.result,
                "error": context.error,
                "duration": (context.end_time - context.start_time).total_seconds() if context.end_time else None
            }
            requests.post(url, json=payload, timeout=10)
        except Exception as e:
            print(f"Callback error: {e}")
    
    def get_execution(self, execution_id: str) -> Optional[ExecutionContext]:
        """获取执行状态"""
        return self.executions.get(execution_id)
    
    def cancel_execution(self, execution_id: str) -> bool:
        """取消执行"""
        if execution_id in self.executions:
            context = self.executions[execution_id]
            if context.status == ExecutionStatus.RUNNING:
                context.status = ExecutionStatus.CANCELLED
                return True
        return False
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.executions)
        by_status = {}
        for ctx in self.executions.values():
            status = ctx.status.value
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_executions": total,
            "by_status": by_status,
            "active_count": by_status.get("running", 0),
            "success_rate": by_status.get("success", 0) / total if total > 0 else 0
        }


# 全局执行器管理器
manager = TaskExecutorManager()


# ============== REST API ==============

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy", "service": "agent-task-executor"})


@app.route("/api/execute", methods=["POST"])
def execute_task():
    """执行任务"""
    data = request.json
    
    task = TaskDefinition(
        task_id=data.get("task_id", str(uuid.uuid4())),
        name=data.get("name", "Unnamed Task"),
        description=data.get("description", ""),
        executor_type=ExecutorType(data.get("executor_type", "shell")),
        payload=data.get("payload", {}),
        timeout=data.get("timeout", 300),
        max_retries=data.get("max_retries", 3),
        callback_url=data.get("callback_url"),
        tags=data.get("tags", [])
    )
    
    # 异步执行
    async def run():
        return await manager.execute_task(task)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(run())
    loop.close()
    
    return jsonify({
        "execution_id": result.execution_id,
        "task_id": task.task_id,
        "status": result.status.value,
        "result": result.result,
        "error": result.error,
        "duration": (result.end_time - result.start_time).total_seconds() if result.end_time else None
    })


@app.route("/api/executions/<execution_id>", methods=["GET"])
def get_execution(execution_id):
    """获取执行状态"""
    context = manager.get_execution(execution_id)
    if not context:
        return jsonify({"error": "Execution not found"}), 404
    
    return jsonify({
        "execution_id": context.execution_id,
        "task_id": context.task_id,
        "status": context.status.value,
        "progress": context.progress,
        "result": context.result,
        "error": context.error,
        "stdout": context.stdout[:5000],
        "stderr": context.stderr[:5000],
        "start_time": context.start_time.isoformat(),
        "end_time": context.end_time.isoformat() if context.end_time else None
    })


@app.route("/api/executions/<execution_id>/cancel", methods=["POST"])
def cancel_execution(execution_id):
    """取消执行"""
    success = manager.cancel_execution(execution_id)
    return jsonify({"success": success})


@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取统计信息"""
    return jsonify(manager.get_stats())


@app.route("/api/tasks", methods=["POST"])
def define_task():
    """定义任务模板"""
    data = request.json
    
    task = TaskDefinition(
        task_id=data["task_id"],
        name=data["name"],
        description=data.get("description", ""),
        executor_type=ExecutorType(data["executor_type"]),
        payload=data.get("payload", {}),
        timeout=data.get("timeout", 300),
        max_retries=data.get("max_retries", 3),
        callback_url=data.get("callback_url"),
        on_success=data.get("on_success"),
        on_failure=data.get("on_failure"),
        tags=data.get("tags", [])
    )
    
    manager.task_definitions[task.task_id] = task
    return jsonify({"task_id": task.task_id, "status": "created"})


@app.route("/api/tasks/<task_id>/run", methods=["POST"])
def run_defined_task(task_id):
    """运行预定义任务"""
    task = manager.task_definitions.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    
    # 允许覆盖payload
    if request.json:
        task.payload.update(request.json.get("payload", {}))
    
    async def run():
        return await manager.execute_task(task)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(run())
    loop.close()
    
    return jsonify({
        "execution_id": result.execution_id,
        "status": result.status.value
    })


# ============== 主程序 ==============

def main():
    port = 8096
    print(f"🤖 Agent任务执行器启动 - 端口 {port}")
    print(f"   Executor types: {[e.name for e in ExecutorType]}")
    app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()