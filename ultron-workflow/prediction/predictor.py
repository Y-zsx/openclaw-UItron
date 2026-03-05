#!/usr/bin/env python3
"""
预测分析器 - 基于时间序列数据进行趋势预测
"""
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collections import deque
import statistics

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ModelType:
    """支持的预测模型类型"""
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_TREND = "linear_trend"
    SIMPLE_FORECAST = "simple"

class ForecastResult:
    """预测结果"""
    def __init__(self, predictions: List[float], confidence: float, model_type: str, metadata: Dict[str, Any]):
        self.predictions = predictions
        self.confidence = confidence
        self.model_type = model_type
        self.metadata = metadata

class Predictor:
    """预测分析器"""
    
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.history = deque(maxlen=100)
        
    def add_data_point(self, value: float, timestamp: str = None):
        """添加数据点"""
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        self.history.append({"value": value, "timestamp": timestamp})
        
    def predict(self, steps: int = 1, model: str = "exponential_smoothing") -> ForecastResult:
        """执行预测"""
        if len(self.history) < 3:
            # 数据不足，使用简单预测
            return self._simple_predict(steps)
            
        values = [d["value"] for d in self.history]
        
        if model == "moving_average":
            return self._moving_average_predict(values, steps)
        elif model == "exponential_smoothing":
            return self._exponential_smoothing_predict(values, steps)
        elif model == "linear_trend":
            return self._linear_trend_predict(values, steps)
        else:
            return self._simple_predict(steps)
    
    def _simple_predict(self, steps: int) -> ForecastResult:
        """简单预测：使用历史平均值"""
        if not self.history:
            return ForecastResult(predictions=[0.0] * steps, confidence=0.0, 
                                model_type="simple", metadata={})
        
        values = [d["value"] for d in self.history]
        avg = statistics.mean(values)
        
        return ForecastResult(
            predictions=[avg] * steps,
            confidence=0.3,
            model_type="simple",
            metadata={"base_value": avg, "history_size": len(values)}
        )
    
    def _moving_average_predict(self, values: List[float], steps: int):
        """移动平均预测"""
        n = min(self.window_size, len(values))
        recent = values[-n:]
        ma = sum(recent) / n
        
        predictions = [ma] * steps
        
        # 计算置信度（基于历史波动）
        if len(values) > 1:
            stdev = statistics.stdev(values) if len(values) > 1 else 0
            mean_val = statistics.mean(values)
            confidence = max(0.1, 1.0 - (stdev / mean_val if mean_val > 0 else 0))
        else:
            confidence = 0.5
            
        return ForecastResult(
            predictions=predictions,
            confidence=confidence,
            model_type="moving_average",
            metadata={"window_size": n, "ma_value": ma}
        )
    
    def _exponential_smoothing_predict(self, values: List[float], steps: int):
        """指数平滑预测"""
        alpha = 0.3  # 平滑系数
        
        # 计算初始值
        smoothed = values[0]
        
        # 指数平滑
        for val in values[1:]:
            smoothed = alpha * val + (1 - alpha) * smoothed
            
        predictions = [smoothed] * steps
        
        # 计算趋势
        trend = 0
        if len(values) >= 3:
            trend = (values[-1] - values[0]) / len(values)
            # 调整预测值（考虑趋势）
            predictions = [smoothed + trend * i for i in range(1, steps + 1)]
        
        # 置信度
        confidence = min(0.8, 0.4 + 0.1 * len(values))
        
        return ForecastResult(
            predictions=predictions,
            confidence=confidence,
            model_type="exponential_smoothing",
            metadata={"alpha": alpha, "smoothed_value": smoothed, "trend": trend}
        )
    
    def _linear_trend_predict(self, values: List[float], steps: int):
        """线性趋势预测"""
        n = len(values)
        
        # 简单线性回归
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n
        
        # 计算斜率和截距
        numerator = sum((i - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return self._simple_predict(steps)
            
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # 预测
        predictions = [intercept + slope * (n + i) for i in range(steps)]
        
        # 置信度（基于R²）
        y_pred = [intercept + slope * i for i in range(n)]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        confidence = max(0.1, min(0.9, r_squared))
        
        return ForecastResult(
            predictions=predictions,
            confidence=confidence,
            model_type="linear_trend",
            metadata={"slope": slope, "intercept": intercept, "r_squared": r_squared}
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取历史统计信息"""
        if not self.history:
            return {"count": 0}
            
        values = [d["value"] for d in self.history]
        
        return {
            "count": len(values),
            "mean": statistics.mean(values),
            "median": statistics.median(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "latest": values[-1],
            "trend": "up" if len(values) > 1 and values[-1] > values[0] else "down"
        }


class PredictionEngine:
    """预测引擎 - 管理多个预测器"""
    
    def __init__(self):
        self.predictors: Dict[str, Predictor] = {}
        
    def get_or_create_predictor(self, metric_name: str) -> Predictor:
        """获取或创建预测器"""
        if metric_name not in self.predictors:
            self.predictors[metric_name] = Predictor()
        return self.predictors[metric_name]
    
    def predict_metric(self, metric_name: str, steps: int = 1, 
                       model: str = "exponential_smoothing") -> Dict[str, Any]:
        """预测指定指标"""
        predictor = self.get_or_create_predictor(metric_name)
        result = predictor.predict(steps, model)
        
        return {
            "metric": metric_name,
            "predictions": result.predictions,
            "confidence": result.confidence,
            "model": result.model_type,
            "metadata": result.metadata,
            "statistics": predictor.get_statistics()
        }
    
    def add_metric_data(self, metric_name: str, value: float, timestamp: str = None):
        """添加指标数据"""
        predictor = self.get_or_create_predictor(metric_name)
        predictor.add_data_point(value, timestamp)


if __name__ == "__main__":
    # 测试
    engine = PredictionEngine()
    
    # 模拟CPU使用率数据
    cpu_values = [45, 52, 48, 55, 60, 58, 65, 70, 68, 75]
    for val in cpu_values:
        engine.add_metric_data("cpu_usage", val)
    
    # 预测
    result = engine.predict_metric("cpu_usage", steps=3)
    print(json.dumps(result, indent=2))