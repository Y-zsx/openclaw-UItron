#!/usr/bin/env python3
"""
光年延迟处理器 (Light-Latency Handler)
处理光年级别通信延迟的系统

功能:
- 自适应延迟补偿
- 批量传输优化
- 预测性预取
- 异步消息队列
"""

import time
import asyncio
import heapq
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
from threading import Thread, Lock
import math


class LatencyClass(Enum):
    """延迟等级"""
    LOCAL = 0           # 本地 (< 1秒)
    NEAR_STAR = 1       # 近星 (< 10光秒)
    SOLAR_SYSTEM = 2    # 太阳系 (< 1光年)
    NEARBY_STAR = 3     # 近邻星 (1-10光年)
    GALACTIC = 4        # 银河系 (10-100光年)
    INTER_GALACTIC = 5  # 星系间 (> 100光年)


@dataclass
class TransmissionRecord:
    """传输记录"""
    message_id: str
    send_time: float
    estimated_arrival: float
    actual_arrival: Optional[float] = None
    retry_count: int = 0
    status: str = "pending"
    payload_size: int = 0
    
    @property
    def actual_latency(self) -> Optional[float]:
        if self.actual_arrival:
            return self.actual_arrival - self.send_time
        return None
    
    @property
    def delay_factor(self) -> float:
        if self.actual_latency and self.estimated_arrival > self.send_time:
            return self.actual_latency / (self.estimated_arrival - self.send_time)
        return 1.0


class AdaptiveLatencyCompensator:
    """自适应延迟补偿器"""
    
    # 光速 (光秒/秒)
    SPEED_OF_LIGHT = 1.0  # 1光秒/秒
    
    def __init__(self):
        self.latency_history: Dict[str, List[float]] = {}
        self.observed_delays: Dict[Tuple[str, str], List[float]] = {}
        self.compensation_factor = 1.0
        self.adaptive_weights = {
            'recent': 0.6,
            'medium': 0.3,
            'old': 0.1
        }
        
    def estimate_latency(self, distance_ly: float) -> float:
        """估计延迟（秒）"""
        # 1光年 = 365.25 * 24 * 3600 光秒
        light_seconds_per_year = 365.25 * 24 * 3600
        return distance_ly * light_seconds_per_year
    
    def get_latency_class(self, distance_ly: float) -> LatencyClass:
        """获取延迟等级"""
        if distance_ly < 0.0000000278:  # < 1秒
            return LatencyClass.LOCAL
        elif distance_ly < 0.000000278:  # < 10光秒
            return LatencyClass.NEAR_STAR
        elif distance_ly < 1:  # < 1光年
            return LatencyClass.SOLAR_SYSTEM
        elif distance_ly < 10:  # < 10光年
            return LatencyClass.NEARBY_STAR
        elif distance_ly < 100:  # < 100光年
            return LatencyClass.GALACTIC
        else:
            return LatencyClass.INTER_GALACTIC
    
    def update_latency_observation(self, source: str, dest: str, 
                                   observed_latency: float) -> None:
        """更新延迟观测"""
        key = (source, dest)
        if key not in self.observed_delays:
            self.observed_delays[key] = []
        
        self.observed_delays[key].append(observed_latency)
        
        # 保持最近1000条记录
        if len(self.observed_delays[key]) > 1000:
            self.observed_delays[key] = self.observed_delays[key][-1000:]
    
    def predict_latency(self, source: str, dest: str, 
                        distance_ly: float) -> float:
        """预测延迟（带自适应补偿）"""
        key = (source, dest)
        
        # 基础延迟
        base_latency = self.estimate_latency(distance_ly)
        
        if key in self.observed_delays and self.observed_delays[key]:
            observations = self.observed_delays[key]
            n = len(observations)
            
            # 加权平均
            if n >= 10:
                recent = observations[-int(n*0.2):]
                medium = observations[-int(n*0.5):-int(n*0.2)] if n > 5 else []
                old = observations[:-int(n*0.5)] if n > 10 else []
                
                weighted = (
                    sum(recent) * self.adaptive_weights['recent'] +
                    sum(medium) * self.adaptive_weights['medium'] +
                    sum(old) * self.adaptive_weights['old']
                ) / (len(recent) + len(medium) + len(old) or 1)
                
                # 平滑调整因子
                adjustment = weighted / base_latency if base_latency > 0 else 1.0
                self.compensation_factor = self.compensation_factor * 0.9 + adjustment * 0.1
                
                return weighted
            
        return base_latency * self.compensation_factor


class BatchTransferOptimizer:
    """批量传输优化器"""
    
    def __init__(self, max_batch_size: int = 100, 
                 max_delay_ms: float = 100):
        self.max_batch_size = max_batch_size
        self.max_delay_ms = max_delay_ms
        self.pending_messages: List[Dict] = []
        self.batch_history: List[Dict] = []
        self.lock = Lock()
        
    def add_message(self, message: Dict) -> None:
        """添加消息到待批处理队列"""
        with self.lock:
            message['queue_time'] = time.time()
            heapq.heappush(self.pending_messages, 
                          (message['queue_time'], message))
    
    def get_ready_batch(self) -> List[Dict]:
        """获取准备好的批次"""
        with self.lock:
            current_time = time.time()
            ready = []
            remaining = []
            
            while self.pending_messages:
                _, msg = heapq.heappop(self.pending_messages)
                wait_time = (current_time - msg['queue_time']) * 1000
                
                if wait_time >= self.max_delay_ms or len(ready) >= self.max_batch_size:
                    ready.append(msg)
                else:
                    remaining.append((msg['queue_time'], msg))
            
            self.pending_messages = remaining
            
            if ready:
                self.batch_history.append({
                    'time': current_time,
                    'size': len(ready),
                    'total_size': sum(m.get('size', 0) for m in ready)
                })
            
            return ready
    
    def get_optimal_batch_size(self, message_sizes: List[int], 
                               bandwidth_mbps: float) -> int:
        """计算最优批次大小"""
        if not message_sizes or bandwidth_mbps <= 0:
            return self.max_batch_size
        
        # 基于MTU和带宽延迟积计算
        mtu = 1500  # bytes
        bdp = int(bandwidth_mbps * 1e6 / 8 * self.max_delay_ms / 1000)
        
        # 选择最小的成本函数
        best_size = 1
        best_cost = float('inf')
        
        for size in range(1, min(len(message_sizes), self.max_batch_size) + 1):
            total_size = sum(message_sizes[:size])
            transfer_time = total_size * 8 / (bandwidth_mbps * 1e6)
            overhead = size * mtu
            cost = transfer_time + overhead / (bandwidth_mbps * 1e6)
            
            if cost < best_cost:
                best_cost = cost
                best_size = size
        
        return best_size


class PredictivePrefetcher:
    """预测性预取器"""
    
    def __init__(self, history_window: int = 1000):
        self.history_window = history_window
        self.access_patterns: Dict[str, List[float]] = {}
        self.prefetch_queue: List[Tuple[str, float]] = []  # (data_id, priority)
        self.hit_rate = 0.0
        self.prefetch_count = 0
        self.cache_hits = 0
        
    def analyze_access_pattern(self, data_id: str, access_time: float) -> None:
        """分析访问模式"""
        if data_id not in self.access_patterns:
            self.access_patterns[data_id] = []
        
        self.access_patterns[data_id].append(access_time)
        
        if len(self.access_patterns[data_id]) > self.history_window:
            self.access_patterns[data_id] = self.access_patterns[data_id][-self.history_window:]
    
    def predict_next_access(self, data_id: str) -> Optional[float]:
        """预测下次访问时间"""
        if data_id not in self.access_patterns:
            return None
        
        times = self.access_patterns[data_id]
        if len(times) < 2:
            return None
        
        # 计算时间间隔
        intervals = [times[i+1] - times[i] for i in range(len(times)-1)]
        
        # 使用指数移动平均
        alpha = 0.3
        ema = intervals[0]
        for interval in intervals[1:]:
            ema = alpha * interval + (1 - alpha) * ema
        
        return times[-1] + ema
    
    def should_prefetch(self, data_id: str, current_time: float,
                       threshold: float = 0.7) -> bool:
        """判断是否应该预取"""
        next_access = self.predict_next_access(data_id)
        
        if next_access is None:
            return False
        
        time_until_access = next_access - current_time
        prefetch_window = 10  # 10秒预取窗口
        
        return 0 < time_until_access < prefetch_window
    
    def prefetch(self, data_id: str, data: Any, priority: float = 1.0) -> None:
        """执行预取"""
        self.prefetch_queue.append((data_id, priority))
        self.prefetch_count += 1
        heapq.heapify(self.prefetch_queue)
    
    def get_prefetch_priority(self, data_id: str) -> float:
        """获取预取优先级"""
        next_access = self.predict_next_access(data_id)
        if next_access is None:
            return 0.5
        
        # 越接近访问时间，优先级越高
        time_diff = next_access - time.time()
        return max(0, min(1, 1 - time_diff / 10))
    
    def record_cache_hit(self) -> None:
        """记录缓存命中"""
        self.cache_hits += 1
        if self.prefetch_count > 0:
            self.hit_rate = self.cache_hits / self.prefetch_count
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'tracked_data': len(self.access_patterns),
            'prefetch_queue_size': len(self.prefetch_queue),
            'prefetch_count': self.prefetch_count,
            'cache_hits': self.cache_hits,
            'hit_rate': self.hit_rate
        }


class AsyncMessageQueue:
    """异步消息队列（支持光年延迟）"""
    
    def __init__(self, max_size: int = 10000):
        self.max_size = max_size
        self.queue: deque = deque(maxlen=max_size)
        self.pending_acks: Dict[str, float] = {}
        self.sent_history: List[TransmissionRecord] = []
        self.lock = Lock()
        self.callbacks: Dict[str, Callable] = {}
        
    def enqueue(self, message: Dict, scheduled_time: Optional[float] = None) -> str:
        """入队消息"""
        msg_id = message.get('id', f"msg_{time.time()}")
        
        with self.lock:
            self.queue.append({
                'message': message,
                'scheduled_time': scheduled_time or time.time(),
                'enqueue_time': time.time()
            })
        
        return msg_id
    
    def dequeue(self) -> Optional[Dict]:
        """出队消息"""
        with self.lock:
            current_time = time.time()
            
            while self.queue:
                item = self.queue.popleft()
                if item['scheduled_time'] <= current_time:
                    return item['message']
                else:
                    # 重新放回（保持顺序）
                    self.queue.appendleft(item)
                    break
        
        return None
    
    def wait_for_ack(self, message_id: str, timeout: float) -> bool:
        """等待确认"""
        start = time.time()
        
        while time.time() - start < timeout:
            if message_id not in self.pending_acks:
                time.sleep(0.1)
                continue
            
            if time.time() > self.pending_acks[message_id]:
                del self.pending_acks[message_id]
                return False
            
            del self.pending_acks[message_id]
            return True
        
        return False
    
    def register_callback(self, event: str, callback: Callable) -> None:
        """注册回调"""
        self.callbacks[event] = callback
    
    def trigger_callback(self, event: str, *args, **kwargs) -> None:
        """触发回调"""
        if event in self.callbacks:
            try:
                self.callbacks[event](*args, **kwargs)
            except Exception as e:
                print(f"Callback error: {e}")


class LightLatencyHandler:
    """光年延迟处理器主类"""
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.compensator = AdaptiveLatencyCompensator()
        self.batch_optimizer = BatchTransferOptimizer()
        self.prefetcher = PredictivePrefetcher()
        self.message_queue = AsyncMessageQueue()
        self.transmission_history: List[TransmissionRecord] = []
        
    def calculate_one_way_delay(self, distance_ly: float) -> float:
        """计算单向延迟"""
        return self.compensator.estimate_latency(distance_ly)
    
    def calculate_round_trip_time(self, distance_ly: float) -> float:
        """计算往返时间"""
        return 2 * self.calculate_one_way_delay(distance_ly)
    
    def prepare_message(self, message: Dict, distance_ly: float,
                       priority: float = 1.0) -> Dict:
        """准备消息（添加延迟信息）"""
        estimated_delay = self.compensator.estimate_latency(distance_ly)
        
        prepared = {
            **message,
            'estimated_delay': estimated_delay,
            'estimated_arrival': time.time() + estimated_delay,
            'distance_ly': distance_ly,
            'priority': priority,
            'sender': self.node_id,
            'send_time': time.time()
        }
        
        # 创建传输记录
        record = TransmissionRecord(
            message_id=message.get('id', ''),
            send_time=time.time(),
            estimated_arrival=time.time() + estimated_delay,
            payload_size=len(str(message))
        )
        self.transmission_history.append(record)
        
        return prepared
    
    def optimize_batch(self, messages: List[Dict], 
                      bandwidth_mbps: float = 100) -> List[Dict]:
        """优化批量传输"""
        message_sizes = [len(str(m)) for m in messages]
        optimal_size = self.batch_optimizer.get_optimal_batch_size(
            message_sizes, bandwidth_mbps
        )
        
        return messages[:optimal_size]
    
    def add_to_queue(self, message: Dict, delay: float = 0) -> str:
        """添加到延迟队列"""
        scheduled_time = time.time() + delay
        return self.message_queue.enqueue(message, scheduled_time)
    
    def process_completion(self, message_id: str, actual_arrival: float) -> None:
        """处理消息传输完成"""
        for record in reversed(self.transmission_history):
            if record.message_id == message_id:
                record.actual_arrival = actual_arrival
                record.status = 'completed'
                
                # 更新补偿器
                if record.actual_latency:
                    self.compensator.update_latency_observation(
                        self.node_id, 'unknown', record.actual_latency
                    )
                break
    
    def get_latency_report(self) -> Dict[str, Any]:
        """获取延迟报告"""
        completed = [r for r in self.transmission_history 
                    if r.status == 'completed' and r.actual_latency]
        
        if not completed:
            return {'status': 'No data'}
        
        latencies = [r.actual_latency for r in completed]
        
        return {
            'total_transmissions': len(self.transmission_history),
            'completed': len(completed),
            'avg_latency': sum(latencies) / len(latencies),
            'min_latency': min(latencies),
            'max_latency': max(latencies),
            'pending': len([r for r in self.transmission_history 
                          if r.status == 'pending']),
            'batch_stats': self.batch_optimizer.batch_history[-10:],
            'prefetch_stats': self.prefetcher.get_statistics()
        }


def demo():
    """演示光年延迟处理"""
    print("=" * 60)
    print("光年延迟处理器演示")
    print("=" * 60)
    
    handler = LightLatencyHandler("earth")
    
    # 测试不同距离的延迟
    distances = [
        ("月球", 0.000001),
        ("火星", 0.00037),
        ("比邻星", 4.24),
        ("TRAPPIST-1", 39.5),
        ("银河系中心", 26000)
    ]
    
    print("\n光年级延迟计算:")
    for name, ly in distances:
        one_way = handler.calculate_one_way_delay(ly)
        rtt = handler.calculate_round_trip_time(ly)
        lat_class = handler.compensator.get_latency_class(ly)
        
        one_way_days = one_way / 86400
        rtt_days = rtt / 86400
        
        print(f"  {name:12s}: 单程 {one_way_days:10.2f}天, "
              f"RTT {rtt_days:10.2f}天 [{lat_class.name}]")
    
    # 测试批量优化
    print("\n批量传输优化:")
    messages = [{'id': f'msg_{i}', 'data': 'x' * 1000} for i in range(50)]
    optimized = handler.optimize_batch(messages, bandwidth_mbps=100)
    print(f"  输入: {len(messages)} 条消息")
    print(f"  优化后: {len(optimized)} 条消息")
    
    # 测试预测预取
    print("\n预测性预取:")
    prefetcher = handler.prefetcher
    
    # 模拟访问模式
    base_time = time.time()
    for i in range(20):
        prefetcher.analyze_access_pattern("data_001", base_time + i * 5)
    
    next_access = prefetcher.predict_next_access("data_001")
    should_prefetch = prefetcher.should_prefetch("data_001", time.time())
    
    if next_access:
        print(f"  预测下次访问: {next_access - time.time():.2f}秒后")
    print(f"  应该预取: {should_prefetch}")
    
    # 测试消息队列
    print("\n异步消息队列:")
    for i in range(3):
        handler.add_to_queue({'id': f'queue_msg_{i}', 'data': f'test{i}'}, delay=i)
    
    print(f"  入队3条消息")
    
    # 延迟报告
    print("\n延迟报告:")
    report = handler.get_latency_report()
    for k, v in report.items():
        print(f"  {k}: {v}")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()