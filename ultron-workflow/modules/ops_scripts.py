#!/usr/bin/env python3
"""
自动化运维脚本集合
提供常用的系统运维自动化功能
"""
import os, subprocess, json
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
OPS_DIR = f'{WORKSPACE}/ultron-workflow/ops_scripts'

def ensure_dir():
    os.makedirs(OPS_DIR, exist_ok=True)

def health_check():
    """健康检查脚本"""
    result = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:18789/'], 
                            capture_output=True, timeout=5)
    return result.stdout.decode().strip() == '200'

def restart_service(service_name):
    """重启服务脚本"""
    result = subprocess.run(['systemctl', 'restart', service_name], capture_output=True, timeout=30)
    return result.returncode == 0

def backup_config():
    """配置备份脚本"""
    configs = ['/root/.openclaw/workspace/ultron-workflow/state.json']
    backup_dir = f'{WORKSPACE}/ultron-workflow/backups'
    os.makedirs(backup_dir, exist_ok=True)
    
    for config in configs:
        if os.path.exists(config):
            subprocess.run(['cp', config, f'{backup_dir}/'])
    
    return len(configs)

def cleanup_logs():
    """日志清理脚本"""
    log_dir = f'{WORKSPACE}/ultron-workflow/logs'
    count = 0
    
    for root, dirs, files in os.walk(log_dir):
        for f in files:
            if f.endswith('.log') and os.path.getsize(os.path.join(root, f)) > 10*1024*1024:  # >10MB
                os.remove(os.path.join(root, f))
                count += 1
    
    return count

def run_all_ops():
    """运行所有运维操作"""
    results = {
        'health_check': health_check(),
        'backup_count': backup_config(),
        'cleanup_count': cleanup_logs(),
        'timestamp': datetime.now().isoformat()
    }
    return results

if __name__ == '__main__':
    ensure_dir()
    results = run_all_ops()
    print(f'运维脚本执行结果:')
    print(f'  健康检查: {results["health_check"]}')
    print(f'  配置备份: {results["backup_count"]}个')
    print(f'  日志清理: {results["cleanup_count"]}个')
