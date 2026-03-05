#!/usr/bin/env python3
"""
智能运维助手 - 监控系统采集器
第27世: 实现监控系统采集器
"""

import psutil
import json
import time
from datetime import datetime
from typing import Dict, List, Any


class MetricCollector:
    """系统指标采集器"""
    
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
    
    def cpu_metrics(self) -> Dict[str, Any]:
        """采集CPU指标"""
        return {
            "usage_percent": psutil.cpu_percent(interval=1),
            "per_cpu": psutil.cpu_percent(interval=1, percpu=True),
            "load_avg": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else [0, 0, 0],
            "ctx_switches": psutil.cpu_stats().ctx_switches,
            "interrupts": psutil.cpu_stats().interrupts
        }
    
    def memory_metrics(self) -> Dict[str, Any]:
        """采集内存指标"""
        mem = psutil.virtual_memory()
        swap = psutil.swap_memory()
        return {
            "total": mem.total,
            "available": mem.available,
            "used": mem.used,
            "percent": mem.percent,
            "swap_total": swap.total,
            "swap_used": swap.used,
            "swap_percent": swap.percent
        }
    
    def disk_metrics(self) -> Dict[str, Any]:
        """采集磁盘指标"""
        disks = []
        for partition in psutil.disk_partitions():
            try:
                usage = psutil.disk_usage(partition.mountpoint)
                disks.append({
                    "device": partition.device,
                    "mountpoint": partition.mountpoint,
                    "fstype": partition.fstype,
                    "total": usage.total,
                    "used": usage.used,
                    "free": usage.free,
                    "percent": usage.percent
                })
            except PermissionError:
                continue
        return {"disks": disks}
    
    def network_metrics(self) -> Dict[str, Any]:
        """采集网络指标"""
        net = psutil.net_io_counters()
        return {
            "bytes_sent": net.bytes_sent,
            "bytes_recv": net.bytes_recv,
            "packets_sent": net.packets_sent,
            "packets_recv": net.packets_recv,
            "errin": net.errin,
            "errout": net.errout,
            "dropin": net.dropin,
            "dropout": net.dropout
        }
    
    def process_metrics(self) -> List[Dict[str, Any]]:
        """采集进程TOP10 (CPU/内存)"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                pinfo = proc.info
                if pinfo['cpu_percent'] is None:
                    pinfo['cpu_percent'] = 0
                if pinfo['memory_percent'] is None:
                    pinfo['memory_percent'] = 0
                processes.append(pinfo)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # 按CPU排序取TOP10
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        top_cpu = processes[:10]
        
        return {
            "top_cpu": top_cpu,
            "total_processes": len(processes)
        }
    
    def service_checks(self) -> Dict[str, Any]:
        """服务健康检查"""
        # 检查关键进程
        critical_services = ['sshd', 'docker', 'gateway', 'cron']
        service_status = {}
        
        for svc in critical_services:
            found = False
            for proc in psutil.process_iter(['name']):
                try:
                    if svc in proc.info['name'].lower():
                        found = True
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            service_status[svc] = "running" if found else "stopped"
        
        return service_status
    
    def collect_all(self) -> Dict[str, Any]:
        """采集所有指标"""
        return {
            "timestamp": self.timestamp,
            "cpu": self.cpu_metrics(),
            "memory": self.memory_metrics(),
            "disk": self.disk_metrics(),
            "network": self.network_metrics(),
            "processes": self.process_metrics(),
            "services": self.service_checks()
        }


def main():
    """主函数"""
    collector = MetricCollector()
    data = collector.collect_all()
    
    # 输出JSON格式
    print(json.dumps(data, indent=2, default=str))
    
    # 简单告警检查
    if data['memory']['percent'] > 90:
        print("\n⚠️ [P2] 内存使用率超过90%", file=__import__('sys').stderr)
    
    if data['cpu']['usage_percent'] > 90:
        print("\n⚠️ [P2] CPU使用率超过90%", file=__import__('sys').stderr)


if __name__ == "__main__":
    main()