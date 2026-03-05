#!/usr/bin/env python3
"""
定时任务自动调度器
功能：动态管理cron任务、监控执行状态、自动调整执行间隔
"""
import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = "/root/.openclaw/workspace"
SCHEDULER_STATE = f"{WORKSPACE}/ultron-workflow/scheduler_state.json"

class TaskScheduler:
    def __init__(self):
        self.state = self.load_state()
    
    def load_state(self):
        if os.path.exists(SCHEDULER_STATE):
            with open(SCHEDULER_STATE, 'r') as f:
                return json.load(f)
        return {
            "tasks": {},
            "last_scan": None,
            "adjustments": []
        }
    
    def save_state(self):
        with open(SCHEDULER_STATE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def get_cron_tasks(self):
        """获取所有活跃的cron任务"""
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return self._parse_cron_text(result.stdout)
            return []
        except Exception as e:
            print(f"获取cron任务失败: {e}")
            return []
    
    def _parse_cron_text(self, text):
        """解析cron列表文本输出"""
        tasks = []
        lines = text.strip().split('\n')
        for line in lines:
            if line.strip() and not line.startswith('ID') and not line.startswith('─'):
                tasks.append({"raw": line, "id": line.split()[0] if line.split() else "unknown"})
        return tasks
    
    def analyze_task_health(self, task_id):
        """分析任务健康状态"""
        # 模拟：检查任务执行历史
        # 实际可以从日志系统获取
        return {
            "task_id": task_id,
            "status": "healthy",
            "last_execution": datetime.now().isoformat(),
            "avg_duration": 0,
            "error_count": 0
        }
    
    def should_adjust_interval(self, task_id, current_interval):
        """判断是否需要调整执行间隔"""
        health = self.analyze_task_health(task_id)
        
        # 简单策略：错误多时缩短间隔，健康时保持
        # 只在异常情况下调整，避免频繁修改
        if health.get("error_count", 0) > 3:
            return max(1, current_interval - 1), "错误过多，加速"
        
        return current_interval, "无需调整"  # 默认不调整，保持稳定
    
    def scan_and_adjust(self):
        """扫描并调整任务"""
        tasks = self.get_cron_tasks()
        self.state["last_scan"] = datetime.now().isoformat()
        
        adjustments = []
        for task in tasks:
            task_id = task.get("id", task.get("raw", "unknown"))
            # 分析并调整
            current_interval = task.get("interval", 3)
            new_interval, reason = self.should_adjust_interval(task_id, current_interval)
            
            if new_interval != current_interval:
                adjustments.append({
                    "task_id": task_id,
                    "old_interval": current_interval,
                    "new_interval": new_interval,
                    "reason": reason,
                    "time": datetime.now().isoformat()
                })
        
        self.state["adjustments"] = adjustments
        self.state["tasks_scanned"] = len(tasks)
        self.save_state()
        
        return {
            "scanned": len(tasks),
            "adjustments": adjustments,
            "timestamp": datetime.now().isoformat()
        }
    
    def run(self):
        """运行调度器"""
        result = self.scan_and_adjust()
        
        print(f"✅ 任务调度器扫描完成")
        print(f"   扫描任务数: {result['scanned']}")
        print(f"   调整数: {len(result['adjustments'])}")
        
        if result['adjustments']:
            for adj in result['adjustments']:
                print(f"   - {adj['task_id']}: {adj['old_interval']}m → {adj['new_interval']}m ({adj['reason']})")
        
        return result

if __name__ == "__main__":
    scheduler = TaskScheduler()
    result = scheduler.run()
    print(json.dumps(result, indent=2))