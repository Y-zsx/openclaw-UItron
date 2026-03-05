#!/usr/bin/env python3
"""
Agent任务执行器集成模块
将决策系统的动作委托给Agent任务执行器执行
"""
import requests
import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Agent任务执行器配置
AGENT_EXECUTOR_URL = "http://localhost:8096"
AGENT_EXECUTOR_API = f"{AGENT_EXECUTOR_URL}/api"


class AgentExecutorIntegration:
    """Agent执行器集成类"""
    
    def __init__(self, executor_url: str = AGENT_EXECUTOR_URL):
        self.executor_url = executor_url
        self.api_base = f"{executor_url}/api"
        self._health_check()
    
    def _health_check(self) -> bool:
        """健康检查"""
        try:
            resp = requests.get(f"{self.executor_url}/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                logger.info(f"✅ Agent执行器连接正常: {data.get('service')}")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Agent执行器健康检查失败: {e}")
        return False
    
    def is_available(self) -> bool:
        """检查执行器是否可用"""
        return self._health_check()
    
    def execute_task(self, task_type: str, payload: Dict[str, Any], 
                     timeout: int = 300) -> Dict[str, Any]:
        """
        通过Agent执行器执行任务
        
        Args:
            task_type: 任务类型 (shell/http/script/function/agent)
            payload: 任务payload
            timeout: 超时时间（秒）
            
        Returns:
            执行结果
        """
        try:
            # 构建执行请求
            execution_request = {
                "task_id": f"dec_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                "executor_type": task_type,
                "payload": payload,
                "timeout": timeout
            }
            
            # 发送执行请求
            resp = requests.post(
                f"{self.api_base}/execute",
                json=execution_request,
                timeout=timeout + 10
            )
            
            if resp.status_code == 200:
                result = resp.json()
                logger.info(f"✅ Agent任务执行成功: {task_type}")
                return {
                    "success": True,
                    "result": result,
                    "executor": "agent_task_executor"
                }
            else:
                logger.error(f"❌ Agent任务执行失败: {resp.status_code}")
                return {
                    "success": False,
                    "error": f"HTTP {resp.status_code}",
                    "executor": "agent_task_executor"
                }
                
        except requests.exceptions.Timeout:
            logger.error(f"⏱️ Agent任务执行超时: {task_type}")
            return {
                "success": False,
                "error": "timeout",
                "executor": "agent_task_executor"
            }
        except Exception as e:
            logger.error(f"❌ Agent任务执行异常: {e}")
            return {
                "success": False,
                "error": str(e),
                "executor": "agent_task_executor"
            }
    
    def execute_shell(self, command: str, timeout: int = 60) -> Dict[str, Any]:
        """执行Shell命令"""
        return self.execute_task("shell", {"command": command}, timeout)
    
    def execute_http(self, method: str, url: str, headers: Optional[Dict] = None,
                     data: Optional[Dict] = None, timeout: int = 30) -> Dict[str, Any]:
        """执行HTTP请求"""
        return self.execute_task("http", {
            "method": method,
            "url": url,
            "headers": headers or {},
            "data": data or {}
        }, timeout)
    
    def execute_script(self, script: str, language: str = "python", 
                       timeout: int = 120) -> Dict[str, Any]:
        """执行脚本"""
        return self.execute_task("script", {
            "script": script,
            "language": language
        }, timeout)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行器统计"""
        try:
            resp = requests.get(f"{self.api_base}/stats", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"获取统计失败: {e}")
        return {"error": str(e)}
    
    def get_execution(self, execution_id: str) -> Dict[str, Any]:
        """获取执行结果"""
        try:
            resp = requests.get(f"{self.api_base}/executions/{execution_id}", timeout=5)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.error(f"获取执行结果失败: {e}")
        return {"error": str(e)}


# 全局集成实例
_agent_integration: Optional[AgentExecutorIntegration] = None


def get_agent_integration() -> AgentExecutorIntegration:
    """获取全局Agent集成实例"""
    global _agent_integration
    if _agent_integration is None:
        _agent_integration = AgentExecutorIntegration()
    return _agent_integration


def register_agent_executor_actions(executor) -> None:
    """
    向决策系统的执行器注册Agent执行动作
    这需要在决策引擎启动时调用
    """
    from executor import Action, ActionType
    
    integration = get_agent_integration()
    
    # 注册shell执行动作
    executor.register_action(Action(
        name="agent_shell",
        action_type=ActionType.FUNCTION,
        description="通过Agent执行器执行Shell命令",
        config={
            "func": lambda ctx: integration.execute_shell(
                ctx.get("command", ""),
                ctx.get("timeout", 60)
            )
        }
    ))
    
    # 注册HTTP执行动作
    executor.register_action(Action(
        name="agent_http",
        action_type=ActionType.FUNCTION,
        description="通过Agent执行器执行HTTP请求",
        config={
            "func": lambda ctx: integration.execute_http(
                ctx.get("method", "GET"),
                ctx.get("url", ""),
                ctx.get("headers"),
                ctx.get("data"),
                ctx.get("timeout", 30)
            )
        }
    ))
    
    # 注册脚本执行动作
    executor.register_action(Action(
        name="agent_script",
        action_type=ActionType.FUNCTION,
        description="通过Agent执行器执行脚本",
        config={
            "func": lambda ctx: integration.execute_script(
                ctx.get("script", ""),
                ctx.get("language", "python"),
                ctx.get("timeout", 120)
            )
        }
    ))
    
    # 注册通用Agent任务执行
    executor.register_action(Action(
        name="agent_task",
        action_type=ActionType.FUNCTION,
        description="通过Agent执行器执行通用任务",
        config={
            "func": lambda ctx: integration.execute_task(
                ctx.get("task_type", "function"),
                ctx.get("payload", {}),
                ctx.get("timeout", 300)
            )
        }
    ))
    
    logger.info("✅ 已注册4个Agent执行器动作: agent_shell, agent_http, agent_script, agent_task")


if __name__ == "__main__":
    # 测试集成
    integration = AgentExecutorIntegration()
    
    print("=== Agent执行器集成测试 ===")
    print(f"执行器可用: {integration.is_available()}")
    
    # 测试Shell执行
    print("\n--- Shell命令测试 ---")
    result = integration.execute_shell("echo 'Hello from Agent Executor!'")
    print(f"结果: {result}")
    
    # 获取统计
    print("\n--- 统计信息 ---")
    stats = integration.get_stats()
    print(f"统计: {stats}")