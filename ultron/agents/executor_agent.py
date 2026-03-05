#!/usr/bin/env python3
"""Executor Agent - 执行自动化任务
第15世: 实现执行Agent (Executor Agent)
- 定义Executor Agent接口
- 实现任务执行引擎
- 集成安全命令检查
- 实现任务队列管理
"""
import json
import subprocess
import sys
import re
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))
from message_bus import MessageBus

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"

class SecurityLevel(Enum):
    SAFE = "safe"           # 可自动执行
    REVIEW = "review"       # 需要审核
    DANGEROUS = "dangerous" # 禁止执行

class CommandSecurityChecker:
    """安全命令检查器 - 白名单机制"""
    
    # 安全命令白名单
    SAFE_COMMANDS = {
        # 系统监控
        "cat /proc/loadavg", "free -m", "df -h", "uptime", "ps aux",
        "top -bn1", "netstat -tuln", "ss -tuln",
        # 文件操作（只读）
        "ls -la", "ls -lh", "find /tmp", "head -n", "tail -n",
        "cat /proc/meminfo", "cat /proc/cpuinfo",
        # 状态查询
        "systemctl status", "service status", "pgrep -f",
        "openclaw status", "openclaw gateway status",
    }
    
    # 需要审核的命令
    REVIEW_COMMANDS = {
        "rm -rf /tmp/*", "rm -rf /var/log/*", "sync",
        "echo 3 > /proc/sys/vm/drop_caches",
        "find /var/log -name '*.log' -mtime +7",
        "openclaw gateway restart", "systemctl restart",
    }
    
    # 危险命令（禁止执行）
    DANGEROUS_PATTERNS = [
        r"rm\s+-rf\s+/",           # 删根
        r"dd\s+if=",               # dd写入
        r">\s*/dev/sd",            # 写设备
        r"chmod\s+-R\s+777",       # 777权限
        r"wget.*\|\s*sh",          # 远程脚本执行
        r"curl.*\|\s*sh",          # 远程脚本执行
        r":\(\)\{",                # Fork炸弹
        r"shutdown",               # 关机
        r"reboot",                 # 重启
        r"mkfs",                   # 格式化
        f"> {os.devnull}",         # 重定向到设备
    ]
    
    def __init__(self):
        self.audit_log = []
    
    def check(self, command: str) -> tuple[SecurityLevel, str]:
        """检查命令安全性"""
        command = command.strip()
        
        # 检查危险模式
        for pattern in self.DANGEROUS_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                self._log(command, SecurityLevel.DANGEROUS, "危险命令模式匹配")
                return SecurityLevel.DANGEROUS, f"危险命令: {pattern}"
        
        # 检查白名单
        for safe_cmd in self.SAFE_COMMANDS:
            if command.startswith(safe_cmd) or command == safe_cmd:
                self._log(command, SecurityLevel.SAFE, "白名单匹配")
                return SecurityLevel.SAFE, "白名单命令"
        
        # 检查需要审核的命令
        for review_cmd in self.REVIEW_COMMANDS:
            if command.startswith(review_cmd):
                self._log(command, SecurityLevel.REVIEW, "需要审核")
                return SecurityLevel.REVIEW, f"需审核: {review_cmd}"
        
        # 默认危险
        self._log(command, SecurityLevel.DANGEROUS, "未知命令")
        return SecurityLevel.DANGEROUS, "未授权命令"
    
    def _log(self, command: str, level: SecurityLevel, reason: str):
        """记录审计日志"""
        self.audit_log.append({
            "command": command,
            "level": level.value,
            "reason": reason,
            "timestamp": datetime.now().isoformat()
        })
        # 只保留最近100条
        if len(self.audit_log) > 100:
            self.audit_log = self.audit_log[-100:]
    
    def get_audit_log(self) -> List[Dict]:
        """获取审计日志"""
        return self.audit_log

class TaskQueue:
    """任务队列管理"""
    
    def __init__(self, queue_file: str = None):
        if queue_file is None:
            queue_file = Path(__file__).parent / "executor_queue.json"
        self.queue_file = Path(queue_file)
        self.queue = self._load_queue()
    
    def _load_queue(self) -> List[Dict]:
        """加载队列"""
        if self.queue_file.exists():
            try:
                with open(self.queue_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_queue(self):
        """保存队列"""
        with open(self.queue_file, 'w') as f:
            json.dump(self.queue, f, indent=2, ensure_ascii=False)
    
    def enqueue(self, task: Dict) -> str:
        """入队"""
        task_id = f"task_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(self.queue)}"
        task["id"] = task_id
        task["status"] = TaskStatus.PENDING.value
        task["created_at"] = datetime.now().isoformat()
        self.queue.append(task)
        self._save_queue()
        return task_id
    
    def dequeue(self) -> Optional[Dict]:
        """出队（获取第一个待处理任务）"""
        for task in self.queue:
            if task.get("status") == TaskStatus.PENDING.value:
                task["status"] = TaskStatus.RUNNING.value
                task["started_at"] = datetime.now().isoformat()
                self._save_queue()
                return task
        return None
    
    def complete(self, task_id: str, result: Any):
        """完成任务"""
        for task in self.queue:
            if task.get("id") == task_id:
                task["status"] = TaskStatus.COMPLETED.value
                task["result"] = result
                task["completed_at"] = datetime.now().isoformat()
                self._save_queue()
                return True
        return False
    
    def fail(self, task_id: str, error: str):
        """标记任务失败"""
        for task in self.queue:
            if task.get("id") == task_id:
                task["status"] = TaskStatus.FAILED.value
                task["error"] = error
                task["failed_at"] = datetime.now().isoformat()
                self._save_queue()
                return True
        return False
    
    def get_pending(self) -> List[Dict]:
        """获取所有待处理任务"""
        return [t for t in self.queue if t.get("status") == TaskStatus.PENDING.value]
    
    def get_stats(self) -> Dict:
        """获取队列统计"""
        stats = {
            "total": len(self.queue),
            "pending": 0,
            "running": 0,
            "completed": 0,
            "failed": 0
        }
        for task in self.queue:
            status = task.get("status", "pending")
            if status in stats:
                stats[status] += 1
        return stats

class TaskExecutor:
    """任务执行引擎"""
    
    def __init__(self):
        self.security = CommandSecurityChecker()
        self.queue = TaskQueue()
        
        # 预设任务处理器
        self.handlers = {
            "load_high": self._fix_high_load,
            "memory_high": self._fix_high_memory,
            "disk_full": self._fix_disk_full,
            "gateway_down": self._restart_gateway,
            "custom": self._execute_custom_command
        }
    
    def execute_task(self, task: Dict) -> Dict:
        """执行单个任务"""
        task_id = task.get("id")
        task_type = task.get("type", "custom")
        
        handler = self.handlers.get(task_type)
        if not handler:
            return {"success": False, "error": f"未知任务类型: {task_type}"}
        
        try:
            result = handler(task)
            self.queue.complete(task_id, result)
            return {"success": True, "result": result}
        except Exception as e:
            self.queue.fail(task_id, str(e))
            return {"success": False, "error": str(e)}
    
    def _fix_high_load(self, task: Dict) -> Dict:
        """高负载处理"""
        # 安全检查
        cmd = "rm -rf /tmp/* 2>/dev/null || true"
        level, _ = self.security.check(cmd)
        
        if level == SecurityLevel.DANGEROUS:
            raise Exception("安全检查拒绝: 高负载修复命令被禁止")
        
        # 执行
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"action": "cleanup_temp", "result": "已清理临时文件", "output": result.stdout}
    
    def _fix_high_memory(self, task: Dict) -> Dict:
        """高内存处理"""
        cmd = "sync && echo 3 > /proc/sys/vm/drop_caches"
        level, _ = self.security.check(cmd)
        
        if level == SecurityLevel.DANGEROUS:
            raise Exception("安全检查拒绝: 内存清理命令被禁止")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"action": "clear_cache", "result": "已清理缓存", "output": result.stdout}
    
    def _fix_disk_full(self, task: Dict) -> Dict:
        """磁盘满处理"""
        cmd = "find /var/log -name '*.log' -mtime +7 -delete 2>/dev/null || true"
        level, _ = self.security.check(cmd)
        
        if level == SecurityLevel.DANGEROUS:
            raise Exception("安全检查拒绝: 日志清理命令被禁止")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"action": "clean_logs", "result": "已清理7天前日志", "output": result.stdout}
    
    def _restart_gateway(self, task: Dict) -> Dict:
        """重启Gateway"""
        cmd = "openclaw gateway restart"
        level, _ = self.security.check(cmd)
        
        if level == SecurityLevel.DANGEROUS:
            raise Exception("安全检查拒绝: Gateway重启命令被禁止")
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        return {"action": "restart_gateway", "result": "已重启Gateway", "output": result.stdout}
    
    def _execute_custom_command(self, task: Dict) -> Dict:
        """执行自定义命令"""
        command = task.get("command", "")
        if not command:
            raise Exception("未提供命令")
        
        # 安全检查
        level, reason = self.security.check(command)
        
        if level == SecurityLevel.DANGEROUS:
            raise Exception(f"安全检查拒绝: {reason}")
        
        if level == SecurityLevel.REVIEW:
            raise Exception(f"需要审核: {reason}")
        
        # 执行
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True,
            timeout=task.get("timeout", 30)
        )
        
        return {
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr
        }

class ExecutorAgent:
    """Executor Agent - 任务执行代理"""
    
    def __init__(self):
        self.name = "executor"
        self.bus = MessageBus()
        self.executor = TaskExecutor()
        self.last_run = None
    
    def get_pending_tasks(self) -> List[Dict]:
        """从消息总线获取待处理任务"""
        return self.bus.get_tasks("executor")
    
    def handle_alert(self, alert_type: str) -> Dict:
        """处理告警"""
        handler = self.executor.handlers.get(alert_type)
        if handler:
            task = {"type": alert_type, "source": "alert"}
            return handler(task)
        return {"action": "unknown_alert", "result": "未处理"}
    
    def run(self) -> List[Dict]:
        """运行executor"""
        self.last_run = datetime.now()
        
        # 1. 从消息总线获取任务
        bus_tasks = self.get_pending_tasks()
        
        # 2. 添加到本地队列
        for task in bus_tasks:
            message = task.get("message", "")
            # 解析消息为任务类型
            task_type = self._parse_task_type(message)
            task_id = self.executor.queue.enqueue({
                "type": task_type,
                "source": "message_bus",
                "original": task
            })
            print(f"[Executor] 从消息总线接收任务: {message} -> type:{task_type}")
        
        # 3. 执行队列中的任务
        results = []
        while True:
            task = self.executor.queue.dequeue()
            if not task:
                break
            
            result = self.executor.execute_task(task)
            results.append(result)
            print(f"[Executor] 执行完成: {task.get('type')} -> {result.get('success')}")
        
        # 4. 如果没有任务，输出状态
        if not results:
            stats = self.executor.queue.get_stats()
            print(f"[Executor] 无待处理任务 | 队列: {stats}")
        
        # 5. 发送执行结果给messenger
        if results:
            self.bus.publish(
                sender="executor",
                recipient="messenger",
                message=f"执行完成: {len(results)}个任务",
                task_type="message"
            )
        
        return results
    
    def _parse_task_type(self, message: str) -> str:
        """解析消息为任务类型"""
        msg = message.lower()
        
        # 告警类型映射
        if "load" in msg and "高" in msg or "load_high" in msg:
            return "load_high"
        if "内存" in msg or "memory" in msg:
            return "memory_high"
        if "磁盘" in msg or "disk" in msg:
            return "disk_full"
        if "gateway" in msg or "网关" in msg:
            return "gateway_down"
        
        # 通用告警
        if "告警" in msg or "alert" in msg:
            return "custom"
        
        return "custom"
    
    def get_queue_status(self) -> Dict:
        """获取队列状态"""
        return self.executor.queue.get_stats()
    
    def get_audit_log(self) -> List[Dict]:
        """获取安全审计日志"""
        return self.executor.security.get_audit_log()

if __name__ == "__main__":
    agent = ExecutorAgent()
    results = agent.run()
    
    # 输出状态
    print("\n=== Executor Status ===")
    print(f"Queue: {agent.get_queue_status()}")
    print(f"Audit Log: {len(agent.get_audit_log())} entries")
    
    if results:
        print("\n=== Results ===")
        print(json.dumps(results, indent=2, ensure_ascii=False))