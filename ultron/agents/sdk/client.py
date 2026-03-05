"""
Ultron Multi-Agent Collaboration Network SDK
核心客户端实现
"""

import os
import json
import time
import requests
from typing import Optional, List, Dict, Any, Union
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum

from .exceptions import (
    UltronSDKError,
    AgentNotFoundError,
    TaskNotFoundError,
    AuthenticationError,
    APIError
)

class AgentStatus(Enum):
    ACTIVE = "active"
    IDLE = "idle"
    BUSY = "busy"
    OFFLINE = "offline"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Agent:
    """Agent模型"""
    id: str
    name: str
    status: str
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    uptime: int = 0
    tasks_completed: int = 0

@dataclass
class Task:
    """任务模型"""
    id: str
    type: str
    status: str
    created_at: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    assigned_agent: Optional[str] = None

@dataclass
class TaskResult:
    """任务结果模型"""
    task_id: str
    results: List[Dict[str, Any]]
    aggregated: Dict[str, Any] = field(default_factory=dict)
    stats: Dict[str, Any] = field(default_factory=dict)

@dataclass
class Session:
    """协作会话模型"""
    id: str
    status: str
    participants: List[str]
    created_at: str
    strategy: str = "parallel"

@dataclass
class HealthStatus:
    """健康状态模型"""
    status: str
    version: str
    uptime: int
    components: Dict[str, Any] = field(default_factory=dict)

class BaseClient:
    """API客户端基类"""
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: int = 30
    ):
        self.base_url = base_url or os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")
        self.api_key = api_key or os.getenv("ULTRON_API_KEY", "")
        self.timeout = timeout
        self.session = requests.Session()
        
        if self.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {self.api_key}",
                "X-API-Key": self.api_key
            })
        self.session.headers.update({
            "Content-Type": "application/json",
            "User-Agent": f"Ultron-SDK/3.0.0"
        })
    
    def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """发送API请求"""
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                json=data,
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 401:
                raise AuthenticationError("认证失败，请检查API密钥")
            elif response.status_code == 404:
                raise APIError(f"资源不存在: {endpoint}")
            elif response.status_code >= 400:
                raise APIError(f"API错误 {response.status_code}: {response.text}")
            
            if response.status_code == 204:
                return {}
            
            return response.json()
            
        except requests.exceptions.ConnectionError:
            raise UltronSDKError(f"无法连接到服务器: {self.base_url}")
        except requests.exceptions.Timeout:
            raise UltronSDKError(f"请求超时: {endpoint}")
        except json.JSONDecodeError:
            raise UltronSDKError("响应解析失败")
    
    def get(self, endpoint: str, params: Optional[Dict] = None) -> Dict:
        return self._request("GET", endpoint, params=params)
    
    def post(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        return self._request("POST", endpoint, data=data)
    
    def put(self, endpoint: str, data: Optional[Dict] = None) -> Dict:
        return self._request("PUT", endpoint, data=data)
    
    def delete(self, endpoint: str) -> Dict:
        return self._request("DELETE", endpoint)


class AgentClient(BaseClient):
    """Agent管理客户端"""
    
    def list(self, status: Optional[str] = None, capability: Optional[str] = None) -> List[Agent]:
        """获取Agent列表"""
        params = {}
        if status:
            params["status"] = status
        if capability:
            params["capability"] = capability
            
        response = self.get("/agents", params)
        return [Agent(**a) for a in response.get("agents", [])]
    
    def get(self, agent_id: str) -> Agent:
        """获取指定Agent详情"""
        response = self.get(f"/agents/{agent_id}")
        return Agent(**response)
    
    def register(self, name: str, capabilities: List[str], metadata: Optional[Dict] = None) -> Agent:
        """注册新Agent"""
        data = {
            "name": name,
            "capabilities": capabilities
        }
        if metadata:
            data["metadata"] = metadata
            
        response = self.post("/agents", data)
        return Agent(**response)
    
    def update(self, agent_id: str, **kwargs) -> Agent:
        """更新Agent信息"""
        response = self.put(f"/agents/{agent_id}", kwargs)
        return Agent(**response)
    
    def unregister(self, agent_id: str) -> bool:
        """注销Agent"""
        self.delete(f"/agents/{agent_id}")
        return True
    
    def health_check(self) -> HealthStatus:
        """健康检查"""
        response = self.get("/health")
        return HealthStatus(**response)
    
    def metrics(self, period: str = "5m") -> Dict:
        """获取监控指标"""
        return self.get("/metrics", {"period": period})


class TaskClient(BaseClient):
    """任务管理客户端"""
    
    def list(self, status: Optional[str] = None, limit: int = 50) -> List[Task]:
        """获取任务列表"""
        params = {"limit": limit}
        if status:
            params["status"] = status
            
        response = self.get("/tasks", params)
        return [Task(**t) for t in response.get("tasks", [])]
    
    def get(self, task_id: str) -> Task:
        """获取任务详情"""
        response = self.get(f"/tasks/{task_id}")
        return Task(**response)
    
    def create(
        self,
        task_type: str,
        payload: Dict[str, Any],
        priority: int = 5,
        timeout: int = 300
    ) -> Task:
        """创建新任务"""
        data = {
            "type": task_type,
            "payload": payload,
            "priority": priority,
            "timeout": timeout
        }
        response = self.post("/tasks", data)
        return Task(**response)
    
    def cancel(self, task_id: str) -> bool:
        """取消任务"""
        self.delete(f"/tasks/{task_id}")
        return True
    
    def results(self, task_id: str) -> TaskResult:
        """获取任务结果"""
        response = self.get(f"/tasks/{task_id}/results")
        return TaskResult(**response)
    
    def wait_for_completion(self, task_id: str, timeout: int = 300, poll_interval: float = 1.0) -> Task:
        """等待任务完成"""
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            task = self.get(task_id)
            
            if task.status in ["completed", "failed"]:
                return task
            
            time.sleep(poll_interval)
        
        raise UltronSDKError(f"任务等待超时: {task_id}")


class CollaborationClient(BaseClient):
    """协作会话客户端"""
    
    def list_sessions(self, status: Optional[str] = None) -> List[Session]:
        """获取协作会话列表"""
        params = {}
        if status:
            params["status"] = status
            
        response = self.get("/collaboration/sessions", params)
        return [Session(**s) for s in response.get("sessions", [])]
    
    def get_session(self, session_id: str) -> Session:
        """获取会话详情"""
        response = self.get(f"/collaboration/sessions/{session_id}")
        return Session(**response)
    
    def create_session(
        self,
        participants: List[str],
        strategy: str = "parallel",
        checkpoint_enabled: bool = False
    ) -> Session:
        """创建协作会话"""
        data = {
            "participants": participants,
            "strategy": strategy,
            "checkpointEnabled": checkpoint_enabled
        }
        response = self.post("/collaboration/sessions", data)
        return Session(**response)
    
    def end_session(self, session_id: str) -> bool:
        """结束会话"""
        self.delete(f"/collaboration/sessions/{session_id}")
        return True


class MeshClient(BaseClient):
    """服务网格客户端"""
    
    def list_services(self) -> List[Dict]:
        """获取服务列表"""
        response = self.get("/mesh/services")
        return response.get("services", [])
    
    def circuit_breakers(self) -> Dict:
        """获取熔断器状态"""
        return self.get("/mesh/circuit-breaker")


class MobileClient(BaseClient):
    """移动端API客户端"""
    
    def query(self, query: str, variables: Optional[Dict] = None) -> Dict:
        """GraphQL风格查询"""
        data = {"query": query}
        if variables:
            data["variables"] = variables
        return self.post("/query", data)
    
    def batch(self, operations: List[Dict]) -> List[Dict]:
        """批量操作"""
        data = {"operations": operations}
        return self.post("/batch", data).get("results", [])
    
    def get_sync_token(self) -> str:
        """获取离线同步令牌"""
        response = self.post("/sync/token", {})
        return response.get("token", "")
    
    def get_changes(self, since: str) -> List[Dict]:
        """获取增量变更"""
        return self.get("/sync/changes", {"since": since}).get("changes", [])
    
    def register_connection(self, device_id: str, platform: str) -> bool:
        """注册连接/心跳"""
        data = {"deviceId": device_id, "platform": platform}
        self.post("/connection", data)
        return True