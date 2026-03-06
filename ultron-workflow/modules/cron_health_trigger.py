#!/usr/bin/env python3
"""
定时健康检查触发器
与告警API服务(端口18170)集成
"""
import os, sys, subprocess, json, requests
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/cron_health_trigger.log'
HEALTH_LOG = f'{WORKSPACE}/ultron-workflow/logs/health_check_log.json'
ALERT_API_URL = 'http://localhost:18170'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def check_alert_api() -> bool:
    """检查告警API是否可用"""
    try:
        resp = requests.get(f'{ALERT_API_URL}/health', timeout=3)
        return resp.status_code == 200
    except:
        return False

def send_health_alert(service_name: str, error: str, level: str = 'error') -> bool:
    """发送健康检查告警到API"""
    alert_data = {
        'rule_id': f'cron_health_{service_name}',
        'rule_name': f'定时健康检查: {service_name}',
        'service_name': 'cron-health-monitor',
        'level': level,
        'message': f'服务 {service_name} 异常: {error}',
        'value': 0,
        'threshold': 200,
        'labels': {
            'service': service_name,
            'check_type': 'cron_health'
        },
        'annotations': {
            'checked_at': datetime.now().isoformat(),
            'trigger': 'cron_health_trigger'
        }
    }
    
    try:
        resp = requests.post(f'{ALERT_API_URL}/alerts', json=alert_data, timeout=10)
        return resp.status_code == 200
    except:
        return False

def resolve_health_alert(service_name: str) -> bool:
    """解决健康检查告警"""
    try:
        resp = requests.get(
            f'{ALERT_API_URL}/alerts',
            params={'status': 'firing', 'service': 'cron-health-monitor'},
            timeout=5
        )
        if resp.status_code == 200:
            data = resp.json()
            for alert in data.get('alerts', []):
                labels = alert.get('labels', {})
                if labels.get('service') == service_name:
                    requests.post(
                        f"{ALERT_API_URL}/alerts/{alert['id']}/resolve",
                        json={'message': '健康检查恢复'},
                        timeout=5
                    )
                    return True
    except:
        pass
    return False

def load_health_log():
    """加载健康检查日志"""
    if os.path.exists(HEALTH_LOG):
        try:
            with open(HEALTH_LOG) as f:
                data = json.load(f)
                if isinstance(data, list):
                    return {'checks': data, 'summary': {'total': len(data), 'healthy': 0, 'warning': 0}}
                return data
        except:
            pass
    return {'checks': [], 'summary': {'total': 0, 'healthy': 0, 'warning': 0}}

def save_health_log(data):
    """保存健康检查日志"""
    with open(HEALTH_LOG, 'w') as f:
        json.dump(data, f, indent=2)

def run_scheduled_health_check():
    """由Cron触发的健康检查（带告警集成）"""
    log('Cron触发健康检查开始...')
    
    # 检查告警API是否可用
    alert_api_ok = check_alert_api()
    log(f'告警API状态: {"可用" if alert_api_ok else "不可用"}')
    
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
        'failed': result.get('failed', []),
        'recovered': result.get('recovered', [])
    }
    
    health_log.setdefault('checks', []).append(check_record)
    
    # 只保留最近100条
    checks = health_log.get('checks', [])
    if len(checks) > 100:
        checks = checks[-100:]
    health_log['checks'] = checks
    
    # 更新统计
    health_log['summary']['total'] = len(checks)
    health_log['summary']['healthy'] = len([c for c in checks if c.get('status') == 'healthy'])
    health_log['summary']['warning'] = len([c for c in checks if c.get('status') == 'warning'])
    
    save_health_log(health_log)
    log(f'日志已记录: 总检查{health_log["summary"]["total"]}次，健康{health_log["summary"]["healthy"]}次')
    
    # 发送到告警API
    if alert_api_ok:
        failed = result.get('failed', [])
        recovered = result.get('recovered', [])
        
        # 发送新告警
        for service in failed:
            if send_health_alert(service, f'健康检查失败', 'error'):
                log(f'已发送告警: {service}')
        
        # 解决已恢复的告警
        for service in recovered:
            if resolve_health_alert(service):
                log(f'已解决告警: {service}')
    else:
        log('告警API不可用，跳过告警发送')
    
    return result

if __name__ == '__main__':
    run_scheduled_health_check()