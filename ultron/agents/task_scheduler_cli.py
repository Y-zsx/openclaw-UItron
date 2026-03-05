#!/usr/bin/env python3
"""
Task Scheduler CLI - 任务调度命令行工具
======================================
用于管理定时任务和任务队列
"""

import sys
import json
import argparse
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from task_scheduler_v2 import TaskSchedulerV2, get_scheduler, TaskPriority


def cmd_list(args):
    """列出任务"""
    scheduler = get_scheduler()
    
    if args.type == "scheduled":
        tasks = scheduler.list_scheduled_tasks()
        print(f"📅 定时任务 ({len(tasks)}个):")
        for t in tasks:
            status = "✅" if t["enabled"] else "⏸️"
            print(f"  {status} {t['id']}: {t['name']}")
            print(f"      类型: {t['task_type']} | 优先级: {t['priority']}")
            if t["cron"]:
                print(f"      Cron: {t['cron']}")
            if t["interval"]:
                print(f"      间隔: {t['interval']}秒")
            if t["next_run"]:
                print(f"      下次: {t['next_run']}")
            print()
    
    elif args.type == "running":
        tasks = scheduler.list_running_tasks()
        print(f"🔄 运行中 ({len(tasks)}个):")
        for t in tasks:
            print(f"  {t['id']}: {t['name']} | 状态: {t['status']}")
    
    elif args.type == "pending":
        tasks = scheduler.list_pending_tasks()
        print(f"⏳ 等待中 ({len(tasks)}个):")
        for t in tasks:
            print(f"  {t['id']}: {t['name']} | 优先级: {t['priority']}")
    
    elif args.type == "stats":
        stats = scheduler.get_stats()
        print("📊 调度器统计:")
        print(f"  定时任务总数: {stats['scheduled_tasks']}")
        print(f"  已完成: {stats['total_completed']}")
        print(f"  失败: {stats['total_failed']}")
        print(f"  取消: {stats['total_cancelled']}")
        print(f"  运行中: {stats['running_tasks']}")
        print(f"  等待中: {stats['pending_tasks']}")
        print(f"  平均执行时间: {stats['avg_execution_time']:.2f}秒")


def cmd_create(args):
    """创建任务"""
    scheduler = get_scheduler()
    
    task_id = scheduler.create_task(
        name=args.name,
        task_type=args.task_type,
        payload=json.loads(args.payload) if args.payload else {},
        priority=args.priority,
        cron_expression=args.cron,
        interval_seconds=args.interval,
        run_at=args.run_at,
        timeout=args.timeout,
        max_retries=args.retries
    )
    
    print(f"✅ 创建定时任务成功: {task_id}")
    
    # 如果指定了--trigger，立即触发
    if args.trigger:
        instance_id = scheduler.trigger_task(task_id)
        print(f"🔄 触发任务实例: {instance_id}")


def cmd_trigger(args):
    """触发任务"""
    scheduler = get_scheduler()
    
    payload = json.loads(args.payload) if args.payload else None
    instance_id = scheduler.trigger_task(args.task_id, payload)
    
    if instance_id:
        print(f"✅ 触发成功: {instance_id}")
    else:
        print(f"❌ 任务不存在: {args.task_id}")


def cmd_cancel(args):
    """取消任务"""
    scheduler = get_scheduler()
    
    if scheduler.cancel_task(args.task_id):
        print(f"✅ 取消定时任务: {args.task_id}")
    else:
        print(f"❌ 任务不存在: {args.task_id}")


def cmd_pause(args):
    """暂停任务"""
    scheduler = get_scheduler()
    
    if scheduler.pause_task(args.task_id):
        print(f"⏸️ 暂停任务: {args.task_id}")
    else:
        print(f"❌ 任务不存在: {args.task_id}")


def cmd_resume(args):
    """恢复任务"""
    scheduler = get_scheduler()
    
    if scheduler.resume_task(args.task_id):
        print(f"▶️ 恢复任务: {args.task_id}")
    else:
        print(f"❌ 任务不存在: {args.task_id}")


def cmd_status(args):
    """查看任务状态"""
    scheduler = get_scheduler()
    
    task = scheduler.get_task_status(args.instance_id)
    if task:
        print(f"📋 任务状态:")
        for k, v in task.items():
            print(f"  {k}: {v}")
    else:
        print(f"❌ 任务不存在: {args.instance_id}")


def cmd_start(args):
    """启动调度器"""
    scheduler = get_scheduler()
    scheduler.start()
    print("✅ 调度器已启动")


def cmd_stop(args):
    """停止调度器"""
    scheduler = get_scheduler()
    scheduler.stop()
    print("✅ 调度器已停止")


def main():
    parser = argparse.ArgumentParser(description="任务调度器CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # list
    list_parser = subparsers.add_parser("list", help="列出任务")
    list_parser.add_argument("type", choices=["scheduled", "running", "pending", "stats"],
                            help="任务类型")
    
    # create
    create_parser = subparsers.add_parser("create", help="创建定时任务")
    create_parser.add_argument("--name", required=True, help="任务名称")
    create_parser.add_argument("--type", dest="task_type", required=True, help="任务类型")
    create_parser.add_argument("--payload", default="{}", help="任务数据(JSON)")
    create_parser.add_argument("--priority", type=int, default=5, help="优先级(1-10)")
    create_parser.add_argument("--cron", help="Cron表达式")
    create_parser.add_argument("--interval", type=int, help="间隔秒数")
    create_parser.add_argument("--run-at", help="运行时间(ISO格式)")
    create_parser.add_argument("--timeout", type=float, default=300, help="超时秒数")
    create_parser.add_argument("--retries", type=int, default=3, help="最大重试次数")
    create_parser.add_argument("--trigger", action="store_true", help="创建后立即触发")
    
    # trigger
    trigger_parser = subparsers.add_parser("trigger", help="触发任务")
    trigger_parser.add_argument("task_id", help="定时任务ID")
    trigger_parser.add_argument("--payload", default="{}", help="任务数据(JSON)")
    
    # cancel
    cancel_parser = subparsers.add_parser("cancel", help="取消定时任务")
    cancel_parser.add_argument("task_id", help="定时任务ID")
    
    # pause
    pause_parser = subparsers.add_parser("pause", help="暂停任务")
    pause_parser.add_argument("task_id", help="定时任务ID")
    
    # resume
    resume_parser = subparsers.add_parser("resume", help="恢复任务")
    resume_parser.add_argument("task_id", help="定时任务ID")
    
    # status
    status_parser = subparsers.add_parser("status", help="查看任务状态")
    status_parser.add_argument("instance_id", help="任务实例ID")
    
    # start
    start_parser = subparsers.add_parser("start", help="启动调度器")
    
    # stop
    stop_parser = subparsers.add_parser("stop", help="停止调度器")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 执行命令
    commands = {
        "list": cmd_list,
        "create": cmd_create,
        "trigger": cmd_trigger,
        "cancel": cmd_cancel,
        "pause": cmd_pause,
        "resume": cmd_resume,
        "status": cmd_status,
        "start": cmd_start,
        "stop": cmd_stop
    }
    
    commands[args.command](args)


if __name__ == "__main__":
    main()