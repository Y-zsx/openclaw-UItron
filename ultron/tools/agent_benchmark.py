#!/usr/bin/env python3
"""Agent性能基准测试工具"""

import time
import json
import requests
import statistics
from datetime import datetime

EXECUTOR_URL = "http://localhost:8096"

def submit_task(priority="NORMAL", task_type="shell", command="echo 'benchmark test'"):
    """提交测试任务"""
    start = time.time()
    try:
        resp = requests.post(
            f"{EXECUTOR_URL}/api/v1/tasks",
            json={
                "command": command,
                "priority": priority,
                "type": task_type
            },
            timeout=30
        )
        elapsed = time.time() - start
        if resp.status_code == 200:
            return {"success": True, "elapsed_ms": elapsed * 1000, "data": resp.json()}
        return {"success": False, "elapsed_ms": elapsed * 1000, "error": resp.text}
    except Exception as e:
        return {"success": False, "elapsed_ms": (time.time() - start) * 1000, "error": str(e)}

def get_stats():
    """获取执行器统计信息"""
    try:
        resp = requests.get(f"{EXECUTOR_URL}/api/v1/stats", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}

def run_benchmark(iterations=20):
    """运行基准测试"""
    results = []
    print(f"开始Agent性能基准测试 ({iterations}次迭代)...")
    
    for i in range(iterations):
        result = submit_task(priority="NORMAL", command=f"echo 'test-{i}'")
        results.append(result)
        time.sleep(0.1)
    
    # 统计结果
    success_count = sum(1 for r in results if r.get("success"))
    response_times = [r.get("elapsed_ms", 0) for r in results if r.get("success")]
    
    benchmark_result = {
        "timestamp": datetime.now().isoformat(),
        "iterations": iterations,
        "success_count": success_count,
        "success_rate": success_count / iterations * 100,
        "response_times": {
            "min_ms": min(response_times) if response_times else 0,
            "max_ms": max(response_times) if response_times else 0,
            "avg_ms": statistics.mean(response_times) if response_times else 0,
            "median_ms": statistics.median(response_times) if response_times else 0,
            "stdev_ms": statistics.stdev(response_times) if len(response_times) > 1 else 0
        },
        "executor_stats": get_stats()
    }
    
    return benchmark_result

if __name__ == "__main__":
    result = run_benchmark(20)
    print(json.dumps(result, indent=2))
    
    # 保存结果
    with open("/root/.openclaw/workspace/ultron/data/agent_benchmark_result.json", "w") as f:
        json.dump(result, f, indent=2)
    print("\n结果已保存到 agent_benchmark_result.json")