#!/usr/bin/env python3
"""
统一入口 - Agent协作网络CLI
提供统一的命令行界面访问所有Agent服务
"""

import asyncio
import argparse
import json
import sys
import aiohttp
from typing import Optional

GATEWAY_URL = "http://localhost:8090"


async def health_check():
    """健康检查"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GATEWAY_URL}/health") as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))
            return data


async def list_agents(capability: Optional[str] = None):
    """列出Agent"""
    async with aiohttp.ClientSession() as session:
        url = f"{GATEWAY_URL}/api/agents"
        if capability:
            url += f"?capability={capability}"
        async with session.get(url) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def discover_agent(capability: str):
    """服务发现"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GATEWAY_URL}/api/discover?capability={capability}") as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def list_capabilities():
    """列出所有能力"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GATEWAY_URL}/api/capabilities") as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def get_metrics(agent_id: Optional[str] = None):
    """获取指标"""
    async with aiohttp.ClientSession() as session:
        url = f"{GATEWAY_URL}/api/metrics"
        if agent_id:
            url += f"?agent_id={agent_id}"
        async with session.get(url) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def get_stats():
    """获取统计"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GATEWAY_URL}/api/stats") as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def submit_task(agent_id: str, action: str, payload: dict, priority: int = 5):
    """提交任务"""
    async with aiohttp.ClientSession() as session:
        data = {
            "agent_id": agent_id,
            "action": action,
            "payload": payload,
            "priority": priority
        }
        async with session.post(f"{GATEWAY_URL}/api/tasks", json=data) as resp:
            result = await resp.json()
            print(json.dumps(result, indent=2))
            return result


async def list_tasks(status: Optional[str] = None, limit: int = 10):
    """列出任务"""
    async with aiohttp.ClientSession() as session:
        url = f"{GATEWAY_URL}/api/tasks?limit={limit}"
        if status:
            url += f"&status={status}"
        async with session.get(url) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def get_task(task_id: str):
    """获取任务详情"""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{GATEWAY_URL}/api/tasks/{task_id}") as resp:
            if resp.status == 404:
                print("Task not found")
                return
            data = await resp.json()
            print(json.dumps(data, indent=2))


async def register_agent(agent_id: str, name: str, capabilities: list, endpoint: str):
    """注册Agent"""
    async with aiohttp.ClientSession() as session:
        data = {
            "agent_id": agent_id,
            "name": name,
            "capabilities": capabilities,
            "endpoint": endpoint
        }
        async with session.post(f"{GATEWAY_URL}/api/agents", json=data) as resp:
            result = await resp.json()
            print(json.dumps(result, indent=2))


async def unregister_agent(agent_id: str):
    """注销Agent"""
    async with aiohttp.ClientSession() as session:
        async with session.delete(f"{GATEWAY_URL}/api/agents/{agent_id}") as resp:
            result = await resp.json()
            print(json.dumps(result, indent=2))


async def batch_submit(tasks: list):
    """批量提交任务"""
    async with aiohttp.ClientSession() as session:
        data = {"tasks": tasks}
        async with session.post(f"{GATEWAY_URL}/api/batch", json=data) as resp:
            result = await resp.json()
            print(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description="Agent协作网络CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # health
    subparsers.add_parser("health", help="健康检查")
    
    # list-agents
    parser_list = subparsers.add_parser("list-agents", help="列出Agent")
    parser_list.add_argument("--capability", help="按能力过滤")
    
    # discover
    parser_discover = subparsers.add_parser("discover", help="服务发现")
    parser_discover.add_argument("capability", help="能力名称")
    
    # capabilities
    subparsers.add_parser("capabilities", help="列出所有能力")
    
    # metrics
    parser_metrics = subparsers.add_parser("metrics", help="获取指标")
    parser_metrics.add_argument("--agent-id", help="Agent ID")
    
    # stats
    subparsers.add_parser("stats", help="获取统计")
    
    # submit-task
    parser_submit = subparsers.add_parser("submit-task", help="提交任务")
    parser_submit.add_argument("--agent-id", required=True, help="Agent ID")
    parser_submit.add_argument("--action", required=True, help="动作")
    parser_submit.add_argument("--payload", required=True, help="负载(JSON字符串)")
    parser_submit.add_argument("--priority", type=int, default=5, help="优先级")
    
    # list-tasks
    parser_tasks = subparsers.add_parser("list-tasks", help="列出任务")
    parser_tasks.add_argument("--status", help="状态过滤")
    parser_tasks.add_argument("--limit", type=int, default=10, help="数量限制")
    
    # get-task
    parser_get = subparsers.add_parser("get-task", help="获取任务")
    parser_get.add_argument("task_id", help="任务ID")
    
    # register
    parser_reg = subparsers.add_parser("register", help="注册Agent")
    parser_reg.add_argument("--agent-id", required=True, help="Agent ID")
    parser_reg.add_argument("--name", required=True, help="名称")
    parser_reg.add_argument("--capabilities", required=True, help="能力(逗号分隔)")
    parser_reg.add_argument("--endpoint", required=True, help="端点URL")
    
    # unregister
    parser_unreg = subparsers.add_parser("unregister", help="注销Agent")
    parser_unreg.add_argument("agent_id", help="Agent ID")
    
    # batch
    parser_batch = subparsers.add_parser("batch", help="批量提交")
    parser_batch.add_argument("tasks_file", help="任务文件(JSON)")

    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        if args.command == "health":
            asyncio.run(health_check())
        elif args.command == "list-agents":
            asyncio.run(list_agents(args.capability))
        elif args.command == "discover":
            asyncio.run(discover_agent(args.capability))
        elif args.command == "capabilities":
            asyncio.run(list_capabilities())
        elif args.command == "metrics":
            asyncio.run(get_metrics(args.agent_id))
        elif args.command == "stats":
            asyncio.run(get_stats())
        elif args.command == "submit-task":
            payload = json.loads(args.payload)
            asyncio.run(submit_task(args.agent_id, args.action, payload, args.priority))
        elif args.command == "list-tasks":
            asyncio.run(list_tasks(args.status, args.limit))
        elif args.command == "get-task":
            asyncio.run(get_task(args.task_id))
        elif args.command == "register":
            capabilities = args.capabilities.split(",")
            asyncio.run(register_agent(args.agent_id, args.name, capabilities, args.endpoint))
        elif args.command == "unregister":
            asyncio.run(unregister_agent(args.agent_id))
        elif args.command == "batch":
            with open(args.tasks_file) as f:
                tasks = json.load(f)
            asyncio.run(batch_submit(tasks))
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()