#!/usr/bin/env python3
"""
工作流管理CLI
第59世: Agent协作工作流引擎与状态管理
"""

import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from workflow_state_manager import (
    WorkflowStateManager, WorkflowRecovery, WorkflowMonitor,
    WorkflowStatus, TaskState
)

AGENTS_DIR = os.path.dirname(os.path.abspath(__file__))


def cmd_create(args):
    """创建工作流"""
    manager = WorkflowStateManager()
    
    workflow_id = manager.create_workflow(
        name=args.name,
        context=json.loads(args.context) if args.context else {},
        metadata=json.loads(args.metadata) if args.metadata else {}
    )
    
    print(f"✅ 创建工作流成功: {workflow_id}")
    return workflow_id


def cmd_start(args):
    """启动工作流"""
    manager = WorkflowStateManager()
    
    if args.all:
        # 启动所有待启动的工作流
        workflows = manager.list_workflows(WorkflowStatus.CREATED.value)
        for wf in workflows:
            manager.start_workflow(wf['workflow_id'])
            print(f"✅ 启动工作流: {wf['workflow_id']} - {wf['name']}")
    else:
        manager.start_workflow(args.workflow_id)
        print(f"✅ 启动工作流: {args.workflow_id}")


def cmd_add_task(args):
    """添加任务"""
    manager = WorkflowStateManager()
    
    deps = args.dependencies.split(',') if args.dependencies else []
    deps = [d.strip() for d in deps if d.strip()]
    
    manager.add_task(
        workflow_id=args.workflow_id,
        task_id=args.task_id or str(uuid.uuid4())[:8],
        name=args.name,
        dependencies=deps,
        timeout=args.timeout,
        max_attempts=args.max_retries
    )
    
    print(f"✅ 添加任务成功: {args.task_id or 'auto'}")


def cmd_start_task(args):
    """开始任务"""
    manager = WorkflowStateManager()
    manager.start_task(args.workflow_id, args.task_id)
    print(f"✅ 任务开始: {args.task_id}")


def cmd_complete_task(args):
    """完成任务"""
    manager = WorkflowStateManager()
    result = json.loads(args.result) if args.result else None
    manager.complete_task(args.workflow_id, args.task_id, result, args.error)
    print(f"✅ 任务完成: {args.task_id}")


def cmd_complete(args):
    """完成工作流"""
    manager = WorkflowStateManager()
    manager.complete_workflow(args.workflow_id, args.error)
    print(f"✅ 工作流完成: {args.workflow_id}")


def cmd_pause(args):
    """暂停工作流"""
    manager = WorkflowStateManager()
    manager.pause_workflow(args.workflow_id)
    print(f"⏸️ 工作流已暂停: {args.workflow_id}")


def cmd_resume(args):
    """恢复工作流"""
    manager = WorkflowStateManager()
    manager.resume_workflow(args.workflow_id)
    print(f"▶️ 工作流已恢复: {args.workflow_id}")


def cmd_cancel(args):
    """取消工作流"""
    manager = WorkflowStateManager()
    manager.cancel_workflow(args.workflow_id)
    print(f"❌ 工作流已取消: {args.workflow_id}")


def cmd_status(args):
    """查看工作流状态"""
    manager = WorkflowStateManager()
    
    if args.workflow_id:
        state = manager.get_workflow_state(args.workflow_id)
        if state:
            print(f"\n📊 工作流状态: {args.workflow_id}")
            print(f"  名称: {state['name']}")
            print(f"  状态: {state['status']}")
            print(f"  进度: {state['progress']:.1f}%")
            print(f"  任务: {state['completed_tasks']}/{state['total_tasks']}")
            print(f"  失败: {state['failed_tasks']}")
            if state.get('error'):
                print(f"  错误: {state['error']}")
            
            # 显示任务列表
            tasks = manager.list_tasks(args.workflow_id)
            print(f"\n📋 任务列表:")
            for task in tasks:
                icon = {
                    TaskState.COMPLETED.value: "✅",
                    TaskState.FAILED.value: "❌",
                    TaskState.RUNNING.value: "🔄",
                    TaskState.BLOCKED.value: "🔒",
                    TaskState.PENDING.value: "⏳"
                }.get(task['state'], "❓")
                print(f"  {icon} {task['task_id']}: {task['name']} ({task['state']})")
        else:
            print(f"❌ 工作流不存在: {args.workflow_id}")
    else:
        # 列出所有工作流
        workflows = manager.list_workflows(limit=args.limit)
        print(f"\n📊 工作流列表 (共 {len(workflows)} 个):")
        for wf in workflows:
            icon = {
                WorkflowStatus.RUNNING.value: "🔄",
                WorkflowStatus.COMPLETED.value: "✅",
                WorkflowStatus.FAILED.value: "❌",
                WorkflowStatus.PAUSED.value: "⏸️",
                WorkflowStatus.CREATED.value: "📝"
            }.get(wf['status'], "❓")
            print(f"  {icon} {wf['workflow_id'][:8]} | {wf['name']} | {wf['status']} | {wf['progress']:.0f}%")


def cmd_history(args):
    """查看工作流历史"""
    manager = WorkflowStateManager()
    history = manager.get_workflow_history(limit=args.limit)
    
    print(f"\n📜 工作流历史 (共 {len(history)} 条):")
    for h in history:
        icon = "✅" if h['status'] == "completed" else "❌"
        duration = f"{h['duration']:.1f}s" if h.get('duration') else "N/A"
        print(f"  {icon} {h['name']} | {duration} | {h['tasks_completed']}/{h['tasks_total']} 任务")


def cmd_stats(args):
    """查看统计信息"""
    manager = WorkflowStateManager()
    stats = manager.get_statistics()
    
    print("\n📈 工作流统计:")
    print(f"  成功率: {stats['success_rate']:.1f}%")
    print(f"  平均执行时间: {stats['avg_duration']:.1f}秒")
    
    print(f"\n  工作流状态分布:")
    for status, count in stats.get('workflows_by_status', {}).items():
        print(f"    {status}: {count}")
    
    print(f"\n  任务状态分布:")
    for state, count in stats.get('tasks_by_state', {}).items():
        print(f"    {state}: {count}")


def cmd_recover(args):
    """恢复工作流"""
    manager = WorkflowStateManager()
    recovery = WorkflowRecovery(manager)
    
    if args.workflow_id:
        result = recovery.auto_recover(args.workflow_id)
        print(f"✅ 恢复完成: {result}")
    else:
        # 列出可恢复的工作流
        recoverable = manager.get_recoverable_workflows()
        print(f"\n🔧 可恢复的工作流 ({len(recoverable)} 个):")
        for wf in recoverable:
            print(f"  {wf['workflow_id']} - {wf['name']} ({wf['status']})")


def cmd_monitor(args):
    """监控工作流"""
    manager = WorkflowStateManager()
    monitor = WorkflowMonitor(manager)
    
    if args.workflow_id:
        health = monitor.get_workflow_health(args.workflow_id)
        print(f"\n💚 工作流健康状态: {args.workflow_id}")
        print(f"  健康分数: {health['health_score']:.1f}")
        print(f"  状态: {health['status']}")
        print(f"  进度: {health['progress']:.1f}%")
        
        if health.get('issues'):
            print(f"  问题:")
            for issue in health['issues']:
                print(f"    - {issue}")
        
        print(f"  任务统计:")
        print(f"    总数: {health['tasks']['total']}")
        print(f"    完成: {health['tasks']['completed']}")
        print(f"    失败: {health['tasks']['failed']}")
        print(f"    阻塞: {health['tasks']['blocked']}")
    else:
        active = monitor.get_active_workflows()
        print(f"\n🔴 活跃工作流 ({len(active)} 个):")
        for wf in active:
            print(f"  {wf['workflow_id'][:8]} | {wf['name']} | {wf['progress']:.0f}%")


def cmd_events(args):
    """查看事件日志"""
    manager = WorkflowStateManager()
    events = manager.get_events(args.workflow_id, limit=args.limit)
    
    print(f"\n📜 事件日志 (共 {len(events)} 条):")
    for e in events:
        print(f"  [{e['timestamp'][:19]}] {e['event_type']}: {e['workflow_id'][:8]}")


def cmd_watch(args):
    """实时监控工作流"""
    manager = WorkflowStateManager()
    monitor = WorkflowMonitor(manager)
    
    print(f"\n🔄 实时监控工作流: {args.workflow_id}")
    print("按 Ctrl+C 退出\n")
    
    try:
        while True:
            health = monitor.get_workflow_health(args.workflow_id)
            
            # 清除行
            print("\033[2J\033[H", end="")
            
            print(f"💚 健康状态: {health['health_score']:.1f}% | 状态: {health['status']}")
            print(f"📊 进度: {health['progress']:.1f}% | 任务: {health['tasks']['completed']}/{health['tasks']['total']}")
            
            if health.get('issues'):
                print(f"⚠️ 问题: {', '.join(health['issues'])}")
            
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\n👋 监控结束")


def main():
    parser = argparse.ArgumentParser(description="工作流管理CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 创建工作流
    p_create = subparsers.add_parser("create", help="创建工作流")
    p_create.add_argument("name", help="工作流名称")
    p_create.add_argument("--context", default="{}", help="上下文JSON")
    p_create.add_argument("--metadata", default="{}", help="元数据JSON")
    p_create.set_defaults(func=cmd_create)
    
    # 启动工作流
    p_start = subparsers.add_parser("start", help="启动工作流")
    p_start.add_argument("workflow_id", nargs="?", help="工作流ID")
    p_start.add_argument("--all", action="store_true", help="启动所有待启动工作流")
    p_start.set_defaults(func=cmd_start)
    
    # 添加任务
    p_task = subparsers.add_parser("add-task", help="添加任务")
    p_task.add_argument("workflow_id", help="工作流ID")
    p_task.add_argument("name", help="任务名称")
    p_task.add_argument("--task-id", help="任务ID")
    p_task.add_argument("--dependencies", default="", help="依赖任务ID，逗号分隔")
    p_task.add_argument("--timeout", type=float, default=60.0, help="超时时间(秒)")
    p_task.add_argument("--max-retries", type=int, default=3, help="最大重试次数")
    p_task.set_defaults(func=cmd_add_task)
    
    # 开始任务
    p_start_task = subparsers.add_parser("start-task", help="开始任务")
    p_start_task.add_argument("workflow_id", help="工作流ID")
    p_start_task.add_argument("task_id", help="任务ID")
    p_start_task.set_defaults(func=cmd_start_task)
    
    # 完成任务
    p_complete_task = subparsers.add_parser("complete-task", help="完成任务")
    p_complete_task.add_argument("workflow_id", help="工作流ID")
    p_complete_task.add_argument("task_id", help="任务ID")
    p_complete_task.add_argument("--result", help="结果JSON")
    p_complete_task.add_argument("--error", help="错误信息")
    p_complete_task.set_defaults(func=cmd_complete_task)
    
    # 完成工作流
    p_complete = subparsers.add_parser("complete", help="完成工作流")
    p_complete.add_argument("workflow_id", help="工作流ID")
    p_complete.add_argument("--error", help="错误信息")
    p_complete.set_defaults(func=cmd_complete)
    
    # 暂停工作流
    p_pause = subparsers.add_parser("pause", help="暂停工作流")
    p_pause.add_argument("workflow_id", help="工作流ID")
    p_pause.set_defaults(func=cmd_pause)
    
    # 恢复工作流
    p_resume = subparsers.add_parser("resume", help="恢复工作流")
    p_resume.add_argument("workflow_id", help="工作流ID")
    p_resume.set_defaults(func=cmd_resume)
    
    # 取消工作流
    p_cancel = subparsers.add_parser("cancel", help="取消工作流")
    p_cancel.add_argument("workflow_id", help="工作流ID")
    p_cancel.set_defaults(func=cmd_cancel)
    
    # 状态
    p_status = subparsers.add_parser("status", help="查看状态")
    p_status.add_argument("workflow_id", nargs="?", help="工作流ID")
    p_status.add_argument("--limit", type=int, default=20, help="显示数量")
    p_status.set_defaults(func=cmd_status)
    
    # 历史
    p_history = subparsers.add_parser("history", help="查看历史")
    p_history.add_argument("--limit", type=int, default=20, help="显示数量")
    p_history.set_defaults(func=cmd_history)
    
    # 统计
    p_stats = subparsers.add_parser("stats", help="查看统计")
    p_stats.set_defaults(func=cmd_stats)
    
    # 恢复
    p_recover = subparsers.add_parser("recover", help="恢复工作流")
    p_recover.add_argument("workflow_id", nargs="?", help="工作流ID")
    p_recover.set_defaults(func=cmd_recover)
    
    # 监控
    p_monitor = subparsers.add_parser("monitor", help="监控工作流")
    p_monitor.add_argument("workflow_id", nargs="?", help="工作流ID")
    p_monitor.set_defaults(func=cmd_monitor)
    
    # 事件
    p_events = subparsers.add_parser("events", help="查看事件")
    p_events.add_argument("workflow_id", nargs="?", help="工作流ID")
    p_events.add_argument("--limit", type=int, default=50, help="显示数量")
    p_events.set_defaults(func=cmd_events)
    
    # 实时监控
    p_watch = subparsers.add_parser("watch", help="实时监控")
    p_watch.add_argument("workflow_id", help="工作流ID")
    p_watch.add_argument("--interval", type=int, default=2, help="刷新间隔(秒)")
    p_watch.set_defaults(func=cmd_watch)
    
    args = parser.parse_args()
    
    if hasattr(args, 'func'):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()