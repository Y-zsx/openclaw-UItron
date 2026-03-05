#!/usr/bin/env python3
"""
Agent生命周期状态追踪器 v2.0
记录Agent创建、运行、停止等事件
自动发现和监控Agent进程
"""

import json
import os
import subprocess
import psutil
import argparse
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
STATE_DEGRADED = "degraded"
STATE_RECOVERING = "recovering"

# Agent进程关键字
AGENT_KEYWORDS = [
    'agent_', 'ultron-', 'openclaw', 'orchestrator', 
    'workflow', 'monitor', 'lifecycle', 'federation'
]

def load_events():
    """加载历史事件"""
    if LIFECYCLE_DB.exists():
        with open(LIFECYCLE_DB, 'r') as f:
            return json.load(f)
    return {"events": [], "agents": {}, "last_scan": None}

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
    
    # 更新agents状态
    if event_type in [STATE_RUNNING, STATE_STARTING]:
        data["agents"][agent_id] = {
            "state": event_type,
            "last_seen": datetime.now().isoformat(),
            "details": details or {}
        }
    elif event_type in [STATE_STOPPED, STATE_FAILED]:
        if agent_id in data["agents"]:
            data["agents"][agent_id]["state"] = event_type
            data["agents"][agent_id]["last_seen"] = datetime.now().isoformat()
    
    # 保留最近1000条
    data["events"] = data["events"][-1000:]
    
    save_events(data)
    return event

def is_agent_process(proc):
    """判断是否是Agent进程"""
    try:
        pinfo = proc.info
        cmdline = pinfo.get('cmdline', [])
        if not cmdline:
            return False
            
        cmd_str = ' '.join(cmdline).lower()
        
        # 检查关键字
        for kw in AGENT_KEYWORDS:
            if kw in cmd_str:
                return True
                
        # 检查是否是python进程运行ultron相关脚本
        if 'python' in cmd_str and 'ultron' in cmd_str:
            return True
            
        return False
    except:
        return False

def get_agent_processes():
    """获取当前运行的Agent进程"""
    agents = {}
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_percent']):
        try:
            if is_agent_process(proc):
                pinfo = proc.info
                cmdline = pinfo.get('cmdline', [])
                
                # 从cmdline提取agent_id
                agent_id = "unknown"
                for arg in cmdline:
                    if 'agent' in arg.lower() or 'ultron' in arg.lower():
                        agent_id = arg.split('/')[-1].replace('.py', '')
                        break
                
                if len(cmdline) >= 2:
                    agent_id = cmdline[-1].replace('.py', '') or agent_id
                
                agents[agent_id] = {
                    "pid": pinfo.get('pid'),
                    "name": pinfo.get('name'),
                    "cmdline": ' '.join(cmdline[:3]),  # 前3个参数
                    "create_time": pinfo.get('create_time'),
                    "cpu_percent": pinfo.get('cpu_percent', 0),
                    "memory_percent": pinfo.get('memory_percent', 0),
                    "state": STATE_RUNNING,
                    "last_seen": datetime.now().isoformat()
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    return agents

def scan_and_track():
    """扫描并跟踪Agent进程"""
    data = load_events()
    current_agents = get_agent_processes()
    previous_agents = data.get("agents", {})
    
    # 检测新启动的Agent
    for agent_id, info in current_agents.items():
        if agent_id not in previous_agents:
            track_agent_event(agent_id, STATE_STARTING, {"pid": info.get("pid")})
            print(f"[+] 新Agent启动: {agent_id} (PID: {info.get('pid')})")
        else:
            # 更新状态
            data["agents"][agent_id] = info
    
    # 检测已停止的Agent
    for agent_id in previous_agents:
        if agent_id not in current_agents:
            track_agent_event(agent_id, STATE_STOPPED, {"pid": previous_agents[agent_id].get("pid")})
            print(f"[-] Agent已停止: {agent_id}")
    
    data["last_scan"] = datetime.now().isoformat()
    save_events(data)
    
    return current_agents

def get_agent_states():
    """获取当前Agent状态"""
    data = load_events()
    return data.get("agents", get_agent_processes())

def get_lifecycle_summary():
    """获取生命周期摘要"""
    data = load_events()
    
    summary = {
        "total_events": len(data["events"]),
        "active_agents": len(get_agent_processes()),
        "event_types": {},
        "recent_events": data["events"][-10:] if data["events"] else [],
        "last_scan": data.get("last_scan")
    }
    
    for event in data["events"]:
        etype = event.get("event_type", "unknown")
        summary["event_types"][etype] = summary["event_types"].get(etype, 0) + 1
    
    return summary

def main():
    parser = argparse.ArgumentParser(description="Agent生命周期追踪器")
    parser.add_argument("--scan", action="store_true", help="扫描并跟踪Agent进程")
    parser.add_argument("--status", action="store_true", help="显示状态")
    parser.add_argument("--watch", action="store_true", help="持续监控")
    
    args = parser.parse_args()
    
    if args.scan or args.watch:
        print("=== 扫描Agent进程 ===\n")
        agents = scan_and_track()
        print(f"\n共发现 {len(agents)} 个Agent进程")
        
    if args.status:
        print("=== Agent生命周期追踪 ===\n")
        
        summary = get_lifecycle_summary()
        print(f"总事件数: {summary['total_events']}")
        print(f"活跃Agent: {summary['active_agents']}")
        print(f"事件类型分布: {summary['event_types']}")
        
        if summary['last_scan']:
            print(f"最后扫描: {summary['last_scan']}")
        
        print("\n最近事件:")
        for event in summary["recent_events"]:
            print(f"  [{event['timestamp'][:19]}] {event['event_type']}: {event['agent_id']}")
    
    if not (args.scan or args.status or args.watch):
        # 默认显示状态
        print("=== Agent生命周期追踪 ===\n")
        summary = get_lifecycle_summary()
        print(f"总事件数: {summary['total_events']}")
        print(f"活跃Agent: {summary['active_agents']}")
        print(f"事件类型分布: {summary['event_types']}")
        
        print("\n最近事件:")
        for event in summary["recent_events"]:
            print(f"  [{event['timestamp'][:19]}] {event['event_type']}: {event['agent_id']}")

if __name__ == "__main__":
    main()