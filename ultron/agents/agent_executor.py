#!/usr/bin/env python3
"""
Agent执行器 - 多智能体协作网络核心
第34世：Agent执行器设计与实现

负责:
- 任务实际执行 (shell命令、API调用、函数执行)
- 执行结果标准化
- 超时与错误处理
- 执行日志记录
"""

import json
import time
import asyncio
import subprocess
import shlex
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import sys
import os

# 添加agents目录到路径
AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENTS_DIR)

class ExecutionType(Enum):
    """执行类型"""
    SHELL = "shell"           # Shell命令
    PYTHON = "python"         # Python代码
    FUNCTION = "function"     # 预定义函数
    API = "api"              # API调用
    WORKFLOW = "workflow"     # 工作流

class ExecutionStatus(Enum):
    """执行状态"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"

@dataclass
class ExecutionResult:
    """执行结果"""
    task_id: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0
    start_time: str = ""
    end_time: str = ""
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "metadata": self.metadata
        }

@dataclass
class ExecutionTask:
    """执行任务"""
    task_id: str
    execution_type: ExecutionType
    command: str = ""           # shell命令或python代码
    func_name: str = ""         # 函数名
    func_args: List[Any] = field(default_factory=list)  # 函数参数
    api_config: Dict = field(default_factory=dict)      # API配置
    timeout: float = 30.0       # 超时秒数
    env: Dict = field(default_factory=dict)  # 环境变量
    cwd: str = ""               # 工作目录
    retry: int = 0              # 重试次数
    max_retry: int = 2          # 最大重试

# 预定义执行函数注册表
FUNCTION_REGISTRY: Dict[str, Callable] = {}

def register_function(name: str):
    """装饰器: 注册执行函数"""
    def decorator(func: Callable):
        FUNCTION_REGISTRY[name] = func
        return func
    return decorator

# 注册内置函数
@register_function("get_system_status")
def _get_system_status() -> Dict:
    """获取系统状态"""
    import psutil
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_percent": psutil.disk_usage('/').percent,
        "timestamp": datetime.now().isoformat()
    }

@register_function("check_gateway")
def _check_gateway() -> Dict:
    """检查Gateway状态"""
    import requests
    try:
        r = requests.get("http://localhost:18789/health", timeout=2)
        return {"status": "healthy", "code": r.status_code}
    except:
        return {"status": "unhealthy", "error": "connection failed"}

@register_function("list_processes")
def _list_processes() -> List[Dict]:
    """列出运行中的进程"""
    import psutil
    return [
        {"pid": p.pid, "name": p.name(), "cpu": p.cpu_percent()}
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent'])[:10]
    ]

@register_function("get_disk_usage")
def _get_disk_usage() -> Dict:
    """获取磁盘使用情况"""
    import psutil
    d = psutil.disk_usage('/')
    return {
        "total_gb": round(d.total / (1024**3), 2),
        "used_gb": round(d.used / (1024**3), 2),
        "free_gb": round(d.free / (1024**3), 2),
        "percent": d.percent
    }


class AgentExecutor:
    """Agent执行器 - 核心执行引擎"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.execution_history: List[ExecutionResult] = []
        self.active_executions: Dict[str, ExecutionTask] = {}
        self.stats = {
            "total": 0,
            "success": 0,
            "failed": 0,
            "timeout": 0,
            "total_duration_ms": 0
        }
        self._lock = asyncio.Lock()
        
    async def execute(self, task: ExecutionTask) -> ExecutionResult:
        """执行任务 - 主入口"""
        start_time = time.time()
        start_str = datetime.now().isoformat()
        
        result = ExecutionResult(
            task_id=task.task_id,
            status=ExecutionStatus.RUNNING,
            start_time=start_str
        )
        
        self.active_executions[task.task_id] = task
        self.stats["total"] += 1
        
        try:
            # 根据执行类型分发
            if task.execution_type == ExecutionType.SHELL:
                result.output = await self._execute_shell(task)
            elif task.execution_type == ExecutionType.PYTHON:
                result.output = await self._execute_python(task)
            elif task.execution_type == ExecutionType.FUNCTION:
                result.output = await self._execute_function(task)
            elif task.execution_type == ExecutionType.API:
                result.output = await self._execute_api(task)
            elif task.execution_type == ExecutionType.WORKFLOW:
                result.output = await self._execute_workflow(task)
            else:
                raise ValueError(f"Unknown execution type: {task.execution_type}")
            
            result.status = ExecutionStatus.SUCCESS
            self.stats["success"] += 1
            
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Execution timeout after {task.timeout}s"
            self.stats["timeout"] += 1
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = str(e)
            self.stats["failed"] += 1
            
            # 重试逻辑
            if task.retry < task.max_retry:
                task.retry += 1
                return await self.execute(task)
        
        finally:
            end_time = time.time()
            end_str = datetime.now().isoformat()
            result.duration_ms = (end_time - start_time) * 1000
            result.end_time = end_str
            self.stats["total_duration_ms"] += result.duration_ms
            
            if task.task_id in self.active_executions:
                del self.active_executions[task.task_id]
        
        self.execution_history.append(result)
        return result
    
    async def _execute_shell(self, task: ExecutionTask) -> Dict:
        """执行Shell命令"""
        cmd = task.command
        if not cmd:
            raise ValueError("Shell command is empty")
        
        # 安全检查 - 禁止危险命令
        dangerous = ["rm -rf /", "mkfs", "dd if="]
        for d in dangerous:
            if d in cmd.lower():
                raise ValueError(f"Dangerous command blocked: {d}")
        
        cwd = task.cwd or self.workspace
        env = os.environ.copy()
        env.update(task.env)
        
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd,
            env=env
        )
        
        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=task.timeout
            )
        except asyncio.TimeoutError:
            process.kill()
            raise
        
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode('utf-8', errors='replace').strip(),
            "stderr": stderr.decode('utf-8', errors='replace').strip()
        }
    
    async def _execute_python(self, task: ExecutionTask) -> Any:
        """执行Python代码"""
        code = task.command
        if not code:
            raise ValueError("Python code is empty")
        
        # 创建隔离的命名空间
        namespace = {
            "__builtins__": __builtins__,
            "workspace": self.workspace
        }
        
        # 执行代码
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: exec(code, namespace)
        )
        
        return {"executed": True, "result": result}
    
    async def _execute_function(self, task: ExecutionTask) -> Any:
        """执行预定义函数"""
        func_name = task.func_name
        if not func_name:
            raise ValueError("Function name is empty")
            
        if func_name not in FUNCTION_REGISTRY:
            raise ValueError(f"Function not found: {func_name}")
        
        func = FUNCTION_REGISTRY[func_name]
        
        # 在线程池中执行
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            lambda: func(*task.func_args)
        )
        
        return result
    
    async def _execute_api(self, task: ExecutionTask) -> Any:
        """执行API调用"""
        import requests
        
        config = task.api_config
        method = config.get("method", "GET").upper()
        url = config.get("url", "")
        headers = config.get("headers", {})
        data = config.get("data", {})
        params = config.get("params", {})
        
        if not url:
            raise ValueError("API URL is empty")
        
        loop = asyncio.get_event_loop()
        
        async def _request():
            return requests.request(
                method=method,
                url=url,
                headers=headers,
                json=data if method != "GET" else None,
                params=params,
                timeout=task.timeout
            )
        
        response = await loop.run_in_executor(None, _request)
        
        return {
            "status_code": response.status_code,
            "headers": dict(response.headers),
            "body": response.text[:5000]  # 限制返回大小
        }
    
    async def _execute_workflow(self, task: ExecutionTask) -> Any:
        """执行工作流"""
        # TODO: 实现工作流执行
        return {"status": "workflow_execution_pending"}
    
    def get_stats(self) -> Dict:
        """获取执行统计"""
        avg_duration = (
            self.stats["total_duration_ms"] / self.stats["total"]
            if self.stats["total"] > 0 else 0
        )
        
        return {
            "total": self.stats["total"],
            "success": self.stats["success"],
            "failed": self.stats["failed"],
            "timeout": self.stats["timeout"],
            "success_rate": round(
                self.stats["success"] / self.stats["total"] * 100, 2
            ) if self.stats["total"] > 0 else 0,
            "avg_duration_ms": round(avg_duration, 2),
            "active": len(self.active_executions)
        }
    
    def get_history(self, limit: int = 50) -> List[Dict]:
        """获取执行历史"""
        return [r.to_dict() for r in self.execution_history[-limit:]]
    
    def clear_history(self):
        """清空历史"""
        self.execution_history.clear()


# 全局单例
_executor = None

def get_executor() -> AgentExecutor:
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor


# CLI接口
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent执行器")
    parser.add_argument("action", choices=["execute", "stats", "history", "register"], help="操作")
    parser.add_argument("--type", type=str, default="shell", help="执行类型")
    parser.add_argument("--command", type=str, help="命令")
    parser.add_argument("--function", type=str, help="函数名")
    parser.add_argument("--timeout", type=float, default=30, help="超时秒数")
    parser.add_argument("--task-id", type=str, help="任务ID")
    
    args = parser.parse_args()
    
    executor = get_executor()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    if args.action == "execute":
        task = ExecutionTask(
            task_id=args.task_id or f"task_{int(time.time()*1000)}",
            execution_type=ExecutionType(args.type),
            command=args.command or "",
            func_name=args.function or "",
            timeout=args.timeout
        )
        result = loop.run_until_complete(executor.execute(task))
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        
    elif args.action == "stats":
        print(json.dumps(executor.get_stats(), indent=2))
        
    elif args.action == "history":
        print(json.dumps(executor.get_history(), indent=2, ensure_ascii=False))
        
    elif args.action == "register":
        print(f"已注册函数: {list(FUNCTION_REGISTRY.keys())}")
    
    loop.close()