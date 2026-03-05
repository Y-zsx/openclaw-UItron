"""
决策引擎API客户端
"""
import requests
import json
from typing import Dict, Any, Optional

API_BASE = "http://localhost:8080"

class DecisionClient:
    def __init__(self, base_url: str = API_BASE):
        self.base_url = base_url
    
    def decide(self, context: Dict[str, Any], options: list, 
               criteria: Optional[Dict[str, float]] = None, 
               priority: int = 1) -> Dict[str, Any]:
        """发起决策请求"""
        resp = requests.post(f"{self.base_url}/decide", json={
            "context": context,
            "options": options,
            "criteria": criteria,
            "priority": priority
        })
        resp.raise_for_status()
        return resp.json()
    
    def get(self, decision_id: str) -> Dict[str, Any]:
        """获取决策"""
        resp = requests.get(f"{self.base_url}/decision/{decision_id}")
        resp.raise_for_status()
        return resp.json()
    
    def list(self, limit: int = 10) -> list:
        """列出决策"""
        resp = requests.get(f"{self.base_url}/decisions", params={"limit": limit})
        resp.raise_for_status()
        return resp.json()
    
    def evaluate(self, decision_id: str, outcome: str, score: float) -> Dict[str, Any]:
        """评估决策"""
        resp = requests.post(f"{self.base_url}/evaluate", json={
            "decision_id": decision_id,
            "outcome": outcome,
            "score": score
        })
        resp.raise_for_status()
        return resp.json()
    
    def stats(self) -> Dict[str, Any]:
        """统计信息"""
        resp = requests.get(f"{self.base_url}/stats")
        resp.raise_for_status()
        return resp.json()

def demo():
    """演示"""
    client = DecisionClient()
    
    # 示例决策
    result = client.decide(
        context={"budget": 10000, "urgency": "high", "team_size": 5},
        options=["AWS", "GCP", "Azure", "阿里云"],
        criteria={"cost": 0.4, "reliability": 0.3, "latency": 0.3},
        priority=2
    )
    print("决策结果:", json.dumps(result, indent=2, ensure_ascii=False))
    
    # 查看统计
    print("统计:", json.dumps(client.stats(), indent=2))

if __name__ == "__main__":
    demo()