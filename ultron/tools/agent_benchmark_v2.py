#!/usr/bin/env python3
"""Agent性能基准测试工具 v2 - 使用正确的API端点"""

import time
import json
import requests
import statistics
from datetime import datetime

AGENT_API_URL = "http://localhost:18131"
WORKFLOW_URL = "http://localhost:18100"
DECISION_URL = "http://localhost:18120"

def measure_endpoint(url, method="GET", json_data=None, iterations=10):
    """测量端点性能"""
    times = []
    success = 0
    for _ in range(iterations):
        start = time.time()
        try:
            if method == "GET":
                resp = requests.get(url, timeout=10)
            else:
                resp = requests.post(url, json=json_data, timeout=10)
            elapsed = (time.time() - start) * 1000
            if resp.status_code < 400:
                success += 1
                times.append(elapsed)
        except Exception as e:
            pass
    return {
        "iterations": iterations,
        "success": success,
        "min_ms": min(times) if times else 0,
        "max_ms": max(times) if times else 0,
        "avg_ms": round(statistics.mean(times), 2) if times else 0,
        "median_ms": round(statistics.median(times), 2) if times else 0
    }

def get_agent_stats():
    """获取Agent状态统计"""
    try:
        resp = requests.get(f"{AGENT_API_URL}/agents", timeout=10)
        if resp.status_code == 200:
            agents = resp.json()
            return {
                "total_agents": len(agents),
                "active_agents": sum(1 for a in agents.values() if a.get("status") == "active"),
                "agents": agents
            }
    except:
        pass
    return {"total_agents": 0, "active_agents": 0}

def run_full_benchmark():
    """运行完整基准测试"""
    print("=" * 50)
    print("Agent性能基准测试")
    print("=" * 50)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "endpoints": {},
        "agent_stats": {}
    }
    
    # 测试各端点性能
    endpoints = [
        ("GET", f"{AGENT_API_URL}/agents"),
        ("GET", f"{AGENT_API_URL}/metrics"),
        ("GET", f"{WORKFLOW_URL}/health"),
        ("GET", f"{DECISION_URL}/health"),
    ]
    
    for method, url in endpoints:
        print(f"测试 {method} {url}...")
        results["endpoints"][f"{method}:{url}"] = measure_endpoint(url, method)
    
    # 获取Agent统计
    results["agent_stats"] = get_agent_stats()
    
    # 打印结果
    print("\n" + "=" * 50)
    print("基准测试结果")
    print("=" * 50)
    for endpoint, metrics in results["endpoints"].items():
        print(f"\n{endpoint}:")
        print(f"  成功率: {metrics['success']}/{metrics['iterations']} ({metrics['success']/metrics['iterations']*100:.0f}%)")
        print(f"  响应时间: min={metrics['min_ms']:.1f}ms, max={metrics['max_ms']:.1f}ms, avg={metrics['avg_ms']:.1f}ms, median={metrics['median_ms']:.1f}ms")
    
    print(f"\nAgent状态:")
    print(f"  总数: {results['agent_stats'].get('total_agents', 0)}")
    print(f"  活跃: {results['agent_stats'].get('active_agents', 0)}")
    
    # 保存结果
    output_file = "/root/.openclaw/workspace/ultron/data/agent_benchmark_result.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n结果已保存到: {output_file}")
    
    return results

if __name__ == "__main__":
    run_full_benchmark()