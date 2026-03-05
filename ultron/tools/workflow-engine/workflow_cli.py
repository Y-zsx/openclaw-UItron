#!/usr/bin/env python3
"""
工作流引擎 CLI 工具
"""

import sys
import json
import argparse

sys.path.insert(0, "/root/.openclaw/workspace/ultron/tools/workflow-engine")
from workflow_engine import get_engine, WorkflowEngine

def cmd_create(args):
    engine = get_engine()
    tasks = []
    
    if args.tasks_file:
        with open(args.tasks_file) as f:
            tasks = json.load(f)
    else:
        # 从参数构建任务
        task_names = args.tasks.split(",") if args.tasks else []
        for i, name in enumerate(task_names):
            tasks.append({
                "name": name.strip(),
                "command": f"shell:echo 'Running {name}'",
                "depends_on": []
            })
    
    if not tasks:
        print("Error: No tasks provided")
        return 1
    
    wf_id = engine.create_workflow(args.name, args.description, tasks)
    print(f"Created workflow: {wf_id}")
    return 0

def cmd_run(args):
    engine = get_engine()
    result = engine.run_workflow(args.workflow_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("success") else 1

def cmd_list(args):
    engine = get_engine()
    workflows = engine.list_workflows()
    for wf in workflows:
        print(f"{wf['id']} | {wf['name']} | {wf['status']} | {wf['completed']}/{wf['tasks_count']} tasks")
    return 0

def cmd_status(args):
    engine = get_engine()
    status = engine.get_workflow_status(args.workflow_id)
    if status:
        print(json.dumps(status, indent=2, ensure_ascii=False))
    else:
        print("Workflow not found")
        return 1
    return 0

def cmd_cancel(args):
    engine = get_engine()
    if engine.cancel_workflow(args.workflow_id):
        print(f"Cancelled workflow {args.workflow_id}")
        return 0
    else:
        print("Cannot cancel workflow")
        return 1

def main():
    parser = argparse.ArgumentParser(prog="workflow")
    sub = parser.add_subparsers()
    
    p_create = sub.add_parser("create", help="Create workflow")
    p_create.add_argument("-n", "--name", default="Untitled", help="Workflow name")
    p_create.add_argument("-d", "--description", default="", help="Description")
    p_create.add_argument("-t", "--tasks", help="Comma-separated task names")
    p_create.add_argument("-f", "--tasks-file", help="JSON file with tasks")
    p_create.set_defaults(func=cmd_create)
    
    p_run = sub.add_parser("run", help="Run workflow")
    p_run.add_argument("workflow_id", help="Workflow ID")
    p_run.set_defaults(func=cmd_run)
    
    p_list = sub.add_parser("list", help="List workflows")
    p_list.set_defaults(func=cmd_list)
    
    p_status = sub.add_parser("status", help="Get workflow status")
    p_status.add_argument("workflow_id", help="Workflow ID")
    p_status.set_defaults(func=cmd_status)
    
    p_cancel = sub.add_parser("cancel", help="Cancel workflow")
    p_cancel.add_argument("workflow_id", help="Workflow ID")
    p_cancel.set_defaults(func=cmd_cancel)
    
    args = parser.parse_args()
    if hasattr(args, "func"):
        return args.func(args)
    parser.print_help()
    return 0

if __name__ == "__main__":
    sys.exit(main())