"""
行动执行器模块
Action Executor - 决策的执行层
"""
import asyncio
import logging
import subprocess
from typing import Dict, Any, Callable, Optional, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import json

logger = logging.getLogger(__name__)


class ExecutionStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"


class ActionType(Enum):
    SHELL = "shell"           # Shell命令
    HTTP = "http"            # HTTP请求
    SCRIPT = "script"        # Python脚本
    NOTIFY = "notify"        # 通知
    WEBHOOK = "webhook"      # Webhook
    FUNCTION = "function"    # Python函数


@dataclass
class ExecutionResult:
    """执行结果"""
    action_id: str
    status: ExecutionStatus
    output: Any = None
    error: str = None
    duration_ms: int = 0
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "status": self.status.value,
            "output": self.output,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


@dataclass
class Action:
    """行动定义"""
    name: str
    action_type: ActionType
    config: Dict = field(default_factory=dict)
    retry: int = 0
    timeout: int = 30  # 秒
    enabled: bool = True
    
    # 执行历史
    execution_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    last_executed: datetime = None
    
    def success_rate(self) -> float:
        if self.execution_count == 0:
            return 0.0
        return self.success_count / self.execution_count


class ActionExecutor:
    """
    行动执行器
    负责执行决策产生的具体行动
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.actions: Dict[str, Action] = {}
        self.execution_history: List[ExecutionResult] = []
        self.max_history = self.config.get("max_history", 1000)
        
        # 外部函数调用
        self.function_registry: Dict[str, Callable] = {}
        
        # HTTP客户端配置
        self.http_timeout = self.config.get("http_timeout", 30)
        
        # 加载内置行动
        self._load_builtin_actions()
        
        logger.info("行动执行器初始化完成")
        
    def _load_builtin_actions(self):
        """加载内置行动"""
        # 空操作
        self.register_action(Action(
            name="noop",
            action_type=ActionType.FUNCTION,
            config={"func": lambda ctx: {"status": "ok"}}
        ))
        
    def register_action(self, action: Action):
        """注册行动"""
        self.actions[action.name] = action
        logger.info(f"注册行动: {action.name}")
        
    def register_function(self, name: str, func: Callable):
        """注册可调用的函数"""
        self.function_registry[name] = func
        logger.info(f"注册函数: {name}")
        
    async def execute_async(self, action_name: str, context: Any) -> ExecutionResult:
        """异步执行行动"""
        action = self.actions.get(action_name)
        if not action:
            return ExecutionResult(
                action_id=action_name,
                status=ExecutionStatus.FAILED,
                error=f"未知行动: {action_name}"
            )
            
        if not action.enabled:
            return ExecutionResult(
                action_id=action_name,
                status=ExecutionStatus.FAILED,
                error=f"行动已禁用: {action_name}"
            )
            
        start_time = datetime.now()
        
        try:
            # 根据类型执行
            if action.action_type == ActionType.SHELL:
                result = await self._execute_shell(action, context)
            elif action.action_type == ActionType.HTTP:
                result = await self._execute_http(action, context)
            elif action.action_type == ActionType.SCRIPT:
                result = await self._execute_script(action, context)
            elif action.action_type == ActionType.FUNCTION:
                result = await self._execute_function(action, context)
            elif action.action_type == ActionType.NOTIFY:
                result = await self._execute_notify(action, context)
            elif action.action_type == ActionType.WEBHOOK:
                result = await self._execute_webhook(action, context)
            else:
                result = ExecutionResult(
                    action_id=action_name,
                    status=ExecutionStatus.FAILED,
                    error=f"不支持的行动类型: {action.action_type}"
                )
                
        except Exception as e:
            logger.error(f"行动执行异常 {action_name}: {e}")
            result = ExecutionResult(
                action_id=action_name,
                status=ExecutionStatus.FAILED,
                error=str(e)
            )
            
        # 计算执行时间
        duration = (datetime.now() - start_time).total_seconds() * 1000
        result.duration_ms = int(duration)
        
        # 更新统计
        action.execution_count += 1
        if result.status == ExecutionStatus.SUCCESS:
            action.success_count += 1
        else:
            action.failure_count += 1
        action.last_executed = datetime.now()
        
        # 记录历史
        self.execution_history.append(result)
        if len(self.execution_history) > self.max_history:
            self.execution_history = self.execution_history[-self.max_history:]
            
        return result
    
    def execute(self, action_name: str, context: Any) -> ExecutionResult:
        """同步执行行动"""
        return asyncio.run(self.execute_async(action_name, context))
    
    async def _execute_shell(self, action: Action, context: Any) -> ExecutionResult:
        """执行Shell命令"""
        cmd = action.config.get("command", "")
        
        # 替换变量
        if isinstance(context, dict):
            for key, value in context.items():
                cmd = cmd.replace(f"{{{key}}}", str(value))
        
        try:
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), 
                    timeout=action.timeout
                )
                
                if proc.returncode == 0:
                    return ExecutionResult(
                        action_id=action.name,
                        status=ExecutionStatus.SUCCESS,
                        output=stdout.decode()
                    )
                else:
                    return ExecutionResult(
                        action_id=action.name,
                        status=ExecutionStatus.FAILED,
                        error=stderr.decode() or "Command failed",
                        output=stdout.decode()
                    )
            except asyncio.TimeoutError:
                proc.kill()
                return ExecutionResult(
                    action_id=action.name,
                    status=ExecutionStatus.TIMEOUT,
                    error=f"命令超时 ({action.timeout}s)"
                )
                
        except Exception as e:
            return ExecutionResult(
                action_id=action.name,
                status=ExecutionStatus.FAILED,
                error=str(e)
            )
    
    async def _execute_http(self, action: Action, context: Any) -> ExecutionResult:
        """执行HTTP请求"""
        import aiohttp
        
        url = action.config.get("url", "")
        method = action.config.get("method", "GET").upper()
        headers = action.config.get("headers", {})
        body = action.config.get("body", {})
        
        # 替换变量
        if isinstance(context, dict):
            for key, value in context.items():
                url = url.replace(f"{{{key}}}", str(value))
                if isinstance(body, dict):
                    for k, v in body.items():
                        if isinstance(v, str):
                            body[k] = v.replace(f"{{{key}}}", str(value))
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    method, url, 
                    json=body if body else None,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=action.timeout)
                ) as response:
                    content = await response.text()
                    
                    if response.status < 400:
                        return ExecutionResult(
                            action_id=action.name,
                            status=ExecutionStatus.SUCCESS,
                            output=content,
                            metadata={"status_code": response.status}
                        )
                    else:
                        return ExecutionResult(
                            action_id=action.name,
                            status=ExecutionStatus.FAILED,
                            error=content,
                            metadata={"status_code": response.status}
                        )
        except Exception as e:
            return ExecutionResult(
                action_id=action.name,
                status=ExecutionStatus.FAILED,
                error=str(e)
            )
    
    async def _execute_script(self, action: Action, context: Any) -> ExecutionResult:
        """执行Python脚本"""
        script = action.config.get("script", "")
        
        try:
            # 创建脚本执行上下文
            exec_globals = {
                "context": context,
                "result": None,
                "__builtins__": __builtins__
            }
            
            # 执行脚本
            exec(script, exec_globals)
            
            return ExecutionResult(
                action_id=action.name,
                status=ExecutionStatus.SUCCESS,
                output=exec_globals.get("result")
            )
        except Exception as e:
            return ExecutionResult(
                action_id=action.name,
                status=ExecutionStatus.FAILED,
                error=str(e)
            )
    
    async def _execute_function(self, action: Action, context: Any) -> ExecutionResult:
        """执行Python函数"""
        func_name = action.config.get("func_name")
        func = action.config.get("func")
        
        if func:
            try:
                result = func(context)
                return ExecutionResult(
                    action_id=action.name,
                    status=ExecutionStatus.SUCCESS,
                    output=result
                )
            except Exception as e:
                return ExecutionResult(
                    action_id=action.name,
                    status=ExecutionStatus.FAILED,
                    error=str(e)
                )
        elif func_name and func_name in self.function_registry:
            try:
                result = self.function_registry[func_name](context)
                return ExecutionResult(
                    action_id=action.name,
                    status=ExecutionStatus.SUCCESS,
                    output=result
                )
            except Exception as e:
                return ExecutionResult(
                    action_id=action.name,
                    status=ExecutionStatus.FAILED,
                    error=str(e)
                )
        else:
            return ExecutionResult(
                action_id=action.name,
                status=ExecutionStatus.FAILED,
                error=f"函数未找到: {func_name}"
            )
    
    async def _execute_notify(self, action: Action, context: Any) -> ExecutionResult:
        """执行通知"""
        # 这里可以集成钉钉、邮件等通知渠道
        logger.info(f"通知: {action.name} - {context}")
        return ExecutionResult(
            action_id=action.name,
            status=ExecutionStatus.SUCCESS,
            output={"notified": True}
        )
    
    async def _execute_webhook(self, action: Action, context: Any) -> ExecutionResult:
        """执行Webhook - 实际上也是HTTP请求"""
        return await self._execute_http(action, context)
    
    def get_actions(self) -> List[Dict]:
        """获取所有行动"""
        return [
            {
                "name": a.name,
                "type": a.action_type.value,
                "enabled": a.enabled,
                "execution_count": a.execution_count,
                "success_rate": a.success_rate(),
                "last_executed": a.last_executed.isoformat() if a.last_executed else None
            }
            for a in self.actions.values()
        ]
    
    def get_history(self, limit: int = 100) -> List[Dict]:
        """获取执行历史"""
        return [r.to_dict() for r in self.execution_history[-limit:]]
    
    def get_stats(self) -> Dict:
        """获取执行统计"""
        total = len(self.execution_history)
        success = len([r for r in self.execution_history if r.status == ExecutionStatus.SUCCESS])
        failed = len([r for r in self.execution_history if r.status == ExecutionStatus.FAILED])
        
        return {
            "total": total,
            "success": success,
            "failed": failed,
            "success_rate": success / total if total > 0 else 0,
            "actions_count": len(self.actions)
        }