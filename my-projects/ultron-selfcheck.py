#!/usr/bin/env python3
"""
奥创定时自检 🦞
每小时自动运行，检查自身状态
"""
import os
import sys
import json
import subprocess
from datetime import datetime

CHECK_FILE = "/tmp/ultron-selfcheck.json"
LOG_FILE = "/tmp/ultron-selfcheck.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def check_gateway():
    """检查Gateway"""
    try:
        result = subprocess.run(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", "http://127.0.0.1:18789/"],
            capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() == "200"
    except:
        return False

def check_browser():
    """检查浏览器"""
    result = subprocess.run(["pgrep", "-f", "chrome"], capture_output=True)
    return result.returncode == 0

def check_ports():
    """检查端口"""
    result = subprocess.run(
        ["netstat", "-tlnp"], capture_output=True, text=True
    )
    ports = []
    for line in result.stdout.split("\n"):
        if "LISTEN" in line:
            parts = line.split()
            if len(parts) >= 4:
                addr = parts[3]
                if ":" in addr:
                    port = addr.split(":")[-1]
                    if port.isdigit():
                        ports.append(int(port))
    return sorted(set(ports))

def check_services():
    """检查服务"""
    services = {
        "nginx": "nginx",
        "openclaw": "openclaw-gateway", 
        "python-status": "python3.*status-panel",
        "python-ultron": "python3.*ultron"
    }
    results = {}
    for name, pattern in services.items():
        result = subprocess.run(["pgrep", "-f", pattern], capture_output=True)
        results[name] = result.returncode == 0
    return results

def main():
    log("=== 奥创自检开始 ===")
    
    status = {
        "time": datetime.now().isoformat(),
        "gateway": check_gateway(),
        "browser": check_browser(),
        "ports": check_ports(),
        "services": check_services()
    }
    
    # 保存状态
    with open(CHECK_FILE, "w") as f:
        json.dump(status, f, indent=2)
    
    log(f"Gateway: {'✓' if status['gateway'] else '✗'}")
    log(f"Browser: {'✓' if status['browser'] else '✗'}")
    log(f"Ports: {status['ports']}")
    
    all_ok = status['gateway'] and all(status['services'].values())
    log(f"整体状态: {'✓ 正常' if all_ok else '⚠ 异常'}")
    
    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())