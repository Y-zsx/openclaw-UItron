#!/usr/bin/env python3
"""
Dashboard自动刷新服务 (V2增强版)
提供API控制Dashboard数据的自动刷新
"""
import os, json, subprocess, time, threading
from datetime import datetime
from flask import Flask, jsonify, request

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/dashboard_autorefresh.log'
DASHBOARD_DATA = f'{WORKSPACE}/ultron-workflow/logs/dashboard_data.json'
CONFIG_FILE = f'{WORKSPACE}/ultron-workflow/logs/autorefresh_config.json'

app = Flask(__name__)

# 全局状态
refresh_state = {
    'running': False,
    'interval': 30,  # 秒
    'last_refresh': None,
    'refresh_count': 0,
    'error_count': 0,
    'thread': None,
    'stop_event': None
}

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(f"[autorefresh] {msg}")

def load_config():
    """加载配置"""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {'interval': 30, 'enabled_dashboards': ['ops', 'health', 'scheduler']}

def save_config(config):
    """保存配置"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def refresh_all_dashboards():
    """刷新所有Dashboard数据"""
    global refresh_state
    
    log('开始刷新所有Dashboard数据...')
    refresh_state['last_refresh'] = datetime.now().isoformat()
    
    # 1. 调用 dashboard_aggregator
    try:
        result = subprocess.run(
            ['python3', f'{WORKSPACE}/ultron-workflow/modules/dashboard_aggregator.py'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            log(f'aggregator失败: {result.stderr}')
            refresh_state['error_count'] += 1
            return False
    except Exception as e:
        log(f"调用aggregator异常: {e}")
        refresh_state['error_count'] += 1
        return False
    
    # 2. 刷新其他Dashboard数据
    dashboards_to_refresh = [
        ('health', f'{WORKSPACE}/ultron-workflow/monitoring/health_check_dashboard.py'),
        ('scheduler', f'{WORKSPACE}/ultron-workflow/agents/queue_dashboard.py'),
    ]
    
    for name, script in dashboards_to_refresh:
        if os.path.exists(script):
            try:
                subprocess.run(
                    ['python3', script],
                    capture_output=True, text=True, timeout=20
                )
            except:
                pass
    
    refresh_state['refresh_count'] += 1
    log(f'Dashboard刷新完成 (第{refresh_state["refresh_count"]}次)')
    return True

def refresh_loop(interval, stop_event):
    """刷新循环"""
    while not stop_event.is_set():
        refresh_all_dashboards()
        # 等待间隔或检查停止事件
        for _ in range(interval):
            if stop_event.is_set():
                break
            time.sleep(1)

def start_auto_refresh(interval=30):
    """启动自动刷新"""
    global refresh_state
    
    if refresh_state['running']:
        return {'status': 'already_running', 'interval': refresh_state['interval']}
    
    refresh_state['interval'] = interval
    refresh_state['stop_event'] = threading.Event()
    refresh_state['thread'] = threading.Thread(target=refresh_loop, args=(interval, refresh_state['stop_event']))
    refresh_state['thread'].daemon = True
    refresh_state['thread'].start()
    refresh_state['running'] = True
    
    # 保存配置
    config = load_config()
    config['interval'] = interval
    save_config(config)
    
    log(f'自动刷新已启动 (间隔{interval}秒)')
    return {'status': 'started', 'interval': interval}

def stop_auto_refresh():
    """停止自动刷新"""
    global refresh_state
    
    if not refresh_state['running']:
        return {'status': 'not_running'}
    
    refresh_state['stop_event'].set()
    refresh_state['thread'].join(timeout=5)
    refresh_state['running'] = False
    refresh_state['stop_event'] = None
    refresh_state['thread'] = None
    
    log('自动刷新已停止')
    return {'status': 'stopped'}

# ========== API 端点 ==========

@app.route('/api/status', methods=['GET'])
def get_status():
    """获取自动刷新状态"""
    return jsonify({
        'running': refresh_state['running'],
        'interval': refresh_state['interval'],
        'last_refresh': refresh_state['last_refresh'],
        'refresh_count': refresh_state['refresh_count'],
        'error_count': refresh_state['error_count']
    })

@app.route('/api/start', methods=['POST'])
def start_refresh():
    """启动自动刷新"""
    interval = request.json.get('interval', 30) if request.json else 30
    return jsonify(start_auto_refresh(interval))

@app.route('/api/stop', methods=['POST'])
def stop_refresh():
    """停止自动刷新"""
    return jsonify(stop_auto_refresh())

@app.route('/api/refresh', methods=['POST'])
def manual_refresh():
    """手动触发刷新"""
    success = refresh_all_dashboards()
    return jsonify({
        'success': success,
        'refresh_count': refresh_state['refresh_count'],
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/config', methods=['GET', 'POST'])
def config_handler():
    """配置管理"""
    if request.method == 'GET':
        return jsonify(load_config())
    
    # POST - 更新配置
    config = request.json
    save_config(config)
    
    # 如果运行中，更新间隔
    if refresh_state['running']:
        stop_auto_refresh()
        start_auto_refresh(config.get('interval', 30))
    
    return jsonify({'status': 'updated', 'config': config})

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'dashboard_autorefresh'})

if __name__ == '__main__':
    # 尝试使用闲置端口
    import socket
    port = 18208
    for p in range(18208, 18220):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('0.0.0.0', p))
            s.close()
            port = p
            break
        except:
            continue
    
    log(f'Dashboard自动刷新服务启动在端口 {port}')
    
    # 自动启动刷新
    config = load_config()
    start_auto_refresh(config.get('interval', 30))
    
    app.run(host='0.0.0.0', port=port, debug=False)