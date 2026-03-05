#!/usr/bin/env python3
"""
Agent任务调度与队列管理模块
管理任务队列、优先级和执行调度
"""
import os, json, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
QUEUE_FILE = f'{WORKSPACE}/ultron-workflow/logs/task_queue.json'
QUEUE_LOG = f'{WORKSPACE}/ultron-workflow/logs/queue_manager.log'

PRIORITY = {'critical': 1, 'high': 2, 'normal': 3, 'low': 4}

def log(msg):
    os.makedirs(os.path.dirname(QUEUE_LOG), exist_ok=True)
    with open(QUEUE_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def load_queue():
    if os.path.exists(QUEUE_FILE):
        with open(QUEUE_FILE) as f:
            return json.load(f)
    return {'pending': [], 'running': [], 'completed': [], 'failed': []}

def save_queue(queue):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

def add_task(task_type, params, priority='normal'):
    queue = load_queue()
    task = {
        'id': f"task_{int(time.time() * 1000)}",
        'type': task_type,
        'params': params,
        'priority': priority,
        'priority_val': PRIORITY.get(priority, 3),
        'status': 'pending',
        'added_at': datetime.now().isoformat(),
        'started_at': None,
        'completed_at': None
    }
    queue['pending'].append(task)
    queue['pending'].sort(key=lambda x: x['priority_val'])
    save_queue(queue)
    log(f'任务已添加: {task["id"]} - {task_type} ({priority})')
    return task

def get_next_task():
    queue = load_queue()
    if not queue['pending']:
        return None
    task = queue['pending'].pop(0)
    task['status'] = 'running'
    task['started_at'] = datetime.now().isoformat()
    queue['running'].append(task)
    save_queue(queue)
    return task

def complete_task(task_id, success=True):
    queue = load_queue()
    task = None
    for t in queue['running']:
        if t['id'] == task_id:
            task = t
            break
    if task:
        queue['running'] = [t for t in queue['running'] if t['id'] != task_id]
        task['status'] = 'completed' if success else 'failed'
        task['completed_at'] = datetime.now().isoformat()
        if success:
            queue['completed'].append(task)
        else:
            queue['failed'].append(task)
        if len(queue['completed']) > 100:
            queue['completed'] = queue['completed'][-100:]
        if len(queue['failed']) > 100:
            queue['failed'] = queue['failed'][-100:]
        save_queue(queue)
        log(f'任务完成: {task_id} - {success}')
    return task

def get_queue_status():
    queue = load_queue()
    return {'pending': len(queue['pending']), 'running': len(queue['running']), 'completed': len(queue['completed']), 'failed': len(queue['failed'])}

if __name__ == '__main__':
    add_task('health_check', {}, 'high')
    add_task('monitor', {}, 'normal')
    add_task('alert', {}, 'low')
    status = get_queue_status()
    print(f'队列状态: {status}')
    next_task = get_next_task()
    print(f'下一个任务: {next_task["id"]} - {next_task["type"]}')
    complete_task(next_task['id'], True)
    final_status = get_queue_status()
    print(f'最终状态: {final_status}')
    log('任务队列管理测试完成')