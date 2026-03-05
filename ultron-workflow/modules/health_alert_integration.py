#!/usr/bin/env python3
"""
健康检查告警集成模块
将告警系统与健康检查系统深度集成
"""
import os, json, subprocess
from datetime import datetime, timedelta

WORKSPACE = '/root/.openclaw/workspace'
HEALTH_ALERT_LOG = f'{WORKSPACE}/ultron-workflow/logs/health_alerts.json'

def check_services_health():
    """检查服务健康状态"""
    services = {
        'gateway': 'http://localhost:18789/',
        'status_panel': 'http://localhost:8889/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/'
    }
    
    results = {}
    for name, url in services.items():
        try:
            result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '3', url],
                capture_output=True, timeout=5
            )
            status = result.stdout.decode().strip()
            results[name] = status == '200'
        except:
            results[name] = False
    
    return results

def load_alert_integration_module():
    """加载告警集成模块"""
    alert_module = f'{WORKSPACE}/ultron-workflow/modules/alert_integration.py'
    if os.path.exists(alert_module):
        # 动态导入
        import sys
        sys.path.insert(0, f'{WORKSPACE}/ultron-workflow/modules')
        try:
            import alert_integration
            return alert_integration
        except:
            return None
    return None

def health_check_with_alert():
    """健康检查并发送告警"""
    print('执行健康检查并集成告警...')
    
    # 1. 检查服务状态
    services = check_services_health()
    unhealthy = [k for k, v in services.items() if not v]
    
    # 2. 加载告警模块
    alert_mod = load_alert_integration_module()
    
    # 3. 发送告警
    if unhealthy and alert_mod:
        alert_mod.send_alert(
            '服务异常',
            f'异常服务: {unhealthy}',
            'critical'
        )
        print(f'已发送告警: {len(unhealthy)}个服务异常')
    elif alert_mod:
        print('所有服务正常，无告警')
    
    # 4. 保存健康检查结果
    health_data = {
        'timestamp': datetime.now().isoformat(),
        'services': services,
        'unhealthy_count': len(unhealthy)
    }
    
    with open(HEALTH_ALERT_LOG, 'w') as f:
        json.dump(health_data, f, indent=2)
    
    return {
        'services': services,
        'unhealthy': unhealthy,
        'alert_sent': len(unhealthy) > 0
    }

if __name__ == '__main__':
    result = health_check_with_alert()
    print(f'健康检查结果: {result}')
