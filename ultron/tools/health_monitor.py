#!/usr/bin/env python3
"""
Agent服务健康检测与自动故障恢复系统
功能：
- 多维度健康检测 (端口/API/资源/响应时间)
- 故障自动恢复 (重启/切换/回滚)
- 告警通知 (钉钉/日志)
- 健康历史与统计
"""

import asyncio
import json
import time
import subprocess
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import os

class HealthStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ServiceEndpoint:
    name: str
    port: int
    health_check_path: str = "/health"
    process_name: str = ""
    restart_command: str = ""
    dependencies: List[str] = field(default_factory=list)
    max_response_time: float = 2.0
    max_failures: int = 3
    check_interval: int = 30

@dataclass
class HealthCheckResult:
    service: str
    status: HealthStatus
    response_time: float
    timestamp: str
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)

class AlertManager:
    """告警管理器"""
    def __init__(self):
        self.alerts: List[Dict] = []
        self.alert_callbacks: List[Callable] = []
    
    def add_alert(self, level: str, service: str, message: str):
        alert = {
            "level": level,
            "service": service,
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        self.alerts.append(alert)
        # 保留最近100条告警
        if len(self.alerts) > 100:
            self.alerts = self.alerts[-100:]
        
        # 触发回调
        for cb in self.alert_callbacks:
            try:
                cb(alert)
            except Exception as e:
                print(f"Alert callback error: {e}")
    
    def register_callback(self, callback: Callable):
        self.alert_callbacks.append(callback)

class FaultRecovery:
    """故障恢复"""
    def __init__(self):
        self.recovery_actions: Dict[str, List[Dict]] = {}
    
    async def restart_service(self, service: ServiceEndpoint) -> bool:
        """重启服务"""
        if not service.restart_command:
            return False
        
        try:
            # 查找并终止进程
            if service.process_name:
                subprocess.run(f"pkill -f '{service.process_name}'", 
                             shell=True, capture_output=True)
                await asyncio.sleep(2)
            
            # 启动服务
            subprocess.Popen(service.restart_command, shell=True)
            return True
        except Exception as e:
            print(f"Restart failed: {e}")
            return False
    
    async def recover(self, service: ServiceEndpoint, failure_count: int) -> bool:
        """执行恢复"""
        if failure_count >= service.max_failures:
            return await self.restart_service(service)
        return False

class HealthMonitor:
    """健康检测核心"""
    def __init__(self, data_dir: str = "/root/.openclaw/workspace/ultron/data"):
        self.services: Dict[str, ServiceEndpoint] = {}
        self.health_history: Dict[str, List[HealthCheckResult]] = {}
        self.failure_count: Dict[str, int] = {}
        self.alert_manager = AlertManager()
        self.fault_recovery = FaultRecovery()
        self.running = False
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)
        
    def add_service(self, service: ServiceEndpoint):
        self.services[service.name] = service
        self.health_history[service.name] = []
        self.failure_count[service.name] = 0
    
    async def check_service(self, service: ServiceEndpoint) -> HealthCheckResult:
        """检测单个服务"""
        start = time.time()
        url = f"http://localhost:{service.port}{service.health_check_path}"
        
        try:
            resp = requests.get(url, timeout=service.max_response_time)
            response_time = time.time() - start
            
            if resp.status_code == 200:
                status = HealthStatus.HEALTHY
                self.failure_count[service.name] = 0
            else:
                status = HealthStatus.DEGRADED
                self.failure_count[service.name] += 1
                
        except requests.exceptions.Timeout:
            response_time = time.time() - start
            status = HealthStatus.UNHEALTHY
            self.failure_count[service.name] += 1
            error = "Timeout"
        except requests.exceptions.ConnectionError:
            response_time = time.time() - start
            status = HealthStatus.UNHEALTHY
            self.failure_count[service.name] += 1
            error = "Connection refused"
        except Exception as e:
            response_time = time.time() - start
            status = HealthStatus.UNHEALTHY
            self.failure_count[service.name] += 1
            error = str(e)
        
        result = HealthCheckResult(
            service=service.name,
            status=status,
            response_time=response_time,
            timestamp=datetime.now().isoformat(),
            error=error if status != HealthStatus.HEALTHY else None,
            details={"port": service.port, "url": url}
        )
        
        # 记录历史
        self.health_history[service.name].append(result)
        if len(self.health_history[service.name]) > 1000:
            self.health_history[service.name] = self.health_history[service.name][-1000:]
        
        # 检查失败告警
        if self.failure_count[service.name] > 0 and self.failure_count[service.name] % service.max_failures == 0:
            self.alert_manager.add_alert(
                "critical", 
                service.name, 
                f"连续{self.failure_count[service.name]}次检测失败"
            )
        
        return result
    
    async def check_all(self) -> Dict[str, HealthCheckResult]:
        """检测所有服务"""
        results = {}
        tasks = [self.check_service(s) for s in self.services.values()]
        results_list = await asyncio.gather(*tasks)
        for r in results_list:
            results[r.service] = r
        return results
    
    async def auto_recover(self):
        """自动故障恢复"""
        for name, count in self.failure_count.items():
            if count >= self.services[name].max_failures:
                service = self.services[name]
                self.alert_manager.add_alert(
                    "warning",
                    name,
                    f"触发自动恢复 (失败{count}次)"
                )
                success = await self.fault_recovery.recover(service, count)
                if success:
                    self.failure_count[name] = 0
                    self.alert_manager.add_alert(
                        "info",
                        name,
                        "自动恢复成功"
                    )
    
    async def monitor_loop(self):
        """监控循环"""
        while self.running:
            try:
                await self.check_all()
                await self.auto_recover()
                await asyncio.sleep(30)  # 默认30秒检测一次
            except Exception as e:
                print(f"Monitor loop error: {e}")
                await asyncio.sleep(5)
    
    def start(self):
        self.running = True
    
    def stop(self):
        self.running = False
    
    def get_system_resources(self) -> Dict:
        """获取系统资源使用情况"""
        try:
            # CPU使用率
            cpu_cmd = "top -bn1 | grep 'Cpu(s)' | awk '{print $2}' | cut -d'%' -f1"
            cpu_result = subprocess.run(cpu_cmd, shell=True, capture_output=True, text=True)
            cpu_usage = float(cpu_result.stdout.strip()) if cpu_result.stdout.strip() else 0
            
            # 内存使用率
            mem_cmd = "free | grep Mem | awk '{printf \"%.1f\", $3/$2 * 100}'"
            mem_result = subprocess.run(mem_cmd, shell=True, capture_output=True, text=True)
            mem_usage = float(mem_result.stdout.strip()) if mem_result.stdout.strip() else 0
            
            # 磁盘使用率
            disk_cmd = "df -h / | tail -1 | awk '{print $5}' | cut -d'%' -f1"
            disk_result = subprocess.run(disk_cmd, shell=True, capture_output=True, text=True)
            disk_usage = float(disk_result.stdout.strip()) if disk_result.stdout.strip() else 0
            
            # 负载平均值
            load_cmd = "uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | cut -d',' -f1"
            load_result = subprocess.run(load_cmd, shell=True, capture_output=True, text=True)
            load_avg = float(load_result.stdout.strip()) if load_result.stdout.strip() else 0
            
            return {
                "cpu": cpu_usage,
                "memory": mem_usage,
                "disk": disk_usage,
                "load": load_avg
            }
        except Exception as e:
            return {"cpu": 0, "memory": 0, "disk": 0, "load": 0, "error": str(e)}
    
    def get_status(self) -> Dict:
        """获取状态"""
        latest = {}
        for name, history in self.health_history.items():
            if history:
                latest[name] = {
                    "status": history[-1].status.value,
                    "response_time": history[-1].response_time,
                    "timestamp": history[-1].timestamp,
                    "failure_count": self.failure_count.get(name, 0)
                }
            else:
                latest[name] = {"status": "unknown", "failure_count": 0}
        return {
            "services": latest,
            "alerts": self.alert_manager.alerts[-10:],
            "timestamp": datetime.now().isoformat(),
            "health": self.get_system_resources()
        }

# 全局实例
_monitor: Optional[HealthMonitor] = None

def get_monitor() -> HealthMonitor:
    global _monitor
    if _monitor is None:
        _monitor = HealthMonitor()
        # 默认注册已知服务 - 包含自动恢复配置
        _monitor.add_service(ServiceEndpoint(
            name="api-gateway",
            port=8090,
            health_check_path="/health",
            process_name="agent_api_gateway",
            restart_command="cd /root/.openclaw/workspace/ultron && python3 -c 'import asyncio; from tools.agent_api_gateway import AgentAPIGateway; asyncio.run(AgentAPIGateway().start())'",
            max_response_time=1.0,
            max_failures=3
        ))
        _monitor.add_service(ServiceEndpoint(
            name="service-mesh",
            port=8094,
            health_check_path="/health",
            process_name="service_mesh_api.py",
            restart_command="cd /root/.openclaw/workspace/ultron/agents && python3 service_mesh_api.py",
            max_response_time=1.5,
            max_failures=3
        ))
        _monitor.add_service(ServiceEndpoint(
            name="agent-deployer",
            port=8096,
            health_check_path="/health",
            process_name="agent_deployer.py",
            restart_command="cd /root/.openclaw/workspace/ultron/tools && python3 agent_deployer.py",
            max_response_time=2.0,
            max_failures=3
        ))
        _monitor.add_service(ServiceEndpoint(
            name="agent-orchestrator",
            port=8097,
            health_check_path="/health",
            process_name="agent_orchestrator.py",
            restart_command="cd /root/.openclaw/workspace/ultron/tools && python3 agent_orchestrator.py",
            max_response_time=2.0,
            max_failures=3
        ))
        # 新增: workflow engine
        _monitor.add_service(ServiceEndpoint(
            name="workflow-engine",
            port=8099,
            health_check_path="/health",
            process_name="workflow_api.py",
            restart_command="cd /root/.openclaw/workspace/ultron/tools && python3 workflow_api.py",
            max_response_time=2.0,
            max_failures=3
        ))
    return _monitor

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: health_monitor.py [start|status|add|check]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    monitor = get_monitor()
    
    if cmd == "start":
        monitor.start()
        print("Health monitor started")
        asyncio.run(monitor.monitor_loop())
    elif cmd == "status":
        print(json.dumps(monitor.get_status(), indent=2, ensure_ascii=False))
    elif cmd == "check":
        result = asyncio.run(monitor.check_all())
        print(json.dumps({k: {"status": v.status.value, "response_time": v.response_time} 
                        for k, v in result.items()}, indent=2))
    elif cmd == "add":
        # python health_monitor.py add <name> <port>
        if len(sys.argv) >= 4:
            monitor.add_service(ServiceEndpoint(
                name=sys.argv[2],
                port=int(sys.argv[3])
            ))
            print(f"Added service: {sys.argv[2]}")