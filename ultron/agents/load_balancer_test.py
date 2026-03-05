#!/usr/bin/env python3
"""
负载均衡与故障转移 - 模拟测试
=============================
"""

import requests
import time
import random
import json
import sys

API = "http://localhost:8093"


def test_basic():
    """基础功能测试"""
    print("=" * 50)
    print("1. 基础功能测试")
    print("=" * 50)
    
    # 健康检查
    r = requests.get(f"{API}/health")
    print(f"  健康检查: {r.json()}")
    
    # 注册5个Agent
    for i in range(5):
        weight = random.choice([80, 90, 100, 100, 120])
        r = requests.post(f"{API}/api/agents/register", json={
            "agent_id": f"agent-{i}",
            "weight": weight
        })
        print(f"  注册 agent-{i}: 权重={weight}")
    
    # 查看所有Agent
    r = requests.get(f"{API}/api/agents")
    print(f"\n  总Agent数: {r.json()['total_agents']}")
    print(f"  健康Agent: {r.json()['healthy_agents']}")


def test_load_balance():
    """负载均衡测试"""
    print("\n" + "=" * 50)
    print("2. 负载均衡测试 - 分配20个任务")
    print("=" * 50)
    
    selection = {}
    for i in range(20):
        r = requests.post(f"{API}/api/select", json={
            "task_id": f"task-{i}",
            "capability": None
        })
        if r.status_code == 200:
            agent = r.json()['selected_agent']
            selection[agent] = selection.get(agent, 0) + 1
            
            # 模拟任务完成
            exec_time = random.uniform(10, 100)
            requests.post(f"{API}/api/agents/{agent}/complete", json={
                "execution_time": exec_time
            })
    
    print("  任务分配结果:")
    for agent, count in sorted(selection.items()):
        print(f"    {agent}: {count} 任务")


def test_failover():
    """故障转移测试"""
    print("\n" + "=" * 50)
    print("3. 故障转移测试")
    print("=" * 50)
    
    # 模拟任务失败
    for i in range(3):
        r = requests.post(f"{API}/api/failover/task", json={
            "task_id": f"fail-task-{i}",
            "agent_id": "agent-0",
            "error": "Connection timeout",
            "task_data": {"type": "test"}
        })
        result = r.json()
        print(f"  失败任务 {i}: {result.get('action')} (重试 {result.get('retry_count', 0)}/{result.get('max_retries', 3)})")
    
    # 查看失败任务
    r = requests.get(f"{API}/api/failover/tasks")
    print(f"  失败任务数: {r.json()['count']}")


def test_strategy():
    """策略测试"""
    print("\n" + "=" * 50)
    print("4. 策略切换测试")
    print("=" * 50)
    
    strategies = ['round_robin', 'least_connections', 'weighted', 'random']
    for strategy in strategies:
        r = requests.put(f"{API}/api/strategy", json={"strategy": strategy})
        if r.status_code == 200:
            print(f"  策略切换: {strategy}")
            
            # 测试选择
            for _ in range(3):
                r = requests.post(f"{API}/api/select")
                if r.status_code == 200:
                    print(f"    选择: {r.json()['selected_agent']}")


def test_stats():
    """统计信息"""
    print("\n" + "=" * 50)
    print("5. 统计信息")
    print("=" * 50)
    
    r = requests.get(f"{API}/api/stats")
    stats = r.json()
    print(f"  负载均衡器:")
    print(f"    - 策略: {stats['load_balancer']['strategy']}")
    print(f"    - 总Agent: {stats['load_balancer']['total_agents']}")
    print(f"    - 健康Agent: {stats['load_balancer']['healthy_agents']}")
    print(f"  故障转移:")
    print(f"    - 失败任务: {stats['failover']['failed_tasks']}")
    print(f"    - 离线Agent: {len(stats['failover']['offline_agents'])}")


def main():
    # 等待API启动
    print("等待API服务启动...")
    for i in range(10):
        try:
            r = requests.get(f"{API}/health", timeout=1)
            if r.status_code == 200:
                break
        except:
            time.sleep(1)
    else:
        print("❌ API服务未运行，请先启动 load_balancer_api.py")
        sys.exit(1)
    
    print("✅ API服务已就绪\n")
    
    test_basic()
    test_load_balance()
    test_failover()
    test_strategy()
    test_stats()
    
    print("\n" + "=" * 50)
    print("✅ 所有测试完成!")
    print("=" * 50)


if __name__ == '__main__':
    main()