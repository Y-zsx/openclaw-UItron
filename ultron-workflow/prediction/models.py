# 预测模型定义
from enum import Enum
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

class ModelType(Enum):
    """支持的预测模型类型"""
    MOVING_AVERAGE = "moving_average"
    EXPONENTIAL_SMOOTHING = "exponential_smoothing"
    LINEAR_TREND = "linear_trend"
    SIMPLE_FORECAST = "simple"

@dataclass
class ForecastResult:
    """预测结果"""
    predictions: List[float]
    confidence: float
    model_type: ModelType
    metadata: Dict[str, Any]

@dataclass
class TimeSeriesData:
    """时间序列数据"""
    timestamps: List[str]
    values: List[float]
    metric_name: str
    
    def __len__(self):
        return len(self.values)