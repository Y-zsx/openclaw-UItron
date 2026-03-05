#!/usr/bin/env python3
"""
跨系统协调器 (Cross-System Coordinator)
第3世：跨系统协同 - API集成框架+事件总线+协调调度

功能：
1. API集成框架 - 通用API客户端、重试机制、熔断器
2. 事件总线 - 发布/订阅模式、事件路由、事件过滤
3. 协调调度 - 跨系统任务协调、分布式锁、限流
"""

import json
import time
import hashlib
import uuid
import threading
import queue
import logging
import subprocess
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
from dataclasses import dataclass, field
from collections import defaultdict
from urllib.parse import urljoin, urlparse
import urllib.request
import urllib.error
import ssl

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ==================== API集成框架 ====================

class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断开启
    HALF_OPEN = "half_open"  # 半开


@dataclass
class CircuitBreaker:
    """熔断器 - 防止级联故障"""
    failure_threshold: int = 5
    recovery_timeout: int = 60
    half_open_requests: int = 3
    
    state: CircuitState = field(default=CircuitState.CLOSED)
    failure_count: int = field(default=0)
    last_failure_time: float = field(default=0)
    half_open_success: int = field(default=0)
    lock: threading.Lock = field(default_factory=threading.Lock)
    
    def record_success(self):
        with self.lock:
            if self.state == CircuitState.HALF_OPEN:
                self.half_open_success += 1
                if self.half_open_success >= self.half_open_requests:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.half_open_success = 0
                    logger.info("Circuit breaker CLOSED")
            elif self.state == CircuitState.CLOSED:
                self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN (half-open failure)")
            elif self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning("Circuit breaker OPEN")
    
    def can_execute(self) -> bool:
        with self.lock:
            if self.state == CircuitState.CLOSED:
                return True
            
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                    self.half_open_success = 0
                    logger.info("Circuit breaker HALF_OPEN")
                    return True
                return False
            
            return True  # HALF_OPEN


class APIClient:
    """通用API客户端 - 支持重试、熔断、超时"""
    
    def __init__(self, base_url: str = "", timeout: int = 30, max_retries: int = 3):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.default_headers = {
            "User-Agent": "Ultron-CrossSystem-Coordinator/1.0",
            "Content-Type": "application/json"
        }
    
    def _get_breaker(self, host: str) -> CircuitBreaker:
        if host not in self.circuit_breakers:
            self.circuit_breakers[host] = CircuitBreaker()
        return self.circuit_breakers[host]
    
    def request(self, method: str, endpoint: str, 
                headers: Dict = None, data: Any = None,
                retry_on_status: List[int] = None) -> Dict[str, Any]:
        """发送API请求"""
        url = urljoin(self.base_url, endpoint)
        parsed = urlparse(url)
        host = parsed.netloc
        breaker = self._get_breaker(host)
        
        retry_on_status = retry_on_status or [500, 502, 503, 504]
        
        for attempt in range(self.max_retries):
            if not breaker.can_execute():
                return {"error": "Circuit breaker OPEN", "success": False}
            
            req_headers = {**self.default_headers, **(headers or {})}
            
            try:
                body = json.dumps(data) if data else None
                req = urllib.request.Request(url, data=body, headers=req_headers, method=method)
                
                ctx = ssl.create_default_context()
                ctx.check_hostname = True
                ctx.verify_mode = ssl.CERT_REQUIRED
                
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as response:
                    content = response.read().decode('utf-8')
                    breaker.record_success()
                    
                    try:
                        return {"data": json.loads(content), "status": response.status, "success": True}
                    except json.JSONDecodeError:
                        return {"data": content, "status": response.status, "success": True}
                        
            except urllib.error.HTTPError as e:
                breaker.record_failure()
                if e.code not in retry_on_status or attempt == self.max_retries - 1:
                    return {"error": f"HTTP {e.code}: {e.reason}", "status": e.code, "success": False}
                    
            except urllib.error.URLError as e:
                breaker.record_failure()
                if attempt == self.max_retries - 1:
                    return {"error": f"URL Error: {e.reason}", "success": False}
                    
            except Exception as e:
                breaker.record_failure()
                if attempt == self.max_retries - 1:
                    return {"error": str(e), "success": False}
            
            time.sleep(2 ** attempt)  # 指数退避
        
        return {"error": "Max retries exceeded", "success": False}
    
    def get(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self.request("GET", endpoint, **kwargs)
    
    def post(self, endpoint: str, data: Any = None, **kwargs) -> Dict[str, Any]:
        return self.request("POST", endpoint, data=data, **kwargs)
    
    def put(self, endpoint: str, data: Any = None, **kwargs) -> Dict[str, Any]:
        return self.request("PUT", endpoint, data=data, **kwargs)
    
    def delete(self, endpoint: str, **kwargs) -> Dict[str, Any]:
        return self.request("DELETE", endpoint, **kwargs)


class LocalCommandExecutor:
    """本地命令执行器 - 用于本地系统集成"""
    
    def __init__(self, timeout: int = 60):
        self.timeout = timeout
    
    def execute(self, command: Union[str, List[str]], env: Dict = None) -> Dict[str, Any]:
        """执行本地命令"""
        try:
            if isinstance(command, str):
                cmd = command.split()
            else:
                cmd = command
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout,
                env={**subprocess.os.environ, **(env or {})}
            )
            
            return {
                "success": result.returncode == 0,
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "timestamp": datetime.now().isoformat()
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timeout", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            return {"success": False, "error": str(e), "timestamp": datetime.now().isoformat()}


# ==================== 事件总线 ====================

@dataclass
class Event:
    """事件对象"""
    event_type: str
    payload: Any
    source: str
    timestamp: float = field(default_factory=time.time)
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: Dict = field(default_factory=dict)


class EventBus:
    """事件总线 - 发布/订阅模式"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue: queue.Queue = queue.Queue()
        self.event_history: List[Event] = []
        self.max_history = 1000
        self.lock = threading.Lock()
        self.running = False
        self.worker_thread: Optional[threading.Thread] = None
    
    def subscribe(self, event_type: str, handler: Callable):
        """订阅事件"""
        with self.lock:
            self.subscribers[event_type].append(handler)
            logger.info(f"Subscribed to event: {event_type}")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """取消订阅"""
        with self.lock:
            if event_type in self.subscribers:
                self.subscribers[event_type].remove(handler)
    
    def publish(self, event: Event):
        """发布事件"""
        with self.lock:
            self.event_queue.put(event)
            self.event_history.append(event)
            if len(self.event_history) > self.max_history:
                self.event_history.pop(0)
    
    def publish_sync(self, event: Event):
        """同步发布事件（立即处理）"""
        self._process_event(event)
    
    def _process_event(self, event: Event):
        """处理事件"""
        handlers = self.subscribers.get(event.event_type, [])
        
        # 也通知通配符订阅者
        handlers.extend(self.subscribers.get("*", []))
        
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"Event handler error: {e}")
    
    def start(self):
        """启动事件处理循环"""
        self.running = True
        self.worker_thread = threading.Thread(target=self._event_loop, daemon=True)
        self.worker_thread.start()
        logger.info("Event bus started")
    
    def stop(self):
        """停止事件处理"""
        self.running = False
        if self.worker_thread:
            self.worker_thread.join(timeout=5)
        logger.info("Event bus stopped")
    
    def _event_loop(self):
        """事件处理循环"""
        while self.running:
            try:
                event = self.event_queue.get(timeout=1)
                self._process_event(event)
            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"Event loop error: {e}")
    
    def get_history(self, event_type: str = None, limit: int = 100) -> List[Event]:
        """获取事件历史"""
        with self.lock:
            if event_type:
                return [e for e in self.event_history if e.event_type == event_type][-limit:]
            return self.event_history[-limit:]


class EventFilter:
    """事件过滤器"""
    
    def __init__(self):
        self.filters: List[Callable[[Event], bool]] = []
    
    def add_filter(self, filter_fn: Callable[[Event], bool]):
        self.filters.append(filter_fn)
    
    def matches(self, event: Event) -> bool:
        return all(f(event) for f in self.filters)


# ==================== 协调调度 ====================

class LockType(Enum):
    REENTRANT = "reentrant"      # 可重入锁
    READ_WRITE = "read_write"    # 读写锁
    DISTRIBUTED = "distributed"  # 分布式锁（模拟）


@dataclass
class Lock:
    """锁对象"""
    name: str
    owner: str
    lock_type: LockType
    acquire_time: float
    timeout: float
    token: str = field(default_factory=lambda: str(uuid.uuid4()))


class DistributedLock:
    """分布式锁（基于文件锁实现）"""
    
    def __init__(self, lock_dir: str = "/tmp/ultron-locks"):
        self.lock_dir = lock_dir
        import os
        os.makedirs(lock_dir, exist_ok=True)
        self.local_locks: Dict[str, threading.Lock] = {}
    
    def acquire(self, name: str, owner: str, timeout: float = 30) -> Optional[str]:
        """获取锁"""
        if name not in self.local_locks:
            self.local_locks[name] = threading.Lock()
        
        lock = self.local_locks[name]
        acquired = lock.acquire(timeout=timeout)
        
        if acquired:
            lock_file = f"{self.lock_dir}/{name}.lock"
            with open(lock_file, 'w') as f:
                f.write(json.dumps({
                    "owner": owner,
                    "acquire_time": time.time(),
                    "token": str(uuid.uuid4())
                }))
            return lock_file
        
        return None
    
    def release(self, name: str, token: str):
        """释放锁"""
        lock_file = f"{self.lock_dir}/{name}.lock"
        try:
            with open(lock_file, 'r') as f:
                data = json.load(f)
                if data.get("token") == token:
                    import os
                    os.remove(lock_file)
                    if name in self.local_locks:
                        self.local_locks[name].release()
                    return True
        except:
            pass
        return False


class RateLimiter:
    """限流器 - 令牌桶算法"""
    
    def __init__(self, rate: int, capacity: int):
        self.rate = rate  # 每秒令牌数
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
        self.lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> bool:
        """获取令牌"""
        with self.lock:
            now = time.time()
            elapsed = now - self.last_update
            self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def wait_for_tokens(self, tokens: int = 1, timeout: float = None):
        """等待令牌"""
        start = time.time()
        while True:
            if self.acquire(tokens):
                return True
            if timeout and time.time() - start >= timeout:
                return False
            time.sleep(0.1)


class CoordinationScheduler:
    """协调调度器 - 跨系统任务协调"""
    
    def __init__(self):
        self.event_bus = EventBus()
        self.api_client = APIClient()
        self.local_executor = LocalCommandExecutor()
        self.distributed_lock = DistributedLock()
        self.rate_limiter = RateLimiter(rate=10, capacity=100)
        self.tasks: Dict[str, Dict] = {}
        self.lock = threading.Lock()
    
    def register_api(self, name: str, base_url: str):
        """注册外部API"""
        with self.lock:
            self.tasks[name] = {
                "type": "api",
                "base_url": base_url,
                "client": APIClient(base_url)
            }
            logger.info(f"Registered API: {name} -> {base_url}")
    
    def register_command(self, name: str, command: str):
        """注册本地命令"""
        with self.lock:
            self.tasks[name] = {
                "type": "command",
                "command": command
            }
            logger.info(f"Registered command: {name}")
    
    def execute_task(self, name: str, params: Dict = None) -> Dict[str, Any]:
        """执行跨系统任务"""
        params = params or {}
        
        with self.lock:
            if name not in self.tasks:
                return {"success": False, "error": f"Task {name} not found"}
            
            task = self.tasks[name]
        
        # 限流
        if not self.rate_limiter.acquire():
            return {"success": False, "error": "Rate limited"}
        
        # 发布任务开始事件
        self.event_bus.publish(Event(
            event_type="task.start",
            payload={"task": name, "params": params},
            source="coordinator"
        ))
        
        result = {"task": name, "timestamp": datetime.now().isoformat()}
        
        try:
            if task["type"] == "api":
                client = task["client"]
                method = params.get("method", "GET")
                endpoint = params.get("endpoint", "/")
                data = params.get("data")
                result.update(client.request(method, endpoint, data=data))
                
            elif task["type"] == "command":
                cmd = task["command"].format(**params)
                result.update(self.local_executor.execute(cmd))
            
            # 发布任务完成事件
            self.event_bus.publish(Event(
                event_type="task.complete",
                payload={"task": name, "result": result},
                source="coordinator"
            ))
            
        except Exception as e:
            result["success"] = False
            result["error"] = str(e)
            
            # 发布任务失败事件
            self.event_bus.publish(Event(
                event_type="task.failed",
                payload={"task": name, "error": str(e)},
                source="coordinator"
            ))
        
        return result
    
    def coordinate_multi(self, tasks: List[Dict]) -> List[Dict]:
        """多任务协调执行"""
        results = []
        
        for task_spec in tasks:
            name = task_spec.get("name")
            params = task_spec.get("params", {})
            depends_on = task_spec.get("depends_on", [])
            
            # 检查依赖
            for dep in depends_on:
                dep_result = next((r for r in results if r.get("task") == dep), None)
                if not dep_result or not dep_result.get("success"):
                    results.append({
                        "task": name,
                        "success": False,
                        "error": f"Dependency {dep} failed"
                    })
                    break
            else:
                result = self.execute_task(name, params)
                results.append(result)
        
        return results


# ==================== 主类 ====================

class CrossSystemCoordinator:
    """跨系统协调器 - 整合API集成、事件总线、协调调度"""
    
    def __init__(self):
        self.api_client = APIClient()
        self.event_bus = EventBus()
        self.scheduler = CoordinationScheduler()
        self.running = False
    
    def start(self):
        """启动协调器"""
        self.event_bus.start()
        self.running = True
        logger.info("Cross-System Coordinator started")
    
    def stop(self):
        """停止协调器"""
        self.event_bus.stop()
        self.running = False
        logger.info("Cross-System Coordinator stopped")
    
    def status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self.running,
            "event_bus": {
                "subscribers": len(self.event_bus.subscribers),
                "queue_size": self.event_bus.event_queue.qsize(),
                "history_size": len(self.event_bus.event_history)
            },
            "scheduler": {
                "registered_tasks": len(self.scheduler.tasks),
                "rate_limiter": {
                    "tokens": self.scheduler.rate_limiter.tokens,
                    "capacity": self.scheduler.rate_limiter.capacity
                }
            }
        }


# ==================== CLI ====================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="跨系统协调器")
    parser.add_argument("command", choices=["start", "status", "test-api", "test-event", "test-lock"],
                       help="命令")
    parser.add_argument("--name", help="任务名称")
    parser.add_argument("--url", help="API URL")
    parser.add_argument("--event-type", help="事件类型")
    parser.add_argument("--lock", help="锁名称")
    
    args = parser.parse_args()
    
    coordinator = CrossSystemCoordinator()
    
    if args.command == "start":
        coordinator.start()
        print("Coordinator started. Press Ctrl+C to stop.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            coordinator.stop()
            
    elif args.command == "status":
        status = coordinator.status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        
    elif args.command == "test-api":
        if args.url:
            result = coordinator.api_client.get(args.url)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print("Usage: --url required")
            
    elif args.command == "test-event":
        coordinator.event_bus.start()
        
        def handler(event: Event):
            print(f"Received: {event.event_type} - {event.payload}")
        
        coordinator.event_bus.subscribe(args.event_type or "test", handler)
        coordinator.event_bus.publish(Event(
            event_type=args.event_type or "test",
            payload={"message": "Hello"},
            source="test"
        ))
        time.sleep(1)
        coordinator.event_bus.stop()
        
    elif args.command == "test-lock":
        lock_name = args.lock or "test-lock"
        token = coordinator.scheduler.distributed_lock.acquire(lock_name, "test-owner")
        if token:
            print(f"Lock acquired: {token}")
            time.sleep(2)
            coordinator.scheduler.distributed_lock.release(lock_name, token)
            print("Lock released")
        else:
            print("Failed to acquire lock")


if __name__ == "__main__":
    main()