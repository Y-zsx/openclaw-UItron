#!/usr/bin/env python3
"""
智能监控系统 - 第1世：全方位监控
功能：系统资源监控、进程服务监控、性能指标收集、自适应阈值
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# 配置
CONFIG_PATH = "/root/.openclaw/workspace/ultron/logs/monitor-config.json"
DATA_PATH = "/root/.openclaw/workspace/ultron/logs/metrics-history.json"
ALERT_PATH = "/root/.openclaw/workspace/ultron/logs/alerts.json"

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

@dataclass
class SystemMetrics:
    """系统指标"""
    timestamp: str
    cpu: Dict[str, Any]
    memory: Dict[str, Any]
    disk: Dict[str, Any]
    network: Dict[str, Any]
    processes: int
    services: Dict[str, str]

@dataclass
class Alert:
    """告警"""
    id: str
    timestamp: str
    level: str
    source: str
    message: str
    value: Optional[float]
    threshold: Optional[float]

class IntelligentMonitor:
    """智能监控系统"""
    
    def __init__(self):
        self.config = self._load_config()
        self.history: List[SystemMetrics] = []
        self.alerts: List[Alert] = []
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
    def _load_config(self) -> Dict:
        """加载配置"""
        default = {
            "cpu_threshold": 80,
            "memory_threshold": 85,
            "disk_threshold": 90,
            "process_threshold": 300,
            "check_interval": 60,
            "history_size": 1000,
            "services": ["openclaw", "nginx", "chromium", "cron"]
        }
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH) as f:
                    return {**default, **json.load(f)}
            except:
                pass
        return default
    
    def _save_config(self):
        """保存配置"""
        Path(CONFIG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            json.dump(self.config, f, indent=2)
    
    def get_cpu_metrics(self) -> Dict[str, Any]:
        """获取CPU指标"""
        try:
            with open('/proc/loadavg') as f:
                load = f.read().split()
            return {
                "load_1m": float(load[0]),
                "load_5m": float(load[1]),
                "load_15m": float(load[2]),
                "running_processes": int(load[3].split('/')[0]),
                "total_processes": int(load[3].split('/')[1])
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_memory_metrics(self) -> Dict[str, Any]:
        """获取内存指标"""
        try:
            with open('/proc/meminfo') as f:
                meminfo = f.read()
            
            def get_mem(key):
                lines = [l for l in meminfo.split('\n') if l.startswith(key)]
                return int(lines[0].split()[1]) / 1024 if lines else 0
            
            total = get_mem('MemTotal:')
            available = get_mem('MemAvailable:')
            used = total - available
            free = get_mem('MemFree:')
            buffers = get_mem('Buffers:')
            cached = get_mem('Cached:')
            
            return {
                "total_gb": round(total / 1024 / 1024, 2),
                "available_gb": round(available / 1024 / 1024, 2),
                "used_gb": round(used / 1024 / 1024, 2),
                "free_gb": round(free / 1024 / 1024, 2),
                "buffers_gb": round(buffers / 1024 / 1024, 2),
                "cached_gb": round(cached / 1024 / 1024, 2),
                "usage_percent": round((used / total) * 100, 1) if total > 0 else 0
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_disk_metrics(self) -> Dict[str, Any]:
        """获取磁盘指标"""
        try:
            result = subprocess.run(['df', '-B1', '/'], capture_output=True, text=True)
            parts = result.stdout.strip().split('\n')[1].split()
            return {
                "total_bytes": int(parts[1]),
                "used_bytes": int(parts[2]),
                "available_bytes": int(parts[3]),
                "usage_percent": int(parts[4].replace('%', '')),
                "mount_point": parts[5]
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_network_metrics(self) -> Dict[str, Any]:
        """获取网络指标"""
        try:
            result = subprocess.run(['ss', '-s'], capture_output=True, text=True)
            lines = result.stdout.split('\n')
            
            tcp_est = 0
            tcp_timewait = 0
            for line in lines:
                if 'established' in line:
                    tcp_est = int(line.split()[0])
                if 'timewait' in line:
                    tcp_timewait = int(line.split()[0])
            
            return {
                "tcp_established": tcp_est,
                "tcp_timewait": tcp_timewait,
                "listening_ports": len(subprocess.run(['ss', '-tln'], capture_output=True, text=True).stdout.split('\n')) - 2
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_process_count(self) -> int:
        """获取进程数"""
        try:
            return len(subprocess.run(['ps', 'aux'], capture_output=True, text=True).stdout.split('\n')) - 1
        except:
            return 0
    
    def check_services(self) -> Dict[str, str]:
        """检查服务状态"""
        services = self.config.get("services", [])
        status = {}
        for svc in services:
            result = subprocess.run(['pgrep', '-f', svc], capture_output=True)
            status[svc] = "running" if result.returncode == 0 else "stopped"
        return status
    
    def collect_metrics(self) -> SystemMetrics:
        """收集所有指标"""
        return SystemMetrics(
            timestamp=datetime.now().isoformat(),
            cpu=self.get_cpu_metrics(),
            memory=self.get_memory_metrics(),
            disk=self.get_disk_metrics(),
            network=self.get_network_metrics(),
            processes=self.get_process_count(),
            services=self.check_services()
        )
    
    def check_thresholds(self, metrics: SystemMetrics) -> List[Alert]:
        """检查阈值并生成告警"""
        alerts = []
        alert_id = 0
        
        # CPU检查
        if metrics.cpu.get('load_1m', 0) > self.config['cpu_threshold']:
            alerts.append(Alert(
                id=f"cpu_{alert_id}",
                timestamp=metrics.timestamp,
                level=AlertLevel.WARNING.value,
                source="cpu",
                message=f"CPU负载过高: {metrics.cpu['load_1m']}",
                value=metrics.cpu['load_1m'],
                threshold=self.config['cpu_threshold']
            ))
        
        # 内存检查
        if metrics.memory.get('usage_percent', 0) > self.config['memory_threshold']:
            alerts.append(Alert(
                id=f"mem_{alert_id}",
                timestamp=metrics.timestamp,
                level=AlertLevel.WARNING.value,
                source="memory",
                message=f"内存使用率过高: {metrics.memory['usage_percent']}%",
                value=metrics.memory['usage_percent'],
                threshold=self.config['memory_threshold']
            ))
        
        # 磁盘检查
        if metrics.disk.get('usage_percent', 0) > self.config['disk_threshold']:
            alerts.append(Alert(
                id=f"disk_{alert_id}",
                timestamp=metrics.timestamp,
                level=AlertLevel.CRITICAL.value,
                source="disk",
                message=f"磁盘使用率过高: {metrics.disk['usage_percent']}%",
                value=metrics.disk['usage_percent'],
                threshold=self.config['disk_threshold']
            ))
        
        # 进程数检查
        if metrics.processes > self.config['process_threshold']:
            alerts.append(Alert(
                id=f"proc_{alert_id}",
                timestamp=metrics.timestamp,
                level=AlertLevel.WARNING.value,
                source="processes",
                message=f"进程数过多: {metrics.processes}",
                value=metrics.processes,
                threshold=self.config['process_threshold']
            ))
        
        # 服务检查
        for svc, status in metrics.services.items():
            if status == "stopped":
                alerts.append(Alert(
                    id=f"svc_{alert_id}",
                    timestamp=metrics.timestamp,
                    level=AlertLevel.CRITICAL.value,
                    source="service",
                    message=f"服务停止: {svc}",
                    value=None,
                    threshold=None
                ))
        
        return alerts
    
    def save_metrics(self, metrics: SystemMetrics):
        """保存指标到历史"""
        self.history.append(metrics)
        
        # 限制历史大小
        max_size = self.config.get('history_size', 1000)
        if len(self.history) > max_size:
            self.history = self.history[-max_size:]
        
        # 保存到文件
        Path(DATA_PATH).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "metrics": [asdict(m) for m in self.history],
            "last_update": datetime.now().isoformat()
        }
        with open(DATA_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_alerts(self, alerts: List[Alert]):
        """保存告警"""
        if not alerts:
            return
        
        self.alerts.extend(alerts)
        
        # 只保留最近100条告警
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        Path(ALERT_PATH).parent.mkdir(parents=True, exist_ok=True)
        data = {
            "alerts": [asdict(a) for a in self.alerts],
            "last_update": datetime.now().isoformat()
        }
        with open(ALERT_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    
    def get_summary(self) -> Dict:
        """获取监控摘要"""
        if not self.history:
            return {"status": "no_data"}
        
        latest = self.history[-1]
        return {
            "timestamp": latest.timestamp,
            "cpu": latest.cpu,
            "memory": latest.memory,
            "disk": latest.disk,
            "processes": latest.processes,
            "services": latest.services,
            "history_size": len(self.history)
        }
    
    def get_trends(self, hours: int = 1) -> Dict:
        """获取趋势数据"""
        if len(self.history) < 2:
            return {"status": "insufficient_data"}
        
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [m for m in self.history if datetime.fromisoformat(m.timestamp) > cutoff]
        
        if len(recent) < 2:
            return {"status": "insufficient_data"}
        
        # 计算趋势
        cpu_loads = [m.cpu.get('load_1m', 0) for m in recent]
        mem_usages = [m.memory.get('usage_percent', 0) for m in recent]
        disk_usages = [m.disk.get('usage_percent', 0) for m in recent]
        
        return {
            "period_hours": hours,
            "data_points": len(recent),
            "cpu": {
                "avg": round(sum(cpu_loads) / len(cpu_loads), 2),
                "max": max(cpu_loads),
                "min": min(cpu_loads)
            },
            "memory": {
                "avg": round(sum(mem_usages) / len(mem_usages), 1),
                "max": max(mem_usages),
                "min": min(mem_usages)
            },
            "disk": {
                "avg": round(sum(disk_usages) / len(disk_usages), 1),
                "max": max(disk_usages),
                "min": min(disk_usages)
            }
        }


# CLI接口
def main():
    import argparse
    parser = argparse.ArgumentParser(description='智能监控系统')
    parser.add_argument('action', choices=['collect', 'summary', 'trends', 'alerts'], 
                        help='操作类型')
    parser.add_argument('--hours', type=int, default=1, help='趋势分析小时数')
    args = parser.parse_args()
    
    monitor = IntelligentMonitor()
    
    if args.action == 'collect':
        metrics = monitor.collect_metrics()
        alerts = monitor.check_thresholds(metrics)
        monitor.save_metrics(metrics)
        monitor.save_alerts(alerts)
        
        print(f"✅ 指标收集完成 - {metrics.timestamp}")
        print(f"  CPU负载: {metrics.cpu.get('load_1m', 0)}")
        print(f"  内存: {metrics.memory.get('usage_percent', 0)}%")
        print(f"  磁盘: {metrics.disk.get('usage_percent', 0)}%")
        print(f"  进程: {metrics.processes}")
        
        if alerts:
            print(f"\n⚠️  告警: {len(alerts)}个")
            for a in alerts:
                print(f"  [{a.level}] {a.message}")
        else:
            print("\n✅ 无告警")
    
    elif args.action == 'summary':
        summary = monitor.get_summary()
        print(json.dumps(summary, indent=2))
    
    elif args.action == 'trends':
        trends = monitor.get_trends(args.hours)
        print(json.dumps(trends, indent=2))
    
    elif args.action == 'alerts':
        if os.path.exists(ALERT_PATH):
            with open(ALERT_PATH) as f:
                print(f.read())
        else:
            print("无告警记录")

if __name__ == '__main__':
    main()