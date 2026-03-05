#!/usr/bin/env python3
"""
Predictive Alert Module - 智能预测告警
功能：基于历史数据分析趋势，预测未来可能发生的告警

第45世任务：智能预测告警
"""

import json
import os
import time
from collections import deque
from datetime import datetime
from pathlib import Path

# 配置路径
HISTORY_FILE = "/root/.openclaw/workspace/ultron/logs/metrics-history.json"
MAX_HISTORY = 60  # 保留最近60个数据点

class PredictiveAlert:
    def __init__(self):
        self.history = self._load_history()
        self.prediction_window = 10  # 预测未来10个时间单位
        
    def _load_history(self):
        """加载历史数据"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    data = json.load(f)
                    # 转换为deque以高效处理
                    return deque(data.get('metrics', []), maxlen=MAX_HISTORY)
            except:
                return deque(maxlen=MAX_HISTORY)
        return deque(maxlen=MAX_HISTORY)
    
    def _save_history(self):
        """保存历史数据"""
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        data = {
            'metrics': list(self.history),
            'last_update': datetime.now().isoformat()
        }
        with open(HISTORY_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    
    def add_metrics(self, metrics: dict):
        """添加新的指标数据"""
        # 提取关键指标
        entry = {
            'timestamp': datetime.now().isoformat(),
            'load': metrics.get('load', 0),
            'memory_pct': metrics.get('memory_pct', 0),
            'disk_pct': metrics.get('disk_pct', 0),
        }
        self.history.append(entry)
        self._save_history()
    
    def _calculate_trend(self, values: list) -> dict:
        """计算趋势（简单线性回归）"""
        if len(values) < 3:
            return {'trend': 'stable', 'rate': 0, 'prediction': values[-1] if values else 0}
        
        n = len(values)
        x = list(range(n))
        y = values
        
        # 计算斜率（简单线性回归）
        x_mean = sum(x) / n
        y_mean = sum(y) / n
        
        numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return {'trend': 'stable', 'rate': 0, 'prediction': values[-1]}
        
        slope = numerator / denominator
        
        # 预测未来值
        future_x = n + self.prediction_window
        prediction = y_mean + slope * (future_x - x_mean)
        
        # 确定趋势方向
        if slope > 0.1:
            trend = 'rising'
        elif slope < -0.1:
            trend = 'falling'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'rate': round(slope, 3),
            'prediction': round(prediction, 2),
            'current': values[-1],
            'avg': round(sum(values) / n, 2)
        }
    
    def predict(self) -> dict:
        """预测未来告警"""
        if len(self.history) < 3:
            return {
                'status': 'insufficient_data',
                'message': '数据点不足，无法预测',
                'predictions': {}
            }
        
        # 提取历史数据
        loads = [m['load'] for m in self.history]
        memory = [m['memory_pct'] for m in self.history]
        disk = [m['disk_pct'] for m in self.history]
        
        # 计算各指标趋势
        load_trend = self._calculate_trend(loads)
        memory_trend = self._calculate_trend(memory)
        disk_trend = self._calculate_trend(disk)
        
        # 定义告警阈值
        thresholds = {
            'load': {'warning': 4, 'critical': 6},
            'memory_pct': {'warning': 70, 'critical': 85},
            'disk_pct': {'warning': 75, 'critical': 90}
        }
        
        predictions = {}
        alerts = []
        
        # 分析每个指标
        for metric, trend_data in [('load', load_trend), ('memory_pct', memory_trend), ('disk_pct', disk_trend)]:
            prediction = trend_data['prediction']
            threshold = thresholds.get(metric, {})
            
            predictions[metric] = {
                'current': trend_data['current'],
                'trend': trend_data['trend'],
                'rate': trend_data['rate'],
                'prediction': prediction,
                'threshold_warning': threshold.get('warning'),
                'threshold_critical': threshold.get('critical')
            }
            
            # 检查预测是否超过阈值
            if prediction >= threshold.get('critical', 100):
                alerts.append({
                    'metric': metric,
                    'level': 'critical',
                    'message': f'{metric} 预测将达到 {prediction}，超过严重阈值 {threshold.get("critical")}',
                    'current': trend_data['current'],
                    'prediction': prediction,
                    'threshold': threshold.get('critical'),
                    'trend': trend_data['trend']
                })
            elif prediction >= threshold.get('warning', 80):
                alerts.append({
                    'metric': metric,
                    'level': 'warning',
                    'message': f'{metric} 预测将达到 {prediction}，超过警告阈值 {threshold.get("warning")}',
                    'current': trend_data['current'],
                    'prediction': prediction,
                    'threshold': threshold.get('warning'),
                    'trend': trend_data['trend']
                })
        
        return {
            'status': 'analyzed',
            'timestamp': datetime.now().isoformat(),
            'data_points': len(self.history),
            'predictions': predictions,
            'alerts': alerts
        }
    
    def get_trend_summary(self) -> str:
        """获取趋势摘要"""
        if len(self.history) < 3:
            return "数据不足，无法分析趋势"
        
        prediction = self.predict()
        if prediction['status'] == 'insufficient_data':
            return "数据不足，无法分析趋势"
        
        summary_parts = []
        for metric, pred in prediction['predictions'].items():
            trend = pred['trend']
            current = pred['current']
            prediction_val = pred['prediction']
            
            if trend == 'rising':
                summary_parts.append(
                    f"{metric}: 上升趋势 (当前{current}→预测{prediction_val})"
                )
            elif trend == 'falling':
                summary_parts.append(
                    f"{metric}: 下降趋势 (当前{current}→预测{prediction_val})"
                )
            else:
                summary_parts.append(
                    f"{metric}: 稳定 (当前{current})"
                )
        
        return ", ".join(summary_parts)


def test_predictive_alert():
    """测试预测告警"""
    predictor = PredictiveAlert()
    
    # 模拟添加历史数据（上升趋势）
    for i in range(10):
        predictor.add_metrics({
            'load': 2 + i * 0.3,
            'memory_pct': 50 + i * 2,
            'disk_pct': 70 + i * 0.5
        })
    
    # 进行预测
    result = predictor.predict()
    print("=== 预测分析结果 ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 输出趋势摘要
    print("\n=== 趋势摘要 ===")
    print(predictor.get_trend_summary())
    
    return result


if __name__ == "__main__":
    test_predictive_alert()