#!/usr/bin/env python3
"""
健康检测CLI工具
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8098"

def status():
    """查看所有服务状态"""
    r = requests.get(f"{BASE_URL}/status")
    data = r.json()
    
    print("=" * 60)
    print("🟢 Agent服务健康检测状态")
    print("=" * 60)
    
    services = data.get("services", {})
    for name, info in services.items():
        status_icon = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌",
            "unknown": "❓"
        }.get(info.get("status", "unknown"), "❓")
        
        print(f"{status_icon} {name}: {info.get('status', 'unknown')}")
        print(f"   响应时间: {info.get('response_time', 'N/A')}s")
        print(f"   失败次数: {info.get('failure_count', 0)}")
        print(f"   更新时间: {info.get('timestamp', 'N/A')[:19]}")
        print()
    
    # 显示最近告警
    alerts = data.get("alerts", [])
    if alerts:
        print("📢 最近告警:")
        for a in alerts[-5:]:
            print(f"   [{a['level']}] {a['service']}: {a['message']} ({a['timestamp'][:19]})")
    
    print(f"\n更新时间: {data.get('timestamp', 'N/A')[:19]}")

def check():
    """手动触发检测"""
    r = requests.post(f"{BASE_URL}/check")
    data = r.json()
    
    print("=" * 60)
    print("🔍 健康检测结果")
    print("=" * 60)
    
    for name, info in data.items():
        status_icon = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌"
        }.get(info["status"], "❓")
        
        print(f"{status_icon} {name}: {info['status']}")
        print(f"   响应时间: {info['response_time']}s")
        if info.get("error"):
            print(f"   错误: {info['error']}")
        print()

def add_service(name, port, path="/health", timeout=2.0):
    """添加服务"""
    r = requests.post(f"{BASE_URL}/service", json={
        "name": name,
        "port": port,
        "path": path,
        "timeout": timeout
    })
    print(r.json())

def history(service=None, limit=20):
    """查看历史"""
    params = {"limit": limit}
    if service:
        params["service"] = service
    r = requests.get(f"{BASE_URL}/history", params=params)
    data = r.json()
    
    print("=" * 60)
    print("📊 健康检测历史")
    print("=" * 60)
    
    for h in data:
        status_icon = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌"
        }.get(h["status"], "❓")
        print(f"{status_icon} {h['service']}: {h['status']} ({h['response_time']}s) - {h['timestamp'][:19]}")

def alerts(limit=20):
    """查看告警"""
    r = requests.get(f"{BASE_URL}/alerts")
    data = r.json()
    
    print("=" * 60)
    print("📢 告警历史")
    print("=" * 60)
    
    level_icons = {
        "critical": "🔴",
        "warning": "🟡",
        "info": "🔵"
    }
    
    for a in data[-limit:]:
        icon = level_icons.get(a["level"], "⚪")
        print(f"{icon} [{a['level']}] {a['service']}: {a['message']}")
        print(f"   时间: {a['timestamp'][:19]}")
        print()

def main():
    if len(sys.argv) < 2:
        print("Usage: health_cli.py <command> [args]")
        print("Commands:")
        print("  status          查看所有服务状态")
        print("  check           手动触发检测")
        print("  add <name> <port> [path] [timeout]  添加服务")
        print("  history [service] [limit]   查看历史")
        print("  alerts [limit]    查看告警")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == "status":
        status()
    elif cmd == "check":
        check()
    elif cmd == "add":
        if len(sys.argv) >= 4:
            add_service(sys.argv[2], int(sys.argv[3]), 
                       sys.argv[4] if len(sys.argv) > 4 else "/health",
                       float(sys.argv[5]) if len(sys.argv) > 5 else 2.0)
        else:
            print("Usage: health_cli.py add <name> <port> [path] [timeout]")
    elif cmd == "history":
        history(sys.argv[2] if len(sys.argv) > 2 else None,
                int(sys.argv[3]) if len(sys.argv) > 3 else 20)
    elif cmd == "alerts":
        alerts(int(sys.argv[2]) if len(sys.argv) > 2 else 20)
    else:
        print(f"Unknown command: {cmd}")

if __name__ == "__main__":
    main()