#!/usr/bin/env python3
"""
服务网格测试
"""

import sys
import time
import requests
import threading

API_BASE = "http://localhost:8094"


def test_health():
    """测试健康检查"""
    print("\n📋 测试: 健康检查")
    r = requests.get(f"{API_BASE}/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"
    print("✅ 健康检查通过")


def test_circuit_breaker():
    """测试熔断器"""
    print("\n📋 测试: 熔断器")
    
    # 创建
    r = requests.post(f"{API_BASE}/api/circuit/test-cb", json={
        "failure_threshold": 0.3,
        "success_threshold": 2,
        "timeout": 5
    })
    assert r.status_code == 200
    print("✅ 创建熔断器")
    
    # 初始状态
    r = requests.get(f"{API_BASE}/api/circuit/test-cb")
    assert r.json()["state"] == "closed"
    print("✅ 初始状态: closed")
    
    # 记录失败
    for i in range(5):
        requests.post(f"{API_BASE}/api/circuit/test-cb/fail")
    
    r = requests.get(f"{API_BASE}/api/circuit/test-cb")
    assert r.json()["state"] == "open"
    print("✅ 熔断器打开: open")
    
    # 检查可用性
    r = requests.get(f"{API_BASE}/api/circuit/test-cb/available")
    assert r.json()["available"] == False
    print("✅ 熔断期间不可用")
    
    # 等待超时后进入半开
    time.sleep(6)
    r = requests.get(f"{API_BASE}/api/circuit/test-cb")
    print(f"✅ 超时后状态: {r.json()['state']}")
    
    # 恢复
    for i in range(3):
        requests.post(f"{API_BASE}/api/circuit/test-cb/success")
    
    r = requests.get(f"{API_BASE}/api/circuit/test-cb")
    assert r.json()["state"] == "closed"
    print("✅ 熔断器恢复: closed")


def test_rate_limiter():
    """测试限流器"""
    print("\n📋 测试: 限流器")
    
    # 创建
    r = requests.post(f"{API_BASE}/api/ratelimit/test-rl", json={
        "rate": 10,      # 每秒10个
        "capacity": 5    # 桶容量5
    })
    assert r.status_code == 200
    print("✅ 创建限流器")
    
    # 消耗令牌
    allowed = 0
    for i in range(10):
        r = requests.get(f"{API_BASE}/api/ratelimit/test-rl/check",
                        params={"client_id": "test-client"})
        if r.json()["allowed"]:
            allowed += 1
    
    print(f"✅ 10次请求中允许: {allowed}次")
    assert allowed <= 6  # 初始5 + 1秒补充1
    
    # 等待补充
    time.sleep(1)
    r = requests.get(f"{API_BASE}/api/ratelimit/test-rl/check",
                    params={"client_id": "test-client"})
    assert r.json()["allowed"] == True
    print("✅ 令牌补充后可用")


def test_traffic_router():
    """测试流量路由"""
    print("\n📋 测试: 流量路由")
    
    # 添加路由
    r = requests.post(f"{API_BASE}/api/route/test-service", json={
        "type": "canary",
        "targets": [
            {"version": "v1", "endpoint": "http://v1:8080"},
            {"version": "v2", "endpoint": "http://v2:8080"}
        ],
        "weights": [95, 5]
    })
    assert r.status_code == 200
    print("✅ 添加金丝雀路由")
    
    # 获取路由
    r = requests.get(f"{API_BASE}/api/route/test-service")
    assert r.json()["type"] == "canary"
    print(f"✅ 路由类型: {r.json()['type']}")
    
    # 路由分发
    results = {"v1": 0, "v2": 0}
    for i in range(100):
        r = requests.post(f"{API_BASE}/api/route/test-service/dispatch", json={})
        endpoint = r.json()["routed_to"]
        if "v1" in endpoint:
            results["v1"] += 1
        else:
            results["v2"] += 1
    
    print(f"✅ 分发结果: v1={results['v1']}, v2={results['v2']}")
    assert results["v1"] > results["v2"]  # v1权重更高
    
    # A/B测试
    requests.post(f"{API_BASE}/api/route/ab-service", json={
        "type": "ab_test",
        "targets": [
            {"version": "a", "endpoint": "http://a:8080"},
            {"version": "b", "endpoint": "http://b:8080"}
        ]
    })
    
    # 同一用户应该走同一版本
    r1 = requests.post(f"{API_BASE}/api/route/ab-service/dispatch", 
                      json={"user_id": "user123"})
    r2 = requests.post(f"{API_BASE}/api/route/ab-service/dispatch",
                      json={"user_id": "user123"})
    assert r1.json()["metadata"]["variant"] == r2.json()["metadata"]["variant"]
    print("✅ A/B测试: 同一用户走同一版本")


def test_service_discovery():
    """测试服务发现"""
    print("\n📋 测试: 服务发现")
    
    # 注册服务
    r = requests.post(f"{API_BASE}/api/discover/register", json={
        "service_name": "test-agent",
        "endpoint": "http://agent-1:8093",
        "metadata": {"version": "1.0"}
    })
    assert r.status_code == 200
    print("✅ 注册服务")
    
    # 发现服务
    r = requests.get(f"{API_BASE}/api/discover/test-agent")
    assert r.json()["instances"] == 1
    assert r.json()["healthy"] == 1
    print(f"✅ 发现服务: {r.json()['instances']}实例")
    
    # 心跳
    r = requests.post(f"{API_BASE}/api/discover/test-agent/heartbeat", json={
        "instance_id": "test-agent-0"
    })
    assert r.json()["success"] == True
    print("✅ 心跳成功")


def test_traffic_stats():
    """测试流量统计"""
    print("\n📋 测试: 流量统计")
    
    # 记录流量
    for i in range(20):
        requests.post(f"{API_BASE}/api/stats/traffic", json={
            "service": "test-service",
            "target": "v1",
            "latency_ms": 50 + i * 2,
            "success": i < 18,
            "status_code": 200 if i < 18 else 500
        })
    print("✅ 记录20条流量")
    
    # 获取统计
    r = requests.get(f"{API_BASE}/api/stats/traffic/test-service?window=60")
    stats = r.json()
    assert stats["requests"] == 20
    assert abs(stats["success_rate"] - 0.9) < 0.01
    print(f"✅ 请求数: {stats['requests']}, 成功率: {stats['success_rate']*100:.0f}%")


def test_status():
    """测试状态API"""
    print("\n📋 测试: 网格状态")
    r = requests.get(f"{API_BASE}/api/status")
    status = r.json()
    print(f"✅ 熔断器: {len(status['circuit_breakers'])}个")
    print(f"✅ 限流器: {len(status['rate_limiters'])}个")
    print(f"✅ 路由: {len(status['routes'])}条")


def main():
    print("=" * 50)
    print("🕸️  服务网格测试")
    print("=" * 50)
    
    try:
        test_health()
        test_circuit_breaker()
        test_rate_limiter()
        test_traffic_router()
        test_service_discovery()
        test_traffic_stats()
        test_status()
        
        print("\n" + "=" * 50)
        print("✅ 所有测试通过!")
        print("=" * 50)
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()