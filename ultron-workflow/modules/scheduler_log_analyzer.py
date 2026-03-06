#!/usr/bin/env python3
"""
调度任务执行日志分析器
Scheduler Task Execution Log Analyzer
"""

import json
import os
import re
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

LOG_DIR = Path("/root/.openclaw/workspace/ultron-workflow/logs")
ANALYSIS_FILE = LOG_DIR / "scheduler_log_analysis.json"

# 日志文件映射
LOG_FILES = {
    "scheduler_daemon": "scheduler_daemon.log",
}


class SchedulerLogAnalyzer:
    def __init__(self):
        self.logs = {}
        self.stats = {
            "total_executions": 0,
            "successful_executions": 0,
            "failed_executions": 0,
            "by_task": defaultdict(lambda: {"success": 0, "fail": 0, "total": 0}),
            "hourly_stats": defaultdict(lambda: {"success": 0, "fail": 0}),
            "last_24h": [],
        }
    
    def parse_log_line(self, line, log_type):
        """解析单行日志"""
        # 匹配格式: 2026-03-06T08:28:15.870854 - 任务描述
        pattern = r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*(.+)"
        match = re.match(pattern, line)
        if not match:
            return None
        
        timestamp_str, message = match.groups()
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        
        # 提取任务执行结果
        result = {
            "timestamp": timestamp.isoformat(),
            "message": message.strip(),
            "log_type": log_type,
        }
        
        # 检测执行结果
        if "完成: returncode=0" in message or "OK:" in message:
            result["status"] = "success"
        elif "完成: returncode=" in message:
            result["status"] = "failed"
            result["returncode"] = int(re.search(r"returncode=(\d+)", message).group(1))
        elif "WARNING:" in message:
            result["status"] = "warning"
        elif "ERROR" in message or "失败" in message:
            result["status"] = "error"
        
        # 提取任务名称
        task_match = re.search(r"执行任务:\s*(\w+)", message)
        if task_match:
            result["task"] = task_match.group(1)
        
        return result
    
    def load_logs(self):
        """加载所有日志文件"""
        for log_type, filename in LOG_FILES.items():
            filepath = LOG_DIR / filename
            if filepath.exists():
                with open(filepath, 'r') as f:
                    lines = f.readlines()
                    self.logs[log_type] = []
                    for line in lines:
                        parsed = self.parse_log_line(line.strip(), log_type)
                        if parsed:
                            self.logs[log_type].append(parsed)
    
    def analyze(self):
        """执行分析"""
        now = datetime.now()
        last_24h = now - timedelta(hours=24)
        
        # 按日志类型分别处理，维护当前任务上下文
        for log_type, entries in self.logs.items():
            current_task = None  # 当前正在执行的任务
            
            for entry in entries:
                entry_time = datetime.fromisoformat(entry["timestamp"].replace("Z", "+00:00"))
                message = entry.get("message", "")
                
                # 任务执行开始
                if "执行任务:" in message:
                    current_task = entry.get("task")
                    if current_task:
                        self.stats["total_executions"] += 1
                        self.stats["by_task"][current_task]["total"] += 1
                
                # 任务完成 - 关联到当前任务
                if "完成:" in message and current_task:
                    status = entry.get("status")
                    if status == "success":
                        self.stats["successful_executions"] += 1
                        self.stats["by_task"][current_task]["success"] += 1
                    elif status in ("failed", "error"):
                        self.stats["failed_executions"] += 1
                        self.stats["by_task"][current_task]["fail"] += 1
                    current_task = None  # 重置
                
                # 健康检查单独处理 (从health_scheduler.log)
                if log_type == "health_scheduler":
                    if "OK:" in message:
                        self.stats["by_task"]["health_check"]["success"] += 1
                        self.stats["successful_executions"] += 1
                    elif "WARNING:" in message:
                        self.stats["by_task"]["health_check"]["fail"] += 1
                        self.stats["failed_executions"] += 1
                
                # 24小时内统计
                if entry_time > last_24h:
                    self.stats["last_24h"].append(entry)
                
                # 按小时统计
                hour = entry_time.strftime("%Y-%m-%d %H:00")
                if "执行任务:" in message or "完成:" in message or "OK:" in message:
                    if entry.get("status") == "success":
                        self.stats["hourly_stats"][hour]["success"] += 1
                    elif entry.get("status") in ("failed", "error", "warning"):
                        self.stats["hourly_stats"][hour]["fail"] += 1
        
        # 计算成功率
        if self.stats["total_executions"] > 0:
            self.stats["success_rate"] = round(
                self.stats["successful_executions"] / self.stats["total_executions"] * 100, 2
            )
        else:
            self.stats["success_rate"] = 100.0
        
        # 按任务计算成功率
        for task, data in self.stats["by_task"].items():
            if data["total"] > 0:
                data["success_rate"] = round(data["success"] / data["total"] * 100, 1)
            else:
                data["success_rate"] = 100.0
        
        # 转换为普通dict
        self.stats["by_task"] = dict(self.stats["by_task"])
        self.stats["hourly_stats"] = dict(self.stats["hourly_stats"])
        self.stats["recent_tasks"] = self.get_recent_tasks()
        
        return self.stats
    
    def get_recent_tasks(self, limit=10):
        """获取最近的任务执行"""
        all_tasks = []
        for entries in self.logs.values():
            for entry in entries:
                if "task" in entry:
                    all_tasks.append(entry)
        
        all_tasks.sort(key=lambda x: x["timestamp"], reverse=True)
        return all_tasks[:limit]
    
    def save(self):
        """保存分析结果"""
        with open(ANALYSIS_FILE, 'w') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        return ANALYSIS_FILE
    
    def get_summary(self):
        """获取摘要"""
        return {
            "总执行次数": self.stats["total_executions"],
            "成功次数": self.stats["successful_executions"],
            "失败次数": self.stats["failed_executions"],
            "成功率": f"{self.stats.get('success_rate', 100)}%",
            "24小时执行": len(self.stats["last_24h"]),
        }


def main():
    """主函数"""
    analyzer = SchedulerLogAnalyzer()
    analyzer.load_logs()
    stats = analyzer.analyze()
    analyzer.save()
    
    print("=" * 50)
    print("调度任务执行日志分析")
    print("=" * 50)
    
    summary = analyzer.get_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    print("\n按任务统计:")
    for task, data in stats["by_task"].items():
        success_rate = (data["success"] / data["total"] * 100) if data["total"] > 0 else 100
        print(f"  {task}: 总计{data['total']}, 成功{data['success']}, 失败{data['fail']}, 成功率{success_rate:.1f}%")
    
    print(f"\n详细分析已保存到: {ANALYSIS_FILE}")
    return stats


if __name__ == "__main__":
    main()