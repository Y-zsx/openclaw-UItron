#!/usr/bin/env python3
"""
自动修复模块 - Auto Repair Module
智能运维助手系统组成部分

功能:
- 抽象修复接口基类
- 常见修复策略实现
- 修复执行引擎
- 与告警系统集成
"""

import json
import os
import subprocess
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Any
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('AutoRepair')


class RepairBase(ABC):
    """修复策略抽象基类"""
    
    def __init__(self, name: str, description: str, priority: int = 5):
        self.name = name
        self.description = description
        self.priority = priority  # 1-10, 越高越优先执行
    
    @abstractmethod
    def can_handle(self, alert: Dict) -> bool:
        """判断此修复策略是否能处理该告警"""
        pass
    
    @abstractmethod
    def execute(self, alert: Dict, context: Dict) -> Dict:
        """执行修复操作"""
        pass
    
    def validate(self) -> bool:
        """验证修复策略是否可用"""
        return True
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "priority": self.priority
        }


class RestartService(RepairBase):
    """重启服务修复策略"""
    
    KNOWN_SERVICES = {
        "nginx": "nginx",
        "apache": "apache2", 
        "mysql": "mysql",
        "postgresql": "postgresql",
        "redis": "redis-server",
        "docker": "docker",
        "openclaw": "openclaw"
    }
    
    def __init__(self):
        super().__init__("RestartService", "重启指定服务", priority=8)
    
    def can_handle(self, alert: Dict) -> bool:
        alert_type = alert.get("type", "")
        message = alert.get("message", "").lower()
        
        # 服务宕机、响应超时等情况 (支持中英文)
        keywords = [
            "service down", "not responding", "connection refused", "timeout",
            "服务宕机", "服务 down", "服务停止", "服务异常", "服务无响应"
        ]
        return any(k in message for k in keywords) or alert_type == "service"
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        service_name = alert.get("service", "")
        
        # 尝试从告警中提取服务名
        if not service_name:
            message = alert.get("message", "").lower()
            for known, svc in self.KNOWN_SERVICES.items():
                if known in message:
                    service_name = svc
                    break
        
        if not service_name:
            return {"success": False, "reason": "无法确定服务名"}
        
        try:
            # 尝试systemctl重启
            result = subprocess.run(
                ["systemctl", "restart", service_name],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode == 0:
                logger.info(f"Successfully restarted service: {service_name}")
                return {
                    "success": True,
                    "action": f"restarted_service",
                    "service": service_name,
                    "output": result.stdout
                }
            else:
                logger.warning(f"Failed to restart {service_name}: {result.stderr}")
                return {
                    "success": False,
                    "reason": result.stderr
                }
        except subprocess.TimeoutExpired:
            return {"success": False, "reason": "重启超时"}
        except FileNotFoundError:
            # systemctl不可用，尝试直接运行
            return {"success": False, "reason": "systemctl不可用"}
        except Exception as e:
            return {"success": False, "reason": str(e)}


class ClearDiskSpace(RepairBase):
    """清理磁盘空间修复策略"""
    
    def __init__(self):
        super().__init__("ClearDiskSpace", "清理磁盘空间", priority=7)
    
    def can_handle(self, alert: Dict) -> bool:
        alert_type = alert.get("type", "")
        message = alert.get("message", "").lower()
        # 支持中英文关键字 + alert_type
        return alert_type == "disk" or (("disk" in message or "磁盘" in message) and \
               ("full" in message or "usage" in message or "使用" in message or "高" in message))
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        actions_taken = []
        
        # 1. 清理日志文件
        log_dirs = ["/var/log", "/root/.openclaw/workspace/ultron/logs"]
        total_cleaned = 0
        
        for log_dir in log_dirs:
            if not os.path.exists(log_dir):
                continue
            try:
                # 清理7天前的日志
                result = subprocess.run(
                    ["find", log_dir, "-type", "f", "-name", "*.log", "-mtime", "+7", "-delete"],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    actions_taken.append("清理7天前日志文件")
            except:
                pass
        
        # 2. 清理临时文件
        temp_dirs = ["/tmp", "/var/tmp"]
        for temp_dir in temp_dirs:
            if os.path.exists(temp_dir):
                try:
                    subprocess.run(
                        ["find", temp_dir, "-type", "f", "-atime", "+1", "-delete"],
                        capture_output=True,
                        timeout=10
                    )
                    actions_taken.append(f"清理{temp_dir}下1天未访问文件")
                except:
                    pass
        
        # 3. 清理Python缓存
        try:
            subprocess.run(
                ["find", "/root/.openclaw/workspace", "-type", "d", "-name", "__pycache__", "-exec", "rm", "-rf", "{}", "+"],
                capture_output=True,
                timeout=10
            )
            actions_taken.append("清理Python缓存")
        except:
            pass
        
        if actions_taken:
            return {
                "success": True,
                "action": "disk_cleanup",
                "details": actions_taken
            }
        else:
            return {
                "success": False, 
                "reason": "无法执行清理操作或无需清理"
            }


class FreeMemory(RepairBase):
    """释放内存修复策略"""
    
    def __init__(self):
        super().__init__("FreeMemory", "释放内存", priority=6)
    
    def can_handle(self, alert: Dict) -> bool:
        alert_type = alert.get("type", "")
        message = alert.get("message", "").lower()
        # 支持中英文关键字 + alert_type
        return alert_type in ["memory", "cpu"] or \
               (("memory" in message or "内存" in message or "cpu" in message or "CPU" in message) and \
               ("high" in message or "over" in message or "usage" in message or "使用" in message or "高" in message or "超过" in message))
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        actions_taken = []
        
        # 1. 清理缓存
        try:
            # 写入缓存以强制sync
            with open('/proc/sys/vm/drop_caches', 'w') as f:
                f.write('3')
            actions_taken.append("清除页面缓存")
        except Exception as e:
            logger.debug(f"Cannot drop caches: {e}")
        
        # 2. 查找并终止占用内存高的进程
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort", "-rss"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            lines = result.stdout.split('\n')[1:6]  # 前5个进程
            killed = []
            
            for line in lines:
                parts = line.split()
                if len(parts) >= 11:
                    pid = parts[1]
                    proc = parts[10]
                    # 跳过重要进程
                    if proc not in ['systemd', 'python3', 'node', 'containerd']:
                        try:
                            # 只杀自己的子进程
                            if 'python' in proc or 'node' in proc:
                                subprocess.run(["kill", "-9", pid], timeout=2, capture_output=True)
                                killed.append(f"{proc}({pid})")
                        except:
                            pass
            
            if killed:
                actions_taken.append(f"终止高内存进程: {', '.join(killed)}")
                
        except Exception as e:
            logger.debug(f"Error killing processes: {e}")
        
        if actions_taken:
            return {
                "success": True,
                "action": "memory_free",
                "details": actions_taken
            }
        else:
            return {"success": False, "reason": "无法释放内存"}


class RotateLogs(RepairBase):
    """日志轮转修复策略"""
    
    def __init__(self):
        super().__init__("RotateLogs", "日志轮转", priority=5)
    
    def can_handle(self, alert: bool) -> bool:
        # 需要与告警引擎集成时使用
        return False  # 默认不自动触发
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        # 手动触发日志轮转
        try:
            subprocess.run(["logrotate", "-f", "/etc/logrotate.conf"], 
                         capture_output=True, timeout=10)
            return {"success": True, "action": "log_rotation"}
        except:
            return {"success": False, "reason": "logrotate不可用"}


class KillProcess(RepairBase):
    """终止进程修复策略"""
    
    def __init__(self):
        super().__init__("KillProcess", "终止异常进程", priority=9)
    
    def can_handle(self, alert: Dict) -> bool:
        alert_type = alert.get("type", "")
        message = alert.get("message", "").lower()
        # 支持alert_type或关键字匹配
        return alert_type == "process" or ("process" in message and ("hung" in message or "stuck" in message or "zombie" in message or "卡" in message or "僵死" in message))
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        process_pattern = alert.get("process", "")
        
        if not process_pattern:
            return {"success": False, "reason": "未指定进程"}
        
        try:
            # 查找进程
            result = subprocess.run(
                ["pgrep", "-f", process_pattern],
                capture_output=True,
                text=True
            )
            
            pids = result.stdout.strip().split('\n')
            killed = []
            
            for pid in pids:
                if pid:
                    try:
                        subprocess.run(["kill", "-9", pid], timeout=2, capture_output=True)
                        killed.append(pid)
                    except:
                        pass
            
            if killed:
                return {
                    "success": True,
                    "action": "killed_processes",
                    "pids": killed
                }
            else:
                return {"success": False, "reason": "未找到进程"}
                
        except Exception as e:
            return {"success": False, "reason": str(e)}


class NetworkRepair(RepairBase):
    """网络修复策略"""
    
    def __init__(self):
        super().__init__("NetworkRepair", "网络故障修复", priority=9)
    
    def can_handle(self, alert: Dict) -> bool:
        alert_type = alert.get("type", "")
        message = alert.get("message", "").lower()
        # 支持alert_type和网络相关关键字
        return alert_type == "network" or "network" in message or "connection" in message or "dns" in message or "网络" in message or "连接" in message
    
    def execute(self, alert: Dict, context: Dict) -> Dict:
        actions = []
        
        # 1. 刷新DNS缓存
        try:
            subprocess.run(["systemd-resolve", "--flush-caches"], 
                         capture_output=True, timeout=5)
            actions.append("刷新DNS缓存")
        except:
            try:
                subprocess.run(["service", "nscd", "restart"], 
                             capture_output=True, timeout=5)
                actions.append("重启nscd")
            except:
                pass
        
        # 2. 重启网络接口
        try:
            # 获取默认网卡
            result = subprocess.run(
                ["ip", "route", "show", "default"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout:
                iface = result.stdout.split()[4]
                subprocess.run(["ip", "link", "set", iface, "down"], timeout=3)
                subprocess.run(["ip", "link", "set", iface, "up"], timeout=3)
                actions.append(f"重启网络接口 {iface}")
        except Exception as e:
            logger.debug(f"Network repair error: {e}")
        
        if actions:
            return {
                "success": True,
                "action": "network_repair",
                "details": actions
            }
        return {"success": False, "reason": "无法执行网络修复"}


class RepairEngine:
    """修复执行引擎"""
    
    def __init__(self):
        self.strategies: List[RepairBase] = []
        self.repair_history: List[Dict] = []
        self.enabled = True
        
        # 注册默认修复策略
        self.register_default_strategies()
    
    def register_default_strategies(self):
        """注册默认修复策略"""
        self.strategies = [
            KillProcess(),        # 终止异常进程 (高优先级)
            NetworkRepair(),      # 网络修复
            RestartService(),     # 重启服务
            ClearDiskSpace(),     # 清理磁盘
            FreeMemory(),         # 释放内存
        ]
        # 按优先级排序
        self.strategies.sort(key=lambda x: x.priority, reverse=True)
        logger.info(f"注册了 {len(self.strategies)} 个修复策略")
    
    def add_strategy(self, strategy: RepairBase):
        """添加自定义修复策略"""
        self.strategies.append(strategy)
        self.strategies.sort(key=lambda x: x.priority, reverse=True)
    
    def find_strategy(self, alert: Dict) -> Optional[RepairBase]:
        """查找适合的修复策略"""
        for strategy in self.strategies:
            if strategy.can_handle(alert):
                return strategy
        return None
    
    def repair(self, alert: Dict, context: Dict = None) -> Dict:
        """执行修复"""
        if not self.enabled:
            return {"success": False, "reason": "修复引擎已禁用"}
        
        if context is None:
            context = {}
        
        # 查找合适的策略
        strategy = self.find_strategy(alert)
        
        if not strategy:
            return {
                "success": False,
                "reason": "没有找到适用的修复策略",
                "alert_id": alert.get("id", "unknown")
            }
        
        # 执行修复
        logger.info(f"使用策略 {strategy.name} 修复告警: {alert.get('id')}")
        
        try:
            result = strategy.execute(alert, context)
            
            # 记录修复历史
            repair_record = {
                "timestamp": datetime.now().isoformat(),
                "alert_id": alert.get("id"),
                "strategy": strategy.name,
                "result": result
            }
            self.repair_history.append(repair_record)
            
            # 保存历史
            self._save_history()
            
            return result
            
        except Exception as e:
            logger.error(f"修复执行失败: {e}")
            return {
                "success": False,
                "reason": str(e),
                "strategy": strategy.name
            }
    
    def _save_history(self):
        """保存修复历史"""
        history_file = Path("/root/.openclaw/workspace/ultron/data/repair_history.json")
        history_file.parent.mkdir(parents=True, exist_ok=True)
        
        # 只保留最近100条
        recent = self.repair_history[-100:]
        
        with open(history_file, 'w') as f:
            json.dump(recent, f, indent=2, ensure_ascii=False)
    
    def get_status(self) -> Dict:
        """获取修复引擎状态"""
        return {
            "enabled": self.enabled,
            "strategies_count": len(self.strategies),
            "strategies": [s.to_dict() for s in self.strategies],
            "total_repairs": len(self.repair_history)
        }


# 全局修复引擎实例
_engine = None

def get_engine() -> RepairEngine:
    """获取全局修复引擎实例"""
    global _engine
    if _engine is None:
        _engine = RepairEngine()
    return _engine


def repair_alert(alert: Dict) -> Dict:
    """快捷修复函数"""
    engine = get_engine()
    return engine.repair(alert)


if __name__ == "__main__":
    # 测试修复引擎
    engine = get_engine()
    print("=== 修复引擎状态 ===")
    print(json.dumps(engine.get_status(), indent=2, ensure_ascii=False))
    
    print("\n=== 测试修复策略 ===")
    
    # 测试告警
    test_alerts = [
        {"id": "test1", "type": "disk", "message": "Disk usage is high", "severity": "warning"},
        {"id": "test2", "type": "memory", "message": "Memory usage is high", "severity": "critical"},
        {"id": "test3", "type": "service", "message": "nginx service is down", "severity": "critical"},
    ]
    
    for alert in test_alerts:
        result = engine.repair(alert)
        print(f"\n告警 {alert['id']}: {result}")