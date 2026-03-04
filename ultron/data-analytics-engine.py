#!/usr/bin/env python3
"""
奥创实时数据分析引擎 - 智能数据分析与预测系统
Real-time Data Analytics Engine

功能:
- 实时数据流处理
- 多维度数据分析
- 异常检测
"""

import asyncio
import time
import json
import random
import uuid
import math
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict, deque
import threading


class MetricType(Enum):
    """指标类型"""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    REQUEST = "request"
    ERROR = "error"
    CUSTOM = "custom"


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class DataPoint:
    """数据点"""
    timestamp: float
    metric_type: MetricType
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class TimeSeries:
    """时间序列"""
    metric_type: MetricType
    data: deque = field(default_factory=lambda: deque(maxlen=1000))
    tags: Dict[str, str] = field(default_factory=dict)
    
    def add(self, value: float, timestamp: float = None, tags: Dict = None):
        """添加数据点"""
        self.data.append(DataPoint(
            timestamp=timestamp or time.time(),
            metric_type=self.metric_type,
            value=value,
            tags=tags or {}
        ))
    
    def get_range(self, start: float, end: float) -> List[DataPoint]:
        """获取时间范围内的数据"""
        return [d for d in self.data if start <= d.timestamp <= end]
    
    def get_latest(self, count: int = 10) -> List[DataPoint]:
        """获取最新的N个数据点"""
        return list(self.data)[-count:]


class StreamProcessor:
    """实时数据流处理器"""
    
    def __init__(self, buffer_size: int = 10000):
        self.buffer_size = buffer_size
        self.streams: Dict[str, deque] = defaultdict(lambda: deque(maxlen=buffer_size))
        self.handlers: List[Callable] = []
        self._lock = threading.Lock()
    
    def push(self, stream_id: str, data: Any):
        """推送数据到流"""
        with self._lock:
            self.streams[stream_id].append({
                "timestamp": time.time(),
                "data": data
            })
            
            # 触发处理器
            for handler in self.handlers:
                try:
                    handler(stream_id, data)
                except Exception as e:
                    print(f"Handler error: {e}")
    
    def register_handler(self, handler: Callable):
        """注册处理器"""
        self.handlers.append(handler)
    
    def get_stream(self, stream_id: str) -> List[Dict]:
        """获取流数据"""
        return list(self.streams.get(stream_id, []))


class AnalyticsEngine:
    """分析引擎"""
    
    def __init__(self):
        self.time_series: Dict[str, TimeSeries] = {}
        self.aggregations: Dict[str, Dict] = {}
    
    def add_time_series(self, name: str, metric_type: MetricType, tags: Dict = None):
        """添加时间序列"""
        ts = TimeSeries(metric_type=metric_type, tags=tags or {})
        self.time_series[name] = ts
        return ts
    
    def calculate_statistics(self, name: str, window_seconds: int = 300) -> Dict:
        """计算统计信息"""
        ts = self.time_series.get(name)
        if not ts:
            return {}
        
        now = time.time()
        start = now - window_seconds
        data = ts.get_range(start, now)
        
        if not data:
            return {}
        
        values = [d.value for d in data]
        
        return {
            "count": len(values),
            "sum": sum(values),
            "mean": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "std": self._std(values),
            "p50": self._percentile(values, 50),
            "p90": self._percentile(values, 90),
            "p95": self._percentile(values, 95),
            "p99": self._percentile(values, 99)
        }
    
    def _std(self, values: List[float]) -> float:
        """标准差"""
        if len(values) < 2:
            return 0.0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / len(values)
        return math.sqrt(variance)
    
    def _percentile(self, values: List[float], p: float) -> float:
        """百分位数"""
        if not values:
            return 0.0
        sorted_values = sorted(values)
        k = (len(sorted_values) - 1) * (p / 100)
        f = math.floor(k)
        c = math.ceil(k)
        if f == c:
            return sorted_values[int(k)]
        return sorted_values[f] * (c - k) + sorted_values[c] * (k - f)
    
    def calculate_trend(self, name: str, points: int = 30) -> str:
        """计算趋势"""
        ts = self.time_series.get(name)
        if not ts:
            return "unknown"
        
        data = ts.get_latest(points)
        if len(data) < 2:
            return "unknown"
        
        # 简单线性回归
        values = [d.value for d in data]
        x_mean = sum(range(len(values))) / len(values)
        y_mean = sum(values) / len(values)
        
        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(len(values)))
        
        if denominator == 0:
            return "stable"
        
        slope = numerator / denominator
        
        # 判断趋势
        if slope > 0.1:
            return "rising"
        elif slope < -0.1:
            return "falling"
        else:
            return "stable"
    
    def get_correlation(self, name1: str, name2: str) -> float:
        """计算相关性"""
        ts1 = self.time_series.get(name1)
        ts2 = self.time_series.get(name2)
        
        if not ts1 or not ts2:
            return 0.0
        
        # 获取最新数据点
        data1 = ts1.get_latest(50)
        data2 = ts2.get_latest(50)
        
        if len(data1) != len(data2) or len(data1) < 2:
            return 0.0
        
        values1 = [d.value for d in data1]
        values2 = [d.value for d in data2]
        
        # Pearson相关系数
        mean1 = sum(values1) / len(values1)
        mean2 = sum(values2) / len(values2)
        
        numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2))
        denom1 = math.sqrt(sum((v - mean1) ** 2 for v in values1))
        denom2 = math.sqrt(sum((v - mean2) ** 2 for v in values2))
        
        if denom1 == 0 or denom2 == 0:
            return 0.0
        
        return numerator / (denom1 * denom2)


class AnomalyDetector:
    """异常检测器"""
    
    def __init__(self, sensitivity: float = 2.0):
        self.sensitivity = sensitivity
        self.baseline: Dict[str, Dict] = {}
        self.alert_callbacks: List[Callable] = []
    
    def set_baseline(self, name: str, mean: float, std: float):
        """设置基线"""
        self.baseline[name] = {"mean": mean, "std": std}
    
    def detect(self, name: str, value: float) -> Optional[Dict]:
        """检测异常"""
        baseline = self.baseline.get(name)
        if not baseline:
            return None
        
        mean = baseline["mean"]
        std = baseline["std"]
        
        if std == 0:
            z_score = 0 if value == mean else float('inf')
        else:
            z_score = abs(value - mean) / std
        
        if z_score > self.sensitivity:
            level = AlertLevel.CRITICAL if z_score > 3 * self.sensitivity else AlertLevel.WARNING
            
            alert = {
                "name": name,
                "value": value,
                "expected": mean,
                "z_score": z_score,
                "level": level.value,
                "timestamp": time.time()
            }
            
            # 触发回调
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    print(f"Alert callback error: {e}")
            
            return alert
        
        return None
    
    def register_alert_callback(self, callback: Callable):
        """注册告警回调"""
        self.alert_callbacks.append(callback)


class MultiDimensionalAnalyzer:
    """多维度分析器"""
    
    def __init__(self):
        self.dimensions: Dict[str, Dict] = {}
        self.cross_analysis: Dict[str, Callable] = {}
    
    def add_dimension(self, name: str, values: List[float], labels: List[str] = None):
        """添加维度"""
        self.dimensions[name] = {
            "values": values,
            "labels": labels or [str(i) for i in range(len(values))],
            "timestamp": time.time()
        }
    
    def calculate_correlation_matrix(self) -> Dict[str, Dict[str, float]]:
        """计算相关矩阵"""
        result = {}
        dim_names = list(self.dimensions.keys())
        
        for i, d1 in enumerate(dim_names):
            result[d1] = {}
            for j, d2 in enumerate(dim_names):
                if i == j:
                    result[d1][d2] = 1.0
                else:
                    corr = self._correlation(
                        self.dimensions[d1]["values"],
                        self.dimensions[d2]["values"]
                    )
                    result[d1][d2] = corr
        
        return result
    
    def _correlation(self, values1: List[float], values2: List[float]) -> float:
        """计算相关系数"""
        if len(values1) != len(values2) or len(values1) < 2:
            return 0.0
        
        mean1 = sum(values1) / len(values1)
        mean2 = sum(values2) / len(values2)
        
        numerator = sum((v1 - mean1) * (v2 - mean2) for v1, v2 in zip(values1, values2))
        denom1 = math.sqrt(sum((v - mean1) ** 2 for v in values1))
        denom2 = math.sqrt(sum((v - mean2) ** 2 for v in values2))
        
        if denom1 == 0 or denom2 == 0:
            return 0.0
        
        return numerator / (denom1 * denom2)
    
    def get_top_n(self, dimension: str, n: int = 5, descending: bool = True) -> List[tuple]:
        """获取Top N"""
        dim = self.dimensions.get(dimension)
        if not dim:
            return []
        
        indexed = list(zip(dim["labels"], dim["values"]))
        indexed.sort(key=lambda x: x[1], reverse=descending)
        return indexed[:n]


class DataDashboard:
    """数据仪表盘"""
    
    def __init__(self, analytics: AnalyticsEngine):
        self.analytics = analytics
    
    def generate_report(self) -> Dict[str, Any]:
        """生成分析报告"""
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": {},
            "trends": {},
            "anomalies": []
        }
        
        # 收集所有时间序列的统计
        for name, ts in self.analytics.time_series.items():
            stats = self.analytics.calculate_statistics(name)
            if stats:
                report["metrics"][name] = stats
            
            trend = self.analytics.calculate_trend(name)
            if trend:
                report["trends"][name] = trend
        
        return report
    
    def generate_html(self) -> str:
        """生成HTML仪表盘"""
        report = self.generate_report()
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>奥创数据分析面板</title>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        h1 {{ color: #00d4ff; text-align: center; }}
        .timestamp {{ text-align: center; color: #888; margin-bottom: 20px; }}
        .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(350px, 1fr)); gap: 20px; }}
        .card {{ background: #16213e; padding: 20px; border-radius: 10px; border-left: 4px solid #00d4ff; }}
        .card h3 {{ margin: 0 0 15px 0; color: #00d4ff; }}
        .metric {{ display: flex; justify-content: space-between; margin: 8px 0; border-bottom: 1px solid #2a3f5f; padding-bottom: 4px; }}
        .metric-label {{ color: #888; }}
        .metric-value {{ font-weight: bold; color: #fff; }}
        .trend {{ display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; margin-left: 10px; }}
        .trend-rising {{ background: #ff4444; color: white; }}
        .trend-falling {{ background: #00ff88; color: #1a1a2e; }}
        .trend-stable {{ background: #888; color: white; }}
    </style>
</head>
<body>
    <h1>📊 奥创数据分析面板</h1>
    <div class="timestamp">更新时间: {report['timestamp']}</div>
    <div class="grid">
"""
        
        for name, stats in report["metrics"].items():
            trend = report["trends"].get(name, "unknown")
            trend_class = f"trend-{trend}"
            trend_text = {"rising": "↑上升", "falling": "↓下降", "stable": "→稳定"}.get(trend, trend)
            
            html += f"""        <div class="card">
            <h3>{name} <span class="trend {trend_class}">{trend_text}</span></h3>
            <div class="metric"><span class="metric-label">平均值</span><span class="metric-value">{stats['mean']:.2f}</span></div>
            <div class="metric"><span class="metric-label">最小值</span><span class="metric-value">{stats['min']:.2f}</span></div>
            <div class="metric"><span class="metric-label">最大值</span><span class="metric-value">{stats['max']:.2f}</span></div>
            <div class="metric"><span class="metric-label">标准差</span><span class="metric-value">{stats['std']:.2f}</span></div>
            <div class="metric"><span class="metric-label">P95</span><span class="metric-value">{stats['p95']:.2f}</span></div>
            <div class="metric"><span class="metric-label">样本数</span><span class="metric-value">{stats['count']}</span></div>
        </div>
"""
        
        html += """    </div>
</body>
</html>"""
        
        return html


async def demo():
    """演示"""
    print("=== 实时数据分析引擎演示 ===\n")
    
    # 创建引擎
    analytics = AnalyticsEngine()
    
    # 创建时间序列
    ts_cpu = analytics.add_time_series("cpu_usage", MetricType.CPU)
    ts_memory = analytics.add_time_series("memory_usage", MetricType.MEMORY)
    ts_disk = analytics.add_time_series("disk_usage", MetricType.DISK)
    
    # 模拟数据流
    print("模拟数据流...")
    base_time = time.time() - 3600  # 1小时前
    
    for i in range(100):
        ts_cpu.add(20 + 10 * math.sin(i / 10) + random.gauss(0, 2), base_time + i * 36)
        ts_memory.add(40 + 5 * math.cos(i / 15) + random.gauss(0, 1), base_time + i * 36)
        ts_disk.add(35 + i * 0.05, base_time + i * 36)
    
    print(f"添加了 {len(ts_cpu.data)} 个数据点到每个时间序列")
    
    # 计算统计信息
    print("\n统计信息:")
    for name in ["cpu_usage", "memory_usage", "disk_usage"]:
        stats = analytics.calculate_statistics(name)
        trend = analytics.calculate_trend(name)
        print(f"  {name}:")
        print(f"    平均: {stats['mean']:.2f}, 标准差: {stats['std']:.2f}, 趋势: {trend}")
    
    # 相关性分析
    print("\n相关性分析:")
    corr = analytics.get_correlation("cpu_usage", "memory_usage")
    print(f"  CPU-内存 相关性: {corr:.3f}")
    
    # 异常检测
    print("\n异常检测:")
    detector = AnomalyDetector(sensitivity=2.0)
    detector.set_baseline("cpu_usage", 20.0, 5.0)
    
    alerts = []
    detector.register_alert_callback(lambda a: alerts.append(a))
    
    test_values = [45.0, 22.0, 18.0, 50.0]
    for val in test_values:
        result = detector.detect("cpu_usage", val)
        if result:
            print(f"  ⚠ 检测到异常: 值={result['value']:.1f}, Z分数={result['z_score']:.1f}, 级别={result['level']}")
    
    # 多维度分析
    print("\n多维度分析:")
    analyzer = MultiDimensionalAnalyzer()
    analyzer.add_dimension("cpu", [20, 25, 30, 35, 40, 45, 50, 55, 60])
    analyzer.add_dimension("memory", [40, 42, 45, 48, 50, 52, 55, 58, 60])
    
    corr_matrix = analyzer.calculate_correlation_matrix()
    print(f"  相关矩阵: CPU-Memory = {corr_matrix['cpu']['memory']:.3f}")
    
    top = analyzer.get_top_n("cpu", 3)
    print(f"  Top 3 CPU: {top}")
    
    # 生成仪表盘
    print("\n生成仪表盘...")
    dashboard = DataDashboard(analytics)
    html = dashboard.generate_html()
    
    with open("/root/.openclaw/workspace/ultron/data-analytics-dashboard.html", "w") as f:
        f.write(html)
    
    print(f"  仪表盘已保存: ultron/data-analytics-dashboard.html")
    
    # 生成报告
    report = dashboard.generate_report()
    print(f"\n报告摘要:")
    print(f"  指标数: {len(report['metrics'])}")
    print(f"  趋势数: {len(report['trends'])}")
    
    return report


if __name__ == "__main__":
    asyncio.run(demo())