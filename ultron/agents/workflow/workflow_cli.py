#!/usr/bin/env python3
"""
工作流CLI管理工具
"""

import requests
import json
import sys

API_BASE = "http://localhost:18100"

def cmd_list(args):
    """列出工作流"""
    status = args.status if hasattr(args, 'status') else None
    url = f"{API_BASE}/api/workflows"
    if status:
        url += f"?status={status}"
    
    resp = requests.get(url)
    data = resp.json()
    
    print(f"\n{'工作流ID':<25} {'名称':<20} {'状态':<12} {'创建时间'}")
    print("-" * 80)
    for wf in data:
        print(f"{wf['id']:<25} {wf['name']:<20} {wf['status']:<12} {wf['created_at'][:19]}")

def cmd_create(args):
    """创建工作流"""
    workflow = {
        "name": args.name,
        "description": args.desc or "",
        "tasks": json.loads(args.tasks) if args.tasks else []
    }
    
    resp = requests.post(f"{API_BASE}/api/workflows", json=workflow)
    data = resp.json()
    print(f"Created: {data['workflow_id']}")

def cmd_execute(args):
    """执行工作流"""
    resp = requests.post(f"{API_BASE}/api/workflows/{args.workflow_id}/execute")
    data = resp.json()
    print(json.dumps(data, indent=2))

def cmd_show(args):
    """显示工作流详情"""
    resp = requests.get(f"{API_BASE}/api/workflows/{args.workflow_id}")
    data = resp.json()
    
    print(f"\n工作流: {data['name']}")
    print(f"ID: {data['id']}")
    print(f"状态: {data['status']}")
    print(f"描述: {data['description']}")
    print(f"\n任务:")
    
    for task in data.get('tasks', []):
        deps = ', '.join(task.get('depends_on', []) or ['-'])
        print(f"  - {task['name']} [{task['status']}] (依赖: {deps})")
        
        if task.get('result_json'):
            print(f"    结果: {task['result_json'][:100]}")
        if task.get('error'):
            print(f"    错误: {task['error']}")

def cmd_templates(args):
    """列出模板"""
    resp = requests.get(f"{API_BASE}/api/templates")
    data = resp.json()
    
    for t in data:
        print(f"\n{t['id']}: {t['name']}")
        print(f"  {t['description']}")
        print(f"  任务数: {len(t['tasks'])}")

def cmd_cancel(args):
    """取消工作流"""
    resp = requests.post(f"{API_BASE}/api/workflows/{args.workflow_id}/cancel")
    print(resp.json())

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='工作流管理CLI')
    sub = parser.add_subparsers()
    
    p_list = sub.add_parser('list', help='列出工作流')
    p_list.add_argument('--status', help='状态过滤')
    
    p_create = sub.add_parser('create', help='创建工作流')
    p_create.add_argument('--name', required=True, help='工作流名称')
    p_create.add_argument('--desc', help='描述')
    p_create.add_argument('--tasks', help='任务JSON')
    
    p_exec = sub.add_parser('execute', help='执行工作流')
    p_exec.add_argument('workflow_id', help='工作流ID')
    
    p_show = sub.add_parser('show', help='显示详情')
    p_show.add_argument('workflow_id', help='工作流ID')
    
    p_tpl = sub.add_parser('templates', help='列出模板')
    
    p_cancel = sub.add_parser('cancel', help='取消工作流')
    p_cancel.add_argument('workflow_id', help='工作流ID')
    
    args = parser.parse_args()
    
    if hasattr(args, 'status'):
        cmd_list(args)
    elif hasattr(args, 'name'):
        cmd_create(args)
    elif hasattr(args, 'workflow_id') and 'show' not in sys.argv:
        if 'cancel' in sys.argv:
            cmd_cancel(args)
        else:
            cmd_execute(args)
    elif hasattr(args, 'workflow_id') and 'show' in sys.argv:
        cmd_show(args)
    else:
        cmd_templates(args)

if __name__ == '__main__':
    main()