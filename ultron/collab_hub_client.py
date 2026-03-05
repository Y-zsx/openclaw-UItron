#!/usr/bin/env python3
"""
协作中心客户端 - 集成到奥创现有系统
提供统一的API调用接口
"""

import requests
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

COLLAB_HUB_URL = "http://localhost:8105"


class CollabHubClient:
    """协作中心API客户端"""
    
    def __init__(self, base_url: str = COLLAB_HUB_URL):
        self.base_url = base_url
        self.available = self._check_health()
    
    def _check_health(self) -> bool:
        """检查服务健康状态"""
        try:
            r = requests.get(f"{self.base_url}/health", timeout=2)
            return r.status_code == 200
        except:
            return False
    
    def get_status(self) -> Dict[str, Any]:
        """获取协作中心状态"""
        try:
            r = requests.get(f"{self.base_url}/status", timeout=2)
            return r.json()
        except Exception as e:
            return {"error": str(e), "available": False}
    
    def get_agents(self) -> List[Dict[str, Any]]:
        """获取所有Agent信息"""
        try:
            r = requests.get(f"{self.base_url}/agents", timeout=2)
            return r.json()
        except Exception as e:
            return []
    
    def get_tasks(self) -> Dict[str, Any]:
        """获取任务状态"""
        try:
            r = requests.get(f"{self.base_url}/tasks", timeout=2)
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    def submit_task(self, agent_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """提交任务到指定Agent"""
        try:
            r = requests.post(
                f"{self.base_url}/tasks",
                json={"agent_id": agent_id, "task": task},
                timeout=5
            )
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取协作中心指标"""
        try:
            r = requests.get(f"{self.base_url}/metrics", timeout=2)
            return r.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_collaboration_links(self) -> List[Dict[str, Any]]:
        """获取协作链接"""
        try:
            r = requests.get(f"{self.base_url}/collaboration/links", timeout=2)
            return r.json()
        except Exception as e:
            return []


# 全局客户端实例
_client = None

def get_hub_client() -> CollabHubClient:
    """获取全局客户端实例"""
    global _client
    if _client is None:
        _client = CollabHubClient()
    return _client


def is_hub_available() -> bool:
    """检查协作中心是否可用"""
    client = get_hub_client()
    return client.available


def integrate_with_ultron() -> Dict[str, Any]:
    """
    集成协作中心到奥创系统
    返回集成状态
    """
    client = get_hub_client()
    
    if not client.available:
        return {
            "integrated": False,
            "error": "协作中心服务未运行",
            "action": "启动服务: python3 agent_collaboration_hub.py"
        }
    
    status = client.get_status()
    agents = client.get_agents()
    metrics = client.get_metrics()
    
    return {
        "integrated": True,
        "timestamp": datetime.now().isoformat(),
        "status": status,
        "agents_count": len(agents),
        "metrics": metrics,
        "message": "协作中心已集成到奥创系统"
    }


if __name__ == "__main__":
    # 测试集成
    result = integrate_with_ultron()
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))