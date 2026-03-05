#!/usr/bin/env python3
"""
监听Agent (Monitor Agent)
职责: 持续监控外部状态变化

接口:
- start_monitoring(config) → stream events
- stop_monitoring() → void
- get_status() → AgentStatus
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path("/root/.openclaw/workspace/ultron-workflow/agents")
STATE_FILE = AGENT_DIR / "monitor-state.json"
LOG_FILE = AGENT_DIR / "monitor.log"


def load_state():
    """加载Agent状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "status": "idle",
        "monitoring_config": None,
        "last_heartbeat": None,
        "events": [],
        "start_time": None
    }


def save_state(state):
    """保存Agent状态"""
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def log(msg):
    """日志记录"""
    timestamp = datetime.now().isoformat()
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(LOG_FILE, 'a') as f:
        f.write(log_msg + '\n')


def start_monitoring(config):
    """启动监控"""
    state = load_state()
    
    # 验证配置
    required_fields = ['type', 'interval']
    for field in required_fields:
        if field not in config:
            return {"status": "failed", "error": f"缺少必需字段: {field}"}
    
    # 设置监控配置
    state['status'] = 'monitoring'
    state['monitoring_config'] = config
    state['start_time'] = datetime.now().isoformat()
    state['last_heartbeat'] = datetime.now().isoformat()
    state['events'] = []
    
    save_state(state)
    log(f"✅ 监控已启动: {config['type']}, 间隔: {config.get('interval', 60)}秒")
    
    return {
        "status": "success",
        "message": f"监控已启动: {config['type']}",
        "config": config
    }


def stop_monitoring():
    """停止监控"""
    state = load_state()
    
    if state['status'] != 'monitoring':
        return {"status": "success", "message": "监控未启动"}
    
    state['status'] = 'idle'
    state['monitoring_config'] = None
    state['last_heartbeat'] = datetime.now().isoformat()
    
    save_state(state)
    log("✅ 监控已停止")
    
    return {"status": "success", "message": "监控已停止"}


def get_status():
    """获取Agent状态"""
    state = load_state()
    
    return {
        "agent_id": "agent-monitor",
        "type": "monitor",
        "status": state['status'],
        "monitoring_config": state['monitoring_config'],
        "last_heartbeat": state['last_heartbeat'],
        "event_count": len(state['events']),
        "start_time": state.get('start_time')
    }


def record_event(event_type, data):
    """记录监控事件"""
    state = load_state()
    
    event = {
        "type": event_type,
        "data": data,
        "timestamp": datetime.now().isoformat()
    }
    
    state['events'].append(event)
    
    # 只保留最近100条事件
    if len(state['events']) > 100:
        state['events'] = state['events'][-100:]
    
    state['last_heartbeat'] = datetime.now().isoformat()
    save_state(state)
    
    return event


def get_events(limit=10):
    """获取最近事件"""
    state = load_state()
    return state['events'][-limit:]


# CLI 接口
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "用法: monitor-agent.py <command> [args...]",
            "commands": ["start", "stop", "status", "events"]
        }, indent=2))
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "start":
        if len(sys.argv) < 3:
            print(json.dumps({"error": "用法: monitor-agent.py start <config_json>"}))
            sys.exit(1)
        config = json.loads(sys.argv[2])
        result = start_monitoring(config)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif cmd == "stop":
        result = stop_monitoring()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif cmd == "status":
        result = get_status()
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif cmd == "events":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        result = get_events(limit)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif cmd == "record":
        # 用于测试: record event
        if len(sys.argv) < 4:
            print(json.dumps({"error": "用法: monitor-agent.py record <type> <data_json>"}))
            sys.exit(1)
        event_type = sys.argv[2]
        data = json.loads(sys.argv[3])
        result = record_event(event_type, data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    else:
        print(json.dumps({"error": f"未知命令: {cmd}"}))
        sys.exit(1)