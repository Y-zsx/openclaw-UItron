#!/usr/bin/env python3
"""
奥创SDK基础示例 - 快速上手
展示最常用的基本操作
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultron_agent_sdk import AgentClient, TaskClient, CollaborationClient

def main():
    # 设置API地址（可选，默认使用环境变量或本地地址）
    base_url = os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")
    
    # 初始化客户端
    print("📡 初始化客户端...")
    agent_client = AgentClient(base_url=base_url)
    task_client = TaskClient(base_url=base_url)
    collab_client = CollaborationClient(base_url=base_url)
    
    # ===== Agent管理 =====
    print("\n🤖 === Agent管理 ===")
    
    # 1. 获取所有Agent列表
    print("\n1. 获取Agent列表:")
    agents = agent_client.list()
    print(f"   总计 {len(agents)} 个Agent")
    for agent in agents[:5]:  # 只显示前5个
        print(f"   - {agent.name} ({agent.status})")
    
    # 2. 按状态筛选
    print("\n2. 筛选活跃Agent:")
    active_agents = agent_client.list(status="active")
    print(f"   活跃: {len(active_agents)} 个")
    
    # 3. 按能力筛选
    print("\n3. 筛选具有特定能力的Agent:")
    compute_agents = agent_client.list(capability="compute")
    print(f"   具备compute能力: {len(compute_agents)} 个")
    
    # 4. 健康检查
    print("\n4. 系统健康检查:")
    health = agent_client.health_check()
    print(f"   状态: {health.status}")
    print(f"   版本: {health.version}")
    print(f"   运行时间: {health.uptime}秒")
    
    # ===== 任务管理 =====
    print("\n📋 === 任务管理 ===")
    
    # 1. 获取任务列表
    print("\n1. 获取任务列表:")
    tasks = task_client.list(limit=10)
    print(f"   最近 {len(tasks)} 个任务")
    for task in tasks[:3]:
        print(f"   - {task.type}: {task.status}")
    
    # 2. 创建新任务
    print("\n2. 创建新任务:")
    new_task = task_client.create(
        task_type="compute",
        payload={
            "operation": "add",
            "a": 10,
            "b": 20
        },
        priority=5,
        timeout=60
    )
    print(f"   任务ID: {new_task.id}")
    print(f"   类型: {new_task.type}")
    print(f"   状态: {new_task.status}")
    
    # 3. 等待任务完成
    print("\n3. 等待任务完成:")
    completed_task = task_client.wait_for_completion(
        new_task.id, 
        timeout=30,
        poll_interval=1.0
    )
    print(f"   最终状态: {completed_task.status}")
    if completed_task.result:
        print(f"   结果: {completed_task.result}")
    
    # ===== 协作会话 =====
    print("\n👥 === 协作会话 ===")
    
    # 1. 获取会话列表
    print("\n1. 获取协作会话:")
    sessions = collab_client.list_sessions()
    print(f"   总计 {len(sessions)} 个会话")
    
    # 2. 创建协作会话
    print("\n2. 创建协作会话:")
    # 获取一些可用Agent
    agent_ids = [a.id for a in agents[:3]]
    if agent_ids:
        session = collab_client.create_session(
            participants=agent_ids,
            strategy="parallel",
            checkpoint_enabled=True
        )
        print(f"   会话ID: {session.id}")
        print(f"   策略: {session.strategy}")
        print(f"   参与者: {len(session.participants)} 个")
    
    print("\n✅ 基础示例完成!")

if __name__ == "__main__":
    main()