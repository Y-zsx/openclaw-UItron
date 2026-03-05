#!/usr/bin/env python3
"""
奥创智能运维 - 监控数据采集器
每5分钟采集系统指标，存储用于可视化分析
"""

import json
import os
import time
from datetime import datetime, timedelta

DATA_DIR = "/root/.openclaw/workspace/ultron/data"
HISTORY_FILE = f"{DATA_DIR}/system_metrics_history.json"

# 采集间隔 (秒)
COLLECTION_INTERVAL = 300  # 5分钟

def get_system_metrics():
    """获取系统指标"""
    metrics = {
        "timestamp": datetime.now().isoformat(),
        "load": get_load_avg(),
        "memory": get_memory_info(),
        "disk": get_disk_info(),
        "network": get_network_info(),
        "processes": get_process_info()
    }
    return metrics

def get_load_avg():
    """获取负载平均值"""
    try:
        with open('/proc/loadavg', 'r') as f:
            parts = f.read().split()
            return {
                "1m": float(parts[0]),
                "5m": float(parts[1]),
                "15m": float(parts[2])
            }
    except:
        return {"1m": 0, "5m": 0, "15m": 0}

def get_memory_info():
    """获取内存信息"""
    try:
        with open('/proc/meminfo', 'r') as f:
            lines = f.readlines()
            mem = {}
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(':')
                    value = int(parts[1])
                    if key in ['MemTotal', 'MemFree', 'MemAvailable', 'Buffers', 'Cached']:
                        mem[key] = value
            total = mem.get('MemTotal', 1)
            available = mem.get('MemAvailable', 0)
            return {
                "total_mb": round(total / 1024, 1),
                "used_mb": round((total - available) / 1024, 1),
                "available_mb": round(available / 1024, 1),
                "usage_pct": round((total - available) / total * 100, 1)
            }
    except:
        return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "usage_pct": 0}

def get_disk_info():
    """获取磁盘信息"""
    try:
        import subprocess
        result = subprocess.run(['df', '-B1', '/'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) >= 2:
            parts = lines[1].split()
            total = int(parts[1])
            used = int(parts[2])
            avail = int(parts[3])
            return {
                "total_gb": round(total / 1024 / 1024 / 1024, 2),
                "used_gb": round(used / 1024 / 1024 / 1024, 2),
                "available_gb": round(avail / 1024 / 1024 / 1024, 2),
                "usage_pct": round(used / total * 100, 1)
            }
    except:
        return {"total_gb": 0, "used_gb": 0, "available_gb": 0, "usage_pct": 0}

def get_network_info():
    """获取网络信息"""
    try:
        import subprocess
        result = subprocess.run(['cat', '/proc/net/dev'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        total_rx = 0
        total_tx = 0
        for line in lines[2:]:
            parts = line.split()
            if len(parts) >= 10:
                iface = parts[0].rstrip(':')
                if iface not in ['lo', 'docker0']:
                    total_rx += int(parts[1])
                    total_tx += int(parts[9])
        return {
            "rx_mb": round(total_rx / 1024 / 1024, 2),
            "tx_mb": round(total_tx / 1024 / 1024, 2)
        }
    except:
        return {"rx_mb": 0, "tx_mb": 0}

def get_process_info():
    """获取进程信息"""
    try:
        with open('/proc/stat', 'r') as f:
            lines = f.readlines()
            for line in lines:
                if line.startswith('procs_running'):
                    return {"running": int(line.split()[1])}
        return {"running": 0}
    except:
        return {"running": 0}

def load_history():
    """加载历史数据"""
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                return json.load(f)
        except:
            return []
    return []

def save_history(history):
    """保存历史数据"""
    os.makedirs(DATA_DIR, exist_ok=True)
    # 只保留最近24小时的数据 (288条，每5分钟一条)
    max_entries = 288
    history = history[-max_entries:]
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def collect_metrics():
    """采集并存储指标"""
    print(f"[{datetime.now().isoformat()}] 开始采集系统指标...")
    
    metrics = get_system_metrics()
    print(f"  Load: {metrics['load']['1m']:.2f}, Memory: {metrics['memory']['usage_pct']}%, Disk: {metrics['disk']['usage_pct']}%")
    
    history = load_history()
    history.append(metrics)
    save_history(history)
    
    print(f"  已存储 {len(history)} 条历史记录")
    return metrics

def get_stats_summary():
    """获取统计摘要"""
    history = load_history()
    if not history:
        return None
    
    recent = history[-12:]  # 最近1小时
    
    loads = [m['load']['1m'] for m in recent]
    mems = [m['memory']['usage_pct'] for m in recent]
    disks = [m['disk']['usage_pct'] for m in recent]
    
    return {
        "load_avg": round(sum(loads) / len(loads), 2) if loads else 0,
        "load_max": max(loads) if loads else 0,
        "memory_avg": round(sum(mems) / len(mems), 1) if mems else 0,
        "memory_max": max(mems) if mems else 0,
        "disk_avg": round(sum(disks) / len(disks), 1) if disks else 0,
        "disk_max": max(disks) if disks else 0,
        "data_points": len(history)
    }

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--stats":
        # 仅显示统计摘要
        stats = get_stats_summary()
        if stats:
            print(json.dumps(stats, indent=2))
        else:
            print("{}")
    else:
        # 采集指标
        collect_metrics()