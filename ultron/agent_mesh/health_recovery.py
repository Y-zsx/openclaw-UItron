"""
Agent服务健康检测与自动故障恢复
第49世: 实现健康检测与自动故障恢复
"""
import asyncio
import time
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class RecoveryAction(Enum):
    NONE = "none"
    RESTART = "restart"
    REPLACE = "replace"
    SCALE_UP = "scale_up"
    FAILOVER = "failover"
    NOTIFY = "notify"


@dataclass
class HealthCheckConfig:
    """健康检查配置"""
    check_interval: float = 30.0  # 秒
    timeout: float = 5.0
    failure_threshold: int = 3  # 连续失败次数触发不健康
    success_threshold: int = 2  # 连续成功次数恢复健康
    slow_threshold: float = 2.0  # 响应时间阈值(秒)
    enabled: bool = True


@dataclass
class ServiceHealth:
    """服务健康状态"""
    service_id: str
    status: HealthStatus = HealthStatus.UNKNOWN
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_check_time: float = 0
    last_response_time: float = 0
    last_error: Optional[str] = None
    check_count: int = 0
    healthy_count: int = 0
    metadata: Dict = field(default_factory=dict)


@dataclass
class RecoveryConfig:
    """故障恢复配置"""
    auto_recovery: bool = True
    max_retry: int = 3
    retry_interval: float = 10.0
    failover_enabled: bool = True
    restart_enabled: bool = True
    notification_enabled: bool = True


class HealthChecker:
    """健康检查器基类"""
    
    async def check(self, service_id: str) -> tuple[bool, float, Optional[str]]:
        """执行健康检查, 返回(is_healthy, response_time, error_msg)"""
        raise NotImplementedError


class HTTPHealthChecker(HealthChecker):
    """HTTP健康检查"""
    
    def __init__(self, endpoint: str, method: str = "GET", headers: Dict = None):
        self.endpoint = endpoint
        self.method = method
        self.headers = headers or {}
    
    async def check(self, service_id: str) -> tuple[bool, float, Optional[str]]:
        import aiohttp
        start = time.time()
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(
                    self.method, self.endpoint,
                    headers=self.headers, timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    response_time = time.time() - start
                    is_healthy = resp.status < 500
                    error = None if is_healthy else f"HTTP {resp.status}"
                    return is_healthy, response_time, error
        except Exception as e:
            return False, time.time() - start, str(e)


class TCPHealthChecker(HealthChecker):
    """TCP端口健康检查"""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
    
    async def check(self, service_id: str) -> tuple[bool, float, Optional[str]]:
        start = time.time()
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port),
                timeout=5.0
            )
            writer.close()
            await writer.wait_closed()
            return True, time.time() - start, None
        except Exception as e:
            return False, time.time() - start, str(e)


class PingHealthChecker(HealthChecker):
    """Ping健康检查"""
    
    def __init__(self, host: str):
        self.host = host
    
    async def check(self, service_id: str) -> tuple[bool, float, Optional[str]]:
        import subprocess
        start = time.time()
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", self.host],
                capture_output=True, timeout=5
            )
            return result.returncode == 0, time.time() - start, None
        except Exception as e:
            return False, time.time() - start, str(e)


class HealthMonitor:
    """服务健康监控与自动故障恢复"""
    
    def __init__(self, config: HealthCheckConfig = None, recovery_config: RecoveryConfig = None):
        self.config = config or HealthCheckConfig()
        self.recovery_config = recovery_config or RecoveryConfig()
        self.services: Dict[str, ServiceHealth] = {}
        self.checkers: Dict[str, HealthChecker] = {}
        self.callbacks: Dict[str, List[Callable]] = {
            "status_change": [],
            "recovery": [],
            "failure": []
        }
        self._running = False
        self._task: Optional[asyncio.Task] = None
    
    def register_service(self, service_id: str, checker: HealthChecker, metadata: Dict = None):
        """注册服务进行健康检查"""
        self.services[service_id] = ServiceHealth(
            service_id=service_id,
            metadata=metadata or {}
        )
        self.checkers[service_id] = checker
        logger.info(f"注册服务健康检查: {service_id}")
    
    def unregister_service(self, service_id: str):
        """注销服务"""
        self.services.pop(service_id, None)
        self.checkers.pop(service_id, None)
        logger.info(f"注销服务: {service_id}")
    
    def on_status_change(self, callback: Callable):
        """状态变更回调"""
        self.callbacks["status_change"].append(callback)
    
    def on_recovery(self, callback: Callable):
        """恢复回调"""
        self.callbacks["recovery"].append(callback)
    
    def on_failure(self, callback: Callable):
        """故障回调"""
        self.callbacks["failure"].append(callback)
    
    async def _check_service(self, service_id: str) -> ServiceHealth:
        """检查单个服务"""
        health = self.services.get(service_id)
        checker = self.checkers.get(service_id)
        
        if not health or not checker:
            return None
        
        try:
            is_healthy, response_time, error = await checker.check(service_id)
            health.last_check_time = time.time()
            health.last_response_time = response_time
            health.last_error = error
            health.check_count += 1
            
            # 状态转换逻辑
            old_status = health.status
            
            if is_healthy and response_time < self.config.slow_threshold:
                health.consecutive_successes += 1
                health.consecutive_failures = 0
                health.healthy_count += 1
                
                if health.consecutive_successes >= self.config.success_threshold:
                    health.status = HealthStatus.HEALTHY
                elif health.status != HealthStatus.HEALTHY:
                    health.status = HealthStatus.DEGRADED
            else:
                health.consecutive_failures += 1
                health.consecutive_successes = 0
                
                if health.consecutive_failures >= self.config.failure_threshold:
                    health.status = HealthStatus.UNHEALTHY
                else:
                    health.status = HealthStatus.DEGRADED
            
            # 触发回调
            if old_status != health.status:
                logger.warning(f"服务 {service_id} 状态变更: {old_status.value} -> {health.status.value}")
                for cb in self.callbacks["status_change"]:
                    try:
                        await cb(service_id, old_status, health.status)
                    except Exception as e:
                        logger.error(f"状态变更回调失败: {e}")
                
                if old_status == HealthStatus.UNHEALTHY and health.status != HealthStatus.UNHEALTHY:
                    for cb in self.callbacks["recovery"]:
                        try:
                            await cb(service_id, health)
                        except Exception as e:
                            logger.error(f"恢复回调失败: {e}")
                
                if health.status == HealthStatus.UNHEALTHY:
                    for cb in self.callbacks["failure"]:
                        try:
                            await cb(service_id, health)
                        except Exception as e:
                            logger.error(f"故障回调失败: {e}")
                    
                    if self.recovery_config.auto_recovery:
                        await self._trigger_recovery(service_id, health)
            
            return health
            
        except Exception as e:
            logger.error(f"健康检查异常 {service_id}: {e}")
            health.last_error = str(e)
            return health
    
    async def _trigger_recovery(self, service_id: str, health: ServiceHealth):
        """触发故障恢复"""
        logger.warning(f"触发故障恢复: {service_id}")
        
        action = RecoveryAction.NONE
        
        # 根据配置决定恢复动作
        if self.recovery_config.failover_enabled:
            action = RecoveryAction.FAILOVER
        elif self.recovery_config.restart_enabled:
            action = RecoveryAction.RESTART
        
        if action != RecoveryAction.NONE:
            logger.info(f"执行恢复动作: {service_id} -> {action.value}")
            
            for cb in self.callbacks["recovery"]:
                try:
                    await cb(service_id, health, action)
                except Exception as e:
                    logger.error(f"恢复执行回调失败: {e}")
    
    async def _monitor_loop(self):
        """监控循环"""
        while self._running:
            try:
                tasks = [
                    self._check_service(sid) 
                    for sid in self.services.keys()
                ]
                if tasks:
                    await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"监控循环异常: {e}")
            
            await asyncio.sleep(self.config.check_interval)
    
    async def start(self):
        """启动监控"""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("健康监控已启动")
    
    async def stop(self):
        """停止监控"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("健康监控已停止")
    
    def get_health(self, service_id: str) -> Optional[ServiceHealth]:
        """获取服务健康状态"""
        return self.services.get(service_id)
    
    def get_all_health(self) -> Dict[str, ServiceHealth]:
        """获取所有服务健康状态"""
        return self.services.copy()
    
    def get_unhealthy_services(self) -> List[str]:
        """获取不健康服务列表"""
        return [
            sid for sid, h in self.services.items()
            if h.status == HealthStatus.UNHEALTHY
        ]
    
    def get_health_summary(self) -> Dict:
        """获取健康汇总"""
        total = len(self.services)
        healthy = sum(1 for h in self.services.values() if h.status == HealthStatus.HEALTHY)
        degraded = sum(1 for h in self.services.values() if h.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for h in self.services.values() if h.status == HealthStatus.UNHEALTHY)
        
        return {
            "total": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy,
            "health_rate": healthy / total if total > 0 else 0,
            "services": {
                sid: {"status": h.status.value, "last_check": h.last_check_time}
                for sid, h in self.services.items()
            }
        }


# 演示
async def demo():
    print("=" * 60)
    print("Agent服务健康检测与自动故障恢复 - 演示")
    print("=" * 60)
    
    # 创建监控器
    monitor = HealthMonitor(
        config=HealthCheckConfig(check_interval=5, failure_threshold=2, success_threshold=1),
        recovery_config=RecoveryConfig(auto_recovery=True, failover_enabled=True)
    )
    
    # 注册状态变更回调 (async)
    async def status_callback(sid, old, new):
        print(f"  [回调] {sid}: {old.value} -> {new.value}")
    monitor.on_status_change(status_callback)
    
    # 注册服务
    monitor.register_service("api-gateway", HTTPHealthChecker("http://httpbin.org/status/200"))
    monitor.register_service("user-service", HTTPHealthChecker("http://httpbin.org/delay/1"))
    monitor.register_service("db-primary", TCPHealthChecker("127.0.0.1", 3306))
    
    # 启动监控
    await monitor.start()
    
    # 模拟运行
    for i in range(3):
        await asyncio.sleep(3)
        summary = monitor.get_health_summary()
        print(f"\n轮次 {i+1}:")
        print(f"  健康率: {summary['health_rate']:.1%}")
        print(f"  状态: healthy={summary['healthy']}, degraded={summary['degraded']}, unhealthy={summary['unhealthy']}")
        for sid, info in summary['services'].items():
            print(f"    {sid}: {info['status']}")
    
    await monitor.stop()
    print("\n演示完成!")


if __name__ == "__main__":
    asyncio.run(demo())
