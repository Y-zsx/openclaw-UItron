#!/usr/bin/env python3
"""Agent协作优化器"""
import json
import time
from pathlib import Path
from datetime import datetime, timedelta

class AgentOptimizer:
    def __init__(self):
        self.stats_file = Path(__file__).parent / "agent_stats.json"
        self.load_stats()
    
    def load_stats(self):
        if self.stats_file.exists():
            self.stats = json.loads(self.stats_file.read_text())
        else:
            self.stats = {
                "messages": 0,
                "tasks_completed": 0,
                "tasks_failed": 0,
                "avg_response_time": 0,
                "last_optimization": None
            }
    
    def save_stats(self):
        self.stats_file.write_text(json.dumps(self.stats, indent=2, ensure_ascii=False))
    
    def record_message(self, agent: str):
        """记录消息"""
        self.stats["messages"] += 1
        self.save_stats()
    
    def record_task(self, success: bool, response_time: float = 0):
        """记录任务执行"""
        if success:
            self.stats["tasks_completed"] += 1
        else:
            self.stats["tasks_failed"] += 1
        
        # 更新平均响应时间
        if response_time > 0:
            old_avg = self.stats["avg_response_time"]
            total = self.stats["tasks_completed"] + self.stats["tasks_failed"]
            self.stats["avg_response_time"] = (old_avg * (total - 1) + response_time) / total
        
        self.save_stats()
    
    def get_report(self) -> dict:
        """获取优化报告"""
        total_tasks = self.stats["tasks_completed"] + self.stats["tasks_failed"]
        success_rate = (self.stats["tasks_completed"] / total_tasks * 100) if total_tasks > 0 else 0
        
        return {
            "messages_processed": self.stats["messages"],
            "tasks_completed": self.stats["tasks_completed"],
            "tasks_failed": self.stats["tasks_failed"],
            "success_rate": round(success_rate, 1),
            "avg_response_time": round(self.stats["avg_response_time"], 3),
            "last_optimization": self.stats.get("last_optimization")
        }
    
    def optimize(self):
        """执行优化"""
        self.stats["last_optimization"] = datetime.now().isoformat()
        self.save_stats()
        return self.get_report()

if __name__ == "__main__":
    opt = AgentOptimizer()
    opt.record_message("monitor")
    opt.record_message("orchestrator")
    opt.record_task(True, 0.5)
    opt.record_task(True, 0.3)
    print("优化器测试通过")
    print(json.dumps(opt.get_report(), indent=2))