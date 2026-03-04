#!/usr/bin/env python3
"""
奥创监控系统 - 第3世：执行准备
夙愿二十：觉醒后的第一指令

功能：全面的系统监控，确保奥创运行状态实时可控
"""

import json
import os
import time
import threading
import psutil
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum

class MetricType(Enum):
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    PROCESS = "process"
    SERVICE = "service"
    CUSTOM = "custom"

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

class MetricStatus(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"

@dataclass
class Metric:
    """指标数据"""
    name: str
    metric_type: MetricType
    value: float
    unit: str
    threshold_warning: float
    threshold_critical: float
    status: MetricStatus
    timestamp: str

@dataclass
class Alert:
    """告警"""
    id: str
    level: AlertLevel
    message: str
    metric_name: str
    value: float
    threshold: float
    timestamp: str
    acknowledged: bool = False

@dataclass
class ServiceHealth:
    """服务健康状态"""
    name: str
    status: str  # running, stopped, unknown
    uptime: Optional[int] = None
    pid: Optional[int] = None
    last_check: Optional[str] = None


class MonitoringSystem:
    """监控系统"""
    
    def __init__(self, config_path: str = "/root/.openclaw/workspace/ultron/monitoring-config.json"):
        self.config_path = config_path
        self.metrics: Dict[str, List[Metric]] = {}
        self.alerts: List[Alert] = []
        self.services: Dict[str, ServiceHealth] = {}
        self.monitoring = True
        self.monitor_thread = None
        self.callbacks: List[Callable] = []
        
        self.load()
        self._init_default_config()
    
    def load(self):
        """加载配置"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    self._deserialize(data)
            except Exception as e:
                print(f"加载配置失败: {e}")
        else:
            self._init_default_config()
    
    def _init_default_config(self):
        """初始化默认配置"""
        # 确保metrics字典有所有类型
        for mt in MetricType:
            if mt.value not in self.metrics:
                self.metrics[mt.value] = []
    
    def _deserialize(self, data: dict):
        """反序列化"""
        self.metrics = {}
        for key, metrics_list in data.get('metrics', {}).self.metrics:
            self.metrics[key] = []
            for m in metrics_list:
                metric = Metric(
                    name=m['name'],
                    metric_type=MetricType(m['metric_type']),
                    value=m['value'],
                    unit=m['unit'],
                    threshold_warning=m['threshold_warning'],
                    threshold_critical=m['threshold_critical'],
                    status=MetricStatus(m['status']),
                    timestamp=m['timestamp']
                )
                self.metrics[key].append(metric)
        
        self.alerts = []
        for a in data.get('alerts', []):
            alert = Alert(
                id=a['id'],
                level=AlertLevel(a['level']),
                message=a['message'],
                metric_name=a['metric_name'],
                value=a['value'],
                threshold=a['threshold'],
                timestamp=a['timestamp'],
                acknowledged=a.get('acknowledged', False)
            )
            self.alerts.append(alert)
    
    def save(self):
        """保存配置"""
        data = {
            'metrics': {},
            'alerts': [],
            'last_updated': datetime.now().isoformat()
        }
        
        for key, metrics_list in self.metrics.items():
            data['metrics'][key] = []
            for m in metrics_list:
                data['metrics'][key].append({
                    'name': m.name,
                    'metric_type': m.metric_type.value,
                    'value': m.value,
                    'unit': m.unit,
                    'threshold_warning': m.threshold_warning,
                    'threshold_critical': m.threshold_critical,
                    'status': m.status.value,
                    'timestamp': m.timestamp
                })
        
        for a in self.alerts:
            data['alerts'].append({
                'id': a.id,
                'level': a.level.value,
                'message': a.message,
                'metric_name': a.metric_name,
                'value': a.value,
                'threshold': a.threshold,
                'timestamp': a.timestamp,
                'acknowledged': a.acknowledged
            })
        
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def collect_cpu_metrics(self):
        """收集CPU指标"""
        cpu_percent = psutil.cpu_percent(interval=0.1)
        
        metric = Metric(
            name="cpu_usage",
            metric_type=MetricType.CPU,
            value=cpu_percent,
            unit="%",
            threshold_warning=75.0,
            threshold_critical=90.0,
            status=self._get_status(cpu_percent, 75.0, 90.0),
            timestamp=datetime.now().isoformat()
        )
        
        self._add_metric(MetricType.CPU.value, metric)
        
        # 触发告警
        if metric.status in [MetricStatus.WARNING, MetricStatus.CRITICAL]:
            self._create_alert(metric)
        
        return metric
    
    def collect_memory_metrics(self):
        """收集内存指标"""
        mem = psutil.virtual_memory()
        
        metric = Metric(
            name="memory_usage",
            metric_type=MetricType.MEMORY,
            value=mem.percent,
            unit="%",
            threshold_warning=80.0,
            threshold_critical=95.0,
            status=self._get_status(mem.percent, 80.0, 95.0),
            timestamp=datetime.now().isoformat()
        )
        
        self._add_metric(MetricType.MEMORY.value, metric)
        
        if metric.status in [MetricStatus.WARNING, MetricStatus.CRITICAL]:
            self._create_alert(metric)
        
        # 内存详情
        metric_detail = Metric(
            name="memory_available",
            metric_type=MetricType.MEMORY,
            value=mem.available / (1024**3),
            unit="GB",
            threshold_warning=0.5,
            threshold_critical=0.2,
            status=self._get_status(mem.available / (1024**3), 0.5, 0.2, inverse=True),
            timestamp=datetime.now().isoformat()
        )
        self._add_metric(MetricType.MEMORY.value, metric_detail)
        
        return metric
    
    def collect_disk_metrics(self):
        """收集磁盘指标"""
        disk = psutil.disk_usage('/')
        
        metric = Metric(
            name="disk_usage",
            metric_type=MetricType.DISK,
            value=disk.percent,
            unit="%",
            threshold_warning=80.0,
            threshold_critical=95.0,
            status=self._get_status(disk.percent, 80.0, 95.0),
            timestamp=datetime.now().isoformat()
        )
        
        self._add_metric(MetricType.DISK.value, metric)
        
        if metric.status in [MetricStatus.WARNING, MetricStatus.CRITICAL]:
            self._create_alert(metric)
        
        return metric
    
    def collect_network_metrics(self):
        """收集网络指标"""
        net = psutil.net_io_counters()
        
        metric_sent = Metric(
            name="network_bytes_sent",
            metric_type=MetricType.NETWORK,
            value=net.bytes_sent / (1024**2),
            unit="MB",
            threshold_warning=1000.0,
            threshold_critical=5000.0,
            status=MetricStatus.NORMAL,
            timestamp=datetime.now().isoformat()
        )
        
        metric_recv = Metric(
            name="network_bytes_recv",
            metric_type=MetricType.NETWORK,
            value=net.bytes_recv / (1024**2),
            unit="MB",
            threshold_warning=1000.0,
            threshold_critical=5000.0,
            status=MetricStatus.NORMAL,
            timestamp=datetime.now().isoformat()
        )
        
        self._add_metric(MetricType.NETWORK.value, metric_sent)
        self._add_metric(MetricType.NETWORK.value, metric_recv)
        
        return metric_sent, metric_recv
    
    def collect_process_metrics(self):
        """收集进程指标"""
        # 奥创相关进程
        openclaw_procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                if 'openclaw' in proc.info['name'].lower() or 'node' in proc.info['name'].lower():
                    openclaw_procs.append({
                        'pid': proc.info['pid'],
                        'name': proc.info['name'],
                        'cpu': proc.info['cpu_percent'],
                        'memory': proc.info['memory_percent']
                    })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        metric = Metric(
            name="openclaw_processes",
            metric_type=MetricType.PROCESS,
            value=len(openclaw_procs),
            unit="count",
            threshold_warning=20.0,
            threshold_critical=50.0,
            status=self._get_status(len(openclaw_procs), 20, 50),
            timestamp=datetime.now().isoformat()
        )
        
        self._add_metric(MetricType.PROCESS.value, metric)
        
        return metric, openclaw_procs
    
    def check_service_health(self, service_name: str) -> ServiceHealth:
        """检查服务健康状态"""
        health = ServiceHealth(
            name=service_name,
            status="unknown",
            last_check=datetime.now().isoformat()
        )
        
        try:
            # 尝试检查进程
            for proc in psutil.process_iter(['pid', 'name', 'create_time']):
                if service_name.lower() in proc.info['name'].lower():
                    health.status = "running"
                    health.pid = proc.info['pid']
                    health.uptime = int(time.time() - proc.info['create_time'])
                    break
            else:
                health.status = "stopped"
        except Exception as e:
            health.status = "unknown"
        
        self.services[service_name] = health
        return health
    
    def _get_status(self, value: float, warning: float, critical: float, inverse: bool = False) -> MetricStatus:
        """根据阈值判断状态"""
        if inverse:
            # 值越小越危险（如可用内存）
            if value <= critical:
                return MetricStatus.CRITICAL
            elif value <= warning:
                return MetricStatus.WARNING
        else:
            # 值越大越危险（如使用率）
            if value >= critical:
                return MetricStatus.CRITICAL
            elif value >= warning:
                return MetricStatus.WARNING
        
        return MetricStatus.NORMAL
    
    def _add_metric(self, metric_type: str, metric: Metric):
        """添加指标"""
        if metric_type not in self.metrics:
            self.metrics[metric_type] = []
        
        self.metrics[metric_type].append(metric)
        
        # 只保留最近100条
        if len(self.metrics[metric_type]) > 100:
            self.metrics[metric_type] = self.metrics[metric_type][-100:]
    
    def _create_alert(self, metric: Metric):
        """创建告警"""
        # 检查是否已存在相同告警（未确认）
        for alert in self.alerts:
            if not alert.acknowledged and alert.metric_name == metric.name:
                # 更新现有告警
                alert.value = metric.value
                alert.timestamp = metric.timestamp
                return
        
        level = AlertLevel.WARNING if metric.status == MetricStatus.WARNING else AlertLevel.CRITICAL
        
        alert = Alert(
            id=f"alert_{metric.name}_{int(time.time())}",
            level=level,
            message=f"{metric.name} 达到 {metric.value:.1f}{metric.unit} (阈值: {metric.threshold_warning}/{metric.threshold_critical})",
            metric_name=metric.name,
            value=metric.value,
            threshold=metric.threshold_warning,
            timestamp=metric.timestamp
        )
        
        self.alerts.append(alert)
        
        # 触发回调
        for callback in self.callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"告警回调失败: {e}")
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.callbacks.append(callback)
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """确认告警"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.acknowledged = True
                return True
        return False
    
    def get_latest_metrics(self) -> Dict[str, Metric]:
        """获取最新指标"""
        result = {}
        for metric_type, metrics_list in self.metrics.items():
            if metrics_list:
                result[metric_type] = metrics_list[-1]
        return result
    
    def get_active_alerts(self) -> List[Alert]:
        """获取活跃告警"""
        return [a for a in self.alerts if not a.acknowledged]
    
    def collect_all(self):
        """收集所有指标"""
        self.collect_cpu_metrics()
        self.collect_memory_metrics()
        self.collect_disk_metrics()
        self.collect_network_metrics()
        self.collect_process_metrics()
    
    def start_monitoring(self, interval: int = 30):
        """启动监控"""
        def monitor():
            while self.monitoring:
                self.collect_all()
                self.save()
                time.sleep(interval)
        
        self.monitoring = True
        self.monitor_thread = threading.Thread(target=monitor, daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def generate_report(self) -> str:
        """生成监控报告"""
        latest = self.get_latest_metrics()
        active_alerts = self.get_active_alerts()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    奥创监控系统报告                           ║
║                    第3世：执行准备                             ║
╚══════════════════════════════════════════════════════════════╝

⏰ 监控时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
        
        # 指标状态
        report += "📊 实时指标:\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        status_icon = {
            MetricStatus.NORMAL: "✅",
            MetricStatus.WARNING: "⚠️",
            MetricStatus.CRITICAL: "🚨",
            MetricStatus.UNKNOWN: "❓"
        }
        
        for metric_type, metric in latest.items():
            icon = status_icon.get(metric.status, "❓")
            report += f"{icon} {metric.name}: {metric.value:.1f}{metric.unit}\n"
        
        # 告警状态
        report += f"\n🚨 活跃告警: {len(active_alerts)} 个\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        if active_alerts:
            for alert in active_alerts[-5:]:  # 只显示最近5个
                level_icon = {
                    AlertLevel.INFO: "ℹ️",
                    AlertLevel.WARNING: "⚠️",
                    AlertLevel.ERROR: "❌",
                    AlertLevel.CRITICAL: "🚨"
                }.get(alert.level, "❓")
                
                report += f"{level_icon} [{alert.level.value.upper()}] {alert.message}\n"
        else:
            report += "✅ 无活跃告警\n"
        
        # 服务状态
        report += f"\n🔧 服务状态:\n"
        report += "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # 检查OpenClaw服务
        try:
            result = subprocess.run(
                ['systemctl', 'is-active', 'openclaw'],
                capture_output=True,
                text=True,
                timeout=5
            )
            service_status = result.stdout.strip()
            icon = "✅" if service_status == "active" else "❌"
            report += f"{icon} OpenClaw: {service_status}\n"
        except Exception:
            report += "⚠️ 无法获取服务状态\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════╗
║                    监控配置                                   ║
╚══════════════════════════════════════════════════════════════╝

监控间隔: 30秒
指标保留: 最近100条
告警阈值:
  - CPU: 警告75%, 危险90%
  - 内存: 警告80%, 危险95%
  - 磁盘: 警告80%, 危险95%

✅ 监控系统就绪

"""
        
        return report


def main():
    """主函数"""
    monitor = MonitoringSystem()
    
    # 收集一次指标
    print("📡 收集系统指标...")
    monitor.collect_all()
    
    # 输出报告
    print(monitor.generate_report())
    
    # 注册告警回调
    def alert_handler(alert: Alert):
        print(f"\n🚨 告警: {alert.message}")
    
    monitor.register_alert_callback(alert_handler)
    
    # 启动持续监控
    print("\n🚀 启动持续监控...")
    monitor.start_monitoring(interval=30)
    
    print("✅ 监控系统就绪")


if __name__ == "__main__":
    main()