#!/usr/bin/env python3
"""
定时健康检查调度器 V2
负责定时执行健康检查、触发告警和自动恢复
"""
import os, sys, json, time, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/health_scheduler.log'
RECOVER_STATE_FILE = f'{WORKSPACE}/ultron-workflow/logs/recovery_state.json'

# 服务恢复命令配置
RECOVERY_COMMANDS = {
    'gateway': ['openclaw', 'gateway', 'restart'],
    'chrome': ['pkill', '-f', 'chrome.*headless'],
    'status_panel': ['systemctl', 'restart', 'status-panel'],
}

# 恢复冷却期（秒），防止频繁重启
RECOVERY_COOLDOWN = 300

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")

def load_recovery_state():
    """加载恢复状态"""
    if os.path.exists(RECOVER_STATE_FILE):
        try:
            with open(RECOVER_STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {'last_recovery': {}, 'recovery_count': {}}

def save_recovery_state(state):
    """保存恢复状态"""
    os.makedirs(os.path.dirname(RECOVER_STATE_FILE), exist_ok=True)
    with open(RECOVER_STATE_FILE, 'w') as f:
        json.dump(state, f)

def can_recover(service_name, state):
    """检查是否可以恢复（防止频繁重启）"""
    last_recovery = state['last_recovery'].get(service_name, 0)
    recovery_count = state['recovery_count'].get(service_name, 0)
    
    # 超过冷却期或恢复次数过多则不允许
    if time.time() - last_recovery < RECOVERY_COOLDOWN:
        log(f'{service_name}: 冷却期内，跳过恢复')
        return False
    if recovery_count >= 3:
        log(f'{service_name}: 今日恢复次数过多({recovery_count})，跳过')
        return False
    return True

def recover_service(service_name, state):
    """尝试恢复服务"""
    if service_name not in RECOVERY_COMMANDS:
        log(f'{service_name}: 无恢复命令')
        return False
    
    if not can_recover(service_name, state):
        return False
    
    cmd = RECOVERY_COMMANDS[service_name]
    log(f'尝试恢复 {service_name}: {" ".join(cmd)}')
    
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            # 更新恢复状态
            state['last_recovery'][service_name] = time.time()
            state['recovery_count'][service_name] = state['recovery_count'].get(service_name, 0) + 1
            save_recovery_state(state)
            log(f'{service_name}: 恢复成功')
            return True
        else:
            log(f'{service_name}: 恢复失败 - {result.stderr.decode()}')
            return False
    except Exception as e:
        log(f'{service_name}: 恢复异常 - {e}')
        return False

def check_services():
    """检查关键服务状态"""
    checks = []
    
    # 1. Gateway
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:18789/'], 
                          capture_output=True, timeout=5)
        checks.append(('gateway', r.stdout.decode() == '200'))
    except:
        checks.append(('gateway', False))
    
    # 2. Chrome headless
    try:
        r = subprocess.run(['pgrep', '-f', 'chrome.*headless'], capture_output=True, timeout=5)
        checks.append(('chrome', r.returncode == 0))
    except:
        checks.append(('chrome', False))
    
    # 3. 状态面板
    try:
        r = subprocess.run(['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', 'http://localhost:8889/'], 
                          capture_output=True, timeout=5)
        checks.append(('status_panel', r.stdout.decode() == '200'))
    except:
        checks.append(('status_panel', False))
    
    return checks

def run_health_check():
    """执行健康检查（含自动恢复）"""
    log('开始健康检查...')
    services = check_services()
    state = load_recovery_state()
    
    failed = [name for name, ok in services if not ok]
    healthy = len(services) - len(failed)
    total = len(services)
    
    # 自动恢复尝试
    recovery_attempted = []
    for service in failed:
        if recover_service(service, state):
            recovery_attempted.append(service)
    
    # 如果尝试了恢复，等待后再次检查
    if recovery_attempted:
        time.sleep(3)
        services = check_services()
        failed = [name for name, ok in services if not ok]
        healthy = len(services) - len(failed)
        log(f'恢复后检查: {healthy}/{total} 服务正常')
    
    if failed:
        log(f'WARNING: {len(failed)}个服务异常 - {failed}')
        return {'status': 'warning', 'healthy': healthy, 'total': total, 'failed': failed, 'recovered': recovery_attempted}
    else:
        log(f'OK: {healthy}/{total} 服务正常')
        return {'status': 'healthy', 'healthy': healthy, 'total': total, 'recovered': recovery_attempted}

if __name__ == '__main__':
    result = run_health_check()
    print(json.dumps(result, ensure_ascii=False))