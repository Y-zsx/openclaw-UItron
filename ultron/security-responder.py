#!/usr/bin/env python3
"""
奥创安全自动化响应系统 - 第2世
功能：自动封禁/隔离、快速恢复机制、告警升级策略
作者：Ultron
创建：2026-03-04
"""

import json
import os
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import threading
import re

# 配置路径
CONFIG_DIR = Path("/root/.openclaw/workspace/ultron-self")
RESPONDER_CONFIG = CONFIG_DIR / "security-responder.json"
ACTION_LOG = CONFIG_DIR / "security-actions.jsonl"
BLOCK_LIST = CONFIG_DIR / "block-list.json"
QUARANTINE_DIR = Path("/tmp/ultron-quarantine")

# 确保目录存在
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

class SecurityResponder:
    """安全自动化响应系统"""
    
    def __init__(self):
        self.config = self._load_config()
        self.action_history = []
        self.blocked_ips = set()
        self.quarantined_files = set()
        self._load_block_list()
        
    def _load_config(self) -> Dict:
        """加载配置"""
        default_config = {
            "auto_block_enabled": True,
            "auto_quarantine_enabled": True,
            "block_threshold": 3,  # 多少次攻击后封禁
            "block_duration": 3600,  # 封禁持续时间(秒)
            "auto_recovery_enabled": True,
            "recovery_timeout": 300,  # 恢复超时(秒)
            "alert_escalation_enabled": True,
            "escalation_levels": {
                "low": {"count": 1, "cooldown": 60},
                "medium": {"count": 5, "cooldown": 300},
                "high": {"count": 10, "cooldown": 600},
                "critical": {"count": 20, "cooldown": 1800}
            },
            "auto_fix_rules": [
                {"pattern": "high_cpu", "action": "restart_service", "service": "gateway"},
                {"pattern": "memory_leak", "action": "clear_cache", "target": "system"},
                {"pattern": "disk_full", "action": "cleanup_logs", "days": 7}
            ],
            "whitelist": ["127.0.0.1", "::1", "172.16.204.191"]
        }
        
        if RESPONDER_CONFIG.exists():
            with open(RESPONDER_CONFIG) as f:
                loaded = json.load(f)
                default_config.update(loaded)
        else:
            self._save_config(default_config)
            
        return default_config
    
    def _save_config(self, config: Dict):
        """保存配置"""
        with open(RESPONDER_CONFIG, 'w') as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    
    def _load_block_list(self):
        """加载封禁列表"""
        if BLOCK_LIST.exists():
            with open(BLOCK_LIST) as f:
                data = json.load(f)
                self.blocked_ips = set(data.get("ips", []))
    
    def _save_block_list(self):
        """保存封禁列表"""
        data = {
            "ips": list(self.blocked_ips),
            "updated": datetime.now().isoformat()
        }
        with open(BLOCK_LIST, 'w') as f:
            json.dump(data, f, indent=2)
    
    def log_action(self, action_type: str, target: str, details: Dict):
        """记录安全动作"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": action_type,
            "target": target,
            "details": details,
            "status": "executed"
        }
        self.action_history.append(entry)
        
        # 写入日志文件
        with open(ACTION_LOG, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
        
        return entry
    
    def block_ip(self, ip: str, reason: str, duration: Optional[int] = None) -> bool:
        """封禁IP地址"""
        if ip in self.config["whitelist"]:
            self.log_action("block_skip", ip, {"reason": "whitelisted"})
            return False
            
        if ip in self.blocked_ips:
            return False
        
        duration = duration or self.config["block_duration"]
        
        # 尝试使用iptables封禁
        try:
            # 检查是否为IPv6
            if ':' in ip:
                subprocess.run(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"], 
                             check=True, capture_output=True)
            else:
                subprocess.run(["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"], 
                             check=True, capture_output=True)
            
            self.blocked_ips.add(ip)
            self._save_block_list()
            
            self.log_action("block_ip", ip, {
                "reason": reason,
                "duration": duration,
                "method": "iptables"
            })
            
            # 设置定时解封
            threading.Timer(duration, self.unblock_ip, args=[ip, "expired"]).start()
            
            return True
        except subprocess.CalledProcessError as e:
            self.log_action("block_failed", ip, {"reason": str(e)})
            return False
    
    def unblock_ip(self, ip: str, reason: str = "manual") -> bool:
        """解封IP地址"""
        if ip not in self.blocked_ips:
            return False
            
        try:
            subprocess.run(["iptables", "-D", "INPUT", "-s", ip, "-j", "DROP"], 
                         capture_output=True)
            self.blocked_ips.discard(ip)
            self._save_block_list()
            
            self.log_action("unblock_ip", ip, {"reason": reason})
            return True
        except subprocess.CalledProcessError:
            return False
    
    def quarantine_file(self, file_path: str, reason: str) -> bool:
        """隔离可疑文件"""
        if not self.config["auto_quarantine_enabled"]:
            return False
            
        path = Path(file_path)
        if not path.exists():
            return False
        
        try:
            # 移动到隔离区
            quarantine_path = QUARANTINE_DIR / path.name
            path.rename(quarantine_path)
            
            self.quarantined_files.add(str(quarantine_path))
            
            self.log_action("quarantine", file_path, {
                "reason": reason,
                "quarantine_path": str(quarantine_path)
            })
            
            return True
        except Exception as e:
            self.log_action("quarantine_failed", file_path, {"error": str(e)})
            return False
    
    def restore_file(self, file_path: str) -> bool:
        """恢复被隔离的文件"""
        path = Path(file_path)
        quarantine_path = QUARANTINE_DIR / path.name
        
        if not quarantine_path.exists():
            return False
            
        try:
            quarantine_path.rename(path)
            self.quarantined_files.discard(str(quarantine_path))
            
            self.log_action("restore", file_path, {"source": str(quarantine_path)})
            return True
        except Exception:
            return False
    
    def auto_recovery(self, issue_type: str) -> bool:
        """自动恢复机制"""
        if not self.config["auto_recovery_enabled"]:
            return False
        
        recovery_actions = {
            "high_cpu": self._fix_high_cpu,
            "memory_leak": self._fix_memory_leak,
            "disk_full": self._fix_disk_full,
            "service_down": self._fix_service_down,
            "connection_timeout": self._fix_connection_issue
        }
        
        fix_func = recovery_actions.get(issue_type)
        if not fix_func:
            self.log_action("recovery_skip", issue_type, {"reason": "no fix defined"})
            return False
        
        try:
            result = fix_func()
            self.log_action("recovery", issue_type, {"result": result})
            return result
        except Exception as e:
            self.log_action("recovery_failed", issue_type, {"error": str(e)})
            return False
    
    def _fix_high_cpu(self) -> str:
        """修复高CPU问题"""
        # 重启gateway服务
        subprocess.run(["openclaw", "gateway", "restart"], capture_output=True)
        return "gateway_restarted"
    
    def _fix_memory_leak(self) -> str:
        """修复内存泄漏"""
        # 清理缓存
        subprocess.run(["sync"], capture_output=True)
        subprocess.run(["echo", "3", ">", "/proc/sys/vm/drop_caches"], shell=True)
        return "cache_cleared"
    
    def _fix_disk_full(self) -> str:
        """修复磁盘满问题"""
        # 清理7天前的日志
        cutoff = datetime.now() - timedelta(days=7)
        
        log_dirs = ["/var/log", "/root/.openclaw/logs"]
        cleaned = 0
        
        for log_dir in log_dirs:
            if not Path(log_dir).exists():
                continue
            for f in Path(log_dir).rglob("*.log"):
                try:
                    mtime = datetime.fromtimestamp(f.stat().st_mtime)
                    if mtime < cutoff:
                        f.unlink()
                        cleaned += 1
                except Exception:
                    pass
        
        return f"cleaned_{cleaned}_files"
    
    def _fix_service_down(self) -> str:
        """修复服务宕机"""
        # 检查并重启服务
        subprocess.run(["openclaw", "gateway", "restart"], capture_output=True)
        time.sleep(5)
        
        # 验证服务状态
        result = subprocess.run(["openclaw", "gateway", "status"], 
                              capture_output=True, text=True)
        
        if "running" in result.stdout.lower():
            return "service_restored"
        return "service_still_down"
    
    def _fix_connection_issue(self) -> str:
        """修复连接问题"""
        # 重启网络相关服务
        subprocess.run(["systemctl", "restart", "networking"], capture_output=True)
        return "network_restarted"
    
    def escalate_alert(self, alert_data: Dict) -> List[Dict]:
        """告警升级策略"""
        if not self.config["alert_escalation_enabled"]:
            return []
        
        level = alert_data.get("severity", "low")
        level_config = self.config["escalation_levels"].get(level, {})
        
        escalations = []
        
        # 根据级别生成升级动作
        if level == "critical":
            escalations.append({
                "level": "critical",
                "action": "notify_admin",
                "message": "CRITICAL安全事件需要立即处理"
            })
            escalations.append({
                "level": "critical", 
                "action": "auto_block",
                "target": alert_data.get("source_ip")
            })
        elif level == "high":
            escalations.append({
                "level": "high",
                "action": "increase_monitoring",
                "target": alert_data.get("source")
            })
        elif level == "medium":
            escalations.append({
                "level": "medium",
                "action": "log_enhanced",
                "target": alert_data.get("source")
            })
        
        self.log_action("alert_escalation", level, {
            "original_alert": alert_data,
            "escalations": escalations
        })
        
        return escalations
    
    def process_threat(self, threat_data: Dict) -> Dict:
        """处理威胁并执行响应"""
        threat_id = threat_data.get("id", f"threat_{int(time.time())}")
        threat_type = threat_data.get("type", "unknown")
        source_ip = threat_data.get("source_ip")
        severity = threat_data.get("severity", "low")
        
        actions_taken = []
        
        # 1. 根据威胁类型执行响应
        if threat_type in ["brute_force", "ddos", "intrusion"]:
            if source_ip and self.config["auto_block_enabled"]:
                blocked = self.block_ip(source_ip, f"auto_block_{threat_type}")
                if blocked:
                    actions_taken.append(f"blocked_ip:{source_ip}")
        
        # 2. 隔离相关文件
        if threat_type in ["malware", "suspicious_file"]:
            target_file = threat_data.get("file_path")
            if target_file:
                quarantined = self.quarantine_file(target_file, threat_type)
                if quarantined:
                    actions_taken.append(f"quarantined:{target_file}")
        
        # 3. 尝试自动恢复
        recovery_issue = threat_data.get("recovery_issue")
        if recovery_issue:
            recovered = self.auto_recovery(recovery_issue)
            if recovered:
                actions_taken.append(f"recovered:{recovery_issue}")
        
        # 4. 告警升级
        if severity in ["high", "critical"]:
            escalations = self.escalate_alert(threat_data)
            actions_taken.append(f"escalated:{len(escalations)}")
        
        result = {
            "threat_id": threat_id,
            "processed": True,
            "actions": actions_taken,
            "timestamp": datetime.now().isoformat()
        }
        
        self.log_action("process_threat", threat_id, result)
        
        return result
    
    def get_status(self) -> Dict:
        """获取响应系统状态"""
        return {
            "auto_block_enabled": self.config["auto_block_enabled"],
            "auto_quarantine_enabled": self.config["auto_quarantine_enabled"],
            "auto_recovery_enabled": self.config["auto_recovery_enabled"],
            "blocked_ips_count": len(self.blocked_ips),
            "quarantined_files_count": len(self.quarantined_files),
            "action_history_count": len(self.action_history),
            "config": self.config
        }
    
    def get_blocked_ips(self) -> List[str]:
        """获取当前封禁的IP列表"""
        return list(self.blocked_ips)
    
    def get_quarantined_files(self) -> List[str]:
        """获取隔离的文件列表"""
        return list(self.quarantined_files)
    
    def get_action_history(self, limit: int = 50) -> List[Dict]:
        """获取操作历史"""
        return self.action_history[-limit:]


def main():
    """命令行接口"""
    responder = SecurityResponder()
    
    import argparse
    parser = argparse.ArgumentParser(description="奥创安全自动化响应系统")
    parser.add_argument("command", choices=["status", "block", "unblock", 
                                            "quarantine", "restore", "process",
                                            "list-blocks", "list-quarantine",
                                            "history", "auto-fix"],
                       help="命令")
    parser.add_argument("--target", help="目标(IP或文件)")
    parser.add_argument("--reason", help="原因")
    parser.add_argument("--duration", type=int, help="封禁时长(秒)")
    parser.add_argument("--threat", help="威胁JSON数据")
    parser.add_argument("--issue", help="问题类型(用于自动修复)")
    parser.add_argument("--limit", type=int, default=50, help="历史记录数量")
    
    args = parser.parse_args()
    
    if args.command == "status":
        status = responder.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        
    elif args.command == "block":
        if not args.target:
            print("Error: --target required")
            return
        responder.block_ip(args.target, args.reason or "manual", args.duration)
        
    elif args.command == "unblock":
        if not args.target:
            print("Error: --target required")
            return
        responder.unblock_ip(args.target, "manual")
        
    elif args.command == "quarantine":
        if not args.target:
            print("Error: --target required")
            return
        responder.quarantine_file(args.target, args.reason or "manual")
        
    elif args.command == "restore":
        if not args.target:
            print("Error: --target required")
            return
        responder.restore_file(args.target)
        
    elif args.command == "process":
        if not args.threat:
            print("Error: --threat required (JSON)")
            return
        threat_data = json.loads(args.threat)
        result = responder.process_threat(threat_data)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "list-blocks":
        ips = responder.get_blocked_ips()
        print(json.dumps(ips, indent=2))
        
    elif args.command == "list-quarantine":
        files = responder.get_quarantined_files()
        print(json.dumps(files, indent=2))
        
    elif args.command == "history":
        history = responder.get_action_history(args.limit)
        print(json.dumps(history, indent=2, ensure_ascii=False))
        
    elif args.command == "auto-fix":
        if not args.issue:
            print("Error: --issue required")
            return
        result = responder.auto_recovery(args.issue)
        print(json.dumps({"success": result}, indent=2))


if __name__ == "__main__":
    main()