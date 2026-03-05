#!/usr/bin/env python3
"""
Agent协作网络性能优化中间件
- 连接池管理
- 请求批处理
- 智能缓存
- 速率限制
"""

import time
import asyncio
import hashlib
import json
from typing import Dict, Any, Callable, Optional
from functools import wraps
from collections import defaultdict, deque
from datetime import datetime

class ConnectionPool:
    """连接池管理"""
    
    def __init__(self, max_connections: int = 100):
        self.max_connections = max_connections
        self.available = deque(maxlen=max_connections)
        self.in_use = set()
        self.stats = {"acquired": 0, "released": 0, "created": 0}
        
    async def acquire(self, timeout: float = 5.0) -> Optional[Any]:
        """获取连接"""
        start = time.time()
        while time.time() - start < timeout:
            if self.available:
                conn = self.available.pop()
                self.in_use.add(conn)
                self.stats["acquired"] += 1
                return conn
            if len(self.in_use) < self.max_connections:
                conn = f"conn_{self.stats['created']}"
                self.stats["created"] += 1
                self.in_use.add(conn)
                self.stats["acquired"] += 1
                return conn
            await asyncio.sleep(0.01)
        return None
        
    def release(self, conn: Any):
        """释放连接"""
        if conn in self.in_use:
            self.in_use.remove(conn)
            self.available.append(conn)
            self.stats["released"] += 1
            
    def get_stats(self) -> Dict:
        return {
            "max": self.max_connections,
            "available": len(self.available),
            "in_use": len(self.in_use),
            **self.stats
        }


class RequestBatcher:
    """请求批处理"""
    
    def __init__(self, batch_size: int = 10, wait_ms: int = 50):
        self.batch_size = batch_size
        self.wait_ms = wait_ms / 1000
        self.pending = {}
        self.results = {}
        
    def add_request(self, request_id: str, key: str, processor: Callable):
        """添加请求到批处理队列"""
        if key not in self.pending:
            self.pending[key] = []
        self.pending[key].append((request_id, processor))
        
    async def process_batch(self, key: str):
        """处理批次"""
        if key not in self.pending or not self.pending[key]:
            return
            
        batch = self.pending.pop(key)
        if len(batch) < self.batch_size:
            await asyncio.sleep(self.wait_ms)
            
        # 执行批处理
        results = []
        for request_id, processor in batch:
            try:
                result = await processor() if asyncio.iscoroutinefunction(processor) else processor()
                results.append((request_id, result))
            except Exception as e:
                results.append((request_id, {"error": str(e)}))
                
        for request_id, result in results:
            self.results[request_id] = result
            
    def get_result(self, request_id: str) -> Optional[Any]:
        return self.results.pop(request_id, None)


class SmartCache:
    """智能缓存 - 支持TTL和模式匹配"""
    
    def __init__(self, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self.cache = {}
        self.access_count = defaultdict(int)
        self.hit_count = 0
        self.miss_count = 0
        
    def _make_key(self, prefix: str, *args, **kwargs) -> str:
        """生成缓存键"""
        key_data = f"{prefix}:{args}:{sorted(kwargs.items())}"
        return hashlib.md5(key_data.encode()).hexdigest()[:16]
    
    def get(self, key: str) -> Optional[Any]:
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < entry["ttl"]:
                self.hit_count += 1
                self.access_count[key] += 1
                return entry["value"]
            else:
                del self.cache[key]
        self.miss_count += 1
        return None
        
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        self.cache[key] = {
            "value": value,
            "timestamp": time.time(),
            "ttl": ttl or self.default_ttl
        }
        
    def invalidate_pattern(self, pattern: str):
        """按模式失效缓存"""
        keys_to_delete = [k for k in self.cache.keys() if pattern in k]
        for key in keys_to_delete:
            del self.cache[key]
            
    def get_stats(self) -> Dict:
        total = self.hit_count + self.miss_count
        hit_rate = (self.hit_count / total * 100) if total > 0 else 0
        return {
            "entries": len(self.cache),
            "hits": self.hit_count,
            "misses": self.miss_count,
            "hit_rate": f"{hit_rate:.1f}%",
            "top_accessed": sorted(self.access_count.items(), key=lambda x: -x[1])[:5]
        }


class RateLimiter:
    """滑动窗口速率限制"""
    
    def __init__(self, requests_per_minute: int = 60):
        self.rpm = requests_per_minute
        self.window_size = 60
        self.requests = defaultdict(lambda: deque(maxlen=requests_per_minute))
        
    def is_allowed(self, client_id: str) -> bool:
        now = time.time()
        window_start = now - self.window_size
        
        # 清理旧请求
        client_requests = self.requests[client_id]
        while client_requests and client_requests[0] < window_start:
            client_requests.popleft()
            
        if len(client_requests) < self.rpm:
            client_requests.append(now)
            return True
        return False
        
    def get_remaining(self, client_id: str) -> int:
        now = time.time()
        window_start = now - self.window_size
        client_requests = self.requests[client_id]
        active = sum(1 for r in client_requests if r >= window_start)
        return max(0, self.rpm - active)


class PerformanceOptimizer:
    """性能优化器 - 整合所有优化功能"""
    
    def __init__(self):
        self.connection_pool = ConnectionPool(max_connections=100)
        self.batcher = RequestBatcher(batch_size=10, wait_ms=50)
        self.cache = SmartCache(default_ttl=300)
        self.rate_limiter = RateLimiter(requests_per_minute=60)
        self.metrics = {
            "requests_total": 0,
            "requests_cached": 0,
            "requests_batched": 0,
            "rate_limited": 0
        }
        
    def cached(self, key_prefix: str, ttl: Optional[int] = None):
        """缓存装饰器"""
        def decorator(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                cache_key = self.cache._make_key(key_prefix, *args, **kwargs)
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.metrics["requests_cached"] += 1
                    return cached_result
                result = await func(*args, **kwargs)
                self.cache.set(cache_key, result, ttl)
                return result
                
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                cache_key = self.cache._make_key(key_prefix, *args, **kwargs)
                cached_result = self.cache.get(cache_key)
                if cached_result is not None:
                    self.metrics["requests_cached"] += 1
                    return cached_result
                result = func(*args, **kwargs)
                self.cache.set(cache_key, result, ttl)
                return result
                
            return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
        return decorator
        
    def rate_limit(self, client_id: str = "default"):
        """速率限制装饰器"""
        def decorator(func):
            @wraps(func)
            async def wrapper(*args, **kwargs):
                if not self.rate_limiter.is_allowed(client_id):
                    self.metrics["rate_limited"] += 1
                    raise Exception(f"Rate limited. Try again later.")
                self.metrics["requests_total"] += 1
                return await func(*args, **kwargs)
            return wrapper
        return decorator
        
    def get_stats(self) -> Dict:
        return {
            "connection_pool": self.connection_pool.get_stats(),
            "cache": self.cache.get_stats(),
            "metrics": self.metrics
        }


# 全局优化器
_optimizer = PerformanceOptimizer()

def get_optimizer() -> PerformanceOptimizer:
    return _optimizer


if __name__ == "__main__":
    optimizer = get_optimizer()
    print(json.dumps(optimizer.get_stats(), indent=2, ensure_ascii=False))