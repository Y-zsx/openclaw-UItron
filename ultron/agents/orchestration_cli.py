#!/usr/bin/env python3
"""
多Agent协作任务编排CLI
用法:
    python orchestration_cli.py create-task --name "任务名" --agent executor --payload '{"key": "value"}'
    python orchestration_cli.py create-workflow --name "工作流名"
    python orchestration_cli.py add-task --workflow wf_1 --task-id task_1
    python orchestration_cli.py execute-workflow --workflow-id wf_1
    python orchestration_cli.py status
    python orchestration_cli.py report
"""

import argparse
import json
import sys
from enhanced_orchestrator import get_orchestrator, TaskStatus

def create_task(args):
    orch = get_orchestrator()
    payload = json.loads(args.payload) if args.payload else {}
    
    task = orch.create_task(
        task_id=args.task_id or f"task_{int(time.time()*1000)}",
        name=args.name,
        agent_type=args.agent,
        payload=payload,
        priority=args.priority,
        depends_on=args.depends.split(',') if args.depends else None,
        timeout=args.timeout,
        max_retries=args.retries
    )
    
    print(json.dumps({
        "status": "created",
        "task_id": task.id,
        "name": task.name,
        "agent_type": task.agent_type,
        "priority": task.priority
    }, indent=2, ensure_ascii=False))

def create_workflow(args):
    orch = get_orchestrator()
    wf = orch.create_workflow(
        workflow_id=args.workflow_id or f"wf_{int(time.time()*1000)}",
        name=args.name,
        description=args.description or ""
    )
    
    print(json.dumps({
        "status": "created",
        "workflow_id": wf.id,
        "name": wf.name
    }, indent=2, ensure_ascii=False))

def add_task_to_workflow(args):
    orch = get_orchestrator()
    
    if args.workflow_id not in orch.workflows:
        print(json.dumps({"error": "Workflow not found"}, indent=2))
        return
    
    if args.task_id not in orch.tasks:
        print(json.dumps({"error": "Task not found"}, indent=2))
        return
    
    task = orch.tasks[args.task_id]
    wf = orch.workflows[args.workflow_id]
    wf.tasks.append(task)
    
    print(json.dumps({
        "status": "added",
        "workflow_id": wf.id,
        "task_id": task.id
    }, indent=2, ensure_ascii=False))

def execute_workflow(args):
    orch = get_orchestrator()
    exec_id = orch.execute_workflow(args.workflow_id)
    
    if exec_id:
        print(json.dumps({
            "status": "started",
            "execution_id": exec_id,
            "workflow_id": args.workflow_id
        }, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": "Workflow not found"}, indent=2))

def get_task_status(args):
    orch = get_orchestrator()
    details = orch.get_task_details(args.task_id)
    
    if details:
        print(json.dumps(details, indent=2, ensure_ascii=False))
    else:
        print(json.dumps({"error": "Task not found"}, indent=2))

def get_workflow_status(args):
    orch = get_orchestrator()
    status = orch.get_workflow_status(args.execution_id)
    print(json.dumps(status, indent=2, ensure_ascii=False))

def list_tasks(args):
    orch = get_orchestrator()
    tasks = []
    
    for task in orch.tasks.values():
        tasks.append({
            "id": task.id,
            "name": task.name,
            "agent_type": task.agent_type,
            "status": task.status.value,
            "priority": task.priority,
            "depends_on": task.depends_on
        })
    
    print(json.dumps(tasks, indent=2, ensure_ascii=False))

def list_workflows(args):
    orch = get_orchestrator()
    wfs = []
    
    for wf in orch.workflows.values():
        wfs.append({
            "id": wf.id,
            "name": wf.name,
            "description": wf.description,
            "task_count": len(wf.tasks)
        })
    
    print(json.dumps(wfs, indent=2, ensure_ascii=False))

def status(args):
    orch = get_orchestrator()
    print(json.dumps(orch.get_stats(), indent=2, ensure_ascii=False))

def report(args):
    orch = get_orchestrator()
    print(json.dumps(orch.get_full_report(), indent=2, ensure_ascii=False))

def run_demo(args):
    """运行演示"""
    orch = get_orchestrator()
    
    # 创建数据采集任务
    task1 = orch.create_task(
        "collect_data", "采集系统指标", "monitor",
        {"metrics": ["cpu", "memory", "disk"]}, priority=8
    )
    
    # 创建分析任务
    task2 = orch.create_task(
        "analyze_data", "分析指标趋势", "executor",
        {"input": "collect_data"}, priority=7, depends_on=["collect_data"]
    )
    
    # 创建告警任务
    task3 = orch.create_task(
        "check_alerts", "检查告警条件", "analyzer",
        {"thresholds": {"cpu": 80, "memory": 85}}, 
        priority=9, depends_on=["analyze_data"]
    )
    
    # 创建通知任务
    task4 = orch.create_task(
        "send_notification", "发送通知", "communicator",
        {"channels": ["dingtalk"]}, priority=6, depends_on=["check_alerts"]
    )
    
    # 创建工作流
    wf = orch.create_workflow(
        "monitoring_workflow", "系统监控工作流",
        "完整的监控、分析、告警流程"
    )
    wf.tasks = [task1, task2, task3, task4]
    
    # 执行工作流
    exec_id = orch.execute_workflow("monitoring_workflow")
    print(f"工作流执行ID: {exec_id}\n")
    
    # 执行任务
    while True:
        task = orch.get_next_task()
        if not task:
            break
        
        print(f"▶ 执行任务: {task.name}")
        orch.start_task(task.id)
        
        # 模拟执行
        import time
        time.sleep(0.05)
        
        # 根据任务类型生成不同结果
        if task.agent_type == "monitor":
            result = {"cpu": 45, "memory": 62, "disk": 38}
        elif task.agent_type == "executor":
            result = {"trend": "stable", "score": 85}
        elif task.agent_type == "analyzer":
            result = {"alerts": [], "status": "healthy"}
        else:
            result = {"sent": True, "channels": 1}
        
        orch.complete_task(task.id, result=result)
        
        # 检查工作流状态
        status = orch.get_workflow_status(exec_id)
        print(f"  状态: {status['status']}\n")
    
    # 最终报告
    print("="*50)
    print(json.dumps(orch.get_full_report(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import time
    
    parser = argparse.ArgumentParser(description="多Agent协作任务编排CLI")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # create-task
    p = subparsers.add_parser("create-task", help="创建任务")
    p.add_argument("--task-id", help="任务ID")
    p.add_argument("--name", required=True, help="任务名称")
    p.add_argument("--agent", required=True, choices=["monitor", "executor", "analyzer", "communicator", "learner"], help="Agent类型")
    p.add_argument("--payload", default="{}", help="任务数据(JSON)")
    p.add_argument("--priority", type=int, default=5, help="优先级(1-10)")
    p.add_argument("--depends", help="依赖任务ID(逗号分隔)")
    p.add_argument("--timeout", type=float, default=60.0, help="超时时间(秒)")
    p.add_argument("--retries", type=int, default=3, help="最大重试次数")
    p.set_defaults(func=create_task)
    
    # create-workflow
    p = subparsers.add_parser("create-workflow", help="创建工作流")
    p.add_argument("--workflow-id", help="工作流ID")
    p.add_argument("--name", required=True, help="工作流名称")
    p.add_argument("--description", help="描述")
    p.set_defaults(func=create_workflow)
    
    # add-task
    p = subparsers.add_parser("add-task", help="添加任务到工作流")
    p.add_argument("--workflow-id", required=True, help="工作流ID")
    p.add_argument("--task-id", required=True, help="任务ID")
    p.set_defaults(func=add_task_to_workflow)
    
    # execute-workflow
    p = subparsers.add_parser("execute-workflow", help="执行工作流")
    p.add_argument("--workflow-id", required=True, help="工作流ID")
    p.set_defaults(func=execute_workflow)
    
    # task-status
    p = subparsers.add_parser("task-status", help="获取任务状态")
    p.add_argument("--task-id", required=True, help="任务ID")
    p.set_defaults(func=get_task_status)
    
    # workflow-status
    p = subparsers.add_parser("workflow-status", help="获取工作流状态")
    p.add_argument("--execution-id", required=True, help="执行ID")
    p.set_defaults(func=get_workflow_status)
    
    # list-tasks
    p = subparsers.add_parser("list-tasks", help="列出所有任务")
    p.set_defaults(func=list_tasks)
    
    # list-workflows
    p = subparsers.add_parser("list-workflows", help="列出所有工作流")
    p.set_defaults(func=list_workflows)
    
    # status
    p = subparsers.add_parser("status", help="获取系统状态")
    p.set_defaults(func=status)
    
    # report
    p = subparsers.add_parser("report", help="获取完整报告")
    p.set_defaults(func=report)
    
    # demo
    p = subparsers.add_parser("demo", help="运行演示")
    p.set_defaults(func=run_demo)
    
    args = parser.parse_args()
    
    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()