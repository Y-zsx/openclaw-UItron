#!/usr/bin/env python3
"""
Agent生命周期状态追踪器
记录Agent创建、运行、停止等事件
"""

import json
import os
import subprocess
import psutil
from datetime import datetime
from pathlib import Path

STATE_DIR = Path("/root/.openclaw/workspace/ultron/state")
STATE_DIR.mkdir(parents=True, exist_ok=True)

LIFECYCLE_DB = STATE_DIR / "lifecycle_events.json"

# Agent状态
STATE_STARTING = "starting"
STATE_RUNNING = "running"
STATE_IDLE = "idle"
STATE_STOPPED = "stopped"
STATE_FAILED = "failed"

def load_events():
    """加载历史事件"""
    if LIFECYCLE_DB.exists():
        with open(LIFECYCLE_DB, 'r') as f:
            return json.load(f)
    return {"events": [], "agents": {}}

def save_events(data):
    """保存事件"""
    with open(LIFECYCLE_DB, 'w') as f:
        json.dump(data, f, indent=2)

def track_agent_event(agent_id, event_type, details=None):
    """记录Agent事件"""
    data = load_events()
    
    event = {
        "timestamp": datetime.now().isoformat(),
        "agent_id": agent_id,
        "event_type": event_type,
        "details": details or {}
    }
    
    data["events"].append(event)
    
    # 保留最近1000条
    data["events"] = data["events"][-1000:]
    
    save_events(data)
    return event

def get_agent_states():
    """获取当前Agent状态"""
    data = load_events()
    states = {}
    
    # 从进程推断状态
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            pinfo = proc.info
            cmdline = pinfo.get('cmdline', [])
            if cmdline:
                cmd_str = ' '.join(cmdline)
                if 'openclaw' in cmd_str or 'ultron' in cmd_str:
                    agent_id = cmdline[0] if cmdline else "unknown"
                    states[agent_id] = {
                        "pid": pinfo.get('pid'),
                        "state": STATE_RUNNING,
                        "last_seen": datetime.now().isoformat()
                    }
        except:
            pass
    
    return states

def get_lifecycle_summary():
    """获取生命周期摘要"""
    data = load_events()
    
    summary = {
        "total_events": len(data["events"]),
        "event_types": {},
        "recent_events": data["events"][-10:] if data["events"] else []
    }
    
    for event in data["events"]:
        etype = event.get("event_type", "unknown")
        summary["event_types"][etype] = summary["event_types"].get(etype, 0) + 1
    
    return summary

if __name__ == "__main__":
    print("=== Agent生命周期追踪 ===\n")
    
    summary = get_lifecycle_summary()
    print(f"总事件数: {summary['total_events']}")
    print(f"事件类型分布: {summary['event_types']}")
    
    print("\n最近事件:")
    for event in summary["recent_events"]:
        print(f"  [{event['timestamp']}] {event['event_type']}: {event['agent_id']}")