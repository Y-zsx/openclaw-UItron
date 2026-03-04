#!/usr/bin/env python3
"""
奥创趋势预测模型 - 趋势预测
Trend Prediction Model

功能:
- 时间序列分析
- 趋势预测算法
- 预测可视化
"""

import asyncio
import time
import json
import math
import random
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque


@dataclass
class DataPoint:
    """数据点"""
    timestamp: float
    value: float
    predicted: bool = False


class TimeSeriesModel:
    """时间序列模型"""
    
    def __init__(self, name: str, window_size: int = 50):
        self.name = name
        self.window_size = window_size
        self.data: deque = deque(maxlen=window_size * 2)
    
    def add(self, value: float, timestamp: float = None):
        """添加数据点"""
        self.data.append(DataPoint(
            timestamp=timestamp or time.time(),
            value=value
        ))
    
    def get_history(self, count: int = None) -> List[DataPoint]:
        """获取历史数据"""
        if count:
            return list(self.data)[-count:]
        return list(self.data)
    
    def get_values(self, count: int = None) -> List[float]:
        """获取数值序列"""
        points = self.get_history(count)
        return [p.value for p in points]


class SimpleMovingAverage:
    """简单移动平均"""
    
    def __init__(self, window: int = 5):
        self.window = window
    
    def predict(self, values: List[float]) -> float:
        """预测下一个值"""
        if len(values) < self.window:
            return sum(values) / len(values) if values else 0
        
        return sum(values[-self.window:]) / self.window


class ExponentialSmoothing:
    """指数平滑"""
    
    def __init__(self, alpha: float = 0.3):
        self.alpha = alpha
        self.smoothed = 0.0
        self.initialized = False
    
    def predict(self, values: List[float]) -> float:
        """预测下一个值"""
        if not values:
            return 0.0
        
        if not self.initialized:
            self.smoothed = values[0]
            self.initialized = True
        
        for v in values[1:]:
            self.smoothed = self.alpha * v + (1 - self.alpha) * self.smoothed
        
        return self.smoothed
    
    def reset(self):
        """重置"""
        self.smoothed = 0.0
        self.initialized = False


class LinearRegression:
    """线性回归"""
    
    def __init__(self):
        self.coefficients: Tuple[float, float] = (0.0, 0.0)  # (slope, intercept)
    
    def fit(self, values: List[float]) -> Tuple[float, float]:
        """训练模型"""
        n = len(values)
        if n < 2:
            return (0.0, sum(values) / n if values else 0.0)
        
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            slope = 0.0
        else:
            slope = numerator / denominator
        
        intercept = y_mean - slope * x_mean
        
        self.coefficients = (slope, intercept)
        return self.coefficients
    
    def predict(self, x: float) -> float:
        """预测"""
        slope, intercept = self.coefficients
        return slope * x + intercept


class HoltWinters:
    """Holt-Winters 三次指数平滑"""
    
    def __init__(self, alpha: float = 0.2, beta: float = 0.1, gamma: float = 0.1, season_period: int = 7):
        self.alpha = alpha
        self.beta = beta
        self.gamma = gamma
        self.season_period = season_period
        
        self.level = 0.0
        self.trend = 0.0
        self.seasonal = []
        self.initialized = False
    
    def predict(self, values: List[float], steps: int = 1) -> List[float]:
        """预测"""
        n = len(values)
        
        # 初始化
        if n < self.season_period * 2:
            # 数据不足，使用简单预测
            return [sum(values) / n] * steps if values else [0.0] * steps
        
        # 初始化季节性
        if not self.initialized:
            self.seasonal = [0.0] * self.season_period
            for i in range(self.season_period):
                self.seasonal[i] = values[i]
            
            self.level = sum(values[:self.season_period]) / self.season_period
            self.trend = (sum(values[self.season_period:2*self.season_period]) - 
                        sum(values[:self.season_period])) / self.season_period
            self.initialized = True
        
        # 预测
        predictions = []
        for h in range(1, steps + 1):
            # 预测值 = 水平 + 趋势 * h + 季节性
            season_idx = (n + h - 1) % self.season_period
            pred = self.level + self.trend * h + self.seasonal[season_idx]
            predictions.append(pred)
        
        # 更新模型
        for v in values:
            last_level = self.level
            self.level = self.alpha * (v - self.seasonal[season_idx]) + (1 - self.alpha) * (self.level + self.trend)
            self.trend = self.beta * (self.level - last_level) + (1 - self.beta) * self.trend
            season_idx = (season_idx + 1) % self.season_period
            self.seasonal[season_idx] = self.gamma * (v - self.level) + (1 - self.gamma) * self.seasonal[season_idx]
        
        return predictions


class TrendPredictor:
    """趋势预测器 - 综合多种算法"""
    
    def __init__(self, name: str):
        self.name = name
        self.model = TimeSeriesModel(name)
        self.models = {
            "sma": SimpleMovingAverage(window=5),
            "ema": ExponentialSmoothing(alpha=0.3),
            "linear": LinearRegression(),
            "hw": HoltWinters(alpha=0.3, beta=0.1, gamma=0.1, season_period=7)
        }
        self.predictions: List[DataPoint] = []
    
    def add_data(self, value: float, timestamp: float = None):
        """添加数据"""
        self.model.add(value, timestamp)
    
    def add_batch(self, values: List[Tuple[float, float]]):
        """批量添加数据 (value, timestamp)"""
        for value, ts in values:
            self.model.add(value, ts)
    
    def predict(self, method: str = "ensemble", steps: int = 5) -> List[float]:
        """预测"""
        history = self.model.get_values()
        
        if not history:
            return [0.0] * steps
        
        results = {}
        
        # 各种模型预测
        if "sma" in method or method == "ensemble":
            results["sma"] = self.models["sma"].predict(history)
        
        if "ema" in method or method == "ensemble":
            results["ema"] = self.models["ema"].predict(history)
        
        if "linear" in method or method == "ensemble":
            self.models["linear"].fit(history)
            results["linear"] = [self.models["linear"].predict(len(history) + i) for i in range(1, steps + 1)]
        
        if "hw" in method or method == "ensemble":
            results["hw"] = self.models["hw"].predict(history, steps)
        
        # 集成预测
        if method == "ensemble":
            # 取平均
            final = []
            for i in range(steps):
                preds = []
                if "sma" in results:
                    preds.append(results["sma"])
                if "ema" in results:
                    preds.append(results["ema"])
                if "linear" in results and i < len(results["linear"]):
                    preds.append(results["linear"][i])
                if "hw" in results and i < len(results["hw"]):
                    preds.append(results["hw"][i])
                
                final.append(sum(preds) / len(preds) if preds else 0.0)
            
            return final
        
        return results.get(method, [0.0] * steps)
    
    def analyze_trend(self) -> Dict:
        """分析趋势"""
        history = self.model.get_values()
        
        if len(history) < 5:
            return {"trend": "unknown", "strength": 0, "confidence": 0}
        
        # 线性回归
        self.models["linear"].fit(history)
        slope, intercept = self.models["linear"].coefficients
        
        # 计算趋势强度
        mean_val = sum(history) / len(history)
        if mean_val == 0:
            strength = 0
        else:
            strength = abs(slope * len(history)) / mean_val
        
        # 判断趋势
        if slope > 0.1:
            trend = "rising"
        elif slope < -0.1:
            trend = "falling"
        else:
            trend = "stable"
        
        # 置信度（基于R²）
        y_mean = mean_val
        ss_tot = sum((v - y_mean) ** 2 for v in history)
        ss_res = 0
        for i, v in enumerate(history):
            predicted = self.models["linear"].predict(i)
            ss_res += (v - predicted) ** 2
        
        if ss_tot > 0:
            r_squared = 1 - (ss_res / ss_tot)
            confidence = max(0, min(1, r_squared))
        else:
            confidence = 0
        
        return {
            "trend": trend,
            "slope": slope,
            "strength": strength,
            "confidence": confidence,
            "next_value": history[-1] + slope
        }
    
    def get_confidence_interval(self, steps: int = 5, confidence: float = 0.95) -> List[Tuple[float, float]]:
        """获取置信区间"""
        history = self.model.get_values()
        
        if len(history) < 10:
            # 数据不足，返回宽区间
            predictions = self.predict(steps=steps)
            return [(p * 0.8, p * 1.2) for p in predictions]
        
        # 计算标准误差
        self.models["linear"].fit(history)
        predictions = self.predict(steps=steps)
        
        # 残差标准差
        residuals = [history[i] - self.models["linear"].predict(i) for i in range(len(history))]
        std_res = math.sqrt(sum(r ** 2 for r in residuals) / max(len(residuals) - 2, 1))
        
        # t值（简化）
        t_value = 1.96 if confidence == 0.95 else 2.576  # 99%
        
        # 置信区间
        intervals = []
        for i, pred in enumerate(predictions):
            # 预测误差随时间增加
            margin = t_value * std_res * math.sqrt(1 + i / len(history))
            intervals.append((pred - margin, pred + margin))
        
        return intervals


class TrendVisualizer:
    """趋势可视化"""
    
    def __init__(self, predictor: TrendPredictor):
        self.predictor = predictor
    
    def generate_chart_data(self, history_points: int = 30, future_points: int = 10) -> Dict:
        """生成图表数据"""
        history = self.predictor.model.get_history(history_points)
        predictions = self.predictor.predict(steps=future_points)
        intervals = self.predictor.get_confidence_interval(steps=future_points)
        
        chart_data = {
            "labels": [],
            "history": [],
            "predicted": [],
            "upper": [],
            "lower": []
        }
        
        # 历史数据
        last_ts = history[-1].timestamp if history else time.time()
        interval = 3600  # 1小时
        
        for point in history:
            chart_data["labels"].append(datetime.fromtimestamp(point.timestamp).strftime("%H:%M"))
            chart_data["history"].append(point.value)
        
        # 预测数据
        future_ts = last_ts + interval
        for i, pred in enumerate(predictions):
            future_ts += interval
            chart_data["labels"].append(datetime.fromtimestamp(future_ts).strftime("%H:%M"))
            chart_data["predicted"].append(pred)
            chart_data["upper"].append(intervals[i][1])
            chart_data["lower"].append(intervals[i][0])
        
        return chart_data
    
    def generate_html(self, title: str = "趋势预测") -> str:
        """生成HTML图表"""
        chart_data = self.generate_chart_data()
        trend = self.predictor.analyze_trend()
        
        # 转换为JSON
        history_json = json.dumps(chart_data["history"])
        predicted_json = json.dumps(chart_data["predicted"])
        upper_json = json.dumps(chart_data["upper"])
        lower_json = json.dumps(chart_data["lower"])
        labels_json = json.dumps(chart_data["labels"])
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; padding: 20px; background: #1a1a2e; color: #eee; }}
        .container {{ max-width: 900px; margin: 0 auto; }}
        h1 {{ color: #00d4ff; text-align: center; }}
        .analysis {{ background: #16213e; padding: 20px; border-radius: 10px; margin: 20px 0; }}
        .analysis-item {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #2a3f5f; }}
        .analysis-label {{ color: #888; }}
        .analysis-value {{ font-weight: bold; }}
        .trend-rising {{ color: #ff4444; }}
        .trend-falling {{ color: #00ff88; }}
        .trend-stable {{ color: #888; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📈 {title}</h1>
        
        <div class="analysis">
            <h3>趋势分析</h3>
            <div class="analysis-item">
                <span class="analysis-label">趋势方向</span>
                <span class="analysis-value trend-{trend['trend']}">{trend['trend'].upper()}</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">斜率</span>
                <span class="analysis-value">{trend['slope']:.4f}</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">趋势强度</span>
                <span class="analysis-value">{trend['strength']:.2f}</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">置信度</span>
                <span class="analysis-value">{trend['confidence']:.1%}</span>
            </div>
            <div class="analysis-item">
                <span class="analysis-label">预测下一个值</span>
                <span class="analysis-value">{trend['next_value']:.2f}</span>
            </div>
        </div>
        
        <canvas id="trendChart" height="100"></canvas>
    </div>
    
    <script>
        const ctx = document.getElementById('trendChart').getContext('2d');
        const chart = new Chart(ctx, {{
            type: 'line',
            data: {{
                labels: {labels_json},
                datasets: [
                    {{
                        label: '历史数据',
                        data: {history_json},
                        borderColor: '#00d4ff',
                        backgroundColor: 'rgba(0, 212, 255, 0.1)',
                        fill: true,
                        tension: 0.4
                    }},
                    {{
                        label: '预测',
                        data: Array({len(chart_data["history"])}).fill(null).concat({predicted_json}),
                        borderColor: '#ff4444',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.4
                    }},
                    {{
                        label: '置信区间上限',
                        data: Array({len(chart_data["history"])}).fill(null).concat({upper_json}),
                        borderColor: 'rgba(255,255,255,0.2)',
                        borderDash: [2, 2],
                        fill: false,
                        pointRadius: 0
                    }},
                    {{
                        label: '置信区间下限',
                        data: Array({len(chart_data["history"])}).fill(null).concat({lower_json}),
                        borderColor: 'rgba(255,255,255,0.2)',
                        borderDash: [2, 2],
                        fill: '-1',
                        backgroundColor: 'rgba(255,255,255,0.05)',
                        pointRadius: 0
                    }}
                ]
            }},
            options: {{
                responsive: true,
                plugins: {{
                    legend: {{ position: 'top' }}
                }},
                scales: {{
                    y: {{ beginAtZero: false }}
                }}
            }}
        }});
    </script>
</body>
</html>"""
        return html


async def demo():
    """演示"""
    print("=== 趋势预测模型演示 ===\n")
    
    # 创建预测器
    predictor = TrendPredictor("cpu_usage")
    
    # 模拟历史数据
    print("生成历史数据...")
    base_value = 50.0
    for i in range(50):
        # 模拟上升趋势+周期性波动
        value = base_value + i * 0.5 + 10 * math.sin(i / 7) + random.gauss(0, 2)
        predictor.add_data(value, time.time() - (50 - i) * 3600)
    
    print(f"  添加了 {len(predictor.model.data)} 个数据点")
    
    # 分析趋势
    print("\n趋势分析:")
    trend = predictor.analyze_trend()
    print(f"  趋势: {trend['trend']}")
    print(f"  斜率: {trend['slope']:.4f}")
    print(f"  置信度: {trend['confidence']:.1%}")
    print(f"  预测下一个值: {trend['next_value']:.2f}")
    
    # 预测
    print("\n预测 (5步):")
    predictions = predictor.predict(method="ensemble", steps=5)
    for i, pred in enumerate(predictions):
        print(f"  步骤 {i+1}: {pred:.2f}")
    
    # 置信区间
    print("\n置信区间 (95%):")
    intervals = predictor.get_confidence_interval(steps=5, confidence=0.95)
    for i, (lower, upper) in enumerate(intervals):
        print(f"  步骤 {i+1}: [{lower:.2f}, {upper:.2f}]")
    
    # 各模型对比
    print("\n各模型预测对比:")
    for method in ["sma", "ema", "linear", "hw"]:
        preds = predictor.predict(method=method, steps=3)
        # 确保是列表
        if isinstance(preds, float):
            preds = [preds]
        print(f"  {method}: {[f'{p:.1f}' for p in preds]}")
    
    # 生成可视化
    print("\n生成可视化...")
    visualizer = TrendVisualizer(predictor)
    html = visualizer.generate_html("CPU使用率趋势预测")
    
    with open("/root/.openclaw/workspace/ultron/trend-prediction-dashboard.html", "w") as f:
        f.write(html)
    
    print(f"  图表已保存: ultron/trend-prediction-dashboard.html")
    
    return {
        "trend": trend,
        "predictions": predictions
    }


if __name__ == "__main__":
    asyncio.run(demo())