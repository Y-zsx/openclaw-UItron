#!/usr/bin/env python3
"""
智能告警分析和预测系统 v2
Intelligent Alert Analysis and Prediction System

功能:
1. 多维度趋势预测 (指数平滑 + 线性回归 + 季节性)
2. 告警关联分析 (因果关系图谱)
3. 根因诊断 (Root Cause Analysis)
4. 动态阈值 (基于历史自适应)
5. 异常模式识别
6. 预测性告警

第33世: 实现智能告警分析和预测
"""

import json
import os
import time
import sqlite3
import statistics
import subprocess
import threading
from datetime import datetime, timedelta
from collections import deque, defaultdict
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
import uuid
import urllib.request
import urllib.error

# 配置
DATA_DIR = "/root/.openclaw/workspace/ultron/monitor/data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "intelligent_alerts.db")
HISTORY_FILE = os.path.join(DATA_DIR, "prediction_history.json")
CAUSALITY_FILE = os.path.join(DATA_DIR, "causality_graph.json")
THRESHOLD_FILE = os.path.join(DATA_DIR, "dynamic_thresholds.json")
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class PredictionType(Enum):
    LINEAR = "linear"           # 线性回归
    EXPONENTIAL = "exponential" # 指数平滑
    SEASONAL = "seasonal"       # 季节性
    COMBINED = "combined"       # 综合预测


@dataclass
class MetricData:
    """指标数据"""
    timestamp: float
    metric_name: str
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Prediction:
    """预测结果"""
    metric_name: str
    current_value: float
    predicted_value: float
    confidence: float  # 0-1
    time_to_threshold: Optional[int]  # 秒
    trend: str  # rising/falling/stable/spiking/dropping
    prediction_type: str
    model_accuracy: float  # 历史准确率


@dataclass
class AlertAnalysis:
    """告警分析结果"""
    alert_id: str
    level: str
    title: str
    message: str
    root_cause: Optional[str]  # 根因
    related_alerts: List[str]  # 关联告警
    predicted_occurrence: Optional[float]  # 预测发生概率
    recommended_actions: List[str]  # 建议操作
    timestamp: float


@dataclass
class DynamicThreshold:
    """动态阈值"""
    metric_name: str
    base_threshold: float
    current_threshold: float
    min_threshold: float
    max_threshold: float
    adaptation_factor: float  # 基于历史波动自适应
    last_updated: float


class IntelligentAlertAnalyzer:
    """智能告警分析和预测器"""
    
    def __init__(self, history_size: int = 100):
        self.history_size = history_size
        self.db_path = DB_PATH
        self._init_db()
        
        # 指标历史缓存
        self.metrics_history: Dict[str, deque] = defaultdict(lambda: deque(maxlen=history_size))
        
        # 告警历史
        self.alert_history: deque = deque(maxlen=500)
        
        # 动态阈值
        self.dynamic_thresholds: Dict[str, DynamicThreshold] = {}
        self._load_dynamic_thresholds()
        
        # 因果关系图谱
        self.causality_graph = self._load_causality_graph()
        
        # 预测模型
        self.prediction_models: Dict[str, Dict] = {}
        
        # 通知冷却
        self.notification_cooldown: Dict[str, float] = {}
        
        # 启动后台趋势收集
        self._collect_thread: Optional[threading.Thread] = None
        self._running = False
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 指标历史表
        c.execute('''CREATE TABLE IF NOT EXISTS metrics_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            metric_name TEXT,
            value REAL,
            tags TEXT
        )''')
        
        # 预测结果表
        c.execute('''CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            metric_name TEXT,
            current_value REAL,
            predicted_value REAL,
            confidence REAL,
            time_to_threshold INTEGER,
            trend TEXT,
            prediction_type TEXT
        )''')
        
        # 告警分析表
        c.execute('''CREATE TABLE IF NOT EXISTS alert_analysis (
            id TEXT PRIMARY KEY,
            timestamp REAL,
            level TEXT,
            title TEXT,
            message TEXT,
            root_cause TEXT,
            related_alerts TEXT,
            predicted_occurrence REAL,
            recommended_actions TEXT
        )''')
        
        # 动态阈值历史
        c.execute('''CREATE TABLE IF NOT EXISTS threshold_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL,
            metric_name TEXT,
            threshold_value REAL,
            is_breach INTEGER
        )''')
        
        c.execute('CREATE INDEX IF NOT EXISTS idx_metrics_name ON metrics_history(metric_name)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_predictions_time ON predictions(timestamp)')
        
        conn.commit()
        conn.close()
    
    def _load_dynamic_thresholds(self) -> Dict:
        """加载动态阈值配置"""
        if os.path.exists(THRESHOLD_FILE):
            try:
                with open(THRESHOLD_FILE) as f:
                    data = json.load(f)
                    for name, th in data.items():
                        self.dynamic_thresholds[name] = DynamicThreshold(**th)
            except Exception as e:
                print(f"加载动态阈值失败: {e}")
        
        # 默认阈值配置
        default_thresholds = {
            "cpu_usage": DynamicThreshold(
                metric_name="cpu_usage", base_threshold=80, current_threshold=80,
                min_threshold=60, max_threshold=95, adaptation_factor=0.1, last_updated=time.time()
            ),
            "memory_usage": DynamicThreshold(
                metric_name="memory_usage", base_threshold=85, current_threshold=85,
                min_threshold=70, max_threshold=95, adaptation_factor=0.1, last_updated=time.time()
            ),
            "disk_usage": DynamicThreshold(
                metric_name="disk_usage", base_threshold=90, current_threshold=90,
                min_threshold=80, max_threshold=98, adaptation_factor=0.05, last_updated=time.time()
            ),
            "load_1m": DynamicThreshold(
                metric_name="load_1m", base_threshold=5.0, current_threshold=5.0,
                min_threshold=2.0, max_threshold=10.0, adaptation_factor=0.15, last_updated=time.time()
            ),
            "task_queue_length": DynamicThreshold(
                metric_name="task_queue_length", base_threshold=100, current_threshold=100,
                min_threshold=50, max_threshold=200, adaptation_factor=0.2, last_updated=time.time()
            ),
            "message_latency": DynamicThreshold(
                metric_name="message_latency", base_threshold=10.0, current_threshold=10.0,
                min_threshold=5.0, max_threshold=30.0, adaptation_factor=0.15, last_updated=time.time()
            )
        }
        
        for name, th in default_thresholds.items():
            if name not in self.dynamic_thresholds:
                self.dynamic_thresholds[name] = th
        
        self._save_dynamic_thresholds()
    
    def _save_dynamic_thresholds(self):
        """保存动态阈值"""
        data = {name: asdict(th) for name, th in self.dynamic_thresholds.items()}
        with open(THRESHOLD_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_causality_graph(self) -> Dict:
        """加载因果关系图谱"""
        if os.path.exists(CAUSALITY_FILE):
            try:
                with open(CAUSALITY_FILE) as f:
                    return json.load(f)
            except:
                pass
        
        # 默认因果关系
        return {
            "cpu_usage": {
                "causes": ["load_1m", "task_queue_length"],
                "caused_by": ["disk_usage"],
                "related_indicators": ["memory_usage", "network_load"]
            },
            "memory_usage": {
                "causes": ["task_queue_length"],
                "caused_by": ["cpu_usage"],
                "related_indicators": ["disk_usage"]
            },
            "disk_usage": {
                "causes": [],
                "caused_by": ["cpu_usage"],  # 高CPU可能伴随高IO
                "related_indicators": ["load_1m"]
            },
            "load_1m": {
                "causes": ["cpu_usage", "memory_usage"],
                "caused_by": [],
                "related_indicators": ["task_queue_length", "message_latency"]
            },
            "task_queue_length": {
                "causes": ["cpu_usage", "memory_usage", "load_1m"],
                "caused_by": [],
                "related_indicators": ["message_latency"]
            },
            "message_latency": {
                "causes": ["cpu_usage", "memory_usage", "load_1m", "task_queue_length"],
                "caused_by": [],
                "related_indicators": ["network_load"]
            }
        }
    
    def _save_causality_graph(self):
        """保存因果关系图谱"""
        with open(CAUSALITY_FILE, 'w') as f:
            json.dump(self.causality_graph, f, indent=2)
    
    def record_metric(self, metric_name: str, value: float, tags: Optional[Dict] = None):
        """记录指标"""
        timestamp = time.time()
        
        # 添加到缓存
        self.metrics_history[metric_name].append({
            'timestamp': timestamp,
            'value': value,
            'tags': tags or {}
        })
        
        # 写入数据库
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'INSERT INTO metrics_history (timestamp, metric_name, value, tags) VALUES (?, ?, ?, ?)',
            (timestamp, metric_name, value, json.dumps(tags or {}))
        )
        conn.commit()
        conn.close()
        
        # 动态阈值自适应
        self._adapt_threshold(metric_name, value)
    
    def _adapt_threshold(self, metric_name: str, current_value: float):
        """动态调整阈值"""
        if metric_name not in self.dynamic_thresholds:
            return
        
        th = self.dynamic_thresholds[metric_name]
        history = list(self.metrics_history[metric_name])
        
        if len(history) < 10:
            return
        
        # 计算历史均值和标准差
        values = [h['value'] for h in history]
        mean = statistics.mean(values)
        stdev = statistics.stdev(values) if len(values) > 1 else 0
        
        # 基于波动调整阈值
        if stdev > 0:
            # 如果最近值普遍高于均值，增加阈值弹性
            if current_value > mean + stdev:
                new_threshold = min(th.current_threshold * (1 + th.adaptation_factor), th.max_threshold)
            elif current_value < mean - stdev:
                new_threshold = max(th.current_threshold * (1 - th.adaptation_factor), th.min_threshold)
            else:
                new_threshold = th.current_threshold
            
            th.current_threshold = new_threshold
            th.last_updated = time.time()
        
        # 保存记录
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute(
            'INSERT INTO threshold_history (timestamp, metric_name, threshold_value, is_breach) VALUES (?, ?, ?, ?)',
            (time.time(), metric_name, th.current_threshold, 1 if current_value > th.current_threshold else 0)
        )
        conn.commit()
        conn.close()
    
    def predict(self, metric_name: str, steps: int = 5, prediction_type: str = "combined") -> Optional[Prediction]:
        """预测指标趋势"""
        history = list(self.metrics_history.get(metric_name, []))
        
        if len(history) < 5:
            return None
        
        values = [h['value'] for h in history]
        current_value = values[-1]
        
        # 多种预测方法
        linear_pred, linear_conf = self._linear_regression(values, steps)
        exp_pred, exp_conf = self._exponential_smoothing(values, steps)
        
        # 综合预测
        if prediction_type == "combined":
            # 加权平均
            total_weight = linear_conf + exp_conf
            if total_weight > 0:
                predicted_value = (linear_pred * linear_conf + exp_pred * exp_conf) / total_weight
                confidence = (linear_conf + exp_conf) / 2
            else:
                predicted_value = current_value
                confidence = 0.3
            
            # 趋势判断
            trend = self._calculate_trend(values)
        
        elif prediction_type == "linear":
            predicted_value = linear_pred
            confidence = linear_conf
            trend = self._calculate_trend(values)
        
        elif prediction_type == "exponential":
            predicted_value = exp_pred
            confidence = exp_conf
            trend = self._calculate_trend(values)
        
        else:
            predicted_value = current_value
            confidence = 0.3
            trend = "stable"
        
        # 计算到达阈值的时间
        th = self.dynamic_thresholds.get(metric_name)
        time_to_threshold = None
        
        if th and predicted_value > th.current_threshold:
            # 简单估算: 假设线性增长
            delta = predicted_value - current_value
            if delta > 0:
                # steps个时间单位后的预测，每步假设1分钟
                time_to_threshold = steps * 60
        
        # 保存预测
        self._save_prediction(metric_name, current_value, predicted_value, confidence, time_to_threshold, trend, prediction_type)
        
        return Prediction(
            metric_name=metric_name,
            current_value=current_value,
            predicted_value=predicted_value,
            confidence=confidence,
            time_to_threshold=time_to_threshold,
            trend=trend,
            prediction_type=prediction_type,
            model_accuracy=self._calculate_model_accuracy(metric_name)
        )
    
    def _linear_regression(self, values: List[float], steps: int) -> Tuple[float, float]:
        """线性回归预测"""
        if len(values) < 3:
            return values[-1] if values else 0, 0.3
        
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return values[-1], 0.3
        
        slope = numerator / denominator
        
        # 预测
        predicted = values[-1] + slope * steps
        predicted = max(0, predicted)  # 不能为负
        
        # 置信度：基于R²
        y_pred_mean = sum(values[-1] + slope * (i - (n-1)) for i in range(n)) / n
        ss_tot = sum((y - y_mean) ** 2 for y in values)
        ss_res = sum((values[i] - (y_pred_mean + slope * (i - x_mean))) ** 2 for i in range(n))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        confidence = max(0.3, min(0.95, r_squared))
        
        return predicted, confidence
    
    def _exponential_smoothing(self, values: List[float], steps: int, alpha: float = 0.3) -> Tuple[float, float]:
        """指数平滑预测"""
        if len(values) < 3:
            return values[-1] if values else 0, 0.3
        
        # 简单指数平滑
        smoothed = values[0]
        for v in values[1:]:
            smoothed = alpha * v + (1 - alpha) * smoothed
        
        # 趋势调整
        n = len(values)
        trend = (values[-1] - values[0]) / n if n > 1 else 0
        
        predicted = smoothed + trend * steps
        predicted = max(0, predicted)
        
        # 置信度：基于平滑误差
        errors = [abs(values[i] - (values[i-1] if i > 0 else values[0])) for i in range(len(values))]
        avg_error = statistics.mean(errors) if errors else 1
        max_val = max(values) if values else 1
        confidence = max(0.3, min(0.9, 1 - avg_error / (max_val + 1)))
        
        return predicted, confidence
    
    def _calculate_trend(self, values: List[float]) -> str:
        """计算趋势"""
        if len(values) < 3:
            return "stable"
        
        # 简单线性回归斜率
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)
        
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        avg_value = y_mean
        normalized_slope = abs(slope) / avg_value if avg_value > 0 else 0
        
        if normalized_slope < 0.02:
            return "stable"
        elif slope > 0:
            return "spiking" if normalized_slope > 0.1 else "rising"
        else:
            return "dropping" if normalized_slope > 0.1 else "falling"
    
    def _calculate_model_accuracy(self, metric_name: str) -> float:
        """计算模型准确率"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # 获取最近预测和实际值
        c.execute('''
            SELECT p.predicted_value, m.value, p.timestamp 
            FROM predictions p 
            JOIN metrics_history m ON m.metric_name = p.metric_name
            WHERE p.metric_name = ? AND m.timestamp >= p.timestamp
            ORDER BY p.timestamp DESC LIMIT 20
        ''', (metric_name,))
        
        rows = c.fetchall()
        conn.close()
        
        if len(rows) < 5:
            return 0.5  # 默认
        
        # 计算MAPE
        errors = []
        for pred, actual, _ in rows:
            if actual > 0:
                errors.append(abs(pred - actual) / actual)
        
        if not errors:
            return 0.5
        
        mape = statistics.mean(errors)
        accuracy = max(0, 1 - mape)
        
        return accuracy
    
    def _save_prediction(self, metric_name: str, current: float, predicted: float, 
                        confidence: float, time_to_threshold: Optional[int], trend: str, ptype: str):
        """保存预测结果"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO predictions (timestamp, metric_name, current_value, predicted_value, 
            confidence, time_to_threshold, trend, prediction_type)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (time.time(), metric_name, current, predicted, confidence, time_to_threshold, trend, ptype))
        conn.commit()
        conn.close()
    
    def analyze_alert(self, alert_id: str, level: str, title: str, message: str,
                     metric_name: str, current_value: float) -> AlertAnalysis:
        """分析告警: 根因诊断 + 关联分析"""
        
        # 1. 根因分析
        root_cause = self._diagnose_root_cause(metric_name, current_value)
        
        # 2. 关联告警
        related_alerts = self._find_related_alerts(metric_name)
        
        # 3. 预测发生概率
        predicted_occurrence = self._predict_alert_occurrence(metric_name)
        
        # 4. 建议操作
        recommended_actions = self._generate_recommendations(metric_name, level, current_value)
        
        analysis = AlertAnalysis(
            alert_id=alert_id,
            level=level,
            title=title,
            message=message,
            root_cause=root_cause,
            related_alerts=related_alerts,
            predicted_occurrence=predicted_occurrence,
            recommended_actions=recommended_actions,
            timestamp=time.time()
        )
        
        # 保存分析结果
        self._save_alert_analysis(analysis)
        
        return analysis
    
    def _diagnose_root_cause(self, metric_name: str, current_value: float) -> Optional[str]:
        """根因诊断"""
        if metric_name not in self.causality_graph:
            return None
        
        # 检查因果链
        causes = self.causality_graph[metric_name].get("causes", [])
        
        if not causes:
            return f"{metric_name} 可能为根因告警，建议检查资源使用情况"
        
        # 检查哪个原因指标也异常
        for cause in causes:
            cause_history = list(self.metrics_history.get(cause, []))
            if len(cause_history) > 0:
                cause_current = cause_history[-1]['value']
                cause_th = self.dynamic_thresholds.get(cause)
                if cause_th and cause_current > cause_th.current_threshold:
                    return f"根因可能是 {cause} 异常 (当前值: {cause_current:.1f})"
        
        return f"{metric_name} 可能由 {', '.join(causes)} 引起"
    
    def _find_related_alerts(self, metric_name: str) -> List[str]:
        """查找关联告警"""
        if metric_name not in self.causality_graph:
            return []
        
        related = self.causality_graph[metric_name].get("related_indicators", [])
        
        # 检查相关指标是否也有告警
        related_alerts = []
        for rel in related:
            th = self.dynamic_thresholds.get(rel)
            if th:
                history = list(self.metrics_history.get(rel, []))
                if history and history[-1]['value'] > th.current_threshold:
                    related_alerts.append(f"{rel}: {history[-1]['value']:.1f}")
        
        return related_alerts
    
    def _predict_alert_occurrence(self, metric_name: str) -> Optional[float]:
        """预测告警发生概率"""
        prediction = self.predict(metric_name, steps=3)
        
        if not prediction:
            return None
        
        th = self.dynamic_thresholds.get(metric_name)
        if not th:
            return None
        
        # 概率基于预测值与阈值的距离
        if prediction.predicted_value > th.current_threshold:
            # 距离越近，概率越高
            distance = prediction.predicted_value - th.current_threshold
            probability = min(0.95, 0.5 + (th.current_threshold - distance) / th.current_threshold)
            return probability
        elif prediction.trend in ["rising", "spiking"]:
            # 上升趋势
            return 0.3
        else:
            return 0.1
    
    def _generate_recommendations(self, metric_name: str, level: str, current_value: float) -> List[str]:
        """生成建议操作"""
        recommendations = []
        
        th = self.dynamic_thresholds.get(metric_name)
        if th:
            utilization = (current_value / th.current_threshold) * 100
            
            if utilization > 100:
                recommendations.append(f"🔴 立即处理: {metric_name} 已超过阈值 {utilization:.0f}%")
                recommendations.append("建议: 检查相关进程/服务，必要时重启或扩容")
            elif utilization > 90:
                recommendations.append(f"⚠️ 警告: {metric_name} 接近阈值")
                recommendations.append("建议: 密切关注，准备扩容或优化")
            elif utilization > 70:
                recommendations.append(f"ℹ️ 注意: {metric_name} 使用率较高 ({utilization:.0f}%)")
                recommendations.append("建议: 监控趋势，考虑优化资源分配")
        
        # 特定指标建议
        if "cpu" in metric_name.lower():
            recommendations.append("可执行: top/htop 查看CPU占用进程")
        elif "memory" in metric_name.lower():
            recommendations.append("可执行: free -m 查看内存，清理缓存")
        elif "disk" in metric_name.lower():
            recommendations.append("可执行: du -sh 查看大文件，清理日志")
        elif "queue" in metric_name.lower():
            recommendations.append("可执行: 检查任务队列，清理积压任务")
        
        return recommendations
    
    def _save_alert_analysis(self, analysis: AlertAnalysis):
        """保存告警分析"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            INSERT INTO alert_analysis (id, timestamp, level, title, message, root_cause, 
            related_alerts, predicted_occurrence, recommended_actions)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            analysis.alert_id, analysis.timestamp, analysis.level, analysis.title,
            analysis.message, analysis.root_cause, json.dumps(analysis.related_alerts),
            analysis.predicted_occurrence, json.dumps(analysis.recommended_actions)
        ))
        conn.commit()
        conn.close()
    
    def get_prediction_summary(self) -> Dict:
        """获取预测摘要"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {}
        }
        
        for metric_name in self.dynamic_thresholds.keys():
            prediction = self.predict(metric_name)
            if prediction:
                summary["metrics"][metric_name] = {
                    "current": prediction.current_value,
                    "predicted": prediction.predicted_value,
                    "trend": prediction.trend,
                    "confidence": prediction.confidence,
                    "threshold": self.dynamic_thresholds[metric_name].current_threshold,
                    "time_to_threshold": prediction.time_to_threshold
                }
        
        return summary
    
    def get_active_predictions(self, min_confidence: float = 0.5) -> List[Dict]:
        """获取活跃的预测告警"""
        predictions = []
        
        for metric_name in self.dynamic_thresholds.keys():
            prediction = self.predict(metric_name)
            if prediction and prediction.confidence >= min_confidence:
                th = self.dynamic_thresholds[metric_name]
                if prediction.predicted_value > th.current_threshold or prediction.trend in ["spiking", "rising"]:
                    predictions.append({
                        "metric": metric_name,
                        "current": prediction.current_value,
                        "predicted": prediction.predicted_value,
                        "threshold": th.current_threshold,
                        "trend": prediction.trend,
                        "confidence": prediction.confidence,
                        "time_to_threshold": prediction.time_to_threshold,
                        "level": "critical" if prediction.predicted_value > th.current_threshold * 1.2 else "warning"
                    })
        
        return predictions
    
    def send_dingtalk_notification(self, predictions: List[Dict], analysis: Optional[AlertAnalysis] = None):
        """发送钉钉通知"""
        if not DINGTALK_WEBHOOK:
            return
        
        # 冷却检查
        notify_key = f"dingtalk_{int(time.time() // 300)}"  # 5分钟冷却
        if notify_key in self.notification_cooldown:
            return
        self.notification_cooldown[notify_key] = time.time()
        
        # 构建消息
        if predictions:
            lines = ["### 🔮 智能预测告警\n"]
            
            for p in predictions[:5]:  # 最多5条
                emoji = "🔴" if p["level"] == "critical" else "🟡"
                lines.append(f"{emoji} **{p['metric']}**\n")
                lines.append(f"- 当前: {p['current']:.1f}\n")
                lines.append(f"- 预测: {p['predicted']:.1f} (置信度: {p['confidence']:.0%})\n")
                lines.append(f"- 趋势: {p['trend']}\n")
                if p.get("time_to_threshold"):
                    lines.append(f"- 预计 {p['time_to_threshold']//60} 分钟后超阈值\n")
                lines.append("\n")
            
            if analysis:
                lines.append(f"### 📊 根因分析\n")
                if analysis.root_cause:
                    lines.append(f"- {analysis.root_cause}\n")
                if analysis.recommended_actions:
                    lines.append("**建议操作:**\n")
                    for action in analysis.recommended_actions[:3]:
                        lines.append(f"- {action}\n")
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": "🔮 智能预测告警",
                    "text": "".join(lines)
                }
            }
            
            try:
                req = urllib.request.Request(
                    DINGTALK_WEBHOOK,
                    data=json.dumps(message).encode('utf-8'),
                    headers={'Content-Type': 'application/json'}
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    print(f"[DingTalk] Prediction alert sent: {len(predictions)} metrics")
            except Exception as e:
                print(f"[DingTalk] Failed: {e}")
    
    def start_background_collection(self, interval: float = 60.0):
        """启动后台指标收集"""
        if self._running:
            return
        
        self._running = True
        self._collect_thread = threading.Thread(target=self._collect_loop, args=(interval,), daemon=True)
        self._collect_thread.start()
    
    def stop_background_collection(self):
        """停止后台收集"""
        self._running = False
        if self._collect_thread:
            self._collect_thread.join(timeout=5)
    
    def _collect_loop(self, interval: float):
        """后台收集循环"""
        while self._running:
            try:
                self._collect_system_metrics()
            except Exception as e:
                print(f"Collection error: {e}")
            time.sleep(interval)
    
    def _collect_system_metrics(self):
        """收集系统指标"""
        try:
            # CPU
            with open('/proc/loadavg') as f:
                load = f.read().split()
            self.record_metric("load_1m", float(load[0]), {"source": "proc"})
            
            # 内存
            with open('/proc/meminfo') as f:
                meminfo = f.read()
            
            total = used = free = 0
            for line in meminfo.split('\n'):
                if line.startswith('MemTotal:'):
                    total = int(line.split()[1]) / 1024
                elif line.startswith('MemAvailable:'):
                    free = int(line.split()[1]) / 1024
            
            if total > 0:
                used = total - free
                self.record_metric("memory_usage", (used / total) * 100, {"source": "proc"})
            
            # 磁盘
            result = subprocess.run(['df', '-B1', '/'], capture_output=True, text=True)
            parts = result.stdout.strip().split('\n')[1].split()
            disk_usage = int(parts[4].replace('%', ''))
            self.record_metric("disk_usage", disk_usage, {"source": "df"})
            
        except Exception as e:
            print(f"System metrics collection error: {e}")


def main():
    """CLI入口"""
    import argparse
    parser = argparse.ArgumentParser(description='智能告警分析和预测系统')
    parser.add_argument('action', choices=['predict', 'summary', 'alerts', 'thresholds', 'monitor'],
                        help='操作')
    parser.add_argument('--metric', help='指定指标')
    parser.add_argument('--confidence', type=float, default=0.5, help='最小置信度')
    
    args = parser.parse_args()
    
    analyzer = IntelligentAlertAnalyzer()
    
    if args.action == 'predict':
        metric = args.metric or "cpu_usage"
        prediction = analyzer.predict(metric)
        if prediction:
            th = analyzer.dynamic_thresholds.get(metric)
            print(f"=== {metric} 预测 ===")
            print(f"当前值: {prediction.current_value:.2f}")
            print(f"预测值: {prediction.predicted_value:.2f}")
            print(f"趋势: {prediction.trend}")
            print(f"置信度: {prediction.confidence:.1%}")
            if th:
                print(f"阈值: {th.current_threshold:.2f}")
                if prediction.predicted_value > th.current_threshold:
                    print(f"⚠️ 预测将超过阈值!")
            if prediction.time_to_threshold:
                print(f"预计 {prediction.time_to_threshold//60} 分钟后超阈值")
        else:
            print("数据不足，无法预测")
    
    elif args.action == 'summary':
        summary = analyzer.get_prediction_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
    
    elif args.action == 'alerts':
        predictions = analyzer.get_active_predictions(args.confidence)
        print(f"=== 活跃预测告警 ({len(predictions)}条) ===")
        for p in predictions:
            emoji = "🔴" if p["level"] == "critical" else "🟡"
            print(f"{emoji} {p['metric']}: {p['current']:.1f} → {p['predicted']:.1f} ({p['trend']})")
    
    elif args.action == 'thresholds':
        print("=== 动态阈值 ===")
        for name, th in analyzer.dynamic_thresholds.items():
            print(f"{name}: {th.current_threshold:.1f} (基线: {th.base_threshold})")
    
    elif args.action == 'monitor':
        print("启动智能监控 (Ctrl+C 停止)...")
        analyzer.start_background_collection(30)
        try:
            while True:
                time.sleep(60)
                predictions = analyzer.get_active_predictions(0.6)
                if predictions:
                    print(f"\n预测告警: {len(predictions)}条")
                    analyzer.send_dingtalk_notification(predictions)
        except KeyboardInterrupt:
            analyzer.stop_background_collection()
            print("\n监控已停止")


if __name__ == '__main__':
    main()