#!/usr/bin/env python3
"""
系统性能监控报告生成器
生成系统性能快照并保存为报告
"""

import json
import psutil
import os
from datetime import datetime

REPORT_PATH = "/root/.openclaw/workspace/ultron/data/performance_report.json"

def get_performance_snapshot():
    """获取性能快照"""
    cpu = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    network = psutil.net_io_counters()
    
    # 服务健康检查
    services = {
        "decision-engine": ("localhost", 18120),
        "automation": ("localhost", 18128),
        "workflow": ("localhost", 18100),
        "agent-executor": ("localhost", 8096),
        "agent-network": ("localhost", 18150),
    }
    
    service_status = {}
    for name, (host, port) in services.items():
        try:
            import socket
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            service_status[name] = "healthy" if result == 0 else "down"
        except:
            service_status[name] = "unknown"
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "system": {
            "cpu_percent": cpu,
            "memory_percent": memory.percent,
            "memory_available_gb": round(memory.available / (1024**3), 2),
            "disk_percent": disk.percent,
            "disk_free_gb": round(disk.free / (1024**3), 2),
        },
        "network": {
            "bytes_sent": network.bytes_sent,
            "bytes_recv": network.bytes_recv,
            "packets_sent": network.packets_sent,
            "packets_recv": network.packets_recv,
        },
        "services": service_status,
        "overall_health": "healthy" if all(s != "down" for s in service_status.values()) else "degraded"
    }

def main():
    snapshot = get_performance_snapshot()
    
    # 确保目录存在
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    
    # 读取历史报告
    try:
        with open(REPORT_PATH, 'r') as f:
            history = json.load(f)
    except:
        history = {"reports": []}
    
    # 添加新报告
    history["reports"].append(snapshot)
    
    # 保留最近100条
    history["reports"] = history["reports"][-100:]
    
    # 保存
    with open(REPORT_PATH, 'w') as f:
        json.dump(history, f, indent=2)
    
    print(f"性能报告已生成: {REPORT_PATH}")
    print(f"系统健康状态: {snapshot['overall_health']}")
    print(f"CPU: {snapshot['system']['cpu_percent']}% | 内存: {snapshot['system']['memory_percent']}% | 磁盘: {snapshot['system']['disk_percent']}%")
    
    return snapshot

if __name__ == "__main__":
    main()
