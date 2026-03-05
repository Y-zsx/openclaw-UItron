#!/usr/bin/env python3
"""
智能监控系统 - 全方位监控 + 智能告警 + 自愈机制
功能：系统资源监控、进程服务监控、性能指标收集、自适应阈值、告警规则引擎、自愈机制

第1世：全方位监控 ✅
第2世：智能告警 ✅
第3世：自愈机制 🔄
  - 异常检测
  - 自动修复策略
  - 恢复验证
"""

import json
import os
import subprocess
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

# 配置
CONFIG_PATH = "/root/.openclaw/workspace/ultron/logs/monitor-config.json"
DATA_PATH = "/root/.openclaw/workspace/ultron/logs/metrics-history.json"
ALERT_PATH = "/root/.openclaw/workspace/ultron/logs/alerts.json"
RULES_PATH = "/root/.openclaw/workspace/ultron/logs/alert-rules.json"

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"

class NotificationChannel(Enum):
    CONSOLE = "console"
    DINGTALK = "dingtalk"
    EMAIL = "email"

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
    rule_id: Optional[str] = None

@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    enabled: bool
    source: str
    metric: str
    operator: str  # gt, lt, eq, gte, lte
    threshold: float
    level: str
    cooldown_minutes: int
    aggregation_window: int  # 分钟
    notify_channels: List[str]

class AlertRuleEngine:
    """告警规则引擎"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.alert_history: Dict[str, List[Alert]] = {}  # rule_id -> alerts
        self.notification_handlers: Dict[str, Callable] = {}
        self._load_rules()
    
    def _load_rules(self):
        """加载规则"""
        if os.path.exists(RULES_PATH):
            try:
                with open(RULES_PATH) as f:
                    data = json.load(f)
                    for r in data.get("rules", []):
                        self.rules[r["id"]] = AlertRule(**r)
            except Exception as e:
                print(f"加载规则失败: {e}")
        
        # 添加默认规则
        if not self.rules:
            self._add_default_rules()
    
    def _add_default_rules(self):
        """添加默认规则"""
        default_rules = [
            AlertRule(
                id="cpu_high",
                name="CPU负载过高",
                enabled=True,
                source="cpu",
                metric="load_1m",
                operator="gt",
                threshold=80,
                level=AlertLevel.WARNING.value,
                cooldown_minutes=5,
                aggregation_window=5,
                notify_channels=["console"]
            ),
            AlertRule(
                id="memory_high",
                name="内存使用率过高",
                enabled=True,
                source="memory",
                metric="usage_percent",
                operator="gt",
                threshold=85,
                level=AlertLevel.WARNING.value,
                cooldown_minutes=5,
                aggregation_window=5,
                notify_channels=["console"]
            ),
            AlertRule(
                id="disk_high",
                name="磁盘使用率过高",
                enabled=True,
                source="disk",
                metric="usage_percent",
                operator="gt",
                threshold=90,
                level=AlertLevel.CRITICAL.value,
                cooldown_minutes=10,
                aggregation_window=10,
                notify_channels=["console", "dingtalk"]
            ),
            AlertRule(
                id="service_down",
                name="服务宕机",
                enabled=True,
                source="services",
                metric="status",
                operator="eq",
                threshold=0,  # 0 = stopped
                level=AlertLevel.CRITICAL.value,
                cooldown_minutes=2,
                aggregation_window=2,
                notify_channels=["console", "dingtalk"]
            )
        ]
        for rule in default_rules:
            self.rules[rule.id] = rule
        self._save_rules()
    
    def _save_rules(self):
        """保存规则"""
        Path(RULES_PATH).parent.mkdir(parents=True, exist_ok=True)
        data = {"rules": [asdict(r) for r in self.rules.values()]}
        with open(RULES_PATH, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_notification_handler(self, channel: str, handler: Callable):
        """注册通知处理器"""
        self.notification_handlers[channel] = handler
    
    def check_rule(self, rule: AlertRule, metrics: SystemMetrics) -> Optional[Alert]:
        """检查单条规则"""
        if not rule.enabled:
            return None
        
        # 获取指标值
        value = None
        source_data = getattr(metrics, rule.source, None)
        
        if source_data is None:
            return None
        
        if rule.source == "services":
            # 服务状态特殊处理
            service_status = metrics.services.get(rule.metric, "stopped")
            if rule.operator == "eq" and service_status == "stopped":
                value = 0
                threshold = 0
            else:
                return None
        else:
            value = source_data.get(rule.metric)
            threshold = rule.threshold
        
        if value is None:
            return None
        
        # 比较
        triggered = False
        if rule.operator == "gt":
            triggered = value > threshold
        elif rule.operator == "lt":
            triggered = value < threshold
        elif rule.operator == "gte":
            triggered = value >= threshold
        elif rule.operator == "lte":
            triggered = value <= threshold
        elif rule.operator == "eq":
            triggered = value == threshold
        
        if not triggered:
            return None
        
        # 检查冷却时间
        rule_alerts = self.alert_history.get(rule.id, [])
        if rule_alerts:
            last_alert = rule_alerts[-1]
            last_time = datetime.fromisoformat(last_alert.timestamp)
            cooldown = timedelta(minutes=rule.cooldown_minutes)
            if datetime.now() - last_time < cooldown:
                return None  # 冷却期内
        
        # 创建告警
        return Alert(
            id=f"{rule.id}_{uuid.uuid4().hex[:6]}",
            timestamp=metrics.timestamp,
            level=rule.level,
            source=rule.source,
            message=f"{rule.name}: {value} (阈值: {threshold})",
            value=value,
            threshold=threshold,
            rule_id=rule.id
        )
    
    def check_all_rules(self, metrics: SystemMetrics) -> List[Alert]:
        """检查所有规则"""
        alerts = []
        for rule in self.rules.values():
            alert = self.check_rule(rule, metrics)
            if alert:
                alerts.append(alert)
                # 记录告警历史
                if rule.id not in self.alert_history:
                    self.alert_history[rule.id] = []
                self.alert_history[rule.id].append(alert)
        
        return alerts
    
    def aggregate_alerts(self, alerts: List[Alert], window_minutes: int = 5) -> List[Alert]:
        """聚合告警"""
        if not alerts:
            return []
        
        # 按规则ID分组
        grouped: Dict[str, List[Alert]] = {}
        for alert in alerts:
            if alert.rule_id:
                if alert.rule_id not in grouped:
                    grouped[alert.rule_id] = []
                grouped[alert.rule_id].append(alert)
        
        # 聚合
        aggregated = []
        for rule_id, rule_alerts in grouped.items():
            if len(rule_alerts) > 1:
                # 多个相同告警，合并为一条
                first = rule_alerts[0]
                first.message = f"{first.message} (共{len(rule_alerts)}次)"
                aggregated.append(first)
            else:
                aggregated.extend(rule_alerts)
        
        return aggregated
    
    def send_notifications(self, alerts: List[Alert]):
        """发送通知"""
        for alert in alerts:
            # 获取规则
            rule = self.rules.get(alert.rule_id)
            if not rule:
                continue
            
            for channel in rule.notify_channels:
                handler = self.notification_handlers.get(channel)
                if handler:
                    try:
                        handler(alert)
                    except Exception as e:
                        print(f"通知发送失败 [{channel}]: {e}")
    
    def get_rule_stats(self) -> Dict:
        """获取规则统计"""
        stats = {}
        for rule_id, alerts in self.alert_history.items():
            rule = self.rules.get(rule_id)
            stats[rule_id] = {
                "name": rule.name if rule else rule_id,
                "total_alerts": len(alerts),
                "last_alert": alerts[-1].timestamp if alerts else None,
                "level": rule.level if rule else None
            }
        return stats


class IntelligentMonitor:
    """智能监控系统"""
    
    def __init__(self):
        self.config = self._load_config()
        self.history: List[SystemMetrics] = []
        self.alerts: List[Alert] = []
        self.rule_engine = AlertRuleEngine()
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        
        # 注册通知处理器
        self.rule_engine.register_notification_handler("console", self._console_notify)
        
    def _console_notify(self, alert: Alert):
        """控制台通知"""
        level_emoji = {
            AlertLevel.INFO.value: "ℹ️",
            AlertLevel.WARNING.value: "⚠️",
            AlertLevel.CRITICAL.value: "🔴"
        }
        print(f"{level_emoji.get(alert.level, '🔔')} [{alert.level.upper()}] {alert.message}")
    
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
            
            return {
                "total_gb": round(total / 1024 / 1024, 2),
                "available_gb": round(available / 1024 / 1024, 2),
                "used_gb": round(used / 1024 / 1024, 2),
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
    
    def process_alerts(self, metrics: SystemMetrics) -> List[Alert]:
        """处理告警：规则检查 + 聚合 + 通知"""
        # 规则检查
        alerts = self.rule_engine.check_all_rules(metrics)
        
        if not alerts:
            return []
        
        # 聚合
        aggregated = self.rule_engine.aggregate_alerts(alerts)
        
        # 发送通知
        self.rule_engine.send_notifications(aggregated)
        
        return aggregated
    
    def check_thresholds(self, metrics: SystemMetrics) -> List[Alert]:
        """检查阈值并生成告警（兼容旧接口）"""
        return self.process_alerts(metrics)
    
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
            "history_size": len(self.history),
            "alert_rules": len(self.rule_engine.rules)
        }
    
    def get_trends(self, hours: int = 1) -> Dict:
        """获取趋势数据"""
        if len(self.history) < 2:
            return {"status": "insufficient_data"}
        
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [m for m in self.history if datetime.fromisoformat(m.timestamp) > cutoff]
        
        if len(recent) < 2:
            return {"status": "insufficient_data"}
        
        cpu_loads = [m.cpu.get('load_1m', 0) for m in recent]
        mem_usages = [m.memory.get('usage_percent', 0) for m in recent]
        disk_usages = [m.disk.get('usage_percent', 0) for m in recent]
        
        return {
            "period_hours": hours,
            "data_points": len(recent),
            "cpu": {"avg": round(sum(cpu_loads) / len(cpu_loads), 2), "max": max(cpu_loads), "min": min(cpu_loads)},
            "memory": {"avg": round(sum(mem_usages) / len(mem_usages), 1), "max": max(mem_usages), "min": min(mem_usages)},
            "disk": {"avg": round(sum(disk_usages) / len(disk_usages), 1), "max": max(disk_usages), "min": min(disk_usages)}
        }
    
    def get_rule_stats(self) -> Dict:
        """获取规则统计"""
        return self.rule_engine.get_rule_stats()
    
    def detect_anomalies(self, metrics: SystemMetrics) -> List[Dict]:
        """异常检测：基于历史数据检测异常"""
        if len(self.history) < 10:
            return []
        
        # 获取最近历史数据计算基线
        recent = self.history[-20:]
        
        cpu_loads = [m.cpu.get('load_1m', 0) for m in recent]
        mem_usages = [m.memory.get('usage_percent', 0) for m in recent]
        
        # 计算均值和标准差
        import statistics
        anomalies = []
        
        current_cpu = metrics.cpu.get('load_1m', 0)
        if cpu_loads:
            cpu_mean = statistics.mean(cpu_loads)
            cpu_stdev = statistics.stdev(cpu_loads) if len(cpu_loads) > 1 else 0
            if cpu_stdev > 0 and (current_cpu > cpu_mean + 3 * cpu_stdev):
                anomalies.append({
                    "type": "cpu_spike",
                    "current": current_cpu,
                    "mean": cpu_mean,
                    "severity": "high"
                })
        
        current_mem = metrics.memory.get('usage_percent', 0)
        if mem_usages:
            mem_mean = statistics.mean(mem_usages)
            mem_stdev = statistics.stdev(mem_usages) if len(mem_usages) > 1 else 0
            if mem_stdev > 0 and (current_mem > mem_mean + 2 * mem_stdev):
                anomalies.append({
                    "type": "memory_spike",
                    "current": current_mem,
                    "mean": mem_mean,
                    "severity": "medium"
                })
        
        return anomalies
    
    def self_heal(self, metrics: SystemMetrics) -> Dict:
        """自愈：检测并自动修复问题"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "anomalies": [],
            "fixes_attempted": [],
            "fixes_succeeded": [],
            "verification": []
        }
        
        # 1. 异常检测
        anomalies = self.detect_anomalies(metrics)
        results["anomalies"] = anomalies
        
        # 2. 自动修复
        # 服务宕机修复
        for svc, status in metrics.services.items():
            if status == "stopped" and svc in self.config.get("services", []):
                fix_result = self._fix_service(svc)
                results["fixes_attempted"].append(fix_result)
                if fix_result["success"]:
                    results["fixes_succeeded"].append(fix_result)
        
        # 3. 恢复验证
        time.sleep(2)  # 等待修复生效
        verified_metrics = self.collect_metrics()
        
        for svc in results.get("fixes_succeeded", []):
            service_name = svc.get("service")
            if service_name in verified_metrics.services:
                if verified_metrics.services[service_name] == "running":
                    results["verification"].append({
                        "service": service_name,
                        "status": "verified",
                        "message": f"{service_name} 已恢复运行"
                    })
                else:
                    results["verification"].append({
                        "service": service_name,
                        "status": "failed",
                        "message": f"{service_name} 恢复失败"
                    })
        
        return results
    
    def _fix_service(self, service_name: str) -> Dict:
        """修复服务"""
        # 服务启动命令映射
        service_commands = {
            "openclaw": "openclaw gateway start",
            "nginx": "systemctl start nginx",
            "cron": "systemctl start cron",
            "chromium": None  # 不自动启动浏览器
        }
        
        command = service_commands.get(service_name)
        
        if not command:
            return {
                "service": service_name,
                "action": "skip",
                "success": False,
                "message": f"无自动修复命令"
            }
        
        try:
            result = subprocess.run(
                command.split(),
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                return {
                    "service": service_name,
                    "action": "restart",
                    "success": True,
                    "message": f"{service_name} 已重启"
                }
            else:
                return {
                    "service": service_name,
                    "action": "restart",
                    "success": False,
                    "message": f"重启失败: {result.stderr}"
                }
        except Exception as e:
            return {
                "service": service_name,
                "action": "restart",
                "success": False,
                "message": f"异常: {str(e)}"
            }


# CLI接口
def main():
    import argparse
    parser = argparse.ArgumentParser(description='智能监控系统')
    parser.add_argument('action', choices=['collect', 'summary', 'trends', 'alerts', 'rules', 'heal'], 
                        help='操作类型')
    parser.add_argument('--hours', type=int, default=1, help='趋势分析小时数')
    args = parser.parse_args()
    
    monitor = IntelligentMonitor()
    
    if args.action == 'collect':
        metrics = monitor.collect_metrics()
        alerts = monitor.process_alerts(metrics)
        monitor.save_metrics(metrics)
        monitor.save_alerts(alerts)
        
        print(f"✅ 指标收集完成 - {metrics.timestamp}")
        print(f"  CPU负载: {metrics.cpu.get('load_1m', 0)}")
        print(f"  内存: {metrics.memory.get('usage_percent', 0)}%")
        print(f"  磁盘: {metrics.disk.get('usage_percent', 0)}%")
        print(f"  进程: {metrics.processes}")
        print(f"  服务: {metrics.services}")
        print(f"  告警规则: {len(monitor.rule_engine.rules)}条")
        
        if alerts:
            print(f"\n⚠️  触发告警: {len(alerts)}个")
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
    
    elif args.action == 'rules':
        print(json.dumps(monitor.get_rule_stats(), indent=2))
    
    elif args.action == 'heal':
        # 自愈：检查并修复问题
        metrics = monitor.collect_metrics()
        healing_results = monitor.self_heal(metrics)
        print(json.dumps(healing_results, indent=2))

if __name__ == '__main__':
    main()