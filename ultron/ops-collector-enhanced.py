#!/usr/bin/env python3
"""
智能运维助手 - 增强版监控系统采集器
采集系统指标 + OpenClaw服务状态 + 应用健康
"""

import psutil
import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional


class MetricCollector:
    """系统指标采集器"""
    
    def __init__(self):
        self.timestamp = datetime.now().isoformat()
    
    def cpu_metrics(self) -> Dict[str, Any]:
        """采集CPU指标"""
        return {
            "usage_percent": psutil.cpu_percent(interval=0.5),
            "per_cpu": psutil.cpu_percent(interval=0.5, percpu=True),
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
                if usage.total > 0:  # 过滤掉squashfs等
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
    
    def process_metrics(self) -> Dict[str, Any]:
        """采集进程TOP10 (CPU/内存)"""
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'num_threads']):
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
        
        # 按内存排序取TOP10
        processes.sort(key=lambda x: x.get('memory_percent', 0), reverse=True)
        top_mem = processes[:10]
        
        return {
            "top_cpu": [{"pid": p['pid'], "name": p['name'], "cpu": p['cpu_percent']} for p in top_cpu],
            "top_memory": [{"pid": p['pid'], "name": p['name'], "memory": p['memory_percent']} for p in top_mem],
            "total_processes": len(processes)
        }
    
    def service_checks(self) -> Dict[str, Any]:
        """服务健康检查"""
        critical_services = ['sshd', 'docker', 'gateway', 'cron', 'systemd']
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
    
    def openclaw_status(self) -> Dict[str, Any]:
        """OpenClaw服务状态"""
        status = {"gateway": "unknown", "browser": "unknown", "channels": []}
        
        # 检查Gateway进程
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'gateway' in ' '.join(cmdline).lower():
                    status['gateway'] = "running"
                    break
            except:
                pass
        
        if status['gateway'] == "unknown":
            # 检查端口
            for conn in psutil.net_connections():
                if conn.laddr.port == 18789:
                    status['gateway'] = "running"
                    break
        
        # 检查浏览器
        for proc in psutil.process_iter(['name']):
            try:
                if 'chrome' in proc.info['name'].lower() or 'chromium' in proc.info['name'].lower():
                    status['browser'] = "running"
                    break
            except:
                pass
        
        # 检查渠道
        channel_procs = {
            'dingtalk': 'clawdbot-dingtalk',
            'telegram': 'clawdbot-telegram',
            'discord': 'clawdbot-discord'
        }
        for channel, proc_name in channel_procs.items():
            for proc in psutil.process_iter(['name']):
                try:
                    if proc_name in proc.info['name']:
                        status['channels'].append(channel)
                        break
                except:
                    pass
        
        return status
    
    def docker_status(self) -> Dict[str, Any]:
        """Docker容器状态"""
        result = {"available": False, "containers": [], "images": 0}
        
        try:
            result['available'] = True
            # 获取容器列表
            subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}'], 
                         capture_output=True, timeout=5)
            # 简单检查
            result['containers'] = []
            for proc in psutil.process_iter(['name', 'status']):
                try:
                    if 'docker' in proc.info['name'].lower():
                        result['containers'].append({
                            "name": proc.info['name'],
                            "status": proc.info.get('status', 'unknown')
                        })
                except:
                    pass
        except FileNotFoundError:
            result['available'] = False
        except Exception as e:
            result['error'] = str(e)
        
        return result
    
    def cron_jobs(self) -> Dict[str, Any]:
        """Cron任务统计"""
        result = {"active": 0, "total": 0, "recent": []}
        
        try:
            # 检查OpenClaw cron任务
            proc = subprocess.run(['openclaw', 'cron', 'list'], 
                                capture_output=True, text=True, timeout=10)
            if proc.returncode == 0:
                lines = proc.stdout.strip().split('\n')
                result['total'] = len([l for l in lines if l.strip()])
        except:
            pass
        
        return result
    
    def connections_summary(self) -> Dict[str, Any]:
        """网络连接统计"""
        conns = psutil.net_connections()
        by_state = {}
        by_type = {}
        
        for conn in conns:
            # 按状态统计
            state = conn.status or 'UNKNOWN'
            by_state[state] = by_state.get(state, 0) + 1
            
            # 按类型统计
            type_name = 'TCP' if conn.type == 1 else ('UDP' if conn.type == 2 else 'Other')
            by_type[type_name] = by_type.get(type_name, 0) + 1
        
        return {
            "total": len(conns),
            "by_state": by_state,
            "by_type": by_type
        }
    
    def temperature_metrics(self) -> Dict[str, Any]:
        """温度指标 (如果可用)"""
        result = {"available": False}
        
        try:
            temps = psutil.sensors_temperatures()
            if temps:
                result['available'] = True
                result['readings'] = {}
                for name, entries in temps.items():
                    if entries:
                        result['readings'][name] = entries[0].current
        except:
            pass
        
        return result
    
    def battery_metrics(self) -> Dict[str, Any]:
        """电池状态 (如果可用)"""
        result = {"available": False}
        
        try:
            battery = psutil.sensors_battery()
            if battery:
                result['available'] = True
                result['percent'] = battery.percent
                result['charging'] = battery.is_charging
                result['time_left'] = battery.secsleft if battery.secsleft > 0 else None
        except:
            pass
        
        return result
    
    def collect_all(self) -> Dict[str, Any]:
        """采集所有指标"""
        return {
            "timestamp": self.timestamp,
            "cpu": self.cpu_metrics(),
            "memory": self.memory_metrics(),
            "disk": self.disk_metrics(),
            "network": self.network_metrics(),
            "processes": self.process_metrics(),
            "services": self.service_checks(),
            "openclaw": self.openclaw_status(),
            "docker": self.docker_status(),
            "cron": self.cron_jobs(),
            "connections": self.connections_summary(),
            "temperature": self.temperature_metrics(),
            "battery": self.battery_metrics()
        }


def check_alerts(data: Dict[str, Any]) -> List[str]:
    """基于指标生成告警"""
    alerts = []
    
    # 内存告警
    if data['memory']['percent'] > 90:
        alerts.append(f"[P1] 内存使用率 {data['memory']['percent']}% 超过90%")
    elif data['memory']['percent'] > 80:
        alerts.append(f"[P2] 内存使用率 {data['memory']['percent']}% 超过80%")
    
    # CPU告警
    if data['cpu']['usage_percent'] > 90:
        alerts.append(f"[P1] CPU使用率 {data['cpu']['usage_percent']}% 超过90%")
    elif data['cpu']['usage_percent'] > 80:
        alerts.append(f"[P2] CPU使用率 {data['cpu']['usage_percent']}% 超过80%")
    
    # 负载告警
    load_avg = data['cpu']['load_avg'][0]  # 1分钟负载
    cpu_count = psutil.cpu_count()
    if load_avg > cpu_count * 2:
        alerts.append(f"[P2] 负载 {load_avg} 超过 CPU核心数*2 ({cpu_count * 2})")
    
    # 磁盘告警 (排除snap等只读文件系统)
    for disk in data['disk']['disks']:
        # 跳过squashfs等只读文件系统
        if disk['fstype'] in ('squashfs', 'overlay'):
            continue
        if disk['percent'] > 90:
            alerts.append(f"[P1] 磁盘 {disk['mountpoint']} 使用率 {disk['percent']}% 超过90%")
        elif disk['percent'] > 80:
            alerts.append(f"[P2] 磁盘 {disk['mountpoint']} 使用率 {disk['percent']}% 超过80%")
    
    # OpenClaw服务告警
    if data['openclaw']['gateway'] != 'running':
        alerts.append(f"[P1] OpenClaw Gateway 未运行")
    
    # 连接数告警
    if data['connections']['total'] > 10000:
        alerts.append(f"[P3] 网络连接数 {data['connections']['total']} 过高")
    
    return alerts


def main():
    """主函数"""
    import sys
    
    collector = MetricCollector()
    data = collector.collect_all()
    
    # 输出JSON格式
    print(json.dumps(data, indent=2, default=str))
    
    # 告警检查
    alerts = check_alerts(data)
    if alerts:
        print("\n" + "=" * 50)
        print("⚠️  告警提醒:")
        for alert in alerts:
            print(f"  {alert}")
        print("=" * 50)
        # 如果有P1告警，以错误码退出
        p1_alerts = [a for a in alerts if a.startswith('[P1]')]
        if p1_alerts:
            sys.exit(2)


if __name__ == "__main__":
    main()