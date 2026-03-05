#!/usr/bin/env python3
"""
多智能体协作网络 - SDK性能监控集成
SDK Performance Monitor Integration
"""

import os
import sys
import time
import threading
import json
from datetime import datetime
from collections import defaultdict

# 添加SDK路径
SDK_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SDK_DIR)

try:
    from sdk.client import AgentClient
    SDK_AVAILABLE = True
except ImportError:
    SDK_AVAILABLE = False


class PerformanceMonitor:
    """性能监控器 - 集成到SDK"""
    
    def __init__(self, api_url="http://localhost:8899"):
        self.api_url = api_url
        self.metrics = defaultdict(lambda: {
            'requests': 0,
            'success': 0,
            'failed': 0,
            'total_time': 0,
            'errors': []
        })
        self._lock = threading.Lock()
        self._enabled = True
    
    def record_request(self, endpoint, success=True, response_time=0, error=None):
        """记录请求"""
        if not self._enabled:
            return
            
        with self._lock:
            m = self.metrics[endpoint]
            m['requests'] += 1
            if success:
                m['success'] += 1
                m['total_time'] += response_time
            else:
                m['failed'] += 1
                if error:
                    m['errors'].append({
                        'time': datetime.now().isoformat(),
                        'error': str(error)
                    })
                    if len(m['errors']) > 10:
                        m['errors'] = m['errors'][-10:]
    
    def get_stats(self):
        """获取统计信息"""
        with self._lock:
            stats = {}
            total_requests = 0
            total_success = 0
            
            for endpoint, m in self.metrics.items():
                total_requests += m['requests']
                total_success += m['success']
                stats[endpoint] = {
                    'requests': m['requests'],
                    'success': m['success'],
                    'failed': m['failed'],
                    'avg_time': m['total_time'] / m['success'] if m['success'] > 0 else 0
                }
            
            return {
                'endpoints': stats,
                'total_requests': total_requests,
                'total_success': total_success,
                'success_rate': (total_success / total_requests * 100) if total_requests > 0 else 0
            }
    
    def reset(self):
        """重置统计"""
        with self._lock:
            self.metrics.clear()


class MonitoredClient:
    """带性能监控的Agent客户端包装器"""
    
    def __init__(self, client: AgentClient = None, monitor: PerformanceMonitor = None):
        self._client = client
        self._monitor = monitor or PerformanceMonitor()
    
    def _wrap_request(self, method, *args, **kwargs):
        """包装请求以监控性能"""
        start = time.time()
        endpoint = method.__name__
        
        try:
            result = method(*args, **kwargs)
            elapsed = (time.time() - start) * 1000  # ms
            self._monitor.record_request(endpoint, True, elapsed)
            return result
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            self._monitor.record_request(endpoint, False, elapsed, e)
            raise
    
    def list_agents(self, agent_type=None):
        """列出Agent (监控)"""
        return self._wrap_request(self._client.list_agents, agent_type)
    
    def register_agent(self, agent_id, agent_type, capabilities):
        """注册Agent (监控)"""
        return self._wrap_request(self._client.register_agent, agent_id, agent_type, capabilities)
    
    def submit_task(self, task_type, payload):
        """提交任务 (监控)"""
        return self._wrap_request(self._client.submit_task, task_type, payload)
    
    def get_task_status(self, task_id):
        """获取任务状态 (监控)"""
        return self._wrap_request(self._client.get_task_status, task_id)
    
    @property
    def monitor(self):
        return self._monitor


def create_monitored_client(base_url="http://localhost:8080", api_key=None):
    """创建带监控的客户端"""
    if not SDK_AVAILABLE:
        print("⚠️ SDK不可用，使用模拟客户端")
        return None
    
    client = AgentClient(base_url=base_url, api_key=api_key)
    return MonitoredClient(client)


# 测试
if __name__ == '__main__':
    print("🔧 性能监控模块测试")
    print("-"*40)
    
    monitor = PerformanceMonitor()
    
    # 模拟请求
    for i in range(10):
        monitor.record_request('/api/agents', True, 15.2)
    
    for i in range(5):
        monitor.record_request('/api/tasks', True, 32.5)
    
    for i in range(2):
        monitor.record_request('/api/health', False, 0, "Connection timeout")
    
    stats = monitor.get_stats()
    print(json.dumps(stats, indent=2))
    
    print("\n✅ 性能监控模块测试完成")