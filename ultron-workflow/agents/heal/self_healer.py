#!/usr/bin/env python3
"""
Agent服务异常自动治愈系统
第83世: Agent服务异常自动治愈系统
"""

import json
import time
import subprocess
import requests
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class HealthLevel(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ErrorType(Enum):
    PROCESS_CRASH = "process_crash"
    MEMORY_LEAK = "memory_leak"
    HIGH_CPU = "high_cpu"
    SERVICE_NOT_RESPONDING = "service_not_responding"
    PORT_BINDING_ERROR = "port_binding_error"
    DEPENDENCY_MISSING = "dependency_missing"
    NETWORK_ERROR = "network_error"
    DATABASE_ERROR = "database_error"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    service_name: str
    health_level: HealthLevel
    error_type: Optional[ErrorType]
    error_message: str
    last_check: str
    metrics: Dict[str, Any]
    heal_actions: List[str]


class SelfHealer:
    """Agent服务异常自动治愈系统"""
    
    # Agent服务端口映射
    AGENT_PORTS = {
        "8091": "日志聚合服务",
        "8095": "性能监控服务",
        "8100": "自动扩缩容服务",
        "8110": "接口规范服务",
        "8120": "故障预测服务",
    }
    
    # 错误类型对应的治愈策略
    HEAL_STRATEGIES = {
        ErrorType.PROCESS_CRASH: [
            "重启服务进程",
            "检查日志输出",
            "验证端口绑定"
        ],
        ErrorType.MEMORY_LEAK: [
            "强制GC回收",
            "重启服务",
            "增加内存限制"
        ],
        ErrorType.HIGH_CPU: [
            "限流降压",
            "重启服务",
            "分析热点代码"
        ],
        ErrorType.SERVICE_NOT_RESPONDING: [
            "等待服务响应",
            "重启服务",
            "检查依赖服务"
        ],
        ErrorType.PORT_BINDING_ERROR: [
            "kill占用进程",
            "更换端口",
            "等待端口释放"
        ],
        ErrorType.DEPENDENCY_MISSING: [
            "安装依赖",
            "重启服务",
            "回滚版本"
        ],
        ErrorType.NETWORK_ERROR: [
            "重试连接",
            "检查网络配置",
            "切换备用线路"
        ],
        ErrorType.DATABASE_ERROR: [
            "重连数据库",
            "检查连接池",
            "验证数据完整性"
        ]
    }
    
    def __init__(self):
        self.heal_history = []
        self.heal_rules = self._load_heal_rules()
        
    def _load_heal_rules(self) -> Dict:
        """加载治愈规则"""
        return {
            "max_restart_attempts": 3,
            "restart_interval": 30,
            "health_check_interval": 10,
            "critical_threshold": 3,
            "degraded_threshold": 2
        }
    
    def check_service_health(self, port: str, service_name: str) -> ServiceHealth:
        """检查服务健康状态"""
        try:
            # 检查端口是否监听
            result = subprocess.run(
                ["ss", "-tlnp"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            port_listening = f":{port}" in result.stdout
            
            if not port_listening:
                return ServiceHealth(
                    service_name=service_name,
                    health_level=HealthLevel.CRITICAL,
                    error_type=ErrorType.PROCESS_CRASH,
                    error_message=f"服务{port}未监听",
                    last_check=datetime.now().isoformat(),
                    metrics={},
                    heal_actions=self.HEAL_STRATEGIES[ErrorType.PROCESS_CRASH]
                )
            
            # 尝试HTTP请求
            try:
                resp = requests.get(f"http://localhost:{port}/health", timeout=5)
                if resp.status_code == 200:
                    return ServiceHealth(
                        service_name=service_name,
                        health_level=HealthLevel.HEALTHY,
                        error_type=None,
                        error_message="",
                        last_check=datetime.now().isoformat(),
                        metrics={"status_code": resp.status_code},
                        heal_actions=[]
                    )
                else:
                    return ServiceHealth(
                        service_name=service_name,
                        health_level=HealthLevel.DEGRADED,
                        error_type=ErrorType.SERVICE_NOT_RESPONDING,
                        error_message=f"HTTP {resp.status_code}",
                        last_check=datetime.now().isoformat(),
                        metrics={"status_code": resp.status_code},
                        heal_actions=self.HEAL_STRATEGIES[ErrorType.SERVICE_NOT_RESPONDING]
                    )
            except requests.exceptions.RequestException as e:
                return ServiceHealth(
                    service_name=service_name,
                    health_level=HealthLevel.DEGRADED,
                    error_type=ErrorType.SERVICE_NOT_RESPONDING,
                    error_message=str(e),
                    last_check=datetime.now().isoformat(),
                    metrics={},
                    heal_actions=self.HEAL_STRATEGIES[ErrorType.SERVICE_NOT_RESPONDING]
                )
                
        except Exception as e:
            return ServiceHealth(
                service_name=service_name,
                health_level=HealthLevel.UNKNOWN,
                error_type=ErrorType.UNKNOWN,
                error_message=str(e),
                last_check=datetime.now().isoformat(),
                metrics={},
                heal_actions=[]
            )
    
    def check_all_services(self) -> Dict[str, ServiceHealth]:
        """检查所有Agent服务"""
        results = {}
        for port, name in self.AGENT_PORTS.items():
            results[port] = self.check_service_health(port, name)
            logger.info(f"检查 {name}({port}): {results[port].health_level.value}")
        return results
    
    def diagnose_error(self, health: ServiceHealth) -> ErrorType:
        """诊断错误类型"""
        if health.error_type:
            return health.error_type
        return ErrorType.UNKNOWN
    
    def execute_heal(self, health: ServiceHealth) -> bool:
        """执行治愈操作"""
        if health.health_level == HealthLevel.HEALTHY:
            logger.info(f"{health.service_name} 健康，无需治愈")
            return True
        
        error_type = self.diagnose_error(health)
        strategies = self.HEAL_STRATEGIES.get(error_type, ["手动干预"])
        
        logger.warning(f"{health.service_name} 异常: {error_type.value}")
        logger.info(f"执行治愈策略: {strategies}")
        
        # 记录治愈历史
        heal_record = {
            "timestamp": datetime.now().isoformat(),
            "service": health.service_name,
            "error_type": error_type.value,
            "strategies": strategies,
            "status": "applied"
        }
        self.heal_history.append(heal_record)
        
        # 这里可以实现具体的治愈逻辑
        # 例如：重启服务、清理缓存、重连网络等
        
        return True
    
    def verify_recovery(self, port: str, service_name: str) -> bool:
        """验证服务恢复"""
        time.sleep(2)
        health = self.check_service_health(port, service_name)
        return health.health_level == HealthLevel.HEALTHY
    
    def run_healing_cycle(self) -> Dict:
        """运行一个完整的治愈周期"""
        logger.info("=" * 50)
        logger.info("开始Agent服务异常自动治愈系统")
        logger.info("=" * 50)
        
        # 1. 检查所有服务
        services = self.check_all_services()
        
        # 2. 找出异常服务
        unhealthy = {k: v for k, v in services.items() 
                    if v.health_level != HealthLevel.HEALTHY}
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_services": len(services),
            "healthy": len(services) - len(unhealthy),
            "unhealthy": len(unhealthy),
            "healed": []
        }
        
        # 3. 对异常服务执行治愈
        for port, health in unhealthy.items():
            logger.info(f"治愈服务: {health.service_name}")
            heal_success = self.execute_heal(health)
            
            if heal_success:
                # 4. 验证恢复
                recovered = self.verify_recovery(port, health.service_name)
                results["healed"].append({
                    "service": health.service_name,
                    "port": port,
                    "recovered": recovered
                })
                logger.info(f"{health.service_name} 恢复状态: {recovered}")
        
        logger.info(f"治愈周期完成: {results}")
        return results


if __name__ == "__main__":
    healer = SelfHealer()
    result = healer.run_healing_cycle()
    print(json.dumps(result, indent=2, ensure_ascii=False))