#!/usr/bin/env python3
"""
健康检查API服务自动启动管理器
"""
import os, subprocess, time, sys, signal
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
PID_FILE = f'{WORKSPACE}/ultron-workflow/logs/health_api.pid'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/health_api.log'
PORT = 8890

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def is_running():
    """检查服务是否在运行"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)
            return True
        except:
            return False
    return False

def start():
    """启动服务"""
    if is_running():
        log('服务已在运行')
        return
    
    proc = subprocess.Popen(
        [sys.executable, f'{WORKSPACE}/ultron-workflow/modules/health_api_server.py'],
        stdout=open(LOG_FILE, 'a'),
        stderr=subprocess.STDOUT
    )
    
    with open(PID_FILE, 'w') as f:
        f.write(str(proc.pid))
    
    log(f'服务已启动, PID: {proc.pid}')

def stop():
    """停止服务"""
    if os.path.exists(PID_FILE):
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        try:
            os.kill(pid, signal.SIGTERM)
            log(f'服务已停止, PID: {pid}')
        except:
            log('停止失败')
        os.remove(PID_FILE)

def health_check():
    """健康检查"""
    import urllib.request
    try:
        r = urllib.request.urlopen(f'http://localhost:{PORT}/health', timeout=5)
        data = r.read().decode()
        return r.status == 200
    except:
        return False

def auto_restart():
    """自动重启不健康的服务"""
    if not health_check():
        log('健康检查失败，尝试重启...')
        stop()
        time.sleep(2)
        start()
        time.sleep(3)
        
        if health_check():
            log('重启成功')
        else:
            log('重启失败')

if __name__ == '__main__':
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        if cmd == 'start':
            start()
        elif cmd == 'stop':
            stop()
        elif cmd == 'restart':
            stop()
            time.sleep(2)
            start()
        elif cmd == 'check':
            log(f'运行状态: {is_running()}')
            log(f'健康状态: {health_check()}')
    else:
        auto_restart()