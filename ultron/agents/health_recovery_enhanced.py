#!/usr/bin/env python3
"""
增强版自动恢复机制
- 多层级恢复策略
- 恢复历史追踪与统计
- 智能恢复决策
"""

import subprocess
import time
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import sqlite3

# 数据库
DB_PATH = "/root/.openclaw/workspace/ultron/agent_network_health.db"
RECOVERY_STATS_PATH = "/root/.openclaw/workspace/ultron/state/recovery_stats.json"

# 恢复策略层级
RECOVERY_STRATEGIES = [
    {"name": "wait_retry", "delay": 5, "max_attempts": 2, "description": "等待后重试"},
    {"name": "systemd_restart", "delay": 3, "max_attempts": 2, "description": "systemd重启"},
    {"name": "force_kill", "delay": 2, "max_attempts": 1, "description": "强制结束进程后重启"},
    {"name": "port_check", "delay": 2, "max_attempts": 1, "description": "端口清理与重绑定"},
    {"name": "service_reload", "delay": 3, "max_attempts": 1, "description": "服务重载配置"},
]

class RecoveryManager:
    def __init__(self):
        self.stats = self._load_stats()
        self.service_mapping = self._get_service_mapping()
    
    def _load_stats(self) -> Dict:
        """加载恢复统计"""
        if os.path.exists(RECOVERY_STATS_PATH):
            with open(RECOVERY_STATS_PATH, "r") as f:
                return json.load(f)
        return {
            "total_recoveries": 0,
            "successful_recoveries": 0,
            "failed_recoveries": 0,
            "by_service": {},
            "by_strategy": defaultdict(int),
            "last_24h": []
        }
    
    def _save_stats(self):
        """保存恢复统计"""
        with open(RECOVERY_STATS_PATH, "w") as f:
            json.dump(self.stats, f, indent=2)
    
    def _get_service_mapping(self) -> Dict[int, str]:
        """获取服务端口到systemd名称的映射"""
        return {
            8089: "agent-service-mesh.service",
            8091: "identity-auth-api.service",
            8095: "agent-lifecycle-api.service",
            8096: "agent-task-executor.service",
            18232: "orchestration-api.service",
        }
    
    def _get_process_by_port(self, port: int) -> Optional[int]:
        """获取占用指定端口的进程PID"""
        try:
            result = subprocess.run(
                ["lsof", "-t", f"-i:{port}"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split()[0])
        except:
            pass
        return None
    
    def _kill_process(self, pid: int, force: bool = False) -> bool:
        """终止进程"""
        try:
            signal = "-9" if force else "-15"
            result = subprocess.run(
                ["kill", signal, str(pid)],
                capture_output=True,
                timeout=10
            )
            return result.returncode == 0
        except:
            return False
    
    def _wait_and_check(self, port: int, endpoint: str, delay: int) -> bool:
        """等待后检查服务是否恢复"""
        time.sleep(delay)
        import requests
        try:
            resp = requests.get(f"http://localhost:{port}{endpoint}", timeout=5)
            return resp.status_code == 200
        except:
            return False
    
    def _get_service_name(self, port: int) -> str:
        """获取服务名称"""
        names = {
            8089: "api-gateway",
            8090: "secure-channel", 
            8091: "identity-auth",
            8095: "collaboration-scheduler",
            8096: "agent-task-executor",
            18232: "orchaboration-dashboard"
        }
        return names.get(port, f"service-{port}")
    
    def execute_recovery(self, port: int, endpoint: str = "/health") -> Dict:
        """执行多层级恢复"""
        service_name = self._get_service_name(port)
        recovery_log = {
            "timestamp": datetime.utcnow().isoformat(),
            "port": port,
            "service_name": service_name,
            "strategies_attempted": [],
            "success": False,
            "final_strategy": None
        }
        
        print(f"\n🔧 开始恢复服务: {service_name} (端口 {port})")
        
        for strategy in RECOVERY_STRATEGIES:
            strategy_name = strategy["name"]
            recovery_log["strategies_attempted"].append(strategy_name)
            
            print(f"  尝试策略: {strategy['description']}...")
            
            success = False
            
            if strategy_name == "wait_retry":
                # 简单等待重试
                success = self._wait_and_check(port, endpoint, strategy["delay"])
            
            elif strategy_name == "systemd_restart":
                # systemd重启
                service = self.service_mapping.get(port)
                if service:
                    try:
                        subprocess.run(["systemctl", "restart", service], 
                                      capture_output=True, timeout=30)
                        success = self._wait_and_check(port, endpoint, strategy["delay"])
                    except:
                        pass
            
            elif strategy_name == "force_kill":
                # 强制终止进程
                pid = self._get_process_by_port(port)
                if pid:
                    self._kill_process(pid, force=True)
                    time.sleep(2)
                    # 重启服务
                    service = self.service_mapping.get(port)
                    if service:
                        try:
                            subprocess.run(["systemctl", "start", service],
                                          capture_output=True, timeout=30)
                            success = self._wait_and_check(port, endpoint, 3)
                        except:
                            pass
            
            elif strategy_name == "port_check":
                # 端口清理
                pid = self._get_process_by_port(port)
                if pid:
                    self._kill_process(pid, force=True)
                    time.sleep(1)
                success = self._wait_and_check(port, endpoint, strategy["delay"])
            
            elif strategy_name == "service_reload":
                # 服务重载
                service = self.service_mapping.get(port)
                if service:
                    try:
                        subprocess.run(["systemctl", "reload", service],
                                      capture_output=True, timeout=30)
                        success = self._wait_and_check(port, endpoint, strategy["delay"])
                    except:
                        pass
            
            # 更新统计
            self.stats["by_strategy"][strategy_name] += 1
            
            if success:
                recovery_log["success"] = True
                recovery_log["final_strategy"] = strategy_name
                print(f"  ✅ 成功! 使用策略: {strategy['description']}")
                break
            else:
                print(f"  ❌ 失败")
        
        # 更新总体统计
        self._update_stats(recovery_log)
        self._save_stats()
        
        return recovery_log
    
    def _update_stats(self, recovery_log: Dict):
        """更新恢复统计"""
        self.stats["total_recoveries"] += 1
        
        if recovery_log["success"]:
            self.stats["successful_recoveries"] += 1
        else:
            self.stats["failed_recoveries"] += 1
        
        service = recovery_log["service_name"]
        if service not in self.stats["by_service"]:
            self.stats["by_service"][service] = {
                "total": 0, "success": 0, "failed": 0
            }
        
        self.stats["by_service"][service]["total"] += 1
        if recovery_log["success"]:
            self.stats["by_service"][service]["success"] += 1
        else:
            self.stats["by_service"][service]["failed"] += 1
        
        # 最近24小时记录
        self.stats["last_24h"].append({
            "timestamp": recovery_log["timestamp"],
            "service": service,
            "success": recovery_log["success"],
            "strategy": recovery_log.get("final_strategy")
        })
        
        # 只保留最近24小时
        cutoff = (datetime.utcnow() - timedelta(hours=24)).isoformat()
        self.stats["last_24h"] = [
            r for r in self.stats["last_24h"] 
            if r["timestamp"] > cutoff
        ]
    
    def get_recovery_stats(self) -> Dict:
        """获取恢复统计"""
        total = self.stats["total_recoveries"]
        success_rate = (self.stats["successful_recoveries"] / total * 100) if total > 0 else 0
        
        return {
            "total_recoveries": total,
            "successful": self.stats["successful_recoveries"],
            "failed": self.stats["failed_recoveries"],
            "success_rate": round(success_rate, 1),
            "by_service": self.stats["by_service"],
            "by_strategy": dict(self.stats["by_strategy"]),
            "last_24h_count": len(self.stats["last_24h"])
        }
    
    def should_auto_recover(self, port: int) -> Tuple[bool, str]:
        """判断是否应该自动恢复"""
        service = self._get_service_name(port)
        
        if service not in self.stats["by_service"]:
            return True, "首次故障"
        
        service_stats = self.stats["by_service"][service]
        
        # 检查过去1小时内的失败次数
        recent_failures = [
            r for r in self.stats["last_24h"]
            if r["service"] == service and not r["success"]
        ]
        
        if len(recent_failures) >= 5:
            return False, f"过去1小时失败{len(recent_failures)}次,暂停自动恢复"
        
        return True, "正常"


def main():
    """测试增强恢复机制"""
    print("=" * 60)
    print("增强版自动恢复机制测试")
    print("=" * 60)
    
    manager = RecoveryManager()
    
    # 测试恢复（模拟）
    print("\n📊 恢复统计:")
    stats = manager.get_recovery_stats()
    print(f"  总恢复次数: {stats['total_recoveries']}")
    print(f"  成功: {stats['successful']}, 失败: {stats['failed']}")
    print(f"  成功率: {stats['success_rate']}%")
    print(f"  过去24小时: {stats['last_24h_count']}次")
    
    if stats["by_service"]:
        print("\n  按服务统计:")
        for svc, data in stats["by_service"].items():
            rate = (data["success"] / data["total"] * 100) if data["total"] > 0 else 0
            print(f"    {svc}: {data['success']}/{data['total']} ({rate:.0f}%)")
    
    print("\n" + "=" * 60)
    
    return stats


if __name__ == "__main__":
    main()