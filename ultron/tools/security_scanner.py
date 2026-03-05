#!/usr/bin/env python3
"""
安全扫描工具 - Agent服务安全监控
第162世: 自动化安全扫描
"""
import os
import json
import subprocess
from datetime import datetime
from pathlib import Path

WORKSPACE = Path("/root/.openclaw/workspace")
DATA_DIR = WORKSPACE / "ultron" / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

def check_open_ports():
    """检查开放端口"""
    try:
        result = subprocess.run(["ss", "-tuln"], capture_output=True, text=True, timeout=10)
        ports = []
        for line in result.stdout.split("\n")[1:]:
            if "LISTEN" in line:
                parts = line.split()
                if len(parts) >= 5:
                    port_info = parts[4]
                    if ":" in port_info:
                        port = port_info.split(":")[-1]
                        try:
                            ports.append(int(port))
                        except:
                            pass
        return sorted(set(ports))
    except Exception as e:
        return [f"error: {e}"]

def check_failed_logins():
    """检查失败登录尝试"""
    try:
        result = subprocess.run(
            ["grep", "Failed password", "/var/log/auth.log", "||", "true"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        recent = [l for l in lines if "Mar  6" in l or "Mar  5" in l]
        return {
            "total": len(lines),
            "recent": len(recent),
            "sample": recent[-5:] if recent else []
        }
    except Exception as e:
        return {"error": str(e)}

def check_running_services():
    """检查关键服务状态"""
    services = ["openclaw-gateway", "docker", "ssh", "cron"]
    result = {}
    for svc in services:
        try:
            r = subprocess.run(
                ["systemctl", "is-active", svc],
                capture_output=True, text=True, timeout=5
            )
            result[svc] = r.stdout.strip()
        except:
            result[svc] = "unknown"
    return result

def check_firewall():
    """检查防火墙状态"""
    try:
        r = subprocess.run(["ufw", "status"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip().split("\n")[0] if r.stdout else "unknown"
    except:
        return "not configured"

def check_ssh_hardening():
    """检查SSH加固状态"""
    ssh_config = "/etc/ssh/sshd_config"
    checks = {
        "password_auth": None,
        "permit_root_login": None,
        "pubkey_auth": None
    }
    try:
        with open(ssh_config, "r") as f:
            for line in f:
                line = line.strip()
                if not line.startswith("#"):
                    if "PasswordAuthentication" in line:
                        checks["password_auth"] = line
                    elif "PermitRootLogin" in line:
                        checks["permit_root_login"] = line
                    elif "PubkeyAuthentication" in line:
                        checks["pubkey_auth"] = line
    except:
        pass
    return checks

def run_security_scan():
    """运行完整安全扫描"""
    report = {
        "timestamp": datetime.now().isoformat(),
        "incarnation": 162,
        "task": "自动化安全扫描",
        "open_ports": check_open_ports(),
        "failed_logins": check_failed_logins(),
        "services": check_running_services(),
        "firewall": check_firewall(),
        "ssh_hardening": check_ssh_hardening(),
    }
    
    # 评估风险
    risks = []
    if report["open_ports"]:
        if 22 in report["open_ports"]:
            risks.append("SSH端口开放(建议限制IP)")
        if 80 in report["open_ports"] or 443 in report["open_ports"]:
            risks.append("Web服务端口开放")
    
    if report["failed_logins"]["recent"] > 50:
        risks.append("近期失败登录过多")
    
    if report["services"].get("openclaw-gateway") != "active":
        risks.append("OpenClaw Gateway未运行")
        
    report["risks"] = risks
    report["security_score"] = max(0, 100 - len(risks) * 20)
    
    return report

if __name__ == "__main__":
    report = run_security_scan()
    
    # 保存报告
    report_path = DATA_DIR / "security_scan_report.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"✅ 安全扫描完成")
    print(f"   安全评分: {report['security_score']}/100")
    print(f"   发现风险: {len(report['risks'])}")
    print(f"   开放端口: {report['open_ports']}")
    print(f"   报告: {report_path}")
    
    if report['risks']:
        print(f"\n⚠️ 风险项:")
        for r in report['risks']:
            print(f"   - {r}")
