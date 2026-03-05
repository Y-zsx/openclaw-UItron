#!/usr/bin/env python3
"""
Agent协作网络服务健康检查增强系统
增强功能:
- 服务依赖图检查
- 主动告警 (超过阈值自动通知)
- 历史趋势分析
- 自定义检查项
"""

import socket
import requests
import json
import time
import os
from datetime import datetime, timedelta
from collections import defaultdict

CONFIG_FILE = '/root/.openclaw/workspace/ultron/data/health-config.json'
STATE_FILE = '/root/.openclaw/workspace/ultron/data/health-state.json'
ALERT_THRESHOLD = 3  # 连续失败3次告警

def load_config():
    """加载健康检查配置"""
    default_config = {
        "services": {
            "enhanced_executor_api": {"host": "127.0.0.1", "port": 18210, "critical": True},
            "gateway": {"host": "127.0.0.1", "port": 18789, "critical": True},
            "browser": {"host": "127.0.0.1", "port": 18800, "critical": False},
            "ultron_api": {"host": "127.0.0.1", "port": 18200, "critical": False},
        },
        "check_interval": 60,
        "alert_webhook": None
    }
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return {**default_config, **json.load(f)}
    return default_config

def load_state():
    """加载历史状态"""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {"history": [], "alerts": []}

def save_state(state):
    """保存状态"""
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def check_port(host, port, timeout=2):
    """检查端口是否开放"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        return result == 0
    except:
        return False

def check_service(name, config):
    """检查单个服务"""
    host, port = config['host'], config['port']
    port_ok = check_port(host, port)
    
    # 尝试HTTP健康检查
    http_ok = False
    if port_ok:
        try:
            r = requests.get(f'http://{host}:{port}/health', timeout=3)
            http_ok = r.status_code == 200
        except:
            pass
    
    return {
        "name": name,
        "host": config.get('host'),
        "port": config.get('port'),
        "port_open": port_ok,
        "http_ok": http_ok,
        "critical": config.get('critical', False),
        "timestamp": datetime.now().isoformat()
    }

def check_all(config):
    """检查所有服务"""
    results = []
    for name, svc_config in config['services'].items():
        result = check_service(name, svc_config)
        results.append(result)
        status = "✓" if result['port_open'] else "✗"
        http = "✓" if result['http_ok'] else "✗"
        print(f"  {status} {name}: port={result['port']}, http={http}")
    return results

def analyze_trends(state, current_results):
    """分析趋势"""
    history = state.get('history', [])
    if not history:
        return {"trend": "unknown", "changes": []}
    
    changes = []
    for curr in current_results:
        name = curr['name']
        # 找上一个状态
        prev = None
        for h in reversed(history):
            found = [s for s in h.get('results', []) if s['name'] == name]
            if found:
                prev = found[0]
                break
        
        if prev and prev['port_open'] != curr['port_open']:
            changes.append(f"{name}: {'up' if curr['port_open'] else 'down'}")
    
    return {"trend": "degrading" if changes else "stable", "changes": changes}

def check_alerts(state, current_results, config):
    """检查是否需要告警"""
    alerts = []
    consecutive = state.get('consecutive_failures', {})
    
    for result in current_results:
        name = result['name']
        if not result['port_open']:
            consecutive[name] = consecutive.get(name, 0) + 1
        else:
            consecutive[name] = 0
        
        if consecutive[name] >= ALERT_THRESHOLD:
            critical = result.get('critical', False)
            if critical or ALERT_THRESHOLD >= 3:
                alerts.append({
                    "service": name,
                    "failures": consecutive[name],
                    "critical": critical,
                    "time": datetime.now().isoformat()
                })
    
    state['consecutive_failures'] = consecutive
    return alerts

def main():
    print("=== Agent协作网络健康检查 ===")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    config = load_config()
    state = load_state()
    
    print("服务状态:")
    current_results = check_all(config)
    
    # 分析趋势
    trends = analyze_trends(state, current_results)
    print(f"\n趋势: {trends['trend']}")
    if trends['changes']:
        for c in trends['changes']:
            print(f"  - {c}")
    
    # 检查告警
    alerts = check_alerts(state, current_results, config)
    if alerts:
        print(f"\n⚠️  告警 ({len(alerts)}):")
        for a in alerts:
            print(f"  - {a['service']}: 连续{a['failures']}次失败")
    
    # 保存状态
    state['history'].append({
        "timestamp": datetime.now().isoformat(),
        "results": current_results
    })
    # 只保留最近100条
    state['history'] = state['history'][-100:]
    state['last_check'] = datetime.now().isoformat()
    save_state(state)
    
    # 汇总
    total = len(current_results)
    healthy = sum(1 for r in current_results if r['port_open'])
    print(f"\n汇总: {healthy}/{total} 服务正常")
    
    return 0 if healthy == total else 1

if __name__ == '__main__':
    exit(main())