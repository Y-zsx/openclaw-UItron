#!/usr/bin/env python3
"""
Agent健康检查CLI工具
Usage: python health_monitor_cli.py <command> [args]
"""

import sys
import json
import argparse
from agent_health_monitor import HealthMonitorCLI, HealthChecker, HealthCheckConfig, HealthStatus

def cmd_register(cli, args):
    """注册Agent"""
    cli.register_agent(args.agent_id)
    print(f"✓ 已注册: {args.agent_id}")

def cmd_unregister(cli, args):
    """注销Agent"""
    cli.health_checker.unregister_agent(args.agent_id)
    print(f"✓ 已注销: {args.agent_id}")

def cmd_check(cli, args):
    """健康检查"""
    cli.run_check(args.agent_id)
    health = cli.health_checker.get_health_status(args.agent_id)
    if health:
        print(f"状态: {health.status.value}")
        print(f"健康分数: {health.health_score:.1f}")
        print(f"连续失败: {health.consecutive_failures}")
        print(f"总失败: {health.total_failures}")

def cmd_status(cli, args):
    """获取状态"""
    if args.agent_id:
        health = cli.health_checker.get_health_status(args.agent_id)
        if health:
            print(json.dumps({
                "agent_id": health.agent_id,
                "status": health.status.value,
                "health_score": health.health_score,
                "consecutive_failures": health.consecutive_failures,
                "total_failures": health.total_failures,
                "last_check": health.last_check.isoformat(),
                "recovery_attempts": health.recovery_attempts
            }, indent=2, ensure_ascii=False))
        else:
            print(f"Agent不存在: {args.agent_id}")
    else:
        stats = cli.get_status()
        print(json.dumps(stats, indent=2, ensure_ascii=False))

def cmd_list(cli, args):
    """列出Agents"""
    agents = cli.list_agents()
    if agents:
        for agent_id in agents:
            health = cli.health_checker.get_health_status(agent_id)
            if health:
                status_icon = {
                    HealthStatus.HEALTHY: "✓",
                    HealthStatus.DEGRADED: "⚠",
                    HealthStatus.UNHEALTHY: "✗",
                    HealthStatus.DEAD: "☠",
                    HealthStatus.UNKNOWN: "?"
                }.get(health.status, "?")
                print(f"{status_icon} {agent_id}: {health.status.value} ({health.health_score:.1f}分)")
            else:
                print(f"? {agent_id}: unknown")
    else:
        print("无注册Agents")

def cmd_export(cli, args):
    """导出JSON"""
    export = cli.health_checker.export_status()
    print(json.dumps(export, indent=2, ensure_ascii=False))

def cmd_start_auto(cli, args):
    """启动自动检查"""
    cli.health_checker.start_auto_check()
    print("✓ 已启动自动健康检查")

def cmd_stop_auto(cli, args):
    """停止自动检查"""
    cli.health_checker.stop_auto_check()
    print("✓ 已停止自动健康检查")

def main():
    parser = argparse.ArgumentParser(description="Agent健康检查CLI")
    parser.add_argument("command", choices=["register", "unregister", "check", "status", "list", "export", "start", "stop"],
                        help="命令")
    parser.add_argument("agent_id", nargs="?", help="Agent ID")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    args = parser.parse_args()
    
    cli = HealthMonitorCLI()
    
    # 命令路由
    commands = {
        "register": cmd_register,
        "unregister": cmd_unregister,
        "check": cmd_check,
        "status": cmd_status,
        "list": cmd_list,
        "export": cmd_export,
        "start": cmd_start_auto,
        "stop": cmd_stop_auto
    }
    
    if args.command in commands:
        commands[args.command](cli, args)
    else:
        parser.print_help()
        
if __name__ == "__main__":
    main()