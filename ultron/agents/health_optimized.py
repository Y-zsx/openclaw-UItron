#!/usr/bin/env python3
"""
奥创Agent健康检查优化版
- 添加响应缓存
- 异步并行检测
- 性能指标追踪
"""
import asyncio
import aiohttp
import time
import json
from datetime import datetime
from typing import Dict, List, Optional

class OptimizedHealthChecker:
    def __init__(self):
        self.cache = {}
        self.cache_ttl = 30  # 缓存30秒
        self.service_endpoints = {
            "health_api": "http://localhost:18210/health",
            # 只检查实际运行的服务
        }
        self.stats = {
            "total_checks": 0,
            "avg_response_time": 0,
            "cache_hits": 0
        }
    
    def _is_cache_valid(self, key: str) -> bool:
        if key not in self.cache:
            return False
        return time.time() - self.cache[key]["timestamp"] < self.cache_ttl
    
    async def check_service(self, name: str, url: str) -> Dict:
        """检查单个服务"""
        start = time.time()
        try:
            async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=3)) as session:
                async with session.get(url) as resp:
                    response_time = (time.time() - start) * 1000
                    return {
                        "name": name,
                        "status": "healthy" if resp.status == 200 else "unhealthy",
                        "response_time": round(response_time, 1),
                        "status_code": resp.status
                    }
        except Exception as e:
            return {
                "name": name,
                "status": "unhealthy",
                "response_time": (time.time() - start) * 1000,
                "error": str(e)
            }
    
    async def check_all(self, use_cache: bool = True) -> Dict:
        """并行检查所有服务"""
        cache_key = "health_check"
        
        # 检查缓存
        if use_cache and self._is_cache_valid(cache_key):
            self.stats["cache_hits"] += 1
            return self.cache[cache_key]["data"]
        
        start_total = time.time()
        
        # 并行检查
        tasks = [self.check_service(name, url) for name, url in self.service_endpoints.items()]
        results = await asyncio.gather(*tasks)
        
        total_time = (time.time() - start_total) * 1000
        
        # 计算健康分数
        healthy_count = sum(1 for r in results if r["status"] == "healthy")
        health_score = int((healthy_count / len(results)) * 100)
        
        response = {
            "status": "healthy" if health_score == 100 else "degraded",
            "timestamp": datetime.now().isoformat(),
            "metrics": {
                "services": list(results),
                "healthy_count": healthy_count,
                "total_services": len(results),
                "health_score": health_score,
                "total_response_time": round(total_time, 1),
                "cache_hits": self.stats["cache_hits"]
            }
        }
        
        # 更新缓存
        self.cache[cache_key] = {
            "data": response,
            "timestamp": time.time()
        }
        
        self.stats["total_checks"] += 1
        
        return response

async def main():
    checker = OptimizedHealthChecker()
    
    # 第一次检查 (无缓存)
    result = await checker.check_all(use_cache=False)
    print(f"首次检查: {result['metrics']['health_score']}分, 耗时{result['metrics']['total_response_time']}ms")
    
    # 第二次检查 (有缓存)
    result = await checker.check_all(use_cache=True)
    print(f"缓存检查: {result['metrics']['health_score']}分, 缓存命中: {result['metrics']['cache_hits']}")
    
    print(f"优化完成: {json.dumps(result, indent=2)}")

if __name__ == "__main__":
    asyncio.run(main())