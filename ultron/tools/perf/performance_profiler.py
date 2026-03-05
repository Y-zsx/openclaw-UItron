#!/usr/bin/env python3
"""
Agent性能分析器 - 性能监控与分析
"""
import psutil
import time
import json
import os
from datetime import datetime
from collections import deque
from threading import Thread, Lock

class PerformanceProfiler:
    """Agent性能分析器 - 实时监控系统性能"""
    
    def __init__(self, sample_interval=1.0, history_size=3600):
        self.sample_interval = sample_interval
        self.history_size = history_size
        self.running = False
        self.thread = None
        self.lock = Lock()
        
        # 指标历史
        self.cpu_history = deque(maxlen=history_size)
        self.memory_history = deque(maxlen=history_size)
        self.disk_io_history = deque(maxlen=history_size)
        self.network_history = deque(maxlen=history_size)
        
        # 进程级指标
        self.process_stats = {}
        
        # Agent指标
        self.agent_metrics = {}
        
        # 系统启动时间
        self.boot_time = psutil.boot_time()
        
    def start(self):
        """启动性能监控"""
        if self.running:
            return
        self.running = True
        self.thread = Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        """停止性能监控"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
            
    def _monitor_loop(self):
        """监控循环"""
        last_disk_io = psutil.disk_io_counters()
        last_net_io = psutil.net_io_counters()
        
        while self.running:
            try:
                timestamp = datetime.now().isoformat()
                
                # CPU指标
                cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
                cpu_avg = sum(cpu_percent) / len(cpu_percent)
                
                # 内存指标
                memory = psutil.virtual_memory()
                swap = psutil.swap_memory()
                
                # 磁盘IO
                disk_io = psutil.disk_io_counters()
                disk_read_mb = (disk_io.read_bytes - last_disk_io.read_bytes) / 1024 / 1024
                disk_write_mb = (disk_io.write_bytes - last_disk_io.write_bytes) / 1024 / 1024
                last_disk_io = disk_io
                
                # 网络IO
                net_io = psutil.net_io_counters()
                net_recv_mb = (net_io.bytes_recv - last_net_io.bytes_recv) / 1024 / 1024
                net_sent_mb = (net_io.bytes_sent - last_net_io.bytes_sent) / 1024 / 1024
                last_net_io = net_io
                
                # 负载
                load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
                
                # 记录数据
                with self.lock:
                    self.cpu_history.append({
                        'timestamp': timestamp,
                        'avg': cpu_avg,
                        'per_cpu': cpu_percent
                    })
                    self.memory_history.append({
                        'timestamp': timestamp,
                        'used_mb': memory.used / 1024 / 1024,
                        'available_mb': memory.available / 1024 / 1024,
                        'percent': memory.percent,
                        'swap_used_mb': swap.used / 1024 / 1024
                    })
                    self.disk_io_history.append({
                        'timestamp': timestamp,
                        'read_mb_s': disk_read_mb,
                        'write_mb_s': disk_write_mb
                    })
                    self.network_history.append({
                        'timestamp': timestamp,
                        'recv_mb_s': net_recv_mb,
                        'sent_mb_s': net_sent_mb
                    })
                    
                time.sleep(self.sample_interval)
                
            except Exception as e:
                print(f"Monitor error: {e}")
                time.sleep(self.sample_interval)
                
    def get_current_stats(self):
        """获取当前系统统计"""
        cpu_percent = psutil.cpu_percent(interval=0.1, percpu=True)
        memory = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        load_avg = os.getloadavg() if hasattr(os, 'getloadavg') else (0, 0, 0)
        
        return {
            'cpu': {
                'avg_percent': sum(cpu_percent) / len(cpu_percent),
                'per_cpu': cpu_percent,
                'count': psutil.cpu_count(),
                'load_avg': load_avg
            },
            'memory': {
                'total_mb': memory.total / 1024 / 1024,
                'used_mb': memory.used / 1024 / 1024,
                'available_mb': memory.available / 1024 / 1024,
                'percent': memory.percent,
            },
            'disk': {
                'total_gb': disk.total / 1024 / 1024 / 1024,
                'used_gb': disk.used / 1024 / 1024 / 1024,
                'free_gb': disk.free / 1024 / 1024 / 1024,
                'percent': disk.percent
            },
            'uptime_seconds': time.time() - self.boot_time
        }
        
    def get_cpu_history(self, limit=60):
        """获取CPU历史"""
        with self.lock:
            return list(self.cpu_history)[-limit:]
            
    def get_memory_history(self, limit=60):
        """获取内存历史"""
        with self.lock:
            return list(self.memory_history)[-limit:]
            
    def get_disk_io_history(self, limit=60):
        """获取磁盘IO历史"""
        with self.lock:
            return list(self.disk_io_history)[-limit:]
            
    def get_network_history(self, limit=60):
        """获取网络IO历史"""
        with self.lock:
            return list(self.network_history)[-limit:]
            
    def register_agent(self, agent_id, metadata=None):
        """注册Agent"""
        with self.lock:
            self.agent_metrics[agent_id] = {
                'registered_at': datetime.now().isoformat(),
                'metadata': metadata or {},
                'metrics': {
                    'request_count': 0,
                    'error_count': 0,
                    'total_latency_ms': 0,
                    'max_latency_ms': 0,
                    'min_latency_ms': float('inf')
                },
                'alerts': []
            }
            
    def record_agent_request(self, agent_id, latency_ms, error=False):
        """记录Agent请求"""
        with self.lock:
            if agent_id in self.agent_metrics:
                m = self.agent_metrics[agent_id]['metrics']
                m['request_count'] += 1
                m['total_latency_ms'] += latency_ms
                m['max_latency_ms'] = max(m['max_latency_ms'], latency_ms)
                m['min_latency_ms'] = min(m['min_latency_ms'], latency_ms)
                if error:
                    m['error_count'] += 1
                    
    def get_agent_metrics(self, agent_id=None):
        """获取Agent指标"""
        with self.lock:
            if agent_id:
                return self.agent_metrics.get(agent_id)
            return dict(self.agent_metrics)
            
    def add_agent_alert(self, agent_id, alert_type, message):
        """添加Agent告警"""
        with self.lock:
            if agent_id in self.agent_metrics:
                self.agent_metrics[agent_id]['alerts'].append({
                    'type': alert_type,
                    'message': message,
                    'timestamp': datetime.now().isoformat()
                })
                
    def analyze_performance(self):
        """分析性能状况"""
        with self.lock:
            cpu_data = list(self.cpu_history)
            mem_data = list(self.memory_history)
            
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'cpu': {},
            'memory': {},
            'overall_score': 100,
            'recommendations': []
        }
        
        if cpu_data:
            cpu_values = [d['avg'] for d in cpu_data[-60:]]
            avg_cpu = sum(cpu_values) / len(cpu_values)
            max_cpu = max(cpu_values)
            
            analysis['cpu'] = {
                'avg_percent': avg_cpu,
                'max_percent': max_cpu,
                'status': 'critical' if avg_cpu > 90 else 'warning' if avg_cpu > 70 else 'normal'
            }
            
            if avg_cpu > 90:
                analysis['overall_score'] -= 30
                analysis['recommendations'].append('CPU使用率极高，考虑扩容或优化负载')
            elif avg_cpu > 70:
                analysis['overall_score'] -= 15
                analysis['recommendations'].append('CPU使用率较高，建议关注')
                
        if mem_data:
            mem_values = [d['percent'] for d in mem_data[-60:]]
            avg_mem = sum(mem_values) / len(mem_values)
            max_mem = max(mem_values)
            
            analysis['memory'] = {
                'avg_percent': avg_mem,
                'max_percent': max_mem,
                'status': 'critical' if avg_mem > 90 else 'warning' if avg_mem > 75 else 'normal'
            }
            
            if avg_mem > 90:
                analysis['overall_score'] -= 30
                analysis['recommendations'].append('内存使用率极高，警惕OOM')
            elif avg_mem > 75:
                analysis['overall_score'] -= 15
                analysis['recommendations'].append('内存使用率较高，建议监控')
                
        # Agent性能分析
        agent_issues = []
        for agent_id, data in self.agent_metrics.items():
            m = data['metrics']
            if m['request_count'] > 0:
                avg_latency = m['total_latency_ms'] / m['request_count']
                error_rate = m['error_count'] / m['request_count'] * 100
                
                if error_rate > 10:
                    agent_issues.append(f"{agent_id}: 错误率 {error_rate:.1f}%")
                    analysis['recommendations'].append(f"Agent {agent_id} 错误率较高({error_rate:.1f}%)")
                    
                if avg_latency > 5000:
                    agent_issues.append(f"{agent_id}: 平均延迟 {avg_latency:.0f}ms")
                    analysis['recommendations'].append(f"Agent {agent_id} 响应延迟较高")
                    
        analysis['agent_issues'] = agent_issues
        analysis['overall_score'] = max(0, int(analysis['overall_score']))
        
        return analysis
        
    def get_full_snapshot(self):
        """获取完整快照"""
        return {
            'current': self.get_current_stats(),
            'cpu_history': self.get_cpu_history(60),
            'memory_history': self.get_memory_history(60),
            'disk_io_history': self.get_disk_io_history(60),
            'network_history': self.get_network_history(60),
            'analysis': self.analyze_performance(),
            'agents': self.get_agent_metrics()
        }


# 全局实例
_profiler = None

def get_profiler():
    """获取全局性能分析器实例"""
    global _profiler
    if _profiler is None:
        _profiler = PerformanceProfiler()
        _profiler.start()
    return _profiler

def stop_profiler():
    """停止性能分析器"""
    global _profiler
    if _profiler:
        _profiler.stop()
        _profiler = None


if __name__ == '__main__':
    profiler = get_profiler()
    print("Performance Profiler started...")
    print(json.dumps(profiler.get_current_stats(), indent=2))