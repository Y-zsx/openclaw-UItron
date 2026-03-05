"""
任务调度器 (Scheduler)
=========================
根据依赖关系和时间安排调度任务执行。

功能:
- 从任务图获取可执行任务
- 管理任务执行间隔
- 创建cron任务
"""

import json
import subprocess
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional
import yaml


class Scheduler:
    """任务调度器"""
    
    def __init__(self, config_path: str, task_graph=None):
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        
        self.task_graph = task_graph  # 外部传入
        self.intervals = {}  # task_id -> 下次执行时间
        
    def set_graph(self, graph):
        """设置任务图"""
        self.task_graph = graph
    
    def should_run(self, task_id: str) -> bool:
        """检查任务是否应该执行"""
        if task_id not in self.intervals:
            return True
        
        next_time = self.intervals[task_id]
        return datetime.now() >= next_time
    
    def set_next_run(self, task_id: str, interval_seconds: int = None):
        """设置下次执行时间"""
        if interval_seconds is None:
            interval_seconds = self.config["tasks"]["default_interval"]
        
        self.intervals[task_id] = datetime.now() + timedelta(seconds=interval_seconds)
    
    def get_scheduled_tasks(self) -> list:
        """获取需要执行的任务列表"""
        if not self.task_graph:
            return []
        
        scheduled = []
        next_task = self.task_graph.get_next_task()
        
        while next_task and self.should_run(next_task.id):
            # 标记为运行中，避免重复返回
            self.task_graph.start_task(next_task.id)
            scheduled.append(next_task)
            # 获取下一个（可能有多个ready）
            next_task = self.task_graph.get_next_task()
        
        return scheduled
    
    def create_cron_for_task(self, task_id: str, message: str) -> str:
        """为任务创建cron"""
        # 使用 openclaw cron add
        cmd = [
            "openclaw", "cron", "add",
            "--name", f"ultron-v4-{task_id}",
            "--every", "5m",
            "--message", message,
            "--session", "isolated",
            "--expect-final"
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout.strip()
    
    def run(self):
        """主循环"""
        print(f"[Scheduler] 检查任务队列...")
        tasks = self.get_scheduled_tasks()
        
        if not tasks:
            print(f"[Scheduler] 无待执行任务")
            return
        
        for task in tasks:
            print(f"[Scheduler] 调度任务: {task.name}")
            # 标记开始
            self.task_graph.start_task(task.id)
            
            # TODO: 调用执行器执行任务
            # executor.run(task)
            
            # 模拟执行完成
            self.task_graph.complete_task(task.id, result="执行完成", success=True)
            
            # 设置下次执行
            self.set_next_run(task.id)
        
        print(f"[Scheduler] 完成 {len(tasks)} 个任务")


if __name__ == "__main__":
    scheduler = Scheduler("/root/.openclaw/workspace/ultron-workflow-v4/config/settings.yaml")
    scheduler.run()