#!/usr/bin/env python3
"""
编排引擎 CLI
"""

import argparse
import json
import requests
import sys

API_BASE = "http://localhost:18102"

def cmd_agents(args):
    """Agent管理"""
    if args.subcommand == "list":
        r = requests.get(f"{API_BASE}/api/agents")
        data = r.json()
        print(f"Total agents: {data['count']}")
        for agent in data.get("agents", []):
            status = "🟢" if agent["status"] == "online" else "🔴"
            print(f"  {status} {agent['id']}: {agent['name']}")
            print(f"     Capabilities: {', '.join(agent['capabilities'])}")
            print(f"     Endpoint: {agent['endpoint']}")
    
    elif args.subcommand == "discover":
        r = requests.get(f"{API_BASE}/api/agents/discover")
        data = r.json()
        print(f"Discovered {data['count']} agents:")
        for agent in data.get("discovered", []):
            print(f"  - {agent['id']}: {agent['name']} ({agent['status']})")
    
    elif args.subcommand == "register":
        data = {
            "id": args.id,
            "name": args.name,
            "capabilities": args.capabilities.split(",") if args.capabilities else [],
            "endpoint": args.endpoint,
            "status": "online"
        }
        r = requests.post(f"{API_BASE}/api/agents/register", json=data)
        print(r.json())
    
    elif args.subcommand == "capability":
        r = requests.get(f"{API_BASE}/api/agents/capability/{args.capability}")
        data = r.json()
        print(f"Agents with capability '{args.capability}':")
        for agent_id in data.get("agents", []):
            print(f"  - {agent_id}")


def cmd_orchestrations(args):
    """编排管理"""
    if args.subcommand == "list":
        r = requests.get(f"{API_BASE}/api/orchestrations")
        data = r.json()
        print(f"Total orchestrations: {data['count']}")
        for orch in data.get("orchestrations", []):
            status_icon = {
                "pending": "⏳", "running": "🔄", 
                "completed": "✅", "failed": "❌"
            }.get(orch["status"], "❓")
            print(f"  {status_icon} {orch['id']}: {orch['name']}")
            print(f"     Status: {orch['status']}, Tasks: {orch['tasks_count']}")
    
    elif args.subcommand == "create":
        tasks = []
        if args.tasks_file:
            with open(args.tasks_file) as f:
                tasks = json.load(f)
        else:
            # 从命令行解析tasks
            for task_str in args.task:
                parts = task_str.split(":")
                tasks.append({
                    "agent_id": parts[0] if len(parts) > 0 else "",
                    "action": parts[1] if len(parts) > 1 else "shell",
                    "params": {"command": parts[2]} if len(parts) > 2 else {}
                })
        
        data = {
            "name": args.name,
            "description": args.description or "",
            "agents": args.agents.split(",") if args.agents else [],
            "tasks": tasks
        }
        r = requests.post(f"{API_BASE}/api/orchestrations/create", json=data)
        result = r.json()
        print(result)
        if result.get("success"):
            print(f"Orchestration created: {result['orchestration_id']}")
    
    elif args.subcommand == "run":
        data = {"orchestration_id": args.orchestration_id}
        r = requests.post(f"{API_BASE}/api/orchestrations/run", json=data)
        result = r.json()
        print(json.dumps(result, indent=2))
    
    elif args.subcommand == "status":
        r = requests.get(f"{API_BASE}/api/orchestrations/{args.orchestration_id}")
        if r.status_code == 200:
            data = r.json()
            print(f"Orchestration: {data['name']}")
            print(f"Status: {data['status']}")
            print(f"Created: {data['created_at']}")
            if data.get('started_at'):
                print(f"Started: {data['started_at']}")
            if data.get('ended_at'):
                print(f"Ended: {data['ended_at']}")
            print("\nTasks:")
            for task in data.get("tasks", []):
                status_icon = {
                    "pending": "⏳", "running": "🔄",
                    "completed": "✅", "failed": "❌"
                }.get(task["status"], "❓")
                print(f"  {status_icon} {task['id']}: {task['action']} on {task['agent_id']}")
        else:
            print(r.json())


def cmd_dashboard(args):
    """仪表盘"""
    r = requests.get(f"{API_BASE}/api/dashboard")
    data = r.json()
    
    print("=" * 40)
    print("Agent Orchestrator Dashboard")
    print("=" * 40)
    
    agents = data.get("agents", {})
    print(f"\n🤖 Agents: {agents['total']} total")
    print(f"   🟢 Online: {agents['online']}")
    print(f"   🔴 Offline: {agents['offline']}")
    
    orchs = data.get("orchestrations", {})
    print(f"\n🔄 Orchestrations: {orchs['total']} total")
    print(f"   Running: {orchs['running']}")
    print(f"   Completed: {orchs['completed']}")
    print(f"   Failed: {orchs['failed']}")


def main():
    parser = argparse.ArgumentParser(description="Agent Orchestrator CLI")
    subparsers = parser.add_subparsers()
    
    # Agents
    parser_agents = subparsers.add_parser("agents", help="Agent management")
    parser_agents.add_argument("subcommand", choices=["list", "discover", "register", "capability"])
    parser_agents.add_argument("--id", help="Agent ID")
    parser_agents.add_argument("--name", help="Agent name")
    parser_agents.add_argument("--capabilities", help="Comma-separated capabilities")
    parser_agents.add_argument("--endpoint", help="Agent endpoint")
    parser_agents.add_argument("--capability", help="Capability to filter by")
    parser_agents.set_defaults(func=cmd_agents)
    
    # Orchestrations
    parser_orch = subparsers.add_parser("orchestrations", help="Orchestration management")
    parser_orch.add_argument("subcommand", choices=["list", "create", "run", "status"])
    parser_orch.add_argument("--name", help="Orchestration name")
    parser_orch.add_argument("--description", help="Description")
    parser_orch.add_argument("--agents", help="Comma-separated agent IDs")
    parser_orch.add_argument("--task", nargs="+", help="Task in format: agent_id:action:params")
    parser_orch.add_argument("--tasks-file", help="JSON file with tasks")
    parser_orch.add_argument("--orchestration-id", help="Orchestration ID")
    parser_orch.set_defaults(func=cmd_orchestrations)
    
    # Dashboard
    parser_dash = subparsers.add_parser("dashboard", help="Show dashboard")
    parser_dash.set_defaults(func=cmd_dashboard)
    
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()