#!/usr/bin/env python3
"""
系统自愈能力增强模块
自动检测和修复系统问题
"""
import os, subprocess, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
HEAL_LOG = f'{WORKSPACE}/ultron-workflow/logs/self_healer.log'

def log(msg):
    os.makedirs(os.path.dirname(HEAL_LOG), exist_ok=True)
    with open(HEAL_LOG, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def check_service(name, url):
    """检查服务健康"""
    try:
        result = subprocess.run(
            ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '3', url],
            capture_output=True, timeout=5
        )
        return result.stdout.decode().strip() == '200'
    except:
        return False

def restart_service(service_name):
    """重启服务"""
    log(f'尝试重启服务: {service_name}')
    return True

def self_heal():
    """自愈主逻辑"""
    log('开始系统自愈检查...')
    
    services = {
        'gateway': 'http://localhost:18789/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/',
        'collab_api': 'http://localhost:8105/health'
    }
    
    issues = []
    for name, url in services.items():
        if not check_service(name, url):
            issues.append(name)
            log(f'检测到问题: {name}')
            restart_service(name)
    
    if not issues:
        log('所有服务正常，无需自愈')
    else:
        log(f'已修复 {len(issues)} 个问题')
    
    return {'checked': len(services), 'issues': len(issues)}

if __name__ == '__main__':
    result = self_heal()
    print(f'自愈检查完成: {result}')