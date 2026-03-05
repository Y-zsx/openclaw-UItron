#!/usr/bin/env python3
"""
Agent Monitor CLI - 命令行管理工具
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import argparse
import json
from agent_monitor import get_monitor


def cmd_summary(args):
    """显示监控汇总"""
    monitor = get_monitor()
    summary = monitor.get_summary()
    
    print("\n" + "="*50)
    print("        Agent 监控中心 - 汇总")
    print("="*50)
    print(f"总Agent数: {summary['total_agents']}")
    print(f"  ├─ 在线: {summary['online_agents']}")
    print(f"  ├─ 忙碌: {summary['busy_agents']}")
    print(f"  ├─ 空闲: {summary['idle_agents']}")
    print(f"  └─ 离线: {summary['offline_agents']}")
    print(f"\n任务统计:")
    print(f"  ├─ 总任务: {summary['total_tasks']}")
    print(f"  ├─ 成功: {summary['total_success']}")
    print(f"  ├─ 失败: {summary['total_failed']}")
    print(f"  └─ 成功率: {summary['success_rate']}%")
    print(f"\n资源使用:")
    print(f"  ├─ 平均CPU: {summary['avg_cpu']}%")
    print(f"  └─ 平均内存: {summary['avg_memory']}%")
    print(f"\n更新时间: {summary['timestamp']}")
    print("="*50)


def cmd_agents(args):
    """列出所有Agent"""
    monitor = get_monitor()
    agents = monitor.get_all_agents()
    
    print("\n" + "="*60)
    print(f"{'Agent ID':<20} {'名称':<15} {'状态':<8} {'任务':<10} {'成功率':<10}")
    print("-"*60)
    
    for a in agents:
        tasks = a.get("tasks_total", 0)
        success = a.get("tasks_success", 0)
        rate = round(success / tasks * 100, 1) if tasks > 0 else 100.0
        print(f"{a['agent_id']:<20} {a['agent_name']:<15} {a['status']:<8} {tasks:<10} {rate:.1f}%")
    
    print("-"*60)
    print(f"共 {len(agents)} 个Agent")
    print("="*60)


def cmd_agent(args):
    """显示指定Agent详情"""
    monitor = get_monitor()
    agent = monitor.get_agent(args.agent_id)
    
    if not agent:
        print(f"错误: Agent {args.agent_id} 不存在")
        return
    
    stats = monitor.get_agent_stats(args.agent_id)
    
    print("\n" + "="*50)
    print(f"       Agent: {agent['agent_name']}")
    print("="*50)
    print(f"Agent ID: {agent['agent_id']}")
    print(f"状态: {agent['status']}")
    print(f"注册时间: {agent['registered_at']}")
    print(f"最后活跃: {agent['last_seen']}")
    print(f"\n任务统计:")
    print(f"  ├─ 总任务: {stats['tasks_total']}")
    print(f"  ├─ 成功: {stats['tasks_success']}")
    print(f"  ├─ 失败: {stats['tasks_failed']}")
    print(f"  └─ 成功率: {stats['success_rate']}%")
    print(f"\n性能:")
    print(f"  ├─ 平均响应时间: {stats['avg_response_time']}ms")
    print(f"  └─ 运行时间: {int(stats['uptime_seconds'])}s")
    print(f"\n资源:")
    print(f"  ├─ CPU: {agent['cpu_usage']}%")
    print(f"  └─ 内存: {agent['memory_usage']}%")
    print("="*50)


def cmd_register(args):
    """注册Agent"""
    monitor = get_monitor()
    metadata = {}
    if args.metadata:
        metadata = json.loads(args.metadata)
    
    success = monitor.register_agent(args.agent_id, args.agent_name, metadata)
    if success:
        print(f"✓ Agent {args.agent_name} ({args.agent_id}) 注册成功")
    else:
        print(f"✗ Agent {args.agent_id} 已存在")


def cmd_unregister(args):
    """注销Agent"""
    monitor = get_monitor()
    success = monitor.unregister_agent(args.agent_id)
    if success:
        print(f"✓ Agent {args.agent_id} 已注销")
    else:
        print(f"✗ Agent {args.agent_id} 不存在")


def cmd_record_task(args):
    """记录任务"""
    monitor = get_monitor()
    monitor.record_task(args.agent_id, args.success, args.response_time, args.error)
    print(f"✓ 任务已记录到 {args.agent_id}")


def cmd_alerts(args):
    """显示告警"""
    monitor = get_monitor()
    
    if args.unresolved:
        alerts = monitor.get_unresolved_alerts()
    else:
        alerts = monitor.check_alerts()
    
    print("\n" + "="*60)
    if not alerts:
        print("当前无告警")
    else:
        print(f"告警列表 ({len(alerts)}条):")
        print("-"*60)
        for a in alerts:
            level_icon = "🔴" if a.get("level") == "critical" else ("⚠️" if a.get("level") == "warning" else "ℹ️")
            print(f"{level_icon} [{a.get('level', 'info').upper()}] {a.get('agent_name', 'N/A')}")
            print(f"   {a.get('message', '')}")
            print("-"*60)
    print("="*60)


def cmd_history(args):
    """显示历史"""
    monitor = get_monitor()
    history = monitor.get_history(args.agent_id, args.minutes)
    
    print("\n" + "="*60)
    print(f"Agent: {args.agent_id} - 历史记录 (最近{args.minutes}分钟)")
    print("-"*60)
    print(f"{'时间':<25} {'状态':<8} {'CPU':<8} {'内存':<8} {'任务':<8} {'成功率':<8}")
    print("-"*60)
    
    for h in history[:20]:
        print(f"{h.get('recorded_at', '')[:19]:<25} {h.get('status', '')[:8]:<8} {h.get('cpu_usage', 0):.1f}%{'':<4} {h.get('memory_usage', 0):.1f}%{'':<4} {h.get('tasks_total', 0):<8} {h.get('success_rate', 0):.1f}%")
    
    print("-"*60)
    print(f"共 {len(history)} 条记录")


def cmd_trends(args):
    """显示趋势"""
    monitor = get_monitor()
    trends = monitor.get_trends(args.agent_id)
    
    print("\n" + "="*60)
    print(f"Agent: {args.agent_id} - 趋势分析")
    print("="*60)
    
    if trends.get("trend") == "insufficient_data":
        print("数据不足，无法分析趋势")
    else:
        print(f"数据点数: {trends.get('data_points', 0)}")
        print(f"\n成功率变化: {trends.get('success_rate_change', 0):+.2f}%")
        print(f"响应时间变化: {trends.get('response_time_change', 0):+.2f}ms")
        print(f"CPU变化: {trends.get('cpu_change', 0):+.2f}%")
    print("="*60)


def cmd_snapshot(args):
    """收集快照"""
    monitor = get_monitor()
    snapshot = monitor.collect_snapshot()
    print(f"✓ 快照已收集: {len(snapshot['agents'])} agents")
    print(f"  总任务: {snapshot['summary']['total_tasks']}")
    print(f"  成功率: {snapshot['summary']['success_rate']}%")


def cmd_thresholds(args):
    """阈值管理"""
    monitor = get_monitor()
    
    if args.set:
        parts = args.set.split('=')
        if len(parts) == 2:
            key, value = parts
            try:
                value = float(value)
            except:
                pass
            monitor.set_thresholds(**{key: value})
            print(f"✓ 阈值 {key} = {value}")
    else:
        print("\n当前阈值:")
        for k, v in monitor.thresholds.items():
            print(f"  {k}: {v}")


def main():
    parser = argparse.ArgumentParser(description="Agent Monitor CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # summary
    subparsers.add_parser("summary", help="显示监控汇总")
    
    # agents
    subparsers.add_parser("agents", help="列出所有Agent")
    
    # agent
    p_agent = subparsers.add_parser("agent", help="显示Agent详情")
    p_agent.add_argument("agent_id", help="Agent ID")
    
    # register
    p_reg = subparsers.add_parser("register", help="注册Agent")
    p_reg.add_argument("agent_id", help="Agent ID")
    p_reg.add_argument("agent_name", help="Agent名称")
    p_reg.add_argument("--metadata", help="元数据(JSON)")
    
    # unregister
    p_unreg = subparsers.add_parser("unregister", help="注销Agent")
    p_unreg.add_argument("agent_id", help="Agent ID")
    
    # record-task
    p_task = subparsers.add_parser("record-task", help="记录任务")
    p_task.add_argument("agent_id", help="Agent ID")
    p_task.add_argument("--success", action="store_true", help="任务成功")
    p_task.add_argument("--time", type=float, default=100, help="响应时间(ms)")
    p_task.add_argument("--error", help="错误信息")
    
    # alerts
    p_alerts = subparsers.add_parser("alerts", help="显示告警")
    p_alerts.add_argument("--unresolved", action="store_true", help="只显示未解决的")
    
    # history
    p_history = subparsers.add_parser("history", help="显示历史")
    p_history.add_argument("agent_id", help="Agent ID")
    p_history.add_argument("--minutes", type=int, default=60, help="分钟数")
    
    # trends
    p_trends = subparsers.add_parser("trends", help="显示趋势")
    p_trends.add_argument("agent_id", help="Agent ID")
    
    # snapshot
    subparsers.add_parser("snapshot", help="收集快照")
    
    # thresholds
    p_thresh = subparsers.add_parser("thresholds", help="阈值管理")
    p_thresh.add_argument("--set", help="设置阈值 (key=value)")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    commands = {
        "summary": cmd_summary,
        "agents": cmd_agents,
        "agent": cmd_agent,
        "register": cmd_register,
        "unregister": cmd_unregister,
        "record-task": cmd_record_task,
        "alerts": cmd_alerts,
        "history": cmd_history,
        "trends": cmd_trends,
        "snapshot": cmd_snapshot,
        "thresholds": cmd_thresholds,
    }
    
    commands.get(args.command, lambda _: parser.print_help())(args)


if __name__ == "__main__":
    main()