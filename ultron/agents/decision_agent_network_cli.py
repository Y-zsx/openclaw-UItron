#!/usr/bin/env python3
"""
决策Agent协作网络CLI工具
"""

import requests
import json
import sys

BASE_URL = "http://localhost:18150"


def list_agents():
    """列出所有Agent"""
    resp = requests.get(f"{BASE_URL}/api/agents")
    data = resp.json()
    print(f"\n📋 注册的Agent ({data['count']}个):")
    for agent in data["agents"]:
        print(f"  - {agent['name']} ({agent['agent_id']})")
        print(f"    状态: {agent['status']}, 能力: {', '.join(agent['capabilities'])}")
        print(f"    端点: {agent['endpoint']}, 已完成任务: {agent['tasks_completed']}")


def find_agent(capability):
    """查找具有特定能力的Agent"""
    resp = requests.get(f"{BASE_URL}/api/agents/find", params={"capability": capability})
    data = resp.json()
    print(f"\n🔍 查找能力 '{capability}' 的Agent ({data['count']}个):")
    for agent in data["agents"]:
        print(f"  - {agent['name']} ({agent['agent_id']})")


def create_task(decision_id, task_type, capabilities):
    """创建协作任务"""
    data = {
        "decision_id": decision_id,
        "task_type": task_type,
        "required_capabilities": capabilities
    }
    resp = requests.post(f"{BASE_URL}/api/tasks", json=data)
    result = resp.json()
    print(f"\n✅ 任务创建成功:")
    print(f"  任务ID: {result['task_id']}")
    print(f"  分配Agent: {result['assigned_agents']}")
    print(f"  状态: {result['status']}")


def list_tasks(status=None):
    """列出任务"""
    params = {}
    if status:
        params["status"] = status
    resp = requests.get(f"{BASE_URL}/api/tasks", params=params)
    data = resp.json()
    print(f"\n📋 任务列表 ({data['count']}个):")
    for task in data["tasks"]:
        print(f"  - {task['task_id']} | {task['task_type']} | {task['status']}")
        print(f"    决策ID: {task['decision_id']}, 分配: {task['assigned_agents']}")


def get_status():
    """获取网络状态"""
    resp = requests.get(f"{BASE_URL}/api/network/status")
    data = resp.json()
    print(f"\n📊 网络状态:")
    print(f"  Agent数量: {data['stats']['agents_count']}")
    print(f"  活跃任务: {data['active_tasks']}")
    print(f"  总会话数: {data['stats']['total_tasks']}")
    print(f"  已完成: {data['stats']['completed_tasks']}")
    print(f"  失败: {data['stats']['failed_tasks']}")


def get_stats():
    """获取统计信息"""
    resp = requests.get(f"{BASE_URL}/api/stats")
    data = resp.json()
    print(f"\n📈 统计信息:")
    print(f"  总会话数: {data['total_tasks']}")
    print(f"  已完成任务: {data['completed_tasks']}")
    print(f"  失败任务: {data['failed_tasks']}")
    print(f"  Agent数量: {data['agents_count']}")


def main():
    if len(sys.argv) < 2:
        print("用法:")
        print("  python3 decision_agent_network_cli.py list              # 列出Agent")
        print("  python3 decision_agent_network_cli.py find <能力>       # 查找Agent")
        print("  python3 decision_agent_network_cli.py task <决策ID> <类型> <能力>  # 创建任务")
        print("  python3 decision_agent_network_cli.py tasks [状态]      # 列出任务")
        print("  python3 decision_agent_network_cli.py status            # 网络状态")
        print("  python3 decision_agent_network_cli.py stats             # 统计信息")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "list":
        list_agents()
    elif cmd == "find":
        if len(sys.argv) < 3:
            print("错误: 需要指定能力")
            sys.exit(1)
        find_agent(sys.argv[2])
    elif cmd == "task":
        if len(sys.argv) < 5:
            print("错误: 需要提供决策ID、任务类型和能力")
            sys.exit(1)
        create_task(sys.argv[2], sys.argv[3], sys.argv[4].split(","))
    elif cmd == "tasks":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        list_tasks(status)
    elif cmd == "status":
        get_status()
    elif cmd == "stats":
        get_stats()
    else:
        print(f"未知命令: {cmd}")


if __name__ == "__main__":
    main()