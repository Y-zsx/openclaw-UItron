#!/usr/bin/env python3
"""
一键健康检查 - Quick Health Check
快速检查奥创系统各项服务状态
"""

import socket
import subprocess
import sys
from datetime import datetime

def check_port(port, name, timeout=2):
    """检查端口是否开放"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex(('localhost', port))
        sock.close()
        return result == 0
    except:
        return False

def check_process(name):
    """检查进程是否运行"""
    try:
        result = subprocess.run(["pgrep", "-f", name], 
                              capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False

def main():
    print("=" * 60)
    print("🏥 奥创系统健康检查")
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    services = [
        (18210, "Agent健康API"),
        (18227, "自愈API"),
        (18228, "集成测试API"),
        (18225, "系统摘要API"),
        (18229, "调度器日志分析"),
    ]
    
    print("\n📡 端口服务检查:")
    all_ok = True
    for port, name in services:
        ok = check_port(port, name)
        status = "✅ 正常" if ok else "❌ 异常"
        print(f"  端口 {port:5d} - {name:<20} {status}")
        if not ok:
            all_ok = False
    
    print("\n🔧 关键进程检查:")
    processes = [
        "agent_health_integration.py",
        "self_healing_api.py",
        "system_summary_api.py",
    ]
    
    for proc in processes:
        ok = check_process(proc)
        status = "✅ 运行中" if ok else "❌ 未运行"
        print(f"  {proc:<40} {status}")
        if not ok:
            all_ok = False
    
    # 系统资源
    print("\n💻 系统资源:")
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        cpu_status = "⚠️ 高" if cpu > 80 else "✅ 正常"
        mem_status = "⚠️ 高" if mem.percent > 80 else "✅ 正常"
        disk_status = "⚠️ 高" if disk.percent > 80 else "✅ 正常"
        
        print(f"  CPU: {cpu:5.1f}% {cpu_status}")
        print(f"  内存: {mem.percent:5.1f}% {mem_status}")
        print(f"  磁盘: {disk.percent:5.1f}% {disk_status}")
    except ImportError:
        print("  (psutil未安装)")
    
    print("\n" + "=" * 60)
    if all_ok:
        print("✅ 系统状态: 正常")
    else:
        print("⚠️ 系统状态: 存在异常")
    print("=" * 60)
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())