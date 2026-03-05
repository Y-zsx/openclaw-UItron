#!/usr/bin/env python3
"""
奥创SDK高级示例 - 工作流编排
展示复杂任务编排和协作模式
"""

import os
import sys
import time
import json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultron_agent_sdk import AgentClient, TaskClient, CollaborationClient
from ultron_agent_sdk.exceptions import UltronSDKError

def run_parallel_tasks(task_client: TaskClient, agent_ids: list):
    """并行执行多个任务"""
    print("\n🔄 并行任务示例:")
    
    # 创建多个并行任务
    tasks = []
    for i, agent_id in enumerate(agent_ids[:3]):
        task = task_client.create(
            task_type="compute",
            payload={
                "operation": "multiply",
                "a": i + 1,
                "b": 10
            },
            priority=5
        )
        tasks.append(task)
        print(f"   创建任务 {i+1}: {task.id}")
    
    # 等待所有任务完成
    print("   等待所有任务完成...")
    results = []
    for task in tasks:
        completed = task_client.wait_for_completion(task.id, timeout=60)
        results.append(completed)
        print(f"   任务 {task.id}: {completed.status}")
    
    return results


def run_sequential_tasks(task_client: TaskClient):
    """顺序执行任务（依赖链）"""
    print("\n📝 顺序任务示例（任务依赖）:")
    
    # 第一个任务
    task1 = task_client.create(
        task_type="compute",
        payload={"operation": "add", "a": 5, "b": 3}
    )
    print(f"   任务1: {task1.id}")
    
    # 第二个任务（依赖第一个任务的结果）
    task2 = task_client.create(
        task_type="compute",
        payload={
            "operation": "multiply", 
            "a": "task_result_1",  # 引用上一个任务
            "b": 2
        },
        priority=3
    )
    print(f"   任务2 (依赖task1): {task2.id}")
    
    # 等待第一个完成后再等待第二个
    task1_result = task_client.wait_for_completion(task1.id)
    print(f"   任务1完成: {task1_result.status}")
    
    task2_result = task_client.wait_for_completion(task2.id)
    print(f"   任务2完成: {task2_result.status}")
    
    return [task1_result, task2_result]


def run_collaboration_session(agent_client: AgentClient, collab_client: CollaborationClient):
    """创建协作会话"""
    print("\n🤝 协作会话示例:")
    
    # 获取可用Agent
    agents = agent_client.list(status="active")
    if len(agents) < 2:
        print("   需要至少2个活跃Agent")
        return None
    
    # 选择参与者
    participants = [a.id for a in agents[:3]]
    print(f"   参与者: {participants}")
    
    # 创建并行协作会话
    session = collab_client.create_session(
        participants=participants,
        strategy="parallel",
        checkpoint_enabled=True
    )
    print(f"   会话ID: {session.id}")
    print(f"   策略: {session.strategy}")
    print(f"   状态: {session.status}")
    
    return session


def run_with_error_handling(task_client: TaskClient):
    """错误处理示例"""
    print("\n⚠️ 错误处理示例:")
    
    # 尝试获取不存在的任务
    try:
        task = task_client.get("non-existent-task-id")
    except Exception as e:
        print(f"   捕获错误: {type(e).__name__}")
        print(f"   错误信息: {e}")
    
    # 尝试创建任务（使用无效类型）
    try:
        task = task_client.create(
            task_type="invalid_type",
            payload={}
        )
    except UltronSDKError as e:
        print(f"   SDK错误: {e}")


def run_batch_operations(task_client: TaskClient):
    """批量操作示例"""
    print("\n📦 批量操作示例:")
    
    # 创建批量任务
    operations = [
        {"type": "compute", "payload": {"a": 1, "b": 2}},
        {"type": "compute", "payload": {"a": 3, "b": 4}},
        {"type": "compute", "payload": {"a": 5, "b": 6}},
    ]
    
    # 注意：需要后端支持批量API
    # 这里展示手动批量创建
    tasks = []
    for op in operations:
        task = task_client.create(
            task_type=op["type"],
            payload=op["payload"]
        )
        tasks.append(task)
        print(f"   创建: {task.id}")
    
    # 等待所有完成
    for task in tasks:
        task_client.wait_for_completion(task.id, timeout=30)
    
    print(f"   批量完成: {len(tasks)} 个任务")


def main():
    base_url = os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")
    
    print("=" * 50)
    print("🚀 奥创SDK高级示例 - 工作流编排")
    print("=" * 50)
    
    agent_client = AgentClient(base_url=base_url)
    task_client = TaskClient(base_url=base_url)
    collab_client = CollaborationClient(base_url=base_url)
    
    # 获取可用Agent列表
    agents = agent_client.list()
    agent_ids = [a.id for a in agents]
    
    if not agent_ids:
        print("❌ 没有可用的Agent")
        return
    
    print(f"可用Agent数量: {len(agent_ids)}")
    
    # 运行各种示例
    try:
        # 并行任务
        run_parallel_tasks(task_client, agent_ids)
        
        # 顺序任务
        run_sequential_tasks(task_client)
        
        # 协作会话
        run_collaboration_session(agent_client, collab_client)
        
        # 错误处理
        run_error_handling(task_client)
        
        # 批量操作
        run_batch_operations(task_client)
        
    except Exception as e:
        print(f"\n❌ 运行时错误: {e}")
    
    print("\n✅ 高级示例完成!")

if __name__ == "__main__":
    main()