#!/usr/bin/env python3
"""
定时健康检查与告警集成系统
第123世: 添加定时健康检查与告警集成
第125世: 集成日志记录到健康检查触发器
第123世(当前): 添加自动恢复机制到网络健康检查
"""

import json
import time
import logging
import requests
import sqlite3
import threading
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# 导入日志模块
from health_check_logger import HealthCheckLogger

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 配置
DB_PATH = "/root/.openclaw/workspace/ultron/agent_network_health.db"
ALERT_API_URL = "http://localhost:18080/alerts"
CHECK_INTERVAL = 60  # 默认60秒检查一次

# 服务配置
COLLAB_SERVICES = {
    8089: {"name": "api-gateway", "health_endpoint": "/health", "critical": True},
    8090: {"name": "secure-channel", "health_endpoint": "/health", "critical": True},
    8091: {"name": "identity-auth", "health_endpoint": "/health", "critical": True},
    8095: {"name": "collaboration-scheduler", "health_endpoint": "/health", "critical": True},
    8096: {"name": "agent-task-executor", "health_endpoint": "/health", "critical": True},
    18232: {"name": "orchestration-dashboard", "health_endpoint": "/api/orchestration/stats", "critical": False},
}


class AlertIntegration:
    """告警集成模块"""
    
    def __init__(self):
        self.alert_endpoint = ALERT_API_URL
        self.last_alert_time = {}  # 记录每个服务上次告警时间
        self.alert_cooldown = 300  # 同一服务告警冷却时间（秒）
        
    def send_alert(self, service_name: str, port: int, status: str, 
                   message: str, level: str = "WARNING") -> bool:
        """发送告警到告警系统"""
        # 检查冷却时间
        key = f"{service_name}:{port}"
        now = time.time()
        if key in self.last_alert_time:
            if now - self.last_alert_time[key] < self.alert_cooldown:
                logger.debug(f"告警冷却中: {service_name}")
                return False
        
        alert_data = {
            "rule": f"health_check:{service_name}",
            "level": level,
            "message": message,
            "metric": "network.health",
            "value": 0 if status == "down" else 1,
            "threshold": 1,
            "condition": "gte" if status == "down" else "lt",
            "timestamp": datetime.now().isoformat(),
            "service": service_name,
            "port": port,
            "status": status
        }
        
        try:
            # 尝试发送到告警API
            response = requests.post(
                self.alert_endpoint,
                json=alert_data,
                timeout=5
            )
            if response.status_code in (200, 201):
                self.last_alert_time[key] = now
                logger.info(f"✅ 告警已发送: {service_name} - {message}")
                return True
            else:
                logger.warning(f"告警API返回: {response.status_code}")
        except requests.exceptions.ConnectionError:
            logger.warning("告警API不可用，记录到本地文件")
        except Exception as e:
            logger.error(f"告警发送失败: {e}")
        
        # 备用：写入本地告警文件
        self._save_local_alert(alert_data)
        return False
    
    def _save_local_alert(self, alert_data: Dict):
        """保存到本地告警文件"""
        alert_file = Path("/root/.openclaw/workspace/ultron/alerts/health_alerts.json")
        alerts = []
        if alert_file.exists():
            try:
                alerts = json.loads(alert_file.read_text())
            except:
                alerts = []
        
        alerts.append(alert_data)
        # 保留最近100条
        alerts = alerts[-100:]
        alert_file.write_text(json.dumps(alerts, indent=2, ensure_ascii=False))
        
        # 更新冷却时间
        key = f"{alert_data['service']}:{alert_data['port']}"
        self.last_alert_time[key] = time.time()


class AutoRecovery:
    """自动恢复机制 - 检测到服务异常时自动尝试恢复"""
    
    def __init__(self):
        self.recovery_attempts = {}  # 记录每个服务的恢复尝试
        self.recovery_cooldown = 120  # 恢复尝试冷却时间（秒）
        self.max_retry = 3  # 最大重试次数
        self.recovery_log = []
        
    def get_service_manager(self, port: int) -> Optional[str]:
        """根据端口返回服务管理器类型"""
        # 映射端口到服务管理方式
        service_map = {
            8089: ("collab-api-gateway", "systemd"),
            8090: ("collab-secure-channel", "systemd"),
            8091: ("collab-identity-auth", "systemd"),
            8095: ("collab-scheduler", "systemd"),
            8096: ("collab-task-executor", "systemd"),
        }
        return service_map.get(port)
    
    def attempt_recovery(self, port: int, service_name: str) -> Dict:
        """尝试恢复服务"""
        key = f"{port}"
        now = time.time()
        
        # 检查冷却时间
        if key in self.recovery_attempts:
            last_attempt = self.recovery_attempts[key].get("last_attempt", 0)
            if now - last_attempt < self.recovery_cooldown:
                return {"action": "skipped", "reason": "cooldown", "wait_seconds": int(self.recovery_cooldown - (now - last_attempt))}
        
        # 获取服务管理信息
        service_info = self.get_service_manager(port)
        if not service_info:
            logger.info(f"端口{port}无自动恢复配置")
            return {"action": "skipped", "reason": "no_recovery_config"}
        
        service_unit, manager = service_info
        
        # 检查当前重试次数
        retry_count = self.recovery_attempts.get(key, {}).get("count", 0)
        if retry_count >= self.max_retry:
            logger.warning(f"⚠️ {service_name} 已达最大重试次数({self.max_retry}),停止自动恢复")
            return {"action": "skipped", "reason": "max_retries_exceeded"}
        
        logger.info(f"🔧 尝试自动恢复 {service_name} (端口{port})...")
        
        recovery_result = {"action": "none", "success": False, "output": ""}
        
        try:
            if manager == "systemd":
                # 尝试重启systemd服务
                result = subprocess.run(
                    ["systemctl", "restart", service_unit],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                recovery_result = {
                    "action": "systemctl_restart",
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                    "returncode": result.returncode
                }
            elif manager == "docker":
                # 尝试重启docker容器
                result = subprocess.run(
                    ["docker", "restart", service_unit],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                recovery_result = {
                    "action": "docker_restart",
                    "success": result.returncode == 0,
                    "output": result.stdout + result.stderr,
                    "returncode": result.returncode
                }
            
            # 更新恢复尝试记录
            self.recovery_attempts[key] = {
                "count": retry_count + 1,
                "last_attempt": now,
                "last_result": recovery_result
            }
            
            if recovery_result["success"]:
                logger.info(f"✅ {service_name} 恢复命令已执行")
                # 记录到恢复日志
                self.recovery_log.append({
                    "port": port,
                    "service": service_name,
                    "action": recovery_result["action"],
                    "timestamp": datetime.now().isoformat(),
                    "success": True
                })
            else:
                logger.error(f"❌ {service_name} 恢复失败: {recovery_result['output']}")
                self.recovery_log.append({
                    "port": port,
                    "service": service_name,
                    "action": recovery_result["action"],
                    "timestamp": datetime.now().isoformat(),
                    "success": False,
                    "error": recovery_result["output"]
                })
                
        except subprocess.TimeoutExpired:
            recovery_result = {"action": "timeout", "success": False, "error": "Command timeout"}
            logger.error(f"❌ {service_name} 恢复超时")
        except Exception as e:
            recovery_result = {"action": "error", "success": False, "error": str(e)}
            logger.error(f"❌ {service_name} 恢复异常: {e}")
        
        return recovery_result
    
    def get_recovery_status(self, port: int) -> Dict:
        """获取服务恢复状态"""
        key = f"{port}"
        if key in self.recovery_attempts:
            attempt = self.recovery_attempts[key]
            return {
                "retry_count": attempt.get("count", 0),
                "max_retry": self.max_retry,
                "last_attempt": datetime.fromtimestamp(attempt.get("last_attempt", 0)).isoformat() if attempt.get("last_attempt") else None,
                "cooldown_remaining": max(0, self.recovery_cooldown - (time.time() - attempt.get("last_attempt", 0)))
            }
        return {"retry_count": 0, "max_retry": self.max_retry, "cooldown_remaining": 0}
    
    def reset_recovery(self, port: int):
        """重置恢复状态（手动或成功后调用）"""
        key = f"{port}"
        if key in self.recovery_attempts:
            del self.recovery_attempts[key]


class ScheduledHealthCheck:
    """定时健康检查系统"""
    
    def __init__(self, interval: int = CHECK_INTERVAL):
        self.interval = interval
        self.alert_integration = AlertIntegration()
        self.auto_recovery = AutoRecovery()  # 自动恢复机制
        self.health_logger = HealthCheckLogger()  # 集成日志记录器
        self.running = False
        self.check_count = 0
        self.last_status = {}
        
    def check_service(self, port: int, endpoint: str) -> Dict:
        """检查单个服务健康状态"""
        url = f"http://localhost:{port}{endpoint}"
        try:
            start = time.time()
            resp = requests.get(url, timeout=5)
            response_time = (time.time() - start) * 1000
            
            try:
                data = resp.json()
                if port == 8089:
                    is_healthy = data.get("status") == "ok" or "healthy" in data
                elif port == 18232:
                    is_healthy = resp.status_code == 200
                else:
                    is_healthy = data.get("status") == "ok" or data.get("healthy") != False
            except:
                is_healthy = resp.status_code == 200
                
            return {
                "port": port,
                "status": "healthy" if is_healthy else "unhealthy",
                "response_time_ms": round(response_time, 2),
                "http_code": resp.status_code,
                "error": None
            }
        except requests.exceptions.ConnectionError:
            return {
                "port": port,
                "status": "down",
                "response_time_ms": None,
                "http_code": None,
                "error": "Connection refused"
            }
        except requests.exceptions.Timeout:
            return {
                "port": port,
                "status": "timeout",
                "response_time_ms": None,
                "http_code": None,
                "error": "Request timeout"
            }
        except Exception as e:
            return {
                "port": port,
                "status": "error",
                "response_time_ms": None,
                "http_code": None,
                "error": str(e)
            }
    
    def run_check(self) -> Dict:
        """执行一次健康检查"""
        self.check_count += 1
        results = {}
        unhealthy_services = []
        
        logger.info(f"🔍 开始第{self.check_count}次健康检查...")
        
        for port, config in COLLAB_SERVICES.items():
            result = self.check_service(port, config["health_endpoint"])
            results[port] = result
            service_name = config["name"]
            
            # 检查状态变化
            last_state = self.last_status.get(port, {}).get("status")
            current_state = result["status"]
            
            if current_state != "healthy" and current_state != last_state:
                # 状态变化：从健康变为不健康
                unhealthy_services.append((port, service_name, current_state, config.get("critical", False)))
                logger.warning(f"⚠️ {service_name} 状态变化: {last_state} -> {current_state}")
                
                # 发送告警
                level = "CRITICAL" if config.get("critical", False) else "WARNING"
                message = f"{service_name} 服务异常: {current_state}"
                if result.get("error"):
                    message += f" - {result['error']}"
                
                self.alert_integration.send_alert(
                    service_name, port, current_state, message, level
                )
                
                # 🚀 触发自动恢复（仅对critical服务）
                if config.get("critical", False) and current_state in ("down", "timeout"):
                    logger.info(f"🚀 触发自动恢复机制 for {service_name}")
                    recovery = self.auto_recovery.attempt_recovery(port, service_name)
                    status["recovery_attempts"] = status.get("recovery_attempts", [])
                    status["recovery_attempts"].append({
                        "port": port,
                        "service": service_name,
                        "recovery": recovery,
                        "timestamp": datetime.now().isoformat()
                    })
                    if recovery.get("success"):
                        message += " (已触发自动恢复)"
            
            # 记录状态
            self.last_status[port] = {
                "status": current_state,
                "timestamp": datetime.now().isoformat()
            }
        
        # 汇总
        total = len(COLLAB_SERVICES)
        healthy = sum(1 for r in results.values() if r["status"] == "healthy")
        network_health = round(healthy / total * 100, 1)
        
        status = {
            "check_count": self.check_count,
            "timestamp": datetime.now().isoformat(),
            "total_services": total,
            "healthy_services": healthy,
            "unhealthy_services": len(unhealthy_services),
            "network_health": network_health,
            "details": results
        }
        
        logger.info(f"📊 健康度: {network_health}% ({healthy}/{total})")
        
        # 保存状态
        self._save_status(status)
        
        # 记录到日志数据库
        try:
            self.health_logger.log_check(status)
            logger.info("✅ 健康检查已记录到日志数据库")
        except Exception as e:
            logger.error(f"日志记录失败: {e}")
        
        return status
    
    def _save_status(self, status: Dict):
        """保存状态到文件"""
        status_file = Path("/root/.openclaw/workspace/ultron/state/scheduled_health_check.json")
        status_file.parent.mkdir(parents=True, exist_ok=True)
        status_file.write_text(json.dumps(status, indent=2, ensure_ascii=False))
    
    def start(self):
        """启动定时健康检查"""
        self.running = True
        logger.info(f"🚀 定时健康检查已启动 (间隔: {self.interval}秒)")
        
        while self.running:
            try:
                self.run_check()
            except Exception as e:
                logger.error(f"健康检查异常: {e}")
            
            # 等待下一个周期
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)
    
    def stop(self):
        """停止定时健康检查"""
        self.running = False
        logger.info("⏹️ 定时健康检查已停止")


def run_once():
    """单次运行"""
    checker = ScheduledHealthCheck()
    status = checker.run_check()
    print(json.dumps(status, indent=2, ensure_ascii=False))
    return status


def run_daemon(interval: int = CHECK_INTERVAL):
    """守护进程模式"""
    checker = ScheduledHealthCheck(interval)
    try:
        checker.start()
    except KeyboardInterrupt:
        checker.stop()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--daemon":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else CHECK_INTERVAL
        run_daemon(interval)
    else:
        run_once()