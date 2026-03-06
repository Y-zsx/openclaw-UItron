#!/usr/bin/env python3
"""
Agent服务熔断器系统 (第201世)
监控Agent调用失败率，自动熔断故障服务
"""

import asyncio
import json
import time
from datetime import datetime
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from aiohttp import web
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("circuit_breaker")

class CircuitState(Enum):
    CLOSED = "closed"      # 正常状态
    OPEN = "open"          # 熔断状态
    HALF_OPEN = "half_open"  # 半开状态（尝试恢复）

@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5        # 失败次数阈值
    success_threshold: int = 3        # 恢复所需成功次数
    timeout: float = 30.0             # 熔断超时时间(秒)
    half_open_requests: int = 3       # 半开状态下允许的请求数
    
    failures: int = 0
    successes: int = 0
    state: CircuitState = CircuitState.CLOSED
    last_failure_time: float = 0
    half_open_count: int = 0
    total_calls: int = 0
    total_failures: int = 0
    total_successes: int = 0
    
    def record_success(self):
        self.total_calls += 1
        self.total_successes += 1
        self.last_failure_time = 0
        
        if self.state == CircuitState.HALF_OPEN:
            self.successes += 1
            if self.successes >= self.success_threshold:
                self.state = CircuitState.CLOSED
                self.failures = 0
                self.successes = 0
                self.half_open_count = 0
                logger.info(f"[{self.name}] 熔断恢复！状态: CLOSED")
        elif self.state == CircuitState.CLOSED:
            self.failures = 0
    
    def record_failure(self):
        self.total_calls += 1
        self.total_failures += 1
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.CLOSED:
            if self.failures >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(f"[{self.name}] 触发熔断！状态: OPEN (失败次数: {self.failures})")
        elif self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.half_open_count = 0
            logger.warning(f"[{self.name}] 半开状态失败，重新打开熔断！状态: OPEN")
        elif self.state == CircuitState.OPEN:
            pass  # 已打开，不记录
    
    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # 检查超时
            if time.time() - self.last_failure_time >= self.timeout:
                self.state = CircuitState.HALF_OPEN
                self.successes = 0
                self.half_open_count = 0
                logger.info(f"[{self.name}] 熔断超时，进入半开状态: HALF_OPEN")
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_count < self.half_open_requests:
                self.half_open_count += 1
                return True
            return False
        
        return False
    
    def get_stats(self) -> dict:
        failure_rate = (self.total_failures / self.total_calls * 100) if self.total_calls > 0 else 0
        return {
            "name": self.name,
            "state": self.state.value,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "failure_rate": f"{failure_rate:.1f}%",
            "current_failures": self.failures,
            "current_successes": self.successes,
            "half_open_count": self.half_open_count
        }

# 熔断器实例字典
circuit_breakers: Dict[str, CircuitBreaker] = {}

# 模拟的Agent后端配置
AGENT_BACKENDS = {
    "collaborate-center": {"url": "http://localhost:8001", "enabled": True},
    "service-governance": {"url": "http://localhost:8002", "enabled": True},
    "collaboration-api": {"url": "http://localhost:8003", "enabled": True},
    "task-scheduler": {"url": "http://localhost:8004", "enabled": True},
    "result-aggregator": {"url": "http://localhost:8005", "enabled": True},
}

def get_or_create_breaker(name: str) -> CircuitBreaker:
    if name not in circuit_breakers:
        circuit_breakers[name] = CircuitBreaker(name=name)
    return circuit_breakers[name]

async def call_agent(agent_name: str, request_data: dict) -> dict:
    """调用Agent服务并记录结果"""
    breaker = get_or_create_breaker(agent_name)
    
    if not breaker.can_execute():
        return {
            "success": False,
            "error": "circuit_open",
            "message": f"熔断器已打开，拒绝请求",
            "circuit_state": breaker.state.value
        }
    
    # 模拟调用（随机失败以测试熔断）
    import random
    # 模拟一定比例的失败
    success = random.random() > 0.3  # 70%成功率
    
    if success:
        breaker.record_success()
        return {
            "success": True,
            "agent": agent_name,
            "result": f"Agent {agent_name} 处理成功",
            "circuit_state": breaker.state.value
        }
    else:
        breaker.record_failure()
        return {
            "success": False,
            "error": "agent_error",
            "message": f"Agent {agent_name} 处理失败",
            "circuit_state": breaker.state.value
        }

# HTTP服务
async def health_check(request):
    """健康检查"""
    return web.json_response({
        "status": "healthy",
        "service": "circuit-breaker",
        "port": 18302,
        "timestamp": datetime.now().isoformat()
    })

async def get_breakers(request):
    """获取所有熔断器状态"""
    breakers_info = {name: breaker.get_stats() for name, breaker in circuit_breakers.items()}
    return web.json_response({
        "circuit_breakers": breakers_info,
        "total": len(circuit_breakers)
    })

async def get_breaker(request):
    """获取单个熔断器状态"""
    name = request.match_info['name']
    if name not in circuit_breakers:
        return web.json_response({"error": "not_found"}, status=404)
    return web.json_response(circuit_breakers[name].get_stats())

async def reset_breaker(request):
    """手动重置熔断器"""
    name = request.match_info['name']
    if name in circuit_breakers:
        circuit_breakers[name].state = CircuitState.CLOSED
        circuit_breakers[name].failures = 0
        circuit_breakers[name].successes = 0
        return web.json_response({"message": f"熔断器 {name} 已重置"})
    return web.json_response({"error": "not_found"}, status=404)

async def call_agent_handler(request):
    """调用Agent的HTTP接口"""
    try:
        data = await request.json()
    except:
        data = {}
    
    agent_name = data.get("agent", "collaborate-center")
    
    # 确保熔断器已创建
    get_or_create_breaker(agent_name)
    
    result = await call_agent(agent_name, data)
    return web.json_response(result)

async def simulate_load(request):
    """模拟负载测试"""
    results = []
    for agent_name in AGENT_BACKENDS.keys():
        get_or_create_breaker(agent_name)
        result = await call_agent(agent_name, {"test": True})
        results.append(result)
    
    return web.json_response({
        "simulation_results": results,
        "summary": {
            "total": len(results),
            "success": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"])
        }
    })

def create_app():
    app = web.Application()
    app.router.add_get('/health', health_check)
    app.router.add_get('/breakers', get_breakers)
    app.router.add_get('/breakers/{name}', get_breaker)
    app.router.add_post('/breakers/{name}/reset', reset_breaker)
    app.router.add_post('/call', call_agent_handler)
    app.router.add_post('/simulate', simulate_load)
    return app

if __name__ == '__main__':
    # 初始化熔断器
    for agent_name in AGENT_BACKENDS.keys():
        get_or_create_breaker(agent_name)
    
    logger.info("=" * 50)
    logger.info("Agent服务熔断器系统启动 (第201世)")
    logger.info("监听端口: 18302")
    logger.info("监控的Agent: " + ", ".join(AGENT_BACKENDS.keys()))
    logger.info("=" * 50)
    
    app = create_app()
    web.run_app(app, host='0.0.0.0', port=18302)