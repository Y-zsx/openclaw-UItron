#!/usr/bin/env python3
"""
网络健康检查触发器
集成到决策引擎的智能网络监控
"""
import json
import logging
import requests
import subprocess
from datetime import datetime
from typing import Dict, List, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 关键服务端点
CRITICAL_SERVICES = [
    {"name": "Gateway", "url": "http://localhost:18789/status", "critical": True},
    {"name": "Decision Engine", "url": "http://localhost:18128/status", "critical": True},
    {"name": "Metrics API", "url": "http://localhost:8888/status", "critical": False},
]

# 关键主机
CRITICAL_HOSTS = [
    "8.8.8.8",        # Google DNS
    "114.114.114.114", # 114 DNS
]


def check_service_health(service: Dict) -> Dict:
    """检查服务健康状态"""
    try:
        response = requests.get(service["url"], timeout=5)
        is_healthy = response.status_code == 200
        return {
            "name": service["name"],
            "healthy": is_healthy,
            "status_code": response.status_code,
            "critical": service["critical"],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "name": service["name"],
            "healthy": False,
            "error": str(e),
            "critical": service["critical"],
            "timestamp": datetime.now().isoformat()
        }


def check_network_connectivity() -> Dict:
    """检查网络连接"""
    results = []
    for host in CRITICAL_HOSTS:
        try:
            result = subprocess.run(
                ["ping", "-c", "1", "-W", "2", host],
                capture_output=True,
                timeout=5
            )
            reachable = result.returncode == 0
            results.append({
                "host": host,
                "reachable": reachable,
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            results.append({
                "host": host,
                "reachable": False,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            })
    
    connected = sum(1 for r in results if r.get("reachable")) > 0
    return {"connected": connected, "hosts": results}


def get_network_health_status() -> Dict:
    """获取网络健康状态"""
    # 检查服务
    service_results = [check_service_health(s) for s in CRITICAL_SERVICES]
    
    # 检查网络连接
    connectivity = check_network_connectivity()
    
    # 判断整体状态
    healthy_services = sum(1 for s in service_results if s["healthy"])
    critical_healthy = all(
        s["healthy"] for s in service_results if s.get("critical")
    )
    
    overall_healthy = connectivity["connected"] and critical_healthy
    
    return {
        "overall_healthy": overall_healthy,
        "connectivity": connectivity,
        "services": service_results,
        "healthy_services": healthy_services,
        "total_services": len(CRITICAL_SERVICES),
        "timestamp": datetime.now().isoformat()
    }


def run_health_check() -> Dict:
    """运行健康检查"""
    status = get_network_health_status()
    
    # 记录日志
    if status["overall_healthy"]:
        logger.info("Network health check: OK")
    else:
        logger.warning(f"Network health check: FAILED - {status}")
    
    return status


if __name__ == "__main__":
    result = run_health_check()
    print(json.dumps(result, indent=2, ensure_ascii=False))