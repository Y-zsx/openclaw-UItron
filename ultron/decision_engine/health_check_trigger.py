#!/usr/bin/env python3
"""
网络健康检查触发器
集成到触发器管理系统的自动化健康监控
"""
import json
import logging
import sys
import os

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from trigger_manager import TriggerManager, Trigger, TriggerType, TriggerSource, TriggerCondition, TriggerAction

logger = logging.getLogger(__name__)


# 添加网络健康检查触发器
def add_network_health_trigger(manager: TriggerManager):
    """添加网络健康检查触发器"""
    
    # 创建条件评估函数
    class NetworkHealthCondition(TriggerCondition):
        def __init__(self, config):
            super().__init__("network_health", config)
            self.fail_threshold = config.get("fail_threshold", 1)
        
        def evaluate(self, context: dict) -> bool:
            # 检查是否有网络健康数据
            network_health = context.get("network_health")
            if not network_health:
                return False
            
            # 检查整体健康状态
            if not network_health.get("overall_healthy", False):
                return True
            
            # 检查关键服务
            critical_unhealthy = [
                s for s in network_health.get("services", [])
                if s.get("critical") and not s.get("healthy", False)
            ]
            
            return len(critical_unhealthy) >= self.fail_threshold
    
    # 创建执行动作
    class NetworkHealthAction(TriggerAction):
        def __init__(self, config):
            super().__init__("network_health_alert", config)
            self.alert_enabled = config.get("alert_enabled", True)
        
        def execute(self, context: dict) -> dict:
            network_health = context.get("network_health", {})
            services = network_health.get("services", [])
            connectivity = network_health.get("connectivity", {})
            
            # 收集问题
            issues = []
            
            if not connectivity.get("connected"):
                issues.append("网络连接失败")
            
            for service in services:
                if not service.get("healthy", False):
                    issues.append(f"服务 {service.get('name')} 不可用")
            
            # 构建告警消息
            message = f"🚨 网络健康告警:\n" + "\n".join(f"  - {issue}" for issue in issues)
            
            logger.warning(message)
            
            return {
                "success": True,
                "action": "network_health_alert",
                "message": message,
                "issues": issues,
                "timestamp": network_health.get("timestamp")
            }
    
    # 添加触发器
    trigger = Trigger(
        id="trigger-network-health",
        name="网络健康检查告警",
        type=TriggerType.SCHEDULE,
        source=TriggerSource.SYSTEM,
        condition=NetworkHealthCondition({
            "fail_threshold": 1
        }),
        action=NetworkHealthAction({
            "alert_enabled": True
        })
    )
    
    manager.add_trigger(trigger)
    logger.info("Added network health trigger")
    return trigger


def create_network_health_context():
    """创建网络健康检查上下文"""
    import requests
    import subprocess
    from datetime import datetime
    
    # 关键服务端点
    CRITICAL_SERVICES = [
        {"name": "Gateway", "url": "http://localhost:18789/status", "critical": True},
        {"name": "Decision Engine", "url": "http://localhost:18128/status", "critical": True},
        {"name": "Metrics API", "url": "http://localhost:8888/status", "critical": False},
    ]
    
    # 关键主机
    CRITICAL_HOSTS = ["8.8.8.8", "114.114.114.114"]
    
    # 检查服务
    service_results = []
    for service in CRITICAL_SERVICES:
        try:
            response = requests.get(service["url"], timeout=5)
            service_results.append({
                "name": service["name"],
                "healthy": response.status_code == 200,
                "status_code": response.status_code,
                "critical": service["critical"],
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            service_results.append({
                "name": service["name"],
                "healthy": False,
                "error": str(e),
                "critical": service["critical"],
                "timestamp": datetime.now().isoformat()
            })
    
    # 检查网络连接
    host_results = []
    for host in CRITICAL_HOSTS:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                capture_output=True,
                timeout=5
            )
            host_results.append({
                "host": host,
                "reachable": result.returncode == 0,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            host_results.append({
                "host": host,
                "reachable": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    connected = sum(1 for r in host_results if r.get("reachable")) > 0
    critical_healthy = all(
        s["healthy"] for s in service_results if s.get("critical")
    )
    overall_healthy = connected and critical_healthy
    
    return {
        "network_health": {
            "overall_healthy": overall_healthy,
            "connectivity": {"connected": connected, "hosts": host_results},
            "services": service_results,
            "healthy_services": sum(1 for s in service_results if s["healthy"]),
            "total_services": len(CRITICAL_SERVICES),
            "timestamp": datetime.now().isoformat()
        }
    }


def test_integration():
    """测试集成"""
    logging.basicConfig(level=logging.INFO)
    
    # 创建管理器
    manager = TriggerManager()
    
    # 添加网络健康触发器
    add_network_health_trigger(manager)
    
    # 测试正常情况
    print("\n=== 测试正常情况 ===")
    context = create_network_health_context()
    print(f"健康状态: {context['network_health']['overall_healthy']}")
    
    results = manager.check_and_trigger(context)
    print(f"触发结果: {results}")
    
    # 获取状态
    status = manager.get_status()
    print(f"\n触发器状态:")
    print(f"  - 总数: {status['total_triggers']}")
    print(f"  - 启用: {status['enabled_triggers']}")
    
    return manager, context


if __name__ == "__main__":
    manager, context = test_integration()