#!/usr/bin/env python3
"""Executor Agent - 执行自动化任务"""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from message_bus import MessageBus

class ExecutorAgent:
    def __init__(self):
        self.name = "executor"
        self.bus = MessageBus()
    
    def get_pending_tasks(self):
        """获取待处理任务"""
        return self.bus.get_tasks("executor")
    
    def handle_alert(self, alert_type):
        """处理告警"""
        handlers = {
            "load_high": self._fix_high_load,
            "memory_high": self._fix_high_memory,
            "disk_full": self._fix_disk_full,
            "gateway_down": self._restart_gateway
        }
        
        handler = handlers.get(alert_type)
        if handler:
            return handler()
        return {"action": "unknown_alert", "result": "未处理"}
    
    def _fix_high_load(self):
        """高负载处理"""
        # 清理临时文件
        subprocess.run("rm -rf /tmp/* 2>/dev/null || true", shell=True)
        return {"action": "cleanup_temp", "result": "已清理临时文件"}
    
    def _fix_high_memory(self):
        """高内存处理"""
        # 清理缓存
        subprocess.run("sync && echo 3 > /proc/sys/vm/drop_caches", shell=True)
        return {"action": "clear_cache", "result": "已清理缓存"}
    
    def _fix_disk_full(self):
        """磁盘满处理"""
        # 清理日志
        subprocess.run("find /var/log -name '*.log' -mtime +7 -delete 2>/dev/null || true", shell=True)
        return {"action": "clean_logs", "result": "已清理7天前日志"}
    
    def _restart_gateway(self):
        """重启Gateway"""
        subprocess.run("openclaw gateway restart", shell=True)
        return {"action": "restart_gateway", "result": "已重启Gateway"}
    
    def run(self):
        """运行executor"""
        tasks = self.get_pending_tasks()
        
        if not tasks:
            print("[Executor] 无待处理任务")
            return []
        
        results = []
        for task in tasks:
            task_id = task["id"]
            message = task["message"]
            
            # 解析告警类型
            msg = message.replace("告警: ", "").strip()
            # 逗号分隔的多个告警，取第一个
            alert_type = msg.split(",")[0].strip()
            
            result = self.handle_alert(alert_type)
            result["task_id"] = task_id
            result["original_alert"] = alert_type
            
            # 完成任务
            self.bus.complete_task(task_id, json.dumps(result))
            results.append(result)
            print(f"[Executor] 处理完成: {alert_type} -> {result['action']}")
        
        return results

if __name__ == "__main__":
    agent = ExecutorAgent()
    agent.run()