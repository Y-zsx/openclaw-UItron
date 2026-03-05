#!/usr/bin/env python3
"""
协作网络API网关客户端库
提供Python API方便集成
"""

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GatewayClient:
    """API网关Python客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8089", 
                 timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        
    def _request(self, method: str, path: str, data: Dict = None) -> Dict:
        """发送请求"""
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                resp = self.session.get(url, params=data, timeout=self.timeout)
            elif method == "POST":
                resp = self.session.post(url, json=data, timeout=self.timeout)
            elif method == "PUT":
                resp = self.session.put(url, json=data, timeout=self.timeout)
            elif method == "DELETE":
                resp = self.session.delete(url, timeout=self.timeout)
            else:
                raise ValueError(f"未知方法: {method}")
            
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接失败: {e}")
            return {"success": False, "error": "无法连接到网关"}
        except requests.exceptions.RequestException as e:
            logger.error(f"请求错误: {e}")
            return {"success": False, "error": str(e)}
    
    # ========== 核心操作 ==========
    
    def health(self) -> Dict:
        """健康检查"""
        return self._request("GET", "/health")
    
    def metrics(self) -> Dict:
        """获取指标"""
        return self._request("GET", "/metrics")
    
    # ========== Agent操作 ==========
    
    def register_agent(self, agent_id: str, 
                       capabilities: List[str] = None,
                       metadata: Dict = None) -> Dict:
        """注册Agent"""
        return self._request("POST", "/agents", {
            "agent_id": agent_id,
            "capabilities": capabilities or [],
            "metadata": metadata or {}
        })
    
    def unregister_agent(self, agent_id: str) -> Dict:
        """注销Agent"""
        return self._request("DELETE", f"/agents/{agent_id}")
    
    def heartbeat(self, agent_id: str, 
                  status: str = None,
                  health_score: float = None) -> Dict:
        """发送心跳"""
        data = {}
        if status:
            data["status"] = status
        if health_score is not None:
            data["health_score"] = health_score
        return self._request("POST", f"/agents/{agent_id}/heartbeat", data)
    
    def update_agent_status(self, agent_id: str, status: str) -> Dict:
        """更新Agent状态"""
        return self._request("PUT", f"/agents/{agent_id}/status", 
                            {"status": status})
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent详情"""
        result = self._request("GET", f"/agents/{agent_id}")
        return result.get("agent")
    
    def list_agents(self, status: str = None, 
                    capability: str = None) -> List[Dict]:
        """列出Agent"""
        params = {}
        if status:
            params["status"] = status
        if capability:
            params["capability"] = capability
        result = self._request("GET", "/agents", params)
        return result.get("agents", [])
    
    # ========== 任务操作 ==========
    
    def submit_task(self, task_type: str, 
                   payload: Dict = None,
                   priority: int = 5,
                   target_agent: str = None) -> Dict:
        """提交任务"""
        data = {
            "task_type": task_type,
            "payload": payload or {},
            "priority": priority
        }
        if target_agent:
            data["target_agent"] = target_agent
        return self._request("POST", "/tasks", data)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务详情"""
        result = self._request("GET", f"/tasks/{task_id}")
        return result.get("task")
    
    def update_task_status(self, task_id: str, status: str,
                          result: Any = None, 
                          error: str = None) -> Dict:
        """更新任务状态"""
        data = {"status": status}
        if result is not None:
            data["result"] = result
        if error:
            data["error"] = error
        return self._request("PUT", f"/tasks/{task_id}/status", data)
    
    def complete_task(self, task_id: str, result: Any = None) -> Dict:
        """完成任务"""
        return self.update_task_status(task_id, "completed", result=result)
    
    def fail_task(self, task_id: str, error: str) -> Dict:
        """任务失败"""
        return self.update_task_status(task_id, "failed", error=error)
    
    def cancel_task(self, task_id: str) -> Dict:
        """取消任务"""
        return self._request("POST", f"/tasks/{task_id}/cancel")
    
    def list_tasks(self, status: str = None,
                   agent_id: str = None,
                   limit: int = 50) -> List[Dict]:
        """列出任务"""
        params = {"limit": limit}
        if status:
            params["status"] = status
        if agent_id:
            params["agent_id"] = agent_id
        result = self._request("GET", "/tasks", params)
        return result.get("tasks", [])
    
    def get_pending_tasks(self) -> List[Dict]:
        """获取待处理任务"""
        result = self._request("GET", "/tasks/pending")
        return result.get("tasks", [])
    
    # ========== 消息操作 ==========
    
    def send_message(self, from_agent: str, to_agent: str,
                    content: Any, 
                    message_type: str = "text") -> Dict:
        """发送消息"""
        return self._request("POST", "/messages", {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "type": message_type
        })
    
    def get_messages(self, agent_id: str, 
                    unread_only: bool = False) -> List[Dict]:
        """获取消息"""
        result = self._request("GET", f"/messages/{agent_id}", 
                              {"unread_only": str(unread_only).lower()})
        return result.get("messages", [])
    
    def mark_read(self, agent_id: str, message_id: str) -> Dict:
        """标记已读"""
        return self._request("POST", f"/messages/{agent_id}/{message_id}/read")


class LocalGatewayClient:
    """本地网关客户端 (直接调用，无需HTTP)"""
    
    def __init__(self, gateway_instance=None):
        # 延迟导入避免循环依赖
        from collab_api_gateway import gateway as _gateway
        self.gateway = gateway_instance or _gateway
    
    def health(self) -> Dict:
        return self.gateway.health_check()
    
    def metrics(self) -> Dict:
        return self.gateway.get_metrics()
    
    def register_agent(self, agent_id: str, 
                       capabilities: List[str] = None,
                       metadata: Dict = None) -> Dict:
        return self.gateway.register_agent(agent_id, capabilities, metadata)
    
    def unregister_agent(self, agent_id: str) -> Dict:
        return self.gateway.unregister_agent(agent_id)
    
    def heartbeat(self, agent_id: str, status: str = None,
                  health_score: float = None) -> Dict:
        return self.gateway.heartbeat(agent_id, status, health_score)
    
    def update_agent_status(self, agent_id: str, status: str) -> Dict:
        return self.gateway.update_agent_status(agent_id, status)
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        return self.gateway.get_agent(agent_id)
    
    def list_agents(self, status: str = None,
                    capability: str = None) -> List[Dict]:
        return self.gateway.list_agents(status, capability)
    
    def submit_task(self, task_type: str, payload: Dict = None,
                   priority: int = 5, target_agent: str = None) -> Dict:
        return self.gateway.submit_task(task_type, payload, priority, target_agent)
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        return self.gateway.get_task(task_id)
    
    def update_task_status(self, task_id: str, status: str,
                          result: Any = None, error: str = None) -> Dict:
        return self.gateway.update_task_status(task_id, status, result, error)
    
    def complete_task(self, task_id: str, result: Any = None) -> Dict:
        """完成任务"""
        return self.gateway.update_task_status(task_id, "completed", result=result)
    
    def fail_task(self, task_id: str, error: str) -> Dict:
        """任务失败"""
        return self.gateway.update_task_status(task_id, "failed", error=error)
    
    def cancel_task(self, task_id: str) -> Dict:
        return self.gateway.cancel_task(task_id)
    
    def list_tasks(self, status: str = None, agent_id: str = None,
                   limit: int = 50) -> List[Dict]:
        return self.gateway.list_tasks(status, agent_id, limit)
    
    def get_pending_tasks(self) -> List[Dict]:
        return self.gateway.get_pending_tasks()
    
    def send_message(self, from_agent: str, to_agent: str,
                    content: Any, message_type: str = "text") -> Dict:
        return self.gateway.send_message(from_agent, to_agent, content, message_type)
    
    def get_messages(self, agent_id: str, unread_only: bool = False) -> List[Dict]:
        return self.gateway.get_messages(agent_id, unread_only)
    
    def mark_read(self, agent_id: str, message_id: str) -> Dict:
        return self.gateway.mark_message_read(agent_id, message_id)


# 便捷函数
def create_client(url: str = "http://localhost:8089") -> GatewayClient:
    """创建网关客户端"""
    return GatewayClient(url)


def create_local_client() -> LocalGatewayClient:
    """创建本地客户端"""
    return LocalGatewayClient()


if __name__ == "__main__":
    # 测试
    client = GatewayClient()
    print("健康检查:", client.health())
    print("指标:", client.metrics())