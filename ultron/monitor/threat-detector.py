#!/usr/bin/env python3
"""
奥创威胁检测系统 - 第1世
功能：威胁情报收集、异常行为检测、入侵检测
"""

import os
import re
import json
import time
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from collections import defaultdict

class ThreatDetector:
    """威胁检测器"""
    
    def __init__(self, workspace="/root/.openclaw/workspace"):
        self.workspace = Path(workspace)
        self.log_dir = self.workspace / "logs"
        self.log_dir.mkdir(exist_ok=True)
        self.threats_log = self.log_dir / "threats.jsonl"
        self.baseline_file = self.log_dir / "baseline.json"
        
        # 威胁级别
        self.LEVEL_CRITICAL = "CRITICAL"
        self.LEVEL_HIGH = "HIGH"
        self.LEVEL_MEDIUM = "MEDIUM"
        self.LEVEL_LOW = "LOW"
        self.LEVEL_INFO = "INFO"
        
        # 已知恶意IP列表 (简化示例)
        self.suspicious_ips = self._load_suspicious_ips()
        
    def _load_suspicious_ips(self):
        """加载可疑IP列表"""
        return {
            "45.33.32.156": "known-scanner",  # 示例
            "185.220.101.1": "tor-exit-node",
        }
    
    def scan_failed_logins(self):
        """扫描失败的SSH登录尝试"""
        threats = []
        
        # 读取系统日志
        log_files = [
            "/var/log/auth.log",
            "/var/log/secure"
        ]
        
        failed_logins = defaultdict(list)
        
        for log_file in log_files:
            if not os.path.exists(log_file):
                continue
                
            try:
                with open(log_file, 'r') as f:
                    lines = f.readlines()[-500:]  # 只读最近500行
                    
                for line in lines:
                    # SSH失败登录模式
                    if "Failed password" in line or "authentication failure" in line:
                        # 提取IP
                        ip_match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', line)
                        if ip_match:
                            ip = ip_match.group(1)
                            # 排除内网IP
                            if not ip.startswith(("10.", "192.168.", "172.16.", "127.")):
                                failed_logins[ip].append(line.strip())
                                
            except PermissionError:
                continue
        
        # 分析失败登录
        for ip, attempts in failed_logins.items():
            count = len(attempts)
            
            if count >= 10:
                level = self.LEVEL_CRITICAL
                desc = f"暴力破解攻击：{ip} 在最近日志中出现 {count} 次失败登录"
            elif count >= 5:
                level = self.LEVEL_HIGH
                desc = f"可疑登录：{ip} 有 {count} 次失败尝试"
            elif count >= 3:
                level = self.LEVEL_MEDIUM
                desc = f"警告：{ip} 有 {count} 次失败尝试"
            else:
                level = self.LEVEL_LOW
                desc = f"注意：{ip} 有 {count} 次失败尝试"
            
            if count >= 3:
                threats.append({
                    "type": "brute_force",
                    "level": level,
                    "source": ip,
                    "count": count,
                    "description": desc,
                    "timestamp": datetime.now().isoformat(),
                    "samples": attempts[:3]
                })
        
        return threats
    
    def scan_suspicious_processes(self):
        """扫描可疑进程"""
        threats = []
        
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            lines = result.stdout.split('\n')[1:]  # 跳过标题
            
            # 可疑进程模式
            suspicious_patterns = [
                (r'miner', "cryptominer"),
                (r'xmrig', "cryptominer"),
                (r'stratum\+tcp', "mining-pool"),
                (r'nc\s+-', "netcat-reverse-shell"),
                (r'/dev/tcp/', "reverse-shell"),
                (r'bash\s+-i', "interactive-bash"),
                (r'python.*-u\s+-c', "reverse-shell-python"),
                (r'wget.*\|.*sh', "remote-script"),
                (r'curl.*\|.*sh', "remote-script"),
            ]
            
            for line in lines:
                for pattern, threat_type in suspicious_patterns:
                    if re.search(pattern, line, re.IGNORECASE):
                        parts = line.split()
                        if len(parts) > 10:
                            threats.append({
                                "type": "suspicious_process",
                                "level": self.LEVEL_HIGH,
                                "process": " ".join(parts[10:]),
                                "pid": parts[1],
                                "threat_type": threat_type,
                                "description": f"检测到可疑进程: {threat_type}",
                                "timestamp": datetime.now().isoformat()
                            })
                            
        except Exception as e:
            pass
            
        return threats
    
    def scan_port_scan(self):
        """检测端口扫描"""
        threats = []
        
        try:
            # 读取最近的连接日志
            result = subprocess.run(
                ["ss", "-tn"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            connections = defaultdict(int)
            for line in result.stdout.split('\n')[1:]:
                if "ESTAB" in line:
                    parts = line.split()
                    if len(parts) >= 4:
                        # 尝试获取远程地址
                        remote = parts[3]
                        if ':' in remote:
                            ip = remote.rsplit(':', 1)[0]
                            connections[ip] += 1
            
            # 同一IP大量连接可能是扫描
            for ip, count in connections.items():
                if count > 50 and not ip.startswith(("10.", "192.168.", "172.16.", "127.")):
                    threats.append({
                        "type": "port_scan",
                        "level": self.LEVEL_MEDIUM,
                        "source": ip,
                        "count": count,
                        "description": f"可疑大量连接: {ip} 有 {count} 个活动连接",
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            pass
            
        return threats
    
    def check_unauthorized_files(self):
        """检查未授权的文件更改"""
        threats = []
        
        # 检查最近修改的可执行文件
        try:
            result = subprocess.run(
                ["find", "/usr/bin", "/usr/sbin", "/bin", "/sbin", "-mmin", "-60", "-type", "f"],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            suspicious_paths = [
                "/tmp/", "/var/tmp/", "/dev/shm/"
            ]
            
            for line in result.stdout.strip().split('\n'):
                if line and any(susp in line for susp in suspicious_paths):
                    threats.append({
                        "type": "unauthorized_file",
                        "level": self.LEVEL_HIGH,
                        "file": line,
                        "description": f"可疑位置的可执行文件: {line}",
                        "timestamp": datetime.now().isoformat()
                    })
                    
        except Exception as e:
            pass
            
        return threats
    
    def check_rootkit_indicators(self):
        """检查rootkit指标"""
        threats = []
        
        # 检查隐藏进程
        try:
            result = subprocess.run(
                ["ls", "-la", "/proc"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            pids = []
            for line in result.stdout.split('\n')[3:]:  # 跳过 . 和 ..
                parts = line.split()
                if len(parts) >= 9:
                    try:
                        pid = int(parts[-1])
                        if pid > 0:
                            pids.append(pid)
                    except:
                        pass
            
            # 检查进程数异常
            if len(pids) > 500:
                threats.append({
                    "type": "rootkit_indicator",
                    "level": self.LEVEL_MEDIUM,
                    "detail": f"进程数异常: {len(pids)} 个进程",
                    "description": "检测到大量进程，可能存在隐藏进程",
                    "timestamp": datetime.now().isoformat()
                })
                
        except Exception as e:
            pass
            
        return threats
    
    def get_system_baseline(self):
        """获取系统基线"""
        if self.baseline_file.exists():
            with open(self.baseline_file) as f:
                return json.load(f)
        return None
    
    def save_baseline(self, baseline):
        """保存系统基线"""
        with open(self.baseline_file, 'w') as f:
            json.dump(baseline, f, indent=2)
    
    def collect_threat_intel(self):
        """收集威胁情报"""
        intel = {
            "timestamp": datetime.now().isoformat(),
            "sources": [],
            "indicators": []
        }
        
        # 检查公开威胁情报源 (简化实现)
        # 实际生产环境应该对接 VirusTotal, AlienVault OTX 等
        
        intel["sources"].append("local-detection")
        
        return intel
    
    def run_full_scan(self):
        """运行完整扫描"""
        print(f"[{datetime.now()}] 开始威胁检测扫描...")
        
        all_threats = []
        
        # 1. SSH暴力破解检测
        print("[-] 扫描SSH暴力破解...")
        threats = self.scan_failed_logins()
        all_threats.extend(threats)
        print(f"    发现 {len(threats)} 个威胁")
        
        # 2. 可疑进程检测
        print("[-] 扫描可疑进程...")
        threats = self.scan_suspicious_processes()
        all_threats.extend(threats)
        print(f"    发现 {len(threats)} 个威胁")
        
        # 3. 端口扫描检测
        print("[-] 检测端口扫描...")
        threats = self.scan_port_scan()
        all_threats.extend(threats)
        print(f"    发现 {len(threats)} 个威胁")
        
        # 4. 未授权文件检测
        print("[-] 检查未授权文件...")
        threats = self.check_unauthorized_files()
        all_threats.extend(threats)
        print(f"    发现 {len(threats)} 个威胁")
        
        # 5. Rootkit指标检测
        print("[-] 检查rootkit指标...")
        threats = self.check_rootkit_indicators()
        all_threats.extend(threats)
        print(f"    发现 {len(threats)} 个威胁")
        
        # 6. 收集威胁情报
        print("[-] 收集威胁情报...")
        intel = self.collect_threat_intel()
        
        # 统计
        summary = {
            "scan_time": datetime.now().isoformat(),
            "total_threats": len(all_threats),
            "by_level": defaultdict(int),
            "by_type": defaultdict(int)
        }
        
        for threat in all_threats:
            summary["by_level"][threat.get("level", "UNKNOWN")] += 1
            summary["by_type"][threat.get("type", "unknown")] += 1
        
        # 保存威胁日志
        if all_threats:
            with open(self.threats_log, 'a') as f:
                for threat in all_threats:
                    f.write(json.dumps(threat, ensure_ascii=False) + '\n')
        
        print(f"\n[+] 扫描完成: 发现 {len(all_threats)} 个威胁")
        for level, count in summary["by_level"].items():
            print(f"    {level}: {count}")
        
        return {
            "summary": dict(summary),
            "threats": all_threats,
            "intel": intel
        }

def main():
    detector = ThreatDetector()
    result = detector.run_full_scan()
    
    # 输出JSON格式便于程序处理
    print("\n--- JSON Output ---")
    print(json.dumps(result["summary"], ensure_ascii=False, indent=2))
    
    # 如果有严重威胁，返回非0退出码
    critical = result["summary"]["by_level"].get("CRITICAL", 0)
    high = result["summary"]["by_level"].get("HIGH", 0)
    
    return 1 if (critical + high) > 0 else 0

if __name__ == "__main__":
    exit(main())