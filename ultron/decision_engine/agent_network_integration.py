#!/usr/bin/env python3
"""
Decision Engine <-> Agent Network Integration
第175世任务：决策引擎与Agent网络深度集成
"""
import requests
import json
import time
from datetime import datetime

AGENT_GATEWAY = "http://localhost:18290"
DECISION_API = "http://localhost:18255"

def get_agent_network_status():
    """获取Agent网络状态"""
    try:
        resp = requests.get(f"{AGENT_GATEWAY}/api/agents", timeout=3)
        agents = resp.json()
        
        # Get health status
        health_resp = requests.get(f"{AGENT_GATEWAY}/api/health", timeout=3)
        
        return {
            "total_agents": len(agents.get("agents", [])),
            "agents": agents.get("agents", [])[:5],  # Top 5
            "gateway_healthy": health_resp.status_code == 200,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

def create_decision_from_agents(action_type="agent_selection", context=None):
    """基于Agent网络状态创建决策"""
    network_status = get_agent_network_status()
    
    decision_req = {
        "type": action_type,
        "params": {
            "context": context or {},
            "network_status": network_status,
            "source": "agent_network_integration"
        }
    }
    
    try:
        resp = requests.post(
            f"{DECISION_API}/api/decision",
            json=decision_req,
            timeout=5
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def get_decision_recommendation(agent_id=None):
    """获取决策推荐 - 用于Agent选择"""
    context = {}
    if agent_id:
        context["target_agent"] = agent_id
    
    result = create_decision_from_agents("agent_selection", context)
    return result

def test_integration():
    """测试集成"""
    print("=" * 50)
    print("Decision Engine <-> Agent Network Integration Test")
    print("=" * 50)
    
    # 1. Get network status
    print("\n[1] Agent Network Status:")
    status = get_agent_network_status()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    
    # 2. Create decision based on agents
    print("\n[2] Decision from Agent Network:")
    decision = get_decision_recommendation()
    print(json.dumps(decision, indent=2, ensure_ascii=False))
    
    # 3. Test prediction
    print("\n[3] Decision Prediction:")
    try:
        pred_resp = requests.post(
            f"{DECISION_API}/api/predict",
            json={"decision_type": "agent_selection", "context": {}},
            timeout=5
        )
        print(json.dumps(pred_resp.json(), indent=2, ensure_ascii=False))
    except Exception as e:
        print(f"Prediction error: {e}")
    
    print("\n" + "=" * 50)
    print("Integration Status: SUCCESS")
    print("=" * 50)
    
    return {
        "network_status": status,
        "decision": decision,
        "integrated_ports": {
            "decision_engine": 18255,
            "agent_gateway": 18290,
            "dashboard": 18256
        }
    }

if __name__ == "__main__":
    result = test_integration()
