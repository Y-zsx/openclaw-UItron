#!/usr/bin/env python3
"""
批量运维操作 - Batch Ops Runner
支持批量启动/停止/重启服务
"""

import os
import sys
import subprocess
import signal
from pathlib import Path

TOOLS_DIR = Path("/root/.openclaw/workspace/ultron/tools")

SERVICES = {
    "health-api": {
        "script": "agent_health_integration.py",
        "port": 18210,
        "description": "Agent健康API",
    },
    "self-healing": {
        "script": "self_healing_api.py",
        "port": 18227,
        "description": "自愈系统API",
    },
    "integration-test": {
        "script": "integration_tester.py",
        "port": 18228,
        "description": "集成测试API",
    },
    "system-summary": {
        "script": "system_summary_api.py",
        "port": 18225,
        "description": "系统摘要API",
    },
    "scheduler-analyzer": {
        "script": "scheduler_log_analyzer.py",
        "port": 18229,
        "description": "调度器日志分析",
    },
}

def find_pid(port):
    """通过端口查找进程PID"""
    try:
        result = subprocess.run(
            ["lsof", "-i", f":{port}", "-t"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return int(result.stdout.strip())
    except:
        pass
    return None

def start_service(name, service_info):
    """启动服务"""
    script = service_info["script"]
    script_path = TOOLS_DIR / script
    
    if not script_path.exists():
        print(f"❌ 脚本不存在: {script}")
        return False
    
    # 检查是否已运行
    port = service_info["port"]
    if find_pid(port):
        print(f"⏭️  服务 {name} 已在运行 (端口 {port})")
        return True
    
    print(f"🚀 启动 {name}...")
    try:
        subprocess.Popen(
            [sys.executable, str(script_path)],
            cwd=TOOLS_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        print(f"✅ {name} 已启动")
        return True
    except Exception as e:
        print(f"❌ 启动失败: {e}")
        return False

def stop_service(name, service_info):
    """停止服务"""
    port = service_info["port"]
    pid = find_pid(port)
    
    if not pid:
        print(f"⏭️  服务 {name} 未运行")
        return True
    
    try:
        os.kill(pid, signal.SIGTERM)
        print(f"✅ {name} 已停止 (PID: {pid})")
        return True
    except Exception as e:
        print(f"❌ 停止失败: {e}")
        return False

def restart_service(name, service_info):
    """重启服务"""
    print(f"🔄 重启 {name}...")
    stop_service(name, service_info)
    import time
    time.sleep(1)
    return start_service(name, service_info)

def status_service(name, service_info):
    """查看服务状态"""
    port = service_info["port"]
    pid = find_pid(port)
    
    if pid:
        print(f"✅ {name}: 运行中 (PID: {pid}, 端口: {port})")
    else:
        print(f"❌ {name}: 未运行 (端口: {port})")

def main():
    if len(sys.argv) < 2:
        print("用法: python batch_ops.py <命令> [服务名]")
        print("\n命令:")
        print("  start <服务名>   启动服务")
        print("  stop <服务名>    停止服务")
        print("  restart <服务名> 重启服务")
        print("  status <服务名>  查看状态")
        print("  start-all        启动所有服务")
        print("  stop-all         停止所有服务")
        print("  status-all       查看所有服务状态")
        sys.exit(1)
    
    command = sys.argv[1]
    service_name = sys.argv[2] if len(sys.argv) > 2 else None
    
    if command == "start-all":
        for name, info in SERVICES.items():
            start_service(name, info)
    
    elif command == "stop-all":
        for name, info in SERVICES.items():
            stop_service(name, info)
    
    elif command == "status-all":
        for name, info in SERVICES.items():
            status_service(name, info)
    
    elif service_name:
        if service_name not in SERVICES:
            print(f"❌ 未知服务: {service_name}")
            print(f"可用服务: {', '.join(SERVICES.keys())}")
            sys.exit(1)
        
        info = SERVICES[service_name]
        
        if command == "start":
            start_service(service_name, info)
        elif command == "stop":
            stop_service(service_name, info)
        elif command == "restart":
            restart_service(service_name, info)
        elif command == "status":
            status_service(service_name, info)
        else:
            print(f"❌ 未知命令: {command}")
            sys.exit(1)
    else:
        print("❌ 请指定服务名或使用 start-all/stop-all/status-all")
        sys.exit(1)

if __name__ == "__main__":
    main()