#!/usr/bin/env python3
"""
任务队列CLI管理工具
"""

import requests
import json
import sys

API_BASE = "http://localhost:18099"

def cmd_summary():
    r = requests.get(f"{API_BASE}/api/queue/summary")
    data = r.json()
    
    print("=== 任务队列状态 ===")
    print(f"总任务: {data['tasks']['total']}")
    print(f"  待处理: {data['tasks']['pending']}")
    print(f"  运行中: {data['tasks']['running']}")
    print(f"  已完成: {data['tasks']['completed']}")
    print(f"  失败: {data['tasks']['failed']}")
    
    print("\n=== Agent状态 ===")
    print(f"总Agent: {data['agents']['total']}")
    print(f"  空闲: {data['agents']['idle']}")
    print(f"  忙碌: {data['agents']['busy']}")
    print(f"  离线: {data['agents']['offline']}")
    print(f"平均负载: {data['agents']['avg_load']}")
    
    if data['pending_tasks']:
        print("\n=== 待处理任务 ===")
        for t in data['pending_tasks'][:5]:
            print(f"  [{t['priority']}] {t['name']} - {t['id'][:8]}")
    
    if data['idle_agents']:
        print("\n=== 空闲Agent ===")
        for a in data['idle_agents']:
            print(f"  {a['name']} (负载: {a['load']})")

def cmd_enqueue(name, payload=None, priority=1):
    r = requests.post(f"{API_BASE}/api/queue/enqueue", json={
        "name": name,
        "payload": payload or {},
        "priority": priority
    })
    data = r.json()
    print(f"任务已创建: {data['task_id']}")

def cmd_list_tasks(status=None):
    url = f"{API_BASE}/api/tasks"
    if status:
        url += f"?status={status}"
    r = requests.get(url)
    tasks = r.json()
    
    if not tasks:
        print("没有任务")
        return
    
    for t in tasks:
        print(f"[{t['status']:8}] {t['name']} (优先级:{t['priority']}) ID:{t['id'][:8]}")

def cmd_list_agents():
    r = requests.get(f"{API_BASE}/api/agents")
    agents = r.json()
    
    if not agents:
        print("没有注册的Agent")
        return
    
    for a in agents:
        print(f"[{a['status']:6}] {a['name']} 负载:{a['load']:.1%} 任务:{a.get('current_task_id', '无')[:8] if a.get('current_task_id') else '无'}")

def cmd_register_agent(name, capabilities=None, max_concurrent=1):
    r = requests.post(f"{API_BASE}/api/agents", json={
        "name": name,
        "capabilities": capabilities or [],
        "max_concurrent": max_concurrent
    })
    data = r.json()
    print(f"Agent已注册: {data['agent_id']}")

def cmd_distribute():
    r = requests.post(f"{API_BASE}/api/distribute")
    data = r.json()
    print(f"已分发 {data['distributed']} 个任务")

def cmd_complete(task_id, result=None, error=None):
    r = requests.post(f"{API_BASE}/api/queue/complete/{task_id}", json={
        "result": result,
        "error": error
    })
    print(f"任务 {task_id[:8]} 已标记为完成")

def cmd_heartbeat(agent_id):
    r = requests.post(f"{API_BASE}/api/agents/{agent_id}/heartbeat")
    print(f"Heartbeat sent for {agent_id[:8]}")

def usage():
    print("""任务队列CLI

用法: queue_cli.py <命令> [参数]

命令:
  summary                    显示队列摘要
  enqueue <name>             添加任务
    --payload <json>         任务数据
    --priority <0-3>         优先级 (默认1)
  
  tasks [status]             列出任务 (可选: pending/running/completed/failed)
  agents                     列出Agent
  register <name>            注册新Agent
    --caps <cap1,cap2>       能力标签
    --max <n>                最大并发任务数
  distribute                 手动分发任务
  complete <task_id>         标记任务完成
    --result <json>          结果数据
    --error <msg>            错误信息
  heartbeat <agent_id>       发送心跳

示例:
  queue_cli.py summary
  queue_cli.py enqueue "下载文件" --payload '{"url":"http://x.com"}' --priority 2
  queue_cli.py register "worker-1" --caps "download,compute" --max 2
  queue_cli.py tasks pending
""")
    sys.exit(1)

if __name__ == '__main__':
    if len(sys.argv) < 2:
        usage()
    
    cmd = sys.argv[1]
    
    if cmd == 'summary':
        cmd_summary()
    elif cmd == 'enqueue':
        name = sys.argv[2] if len(sys.argv) > 2 else 'unnamed'
        payload = None
        priority = 1
        for i, a in enumerate(sys.argv):
            if a == '--payload' and i+1 < len(sys.argv):
                payload = json.loads(sys.argv[i+1])
            if a == '--priority' and i+1 < len(sys.argv):
                priority = int(sys.argv[i+1])
        cmd_enqueue(name, payload, priority)
    elif cmd == 'tasks':
        status = sys.argv[2] if len(sys.argv) > 2 else None
        cmd_list_tasks(status)
    elif cmd == 'agents':
        cmd_list_agents()
    elif cmd == 'register':
        name = sys.argv[2] if len(sys.argv) > 2 else 'unknown'
        caps = None
        max_c = 1
        for i, a in enumerate(sys.argv):
            if a == '--caps' and i+1 < len(sys.argv):
                caps = sys.argv[i+1].split(',')
            if a == '--max' and i+1 < len(sys.argv):
                max_c = int(sys.argv[i+1])
        cmd_register_agent(name, caps, max_c)
    elif cmd == 'distribute':
        cmd_distribute()
    elif cmd == 'complete':
        if len(sys.argv) < 3:
            print("需要task_id")
            sys.exit(1)
        result = None
        error = None
        for i, a in enumerate(sys.argv):
            if a == '--result' and i+1 < len(sys.argv):
                result = json.loads(sys.argv[i+1])
            if a == '--error' and i+1 < len(sys.argv):
                error = sys.argv[i+1]
        cmd_complete(sys.argv[2], result, error)
    elif cmd == 'heartbeat':
        if len(sys.argv) < 3:
            print("需要agent_id")
            sys.exit(1)
        cmd_heartbeat(sys.argv[2])
    else:
        usage()