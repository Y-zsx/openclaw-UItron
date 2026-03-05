#!/usr/bin/env python3
import os, sys, subprocess, json
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/cron_health_trigger.log'
HEALTH_LOG = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def load_health_log():
    """加载健康检查日志"""
    if os.path.exists(HEALTH_LOG):
        with open(HEALTH_LOG) as f:
            return json.load(f)
    return {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}

def save_health_log(data):
    """保存健康检查日志"""
    with open(HEALTH_LOG, 'w') as f:
        json.dump(data, f, indent=2)

def run_scheduled_health_check():
    """由Cron触发的健康检查（带日志）"""
    log('Cron触发健康检查开始...')
    
    # 加载历史日志
    health_log = load_health_log()
    
    # 导入健康检查模块
    sys.path.insert(0, f'{WORKSPACE}/ultron-workflow/modules')
    from health_scheduler import run_health_check
    
    result = run_health_check()
    log(f'健康检查结果: {json.dumps(result)}')
    
    # 记录到日志
    check_record = {
        'time': datetime.now().isoformat(),
        'status': result.get('status'),
        'healthy': result.get('healthy'),
        'total': result.get('total'),
        'failed': result.get('failed', [])
    }
    
    health_log['checks'].append(check_record)
    
    # 只保留最近100条
    if len(health_log['checks']) > 100:
        health_log['checks'] = health_log['checks'][-100:]
    
    # 更新统计
    health_log['summary']['total'] = len(health_log['checks'])
    health_log['summary']['healthy'] = len([c for c in health_log['checks'] if c['status'] == 'healthy'])
    health_log['summary']['warning'] = len([c for c in health_log['checks'] if c['status'] == 'warning'])
    
    save_health_log(health_log)
    log(f'日志已记录: 总检查{health_log["summary"]["total"]}次，健康{health_log["summary"]["healthy"]}次')
    
    # 如果有告警，触发告警模块
    if result.get('status') == 'warning':
        from alert_manager import AlertManager
        am = AlertManager()
        failed = result.get('failed', [])
        am.send_alert(
            '服务异常', 
            f'服务 {failed} 异常',
            'warning'
        )
    
    return result

if __name__ == '__main__':
    run_scheduled_health_check()