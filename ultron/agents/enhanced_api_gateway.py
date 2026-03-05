#!/usr/bin/env python3
"""
多智能体协作网络 - 增强API网关
Enhanced API Gateway with Rate Limiting, Caching, and More
"""

import time
import hashlib
import json
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, Optional, Callable
from functools import wraps
import uuid

class RateLimiter:
    """速率限制器"""
    
    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests = defaultdict(list)
        self._lock = threading.Lock()
    
    def is_allowed(self, client_id: str) -> bool:
        """检查是否允许请求"""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            
            # 清理过期请求
            self._requests[client_id] = [t for t in self._requests[client_id] if t > cutoff]
            
            if len(self._requests[client_id]) >= self.max_requests:
                return False
            
            self._requests[client_id].append(now)
            return True
    
    def get_remaining(self, client_id: str) -> int:
        """获取剩余请求数"""
        with self._lock:
            now = time.time()
            cutoff = now - self.window_seconds
            self._requests[client_id] = [t for t in self._requests[client_id] if t > cutoff]
            return max(0, self.max_requests - len(self._requests[client_id]))


class ResponseCache:
    """响应缓存"""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._cache = {}
        self._lock = threading.Lock()
    
    def _generate_key(self, endpoint: str, params: dict) -> str:
        """生成缓存键"""
        data = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(data.encode()).hexdigest()
    
    def get(self, endpoint: str, params: dict = None) -> Optional[dict]:
        """获取缓存"""
        params = params or {}
        key = self._generate_key(endpoint, params)
        
        with self._lock:
            if key in self._cache:
                entry = self._cache[key]
                if entry['expires'] > time.time():
                    return entry['data']
                else:
                    del self._cache[key]
        return None
    
    def set(self, endpoint: str, data: dict, params: dict = None, ttl: int = None):
        """设置缓存"""
        params = params or {}
        key = self._generate_key(endpoint, params)
        ttl = ttl or self.default_ttl
        
        with self._lock:
            self._cache[key] = {
                'data': data,
                'expires': time.time() + ttl,
                'created': time.time()
            }
    
    def invalidate(self, endpoint: str = None, pattern: str = None):
        """清除缓存"""
        with self._lock:
            if endpoint:
                # 删除特定端点的缓存
                keys_to_delete = []
                for key, entry in self._cache.items():
                    if endpoint in key:
                        keys_to_delete.append(key)
                for key in keys_to_delete:
                    del self._cache[key]
            else:
                self._cache.clear()
    
    def get_stats(self) -> dict:
        """获取缓存统计"""
        with self._lock:
            total = len(self._cache)
            expired = sum(1 for e in self._cache.values() if e['expires'] <= time.time())
            return {
                'total_entries': total,
                'expired': expired,
                'active': total - expired
            }


class CircuitBreaker:
    """熔断器"""
    
    def __init__(self, failure_threshold: int = 5, timeout_seconds: int = 60):
        self.failure_threshold = failure_threshold
        self.timeout_seconds = timeout_seconds
        self._failures = {}
        self._last_failure_time = {}
        self._lock = threading.Lock()
    
    def is_open(self, service: str) -> bool:
        """检查熔断是否开启"""
        with self._lock:
            if service not in self._failures:
                return False
            
            if self._failures[service] >= self.failure_threshold:
                # 检查是否超时
                if service in self._last_failure_time:
                    if time.time() - self._last_failure_time[service] > self.timeout_seconds:
                        # 半开状态
                        return False
                return True
            return False
    
    def record_success(self, service: str):
        """记录成功"""
        with self._lock:
            self._failures[service] = 0
    
    def record_failure(self, service: str):
        """记录失败"""
        with self._lock:
            self._failures[service] = self._failures.get(service, 0) + 1
            self._last_failure_time[service] = time.time()
    
    def get_status(self, service: str) -> dict:
        """获取熔断状态"""
        with self._lock:
            return {
                'service': service,
                'failures': self._failures.get(service, 0),
                'state': 'open' if self.is_open(service) else 'closed',
                'threshold': self.failure_threshold
            }


class EnhancedAPIGateway:
    """增强API网关"""
    
    def __init__(self):
        self.rate_limiter = RateLimiter(max_requests=100, window_seconds=60)
        self.cache = ResponseCache(default_ttl=300)
        self.circuit_breaker = CircuitBreaker(failure_threshold=5, timeout_seconds=60)
        self._middleware = []
        self._routes = {}
        self._stats = {
            'total_requests': 0,
            'cached_requests': 0,
            'rate_limited': 0,
            'circuit_broken': 0,
            'errors': 0
        }
        self._lock = threading.Lock()
    
    def add_middleware(self, func: Callable):
        """添加中间件"""
        self._middleware.append(func)
    
    def register_route(self, path: str, handler: Callable, methods: list = None):
        """注册路由"""
        methods = methods or ['GET']
        self._routes[path] = {
            'handler': handler,
            'methods': methods,
            'cached': False,
            'cache_ttl': 0
        }
    
    def enable_caching(self, path: str, ttl: int = 300):
        """启用缓存"""
        if path in self._routes:
            self._routes[path]['cached'] = True
            self._routes[path]['cache_ttl'] = ttl
    
    def rate_limit(self, path: str, max_requests: int = 100, window: int = 60):
        """设置速率限制"""
        if path not in self._routes:
            self._routes[path] = {'handler': None, 'methods': ['GET']}
        self._routes[path]['rate_limit'] = {
            'max_requests': max_requests,
            'window': window
        }
    
    def protect_service(self, service: str):
        """保护后端服务"""
        if service not in self._routes:
            self._routes[service] = {'handler': None, 'methods': ['GET']}
        self._routes[service]['circuit_breaker'] = True
    
    def handle_request(self, path: str, method: str, params: dict = None,
                       client_id: str = 'default', body: dict = None) -> dict:
        """处理请求"""
        with self._lock:
            self._stats['total_requests'] += 1
        
        params = params or {}
        
        # 速率限制检查
        if path in self._routes and 'rate_limit' in self._routes[path]:
            limit = self._routes[path]['rate_limit']
            limiter = RateLimiter(limit['max_requests'], limit['window'])
            if not limiter.is_allowed(client_id):
                with self._lock:
                    self._stats['rate_limited'] += 1
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'retry_after': limit['window']
                }
        else:
            # 全局限流
            if not self.rate_limiter.is_allowed(client_id):
                with self._lock:
                    self._stats['rate_limited'] += 1
                return {
                    'success': False,
                    'error': 'Rate limit exceeded',
                    'retry_after': 60
                }
        
        # 熔断检查
        if path in self._routes and self._routes[path].get('circuit_breaker'):
            if self.circuit_breaker.is_open(path):
                with self._lock:
                    self._stats['circuit_broken'] += 1
                return {
                    'success': False,
                    'error': 'Service temporarily unavailable',
                    'code': 'CIRCUIT_OPEN'
                }
        
        # 缓存检查
        route = self._routes.get(path, {})
        if route.get('cached'):
            cached = self.cache.get(path, params)
            if cached:
                with self._lock:
                    self._stats['cached_requests'] += 1
                return {
                    'success': True,
                    'data': cached,
                    'cached': True
                }
        
        # 执行中间件
        for mw in self._middleware:
            result = mw(path, method, params, body)
            if result and not result.get('success', True):
                return result
        
        # 路由不存在
        if path not in self._routes:
            return {
                'success': False,
                'error': 'Not found',
                'code': 404
            }
        
        # 调用处理函数
        handler = route.get('handler')
        if handler:
            try:
                result = handler(params, body)
                
                # 缓存结果
                if route.get('cached'):
                    self.cache.set(path, result, params, route.get('cache_ttl', 300))
                
                # 记录成功
                if route.get('circuit_breaker'):
                    self.circuit_breaker.record_success(path)
                
                return {
                    'success': True,
                    'data': result
                }
            except Exception as e:
                # 记录失败
                if route.get('circuit_breaker'):
                    self.circuit_breaker.record_failure(path)
                
                with self._lock:
                    self._stats['errors'] += 1
                
                return {
                    'success': False,
                    'error': str(e)
                }
        
        return {'success': True, 'message': 'No handler registered'}
    
    def get_stats(self) -> dict:
        """获取网关统计"""
        with self._lock:
            stats = self._stats.copy()
            stats['cache'] = self.cache.get_stats()
            return stats


# 测试
if __name__ == '__main__':
    print("🔧 增强API网关测试")
    print("="*50)
    
    gateway = EnhancedAPIGateway()
    
    # 注册路由
    def hello_handler(params, body):
        return {'message': 'Hello, World!', 'time': datetime.now().isoformat()}
    
    def slow_handler(params, body):
        time.sleep(0.1)
        return {'message': 'Slow response'}
    
    gateway.register_route('/api/hello', hello_handler)
    gateway.register_route('/api/slow', slow_handler)
    gateway.register_route('/api/users', lambda p, b: {'users': ['alice', 'bob']})
    
    # 启用功能
    gateway.enable_caching('/api/users', ttl=60)
    gateway.rate_limit('/api/hello', max_requests=10, window=60)
    gateway.protect_service('/api/slow')
    
    print("\n📊 测试请求:")
    
    # 普通请求
    result = gateway.handle_request('/api/hello', 'GET', client_id='test-client')
    print(f"  /api/hello: {result['success']}")
    
    # 缓存请求
    result = gateway.handle_request('/api/users', 'GET', client_id='test-client')
    print(f"  /api/users (1st): cached={result.get('cached', False)}")
    
    result = gateway.handle_request('/api/users', 'GET', client_id='test-client')
    print(f"  /api/users (2nd): cached={result.get('cached', False)}")
    
    # 熔断测试
    for i in range(6):
        gateway.circuit_breaker.record_failure('/api/slow')
    
    result = gateway.handle_request('/api/slow', 'GET', client_id='test-client')
    print(f"  /api/slow (熔断): {result.get('error', 'OK')}")
    
    print("\n📈 网关统计:")
    stats = gateway.get_stats()
    print(json.dumps(stats, indent=2))
    
    print("\n✅ API网关测试完成")