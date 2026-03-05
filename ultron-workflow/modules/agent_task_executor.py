#!/usr/bin/env python3
"""
Agent任务执行器集成模块
支持执行各种类型的Agent任务
"""
import os, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
EXECUTOR_LOG = f'{WORKSPACE}/ultron-workflow/logs/agent_executor.log'

# 任务类型定义
TASK_TYPES = {
    'shell': {'description': '执行Shell命令', 'timeout': 300},
    'python': {'description': '执行Python脚本', 'timeout': 600},
    'health_check': {'description': '健康检查', 'timeout': 30},
    'monitor': {'description': '系统监控', 'timeout': 60},
    'alert': {'description': '告警检查', 'timeout': 30},
    'backup': {'description': '数据备份', 'timeout': 3600}
}

def log(msg):
    os.makedirs(os.path.dirname(EXECUTOR_LOG), exist_ok=True)
    with open(EXECUTOR_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def execute_shell(command, timeout=30):
    """执行Shell命令"""
    log(f'执行Shell: {command[:50]}...')
    try:
        result = subprocess.run(
            command, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'stdout': result.stdout[:500],
            'stderr': result.stderr[:200]
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_python(script_path, timeout=60):
    """执行Python脚本"""
    log(f'执行Python: {script_path}')
    try:
        result = subprocess.run(
            ['python3', script_path], capture_output=True, text=True, timeout=timeout
        )
        return {
            'success': result.returncode == 0,
            'returncode': result.returncode,
            'output': result.stdout[:500]
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def execute_task(task_type, params):
    """执行任务"""
    log(f'执行任务: {task_type}')
    
    if task_type == 'shell':
        return execute_shell(params.get('command', ''), params.get('timeout', 30))
    elif task_type == 'python':
        return execute_python(params.get('script', ''), params.get('timeout', 60))
    elif task_type == 'health_check':
        result = subprocess.run(
            ['python3', f'{WORKSPACE}/ultron-workflow/modules/cron_health_trigger.py'],
            capture_output=True, text=True, timeout=30
        )
        return {'success': result.returncode == 0, 'output': result.stdout[:200]}
    elif task_type == 'monitor':
        result = subprocess.run(
            ['python3', f'{WORKSPACE}/ultron-workflow/modules/dashboard_aggregator.py'],
            capture_output=True, text=True, timeout=30
        )
        return {'success': result.returncode == 0, 'output': result.stdout[:200]}
    else:
        return {'success': False, 'error': f'未知任务类型: {task_type}'}

def list_task_types():
    """列出任务类型"""
    return TASK_TYPES

if __name__ == '__main__':
    types = list_task_types()
    print(f'支持的任务类型: {len(types)}种')
    for name, info in types.items():
        print(f'  - {name}: {info["description"]}')
    
    result = execute_task('health_check', {})
    print(f'健康检查结果: {result}')
    
    log('Agent任务执行器测试完成')