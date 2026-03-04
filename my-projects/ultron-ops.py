#!/usr/bin/env python3
"""
奥创运维工具箱 🦞
自动执行日常运维任务
"""
import os
import json
import subprocess
from datetime import datetime

LOG_FILE = "/tmp/ultron-ops.log"

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

def cmd(cmd_str, shell=False):
    """执行命令"""
    try:
        result = subprocess.run(
            cmd_str if shell else cmd_str.split(),
            capture_output=True, text=True, timeout=30
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def check_server():
    """服务器状态检查"""
    log("=== 服务器状态检查 ===")
    
    # Uptime
    code, out, _ = cmd("uptime")
    if code == 0:
        log(f"运行时间: {out.strip()}")
    
    # CPU负载
    with open("/proc/loadavg") as f:
        load = f.read().split()[:3]
    log(f"负载: {' / '.join(load)}")
    
    # 内存
    code, out, _ = cmd("free -h", shell=True)
    if code == 0:
        for line in out.split("\n"):
            if "Mem:" in line:
                log(f"内存: {line.strip()}")
                break
    
    # 磁盘
    code, out, _ = cmd("df -h /", shell=True)
    if code == 0:
        for line in out.split("\n"):
            if "/" in line:
                log(f"磁盘: {line.strip()}")
                break

def check_services():
    """检查服务状态"""
    log("=== 服务状态 ===")
    
    # 使用ps检测更可靠
    checks = [
        ("nginx", "nginx"),
        ("Gateway", "openclaw-gateway"),
    ]
    for name, proc in checks:
        code, out, _ = cmd(f"pgrep -f {proc}")
        status = "运行中" if code == 0 and out.strip() else "停止"
        log(f"{name}: {status}")

def check_ports():
    """检查端口"""
    log("=== 端口监听 ===")
    code, out, _ = cmd("netstat -tlnp 2>/dev/null | grep LISTEN", shell=True)
    ports = []
    for line in out.split("\n"):
        if "0.0.0.0:" in line or ":::" in line:
            parts = line.split()
            if len(parts) >= 4:
                addr = parts[3]
                if ":" in addr:
                    port = addr.split(":")[-1]
                    if port.isdigit():
                        ports.append(port)
    
    # 去重排序
    ports = sorted(set(ports), key=lambda x: int(x))
    log(f"开放端口: {', '.join(ports[:15])}...")

def check_gateway():
    """检查OpenClaw Gateway"""
    log("=== OpenClaw Gateway ===")
    
    # Gateway 进程
    code, out, _ = cmd("pgrep -f openclaw-gateway")
    if code == 0:
        pids = out.strip().split("\n")
        log(f"Gateway进程数: {len(pids)}")
    
    # 尝试健康检查
    code, out, _ = cmd("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:18789/")
    if code == 0:
        log(f"Gateway HTTP状态: {out.strip()}")

def main():
    log("奥创运维工具启动 🦞")
    check_server()
    check_services()
    check_ports()
    check_gateway()
    log("检查完成")

if __name__ == "__main__":
    main()