#!/usr/bin/env python3
"""
智能预测告警脚本 - 快速版
功能：基于历史数据预测资源趋势，提前告警
"""

import os
import json
import time
import psutil
import statistics
from datetime import datetime
from collections import deque
from typing import Dict, Optional, Tuple

class QuickPredictor:
    """快速趋势预测器"""
    
    def __init__(self, history_size=20):
        self.history = {
            'cpu': deque(maxlen=history_size),
            'memory': deque(maxlen=history_size),
            'disk': deque(maxlen=history_size),
            'load': deque(maxlen=history_size)
        }
        self.thresholds = {
            'cpu': 80,
            'memory': 85,
            'disk': 90,
            'load': 5.0
        }
        self.alerts = []
    
    def collect_metrics(self):
        """收集当前指标"""
        return {
            'cpu': psutil.cpu_percent(interval=0.5),
            'memory': psutil.virtual_memory().percent,
            'disk': psutil.disk_usage('/').percent,
            'load': psutil.getloadavg()[0]
        }
    
    def add_sample(self, metrics: Dict):
        """添加样本到历史"""
        for key, value in metrics.items():
            if key in self.history:
                self.history[key].append(value)
    
    def predict_trend(self, metric: str, current_value: float = None, steps: int = 5) -> Tuple[str, float, float, Optional[int]]:
        """预测趋势: 返回 (方向, 当前值, 预测值, 到达阈值时间秒)"""
        data = list(self.history.get(metric, []))
        
        if current_value is None:
            current_value = data[-1] if data else 0
        
        if len(data) < 3:
            return 'stable', current_value, current_value, None
        
        # 简单线性回归
        n = len(data)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(data)
        
        numerator = sum((i - x_mean) * (data[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 'stable', data[-1], data[-1], None
        
        slope = numerator / denominator
        
        # 预测未来
        predicted = data[-1] + slope * steps
        predicted = max(0, min(100, predicted))
        
        # 方向判断
        if abs(slope) < 0.5:
            direction = 'stable'
        elif slope > 0:
            direction = 'rising' if slope < 2 else 'spiking'
        else:
            direction = 'falling' if slope > -2 else 'dropping'
        
        # 计算到达阈值的时间
        threshold = self.thresholds.get(metric, 80)
        current = data[-1]
        time_to_threshold = None
        
        if slope > 0 and current < threshold:
            remaining = threshold - current
            time_to_threshold = int(remaining / slope * len(data)) if slope > 0 else None
        
        return direction, current, predicted, time_to_threshold
    
    def check_alerts(self, metrics: Dict) -> list:
        """检查是否需要告警"""
        self.alerts = []
        
        for metric in ['cpu', 'memory', 'disk', 'load']:
            current = metrics.get(metric, 0)
            direction, _, predicted, time_to = self.predict_trend(metric, current)
            
            threshold = self.thresholds.get(metric, 80)
            
            # 当前超阈值
            if current >= threshold:
                self.alerts.append({
                    'level': 'critical',
                    'metric': metric,
                    'current': current,
                    'message': f'{metric.upper()} 当前值 {current:.1f}% 已超过阈值 {threshold}%'
                })
            # 预测超阈值
            elif predicted >= threshold and time_to and time_to < 300:  # 5分钟内
                self.alerts.append({
                    'level': 'warning',
                    'metric': metric,
                    'current': current,
                    'predicted': predicted,
                    'time_to': time_to,
                    'message': f'{metric.upper()} 预测 {time_to}秒 后超阈值 (当前{current:.1f}%→预测{predicted:.1f}%)'
                })
            # 趋势上升警告
            elif direction in ['rising', 'spiking'] and current > threshold * 0.7:
                self.alerts.append({
                    'level': 'info',
                    'metric': metric,
                    'direction': direction,
                    'current': current,
                    'message': f'{metric.upper()} 上升趋势 ({direction}), 当前 {current:.1f}%'
                })
        
        return self.alerts


def main():
    predictor = QuickPredictor()
    metrics = predictor.collect_metrics()
    
    # 加载历史数据
    hist_file = '/tmp/ultron_predictive_history.json'
    if os.path.exists(hist_file):
        try:
            with open(hist_file, 'r') as f:
                saved = json.load(f)
                for metric, values in saved.items():
                    if metric in predictor.history:
                        for v in values:
                            predictor.history[metric].append(v)
        except:
            pass
    
    # 添加当前样本
    predictor.add_sample(metrics)
    
    # 保存历史
    history_to_save = {k: list(v) for k, v in predictor.history.items()}
    with open(hist_file, 'w') as f:
        json.dump(history_to_save, f)
    
    # 预测分析
    alerts = predictor.check_alerts(metrics)
    
    print(f"=== 智能预测告警 ({datetime.now().strftime('%Y-%m-%d %H:%M:%S')}) ===")
    print(f"当前指标: CPU {metrics['cpu']:.1f}% | 内存 {metrics['memory']:.1f}% | 磁盘 {metrics['disk']:.1f}% | 负载 {metrics['load']:.2f}")
    print()
    
    if alerts:
        for alert in alerts:
            level_emoji = {'critical': '🔴', 'warning': '🟡', 'info': '🟢'}.get(alert['level'], '⚪')
            print(f"{level_emoji} [{alert['level'].upper()}] {alert['message']}")
    else:
        print("✅ 系统运行正常，无预测告警")
    
    # 打印趋势摘要
    print("\n趋势预测:")
    for metric in ['cpu', 'memory', 'disk', 'load']:
        direction, current, predicted, time_to = predictor.predict_trend(metric, metrics.get(metric, 0))
        emoji = {'stable': '➡️', 'rising': '📈', 'spiking': '🚀', 'falling': '📉', 'dropping': '💨'}.get(direction, '❓')
        print(f"  {emoji} {metric.upper()}: {current:.1f}% → 预测 {predicted:.1f}% (趋势: {direction})")
    
    return len([a for a in alerts if a['level'] in ['critical', 'warning']])


if __name__ == '__main__':
    exit_code = main()
    exit(max(0, exit_code))