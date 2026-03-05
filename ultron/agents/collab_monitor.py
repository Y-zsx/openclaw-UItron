#!/usr/bin/env python3
"""
Agent协作网络实时监控告警系统
Real-time Monitoring and Alerting for Agent Collaboration Network
"""

import json
import time
import threading
import os
import sqlite3
from datetime import datetime, timedelta
from collections import deque
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import statistics
import socket
import subprocess

# Config
DATA_DIR = "/root/.openclaw/workspace/ultron/agents/data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "collab_monitor.db")

class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class MetricType(Enum):
    AGENT_ONLINE = "agent_online"
    AGENT_OFFLINE = "agent_offline"
    TASK_QUEUE_LENGTH = "task_queue_length"
    TASK_LATENCY = "task_latency"
    TASK_FAILURE = "task_failure"
    MESSAGE_LATENCY = "message_latency"
    NETWORK_LOAD = "network_load"
    MEMORY_USAGE = "memory_usage"
    CPU_USAGE = "cpu_usage"

@dataclass
class Metric:
    """监控指标"""
    timestamp: float
    metric_type: str
    value: float
    agent_id: Optional[str] = None
    tags: Dict[str, str] = field(default_factory=dict)

@dataclass
class Alert:
    """告警"""
    id: str
    level: str
    title: str
    message: str
    timestamp: float
    agent_id: Optional[str] = None
    metric_type: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    acknowledged: bool = False
    resolved: bool = False
    resolved_at: Optional[float] = None

class CollabMonitor:
    """协作网络实时监控器"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self._init_db()
        
        # 指标缓存 (最近5分钟)
        self.metrics_buffer: deque = deque(maxlen=1000)
        
        # 告警规则
        self.alert_rules = self._load_alert_rules()
        
        # 告警回调
        self.alert_callbacks: List[Callable] = []
        
        # 监控状态
        self.is_running = False
        self.monitor_thread: Optional[threading.Thread] = None
        
        # 统计
        self.stats = {
            "total_metrics": 0,
            "total_alerts": 0,
            "alerts_by_level": {"info": 0, "warning": 0, "critical": 0, "emergency": 0}
        }
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 指标表
        c.execute('''CREATE TABLE IF NOT EXISTS metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            metric_type TEXT,
            value REAL,
            agent_id TEXT,
            tags TEXT
        )''')
        
        # 告警表
        c.execute('''CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            level TEXT,
            title TEXT,
            message TEXT,
            timestamp REAL,
            agent_id TEXT,
            metric_type TEXT,
            value REAL,
            threshold REAL,
            acknowledged INTEGER DEFAULT 0,
            resolved INTEGER DEFAULT 0,
            resolved_at REAL
        )''')
        
        # 索引
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_time ON metrics(timestamp)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_type ON metrics(metric_type)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_alerts_time ON alerts(timestamp)')
        
        conn.commit()
        conn.close()
    
    def _load_alert_rules(self) -> Dict:
        """加载告警规则"""
        return {
            "agent_offline": {
                "threshold": 1,
                "level": "critical",
                "window_seconds": 60,
                "cooldown_seconds": 300
            },
            "task_queue_length": {
                "threshold": 100,
                "level": "warning",
                "window_seconds": 120,
                "cooldown_seconds": 180
            },
            "task_failure_rate": {
                "threshold": 0.2,
                "level": "warning",
                "window_seconds": 300,
                "cooldown_seconds": 600
            },
            "task_latency_p99": {
                "threshold": 30.0,
                "level": "warning",
                "window_seconds": 180,
                "cooldown_seconds": 300
            },
            "message_latency": {
                "threshold": 10.0,
                "level": "warning",
                "window_seconds": 120,
                "cooldown_seconds": 180
            },
            "network_load": {
                "threshold": 0.9,
                "level": "critical",
                "window_seconds": 60,
                "cooldown_seconds": 120
            },
            "cpu_usage": {
                "threshold": 90.0,
                "level": "critical",
                "window_seconds": 60,
                "cooldown_seconds": 180
            },
            "memory_usage": {
                "threshold": 90.0,
                "level": "critical",
                "window_seconds": 120,
                "cooldown_seconds": 300
            }
        }
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)
    
    def record_metric(self, metric_type: str, value: float, agent_id: Optional[str] = None, tags: Optional[Dict] = None):
        """记录指标"""
        metric = Metric(
            timestamp=time.time(),
            metric_type=metric_type,
            value=value,
            agent_id=agent_id,
            tags=tags or {}
        )
        
        # 写入数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'INSERT INTO metrics (timestamp, metric_type, value, agent_id, tags) VALUES (?, ?, ?, ?, ?)',
            (metric.timestamp, metric.metric_type, metric.value, metric.agent_id, json.dumps(metric.tags))
        )
        conn.commit()
        conn.close()
        
        # 缓存
        self.metrics_buffer.append(metric)
        self.stats["total_metrics"] += 1
        
        # 检查告警
        self._check_alert_rules(metric)
    
    def _check_alert_rules(self, metric: Metric):
        """检查告警规则"""
        rule_key = metric.metric_type
        if rule_key not in self.alert_rules:
            # 尝试匹配
            for key in self.alert_rules:
                if key in metric.metric_type:
                    rule_key = key
                    break
            else:
                return
        
        rule = self.alert_rules[rule_key]
        
        # 检查是否触发告警
        if metric.value >= rule["threshold"]:
            # 检查最近是否有相同告警
            if self._recent_alert_exists(rule_key, rule["cooldown_seconds"]):
                return
            
            # 创建告警
            alert = Alert(
                id=f"alert_{int(time.time() * 1000)}_{metric.metric_type}",
                level=rule["level"],
                title=f"协作网络告警: {metric.metric_type}",
                message=f"{metric.metric_type} 超过阈值: {metric.value:.2f} >= {rule['threshold']}",
                timestamp=time.time(),
                agent_id=metric.agent_id,
                metric_type=metric.metric_type,
                value=metric.value,
                threshold=rule["threshold"]
            )
            
            self._create_alert(alert)
    
    def _recent_alert_exists(self, metric_type: str, cooldown_seconds: float) -> bool:
        """检查最近是否已有告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'SELECT COUNT(*) FROM alerts WHERE metric_type = ? AND timestamp > ? AND resolved = 0',
            (metric_type, time.time() - cooldown_seconds)
        )
        count = c.fetchone()[0]
        conn.close()
        return count > 0
    
    def _create_alert(self, alert: Alert):
        """创建告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'INSERT INTO alerts (id, level, title, message, timestamp, agent_id, metric_type, value, threshold, acknowledged, resolved) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
            (alert.id, alert.level, alert.title, alert.message, alert.timestamp, alert.agent_id, alert.metric_type, alert.value, alert.threshold, 1 if alert.acknowledged else 0, 1 if alert.resolved else 0)
        )
        conn.commit()
        conn.close()
        
        self.stats["total_alerts"] += 1
        self.stats["alerts_by_level"][alert.level] = self.stats["alerts_by_level"].get(alert.level, 0) + 1
        
        # 触发回调
        for callback in self.alert_callbacks:
            try:
                callback(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def get_active_alerts(self) -> List[Dict]:
        """获取活跃告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'SELECT * FROM alerts WHERE resolved = 0 ORDER BY timestamp DESC'
        )
        alerts = []
        for row in c.fetchall():
            alerts.append({
                "id": row[0],
                "level": row[1],
                "title": row[2],
                "message": row[3],
                "timestamp": row[4],
                "agent_id": row[5],
                "metric_type": row[6],
                "value": row[7],
                "threshold": row[8],
                "acknowledged": bool(row[9]),
                "resolved": bool(row[10])
            })
        conn.close()
        return alerts
    
    def get_metrics(self, metric_type: Optional[str] = None, since: Optional[float] = None, limit: int = 100) -> List[Dict]:
        """获取指标"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        query = 'SELECT * FROM metrics WHERE 1=1'
        params = []
        
        if metric_type:
            query += ' AND metric_type = ?'
            params.append(metric_type)
        
        if since:
            query += ' AND timestamp > ?'
            params.append(since)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        c.execute(query, params)
        metrics = []
        for row in c.fetchall():
            metrics.append({
                "id": row[0],
                "timestamp": row[1],
                "metric_type": row[2],
                "value": row[3],
                "agent_id": row[4],
                "tags": json.loads(row[5]) if row[5] else {}
            })
        conn.close()
        return metrics
    
    def get_network_stats(self) -> Dict:
        """获取协作网络统计"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        now = time.time()
        last_5min = now - 300
        
        # 最近的指标
        stats = {}
        
        for metric_type in ["agent_online", "agent_offline", "task_queue_length", "task_failure", "message_latency"]:
            c.execute(
                'SELECT COUNT(*), AVG(value), MAX(value), MIN(value) FROM metrics WHERE metric_type = ? AND timestamp > ?',
                (metric_type, last_5min)
            )
            row = c.fetchone()
            if row[0] > 0:
                stats[metric_type] = {
                    "count": row[0],
                    "avg": row[1],
                    "max": row[2],
                    "min": row[3]
                }
        
        # 告警统计
        c.execute('SELECT COUNT(*) FROM alerts WHERE resolved = 0')
        stats["active_alerts"] = c.fetchone()[0]
        
        c.execute('SELECT level, COUNT(*) FROM alerts WHERE resolved = 0 GROUP BY level')
        stats["alerts_by_level"] = {row[0]: row[1] for row in c.fetchall()}
        
        conn.close()
        return stats
    
    def acknowledge_alert(self, alert_id: str):
        """确认告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE alerts SET acknowledged = 1 WHERE id = ?', (alert_id,))
        conn.commit()
        conn.close()
    
    def resolve_alert(self, alert_id: str):
        """解决告警"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('UPDATE alerts SET resolved = 1, resolved_at = ? WHERE id = ?', (time.time(), alert_id))
        conn.commit()
        conn.close()
    
    def start_monitoring(self, interval: float = 10.0):
        """启动监控"""
        if self.is_running:
            return
        
        self.is_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, args=(interval,), daemon=True)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """停止监控"""
        self.is_running = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
    
    def _monitor_loop(self, interval: float):
        """监控循环"""
        while self.is_running:
            try:
                self._collect_system_metrics()
            except Exception as e:
                print(f"Monitor loop error: {e}")
            
            time.sleep(interval)
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        # CPU使用率
        try:
            result = subprocess.run(['top', '-bn1'], capture_output=True, text=True, timeout=5)
            for line in result.stdout.split('\n'):
                if 'Cpu(s)' in line:
                    # 提取CPU使用率
                    parts = line.split()
                    idle = float(parts[-1].replace('%id,', ''))
                    cpu_usage = 100 - idle
                    self.record_metric("cpu_usage", cpu_usage, tags={"source": "system"})
                    break
        except Exception:
            pass
        
        # 内存使用率
        try:
            result = subprocess.run(['free', '-m'], capture_output=True, text=True, timeout=5)
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                total = float(parts[1])
                used = float(parts[2])
                memory_usage = (used / total * 100) if total > 0 else 0
                self.record_metric("memory_usage", memory_usage, tags={"source": "system"})
        except Exception:
            pass
        
        # 协作网络状态
        self._collect_collab_metrics()
    
    def _collect_collab_metrics(self):
        """收集协作网络指标"""
        # 读取协作状态
        state_files = [
            "/root/.openclaw/workspace/ultron/agents/task_queue.json",
            "/root/.openclaw/workspace/ultron/agents/communication_state.json",
            "/root/.openclaw/workspace/ultron/agent_mesh/health_recovery.py"
        ]
        
        # 任务队列长度
        try:
            if os.path.exists("/root/.openclaw/workspace/ultron/agents/data/task_queue.json"):
                with open("/root/.openclaw/workspace/ultron/agents/data/task_queue.json") as f:
                    data = json.load(f)
                    queue_len = len(data.get("pending_tasks", []))
                    self.record_metric("task_queue_length", float(queue_len), tags={"source": "collab"})
        except Exception:
            pass


class CollabAlertNotifier:
    """协作网络告警通知器"""
    
    def __init__(self, monitor: CollabMonitor):
        self.monitor = monitor
        self.dingtalk_webhook = os.environ.get("DINGTALK_WEBHOOK", "")
        self.last_notification_time = {}
    
    def send_dingtalk_alert(self, alert: Alert):
        """发送钉钉告警"""
        if not self.dingtalk_webhook:
            print(f"[DingTalk] Webhook not configured, skipping alert: {alert.title}")
            return
        
        # 冷却检查
        if alert.id in self.last_notification_time:
            if time.time() - self.last_notification_time[alert.id] < 300:
                return
        
        # 构建消息
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "critical": "🔴",
            "emergency": "🚨"
        }
        
        message = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{level_emoji.get(alert.level, '📢')} {alert.title}",
                "text": f"### {level_emoji.get(alert.level, '📢')} {alert.title}\n\n" +
                       f"**级别**: {alert.level.upper()}\n" +
                       f"**时间**: {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}\n" +
                       f"**消息**: {alert.message}\n" +
                       f"**指标**: {alert.metric_type} = {alert.value:.2f} (阈值: {alert.threshold})\n" +
                       f"**Agent**: {alert.agent_id or 'N/A'}"
            }
        }
        
        try:
            import urllib.request
            req = urllib.request.Request(
                self.dingtalk_webhook,
                data=json.dumps(message).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode())
                if result.get("errcode") == 0:
                    self.last_notification_time[alert.id] = time.time()
                    print(f"[DingTalk] Alert sent: {alert.id}")
                else:
                    print(f"[DingTalk] Error: {result}")
        except Exception as e:
            print(f"[DingTalk] Failed to send alert: {e}")
    
    def format_alert_summary(self, alerts: List[Dict]) -> str:
        """格式化告警摘要"""
        if not alerts:
            return "✅ 协作网络运行正常，无活跃告警"
        
        lines = ["📊 协作网络告警摘要\n"]
        
        # 按级别分组
        by_level = {}
        for a in alerts:
            level = a["level"]
            if level not in by_level:
                by_level[level] = []
            by_level[level].append(a)
        
        for level in ["emergency", "critical", "warning", "info"]:
            if level in by_level:
                count = len(by_level[level])
                emoji = {"emergency": "🚨", "critical": "🔴", "warning": "⚠️", "info": "ℹ️"}.get(level, "📢")
                lines.append(f"{emoji} {level.upper()}: {count}条")
        
        lines.append(f"\n共 {len(alerts)} 条活跃告警")
        
        return "\n".join(lines)


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description="Agent协作网络实时监控告警")
    parser.add_argument("command", choices=["start", "stop", "status", "alerts", "metrics", "stats"], help="命令")
    parser.add_argument("--interval", type=float, default=10.0, help="监控间隔(秒)")
    parser.add_argument("--metric-type", help="指标类型过滤")
    parser.add_argument("--limit", type=int, default=50, help="返回数量限制")
    
    args = parser.parse_args()
    
    monitor = CollabMonitor()
    
    if args.command == "start":
        notifier = CollabAlertNotifier(monitor)
        monitor.register_alert_callback(notifier.send_dingtalk_alert)
        monitor.start_monitoring(args.interval)
        print(f"监控已启动，间隔 {args.interval} 秒")
        try:
            while True:
                time.sleep(60)
                print(f"Stats: {monitor.stats}")
        except KeyboardInterrupt:
            monitor.stop_monitoring()
            print("监控已停止")
    
    elif args.command == "stop":
        monitor.stop_monitoring()
        print("监控已停止")
    
    elif args.command == "status":
        stats = monitor.get_network_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == "alerts":
        alerts = monitor.get_active_alerts()
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
    
    elif args.command == "metrics":
        metrics = monitor.get_metrics(args.metric_type, limit=args.limit)
        print(json.dumps(metrics, indent=2, ensure_ascii=False))
    
    elif args.command == "stats":
        print(json.dumps(monitor.stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()