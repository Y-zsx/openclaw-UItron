#!/usr/bin/env python3
"""
Agent调度器CLI工具
Usage: python3 scheduler_cli.py <command> [args]
"""

import sys
import json
import argparse
from ultron.agent_scheduler import LoadBalancer, TaskScheduler, Task, generate_task_id

# 全局调度器实例
balancer = LoadBalancer(strategy="smart")
scheduler = TaskScheduler(balancer)


def cmd_register(agent_id: str):
    """注册Agent"""
    balancer.register_agent(agent_id)
    print(f"✅ Agent {agent_id} 已注册")


def cmd_unregister(agent_id: str):
    """注销Agent"""
    balancer.unregister_agent(agent_id)
    print(f"✅ Agent {agent_id} 已注销")


def cmd_update(agent_id: str, cpu: float, memory: float, queue: int, success: float, response: float):
    """更新Agent指标"""
    balancer.update_metrics(agent_id, {
        "cpu": cpu, "memory": memory, "queue_size": queue,
        "success_rate": success, "response_time": response
    })
    print(f"✅ Agent {agent_id} 指标已更新")


def cmd_submit(task_type: str, priority: int = 5, capability: str = None):
    """提交任务"""
    task = Task(
        task_id=generate_task_id(),
        task_type=task_type,
        priority=priority,
        required_capability=capability
    )
    scheduler.submit_task(task)
    print(f"✅ 任务 {task.task_id} 已提交 (类型:{task_type}, 优先级:{priority})")


def cmd_dispatch():
    """分发任务"""
    result = scheduler.dispatch()
    if result:
        task, agent_id = result
        print(f"🚀 {task.task_id} -> {agent_id}")
    else:
        print("❌ 无待处理任务")


def cmd_stats():
    """显示统计"""
    stats = balancer.get_stats()
    print("\n📊 Agent状态:")
    for aid, info in stats["agents"].items():
        print(f"  {aid}: 负载{info['load']}% | CPU{info['cpu']}% | 内存{info['memory']}% | 成功率{info['success_rate']}%")
    print(f"\n📋 待处理: {len(scheduler.pending_tasks)} | 运行中: {len(scheduler.running_tasks)} | 已完成: {len(scheduler.completed_tasks)}")


def cmd_rebalance():
    """负载重平衡"""
    moves = balancer.rebalance()
    if moves:
        for src, dsts in moves.items():
            print(f"⚖️ {src} -> {dsts[0]}")
    else:
        print("✅ 无需重平衡")


def cmd_json():
    """JSON输出完整状态"""
    print(json.dumps({
        "balancer": balancer.get_stats(),
        "pending": len(scheduler.pending_tasks),
        "running": len(scheduler.running_tasks),
        "completed": len(scheduler.completed_tasks)
    }, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser(description="Agent调度器CLI")
    sub = parser.add_subparsers(dest="cmd")
    
    sub.add_parser("stats", help="显示状态")
    sub.add_parser("rebalance", help="负载重平衡")
    sub.add_parser("dispatch", help="分发任务")
    sub.add_parser("json", help="JSON输出")
    
    sub.add_parser("list", help="列出所有命令")
    
    p = sub.add_parser("register", help="注册Agent")
    p.add_argument("agent_id")
    
    p = sub.add_parser("unregister", help="注销Agent")
    p.add_argument("agent_id")
    
    p = sub.add_parser("update", help="更新Agent指标")
    p.add_argument("agent_id")
    p.add_argument("cpu", type=float)
    p.add_argument("memory", type=float)
    p.add_argument("queue", type=int)
    p.add_argument("success", type=float)
    p.add_argument("response", type=float)
    
    p = sub.add_parser("submit", help="提交任务")
    p.add_argument("task_type")
    p.add_argument("--priority", type=int, default=5)
    p.add_argument("--capability")
    
    args = parser.parse_args()
    
    cmds = {
        "stats": cmd_stats,
        "rebalance": cmd_rebalance,
        "dispatch": cmd_dispatch,
        "json": cmd_json,
    }
    
    if args.cmd in cmds:
        cmds[args.cmd]()
    elif args.cmd == "register":
        cmd_register(args.agent_id)
    elif args.cmd == "unregister":
        cmd_unregister(args.agent_id)
    elif args.cmd == "update":
        cmd_update(args.agent_id, args.cpu, args.memory, args.queue, args.success, args.response)
    elif args.cmd == "submit":
        cmd_submit(args.task_type, args.priority, args.capability)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()