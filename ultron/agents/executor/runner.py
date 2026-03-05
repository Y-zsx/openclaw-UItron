"""
Task Runner - 任务运行器
提供不同类型的任务运行器：函数、脚本、HTTP
"""

import asyncio
import json
import subprocess
import time
import uuid
from typing import Any, Callable, Dict, Optional
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')


@dataclass
class RunnerResult:
    """运行器结果"""
    success: bool
    output: Any = None
    error: Optional[str] = None
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    duration: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseRunner(ABC):
    """基础运行器"""
    
    @abstractmethod
    def run(self, target: Any, **kwargs) -> RunnerResult:
        """执行任务"""
        pass
    
    def validate(self, target: Any) -> bool:
        """验证目标是否有效"""
        return True


class FunctionRunner(BaseRunner):
    """Python函数运行器"""
    
    def __init__(self, registry: Optional[Dict[str, Callable]] = None):
        self.registry = registry or {}
        
    def register(self, name: str, func: Callable):
        """注册函数"""
        self.registry[name] = func
        
    def run(self, target: Any, timeout: int = 300, **kwargs) -> RunnerResult:
        """执行Python函数"""
        start = time.time()
        
        try:
            if callable(target):
                # 直接执行 callable
                result = target(**kwargs)
                return RunnerResult(success=True, output=result, duration=time.time() - start)
                
            elif isinstance(target, str) and target in self.registry:
                # 按名称执行
                func = self.registry[target]
                result = func(**kwargs)
                return RunnerResult(success=True, output=result, duration=time.time() - start)
                
            elif isinstance(target, dict):
                # 字典格式: {"func": "name", "args": [...], "kwargs": {...}}
                func_name = target.get("func")
                if func_name and func_name in self.registry:
                    func = self.registry[func_name]
                    args = target.get("args", [])
                    kw = target.get("kwargs", {})
                    result = func(*args, **kw)
                    return RunnerResult(success=True, output=result, duration=time.time() - start)
                    
            raise ValueError(f"Invalid function target: {target}")
            
        except Exception as e:
            return RunnerResult(
                success=False,
                error=str(e),
                duration=time.time() - start
            )
    
    def validate(self, target: Any) -> bool:
        if callable(target):
            return True
        if isinstance(target, str):
            return target in self.registry
        if isinstance(target, dict) and "func" in target:
            return target["func"] in self.registry
        return False


class ScriptRunner(BaseRunner):
    """脚本运行器"""
    
    def __init__(self, shell: str = "/bin/bash"):
        self.shell = shell
        
    def run(self, target: str, timeout: int = 300, env: Optional[Dict] = None, cwd: Optional[str] = None, **kwargs) -> RunnerResult:
        """执行Shell脚本"""
        start = time.time()
        
        try:
            result = subprocess.run(
                target,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
                cwd=cwd
            )
            
            return RunnerResult(
                success=result.returncode == 0,
                output=result.stdout,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                duration=time.time() - start
            )
            
        except subprocess.TimeoutExpired:
            return RunnerResult(
                success=False,
                error=f"Script timeout after {timeout}s",
                duration=time.time() - start
            )
            
        except Exception as e:
            return RunnerResult(
                success=False,
                error=str(e),
                duration=time.time() - start
            )
    
    def validate(self, target: Any) -> bool:
        return isinstance(target, (str, list))


class HTTPRunner(BaseRunner):
    """HTTP请求运行器"""
    
    def __init__(self, base_url: str = "", default_headers: Optional[Dict] = None):
        self.base_url = base_url
        self.default_headers = default_headers or {}
        
    async def _async_run(self, target: Dict[str, Any], timeout: int = 30, **kwargs) -> RunnerResult:
        """异步HTTP请求"""
        import aiohttp
        
        start = time.time()
        
        method = target.get("method", "GET").upper()
        url = target.get("url", "")
        if not url.startswith("http"):
            url = self.base_url + url
            
        headers = {**self.default_headers, **target.get("headers", {})}
        data = target.get("data")
        json_data = target.get("json")
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url,
                    headers=headers,
                    data=data,
                    json=json_data,
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    content = await response.text()
                    return RunnerResult(
                        success=response.status < 400,
                        output=content,
                        stdout=content,
                        stderr="",
                        exit_code=response.status,
                        duration=time.time() - start,
                        metadata={
                            "status_code": response.status,
                            "headers": dict(response.headers)
                        }
                    )
                    
        except asyncio.TimeoutError:
            return RunnerResult(
                success=False,
                error=f"Request timeout after {timeout}s",
                duration=time.time() - start
            )
            
        except Exception as e:
            return RunnerResult(
                success=False,
                error=str(e),
                duration=time.time() - start
            )
    
    def run(self, target: Any, timeout: int = 30, **kwargs) -> RunnerResult:
        """执行HTTP请求（同步）"""
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(self._async_run(target, timeout, **kwargs))
        finally:
            loop.close()
    
    def validate(self, target: Any) -> bool:
        if isinstance(target, dict):
            return "url" in target
        return False


class TaskRunner:
    """统一任务运行器 - 路由到具体运行器"""
    
    def __init__(self):
        self.runners = {
            "function": FunctionRunner(),
            "script": ScriptRunner(),
            "http": HTTPRunner(),
            "shell": ScriptRunner()
        }
        
    def register_runner(self, name: str, runner: BaseRunner):
        """注册运行器"""
        self.runners[name] = runner
        
    def register_function(self, name: str, func: Callable):
        """注册函数到函数运行器"""
        self.runners["function"].register(name, func)
        
    def run(self, target: Any, mode: str = "function", timeout: int = 300, **kwargs) -> RunnerResult:
        """执行任务"""
        if mode not in self.runners:
            return RunnerResult(success=False, error=f"Unknown mode: {mode}")
            
        runner = self.runners[mode]
        return runner.run(target, timeout=timeout, **kwargs)
    
    def validate(self, target: Any, mode: str = "function") -> bool:
        """验证目标"""
        if mode not in self.runners:
            return False
        return self.runners[mode].validate(target)


# 全局运行器
_default_runner: Optional[TaskRunner] = None

def get_runner() -> TaskRunner:
    """获取默认运行器"""
    global _default_runner
    if _default_runner is None:
        _default_runner = TaskRunner()
    return _default_runner