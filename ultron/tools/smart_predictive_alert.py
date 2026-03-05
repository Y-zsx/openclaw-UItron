#!/usr/bin/env python3
"""
智能预测告警系统 (Smart Predictive Alert System)
第46世: 智能预测告警

功能:
1. 动态阈值调整 - 基于历史数据自动调整告警阈值
2. 预测性告警 - 基于趋势分析预测未来故障
3. 智能告警聚合 - 减少告警风暴，支持告警收敛
4. 告警关联分析 - 找出告警根本原因
5. 自适应学习 - 根据系统行为自动优化告警规则
6. 多通道通知 - 钉钉、邮件、Webhook
"""

import asyncio
import json
import sqlite3
import time
import threading
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from collections import deque
from enum import Enum
import statistics
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============ 配置 ============
DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "smart_alerts.db"

# 预测配置
CONFIG = {
    "prediction_window": 30,       # 预测时间窗口(分钟)
    "trend_analysis_window": 10,   # 趋势分析窗口(数据点数)
    "baseline_window": 24,         # 基线计算窗口(小时)
    "alert_cooldown": 300,         # 告警冷却时间(秒)
    "aggregation_window": 60,      # 告警聚合窗口(秒)
    "correlation_window": 300,     # 告警关联时间窗口(秒)
    "learning_interval": 3600,     # 学习间隔(秒)
    "min_baseline_samples": 50,    # 基线最少样本数
}

# 通知配置
NOTIFY_CONFIG = {
    "dingtalk_webhook": "",  # 可配置
    "email_smtp": "",
    "webhook_url": "",
}


class AlertSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertStatus(Enum):
    PENDING = "pending"
    FIRING = "firing"
    RESOLVED = "resolved"
    SUPPRESSED = "suppressed"


# ============ 数据模型 ============
@dataclass
class MetricPoint:
    """指标数据点"""
    timestamp: float
    service: str
    metric: str
    value: float


@dataclass
class AlertEvent:
    """告警事件"""
    id: str
    rule_id: str
    service: str
    metric: str
    severity: str
    message: str
    value: float
    threshold: float
    predicted_value: Optional[float]  # 预测值
    probability: Optional[float]       # 预测概率
    trend: str                         # rising/falling/stable
    status: str
    created_at: datetime
    fired_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    related_alerts: List[str] = field(default_factory=list)
    annotations: Dict = field(default_factory=dict)


@dataclass
class AlertRule:
    """告警规则"""
    id: str
    name: str
    service: str
    metric: str
    condition: str          # gt/lt/gte/lte/eq/rising/falling
    threshold: float
    dynamic_threshold: bool  # 是否启用动态阈值
    severity: str
    enabled: bool = True
    consecutive: int = 1
    cooldown: int = 300


@dataclass
class ThresholdBaseline:
    """阈值基线"""
    service: str
    metric: str
    mean: float
    std: float
    p50: float
    p75: float
    p90: float
    p95: float
    p99: float
    samples: int
    updated_at: datetime


# ============ 数据库管理 ============
class SmartAlertDB:
    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            # 指标历史
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    service TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    value REAL NOT NULL
                )
            """)
            
            # 告警事件
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_events (
                    id TEXT PRIMARY KEY,
                    rule_id TEXT NOT NULL,
                    service TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    value REAL,
                    threshold REAL,
                    predicted_value REAL,
                    probability REAL,
                    trend TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    fired_at TEXT,
                    resolved_at TEXT,
                    related_alerts TEXT,
                    annotations TEXT
                )
            """)
            
            # 告警规则
            conn.execute("""
                CREATE TABLE IF NOT EXISTS alert_rules (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    service TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    condition TEXT NOT NULL,
                    threshold REAL NOT NULL,
                    dynamic_threshold INTEGER DEFAULT 0,
                    severity TEXT NOT NULL,
                    enabled INTEGER DEFAULT 1,
                    consecutive INTEGER DEFAULT 1,
                    cooldown INTEGER DEFAULT 300
                )
            """)
            
            # 阈值基线
            conn.execute("""
                CREATE TABLE IF NOT EXISTS threshold_baselines (
                    service TEXT NOT NULL,
                    metric TEXT NOT NULL,
                    mean REAL,
                    std REAL,
                    p50 REAL,
                    p75 REAL,
                    p90 REAL,
                    p95 REAL,
                    p99 REAL,
                    samples INTEGER,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (service, metric)
                )
            """)
            
            # 聚合告警
            conn.execute("""
                CREATE TABLE IF NOT EXISTS aggregated_alerts (
                    id TEXT PRIMARY KEY,
                    group_key TEXT NOT NULL,
                    alert_count INTEGER,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    services TEXT,
                    created_at TEXT NOT NULL,
                    expires_at TEXT
                )
            """)
            
            # 索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_metrics ON metrics_history(timestamp, service, metric)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_alerts ON alert_events(created_at, status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_aggregated ON aggregated_alerts(expires_at)")
            
            conn.commit()
    
    def save_metric(self, metric: MetricPoint):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO metrics_history (timestamp, service, metric, value) VALUES (?, ?, ?, ?)",
                (metric.timestamp, metric.service, metric.metric, metric.value)
            )
            conn.commit()
    
    def get_metrics(self, service: str, metric: str, hours: int = 24) -> List[MetricPoint]:
        cutoff = time.time() - (hours * 3600)
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT timestamp, service, metric, value FROM metrics_history
                WHERE service = ? AND metric = ? AND timestamp > ?
                ORDER BY timestamp ASC
            """, (service, metric, cutoff)).fetchall()
        
        return [MetricPoint(timestamp=r["timestamp"], service=r["service"], 
                           metric=r["metric"], value=r["value"]) for r in rows]
    
    def save_alert(self, alert: AlertEvent):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alert_events
                (id, rule_id, service, metric, severity, message, value, threshold, 
                 predicted_value, probability, trend, status, created_at, fired_at, 
                 resolved_at, related_alerts, annotations)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (alert.id, alert.rule_id, alert.service, alert.metric, alert.severity,
                  alert.message, alert.value, alert.threshold, alert.predicted_value,
                  alert.probability, alert.trend, alert.status, alert.created_at.isoformat(),
                  alert.fired_at.isoformat() if alert.fired_at else None,
                  alert.resolved_at.isoformat() if alert.resolved_at else None,
                  json.dumps(alert.related_alerts), json.dumps(alert.annotations)))
            conn.commit()
    
    def get_active_alerts(self) -> List[AlertEvent]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM alert_events WHERE status IN ('pending', 'firing')
                ORDER BY created_at DESC
            """).fetchall()
        
        return [self._row_to_alert(r) for r in rows]
    
    def get_recent_alerts(self, minutes: int = 60) -> List[AlertEvent]:
        cutoff = (datetime.now() - timedelta(minutes=minutes)).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT * FROM alert_events WHERE created_at > ?
                ORDER BY created_at DESC
            """, (cutoff,)).fetchall()
        
        return [self._row_to_alert(r) for r in rows]
    
    def _row_to_alert(self, row) -> AlertEvent:
        return AlertEvent(
            id=row["id"], rule_id=row["rule_id"], service=row["service"],
            metric=row["metric"], severity=row["severity"], message=row["message"],
            value=row["value"], threshold=row["threshold"],
            predicted_value=row["predicted_value"], probability=row["probability"],
            trend=row["trend"], status=row["status"],
            created_at=datetime.fromisoformat(row["created_at"]),
            fired_at=datetime.fromisoformat(row["fired_at"]) if row["fired_at"] else None,
            resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            related_alerts=json.loads(row["related_alerts"]) if row["related_alerts"] else [],
            annotations=json.loads(row["annotations"]) if row["annotations"] else {}
        )
    
    def save_rule(self, rule: AlertRule):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO alert_rules
                (id, name, service, metric, condition, threshold, dynamic_threshold, 
                 severity, enabled, consecutive, cooldown)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (rule.id, rule.name, rule.service, rule.metric, rule.condition,
                  rule.threshold, 1 if rule.dynamic_threshold else 0, rule.severity,
                  1 if rule.enabled else 0, rule.consecutive, rule.cooldown))
            conn.commit()
    
    def get_rules(self) -> List[AlertRule]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("SELECT * FROM alert_rules WHERE enabled = 1").fetchall()
        
        return [AlertRule(
            id=r["id"], name=r["name"], service=r["service"], metric=r["metric"],
            condition=r["condition"], threshold=r["threshold"],
            dynamic_threshold=r["dynamic_threshold"] == 1, severity=r["severity"],
            enabled=r["enabled"] == 1, consecutive=r["consecutive"], cooldown=r["cooldown"]
        ) for r in rows]
    
    def save_baseline(self, baseline: ThresholdBaseline):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO threshold_baselines
                (service, metric, mean, std, p50, p75, p90, p95, p99, samples, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (baseline.service, baseline.metric, baseline.mean, baseline.std,
                  baseline.p50, baseline.p75, baseline.p90, baseline.p95, baseline.p99,
                  baseline.samples, baseline.updated_at.isoformat()))
            conn.commit()
    
    def get_baseline(self, service: str, metric: str) -> Optional[ThresholdBaseline]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("""
                SELECT * FROM threshold_baselines WHERE service = ? AND metric = ?
            """, (service, metric)).fetchone()
        
        if row:
            return ThresholdBaseline(
                service=row["service"], metric=row["metric"], mean=row["mean"],
                std=row["std"], p50=row["p50"], p75=row["p75"], p90=row["p90"],
                p95=row["p95"], p99=row["p99"], samples=row["samples"],
                updated_at=datetime.fromisoformat(row["updated_at"])
            )
        return None
    
    def save_aggregated(self, alert_id: str, group_key: str, count: int, 
                       severity: str, message: str, services: List[str], expires_at: datetime):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO aggregated_alerts
                (id, group_key, alert_count, severity, message, services, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (alert_id, group_key, count, severity, message, json.dumps(services),
                  datetime.now().isoformat(), expires_at.isoformat()))
            conn.commit()


# ============ 趋势分析引擎 ============
class TrendAnalyzer:
    """趋势分析与预测引擎"""
    
    @staticmethod
    def calculate_trend(values: List[float], window: int = 5) -> str:
        """计算趋势: rising/falling/stable"""
        if len(values) < window:
            return "unknown"
        
        recent = values[-window:]
        older = values[-window*2:-window] if len(values) >= window*2 else values[:-window]
        
        if not older:
            return "unknown"
        
        recent_avg = statistics.mean(recent)
        older_avg = statistics.mean(older)
        
        change_pct = ((recent_avg - older_avg) / older_avg * 100) if older_avg > 0 else 0
        
        if change_pct > 15:
            return "rising"
        elif change_pct < -15:
            return "falling"
        return "stable"
    
    @staticmethod
    def predict_next(values: List[float], window: int = 5) -> float:
        """预测下一个值 (线性回归)"""
        if len(values) < 2:
            return values[-1] if values else 0
        
        # 简单线性回归
        n = len(values)
        x = list(range(n))
        y = values
        
        x_mean = statistics.mean(x)
        y_mean = statistics.mean(y)
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return values[-1]
        
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # 预测下一个点
        return slope * n + intercept
    
    @staticmethod
    def calculate_probability(current: float, threshold: float, trend: str) -> float:
        """计算预测概率"""
        if trend == "rising":
            # 上升趋势，概率较高
            proximity = min(current / threshold, 1.2)
            return min(proximity * 0.6 + 0.4, 1.0)
        elif trend == "stable":
            proximity = min(current / threshold, 1.0)
            return min(proximity * 0.5, 0.9)
        else:  # falling
            return max(0.1, (current / threshold) * 0.2)


# ============ 动态阈值引擎 ============
class DynamicThresholdEngine:
    """动态阈值引擎 - 基于历史数据自动调整阈值"""
    
    def __init__(self, db: SmartAlertDB):
        self.db = db
    
    def calculate_baseline(self, service: str, metric: str) -> Optional[ThresholdBaseline]:
        """计算基线统计"""
        metrics = self.db.get_metrics(service, metric, hours=CONFIG["baseline_window"])
        
        if len(metrics) < CONFIG["min_baseline_samples"]:
            return None
        
        values = [m.value for m in metrics]
        
        baseline = ThresholdBaseline(
            service=service,
            metric=metric,
            mean=statistics.mean(values),
            std=statistics.stdev(values) if len(values) > 1 else 0,
            p50=float(sorted(values)[len(values) // 2]),
            p75=float(sorted(values)[int(len(values) * 0.75)]),
            p90=float(sorted(values)[int(len(values) * 0.90)]),
            p95=float(sorted(values)[int(len(values) * 0.95)]),
            p99=float(sorted(values)[int(len(values) * 0.99)]),
            samples=len(values),
            updated_at=datetime.now()
        )
        
        self.db.save_baseline(baseline)
        return baseline
    
    def get_dynamic_threshold(self, rule: AlertRule, baseline: ThresholdBaseline) -> float:
        """根据基线动态计算阈值"""
        if not rule.dynamic_threshold:
            return rule.threshold
        
        # 基于P95或P99动态调整
        # 例如: P95 * 1.5 作为告警阈值
        multiplier = 1.5
        return baseline.p95 * multiplier
    
    def should_adjust_threshold(self, baseline: ThresholdBaseline) -> bool:
        """判断是否需要调整阈值"""
        # 如果样本足够多，且基线已超过1小时未更新
        time_since_update = (datetime.now() - baseline.updated_at).total_seconds()
        return baseline.samples >= CONFIG["min_baseline_samples"] and time_since_update > 3600


# ============ 告警聚合引擎 ============
class AlertAggregationEngine:
    """告警聚合引擎 - 减少告警风暴"""
    
    def __init__(self, db: SmartAlertDB):
        self.db = db
        self.pending_alerts: Dict[str, List[AlertEvent]] = {}
        self.aggregation_groups: Dict[str, str] = {}  # alert_id -> group_key
    
    def should_aggregate(self, alerts: List[AlertEvent]) -> bool:
        """判断是否应该聚合"""
        if len(alerts) < 3:
            return False
        
        # 检查时间窗口
        time_spread = (alerts[-1].created_at - alerts[0].created_at).total_seconds()
        return time_spread < CONFIG["aggregation_window"]
    
    def generate_group_key(self, alerts: List[AlertEvent]) -> str:
        """生成聚合组key"""
        # 基于服务和告警类型分组
        services = sorted(set(a.service for a in alerts))
        metrics = sorted(set(a.metric for a in alerts))
        
        key_str = f"{'_'.join(services)}_{'_'.join(metrics)}"
        return hashlib.md5(key_str.encode()).hexdigest()[:12]
    
    def aggregate(self, alerts: List[AlertEvent]) -> Optional[AlertEvent]:
        """聚合告警"""
        if not self.should_aggregate(alerts):
            return None
        
        group_key = self.generate_group_key(alerts)
        most_severe = max(alerts, key=lambda a: self._severity_score(a.severity))
        
        # 创建聚合告警
        aggregated = AlertEvent(
            id=f"agg_{group_key}_{int(time.time())}",
            rule_id="aggregated",
            service=", ".join(set(a.service for a in alerts)),
            metric=", ".join(set(a.metric for a in alerts)),
            severity=most_severe.severity,
            message=f"聚合告警: {len(alerts)}个告警事件 - {most_severe.message[:50]}...",
            value=most_severe.value,
            threshold=most_severe.threshold,
            predicted_value=most_severe.predicted_value,
            probability=most_severe.probability,
            trend=most_severe.trend,
            status=AlertStatus.FIRING.value,
            created_at=alerts[0].created_at,
            fired_at=datetime.now(),
            related_alerts=[a.id for a in alerts]
        )
        
        # 保存到数据库
        services = list(set(a.service for a in alerts))
        expires_at = datetime.now() + timedelta(seconds=CONFIG["aggregation_window"])
        self.db.save_aggregated(aggregated.id, group_key, len(alerts), 
                               aggregated.severity, aggregated.message, services, expires_at)
        
        return aggregated
    
    def _severity_score(self, severity: str) -> int:
        scores = {"info": 1, "warning": 2, "error": 3, "critical": 4}
        return scores.get(severity, 0)


# ============ 告警关联引擎 ============
class AlertCorrelationEngine:
    """告警关联分析引擎 - 找出根本原因"""
    
    def __init__(self, db: SmartAlertDB):
        self.db = db
    
    def find_correlations(self, alerts: List[AlertEvent]) -> Dict[str, List[str]]:
        """查找告警关联"""
        correlations = {}
        
        # 按服务分组
        by_service: Dict[str, List[AlertEvent]] = {}
        for alert in alerts:
            if alert.service not in by_service:
                by_service[alert.service] = []
            by_service[alert.service].append(alert)
        
        # 对于同一服务的多个告警，找出根因
        for service, service_alerts in by_service.items():
            if len(service_alerts) < 2:
                continue
            
            # 假设最早发生的告警是根因
            root = min(service_alerts, key=lambda a: a.created_at)
            dependents = [a.id for a in service_alerts if a.id != root.id]
            
            if dependents:
                correlations[root.id] = dependents
        
        return correlations
    
    def identify_root_cause(self, alerts: List[AlertEvent]) -> Optional[AlertEvent]:
        """识别根本原因告警"""
        if not alerts:
            return None
        
        # 规则1: 最早发生的
        # 规则2: 如果有"服务宕机"相关告警，优先选择
        for alert in sorted(alerts, key=lambda a: a.created_at):
            if "宕机" in alert.message or "down" in alert.message.lower():
                return alert
        
        return min(alerts, key=lambda a: a.created_at)


# ============ 智能告警引擎 ============
class SmartAlertEngine:
    """智能告警引擎 - 主控制器"""
    
    def __init__(self):
        self.db = SmartAlertDB(DB_PATH)
        self.trend_analyzer = TrendAnalyzer()
        self.threshold_engine = DynamicThresholdEngine(self.db)
        self.aggregation_engine = AlertAggregationEngine(self.db)
        self.correlation_engine = AlertCorrelationEngine(self.db)
        
        # 缓存
        self.baselines: Dict[str, ThresholdBaseline] = {}
        self.last_alert_time: Dict[str, float] = {}
        
        # 服务和指标配置
        self.services = {
            "system": ["cpu_percent", "memory_percent", "disk_percent", "load_avg_1"],
            "gateway": ["cpu_percent", "memory_percent", "response_time", "connections"],
            "browser": ["cpu_percent", "memory_percent", "tabs"],
            "agent-orchestration": ["cpu_percent", "memory_percent", "response_time", "error_rate"],
            "agent-monitor": ["cpu_percent", "memory_percent", "alert_count"],
            "agent-scaling": ["cpu_percent", "memory_percent", "scaling_events"],
        }
        
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认规则"""
        default_rules = [
            # 系统级
            AlertRule("rule-sys-cpu", "系统CPU过高", "system", "cpu_percent", "rising", 80, True, "warning"),
            AlertRule("rule-sys-mem", "系统内存过高", "system", "memory_percent", "rising", 85, True, "warning"),
            AlertRule("rule-sys-disk", "磁盘使用率过高", "system", "disk_percent", "gte", 90, False, "critical"),
            
            # 服务级
            AlertRule("rule-gw-resp", "Gateway响应时间过长", "gateway", "response_time", "rising", 2000, True, "error"),
            AlertRule("rule-ao-err", "Agent编排错误率", "agent-orchestration", "error_rate", "gte", 5, False, "error"),
        ]
        
        for rule in default_rules:
            self.db.save_rule(rule)
    
    def _generate_id(self) -> str:
        return f"alert_{int(time.time() * 1000)}"
    
    async def collect_metrics(self):
        """收集指标数据"""
        import psutil
        import socket
        
        now = time.time()
        
        # 系统指标
        self.db.save_metric(MetricPoint(now, "system", "cpu_percent", psutil.cpu_percent(interval=0.5)))
        self.db.save_metric(MetricPoint(now, "system", "memory_percent", psutil.virtual_memory().percent))
        self.db.save_metric(MetricPoint(now, "system", "disk_percent", psutil.disk_usage('/').percent))
        self.db.save_metric(MetricPoint(now, "system", "load_avg_1", psutil.getloadavg()[0]))
        
        # Gateway
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', 18789))
            sock.close()
            if result == 0:
                self.db.save_metric(MetricPoint(now, "gateway", "response_time", 10))
                self.db.save_metric(MetricPoint(now, "gateway", "connections", 1))
            else:
                self.db.save_metric(MetricPoint(now, "gateway", "response_time", 9999))
        except:
            self.db.save_metric(MetricPoint(now, "gateway", "response_time", 9999))
    
    def evaluate_rules(self) -> List[AlertEvent]:
        """评估所有告警规则"""
        alerts = []
        rules = self.db.get_rules()
        
        for rule in rules:
            alert = self._evaluate_rule(rule)
            if alert:
                alerts.append(alert)
        
        # 关联分析
        if alerts:
            correlations = self.correlation_engine.find_correlations(alerts)
            for root_id, dependent_ids in correlations.items():
                for alert in alerts:
                    if alert.id == root_id:
                        alert.related_alerts = dependent_ids
                        break
        
        # 聚合处理
        if len(alerts) >= 3:
            aggregated = self.aggregation_engine.aggregate(alerts)
            if aggregated:
                # 用聚合告警替代多个小告警
                alerts = [aggregated]
        
        return alerts
    
    def _evaluate_rule(self, rule: AlertRule) -> Optional[AlertEvent]:
        """评估单个规则"""
        # 冷却检查
        if rule.id in self.last_alert_time:
            time_since_last = time.time() - self.last_alert_time[rule.id]
            if time_since_last < rule.cooldown:
                return None
        
        # 获取历史数据
        metrics = self.db.get_metrics(rule.service, rule.metric, hours=1)
        if len(metrics) < 3:
            return None
        
        values = [m.value for m in metrics]
        
        # 趋势分析
        trend = self.trend_analyzer.calculate_trend(values)
        
        # 动态阈值
        current_value = values[-1]
        threshold = rule.threshold
        
        if rule.dynamic_threshold:
            baseline = self._get_baseline(rule.service, rule.metric)
            if baseline:
                threshold = self.threshold_engine.get_dynamic_threshold(rule, baseline)
        
        # 条件检查
        triggered = False
        if rule.condition == "rising" and trend == "rising":
            triggered = True
        elif rule.condition == "falling" and trend == "falling":
            triggered = True
        elif rule.condition == "gte" and current_value >= threshold:
            triggered = True
        elif rule.condition == "gt" and current_value > threshold:
            triggered = True
        elif rule.condition == "lte" and current_value <= threshold:
            triggered = True
        elif rule.condition == "lt" and current_value < threshold:
            triggered = True
        
        if not triggered:
            return None
        
        # 预测分析
        predicted_value = self.trend_analyzer.predict_next(values)
        probability = self.trend_analyzer.calculate_probability(current_value, threshold, trend)
        
        # 创建告警
        alert = AlertEvent(
            id=self._generate_id(),
            rule_id=rule.id,
            service=rule.service,
            metric=rule.metric,
            severity=rule.severity,
            message=f"{rule.name}: {rule.service}.{rule.metric}={current_value:.1f}, 趋势={trend}, 预测={predicted_value:.1f}",
            value=current_value,
            threshold=threshold,
            predicted_value=predicted_value,
            probability=probability,
            trend=trend,
            status=AlertStatus.PENDING.value,
            created_at=datetime.now()
        )
        
        # 保存并触发
        self.db.save_alert(alert)
        self.last_alert_time[rule.id] = time.time()
        
        # 更新为firing状态
        alert.status = AlertStatus.FIRING.value
        alert.fired_at = datetime.now()
        self.db.save_alert(alert)
        
        return alert
    
    def _get_baseline(self, service: str, metric: str) -> Optional[ThresholdBaseline]:
        """获取或计算基线"""
        key = f"{service}:{metric}"
        if key not in self.baselines:
            self.baselines[key] = self.db.get_baseline(service, metric)
            if not self.baselines[key]:
                self.baselines[key] = self.threshold_engine.calculate_baseline(service, metric)
        return self.baselines[key]
    
    async def run_learning_cycle(self):
        """运行学习周期 - 更新基线"""
        for service, metrics in self.services.items():
            for metric in metrics:
                baseline = self._get_baseline(service, metric)
                if baseline and self.threshold_engine.should_adjust_threshold(baseline):
                    # 重新计算基线
                    new_baseline = self.threshold_engine.calculate_baseline(service, metric)
                    if new_baseline:
                        self.baselines[f"{service}:{metric}"] = new_baseline
    
    def get_status(self) -> Dict:
        """获取系统状态"""
        active_alerts = self.db.get_active_alerts()
        recent_alerts = self.db.get_recent_alerts(minutes=60)
        
        severity_counts = {"critical": 0, "error": 0, "warning": 0, "info": 0}
        for alert in active_alerts:
            if alert.severity in severity_counts:
                severity_counts[alert.severity] += 1
        
        return {
            "status": "running",
            "active_alerts": len(active_alerts),
            "severity_counts": severity_counts,
            "recent_alerts": len(recent_alerts),
            "baselines": len(self.baselines),
            "timestamp": datetime.now().isoformat()
        }


# ============ 通知系统 ============
class NotificationManager:
    """通知管理器"""
    
    def __init__(self):
        self.handlers = []
    
    def add_handler(self, handler):
        self.handlers.append(handler)
    
    async def send(self, alert: AlertEvent):
        for handler in self.handlers:
            try:
                await handler(alert)
            except Exception as e:
                logger.error(f"Notification handler error: {e}")
    
    async def send_dingtalk(self, webhook: str, alert: AlertEvent):
        """发送钉钉通知"""
        if not webhook:
            return
        
        import aiohttp
        msg = {
            "msgtype": "text",
            "text": {
                "content": f"🔔 [{alert.severity.upper()}] {alert.message}\n服务: {alert.service}\n时间: {alert.created_at.isoformat()}"
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                await session.post(webhook, json=msg)
        except Exception as e:
            logger.error(f"DingTalk notification failed: {e}")


# ============ 主服务 ============
class SmartPredictiveAlertService:
    def __init__(self):
        self.engine = SmartAlertEngine()
        self.notifier = NotificationManager()
        self._running = False
    
    async def run_cycle(self):
        """运行一个监控周期"""
        # 1. 收集指标
        await self.engine.collect_metrics()
        
        # 2. 评估规则
        alerts = self.engine.evaluate_rules()
        
        # 3. 发送通知
        for alert in alerts:
            await self.notifier.send(alert)
            logger.warning(f"🔔 [{alert.severity.upper()}] {alert.message}")
        
        # 4. 定期学习
        await self.engine.run_learning_cycle()
        
        return alerts
    
    async def start(self):
        """启动服务"""
        self._running = True
        logger.info("🔮 Smart Predictive Alert Service started")
        
        while self._running:
            try:
                alerts = await self.run_cycle()
            except Exception as e:
                logger.error(f"Alert cycle error: {e}")
            
            await asyncio.sleep(60)
    
    def stop(self):
        self._running = False


# ============ API服务 ============
from aiohttp import web

class SmartAlertAPI:
    def __init__(self, service: SmartPredictiveAlertService):
        self.service = service
        self.app = web.Application()
        self._setup_routes()
    
    def _setup_routes(self):
        self.app.router.add_get("/health", self.health)
        self.app.router.add_get("/status", self.status)
        self.app.router.add_get("/alerts", self.list_alerts)
        self.app.router.add_get("/alerts/active", self.active_alerts)
        self.app.router.add_get("/rules", self.list_rules)
        self.app.router.add_post("/rules", self.add_rule)
        self.app.router.add_get("/baselines", self.list_baselines)
        self.app.router.add_post("/collect", self.manual_collect)
        self.app.router.add_post("/evaluate", self.manual_evaluate)
    
    async def health(self, request):
        return web.json_response({"status": "ok", "service": "smart-predictive-alert"})
    
    async def status(self, request):
        return web.json_response(self.service.engine.get_status())
    
    async def list_alerts(self, request):
        minutes = int(request.query.get("minutes", 60))
        alerts = self.service.engine.db.get_recent_alerts(minutes)
        return web.json_response({
            "alerts": [{
                "id": a.id, "service": a.service, "metric": a.metric,
                "severity": a.severity, "message": a.message, "value": a.value,
                "predicted_value": a.predicted_value, "probability": a.probability,
                "trend": a.trend, "status": a.status, "created_at": a.created_at.isoformat()
            } for a in alerts]
        })
    
    async def active_alerts(self, request):
        alerts = self.service.engine.db.get_active_alerts()
        return web.json_response({
            "alerts": [{
                "id": a.id, "service": a.service, "metric": a.metric,
                "severity": a.severity, "message": a.message,
                "created_at": a.created_at.isoformat()
            } for a in alerts]
        })
    
    async def list_rules(self, request):
        rules = self.service.engine.db.get_rules()
        return web.json_response({
            "rules": [{
                "id": r.id, "name": r.name, "service": r.service, "metric": r.metric,
                "condition": r.condition, "threshold": r.threshold,
                "dynamic_threshold": r.dynamic_threshold, "severity": r.severity
            } for r in rules]
        })
    
    async def add_rule(self, request):
        data = await request.json()
        rule = AlertRule(
            id=data.get("id", f"rule_{int(time.time())}"),
            name=data["name"],
            service=data["service"],
            metric=data["metric"],
            condition=data["condition"],
            threshold=data["threshold"],
            dynamic_threshold=data.get("dynamic_threshold", False),
            severity=data["severity"]
        )
        self.service.engine.db.save_rule(rule)
        return web.json_response({"success": True, "rule_id": rule.id})
    
    async def list_baselines(self, request):
        baselines = self.service.engine.baselines
        return web.json_response({
            "baselines": [{
                "service": b.service, "metric": b.metric,
                "mean": b.mean, "std": b.std, "p95": b.p95,
                "samples": b.samples, "updated_at": b.updated_at.isoformat()
            } for b in baselines.values()]
        })
    
    async def manual_collect(self, request):
        await self.service.engine.collect_metrics()
        return web.json_response({"status": "collected"})
    
    async def manual_evaluate(self, request):
        alerts = self.service.engine.evaluate_rules()
        return web.json_response({
            "triggered": len(alerts),
            "alerts": [{"id": a.id, "message": a.message} for a in alerts]
        })
    
    def run(self, host="0.0.0.0", port=18175):
        import threading
        def _run():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            runner = web.AppRunner(self.app)
            loop.run_until_complete(runner.setup())
            site = web.TCPSite(runner, host, port)
            loop.run_until_complete(site.start())
            print(f"✓ Smart Predictive Alert API running on port {port}")
            loop.run_forever()
        thread = threading.Thread(target=_run, daemon=True)
        thread.start()
        return thread


# ============ 主入口 ============
async def main():
    service = SmartPredictiveAlertService()
    api = SmartAlertAPI(service)
    
    # 启动API
    api.run(port=18175)
    
    # 启动主服务
    asyncio.create_task(service.start())
    
    # 保持运行
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())