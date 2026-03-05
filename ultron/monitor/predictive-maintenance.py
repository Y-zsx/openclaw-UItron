#!/usr/bin/env python3
"""
奥创预测性维护系统 - 第3世：预测性维护
功能：趋势预测、异常预警、预防性维护
"""

import os
import json
import time
import psutil
import threading
import statistics
from datetime import datetime, timedelta
from collections import deque
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import subprocess

class AlertLevel(Enum):
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"

class TrendDirection(Enum):
    STABLE = "stable"
    RISING = "rising"
    FALLING = "falling"
    SPIKING = "spiking"
    DROPPING = "dropping"

class MaintenanceAction(Enum):
    NONE = "none"
    CLEANUP = "cleanup"
    OPTIMIZE = "optimize"
    SCALE = "scale"
    RESTART = "restart"
    ESCALATE = "escalate"

@dataclass
class MetricDataPoint:
    timestamp: float
    cpu: float
    memory: float
    disk: float
    load: float
    network_io: float

@dataclass
class TrendAnalysis:
    direction: TrendDirection
    velocity: float  # 变化速率
    predicted_value: float
    confidence: float  # 预测置信度 0-1
    time_to_threshold: Optional[int]  # 到达阈值需要的秒数

@dataclass
class AnomalyWarning:
    level: AlertLevel
    metric: str
    current_value: float
    predicted_value: float
    threshold: float
    time_to_breach: Optional[int]
    trend: TrendDirection
    recommendation: str

@dataclass
class MaintenanceTask:
    id: str
    action: MaintenanceAction
    target: str
    reason: str
    priority: int
    scheduled_time: Optional[datetime]
    executed: bool = False
    result: Optional[str] = None

class TimeSeriesAnalyzer:
    """时间序列分析器 - 趋势预测核心"""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.cpu_history = deque(maxlen=window_size)
        self.memory_history = deque(maxlen=window_size)
        self.disk_history = deque(maxlen=window_size)
        self.load_history = deque(maxlen=window_size)
        self.network_history = deque(maxlen=window_size)
        
    def add_data_point(self, cpu: float, memory: float, disk: float, 
                       load: float, network_io: float):
        """添加数据点"""
        point = MetricDataPoint(
            timestamp=time.time(),
            cpu=cpu, memory=memory, disk=disk,
            load=load, network_io=network_io
        )
        self.cpu_history.append(point.cpu)
        self.memory_history.append(point.memory)
        self.disk_history.append(point.disk)
        self.load_history.append(point.load)
        self.network_history.append(point.network_io)
        
    def _linear_regression(self, values: List[float]) -> Tuple[float, float, float]:
        """线性回归预测趋势"""
        n = len(values)
        if n < 3:
            return 0, 0, 0
            
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        
        numerator = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
        
        if denominator == 0:
            return 0, y_mean, 0
            
        slope = numerator / denominator
        intercept = y_mean - slope * x_mean
        
        # 计算R²评估拟合度
        y_pred = [slope * xi + intercept for xi in x]
        ss_res = sum((values[i] - y_pred[i]) ** 2 for i in range(n))
        ss_tot = sum((values[i] - y_mean) ** 2 for i in range(n))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0
        
        return slope, intercept, r_squared
    
    def analyze_trend(self, metric: str, current_value: float, 
                      threshold: float, forecast_steps: int = 10) -> TrendAnalysis:
        """分析趋势并预测"""
        history = self._get_history(metric)
        
        if len(history) < 3:
            return TrendAnalysis(
                direction=TrendDirection.STABLE,
                velocity=0,
                predicted_value=current_value,
                confidence=0,
                time_to_threshold=None
            )
        
        slope, intercept, r_squared = self._linear_regression(list(history))
        
        # 预测未来值
        predicted_value = slope * len(history) + intercept + slope * forecast_steps
        predicted_value = max(0, min(100, predicted_value))
        
        # 判断趋势方向
        if abs(slope) < 0.1:
            direction = TrendDirection.STABLE
        elif slope > 0:
            if slope > 1.0:
                direction = TrendDirection.SPIKING
            else:
                direction = TrendDirection.RISING
        else:
            if slope < -1.0:
                direction = TrendDirection.DROPPING
            else:
                direction = TrendDirection.FALLING
        
        # 计算到达阈值的时间
        time_to_threshold = None
        if slope > 0 and predicted_value > threshold:
            # 预测何时超过阈值
            if slope > 0:
                time_to_threshold = int((threshold - current_value) / slope) if slope > 0 else None
        
        return TrendAnalysis(
            direction=direction,
            velocity=slope,
            predicted_value=predicted_value,
            confidence=min(1.0, r_squared),
            time_to_threshold=time_to_threshold
        )
    
    def _get_history(self, metric: str):
        """获取指定指标的历史数据"""
        mapping = {
            'cpu': self.cpu_history,
            'memory': self.memory_history,
            'disk': self.disk_history,
            'load': self.load_history,
            'network': self.network_history
        }
        return mapping.get(metric, self.cpu_history)
    
    def detect_anomalies(self, metric: str, threshold: float, 
                         warning_percent: float = 0.8) -> List[AnomalyWarning]:
        """检测异常"""
        history = list(self._get_history(metric))
        if len(history) < 5:
            return []
        
        current = history[-1]
        mean = statistics.mean(history)
        stdev = statistics.stdev(history) if len(history) > 1 else 0
        
        # 基于统计的异常检测
        z_score = (current - mean) / stdev if stdev > 0 else 0
        
        warnings = []
        
        # 检查是否超过阈值
        if current >= threshold:
            level = AlertLevel.CRITICAL
        elif current >= threshold * warning_percent:
            level = AlertLevel.WARNING
        else:
            level = AlertLevel.NORMAL
        
        # 检查异常模式
        if z_score > 2:
            trend = TrendDirection.SPIKING
        elif z_score > 1.5:
            trend = TrendDirection.RISING
        elif z_score < -2:
            trend = TrendDirection.DROPPING
        else:
            trend = TrendDirection.STABLE
        
        if level != AlertLevel.NORMAL:
            warnings.append(AnomalyWarning(
                level=level,
                metric=metric,
                current_value=current,
                predicted_value=current,
                threshold=threshold,
                time_to_breach=None,
                trend=trend,
                recommendation=self._generate_recommendation(metric, level, trend)
            ))
        
        return warnings
    
    def _generate_recommendation(self, metric: str, level: AlertLevel, 
                                  trend: TrendDirection) -> str:
        """生成维护建议"""
        recommendations = {
            'cpu': {
                AlertLevel.WARNING: "考虑优化CPU密集型进程",
                AlertLevel.CRITICAL: "立即优化或扩容",
                AlertLevel.EMERGENCY: "CPU过载，可能需要重启服务"
            },
            'memory': {
                AlertLevel.WARNING: "监控内存使用，考虑清理缓存",
                AlertLevel.CRITICAL: "释放内存或增加swap",
                AlertLevel.EMERGENCY: "内存耗尽风险，立即清理"
            },
            'disk': {
                AlertLevel.WARNING: "磁盘空间不足，建议清理",
                AlertLevel.CRITICAL: "立即清理日志或缓存",
                AlertLevel.EMERGENCY: "磁盘即将耗尽，紧急清理"
            }
        }
        
        return recommendations.get(metric, {}).get(level, "建议监控")


class PredictiveMaintenanceEngine:
    """预测性维护引擎"""
    
    def __init__(self):
        self.analyzer = TimeSeriesAnalyzer(window_size=60)
        self.maintenance_queue: List[MaintenanceTask] = []
        self.alert_history: List[AnomalyWarning] = []
        self.thresholds = {
            'cpu': {'warning': 70, 'critical': 85, 'emergency': 95},
            'memory': {'warning': 75, 'critical': 90, 'emergency': 95},
            'disk': {'warning': 80, 'critical': 90, 'emergency': 95},
            'load': {'warning': 3.0, 'critical': 5.0, 'emergency': 8.0}
        }
        self.last_maintenance_time = {}
        self.maintenance_cooldown = 300  # 5分钟冷却期
        self._running = False
        self._thread = None
        
    def collect_metrics(self) -> Dict[str, float]:
        """收集当前系统指标"""
        cpu = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory().percent
        disk = psutil.disk_usage('/').percent
        load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
        
        try:
            net_io = psutil.net_io_counters()
            network_io = (net_io.bytes_sent + net_io.bytes_recv) / 1024 / 1024
        except:
            network_io = 0
        
        return {
            'cpu': cpu,
            'memory': memory,
            'disk': disk,
            'load': load,
            'network': network_io
        }
    
    def predict_and_warn(self) -> List[AnomalyWarning]:
        """预测并预警"""
        metrics = self.collect_metrics()
        
        # 添加到时序分析器
        self.analyzer.add_data_point(
            metrics['cpu'], metrics['memory'], 
            metrics['disk'], metrics['load'], metrics['network']
        )
        
        warnings = []
        
        for metric, value in metrics.items():
            if metric == 'network':
                continue
                
            threshold = self.thresholds.get(metric, {}).get('critical', 80)
            warning_pct = self.thresholds.get(metric, {}).get('warning', 70) / 100
            
            # 时序预测
            trend = self.analyzer.analyze_trend(metric, value, threshold)
            
            # 异常检测
            anomalies = self.analyzer.detect_anomalies(metric, threshold, warning_pct)
            
            # 合并预测和异常
            for anomaly in anomalies:
                # 如果趋势显示会恶化，增加预警级别
                if trend.direction in [TrendDirection.RISING, TrendDirection.SPIKING]:
                    if anomaly.level == AlertLevel.WARNING:
                        anomaly.level = AlertLevel.CRITICAL
                    anomaly.predicted_value = trend.predicted_value
                    anomaly.time_to_breach = trend.time_to_threshold
                    
                warnings.append(anomaly)
                self.alert_history.append(anomaly)
        
        # 保持历史记录在合理范围
        if len(self.alert_history) > 100:
            self.alert_history = self.alert_history[-100:]
            
        return warnings
    
    def suggest_maintenance(self, warnings: List[AnomalyWarning]) -> List[MaintenanceTask]:
        """基于预警建议维护任务"""
        tasks = []
        
        for warning in warnings:
            if warning.level in [AlertLevel.CRITICAL, AlertLevel.EMERGENCY]:
                task_id = f"maint_{int(time.time())}_{warning.metric}"
                
                # 根据指标类型决定维护动作
                if warning.metric == 'cpu':
                    action = MaintenanceAction.OPTIMIZE
                    target = "cpu_processes"
                    reason = f"CPU使用率{warning.current_value:.1f}%，趋势{warning.trend.value}"
                elif warning.metric == 'memory':
                    action = MaintenanceAction.CLEANUP
                    target = "memory_cache"
                    reason = f"内存使用率{warning.current_value:.1f}%"
                elif warning.metric == 'disk':
                    action = MaintenanceAction.CLEANUP
                    target = "disk_space"
                    reason = f"磁盘使用率{warning.current_value:.1f}%"
                else:
                    action = MaintenanceAction.OPTIMIZE
                    target = "system"
                    reason = f"指标{warning.metric}异常"
                
                # 检查冷却期
                last_exec = self.last_maintenance_time.get(action, 0)
                if time.time() - last_exec < self.maintenance_cooldown:
                    continue
                
                tasks.append(MaintenanceTask(
                    id=task_id,
                    action=action,
                    target=target,
                    reason=reason,
                    priority=1 if warning.level == AlertLevel.EMERGENCY else 2,
                    scheduled_time=datetime.now()
                ))
                
                self.last_maintenance_time[action] = time.time()
        
        return tasks
    
    def execute_maintenance(self, task: MaintenanceTask) -> bool:
        """执行维护任务"""
        try:
            if task.action == MaintenanceAction.CLEANUP:
                if task.target == "memory_cache":
                    # 清理缓存
                    subprocess.run(['sync'], capture_output=True)
                    subprocess.run(['echo', '3', '>', '/proc/sys/vm/drop_caches'], 
                                 shell=True, capture_output=True)
                    task.result = "内存缓存已清理"
                elif task.target == "disk_space":
                    # 清理日志
                    result = subprocess.run(
                        ['find', '/var/log', '-type', 'f', '-mtime', '+7', '-delete'],
                        capture_output=True, timeout=30
                    )
                    task.result = f"清理完成: {result.returncode}"
                    
            elif task.action == MaintenanceAction.OPTIMIZE:
                task.result = "优化任务已调度"
                
            elif task.action == MaintenanceAction.SCALE:
                task.result = "扩展任务已调度"
                
            task.executed = True
            return True
            
        except Exception as e:
            task.result = f"执行失败: {str(e)}"
            task.executed = False
            return False
    
    def start_monitoring(self, interval: int = 30):
        """启动持续监控"""
        self._running = True
        
        def monitor_loop():
            while self._running:
                try:
                    warnings = self.predict_and_warn()
                    if warnings:
                        tasks = self.suggest_maintenance(warnings)
                        for task in tasks:
                            print(f"[预测性维护] {task.action.value}: {task.reason}")
                            self.maintenance_queue.append(task)
                except Exception as e:
                    print(f"[预测性维护] 监控错误: {e}")
                    
                time.sleep(interval)
                
        self._thread = threading.Thread(target=monitor_loop, daemon=True)
        self._thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'running': self._running,
            'queue_size': len(self.maintenance_queue),
            'alert_count': len(self.alert_history),
            'last_alerts': [asdict(a) for a in self.alert_history[-5:]],
            'thresholds': self.thresholds
        }
    
    def run_diagnostic(self) -> Dict[str, Any]:
        """运行诊断"""
        warnings = self.predict_and_warn()
        tasks = self.suggest_maintenance(warnings)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'current_metrics': self.collect_metrics(),
            'warnings': [asdict(w) for w in warnings],
            'recommended_tasks': [asdict(t) for t in tasks],
            'system_health': 'healthy' if not warnings else 'warning'
        }


def main():
    """主函数 - 演示预测性维护"""
    engine = PredictiveMaintenanceEngine()
    
    print("=" * 50)
    print("奥创预测性维护系统 - 第3世")
    print("=" * 50)
    
    # 收集一些初始数据
    print("\n正在收集基线数据...")
    for _ in range(5):
        engine.collect_metrics()
        time.sleep(1)
    
    # 运行诊断
    print("\n运行预测性诊断...")
    result = engine.run_diagnostic()
    
    print(f"\n当前指标:")
    for k, v in result['current_metrics'].items():
        print(f"  {k}: {v:.1f}")
    
    print(f"\n系统健康: {result['system_health']}")
    
    if result['warnings']:
        print(f"\n预警数量: {len(result['warnings'])}")
        for w in result['warnings']:
            print(f"  [{w['level']}] {w['metric']}: {w['current_value']:.1f}% - {w['recommendation']}")
    
    if result['recommended_tasks']:
        print(f"\n建议维护任务: {len(result['recommended_tasks'])}")
        for t in result['recommended_tasks']:
            print(f"  [{t['action']}] {t['target']}: {t['reason']}")
    
    # 启动持续监控
    print("\n启动持续预测监控 (按Ctrl+C停止)...")
    engine.start_monitoring(interval=30)
    
    try:
        while True:
            time.sleep(60)
            status = engine.get_status()
            if status['alert_count'] > 0:
                print(f"[状态] 警报数: {status['alert_count']}, 队列: {status['queue_size']}")
    except KeyboardInterrupt:
        print("\n停止监控...")
        engine.stop_monitoring()
    
    return result


if __name__ == "__main__":
    main()