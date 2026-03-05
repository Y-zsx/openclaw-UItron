#!/usr/bin/env python3
"""
Agent Executor CLI - 任务执行器命令行工具
"""

import sys
import json
import argparse
from agents.executor import TaskExecutor, ExecutionContext, ExecutionMode, ExecutionStatus
from agents.executor.runner import TaskRunner


def cmd_execute(args):
    """执行任务"""
    executor = TaskExecutor()
    
    # 注册函数
    if args.register:
        for item in args.register:
            name, func_path = item.split('=')
            # 简化: 这里只是占位
            print(f"Register: {name} = {func_path}")
    
    # 解析目标
    if args.func:
        target = {"func": args.func, "kwargs": {}}
        mode = ExecutionMode.FUNCTION
    elif args.script:
        target = args.script
        mode = ExecutionMode.SCRIPT
    else:
        print("Error: must specify --func or --script")
        return 1
    
    # 执行
    ctx = ExecutionContext(
        task_id=args.task_id or "cli-task",
        mode=mode,
        timeout=args.timeout
    )
    
    result = executor.execute(args.task_id or "cli-task", target, ctx)
    
    print(f"Status: {result.status.value}")
    print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"Duration: {result.duration:.3f}s")
    
    return 0 if result.status == ExecutionStatus.SUCCESS else 1


def cmd_run(args):
    """通用运行器"""
    runner = TaskRunner()
    
    result = runner.run(
        target=args.target,
        mode=args.mode,
        timeout=args.timeout
    )
    
    print(f"Success: {result.success}")
    print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"Duration: {result.duration:.3f}s")
    
    return 0 if result.success else 1


def cmd_list(args):
    """列出可用运行器"""
    runner = TaskRunner()
    print("Available runners:")
    for name in runner.runners:
        print(f"  - {name}")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Agent Executor CLI")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # execute 命令
    exec_parser = subparsers.add_parser("execute", help="Execute a task")
    exec_parser.add_argument("--task-id", help="Task ID")
    exec_parser.add_argument("--func", help="Function name")
    exec_parser.add_argument("--script", help="Shell script")
    exec_parser.add_argument("--timeout", type=int, default=300, help="Timeout in seconds")
    exec_parser.add_argument("--register", nargs="+", help="Register functions (name=path)")
    exec_parser.set_defaults(func=cmd_execute)
    
    # run 命令
    run_parser = subparsers.add_parser("run", help="Run with TaskRunner")
    run_parser.add_argument("target", help="Target to run")
    run_parser.add_argument("--mode", default="shell", choices=["function", "script", "shell", "http"], help="Execution mode")
    run_parser.add_argument("--timeout", type=int, default=300, help="Timeout")
    run_parser.set_defaults(func=cmd_run)
    
    # list 命令
    list_parser = subparsers.add_parser("list", help="List available runners")
    list_parser.set_defaults(func=cmd_list)
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
        
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())