#!/usr/bin/env python3
"""
决策引擎原型演示系统
Decision Engine Prototype Demo - API版本
"""
import requests
import json

API_BASE = "http://localhost:18120"

def print_header(title):
    print("\n" + "="*60)
    print(f"🎯 {title}")
    print("="*60)

def test_decision(trigger, context, description):
    """测试单个决策"""
    print(f"\n📋 {description}")
    print(f"   触发器: {trigger}")
    print(f"   数据: {json.dumps(context, ensure_ascii=False)}")
    
    try:
        resp = requests.post(
            f"{API_BASE}/decide",
            json={"trigger": trigger, "context": context},
            timeout=5
        )
        data = resp.json()
        
        if data.get("success"):
            decision = data.get("decision", {})
            print(f"   ✅ 决策: {decision.get('action')}")
            print(f"   📊 风险等级: {decision.get('risk_level')}/10")
            print(f"   📌 状态: {decision.get('status')}")
            return True
        else:
            print(f"   ❌ 失败: {data.get('message')}")
            return False
    except Exception as e:
        print(f"   ❌ 错误: {e}")
        return False

def main():
    print("🚀 启动决策引擎原型演示...")
    
    # 健康检查
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=3)
        health = resp.json()
        print(f"✅ 决策引擎API: {health.get('status')}")
    except Exception as e:
        print(f"❌ 无法连接决策引擎API: {e}")
        return 1
    
    # 演示场景
    scenarios = [
        ("cpu_high", {"cpu": 85, "host": "server01"}, "场景1: CPU过高告警"),
        ("memory_high", {"memory": 95, "host": "server02"}, "场景2: 内存不足"),
        ("disk_low", {"disk_free": 15, "host": "server03"}, "场景3: 磁盘空间不足"),
        ("service_down", {"service": "nginx", "service_status": "down"}, "场景4: 服务宕机"),
        ("error_rate", {"error_rate": 0.08, "endpoint": "/api/users"}, "场景5: 错误率过高"),
        ("health_check", {"status": "healthy", "uptime": 3600}, "场景6: 健康检查"),
    ]
    
    success_count = 0
    for trigger, context, desc in scenarios:
        if test_decision(trigger, context, desc):
            success_count += 1
    
    # 获取统计
    print_header("统计信息")
    try:
        resp = requests.get(f"{API_BASE}/stats", timeout=3)
        stats = resp.json()
        print(f"总决策数: {stats.get('total', 0)}")
        print(f"已批准: {stats.get('approved', 0)}")
        print(f"已完成: {stats.get('completed', 0)}")
        print(f"成功率: {stats.get('success_rate', 0):.1%}")
    except Exception as e:
        print(f"获取统计失败: {e}")
    
    # 获取规则列表
    print_header("已配置规则")
    try:
        resp = requests.get(f"{API_BASE}/rules", timeout=3)
        data = resp.json()
        rules = data.get("rules", [])
        print(f"共 {len(rules)} 条规则:")
        for r in rules[:6]:
            print(f"  - {r.get('name')} [{r.get('tags', [])}]")
    except Exception as e:
        print(f"获取规则失败: {e}")
    
    print_header("演示完成")
    print(f"✅ 成功: {success_count}/{len(scenarios)}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())