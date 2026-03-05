#!/usr/bin/env python3
"""
负载均衡与故障转移 CLI 管理工具
===============================
"""

import argparse
import json
import requests
import sys

API_BASE = "http://localhost:8093"


def cmd_register(args):
    """注册Agent"""
    resp = requests.post(f"{API_BASE}/api/agents/register", json={
        "agent_id": args.agent_id,
        "weight": args.weight
    })
    print_resp(resp)


def cmd_unregister(args):
    """注销Agent"""
    resp = requests.delete(f"{API_BASE}/api/agents/{args.agent_id}")
    print_resp(resp)


def cmd_list(args):
    """列出所有Agent"""
    resp = requests.get(f"{API_BASE}/api/agents")
    print_resp(resp)


def cmd_healthy(args):
    """获取健康Agent"""
    resp = requests.get(f"{API_BASE}/api/healthy")
    print_resp(resp)


def cmd_select(args):
    """选择Agent"""
    resp = requests.post(f"{API_BASE}/api/select", json={
        "task_id": args.task_id,
        "capability": args.capability,
        "exclude": args.exclude.split(',') if args.exclude else []
    })
    print_resp(resp)


def cmd_complete(args):
    """任务完成"""
    resp = requests.post(f"{API_BASE}/api/agents/{args.agent_id}/complete", json={
        "execution_time": args.time
    })
    print_resp(resp)


def cmd_fail(args):
    """任务失败"""
    resp = requests.post(f"{API_BASE}/api/agents/{args.agent_id}/fail", json={
        "error": args.error
    })
    print_resp(resp)


def cmd_failover_status(args):
    """故障转移状态"""
    resp = requests.get(f"{API_BASE}/api/failover/status")
    print_resp(resp)


def cmd_failed_tasks(args):
    """失败任务列表"""
    resp = requests.get(f"{API_BASE}/api/failover/tasks")
    print_resp(resp)


def cmd_strategy(args):
    """策略管理"""
    if args.get:
        resp = requests.get(f"{API_BASE}/api/strategy")
        print_resp(resp)
    else:
        resp = requests.put(f"{API_BASE}/api/strategy", json={
            "strategy": args.strategy
        })
        print_resp(resp)


def cmd_stats(args):
    """统计信息"""
    resp = requests.get(f"{API_BASE}/api/stats")
    print_resp(resp)


def print_resp(resp):
    if resp.status_code >= 400:
        print(f"❌ 错误: {resp.status_code}")
        print(resp.text)
        sys.exit(1)
    try:
        print(json.dumps(resp.json(), indent=2, ensure_ascii=False))
    except:
        print(resp.text)


def main():
    parser = argparse.ArgumentParser(description="负载均衡CLI")
    sub = parser.add_subparsers()
    
    # 注册/注销
    p = sub.add_parser('register', help='注册Agent')
    p.add_argument('agent_id')
    p.add_argument('--weight', type=int, default=100)
    p.set_defaults(func=cmd_register)
    
    p = sub.add_parser('unregister', help='注销Agent')
    p.add_argument('agent_id')
    p.set_defaults(func=cmd_unregister)
    
    p = sub.add_parser('list', help='列出所有Agent')
    p.set_defaults(func=cmd_list)
    
    p = sub.add_parser('healthy', help='获取健康Agent')
    p.set_defaults(func=cmd_healthy)
    
    # 选择
    p = sub.add_parser('select', help='选择Agent')
    p.add_argument('--task-id')
    p.add_argument('--capability')
    p.add_argument('--exclude')
    p.set_defaults(func=cmd_select)
    
    # 任务状态
    p = sub.add_parser('complete', help='任务完成')
    p.add_argument('agent_id')
    p.add_argument('--time', type=float, default=0)
    p.set_defaults(func=cmd_complete)
    
    p = sub.add_parser('fail', help='任务失败')
    p.add_argument('agent_id')
    p.add_argument('--error', default='Unknown error')
    p.set_defaults(func=cmd_fail)
    
    # 故障转移
    p = sub.add_parser('failover-status', help='故障转移状态')
    p.set_defaults(func=cmd_failover_status)
    
    p = sub.add_parser('failed-tasks', help='失败任务列表')
    p.set_defaults(func=cmd_failed_tasks)
    
    # 策略
    p = sub.add_parser('strategy', help='策略管理')
    p.add_argument('--get', action='store_true')
    p.add_argument('--set')
    p.set_defaults(func=cmd_strategy)
    
    # 统计
    p = sub.add_parser('stats', help='统计信息')
    p.set_defaults(func=cmd_stats)
    
    args = parser.parse_args()
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == '__main__':
    main()