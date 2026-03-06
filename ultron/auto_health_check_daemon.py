#!/usr/bin/env python3
"""
服务自动健康检查守护进程
功能：定期检查服务状态，自动重启故障服务
"""

import json
import time
import sqlite3
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
import logging
import socket
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

DB_PATH = "/root/.openclaw/workspace/ultron/logs/service_governance.db"
CHECK_INTERVAL = 60  # 检查间隔（秒）


class AutoHealthChecker:
    """自动健康检查器"""
    
    def __init__(self):
        self.base_dir = "/root/.openclaw/workspace/ultron"
        # 服务注册表（备用）
        self.service_registry = {
            18120: {"name": "decision-engine", "critical": True},
            18128: {"name": "decision-automation", "critical": True},
            18150: {"name": "agent-collaboration", "critical": True},
            18180: {"name": "collab-center", "critical": True},
            18210: {"name": "agent-executor", "critical": True},
            18215: {"name": "agent-network-health", "critical": True},
        }
    
    def check_port(self, port: int) -> bool:
        """检查端口是否可达"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except:
            return False
    
    def check_service(self, port: int, name: str) -> dict:
        """检查服务健康状态"""
        is_up = self.check_port(port)
        
        # 尝试健康检查端点
        health_ok = False
        try:
            req = urllib.request.Request(f"http://127.0.0.1:{port}/health")
            req.add_header('User-Agent', 'AutoHealthChecker/1.0')
            with urllib.request.urlopen(req, timeout=3) as resp:
                health_ok = resp.status == 200
        except:
            pass
        
        return {
            "port": port,
            "name": name,
            "up": is_up,
            "health_ok": health_ok,
            "checked_at": datetime.now().isoformat()
        }
    
    def restart_service(self, name: str, port: int) -> bool:
        """重启服务"""
        service_name = f"{name}.service"
        
        # 尝试通过systemd重启
        try:
            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True, timeout=30
            )
            if result.returncode == 0:
                logger.info(f"✓ Service {name} restarted successfully")
                return True
            else:
                logger.warning(f"✗ Failed to restart {name}: {result.stderr.decode()}")
        except Exception as e:
            logger.error(f"✗ Error restarting {name}: {e}")
        
        return False
    
    def check_all_registered_services(self) -> list:
        """检查所有注册服务"""
        results = []
        
        # 从治理API获取服务列表
        try:
            with urllib.request.urlopen("http://127.0.0.1:18250/services", timeout=10) as resp:
                services = json.loads(resp.read().decode())["services"]
        except Exception as e:
            logger.error(f"Failed to get services from API: {e}")
            # 使用备用列表
            services = [{"port": p, "name": info["name"], "critical": info["critical"]} 
                      for p, info in self.service_registry.items()]
        
        for svc in services:
            port = svc.get("port")
            name = svc.get("name")
            critical = svc.get("critical", 0)
            
            if not port or not name:
                continue
            
            status = self.check_service(port, name)
            results.append(status)
            
            # 如果关键服务故障，尝试重启
            if critical and not status["up"]:
                logger.warning(f"Critical service {name} (port {port}) is DOWN!")
                self.restart_service(name, port)
            
            # 如果健康检查端点失败，也记录
            if not status["health_ok"] and status["up"]:
                logger.info(f"Service {name} is up but /health endpoint not responding")
        
        return results
    
    def run(self):
        """运行健康检查循环"""
        logger.info("Auto Health Checker started")
        print("🔄 Auto Health Checker running...")
        
        while True:
            try:
                results = self.check_all_registered_services()
                
                up_count = sum(1 for r in results if r["up"])
                total = len(results)
                
                logger.info(f"Health check: {up_count}/{total} services up")
                
                # 保存检查结果
                self._save_results(results)
                
            except Exception as e:
                logger.error(f"Health check error: {e}")
            
            time.sleep(CHECK_INTERVAL)
    
    def _save_results(self, results: list):
        """保存检查结果"""
        Path("/root/.openclaw/workspace/ultron/state").mkdir(parents=True, exist_ok=True)
        
        with open("/root/.openclaw/workspace/ultron/state/auto_health_check.json", "w") as f:
            json.dump({
                "results": results,
                "timestamp": datetime.now().isoformat(),
                "up_count": sum(1 for r in results if r["up"]),
                "total": len(results)
            }, f, indent=2)


if __name__ == '__main__':
    checker = AutoHealthChecker()
    checker.run()