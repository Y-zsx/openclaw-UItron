#!/usr/bin/env python3
"""
任务执行监控与日志模块
监控Agent任务执行状态，记录详细日志
"""

import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import uuid

class TaskMonitor:
    """任务执行监控器"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.data_dir = Path(workspace) / "ultron" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.log_file = self.data_dir / "task_execution_log.json"
        self.metrics_file = self.data_dir / "task_metrics.json"
        
        self._load_logs()
        self._load_metrics()
    
    def _load_logs(self):
        """加载执行日志"""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                self.logs = json.load(f)
        else:
            self.logs = {"executions": []}
    
    def _save_logs(self):
        """保存执行日志"""
        with open(self.log_file, 'w') as f:
            json.dump(self.logs, f, indent=2, ensure_ascii=False)
    
    def _load_metrics(self):
        """加载指标"""
        if self.metrics_file.exists():
            with open(self.metrics_file, 'r') as f:
                self.metrics = json.load(f)
        else:
            self.metrics = {
                "total_executions": 0,
                "by_status": {},
                "by_agent": {},
                "avg_duration": 0,
                "total_duration": 0,
                "last_updated": None
            }
    
    def _save_metrics(self):
        """保存指标"""
        with open(self.metrics_file, 'w') as f:
            json.dump(self.metrics, f, indent=2, ensure_ascii=False)
    
    def log_execution(
        self,
        execution_id: str,
        task: str,
        agent_id: str,
        status: str,
        start_time: str,
        end_time: Optional[str] = None,
        duration: Optional[float] = None,
        error: Optional[str] = None,
        stdout: Optional[str] = None,
        stderr: Optional[str] = None
    ):
        """记录任务执行"""
        log_entry = {
            "execution_id": execution_id,
            "task": task,
            "agent_id": agent_id,
            "status": status,
            "start_time": start_time,
            "end_time": end_time,
            "duration": duration,
            "error": error,
            "timestamp": datetime.now().isoformat()
        }
        
        # 添加到日志
        self.logs["executions"].append(log_entry)
        
        # 只保留最近1000条
        if len(self.logs["executions"]) > 1000:
            self.logs["executions"] = self.logs["executions"][-1000:]
        
        self._save_logs()
        
        # 更新指标
        self._update_metrics(
            agent_id=agent_id,
            status=status,
            duration=duration
        )
    
    def _update_metrics(self, agent_id: str, status: str, duration: Optional[float]):
        """更新指标"""
        self.metrics["total_executions"] += 1
        
        # 按状态统计
        if status not in self.metrics["by_status"]:
            self.metrics["by_status"][status] = 0
        self.metrics["by_status"][status] += 1
        
        # 按Agent统计
        if agent_id not in self.metrics["by_agent"]:
            self.metrics["by_agent"][agent_id] = {"total": 0, "completed": 0, "failed": 0}
        self.metrics["by_agent"][agent_id]["total"] += 1
        if status == "completed":
            self.metrics["by_agent"][agent_id]["completed"] += 1
        elif status in ("failed", "error", "timeout"):
            self.metrics["by_agent"][agent_id]["failed"] += 1
        
        # 平均执行时间
        if duration:
            old_total = self.metrics["total_duration"]
            old_count = self.metrics["total_executions"] - 1
            if old_count > 0:
                new_total = old_total + duration
                self.metrics["total_duration"] = new_total
                self.metrics["avg_duration"] = new_total / self.metrics["total_executions"]
            else:
                self.metrics["total_duration"] = duration
                self.metrics["avg_duration"] = duration
        
        self.metrics["last_updated"] = datetime.now().isoformat()
        self._save_metrics()
    
    def get_executions(
        self,
        agent_id: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """获取执行记录"""
        executions = self.logs["executions"]
        
        if agent_id:
            executions = [e for e in executions if e.get("agent_id") == agent_id]
        if status:
            executions = [e for e in executions if e.get("status") == status]
        
        return executions[-limit:]
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取监控指标"""
        return self.metrics
    
    def get_running_tasks(self) -> List[Dict[str, Any]]:
        """获取正在运行的任务"""
        return [
            e for e in self.logs["executions"]
            if e.get("status") == "running"
        ]
    
    def get_failed_tasks(
        self,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """获取失败的任务"""
        cutoff = datetime.now() - timedelta(hours=hours)
        failed = []
        
        for e in self.logs["executions"]:
            if e.get("status") in ("failed", "error", "timeout"):
                try:
                    exec_time = datetime.fromisoformat(e.get("start_time", ""))
                    if exec_time >= cutoff:
                        failed.append(e)
                except:
                    pass
        
        return failed
    
    def get_success_rate(self, hours: int = 24) -> Dict[str, float]:
        """获取成功率"""
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = []
        
        for e in self.logs["executions"]:
            try:
                exec_time = datetime.fromisoformat(e.get("start_time", ""))
                if exec_time >= cutoff:
                    recent.append(e)
            except:
                pass
        
        if not recent:
            return {"success_rate": 0, "total": 0, "completed": 0, "failed": 0}
        
        completed = sum(1 for e in recent if e.get("status") == "completed")
        failed = sum(1 for e in recent if e.get("status") in ("failed", "error", "timeout"))
        
        total = completed + failed
        success_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "success_rate": round(success_rate, 2),
            "total": total,
            "completed": completed,
            "failed": failed
        }
    
    def get_duration_stats(self, hours: int = 24) -> Dict[str, float]:
        """获取执行时间统计"""
        cutoff = datetime.now() - timedelta(hours=hours)
        durations = []
        
        for e in self.logs["executions"]:
            if e.get("status") == "completed" and e.get("duration"):
                try:
                    exec_time = datetime.fromisoformat(e.get("start_time", ""))
                    if exec_time >= cutoff:
                        durations.append(e["duration"])
                except:
                    pass
        
        if not durations:
            return {"avg": 0, "min": 0, "max": 0, "count": 0}
        
        return {
            "avg": round(sum(durations) / len(durations), 2),
            "min": round(min(durations), 2),
            "max": round(max(durations), 2),
            "count": len(durations)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """获取监控摘要"""
        return {
            "metrics": self.get_metrics(),
            "success_rate_24h": self.get_success_rate(24),
            "duration_stats_24h": self.get_duration_stats(24),
            "running_tasks": len(self.get_running_tasks()),
            "failed_tasks_24h": len(self.get_failed_tasks(24))
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="任务执行监控")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 记录执行
    log_parser = subparsers.add_parser("log", help="记录任务执行")
    log_parser.add_argument("--execution-id", required=True)
    log_parser.add_argument("--task", required=True)
    log_parser.add_argument("--agent-id", required=True)
    log_parser.add_argument("--status", required=True)
    log_parser.add_argument("--start-time", required=True)
    log_parser.add_argument("--end-time")
    log_parser.add_argument("--duration", type=float)
    log_parser.add_argument("--error")
    
    # 查看日志
    subparsers.add_parser("list", help="列出执行日志")
    list_parser = subparsers.add_parser("list", help="列出执行日志")
    list_parser.add_argument("--agent-id")
    list_parser.add_argument("--status")
    list_parser.add_argument("--limit", type=int, default=20)
    
    # 指标
    subparsers.add_parser("metrics", help="查看监控指标")
    
    # 摘要
    subparsers.add_parser("summary", help="查看监控摘要")
    
    # 成功率
    rate_parser = subparsers.add_parser("rate", help="查看成功率")
    rate_parser.add_argument("--hours", type=int, default=24)
    
    args = parser.parse_args()
    
    monitor = TaskMonitor()
    
    if args.command == "log":
        monitor.log_execution(
            execution_id=args.execution_id,
            task=args.task,
            agent_id=args.agent_id,
            status=args.status,
            start_time=args.start_time,
            end_time=args.end_time,
            duration=args.duration,
            error=args.error
        )
        print("Execution logged")
        
    elif args.command == "list":
        results = monitor.get_executions(
            agent_id=args.agent_id,
            status=args.status,
            limit=args.limit
        )
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif args.command == "metrics":
        results = monitor.get_metrics()
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif args.command == "summary":
        results = monitor.get_summary()
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif args.command == "rate":
        results = monitor.get_success_rate(args.hours)
        print(json.dumps(results, indent=2, ensure_ascii=False))
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()