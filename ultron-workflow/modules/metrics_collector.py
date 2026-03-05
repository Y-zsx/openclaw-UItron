#!/usr/bin/env python3
"""
定时指标收集调度器
集成到Cron定时任务中
"""
import os, sys, json, subprocess
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/metrics_collector.log'
METRICS_SCRIPT = f'{WORKSPACE}/ultron-workflow/modules/enhanced_metrics.py'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def collect_metrics():
    """收集指标"""
    log('开始收集指标...')
    
    result = subprocess.run(
        [sys.executable, METRICS_SCRIPT],
        capture_output=True, text=True, timeout=30
    )
    
    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            load = data.get('system', {}).get('load', {})
            mem = data.get('system', {}).get('memory', {})
            services = data.get('services', {})
            
            healthy_services = [k for k, v in services.items() if v == 'healthy']
            
            log(f'指标收集完成: 负载{load.get("1m")}, 内存{mem.get("percent")}%, 服务{"+".join(healthy_services)}')
            return True
        except Exception as e:
            log(f'指标解析失败: {e}')
            return False
    else:
        log(f'指标收集失败: {result.stderr}')
        return False

if __name__ == '__main__':
    collect_metrics()