#!/usr/bin/env python3
"""
Agent协作网络健康检查与自动恢复系统
第35世: 健康检查与自动恢复机制
"""

import requests
import sqlite3
import json
import time
import subprocess
from datetime import datetime
from typing import Dict, List, Optional
import os

# 数据库路径
DB_PATH = "/root/.openclaw/workspace/ultron/agent_network_health.db"
LOG_FILE = "/root/.openclaw/workspace/ultron/logs/network_health.log"

# Agent协作网络核心服务
COLLAB_SERVICES = {
    8089: {"name": "api-gateway", "health_endpoint": "/health", "critical": True},
    8090: {"name": "secure-channel", "health_endpoint": "/health", "critical": True},
    8091: {"name": "identity-auth", "health_endpoint": "/health", "critical": True},
    8095: {"name": "collaboration-scheduler", "health_endpoint": "/health", "critical": True},
    8096: {"name": "agent-task-executor", "health_endpoint": "/health", "critical": True},
    18232: {"name": "orchestration-dashboard", "health_endpoint": "/api/orchestration/stats", "critical": False},
}

# systemd服务映射
SYSTEMD_SERVICES = {
    8089: "agent-service-mesh.service",
    8091: "identity-auth-api.service",
    8095: "agent-lifecycle-api.service",  # 使用lifecycle API作为scheduler
    8096: "agent-task-executor.service",
    18232: "orchestration-api.service",
}

def init_db():
    """初始化健康检查数据库"""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS health_checks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        service_port INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        status TEXT NOT NULL,
        response_time_ms REAL,
        error_message TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS auto_recovery (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        service_port INTEGER NOT NULL,
        service_name TEXT NOT NULL,
        action TEXT NOT NULL,
        result TEXT NOT NULL
    )''')
    conn.commit()
    conn.close()

def check_service(port: int, endpoint: str) -> Dict:
    """检查单个服务健康状态"""
    start = time.time()
    url = f"http://localhost:{port}{endpoint}"
    try:
        resp = requests.get(url, timeout=5)
        response_time = (time.time() - start) * 1000
        
        # 解析响应判断健康状态
        try:
            data = resp.json()
            # API网关返回healthy=false表示没有agent注册，这是正常的"空闲"状态
            # orchestration-dashboard是静态HTML，也返回200
            if port == 8089:
                is_healthy = data.get("status") == "ok" or "healthy" in data  # 任何响应都是正常的
            elif port == 18232:
                is_healthy = resp.status_code == 200  # HTML页面也算健康
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

def restart_service(service_name: str) -> bool:
    """尝试通过systemd重启服务"""
    try:
        result = subprocess.run(
            ["systemctl", "restart", service_name],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        return False

def auto_recover(port: int, service_name: str) -> Dict:
    """尝试自动恢复服务"""
    result = {
        "port": port,
        "service_name": service_name,
        "action": None,
        "success": False,
        "message": ""
    }
    
    # 尝试通过systemd重启
    systemd_name = SYSTEMD_SERVICES.get(port)
    if systemd_name:
        result["action"] = f"systemctl restart {systemd_name}"
        result["success"] = restart_service(systemd_name)
        result["message"] = "Service restarted" if result["success"] else "Restart failed"
    else:
        result["message"] = "No systemd service mapping"
        
    return result

def log_health_check(check_result: Dict):
    """记录健康检查结果"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO health_checks 
        (timestamp, service_port, service_name, status, response_time_ms, error_message)
        VALUES (?, ?, ?, ?, ?, ?)''',
        (datetime.utcnow().isoformat(),
         check_result["port"],
         COLLAB_SERVICES[check_result["port"]]["name"],
         check_result["status"],
         check_result["response_time_ms"],
         check_result.get("error")))
    conn.commit()
    conn.close()

def log_recovery(recovery_result: Dict):
    """记录恢复操作"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO auto_recovery 
        (timestamp, service_port, service_name, action, result)
        VALUES (?, ?, ?, ?, ?)''',
        (datetime.utcnow().isoformat(),
         recovery_result["port"],
         recovery_result["service_name"],
         recovery_result["action"],
         json.dumps(recovery_result)))
    conn.commit()
    conn.close()

def get_network_status() -> Dict:
    """获取整个协作网络状态"""
    results = {}
    unhealthy_services = []
    recovered = []
    
    for port, config in COLLAB_SERVICES.items():
        result = check_service(port, config["health_endpoint"])
        results[port] = result
        log_health_check(result)
        
        if result["status"] != "healthy":
            unhealthy_services.append((port, config["name"], config.get("critical", False)))
            
            # 对关键服务尝试自动恢复
            if config.get("critical", False):
                recovery = auto_recover(port, config["name"])
                log_recovery(recovery)
                if recovery["success"]:
                    # 等待后重新检查
                    time.sleep(3)
                    recheck = check_service(port, config["health_endpoint"])
                    if recheck["status"] == "healthy":
                        recovered.append(port)
    
    # 汇总状态
    total = len(COLLAB_SERVICES)
    healthy = total - len(unhealthy_services)
    
    return {
        "timestamp": datetime.utcnow().isoformat(),
        "total_services": total,
        "healthy_services": healthy,
        "unhealthy_services": len(unhealthy_services),
        "recovered": recovered,
        "details": results,
        "network_health": round(healthy / total * 100, 1)
    }

def main():
    """主函数"""
    init_db()
    
    print("=" * 60)
    print("Agent协作网络健康检查")
    print("=" * 60)
    
    status = get_network_status()
    
    print(f"\n⏰ 检查时间: {status['timestamp']}")
    print(f"📊 网络健康度: {status['network_health']}%")
    print(f"✅ 健康服务: {status['healthy_services']}/{status['total_services']}")
    
    if status['unhealthy_services'] > 0:
        print(f"\n⚠️ 问题服务:")
        for port, name, critical in [(p, COLLAB_SERVICES[p]["name"], COLLAB_SERVICES[p].get("critical")) for p in status['details'] if status['details'][p]['status'] != 'healthy']:
            print(f"  - {name} (端口{port}) - {'关键' if critical else '非关键'}")
    
    if status['recovered']:
        print(f"\n🔧 已自动恢复: {status['recovered']}")
    
    print("\n详细状态:")
    for port, result in status['details'].items():
        name = COLLAB_SERVICES[port]["name"]
        emoji = "✅" if result["status"] == "healthy" else "❌"
        rt = result.get("response_time_ms", "N/A")
        print(f"  {emoji} {name}: {result['status']} ({rt}ms)")
    
    print("=" * 60)
    
    # 保存状态到文件
    with open("/root/.openclaw/workspace/ultron/state/network_health.json", "w") as f:
        json.dump(status, f, indent=2)
    
    return status

if __name__ == "__main__":
    main()