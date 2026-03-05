#!/usr/bin/env python3
"""
Task Queue & Load Balancer Demo
================================
演示Agent任务队列与负载均衡功能
"""

import sys
import json
import time
from task_queue_manager import (
    TaskQueueManager, LoadBalancingAlgorithm, TaskPriority
)

def demo_basic_queue():
    """演示基本队列功能"""
    print("\n" + "="*60)
    print("演示1: 基本任务队列")
    print("="*60)
    
    manager = TaskQueueManager("demo_queue_state.json")
    
    # 注册多个Agent
    agents = [
        ("monitor-1", "monitor", ["collect", "metrics"], 3),
        ("monitor-2", "monitor", ["collect", "metrics"], 2),
        ("executor-1", "executor", ["execute", "shell"], 4),
        ("analyzer-1", "analyzer", ["analyze", "predict"], 3),
        ("communicator-1", "communicator", ["notify", "dingtalk"], 5),
    ]
    
    print("\n📋 注册Agent:")
    for agent_id, agent_type, skills, max_con in agents:
        manager.register_agent(agent_id, agent_type, skills, max_con)
        print(f"  ✅ {agent_id} ({agent_type}) - 技能: {skills}, 最大并发: {max_con}")
    
    # 入队多个任务
    print("\n📥 入队任务:")
    tasks = [
        ("采集CPU指标", "monitor", {"metric": "cpu"}, 8),
        ("采集内存指标", "monitor", {"metric": "memory"}, 8),
        ("分析CPU趋势", "executor", {"input": "cpu"}, 6),
        ("分析内存趋势", "executor", {"input": "memory"}, 6),
        ("检查告警条件", "analyzer", {"threshold": 80}, 9),
        ("发送通知", "communicator", {"channel": "dingtalk"}, 5),
        ("采集磁盘指标", "monitor", {"metric": "disk"}, 7),
        ("生成报告", "executor", {"type": "daily"}, 4),
    ]
    
    task_ids = []
    for name, agent_type, payload, priority in tasks:
        task_id = manager.enqueue(name, agent_type, payload, priority)
        task_ids.append(task_id)
        print(f"  ✅ {name} (优先级:{priority}) -> {task_id}")
    
    # 显示队列状态
    status = manager.get_queue_status()
    print(f"\n📊 队列状态: 待处理{status['pending']}个任务")
    
    return manager, task_ids


def demo_load_balancing(manager, task_ids):
    """演示负载均衡"""
    print("\n" + "="*60)
    print("演示2: 负载均衡算法")
    print("="*60)
    
    algorithms = [
        ("round_robin", LoadBalancingAlgorithm.ROUND_ROBIN),
        ("least_loaded", LoadBalancingAlgorithm.LEAST_LOADED),
        ("capability_match", LoadBalancingAlgorithm.CAPABILITY_MATCH),
        ("hybrid", LoadBalancingAlgorithm.HYBRID),
    ]
    
    for algo_name, algo in algorithms:
        print(f"\n🔄 算法: {algo_name}")
        
        # 重置负载
        for agent in manager.agents.values():
            agent.current_load = 0
        
        manager.set_algorithm(algo)
        
        # 分配任务
        for task_id in task_ids[:5]:
            agent_id = manager.select_agent(manager.tasks[task_id])
            if agent_id:
                manager.assign_task(task_id, agent_id)
                task = manager.tasks[task_id]
                print(f"  📤 {task.name[:15]:15} -> {agent_id}")
        
        # 显示负载
        loads = [(a.agent_id, a.current_load) for a in manager.agents.values()]
        print(f"  📊 负载分布: {loads}")


def demo_smart_assignment(manager):
    """演示智能任务分配"""
    print("\n" + "="*60)
    print("演示3: 智能任务分配")
    print("="*60)
    
    # 测试能力匹配
    print("\n🎯 技能匹配优先:")
    
    # 需要特定技能的任务
    task1 = manager.enqueue(
        "复杂数据分析", "executor",
        {"data": "large"},
        required_skills=["predict", "analyze"],
        priority=8
    )
    
    task2 = manager.enqueue(
        "Shell命令执行", "executor",
        {"cmd": "ls -la"},
        required_skills=["shell"],
        priority=5
    )
    
    manager.set_algorithm(LoadBalancingAlgorithm.CAPABILITY_MATCH)
    
    for task_id in [task1, task2]:
        task = manager.tasks[task_id]
        agent_id = manager.select_agent(task)
        manager.assign_task(task_id, agent_id)
        
        print(f"  📤 {task.name}")
        print(f"     要求技能: {task.required_skills}")
        print(f"     分配给: {agent_id} (技能: {manager.agents[agent_id].skills})")
    
    # 显示统计
    print("\n📈 最终负载均衡统计:")
    stats = manager.get_load_balancing_stats()
    print(f"  算法: {stats['algorithm']}")
    for load in stats['agent_loads']:
        print(f"  - {load['agent_id']}: {load['current_load']}/{load['max_concurrent']} "
              f"(负载率:{load['load_factor']})")


def demo_task_completion(manager):
    """演示任务完成流程"""
    print("\n" + "="*60)
    print("演示4: 任务完成与负载释放")
    print("="*60)
    
    # 获取一些待分配任务
    while True:
        task = manager.dequeue()
        if not task:
            break
        
        # 模拟执行
        print(f"\n⚙️  执行任务: {task.name}")
        time.sleep(0.1)  # 模拟执行时间
        
        # 标记完成
        manager.complete_task(task.id, {"status": "ok"}, True)
        print(f"  ✅ 完成 -> Agent负载释放")
        
        # 显示当前负载
        for agent in manager.agents.values():
            if agent.current_load > 0:
                print(f"  📊 {agent.agent_id}: {agent.current_load}/{agent.max_concurrent_tasks}")


def main():
    """主函数"""
    print("\n" + "🎯"*30)
    print("Agent任务队列与负载均衡 - 演示测试")
    print("🎯"*30)
    
    # 演示1: 基本队列
    manager, task_ids = demo_basic_queue()
    
    # 演示2: 负载均衡算法
    demo_load_balancing(manager, task_ids)
    
    # 演示3: 智能分配
    demo_smart_assignment(manager)
    
    # 演示4: 任务完成
    demo_task_completion(manager)
    
    print("\n" + "="*60)
    print("✅ 所有演示测试完成!")
    print("="*60)
    
    # 输出最终统计
    stats = manager.get_load_balancing_stats()
    print("\n📊 最终统计:")
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    return 0


if __name__ == '__main__':
    sys.exit(main())