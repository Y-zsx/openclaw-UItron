#!/usr/bin/env python3
"""
Agent服务熔断与限流系统
结合熔断器模式与限流器，保护Agent服务稳定性
"""

import json
import time
import threading
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
import statistics

# ============== 限流配置 ==============
RATE_LIMIT_CONFIG = {
    "port": 18312,
    "limiters": {
        "collaborate-center": {"rate": 100, "burst": 200},
        "service-governance": {"rate": 50, "burst": 100},
        "collaboration-api": {"rate": 80, "burst": 160},
        "task-scheduler": {"rate": 60, "burst": 120},
        "result-aggregator": {"rate": 50, "burst": 100},
        "health-monitor": {"rate": 40, "burst": 80},
        "autoscaler": {"rate": 30, "burst": 60},
        "loadbalancer": {"rate": 100, "burst": 200}
    }
}

# ============== 熔断器配置 ==============
CIRCUIT_BREAKER_CONFIG = {
    "failure_threshold": 5,      # 失败次数超过此值则熔断
    "success_threshold": 2,      # 成功次数超过此值则恢复
    "timeout": 30,               # 熔断超时（秒）
    "half_open_max_requests": 3  # 半开状态下最大尝试次数
}


class TokenBucket:
    """令牌桶算法"""
    def __init__(self, rate, burst):
        self.rate = rate
        self.burst = burst
        self.tokens = float(burst)
        self.last_time = time.time()
        self.lock = threading.Lock()
    
    def consume(self, tokens=1):
        with self.lock:
            now = time.time()
            elapsed = now - self.last_time
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_time = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, self.tokens
            return False, self.tokens
    
    def get_tokens(self):
        """获取可用令牌数"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_time
            return min(self.burst, self.tokens + elapsed * self.rate)


class CircuitBreaker:
    """熔断器实现"""
    def __init__(self, name, config=None):
        self.name = name
        config = config or CIRCUIT_BREAKER_CONFIG
        self.failure_threshold = config["failure_threshold"]
        self.success_threshold = config["success_threshold"]
        self.timeout = config["timeout"]
        self.half_open_max_requests = config["half_open_max_requests"]
        
        self.state = "closed"  # closed, open, half-open
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = 0
        self.half_open_requests = 0
        self.lock = threading.Lock()
        
        # 统计
        self.total_requests = 0
        self.total_successes = 0
        self.total_failures = 0
        self.latencies = []
    
    def call(self, func, *args, **kwargs):
        """执行函数并自动管理熔断"""
        with self.lock:
            self.total_requests += 1
            
            # 状态检查
            if self.state == "open":
                if time.time() - self.last_failure_time > self.timeout:
                    self.state = "half-open"
                    self.half_open_requests = 0
                    print(f"[CircuitBreaker] {self.name}: OPEN -> HALF-OPEN")
                else:
                    self.total_failures += 1
                    return None, "circuit_open"
            
            elif self.state == "half-open":
                if self.half_open_requests >= self.half_open_max_requests:
                    self.total_failures += 1
                    return None, "circuit_open"
                self.half_open_requests += 1
        
        # 执行调用
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            latency = time.time() - start_time
            
            with self.lock:
                self.total_successes += 1
                self.latencies.append(latency)
                if len(self.latencies) > 100:
                    self.latencies = self.latencies[-100:]
                
                # 状态转换
                if self.state == "half-open":
                    self.success_count += 1
                    if self.success_count >= self.success_threshold:
                        self.state = "closed"
                        self.success_count = 0
                        self.failure_count = 0
                        print(f"[CircuitBreaker] {self.name}: HALF-OPEN -> CLOSED")
                else:
                    self.failure_count = 0
            
            return result, None
            
        except Exception as e:
            latency = time.time() - start_time
            with self.lock:
                self.total_failures += 1
                self.failure_count += 1
                self.last_failure_time = time.time()
                self.latencies.append(latency)
                
                # 检查是否需要熔断
                if self.failure_count >= self.failure_threshold:
                    self.state = "open"
                    print(f"[CircuitBreaker] {self.name}: CLOSED -> OPEN (failures: {self.failure_count})")
            
            return None, str(e)
    
    def get_status(self):
        """获取熔断器状态"""
        with self.lock:
            avg_latency = statistics.mean(self.latencies) if self.latencies else 0
            return {
                "name": self.name,
                "state": self.state,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "total_requests": self.total_requests,
                "total_successes": self.total_successes,
                "total_failures": self.total_failures,
                "avg_latency": round(avg_latency * 1000, 2),
                "last_failure_time": self.last_failure_time
            }
    
    def record_success(self):
        """手动记录成功"""
        with self.lock:
            self.total_successes += 1
            if self.state == "half-open":
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = "closed"
                    self.success_count = 0
                    self.failure_count = 0
    
    def record_failure(self):
        """手动记录失败"""
        with self.lock:
            self.total_failures += 1
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold and self.state == "closed":
                self.state = "open"


class CircuitBreakerManager:
    """熔断器管理器"""
    def __init__(self):
        self.breakers = {}
        self.rate_limiters = {}
        self.lock = threading.Lock()
        
        # 初始化限流器
        for name, config in RATE_LIMIT_CONFIG["limiters"].items():
            self.rate_limiters[name] = TokenBucket(config["rate"], config["burst"])
    
    def get_breaker(self, name):
        """获取或创建熔断器"""
        with self.lock:
            if name not in self.breakers:
                self.breakers[name] = CircuitBreaker(name)
            return self.breakers[name]
    
    def check_rate_limit(self, service_name):
        """检查限流"""
        if service_name not in self.rate_limiters:
            return True, "unknown_service"
        
        limiter = self.rate_limiters[service_name]
        return limiter.consume()
    
    def get_stats(self):
        """获取所有统计"""
        return {
            "breakers": {name: b.get_status() for name, b in self.breakers.items()},
            "limiters": {
                name: {
                    "available_tokens": round(limiter.get_tokens(), 2),
                    "rate": limiter.rate,
                    "burst": limiter.burst
                }
                for name, limiter in self.rate_limiters.items()
            }
        }
    
    def reset_all(self):
        """重置所有熔断器"""
        with self.lock:
            for breaker in self.breakers.values():
                breaker.state = "closed"
                breaker.failure_count = 0
                breaker.success_count = 0


# 全局管理器
manager = CircuitBreakerManager()


class CircuitBreakerHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    def log_message(self, format, *args):
        pass  # 禁用日志
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/health":
            self.send_json({"status": "ok", "service": "circuit-breaker-rate-limiter"})
        
        elif path == "/status":
            self.send_json(manager.get_stats())
        
        elif path == "/breaker":
            # 获取指定熔断器状态
            params = parse_qs(parsed.query)
            name = params.get("name", [None])[0]
            if name:
                breaker = manager.get_breaker(name)
                self.send_json(breaker.get_status())
            else:
                self.send_json({"breakers": list(manager.breakers.keys())})
        
        elif path == "/rate-limit/check":
            # 检查限流
            params = parse_qs(parsed.query)
            service = params.get("service", [None])[0]
            if service:
                allowed, msg = manager.check_rate_limit(service)
                self.send_json({"allowed": allowed, "service": service, "message": msg})
            else:
                self.send_json({"error": "service parameter required"}, 400)
        
        elif path == "/reset":
            manager.reset_all()
            self.send_json({"message": "All breakers reset"})
        
        else:
            self.send_json({
                "service": "circuit-breaker-rate-limiter",
                "port": RATE_LIMIT_CONFIG["port"],
                "endpoints": [
                    "/health",
                    "/status",
                    "/breaker?name=<service>",
                    "/rate-limit/check?service=<name>",
                    "/reset"
                ]
            })
    
    def do_POST(self):
        parsed = urlparse(self.path)
        
        if parsed.path == "/breaker/record":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length)
            data = json.loads(body)
            
            service = data.get("service")
            result = data.get("result")  # "success" or "failure"
            
            if service:
                breaker = manager.get_breaker(service)
                if result == "success":
                    breaker.record_success()
                else:
                    breaker.record_failure()
                self.send_json({"message": "recorded", "service": service, "result": result})
            else:
                self.send_json({"error": "service required"}, 400)
        
        else:
            self.send_json({"error": "not found"}, 404)


def main():
    port = RATE_LIMIT_CONFIG["port"]
    print(f"[CircuitBreaker] Agent服务熔断与限流系统启动，端口: {port}")
    print(f"[CircuitBreaker] 限流配置: {len(RATE_LIMIT_CONFIG['limiters'])} 个服务")
    print(f"[CircuitBreaker] 熔断阈值: 失败{CIRCUIT_BREAKER_CONFIG['failure_threshold']}次触发，"
          f"超时{CIRCUIT_BREAKER_CONFIG['timeout']}秒后半开")
    
    server = HTTPServer(("0.0.0.0", port), CircuitBreakerHandler)
    print(f"[CircuitBreaker] 服务运行在 http://0.0.0.0:{port}")
    print(f"[CircuitBreaker] 端点: /health, /status, /breaker, /rate-limit/check, /reset")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[CircuitBreaker] 关闭服务...")
        server.shutdown()


if __name__ == "__main__":
    main()