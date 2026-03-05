"""
Task Executor - 核心执行器
支持多种执行模式：函数、脚本、进程、远程Agent
"""

import asyncio
import json
import uuid
import time
import traceback
from typing import Any, Callable, Optional, Dict, List
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import threading

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


class ExecutionMode(Enum):
    """执行模式"""
    FUNCTION = "function"      # Python函数
    SCRIPT = "script"          # Shell脚本
    PROCESS = "process"        # 独立进程
    AGENT = "agent"            # 远程Agent


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
    task_id: str
    execution_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mode: ExecutionMode = ExecutionMode.FUNCTION
    timeout: int = 300  # 超时秒数
    max_retries: int = 3
    retry_delay: int = 5
    sandbox: bool = False
    env: Dict[str, str] = field(default_factory=dict)
    cwd: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if isinstance(self.mode, str):
            self.mode = ExecutionMode(self.mode)


@dataclass
class ExecutionResult:
    """执行结果"""
    execution_id: str
    task_id: str
    status: ExecutionStatus
    output: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "task_id": self.task_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "duration": self.duration,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "retries": self.retries,
            "metadata": self.metadata
        }


class TaskExecutor:
    """任务执行器"""
    
    def __init__(self, max_workers: int = 4, default_timeout: int = 300):
        self.max_workers = max_workers
        self.default_timeout = default_timeout
        self.executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="task-exec-")
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.results: Dict[str, ExecutionResult] = {}
        self._lock = threading.Lock()
        self._function_registry: Dict[str, Callable] = {}
        
    def register_function(self, name: str, func: Callable):
        """注册可执行的函数"""
        self._function_registry[name] = func
        logger.info(f"Registered function: {name}")
        
    def execute(self, task_id: str, target: Any, context: Optional[ExecutionContext] = None) -> ExecutionResult:
        """执行任务（同步）"""
        if context is None:
            context = ExecutionContext(task_id=task_id, mode=ExecutionMode.FUNCTION)
            
        context.task_id = task_id
        started = datetime.now()
        
        result = ExecutionResult(
            execution_id=context.execution_id,
            task_id=task_id,
            status=ExecutionStatus.RUNNING,
            started_at=started
        )
        
        logger.info(f"Executing task {task_id} in mode {context.mode}")
        
        try:
            # 根据模式执行
            if context.mode == ExecutionMode.FUNCTION:
                output = self._execute_function(target, context)
            elif context.mode == ExecutionMode.SCRIPT:
                output, stdout, stderr, code = self._execute_script(target, context)
                result.stdout = stdout
                result.stderr = stderr
                result.exit_code = code
            elif context.mode == ExecutionMode.PROCESS:
                output, stdout, stderr, code = self._execute_process(target, context)
                result.stdout = stdout
                result.stderr = stderr
                result.exit_code = code
            elif context.mode == ExecutionMode.AGENT:
                output = self._execute_agent(target, context)
            else:
                raise ValueError(f"Unknown execution mode: {context.mode}")
                
            result.output = output
            result.status = ExecutionStatus.SUCCESS
            
        except asyncio.TimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Task timeout after {context.timeout}s"
            
        except FuturesTimeoutError:
            result.status = ExecutionStatus.TIMEOUT
            result.error = f"Task timeout after {context.timeout}s"
            
        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error = f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
            
        finally:
            result.finished_at = datetime.now()
            result.duration = (result.finished_at - started).total_seconds()
            
        # 保存结果
        with self._lock:
            self.results[result.execution_id] = result
            
        logger.info(f"Task {task_id} finished with status {result.status.value}, duration: {result.duration:.2f}s")
        return result
    
    async def execute_async(self, task_id: str, target: Any, context: Optional[ExecutionContext] = None) -> ExecutionResult:
        """异步执行任务"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.execute,
            task_id,
            target,
            context
        )
    
    def _execute_function(self, target: Any, context: ExecutionContext) -> Any:
        """执行Python函数"""
        retries = 0
        last_error = None
        
        while retries <= context.max_retries:
            try:
                if callable(target):
                    # 直接调用 callable
                    if context.timeout > 0:
                        future = self.executor.submit(target)
                        return future.result(timeout=context.timeout)
                    else:
                        return target()
                        
                elif isinstance(target, dict) and "func" in target:
                    # 指定函数名和参数
                    func_name = target["func"]
                    args = target.get("args", [])
                    kwargs = target.get("kwargs", {})
                    
                    if func_name in self._function_registry:
                        func = self._function_registry[func_name]
                        if context.timeout > 0:
                            future = self.executor.submit(func, *args, **kwargs)
                            return future.result(timeout=context.timeout)
                        else:
                            return func(*args, **kwargs)
                    else:
                        raise ValueError(f"Function not registered: {func_name}")
                        
                else:
                    raise ValueError(f"Invalid function target: {target}")
                    
            except Exception as e:
                last_error = e
                retries += 1
                if retries <= context.max_retries:
                    logger.warning(f"Task {context.task_id} failed, retry {retries}/{context.max_retries}: {e}")
                    time.sleep(context.retry_delay)
                    
        raise last_error
    
    def _execute_script(self, target: str, context: ExecutionContext) -> tuple:
        """执行Shell脚本"""
        import subprocess
        
        cmd = target if isinstance(target, list) else ["/bin/sh", "-c", target]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=context.timeout,
            cwd=context.cwd,
            env={**os.environ, **context.env} if hasattr(__import__('os'), 'environ') else context.env
        )
        
        return result.stdout, result.stderr, result.returncode
    
    def _execute_process(self, target: str, context: ExecutionContext) -> tuple:
        """执行独立进程"""
        return self._execute_script(target, context)
    
    def _execute_agent(self, target: Dict[str, Any], context: ExecutionContext) -> Any:
        """执行远程Agent任务"""
        # 远程Agent执行逻辑
        agent_id = target.get("agent_id")
        task = target.get("task")
        
        if not agent_id or not task:
            raise ValueError("Agent execution requires agent_id and task")
            
        # TODO: 实现远程Agent调用
        logger.info(f"Would execute agent {agent_id} with task: {task}")
        return {"agent_id": agent_id, "task": task, "status": "submitted"}
    
    def get_result(self, execution_id: str) -> Optional[ExecutionResult]:
        """获取执行结果"""
        return self.results.get(execution_id)
    
    def cancel(self, execution_id: str) -> bool:
        """取消执行"""
        if execution_id in self.running_tasks:
            task = self.running_tasks[execution_id]
            task.cancel()
            if execution_id in self.results:
                self.results[execution_id].status = ExecutionStatus.CANCELLED
            return True
        return False
    
    def shutdown(self, wait: bool = True):
        """关闭执行器"""
        self.executor.shutdown(wait=wait)
        logger.info("TaskExecutor shutdown")


# 全局执行器实例
_default_executor: Optional[TaskExecutor] = None

def get_executor() -> TaskExecutor:
    """获取默认执行器"""
    global _default_executor
    if _default_executor is None:
        _default_executor = TaskExecutor()
    return _default_executor