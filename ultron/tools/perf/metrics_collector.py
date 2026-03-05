#!/usr/bin/env python3
"""
Metrics采集器 - 定期采集系统指标并发送到日志聚合系统
"""
import json
import time
import requests
import psutil
from datetime import datetime

LOG_API = "http://localhost:8091"
METRICS_INTERVAL = 30  # 30秒采集一次

def get_system_metrics():
    """获取系统指标"""
    cpu_percent = psutil.cpu_percent(interval=1, percpu=True)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage('/')
    net = psutil.net_io_counters()
    
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "avg_percent": sum(cpu_percent) / len(cpu_percent),
            "per_cpu": cpu_percent,
            "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0]
        },
        "memory": {
            "total_mb": mem.total / 1024 / 1024,
            "used_mb": mem.used / 1024 / 1024,
            "percent": mem.percent
        },
        "disk": {
            "total_gb": disk.total / 1024 / 1024 / 1024,
            "used_gb": disk.used / 1024 / 1024 / 1024,
            "percent": disk.percent
        },
        "network": {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv
        }
    }

def send_to_log_aggregator(metrics):
    """发送指标到日志聚合系统"""
    try:
        # 模拟Agent请求记录
        for service in ['api-gateway', 'service-mesh', 'agent-orchestrator', 'workflow-engine', 'agent-deployer']:
            requests.post(f"{LOG_API}/agents/record", json={
                "agent_id": service,
                "latency_ms": metrics['cpu']['avg_percent'] * 10,  # 模拟延迟
                "error": metrics['cpu']['avg_percent'] > 80
            }, timeout=2)
    except Exception as e:
        print(f"发送失败: {e}")

def main():
    print(f"Metrics采集器启动 - 每{METRICS_INTERVAL}秒采集一次")
    print(f"日志API: {LOG_API}")
    
    while True:
        try:
            metrics = get_system_metrics()
            print(f"[{metrics['timestamp']}] CPU: {metrics['cpu']['avg_percent']:.1f}%, "
                  f"内存: {metrics['memory']['percent']:.1f}%, "
                  f"磁盘: {metrics['disk']['percent']:.1f}%")
            
            # 发送到日志聚合
            send_to_log_aggregator(metrics)
            
        except Exception as e:
            print(f"采集错误: {e}")
        
        time.sleep(METRICS_INTERVAL)

if __name__ == '__main__':
    main()