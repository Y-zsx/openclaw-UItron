#!/usr/bin/env python3
"""
任务失败告警和自动重试模块
监控失败任务并自动重试
"""
import os, json, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
RETRY_CONFIG = f'{WORKSPACE}/ultron-workflow/config/retry_config.json'
RETRY_LOG = f'{WORKSPACE}/ultron-workflow/logs/task_retry.log'

# 默认重试配置
DEFAULT_CONFIG = {
    'enabled': True,
    'max_retries': 3,
    'retry_delay': 60,  # 秒
    'backoff_multiplier': 2,
    'retry_on_status': ['failed', 'timeout']
}

def log(msg):
    os.makedirs(os.path.dirname(RETRY_LOG), exist_ok=True)
    with open(RETRY_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}
")
    print(msg)

def load_config():
    if os.path.exists(RETRY_CONFIG):
        with open(RETRY_CONFIG) as f:
            return json.load(f)
    return DEFAULT_CONFIG

def save_config(config):
    os.makedirs(os.path.dirname(RETRY_CONFIG), exist_ok=True)
    with open(RETRY_CONFIG, 'w') as f:
        json.dump(config, f, indent=2)

def get_failed_tasks():
    """获取失败任务"""
    queue_file = f'{WORKSPACE}/ultron-workflow/logs/task_queue.json'
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            queue = json.load(f)
            return queue.get('failed', [])
    return []

def should_retry(task, config):
    """判断是否应该重试"""
    if not config.get('enabled', True):
        return False
    
    retry_count = task.get('retry_count', 0)
    max_retries = config.get('max_retries', 3)
    
    if retry_count >= max_retries:
        return False
    
    return True

def schedule_retry(task, config):
    """安排重试"""
    task['retry_count'] = task.get('retry_count', 0) + 1
    task['retry_at'] = datetime.now().isoformat()
    
    log(f'安排重试: {task["id"]} (第{task["retry_count"]}次)')
    
    # 更新重试计数
    queue_file = f'{WORKSPACE}/ultron-workflow/logs/task_queue.json'
    if os.path.exists(queue_file):
        with open(queue_file) as f:
            queue = json.load(f)
        
        # 移除失败任务
        queue['failed'] = [t for t in queue['failed'] if t['id'] != task['id']]
        
        # 重新加入pending
        queue['pending'].append(task)
        
        with open(queue_file, 'w') as f:
            json.dump(queue, f, indent=2)
    
    return task

def check_and_retry():
    """检查并重试失败任务"""
    config = load_config()
    log('开始检查失败任务...')
    
    failed = get_failed_tasks()
    log(f'发现 {len(failed)} 个失败任务')
    
    retry_count = 0
    for task in failed:
        if should_retry(task, config):
            schedule_retry(task, config)
            retry_count += 1
    
    log(f'已安排 {retry_count} 个任务重试')
    return {'failed_count': len(failed), 'retry_count': retry_count}

def send_failure_alert(task):
    """发送失败告警"""
    alert_module = f'{WORKSPACE}/ultron-workflow/modules/alert_integration.py'
    if os.path.exists(alert_module):
        import sys
        sys.path.insert(0, f'{WORKSPACE}/ultron-workflow/modules')
        try:
            import alert_integration
            alert_integration.send_alert(
                f'任务失败: {task["type"]}',
                f'任务 {task["id"]} 执行失败',
                'critical'
            )
        except:
            pass

if __name__ == '__main__':
    # 确保配置存在
    config = load_config()
    save_config(config)
    
    # 检查并重试
    result = check_and_retry()
    print(f'重试结果: {result}')
    
    # 检查失败任务并告警
    failed = get_failed_tasks()
    for task in failed:
        if task.get('retry_count', 0) >= config.get('max_retries', 3):
            send_failure_alert(task)
    
    log('任务失败告警和自动重试检查完成')
