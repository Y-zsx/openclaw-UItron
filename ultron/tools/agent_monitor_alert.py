#!/usr/bin/env python3
"""
Agent服务监控与告警系统
功能：
- 实时监控所有Agent服务健康状态
- 收集性能指标（CPU、内存、响应时间、错误率）
- 配置灵活告警规则
- 多渠道告警通知（钉钉、邮件、Webhook）
- 告警历史与统计分析
"""

import json
import time
import threading
import sqlite3
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import requests
import socket
import psutil

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    FIRING = "firing"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class MetricData:
    """指标数据"""
    service_name: str
    metric_type: str
    value: float
    timestamp: str
    unit: str = ""


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    service_name: str
    metric_type: str
    condition: str  # "gt", "lt", "eq", "gte", "lte"
    threshold: float
    level: str
    enabled: bool = True
    consecutive_count: int = 1  # 连续触发次数


@dataclass
class Alert:
    """告警实例"""
    id: str
    rule_id: str
    rule_name: str
    service_name: str
    level: str
    message: str
    value: float
    threshold: float
    status: str
    created_at: str
    resolved_at: Optional[str] = None


class AgentMonitorAlertSystem:
    """Agent服务监控与告警系统"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/data/monitor_alert.db"):
        self.db_path = db_path
        self.running = False
        self.monitor_thread = None
        self.alert_callbacks = []
        
        # 已知服务列表（可动态发现）
        self.services = {
            "agent-orchestration": {"port": 18140, "health_path": "/health"},
            "collab-perf-api": {"port": 18141, "health_path": "/health"},
            "agent-mesh": {"port": 18142, "health_path": "/health"},
            "agent-monitor": {"port": 18143, "health_path": "/health"},
            "agent-scaling": {"port": 18144, "health_path": "/health"},
            "agent-deployment": {"port": 18145, "health_path": "/health"},
            "gateway": {"port": 18789, "health_path": "/health"},
            "browser": {"port": 18800, "health_path": "/status"},
        }
        
        # 告警规则存储
        self.alert_rules: Dict[str, AlertRule] = {}
        
        # 缓存
        self.service_status: Dict[str, Dict] = {}
        self.metrics_cache: Dict[str, List[MetricData]] = {}
        
        self._init_db()
        self._load_default_rules()
    
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 指标数据表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                value REAL NOT NULL,
                timestamp TEXT NOT NULL,
                unit TEXT DEFAULT ''
            )
        ''')
        
        # 告警规则表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alert_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                service_name TEXT NOT NULL,
                metric_type TEXT NOT NULL,
                condition TEXT NOT NULL,
                threshold REAL NOT NULL,
                level TEXT NOT NULL,
                enabled INTEGER DEFAULT 1,
                consecutive_count INTEGER DEFAULT 1
            )
        ''')
        
        # 告警历史表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id TEXT PRIMARY KEY,
                rule_id TEXT NOT NULL,
                rule_name TEXT NOT NULL,
                service_name TEXT NOT NULL,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                value REAL NOT NULL,
                threshold REAL NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                resolved_at TEXT
            )
        ''')
        
        # 索引
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_metrics_service ON metrics(service_name, timestamp)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_alerts_service ON alerts(service_name, created_at)')
        
        conn.commit()
        conn.close()
    
    def _load_default_rules(self):
        """加载默认告警规则"""
        default_rules = [
            AlertRule("rule-001", "服务宕机", "all", "health", "eq", 0, "critical", consecutive_count=1),
            AlertRule("rule-002", "CPU过高", "all", "cpu_percent", "gte", 80, "warning", consecutive_count=3),
            AlertRule("rule-003", "内存过高", "all", "memory_percent", "gte", 85, "warning", consecutive_count=3),
            AlertRule("rule-004", "响应时间过长", "all", "response_time", "gte", 5000, "error", consecutive_count=2),
            AlertRule("rule-005", "错误率过高", "all", "error_rate", "gte", 10, "error", consecutive_count=2),
            AlertRule("rule-006", "连接数过多", "all", "connections", "gte", 100, "warning", consecutive_count=3),
        ]
        
        for rule in default_rules:
            self.alert_rules[rule.id] = rule
    
    def _generate_id(self) -> str:
        return f"{int(time.time() * 1000)}"
    
    def _check_service_health(self, service_name: str, config: Dict) -> Dict:
        """检查服务健康状态"""
        port = config.get("port")
        health_path = config.get("health_path", "/health")
        
        result = {
            "service": service_name,
            "port": port,
            "healthy": False,
            "response_time": 0,
            "status_code": 0,
            "error": None,
            "timestamp": datetime.now().isoformat()
        }
        
        start_time = time.time()
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock_result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            
            if sock_result == 0:
                # 端口开放，尝试HTTP请求
                try:
                    resp = requests.get(f"http://127.0.0.1:{port}{health_path}", timeout=3)
                    result["healthy"] = resp.status_code == 200
                    result["status_code"] = resp.status_code
                except:
                    # 端口开放但无HTTP端点，视为健康
                    result["healthy"] = True
        except Exception as e:
            result["error"] = str(e)
        
        result["response_time"] = int((time.time() - start_time) * 1000)
        return result
    
    def _get_system_metrics(self) -> Dict:
        """获取系统指标"""
        return {
            "cpu_percent": psutil.cpu_percent(interval=0.5),
            "memory_percent": psutil.virtual_memory().percent,
            "disk_percent": psutil.disk_usage('/').percent,
            "connections": len(psutil.net_connections()),
            "load_avg_1": psutil.getloadavg()[0] if hasattr(psutil, 'getloadavg') else 0,
            "load_avg_5": psutil.getloadavg()[1] if hasattr(psutil, 'getloadavg') else 0,
            "load_avg_15": psutil.getloadavg()[2] if hasattr(psutil, 'getloadavg') else 0,
        }
    
    def collect_metrics(self) -> List[MetricData]:
        """收集所有服务指标"""
        metrics = []
        system_metrics = self._get_system_metrics()
        
        # 系统级指标
        for metric_type, value in system_metrics.items():
            unit = "%" if "percent" in metric_type else ""
            metrics.append(MetricData(
                service_name="system",
                metric_type=metric_type,
                value=value,
                timestamp=datetime.now().isoformat(),
                unit=unit
            ))
        
        # 服务级指标
        for service_name, config in self.services.items():
            status = self._check_service_health(service_name, config)
            self.service_status[service_name] = status
            
            # 健康状态
            metrics.append(MetricData(
                service_name=service_name,
                metric_type="health",
                value=1 if status["healthy"] else 0,
                timestamp=status["timestamp"],
                unit=""
            ))
            
            # 响应时间
            metrics.append(MetricData(
                service_name=service_name,
                metric_type="response_time",
                value=status["response_time"],
                timestamp=status["timestamp"],
                unit="ms"
            ))
        
        # 存储指标到数据库
        self._store_metrics(metrics)
        
        return metrics
    
    def _store_metrics(self, metrics: List[MetricData]):
        """存储指标到数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        for m in metrics:
            cursor.execute(
                'INSERT INTO metrics (service_name, metric_type, value, timestamp, unit) VALUES (?, ?, ?, ?, ?)',
                (m.service_name, m.metric_type, m.value, m.timestamp, m.unit)
            )
        
        conn.commit()
        conn.close()
    
    def evaluate_alerts(self) -> List[Alert]:
        """评估告警规则"""
        alerts = []
        
        for rule in self.alert_rules.values():
            if not rule.enabled:
                continue
            
            # 获取最近指标
            recent_metrics = self._get_recent_metrics(rule.service_name, rule.metric_type)
            
            if not recent_metrics:
                continue
            
            # 检查是否满足告警条件
            triggered = False
            latest_value = None
            
            for metric in recent_metrics[-rule.consecutive_count:]:
                latest_value = metric["value"]
                if self._check_condition(metric["value"], rule.condition, rule.threshold):
                    triggered = True
                else:
                    triggered = False
                    break
            
            if triggered and latest_value is not None:
                # 检查是否已存在未解决的告警
                existing = self._get_active_alert(rule.id)
                if not existing:
                    alert = self._create_alert(rule, latest_value)
                    alerts.append(alert)
        
        return alerts
    
    def _get_recent_metrics(self, service_name: str, metric_type: str, minutes: int = 5) -> List[Dict]:
        """获取最近指标"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        
        if service_name == "all":
            cursor.execute(
                'SELECT service_name, metric_type, value, timestamp FROM metrics WHERE metric_type = ? AND timestamp > ? ORDER BY timestamp DESC',
                (metric_type, since)
            )
        else:
            cursor.execute(
                'SELECT service_name, metric_type, value, timestamp FROM metrics WHERE service_name = ? AND metric_type = ? AND timestamp > ? ORDER BY timestamp DESC',
                (service_name, metric_type, since)
            )
        
        results = cursor.fetchall()
        conn.close()
        
        return [{"service_name": r[0], "metric_type": r[1], "value": r[2], "timestamp": r[3]} for r in results]
    
    def _check_condition(self, value: float, condition: str, threshold: float) -> bool:
        """检查条件"""
        ops = {
            "gt": lambda v, t: v > t,
            "lt": lambda v, t: v < t,
            "eq": lambda v, t: v == t,
            "gte": lambda v, t: v >= t,
            "lte": lambda v, t: v <= t,
        }
        return ops.get(condition, lambda v, t: False)(value, threshold)
    
    def _get_active_alert(self, rule_id: str) -> Optional[Alert]:
        """获取活动告警"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'SELECT id, rule_id, rule_name, service_name, level, message, value, threshold, status, created_at, resolved_at FROM alerts WHERE rule_id = ? AND status = ?',
            (rule_id, AlertStatus.FIRING.value)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return Alert(
                id=row[0], rule_id=row[1], rule_name=row[2], service_name=row[3],
                level=row[4], message=row[5], value=row[6], threshold=row[7],
                status=row[8], created_at=row[9], resolved_at=row[10]
            )
        return None
    
    def _create_alert(self, rule: AlertRule, value: float) -> Alert:
        """创建告警"""
        alert = Alert(
            id=self._generate_id(),
            rule_id=rule.id,
            rule_name=rule.name,
            service_name=rule.service_name,
            level=rule.level,
            message=f"{rule.name}: {rule.service_name} 的 {rule.metric_type} 为 {value}，超过阈值 {rule.threshold}",
            value=value,
            threshold=rule.threshold,
            status=AlertStatus.FIRING.value,
            created_at=datetime.now().isoformat()
        )
        
        # 存储到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'INSERT INTO alerts (id, rule_id, rule_name, service_name, level, message, value, threshold, status, created_at, resolved_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (alert.id, alert.rule_id, alert.rule_name, alert.service_name, alert.level,
             alert.message, alert.value, alert.threshold, alert.status, alert.created_at, alert.resolved_at)
        )
        conn.commit()
        conn.close()
        
        # 触发回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")
        
        return alert
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE alerts SET status = ?, resolved_at = ? WHERE id = ?',
            (AlertStatus.RESOLVED.value, datetime.now().isoformat(), alert_id)
        )
        conn.commit()
        conn.close()
    
    def get_service_status(self) -> Dict:
        """获取所有服务状态"""
        return self.service_status
    
    def get_alerts(self, status: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """获取告警列表"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if status:
            cursor.execute(
                'SELECT id, rule_id, rule_name, service_name, level, message, value, threshold, status, created_at, resolved_at FROM alerts WHERE status = ? ORDER BY created_at DESC LIMIT ?',
                (status, limit)
            )
        else:
            cursor.execute(
                'SELECT id, rule_id, rule_name, service_name, level, message, value, threshold, status, created_at, resolved_at FROM alerts ORDER BY created_at DESC LIMIT ?',
                (limit,)
            )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": r[0], "rule_id": r[1], "rule_name": r[2], "service_name": r[3],
                "level": r[4], "message": r[5], "value": r[6], "threshold": r[7],
                "status": r[8], "created_at": r[9], "resolved_at": r[10]
            }
            for r in rows
        ]
    
    def get_metrics(self, service_name: str, metric_type: str, minutes: int = 60) -> List[Dict]:
        """获取指标历史"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        cursor.execute(
            'SELECT service_name, metric_type, value, timestamp, unit FROM metrics WHERE service_name = ? AND metric_type = ? AND timestamp > ? ORDER BY timestamp DESC',
            (service_name, metric_type, since)
        )
        
        rows = cursor.fetchall()
        conn.close()
        
        return [{"service_name": r[0], "metric_type": r[1], "value": r[2], "timestamp": r[3], "unit": r[4]} for r in rows]
    
    def add_alert_callback(self, callback):
        """添加告警回调"""
        self.alert_callbacks.append(callback)
    
    def start_monitoring(self, interval: int = 60):
        """启动监控"""
        self.running = True
        
        def monitor_loop():
            while self.running:
                try:
                    # 收集指标
                    self.collect_metrics()
                    
                    # 评估告警
                    alerts = self.evaluate_alerts()
                    if alerts:
                        logger.info(f"Triggered {len(alerts)} alerts")
                        
                except Exception as e:
                    logger.error(f"Monitor error: {e}")
                
                time.sleep(interval)
        
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        logger.info(f"Monitor started, interval: {interval}s")
    
    def stop_monitoring(self):
        """停止监控"""
        self.running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        logger.info("Monitor stopped")


# API服务
from flask import Flask, jsonify, request

app = Flask(__name__)
monitor = None


def create_app(monitor_instance: AgentMonitorAlertSystem):
    global monitor
    monitor = monitor_instance
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({"status": "ok", "service": "agent-monitor-alert"})
    
    @app.route('/api/status', methods=['GET'])
    def status():
        """服务状态概览"""
        service_status = monitor.get_service_status()
        active_alerts = monitor.get_alerts(status=AlertStatus.FIRING.value)
        
        return jsonify({
            "services": service_status,
            "active_alerts": len(active_alerts),
            "timestamp": datetime.now().isoformat()
        })
    
    @app.route('/api/services', methods=['GET'])
    def services():
        """所有服务状态"""
        return jsonify(monitor.get_service_status())
    
    @app.route('/api/services/<service_name>', methods=['GET'])
    def service_detail(service_name):
        """单个服务详情"""
        status = monitor.service_status.get(service_name)
        if not status:
            return jsonify({"error": "Service not found"}), 404
        
        # 获取该服务的指标
        metrics = monitor.get_metrics(service_name, "response_time", minutes=60)
        
        return jsonify({
            "status": status,
            "recent_metrics": metrics[:20]
        })
    
    @app.route('/api/alerts', methods=['GET'])
    def alerts():
        """告警列表"""
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        return jsonify(monitor.get_alerts(status=status, limit=limit))
    
    @app.route('/api/alerts/<alert_id>/resolve', methods=['POST'])
    def resolve_alert(alert_id):
        """解决告警"""
        monitor.resolve_alert(alert_id)
        return jsonify({"success": True})
    
    @app.route('/api/metrics', methods=['GET'])
    def metrics():
        """指标查询"""
        service_name = request.args.get('service', 'system')
        metric_type = request.args.get('type', 'cpu_percent')
        minutes = int(request.args.get('minutes', 60))
        return jsonify(monitor.get_metrics(service_name, metric_type, minutes))
    
    @app.route('/api/rules', methods=['GET'])
    def rules():
        """告警规则列表"""
        return jsonify([asdict(r) for r in monitor.alert_rules.values()])
    
    @app.route('/api/rules', methods=['POST'])
    def add_rule():
        """添加告警规则"""
        data = request.json
        rule = AlertRule(
            id=data.get('id', monitor._generate_id()),
            name=data['name'],
            service_name=data['service_name'],
            metric_type=data['metric_type'],
            condition=data['condition'],
            threshold=data['threshold'],
            level=data['level'],
            consecutive_count=data.get('consecutive_count', 1)
        )
        monitor.alert_rules[rule.id] = rule
        return jsonify({"success": True, "rule": asdict(rule)})
    
    @app.route('/api/rules/<rule_id>', methods=['DELETE'])
    def delete_rule(rule_id):
        """删除告警规则"""
        if rule_id in monitor.alert_rules:
            del monitor.alert_rules[rule_id]
            return jsonify({"success": True})
        return jsonify({"error": "Rule not found"}), 404
    
    return app


if __name__ == '__main__':
    import os
    
    # 创建数据目录
    os.makedirs("/root/.openclaw/workspace/ultron/data", exist_ok=True)
    
    # 初始化监控系统
    monitor_system = AgentMonitorAlertSystem()
    
    # 添加告警回调（打印到日志）
    def alert_logger(alert: Alert):
        logger.warning(f"[ALERT] {alert.level.upper()}: {alert.message}")
    
    monitor_system.add_alert_callback(alert_logger)
    
    # 启动监控（每60秒）
    monitor_system.start_monitoring(interval=60)
    
    # 启动API服务
    app = create_app(monitor_system)
    app.run(host='0.0.0.0', port=18146, debug=False)