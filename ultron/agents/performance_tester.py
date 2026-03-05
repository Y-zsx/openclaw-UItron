"""
Agent协作网络性能测试与压力测试模块
第30世: 实现自动修复模块
"""

import time
import json
import random
import threading
import statistics
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import sqlite3


@dataclass
class PerformanceMetrics:
    """性能指标"""
    operation: str
    count: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    p50: float
    p95: float
    p99: float
    throughput: float  # ops/sec
    error_count: int = 0
    error_rate: float = 0.0


@dataclass
class StressTestResult:
    """压力测试结果"""
    test_name: str
    duration: float
    total_requests: int
    success_count: int
    error_count: int
    throughput: float
    avg_latency: float
    max_latency: float
    error_rate: float
    metrics: Dict[str, Any] = field(default_factory=dict)


class PerformanceProfiler:
    """性能分析器"""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or "/root/.openclaw/workspace/ultron/agents/performance.db"
        self._init_db()
        self.metrics = defaultdict(list)
        self.lock = threading.Lock()
    
    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS performance_metrics
                     (id INTEGER PRIMARY KEY, operation TEXT, count INTEGER,
                      total_time REAL, avg_time REAL, min_time REAL, max_time REAL,
                      p50 REAL, p95 REAL, p99 REAL, throughput REAL,
                      error_count INTEGER, error_rate REAL, timestamp TEXT)''')
        c.execute('''CREATE TABLE IF NOT EXISTS stress_test_results
                     (id INTEGER PRIMARY KEY, test_name TEXT, duration REAL,
                      total_requests INTEGER, success_count INTEGER, error_count INTEGER,
                      throughput REAL, avg_latency REAL, max_latency REAL,
                      error_rate REAL, metrics_json TEXT, timestamp TEXT)''')
        conn.commit()
        conn.close()
    
    def record(self, operation: str, duration: float, success: bool = True):
        with self.lock:
            self.metrics[operation].append({
                'duration': duration,
                'success': success,
                'timestamp': time.time()
            })
    
    def calculate_metrics(self, operation: str) -> PerformanceMetrics:
        """计算性能指标"""
        data = self.metrics.get(operation, [])
        if not data:
            return None
        
        durations = [m['duration'] for m in data]
        errors = sum(1 for m in data if not m['success'])
        total_time = sum(durations)
        count = len(durations)
        
        sorted_durations = sorted(durations)
        n = len(sorted_durations)
        
        return PerformanceMetrics(
            operation=operation,
            count=count,
            total_time=total_time,
            avg_time=statistics.mean(durations),
            min_time=min(durations),
            max_time=max(durations),
            p50=sorted_durations[int(n * 0.5)],
            p95=sorted_durations[int(n * 0.95)],
            p99=sorted_durations[int(n * 0.99)],
            throughput=count / total_time if total_time > 0 else 0,
            error_count=errors,
            error_rate=errors / count if count > 0 else 0
        )
    
    def save_metrics(self, metrics: PerformanceMetrics):
        """保存性能指标到数据库"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''INSERT INTO performance_metrics
                     (operation, count, total_time, avg_time, min_time, max_time,
                      p50, p95, p99, throughput, error_count, error_rate, timestamp)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (metrics.operation, metrics.count, metrics.total_time,
                   metrics.avg_time, metrics.min_time, metrics.max_time,
                   metrics.p50, metrics.p95, metrics.p99, metrics.throughput,
                   metrics.error_count, metrics.error_rate, datetime.now().isoformat()))
        conn.commit()
        conn.close()
    
    def get_operation_stats(self, operation: str, limit: int = 100) -> List[Dict]:
        """获取操作统计数据"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''SELECT * FROM performance_metrics
                     WHERE operation = ? ORDER BY timestamp DESC LIMIT ?''',
                  (operation, limit))
        cols = [desc[0] for desc in c.description]
        results = [dict(zip(cols, row)) for row in c.fetchall()]
        conn.close()
        return results


class StressTestRunner:
    """压力测试运行器"""
    
    def __init__(self, profiler: PerformanceProfiler = None):
        self.profiler = profiler or PerformanceProfiler()
        self.running = False
        self.results = []
    
    async def run_load_test(
        self,
        name: str,
        request_func: Callable,
        concurrency: int = 10,
        duration: float = 60,
        error_rate_threshold: float = 0.05
    ) -> StressTestResult:
        """运行负载测试"""
        self.running = True
        start_time = time.time()
        success_count = 0
        error_count = 0
        latencies = []
        errors = []
        
        async def worker():
            nonlocal success_count, error_count
            while self.running and (time.time() - start_time) < duration:
                try:
                    req_start = time.time()
                    await request_func()
                    latency = time.time() - req_start
                    latencies.append(latency)
                    success_count += 1
                    self.profiler.record(name, latency, True)
                except Exception as e:
                    error_count += 1
                    errors.append(str(e))
                    self.profiler.record(name, 0, False)
        
        # 启动并发工作器
        tasks = [asyncio.create_task(worker()) for _ in range(concurrency)]
        
        # 等待完成
        await asyncio.sleep(duration)
        self.running = False
        
        # 取消剩余任务
        for task in tasks:
            task.cancel()
        
        total_time = time.time() - start_time
        total_requests = success_count + error_count
        
        return StressTestResult(
            test_name=name,
            duration=total_time,
            total_requests=total_requests,
            success_count=success_count,
            error_count=error_count,
            throughput=total_requests / total_time if total_time > 0 else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            error_rate=error_count / total_requests if total_requests > 0 else 0,
            metrics={'errors': errors[-10:]}  # 保留最近10个错误
        )
    
    def run_concurrent_test(
        self,
        name: str,
        func: Callable,
        threads: int = 10,
        iterations: int = 100
    ) -> StressTestResult:
        """运行并发测试（同步版本）"""
        self.running = True
        start_time = time.time()
        success_count = 0
        error_count = 0
        latencies = []
        errors = []
        lock = threading.Lock()
        
        def worker():
            nonlocal success_count, error_count
            for _ in range(iterations):
                if not self.running:
                    break
                try:
                    req_start = time.time()
                    func()
                    latency = time.time() - req_start
                    with lock:
                        latencies.append(latency)
                        success_count += 1
                    self.profiler.record(name, latency, True)
                except Exception as e:
                    with lock:
                        error_count += 1
                        errors.append(str(e))
                    self.profiler.record(name, 0, False)
        
        # 启动线程
        thread_list = []
        for _ in range(threads):
            t = threading.Thread(target=worker)
            t.start()
            thread_list.append(t)
        
        # 等待完成
        for t in thread_list:
            t.join()
        
        self.running = False
        total_time = time.time() - start_time
        total_requests = success_count + error_count
        
        return StressTestResult(
            test_name=name,
            duration=total_time,
            total_requests=total_requests,
            success_count=success_count,
            error_count=error_count,
            throughput=total_requests / total_time if total_time > 0 else 0,
            avg_latency=statistics.mean(latencies) if latencies else 0,
            max_latency=max(latencies) if latencies else 0,
            error_rate=error_count / total_requests if total_requests > 0 else 0,
            metrics={'errors': errors[-10:]}
        )


class BenchmarkSuite:
    """基准测试套件"""
    
    def __init__(self, profiler: PerformanceProfiler = None):
        self.profiler = profiler or PerformanceProfiler()
        self.results = {}
    
    def benchmark_function(self, name: str, func: Callable, iterations: int = 1000) -> Dict:
        """基准测试函数"""
        latencies = []
        for _ in range(iterations):
            start = time.time()
            try:
                func()
                latencies.append(time.time() - start)
            except Exception:
                latencies.append(0)
        
        return {
            'name': name,
            'iterations': iterations,
            'avg_time': statistics.mean(latencies),
            'min_time': min(latencies),
            'max_time': max(latencies),
            'throughput': iterations / sum(latencies) if sum(latencies) > 0 else 0
        }
    
    def benchmark_async(self, name: str, coro_func: Callable, iterations: int = 100) -> Dict:
        """基准测试异步函数"""
        latencies = []
        
        async def run():
            for _ in range(iterations):
                start = time.time()
                try:
                    await coro_func()
                    latencies.append(time.time() - start)
                except Exception:
                    latencies.append(0)
        
        asyncio.run(run())
        
        return {
            'name': name,
            'iterations': iterations,
            'avg_time': statistics.mean(latencies),
            'min_time': min(latencies),
            'max_time': max(latencies),
            'p95': sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0
        }


class PerformanceOptimizer:
    """性能优化器"""
    
    def __init__(self, profiler: PerformanceProfiler = None):
        self.profiler = profiler or PerformanceProfiler()
    
    def analyze_bottlenecks(self, operation: str) -> Dict[str, Any]:
        """分析瓶颈"""
        metrics = self.profiler.calculate_metrics(operation)
        if not metrics:
            return {'status': 'no_data'}
        
        recommendations = []
        
        # 分析延迟
        if metrics.p95 > 1.0:
            recommendations.append({
                'type': 'high_latency',
                'severity': 'warning',
                'message': f"P95延迟 {metrics.p95:.3f}s 超过1秒，建议优化",
                'suggestion': '考虑使用缓存、异步处理或批量操作'
            })
        
        # 分析吞吐量
        if metrics.throughput < 10:
            recommendations.append({
                'type': 'low_throughput',
                'severity': 'warning',
                'message': f"吞吐量 {metrics.throughput:.2f} ops/sec 较低",
                'suggestion': '考虑增加并发数或优化处理逻辑'
            })
        
        # 分析错误率
        if metrics.error_rate > 0.01:
            recommendations.append({
                'type': 'high_error_rate',
                'severity': 'critical',
                'message': f"错误率 {metrics.error_rate:.2%} 超过1%",
                'suggestion': '检查错误日志，定位失败原因'
            })
        
        return {
            'operation': operation,
            'metrics': {
                'count': metrics.count,
                'avg_time': metrics.avg_time,
                'p50': metrics.p50,
                'p95': metrics.p95,
                'p99': metrics.p99,
                'throughput': metrics.throughput,
                'error_rate': metrics.error_rate
            },
            'recommendations': recommendations
        }
    
    def get_optimization_report(self) -> Dict:
        """获取优化报告"""
        operations = list(self.profiler.metrics.keys())
        bottlenecks = []
        
        for op in operations:
            result = self.analyze_bottlenecks(op)
            if result.get('recommendations'):
                bottlenecks.append(result)
        
        return {
            'timestamp': datetime.now().isoformat(),
            'total_operations': len(operations),
            'bottlenecks': bottlenecks,
            'summary': f"发现 {len(bottlenecks)} 个需要优化的操作"
        }


# CLI工具
def run_performance_test():
    """运行性能测试"""
    import sys
    
    profiler = PerformanceProfiler()
    optimizer = PerformanceOptimizer(profiler)
    
    # 模拟一些测试数据
    for i in range(100):
        profiler.record('task_execution', random.uniform(0.01, 0.1), random.random() > 0.05)
        profiler.record('message_delivery', random.uniform(0.001, 0.02), random.random() > 0.02)
        profiler.record('agent_registration', random.uniform(0.05, 0.3), random.random() > 0.01)
    
    # 生成报告
    report = optimizer.get_optimization_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    return report


if __name__ == '__main__':
    run_performance_test()