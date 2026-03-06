#!/usr/bin/env python3
"""
Agent-Aware Decision System
决策引擎现在能够感知Agent网络状态
"""
import requests
import json
from datetime import datetime

class AgentAwareDecisionEngine:
    def __init__(self, decision_api="http://localhost:18255", agent_gateway="http://localhost:18290"):
        self.decision_api = decision_api
        self.agent_gateway = agent_gateway
        self.integration_status = "initialized"
    
    def get_agent_network_health(self):
        """获取Agent网络健康状态"""
        try:
            agents_resp = requests.get(f"{self.agent_gateway}/api/agents", timeout=3)
            agents = agents_resp.json().get("agents", [])
            
            # 尝试获取更多健康信息
            health_info = {
                "total_agents": len(agents),
                "timestamp": datetime.now().isoformat(),
                "agents": []
            }
            
            for agent in agents[:10]:
                health_info["agents"].append({
                    "agent_id": agent.get("agent_id"),
                    "name": agent.get("name"),
                    "capabilities": agent.get("capabilities", []),
                    "endpoint": agent.get("endpoint")
                })
            
            return health_info
        except Exception as e:
            return {"error": str(e)}
    
    def make_agent_decision(self, decision_type="agent_selection", context=None):
        """做出基于Agent网络的决策"""
        network_health = self.get_agent_network_health()
        
        decision_req = {
            "type": decision_type,
            "params": {
                "network_health": network_health,
                "context": context or {},
                "integration": "agent_network_v1"
            }
        }
        
        try:
            resp = requests.post(f"{self.decision_api}/api/decision", json=decision_req, timeout=5)
            return resp.json()
        except Exception as e:
            return {"error": str(e)}
    
    def get_recommendation(self):
        """获取智能推荐"""
        decision = self.make_agent_decision("agent_selection", {"purpose": "integration_test"})
        health = self.get_agent_network_health()
        
        return {
            "recommendation": decision,
            "network_health": health,
            "integration_complete": True,
            "timestamp": datetime.now().isoformat()
        }

def test():
    engine = AgentAwareDecisionEngine()
    result = engine.get_recommendation()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result

if __name__ == "__main__":
    test()
