#!/usr/bin/env python3
"""
转世任务执行器 - 集成告警和自动重试
专门为reincarnate-v2.py设计的任务执行模块
"""

import json
import time
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable

UTC = timezone.utc

# 任务告警重试API
RETRY_API_URL = "http://127.0.0.1:18197"

# 重试配置
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAYS = [30, 60, 120]  # 指数退避: 30s, 1min, 2min


class ReincarnateTaskExecutor:
    """转世任务执行器 - 带告警和重试"""
    
    def __init__(
        self,
        workspace: str = "/root/.openclaw/workspace",
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delays: list = None,
        alert_api_url: str = RETRY_API_URL
    ):
        self.workspace = workspace
        self.max_retries = max_retries
        self.retry_delays = retry_delays or DEFAULT_RETRY_DELAYS
        self.alert_api_url = alert_api_url
        
        # 检查API是否可用
        self.api_available = self._check_api()
    
    def _check_api(self) -> bool:
        """检查告警重试API是否可用"""
        try:
            resp = requests.get(f"{self.alert_api_url}/api/integrated/status", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def _send_failure_to_api(
        self,
        task_id: str,
        agent_id: str,
        error: str,
        retry_count: int,
        task_data: dict = None
    ) -> Dict:
        """发送失败到API (自动重试+告警)"""
        if not self.api_available:
            return {"api_available": False}
        
        try:
            resp = requests.post(
                f"{self.alert_api_url}/api/task/fail",
                json={
                    "task_id": task_id,
                    "agent_id": agent_id,
                    "error": error,
                    "retry_count": retry_count,
                    "task_data": task_data or {},
                    "max_retries": self.max_retries
                },
                timeout=10
            )
            return resp.json()
        except Exception as e:
            return {"api_available": False, "error": str(e)}
    
    def _send_success_to_api(
        self,
        task_id: str,
        agent_id: str = "reincarnate"
    ) -> Dict:
        """发送成功到API (清除告警)"""
        if not self.api_available:
            return {"api_available": False}
        
        try:
            resp = requests.post(
                f"{self.alert_api_url}/api/task/success",
                json={
                    "task_id": task_id,
                    "agent_id": agent_id
                },
                timeout=10
            )
            return resp.json()
        except Exception as e:
            return {"api_available": False, "error": str(e)}
    
    def execute_with_retry(
        self,
        task_id: str,
        task_func: Callable,
        task_args: tuple = (),
        task_kwargs: dict = None,
        agent_id: str = "reincarnate"
    ) -> Dict[str, Any]:
        """
        执行任务 - 带自动重试和告警
        
        Args:
            task_id: 任务ID (如 "reincarnate_life_150")
            task_func: 任务执行函数
            task_args: 函数位置参数
            task_kwargs: 函数关键字参数
            agent_id: Agent ID
            
        Returns:
            执行结果字典
        """
        task_kwargs = task_kwargs or {}
        task_data = {
            "task_name": task_id,
            "workspace": self.workspace,
            "start_time": datetime.now(UTC).isoformat()
        }
        
        result = {
            "task_id": task_id,
            "status": "pending",
            "attempts": [],
            "final_result": None,
            "api_used": self.api_available
        }
        
        for attempt in range(self.max_retries + 1):
            attempt_result = {
                "attempt": attempt + 1,
                "start_time": datetime.now(UTC).isoformat(),
                "status": "running"
            }
            
            try:
                # 执行任务
                print(f"[TaskExecutor] Attempt {attempt + 1}/{self.max_retries + 1} for {task_id}")
                
                if callable(task_func):
                    output = task_func(*task_args, **task_kwargs)
                    attempt_result["output"] = str(output)[:500]
                    attempt_result["status"] = "success"
                
                result["attempts"].append(attempt_result)
                result["status"] = "success"
                result["final_result"] = attempt_result
                
                # 成功后通知API清除告警
                if self.api_available:
                    self._send_success_to_api(task_id, agent_id)
                
                break
                
            except Exception as e:
                error_msg = str(e)
                attempt_result["status"] = "failed"
                attempt_result["error"] = error_msg
                result["attempts"].append(attempt_result)
                
                print(f"[TaskExecutor] Attempt {attempt + 1} failed: {error_msg}")
                
                # 不是最后一次，尝试重试
                if attempt < self.max_retries:
                    # 发送失败到API (触发重试+告警)
                    if self.api_available:
                        api_result = self._send_failure_to_api(
                            task_id=task_id,
                            agent_id=agent_id,
                            error=error_msg,
                            retry_count=attempt,
                            task_data=task_data
                        )
                        attempt_result["api_notified"] = True
                        attempt_result["api_result"] = api_result
                    
                    # 等待后重试
                    delay = self.retry_delays[attempt] if attempt < len(self.retry_delays) else 60
                    print(f"[TaskExecutor] Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    # 最后一次失败
                    result["status"] = "failed"
                    result["final_result"] = attempt_result
                    
                    # 发送最终失败告警
                    if self.api_available:
                        self._send_failure_to_api(
                            task_id=task_id,
                            agent_id=agent_id,
                            error=error_msg,
                            retry_count=attempt,
                            task_data=task_data
                        )
        
        return result
    
    def execute_simple(
        self,
        task_id: str,
        task_func: Callable,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """简单执行 - 不使用专用API"""
        result = {
            "task_id": task_id,
            "status": "pending",
            "start_time": datetime.now(UTC).isoformat()
        }
        
        try:
            output = task_func(*args, **kwargs)
            result["status"] = "success"
            result["output"] = str(output)[:500]
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        result["end_time"] = datetime.now(UTC).isoformat()
        return result


# 全局实例
_executor = None


def get_executor() -> ReincarnateTaskExecutor:
    """获取全局执行器实例"""
    global _executor
    if _executor is None:
        _executor = ReincarnateTaskExecutor()
    return _executor


def execute_with_retry(task_id: str, task_func: Callable, *args, **kwargs) -> Dict:
    """快捷执行函数"""
    return get_executor().execute_with_retry(task_id, task_func, task_args=args, task_kwargs=kwargs)


if __name__ == "__main__":
    # 测试
    executor = ReincarnateTaskExecutor()
    print(f"API Available: {executor.api_available}")
    
    if executor.api_available:
        status = requests.get(f"{RETRY_API_URL}/api/integrated/status").json()
        print(json.dumps(status, indent=2))