#!/usr/bin/env python3
"""
Agent服务自动扩缩容系统
=======================
根据负载和性能指标自动调整Agent实例数量

功能:
- 基于指标的自动扩缩容
- 多种扩缩容策略
- 扩缩容事件记录
- 冷却期管理
- 最小/最大实例数限制

端口: 18160
"""

import json
import time
import threading
import asyncio
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import statistics


class ScalingAction(Enum):
    """扩缩容动作"""
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"
    NONE = "none"


class ScalingPolicy(Enum):
    """扩缩容策略"""
    REACTIVE = "reactive"        # 被动响应式
    PREDICTIVE = "predictive"    # 预测式
    SCHEDULED = "scheduled"      # 定时式
    HYBRID = "hybrid"            # 混合式


class MetricType(Enum):
    """指标类型"""
    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    TASK_QUEUE_LENGTH = "task_queue_length"
    RESPONSE_TIME = "response_time"
    ERROR_RATE = "error_rate"
    REQUEST_RATE = "request_rate"


@dataclass
class ScalingConfig:
    """扩缩容配置"""
    min_instances: int = 1
    max_instances: int = 10
    scale_up_threshold: float = 0.8      # 扩容阈值 (0-1)
    scale_down_threshold: float = 0.3    # 缩容阈值 (0-1)
    scale_up_cooldown: int = 60          # 扩容冷却期 (秒)
    scale_down_cooldown: int = 300       # 缩容冷却期 (秒)
    scale_step: int = 1                  # 每次扩缩容步长
    policy: str = "hybrid"               # 扩缩容策略


@dataclass
class ScalingMetric:
    """扩缩容指标"""
    timestamp: float
    metric_type: str
    value: float
    agent_id: Optional[str] = None


@dataclass
class ScalingEvent:
    """扩缩容事件"""
    timestamp: str
    action: str
    reason: str
    old_instances: int
    new_instances: int
    metrics: Dict[str, float]


@dataclass
class AgentInstance:
    """Agent实例"""
    instance_id: str
    agent_type: str
    status: str = "starting"
    port: Optional[int] = None
    process: Optional[Any] = None
    start_time: Optional[datetime] = None
    metrics: Dict[str, float] = field(default_factory=dict)


class MetricsCollector:
    """指标收集器"""
    
    def __init__(self, window_size: int = 60):
        self.window_size = window_size
        self.metrics: Dict[str, deque] = {}
        self._lock = threading.Lock()
    
    def add_metric(self, agent_id: str, metric_type: str, value: float):
        with self._lock:
            key = f"{agent_id}:{metric_type}"
            if key not in self.metrics:
                self.metrics[key] = deque(maxlen=self.window_size)
            self.metrics[key].append({
                'timestamp': time.time(),
                'value': value
            })
    
    def get_average(self, agent_id: str, metric_type: str, 
                    seconds: int = 60) -> float:
        with self._lock:
            key = f"{agent_id}:{metric_type}"
            if key not in self.metrics:
                return 0.0
            
            cutoff = time.time() - seconds
            values = [m['value'] for m in self.metrics[key] 
                     if m['timestamp'] >= cutoff]
            return statistics.mean(values) if values else 0.0
    
    def get_trend(self, agent_id: str, metric_type: str,
                  seconds: int = 60) -> float:
        """获取指标趋势 (正数=上升, 负数=下降)"""
        with self._lock:
            key = f"{agent_id}:{metric_type}"
            if key not in self.metrics:
                return 0.0
            
            cutoff = time.time() - seconds
            values = [m['value'] for m in self.metrics[key]
                     if m['timestamp'] >= cutoff]
            if len(values) < 2:
                return 0.0
            
            # 简单线性回归斜率
            n = len(values)
            x = list(range(n))
            sum_x = sum(x)
            sum_y = sum(values)
            sum_xy = sum(x[i] * values[i] for i in range(n))
            sum_xx = sum(x[i] * x[i] for i in range(n))
            
            if n * sum_xx - sum_x * sum_x == 0:
                return 0.0
            
            slope = (n * sum_xy - sum_x * sum_y) / (n * sum_xx - sum_x * sum_x)
            return slope


class AutoScaler:
    """自动扩缩容引擎"""
    
    def __init__(self, agent_type: str, config: ScalingConfig = None):
        self.agent_type = agent_type
        self.config = config or ScalingConfig()
        self.instances: Dict[str, AgentInstance] = {}
        self.metrics_collector = MetricsCollector()
        self.scaling_history: List[ScalingEvent] = []
        self.last_scale_up: float = 0
        self.last_scale_down: float = 0
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread = None
        self._scale_callbacks: List[Callable] = []
        
        # 预测式扩缩容数据
        self.prediction_window = 5
        self.last_predictions: deque = deque(maxlen=10)
    
    def register_scale_callback(self, callback: Callable):
        """注册扩缩容回调"""
        self._scale_callbacks.append(callback)
    
    def _should_scale_up(self, avg_metrics: Dict[str, float]) -> bool:
        """判断是否应该扩容"""
        current_time = time.time()
        
        # 冷却期检查
        if current_time - self.last_scale_up < self.config.scale_up_cooldown:
            return False
        
        # 实例数上限检查
        if len(self.instances) >= self.config.max_instances:
            return False
        
        # 多指标判断
        score = 0
        reasons = []
        
        # CPU使用率
        cpu = avg_metrics.get('cpu_usage', 0)
        if cpu > self.config.scale_up_threshold * 100:
            score += 2
            reasons.append(f"CPU {cpu:.1f}%")
        
        # 内存使用率
        memory = avg_metrics.get('memory_usage', 0)
        if memory > self.config.scale_up_threshold * 100:
            score += 2
            reasons.append(f"内存 {memory:.1f}%")
        
        # 任务队列长度
        queue = avg_metrics.get('task_queue_length', 0)
        max_queue = self.config.max_instances * 10
        if queue > max_queue * self.config.scale_up_threshold:
            score += 3
            reasons.append(f"队列 {queue}")
        
        # 响应时间
        response_time = avg_metrics.get('response_time', 0)
        if response_time > 1000:  # 1秒
            score += 2
            reasons.append(f"响应 {response_time:.0f}ms")
        
        # 错误率
        error_rate = avg_metrics.get('error_rate', 0)
        if error_rate > 0.1:  # 10%
            score += 2
            reasons.append(f"错误率 {error_rate*100:.1f}%")
        
        # 上升趋势检测
        trend = self.metrics_collector.get_trend(
            self.agent_type, MetricType.CPU_USAGE.value
        )
        if trend > 0.5:
            score += 1
            reasons.append("CPU上升趋势")
        
        return score >= 4
    
    def _should_scale_down(self, avg_metrics: Dict[str, float]) -> bool:
        """判断是否应该缩容"""
        current_time = time.time()
        
        # 冷却期检查
        if current_time - self.last_scale_down < self.config.scale_down_cooldown:
            return False
        
        # 实例数下限检查
        if len(self.instances) <= self.config.min_instances:
            return False
        
        # 多指标判断
        score = 0
        reasons = []
        
        # CPU使用率
        cpu = avg_metrics.get('cpu_usage', 0)
        if cpu < self.config.scale_down_threshold * 100:
            score += 2
            reasons.append(f"CPU {cpu:.1f}%")
        
        # 内存使用率
        memory = avg_metrics.get('memory_usage', 0)
        if memory < self.config.scale_down_threshold * 100:
            score += 2
            reasons.append(f"内存 {memory:.1f}%")
        
        # 任务队列长度
        queue = avg_metrics.get('task_queue_length', 0)
        if queue < 2:
            score += 3
            reasons.append(f"队列 {queue}")
        
        # 响应时间
        response_time = avg_metrics.get('response_time', 0)
        if response_time < 100:  # 100ms
            score += 1
            reasons.append(f"响应 {response_time:.0f}ms")
        
        # 错误率
        error_rate = avg_metrics.get('error_rate', 0)
        if error_rate < 0.01:  # 1%
            score += 1
            reasons.append(f"错误率 {error_rate*100:.1f}%")
        
        # 下降趋势检测
        trend = self.metrics_collector.get_trend(
            self.agent_type, MetricType.CPU_USAGE.value
        )
        if trend < -0.3:
            score += 1
            reasons.append("CPU下降趋势")
        
        return score >= 5
    
    def _collect_system_metrics(self) -> Dict[str, float]:
        """收集系统指标"""
        metrics = {}
        
        try:
            # CPU使用率
            result = subprocess.run(
                ["sh", "-c", "top -bn1 | grep 'Cpu(s)' | awk '{print $2}'"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                metrics['cpu_usage'] = float(result.stdout.strip())
            
            # 内存使用率
            result = subprocess.run(
                ["sh", "-c", "free | grep Mem | awk '{print $3/$2 * 100}'"],
                capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                metrics['memory_usage'] = float(result.stdout.strip())
        except:
            pass
        
        return metrics
    
    def _collect_agent_metrics(self) -> Dict[str, float]:
        """收集Agent指标"""
        metrics = {}
        
        try:
            # 从监控API获取Agent指标
            for port in [18091, 18092, 18093, 18094, 18095]:
                try:
                    resp = requests.get(
                        f"http://localhost:{port}/health",
                        timeout=2
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        metrics['task_queue_length'] = data.get(
                            'task_queue', data.get('pending_tasks', 0)
                        )
                        metrics['active_agents'] = data.get(
                            'active_agents', data.get('agents', 0)
                        )
                        break
                except:
                    continue
        except:
            pass
        
        return metrics
    
    def calculate_avg_metrics(self) -> Dict[str, float]:
        """计算平均指标"""
        system_metrics = self._collect_system_metrics()
        agent_metrics = self._collect_agent_metrics()
        return {**system_metrics, **agent_metrics}
    
    def scale_up(self, reason: str = "") -> bool:
        """执行扩容"""
        with self._lock:
            if len(self.instances) >= self.config.max_instances:
                return False
            
            old_count = len(self.instances)
            new_count = min(old_count + self.config.scale_step, 
                          self.config.max_instances)
            
            # 触发扩容回调
            for callback in self._scale_callbacks:
                try:
                    callback(ScalingAction.SCALE_UP, old_count, new_count, reason)
                except Exception as e:
                    print(f"Scale callback error: {e}")
            
            self.last_scale_up = time.time()
            
            # 记录事件
            event = ScalingEvent(
                timestamp=datetime.now().isoformat(),
                action=ScalingAction.SCALE_UP.value,
                reason=reason,
                old_instances=old_count,
                new_instances=new_count,
                metrics=self.calculate_avg_metrics()
            )
            self.scaling_history.append(event)
            
            return True
    
    def scale_down(self, reason: str = "") -> bool:
        """执行缩容"""
        with self._lock:
            if len(self.instances) <= self.config.min_instances:
                return False
            
            old_count = len(self.instances)
            new_count = max(old_count - self.config.scale_step,
                          self.config.min_instances)
            
            # 触发缩容回调
            for callback in self._scale_callbacks:
                try:
                    callback(ScalingAction.SCALE_DOWN, old_count, new_count, reason)
                except Exception as e:
                    print(f"Scale callback error: {e}")
            
            self.last_scale_down = time.time()
            
            # 记录事件
            event = ScalingEvent(
                timestamp=datetime.now().isoformat(),
                action=ScalingAction.SCALE_DOWN.value,
                reason=reason,
                old_instances=old_count,
                new_instances=new_count,
                metrics=self.calculate_avg_metrics()
            )
            self.scaling_history.append(event)
            
            return True
    
    def evaluate_scaling(self) -> ScalingAction:
        """评估是否需要扩缩容"""
        avg_metrics = self.calculate_avg_metrics()
        
        # 更新历史指标
        for metric_type, value in avg_metrics.items():
            self.metrics_collector.add_metric(
                self.agent_type, metric_type, value
            )
        
        # 判断扩容
        if self._should_scale_up(avg_metrics):
            reason = f"指标: {', '.join([k for k,v in avg_metrics.items() if v > 50])}"
            self.scale_up(reason)
            return ScalingAction.SCALE_UP
        
        # 判断缩容
        if self._should_scale_down(avg_metrics):
            reason = f"指标: {', '.join([k for k,v in avg_metrics.items() if v < 30])}"
            self.scale_down(reason)
            return ScalingAction.SCALE_DOWN
        
        return ScalingAction.NONE
    
    def start_auto_scaling(self, interval: int = 30):
        """启动自动扩缩容"""
        if self._running:
            return
        
        self._running = True
        
        def monitor_loop():
            while self._running:
                try:
                    action = self.evaluate_scaling()
                    if action != ScalingAction.NONE:
                        print(f"[AutoScaler] {self.agent_type}: {action.value}")
                except Exception as e:
                    print(f"[AutoScaler] Error: {e}")
                
                time.sleep(interval)
        
        self._monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_auto_scaling(self):
        """停止自动扩缩容"""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            'agent_type': self.agent_type,
            'current_instances': len(self.instances),
            'min_instances': self.config.min_instances,
            'max_instances': self.config.max_instances,
            'config': {
                'scale_up_threshold': self.config.scale_up_threshold,
                'scale_down_threshold': self.config.scale_down_threshold,
                'scale_up_cooldown': self.config.scale_up_cooldown,
                'scale_down_cooldown': self.config.scale_down_cooldown,
                'policy': self.config.policy
            },
            'last_scale_up': self.last_scale_up,
            'last_scale_down': self.last_scale_down,
            'avg_metrics': self.calculate_avg_metrics(),
            'scaling_history': [
                {
                    'timestamp': e.timestamp,
                    'action': e.action,
                    'reason': e.reason,
                    'old_instances': e.old_instances,
                    'new_instances': e.new_instances
                }
                for e in self.scaling_history[-10:]
            ]
        }


class AutoScalerManager:
    """自动扩缩容管理器"""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._scalers = {}
                    cls._instance._lock2 = threading.Lock()
        return cls._instance
    
    def get_or_create_scaler(
        self, 
        agent_type: str, 
        config: ScalingConfig = None
    ) -> AutoScaler:
        with self._lock2:
            if agent_type not in self._scalers:
                self._scalers[agent_type] = AutoScaler(agent_type, config)
            return self._scalers[agent_type]
    
    def remove_scaler(self, agent_type: str) -> bool:
        with self._lock2:
            if agent_type in self._scalers:
                self._scalers[agent_type].stop_auto_scaling()
                del self._scalers[agent_type]
                return True
            return False
    
    def get_all_status(self) -> Dict[str, Any]:
        with self._lock2:
            return {
                agent_type: scaler.get_status()
                for agent_type, scaler in self._scalers.items()
            }


# 全局单例
def get_scaler_manager() -> AutoScalerManager:
    return AutoScalerManager()


def get_scaler(agent_type: str, config: ScalingConfig = None) -> AutoScaler:
    return get_scaler_manager().get_or_create_scaler(agent_type, config)


if __name__ == "__main__":
    import sys
    
    # 测试
    config = ScalingConfig(
        min_instances=1,
        max_instances=5,
        scale_up_threshold=0.7,
        scale_down_threshold=0.3,
        scale_up_cooldown=30,
        scale_down_cooldown=120
    )
    
    scaler = get_scaler("test-agent", config)
    print("AutoScaler created:", scaler.get_status())
    
    # 启动自动扩缩容
    scaler.start_auto_scaling(interval=10)
    
    try:
        while True:
            time.sleep(5)
            print("Status:", json.dumps(scaler.get_status(), indent=2))
    except KeyboardInterrupt:
        scaler.stop_auto_scaling()