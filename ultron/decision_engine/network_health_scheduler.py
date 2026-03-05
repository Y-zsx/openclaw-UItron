#!/usr/bin/env python3
"""
网络健康检查调度器
定期执行网络健康检查并集成到触发器系统
"""
import json
import logging
import time
import os
import sys
from datetime import datetime
from threading import Thread, Event

# 添加决策引擎路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from trigger_manager import TriggerManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NetworkHealthScheduler:
    """网络健康检查调度器"""
    
    def __init__(self, check_interval: int = 60):
        self.check_interval = check_interval
        self.trigger_manager = TriggerManager()
        self.stop_event = Event()
        self.last_check_result = None
        
        # 导入并添加网络健康触发器
        from health_check_trigger import add_network_health_trigger
        add_network_health_trigger(self.trigger_manager)
        
    def check_network_health(self) -> dict:
        """执行网络健康检查"""
        import requests
        import subprocess
        
        CRITICAL_SERVICES = [
            {"name": "Gateway", "url": "http://localhost:18789/status", "critical": True},
            {"name": "Decision Engine", "url": "http://localhost:18128/status", "critical": True},
            {"name": "Metrics API", "url": "http://localhost:8888/status", "critical": False},
        ]
        
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
        
        result = {
            "overall_healthy": overall_healthy,
            "connectivity": {"connected": connected, "hosts": host_results},
            "services": service_results,
            "healthy_services": sum(1 for s in service_results if s["healthy"]),
            "total_services": len(CRITICAL_SERVICES),
            "timestamp": datetime.now().isoformat()
        }
        
        self.last_check_result = result
        return result
    
    def run_check(self) -> dict:
        """运行健康检查并触发相关动作"""
        logger.info("Running network health check...")
        
        # 执行健康检查
        health_data = self.check_network_health()
        
        # 构建上下文
        context = {"network_health": health_data}
        
        # 检查触发器
        triggered = self.trigger_manager.check_and_trigger(context)
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "health": health_data,
            "triggered": triggered
        }
        
        # 记录结果
        if health_data["overall_healthy"]:
            logger.info(f"Network health: OK ({health_data['healthy_services']}/{health_data['total_services']} services)")
        else:
            logger.warning(f"Network health: FAILED")
            for t in triggered:
                logger.warning(f"Triggered: {t.get('trigger_name')} - {t.get('result', {}).get('message', '')}")
        
        return result
    
    def start(self, daemon: bool = True):
        """启动调度器"""
        logger.info(f"Starting network health scheduler (interval: {self.check_interval}s)")
        
        # 立即运行一次
        self.run_check()
        
        # 启动定时循环
        while not self.stop_event.is_set():
            time.sleep(self.check_interval)
            if not self.stop_event.is_set():
                self.run_check()
    
    def stop(self):
        """停止调度器"""
        logger.info("Stopping network health scheduler")
        self.stop_event.set()
    
    def get_status(self) -> dict:
        """获取状态"""
        return {
            "last_check": self.last_check_result,
            "trigger_manager": self.trigger_manager.get_status()
        }


def run_once():
    """运行一次健康检查"""
    scheduler = NetworkHealthScheduler(check_interval=60)
    result = scheduler.run_check()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Network Health Check Scheduler")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--interval", type=int, default=60, help="Check interval in seconds")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    
    args = parser.parse_args()
    
    if args.once:
        run_once()
    else:
        scheduler = NetworkHealthScheduler(check_interval=args.interval)
        try:
            scheduler.start(daemon=args.daemon)
        except KeyboardInterrupt:
            scheduler.stop()