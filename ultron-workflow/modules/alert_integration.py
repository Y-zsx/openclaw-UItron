#!/usr/bin/env python3
"""
告警通知集成模块
统一处理各类告警通知
"""
import os, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
ALERT_CONFIG = f'{WORKSPACE}/ultron-workflow/config/alert_config.json'
ALERT_HISTORY = f'{WORKSPACE}/ultron-workflow/logs/alert_history.json'

def load_config():
    """加载告警配置"""
    if os.path.exists(ALERT_CONFIG):
        with open(ALERT_CONFIG) as f:
            return json.load(f)
    return {
        'enabled': True,
        'cooldown': 300,
        'channels': ['log', 'api']
    }

def save_alert(alert):
    """保存告警到历史"""
    history = []
    if os.path.exists(ALERT_HISTORY):
        with open(ALERT_HISTORY) as f:
            history = json.load(f)
    
    history.append(alert)
    
    # 只保留最近100条
    if len(history) > 100:
        history = history[-100:]
    
    with open(ALERT_HISTORY, 'w') as f:
        json.dump(history, f, indent=2)

def send_alert(title, message, level='warning'):
    """发送告警"""
    config = load_config()
    
    if not config.get('enabled', True):
        return {'status': 'disabled'}
    
    alert = {
        'timestamp': datetime.now().isoformat(),
        'title': title,
        'message': message,
        'level': level,
        'channels': config.get('channels', ['log'])
    }
    
    # 保存到历史
    save_alert(alert)
    
    # 输出告警
    level_emoji = {'critical': '🔴', 'warning': '⚠️', 'info': 'ℹ️'}.get(level, '⚠️')
    print(f"{level_emoji} [ALERT] {title}: {message}")
    
    return {'status': 'sent', 'alert': alert}

def get_alert_history(count=10):
    """获取告警历史"""
    if os.path.exists(ALERT_HISTORY):
        with open(ALERT_HISTORY) as f:
            history = json.load(f)
            return history[-count:]
    return []

def check_health_and_alert():
    """检查健康状态并发送告警"""
    # 检查Dashboard数据
    dashboard_file = f'{WORKSPACE}/ultron-workflow/logs/dashboard_data.json'
    
    if not os.path.exists(dashboard_file):
        return {'status': 'no_data'}
    
    with open(dashboard_file) as f:
        data = json.load(f)
    
    alerts = []
    
    # 检查Gateway状态
    if data.get('gateway', {}).get('status') != 'running':
        alerts.append(('Gateway异常', f"Gateway状态: {data.get('gateway', {}).get('status')}", 'critical'))
    
    # 检查负载
    load = data.get('system', {}).get('load', {})
    if load:
        if load.get('1m', 0) > 5:
            alerts.append(('负载过高', f"1分钟负载: {load.get('1m')}", 'warning'))
    
    # 发送告警
    for title, msg, level in alerts:
        send_alert(title, msg, level)
    
    return {'status': 'checked', 'alerts': len(alerts)}

if __name__ == '__main__':
    # 测试发送告警
    result = send_alert('测试告警', '这是测试告警', 'info')
    print(f'测试结果: {result}')
    
    # 检查健康状态
    health = check_health_and_alert()
    print(f'健康检查: {health}')
    
    # 获取告警历史
    history = get_alert_history(5)
    print(f'告警历史: {len(history)}条')
