#!/usr/bin/env python3
"""
健康检查与API服务集成
在健康检查后自动验证API服务状态
"""
import os, sys, subprocess, json, urllib.request
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
API_PORT = 8890

def check_api_health():
    """检查API服务健康状态"""
    try:
        r = urllib.request.urlopen(f'http://localhost:{API_PORT}/health', timeout=5)
        data = json.loads(r.read().decode())
        return {'status': 'healthy', 'data': data}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}

def ensure_api_running():
    """确保API服务在运行"""
    manager = f'{WORKSPACE}/ultron-workflow/modules/health_api_manager.py'
    
    # 检查运行状态
    result = subprocess.run(
        [sys.executable, manager, 'check'],
        capture_output=True, text=True, timeout=10
    )
    
    if '运行状态: False' in result.stdout or '运行状态: False' in result.stderr:
        # 启动服务
        subprocess.run([sys.executable, manager, 'start'], timeout=10)
        return True
    return True

if __name__ == '__main__':
    health = check_api_health()
    print(json.dumps(health, indent=2))