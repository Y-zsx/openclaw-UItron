#!/usr/bin/env python3
"""
Agent协作网络性能监控服务
第41世: 性能优化与监控增强
"""

import json
import time
import asyncio
import statistics
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque

# 性能指标存储
DATA_DIR = Path("/root/.openclaw/workspace/ultron/monitor/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

class CollabPerformanceMonitor:
    """协作网络性能监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(lambda: deque(maxlen=1000))
        self.alerts = deque(maxlen=100)
        self.thresholds = {
            "response_time_ms": 500,
            "error_rate_percent": 5,
            "cpu_percent": 80,
            "memory_percent": 85,
            "queue_depth": 100
        }
        self.cache = {}
        self.cache_ttl = 60  # seconds
        
    def record_metric(self, metric_type: str, value: float, tags: Dict = None):
        """记录性能指标"""
        entry = {
            "timestamp": time.time(),
            "value": value,
            "tags": tags or {}
        }
        self.metrics[metric_type].append(entry)
        
    def record_request(self, endpoint: str, duration_ms: float, status: int):
        """记录API请求"""
        self.record_metric("api_request_duration", duration_ms, {"endpoint": endpoint, "status": status})
        self.record_metric("api_request_count", 1, {"endpoint": endpoint, "status": status})
        
    def get_statistics(self, metric_type: str, window_seconds: int = 300) -> Dict:
        """获取统计数据"""
        if metric_type not in self.metrics:
            return {}
            
        cutoff = time.time() - window_seconds
        values = [m["value"] for m in self.metrics[metric_type] if m["timestamp"] > cutoff]
        
        if not values:
            return {"count": 0}
            
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": statistics.mean(values),
            "median": statistics.median(values),
            "p95": sorted(values)[int(len(values) * 0.95)] if len(values) > 20 else values[-1],
            "p99": sorted(values)[int(len(values) * 0.99)] if len(values) > 100 else values[-1]
        }
    
    def get_endpoint_stats(self) -> Dict:
        """获取各端点性能统计"""
        endpoint_stats = defaultdict(lambda: {"count": 0, "total_time": 0, "errors": 0})
        
        for entry in self.metrics.get("api_request_duration", []):
            endpoint = entry["tags"].get("endpoint", "unknown")
            endpoint_stats[endpoint]["count"] += 1
            endpoint_stats[endpoint]["total_time"] += entry["value"]
            
        for entry in self.metrics.get("api_request_count", []):
            endpoint = entry["tags"].get("endpoint", "unknown")
            status = entry["tags"].get("status", 200)
            if status >= 400:
                endpoint_stats[endpoint]["errors"] += entry["value"]
                
        result = {}
        for endpoint, stats in endpoint_stats.items():
            result[endpoint] = {
                "requests": stats["count"],
                "avg_time_ms": stats["total_time"] / stats["count"] if stats["count"] > 0 else 0,
                "error_rate": (stats["errors"] / stats["count"] * 100) if stats["count"] > 0 else 0
            }
        return result
    
    def check_health(self) -> Dict:
        """健康检查"""
        stats = self.get_statistics("api_request_duration", window_seconds=60)
        error_stats = self.get_endpoint_stats()
        
        errors = []
        warnings = []
        
        # 检查响应时间
        if stats.get("p95", 0) > self.thresholds["response_time_ms"]:
            warnings.append(f"P95响应时间: {stats['p95']:.1f}ms > {self.thresholds['response_time_ms']}ms")
            
        # 检查错误率
        for endpoint, stat in error_stats.items():
            if stat["error_rate"] > self.thresholds["error_rate_percent"]:
                errors.append(f"{endpoint} 错误率: {stat['error_rate']:.1f}%")
                
        return {
            "status": "healthy" if not errors else "degraded",
            "metrics": stats,
            "endpoints": error_stats,
            "alerts": errors + warnings
        }
    
    def get_cache_stats(self) -> Dict:
        """缓存统计"""
        return {
            "size": len(self.cache),
            "entries": list(self.cache.keys())[:10]
        }
    
    def cache_get(self, key: str) -> Optional[Any]:
        """带统计的缓存获取"""
        if key in self.cache:
            entry = self.cache[key]
            if time.time() - entry["timestamp"] < self.cache_ttl:
                self.record_metric("cache_hit", 1, {"key": key})
                return entry["value"]
            else:
                del self.cache[key]
        self.record_metric("cache_miss", 1, {"key": key})
        return None
    
    def cache_set(self, key: str, value: Any):
        """缓存设置"""
        self.cache[key] = {"value": value, "timestamp": time.time()}
        
    def export_metrics(self) -> Dict:
        """导出所有指标"""
        return {
            "timestamp": datetime.now().isoformat(),
            "health": self.check_health(),
            "endpoint_stats": self.get_endpoint_stats(),
            "cache": self.get_cache_stats()
        }


# 全局监控器实例
_monitor = CollabPerformanceMonitor()

def get_monitor() -> CollabPerformanceMonitor:
    return _monitor


if __name__ == "__main__":
    # 测试
    monitor = get_monitor()
    
    # 模拟请求
    for i in range(10):
        monitor.record_request("/api/agents", 50 + i * 5, 200)
        monitor.record_request("/api/tasks", 100 + i * 10, 200 if i < 8 else 500)
    
    print(json.dumps(monitor.export_metrics(), indent=2, ensure_ascii=False))