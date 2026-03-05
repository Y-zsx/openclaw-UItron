#!/usr/bin/env python3
"""
Task Retry Manager - 任务失败告警与自动重试
功能：
- 监控任务执行状态
- 任务失败时自动发送告警通知
- 自动重试失败的任务（可配置重试次数和间隔）
- 记录重试历史和统计
"""
import json
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import defaultdict
import os

WORKSPACE = "/root/.openclaw/workspace"
RETRY_STATE_FILE = f"{WORKSPACE}/ultron-workflow/retry_state.json"
RETRY_HISTORY_FILE = f"{WORKSPACE}/ultron-workflow/retry_history.json"
ALERT_CONFIG_FILE = f"{WORKSPACE}/ultron-workflow/retry_alert_config.json"

# 默认配置
DEFAULT_CONFIG = {
    "max_retries": 3,
    "retry_interval": 60,  # 秒
    "backoff_multiplier": 2,  # 指数退避
    "alert_on_failure": True,
    "alert_channels": ["dingtalk"],
    "max_concurrent_retries": 5,
    "retry_tasks": ["ultron-life", "ultron-monitor", "ultron-health"]
}

class TaskRetryManager:
    def __init__(self):
        self.state = self._load_state()
        self.config = self._load_config()
        self.history = self._load_history()
        
    def _load_state(self) -> Dict:
        """加载重试状态"""
        if Path(RETRY_STATE_FILE).exists():
            with open(RETRY_STATE_FILE) as f:
                return json.load(f)
        return {
            "failed_tasks": {},
            "retry_queue": [],
            "alert_sent": {},
            "last_check": None
        }
    
    def _save_state(self):
        """保存重试状态"""
        Path(RETRY_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(RETRY_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def _load_config(self) -> Dict:
        """加载告警配置"""
        if Path(ALERT_CONFIG_FILE).exists():
            with open(ALERT_CONFIG_FILE) as f:
                return {**DEFAULT_CONFIG, **json.load(f)}
        return DEFAULT_CONFIG.copy()
    
    def _save_config(self):
        """保存告警配置"""
        Path(ALERT_CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(ALERT_CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def _load_history(self) -> Dict:
        """加载重试历史"""
        if Path(RETRY_HISTORY_FILE).exists():
            with open(RETRY_HISTORY_FILE) as f:
                return json.load(f)
        return {"retries": [], "alerts": []}
    
    def _save_history(self):
        """保存重试历史"""
        Path(RETRY_HISTORY_FILE).parent.mkdir(parents=True, exist_ok=True)
        # 只保留最近1000条记录
        if len(self.history.get("retries", [])) > 1000:
            self.history["retries"] = self.history["retries"][-1000:]
        if len(self.history.get("alerts", [])) > 500:
            self.history["alerts"] = self.history["alerts"][-500:]
        with open(RETRY_HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def check_task_status(self, task_name: str) -> Dict:
        """检查任务状态"""
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list"],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode == 0:
                for line in result.stdout.split('\n'):
                    if task_name in line:
                        # 解析任务状态
                        parts = line.split()
                        if len(parts) >= 3:
                            return {
                                "task_name": task_name,
                                "status": "running" if "running" in line.lower() else "active",
                                "last_run": parts[-1] if parts else "unknown",
                                "found": True
                            }
            
            return {"task_name": task_name, "status": "not_found", "found": False}
        except Exception as e:
            return {"task_name": task_name, "status": "error", "error": str(e)}
    
    def record_failure(self, task_id: str, task_name: str, error: str, 
                       task_type: str = "cron") -> Dict:
        """记录任务失败"""
        current_time = datetime.now()
        
        if task_id not in self.state["failed_tasks"]:
            self.state["failed_tasks"][task_id] = {
                "task_name": task_name,
                "task_type": task_type,
                "first_failure": current_time.isoformat(),
                "failure_count": 0,
                "retry_count": 0,
                "last_error": error,
                "alerts_sent": 0
            }
        
        failed_task = self.state["failed_tasks"][task_id]
        failed_task["last_failure"] = current_time.isoformat()
        failed_task["failure_count"] += 1
        failed_task["last_error"] = error
        
        # 检查是否需要发送告警
        if self.config["alert_on_failure"]:
            self._send_alert(task_id, task_name, error, failed_task)
        
        # 加入重试队列
        self._queue_for_retry(task_id, task_name, failed_task)
        
        self._save_state()
        
        return {
            "task_id": task_id,
            "task_name": task_name,
            "failure_count": failed_task["failure_count"],
            "queued_for_retry": True
        }
    
    def _send_alert(self, task_id: str, task_name: str, error: str, 
                    task_info: Dict) -> bool:
        """发送告警通知"""
        # 防止重复告警（5分钟内不重复）
        alert_key = f"{task_id}:{datetime.now().strftime('%Y%m%d%H%M')[:12]}"
        
        if alert_key in self.state.get("alert_sent", {}):
            last_alert = self.state["alert_sent"][alert_key]
            if (datetime.now() - datetime.fromisoformat(last_alert)).total_seconds() < 300:
                return False
        
        # 构建告警消息
        alert_msg = f"""🔴 任务执行失败告警

任务: {task_name}
任务ID: {task_id}
失败次数: {task_info.get('failure_count', 1)}
首次失败: {task_info.get('first_failure', 'N/A')}
错误信息: {error[:200]}
重试次数: {task_info.get('retry_count', 0)}

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        
        # 记录告警
        self.history["alerts"].append({
            "task_id": task_id,
            "task_name": task_name,
            "error": error,
            "time": datetime.now().isoformat()
        })
        
        self.state["alert_sent"][alert_key] = datetime.now().isoformat()
        
        # 发送告警到配置的渠道
        self._dispatch_alert(alert_msg)
        
        return True
    
    def _dispatch_alert(self, message: str):
        """分发告警到各渠道"""
        for channel in self.config.get("alert_channels", []):
            try:
                if channel == "dingtalk":
                    # 使用 OpenClaw 发送钉钉消息
                    subprocess.run(
                        ["openclaw", "message", "--channel", "dingtalk", "--message", message],
                        capture_output=True, timeout=10
                    )
            except Exception as e:
                print(f"   ⚠️ 告警发送失败 ({channel}): {e}")
    
    def _queue_for_retry(self, task_id: str, task_name: str, task_info: Dict):
        """将任务加入重试队列"""
        max_retries = self.config["max_retries"]
        current_retry = task_info.get("retry_count", 0)
        
        if current_retry >= max_retries:
            task_info["status"] = "max_retries_exceeded"
            return
        
        # 计算重试延迟（指数退避）
        retry_delay = self.config["retry_interval"] * (
            self.config["backoff_multiplier"] ** current_retry
        )
        
        retry_entry = {
            "task_id": task_id,
            "task_name": task_name,
            "retry_count": current_retry + 1,
            "scheduled_time": (datetime.now() + timedelta(seconds=retry_delay)).isoformat(),
            "task_type": task_info.get("task_type", "cron"),
            "last_error": task_info.get("last_error", "")
        }
        
        # 更新任务信息
        task_info["retry_count"] = current_retry + 1
        task_info["status"] = "queued"
        task_info["next_retry"] = retry_entry["scheduled_time"]
        
        # 添加到队列
        self.state["retry_queue"].append(retry_entry)
        
        # 记录历史
        self.history["retries"].append({
            "task_id": task_id,
            "task_name": task_name,
            "retry_number": current_retry + 1,
            "scheduled_time": retry_entry["scheduled_time"],
            "time": datetime.now().isoformat()
        })
    
    def process_retry_queue(self) -> Dict:
        """处理重试队列"""
        current_time = datetime.now()
        processed = []
        failed_again = []
        
        queue = self.state["retry_queue"]
        new_queue = []
        
        for entry in queue:
            scheduled_time = datetime.fromisoformat(entry["scheduled_time"])
            
            if scheduled_time <= current_time:
                # 可以重试
                result = self._execute_retry(entry)
                
                if result["success"]:
                    processed.append({
                        "task_id": entry["task_id"],
                        "task_name": entry["task_name"],
                        "retry_count": entry["retry_count"],
                        "result": "success"
                    })
                    # 从失败任务中清除
                    if entry["task_id"] in self.state["failed_tasks"]:
                        del self.state["failed_tasks"][entry["task_id"]]
                else:
                    failed_again.append({
                        "task_id": entry["task_id"],
                        "task_name": entry["task_name"],
                        "error": result.get("error", "unknown")
                    })
                    # 重新加入队列
                    new_queue.append(entry)
            else:
                # 还未到重试时间
                new_queue.append(entry)
        
        self.state["retry_queue"] = new_queue
        self.state["last_check"] = current_time.isoformat()
        self._save_state()
        self._save_history()
        
        return {
            "processed": len(processed),
            "failed_again": len(failed_again),
            "pending": len(new_queue),
            "details": {
                "success": processed,
                "failed": failed_again
            }
        }
    
    def _execute_retry(self, retry_entry: Dict) -> Dict:
        """执行重试"""
        task_name = retry_entry["task_name"]
        task_type = retry_entry.get("task_type", "cron")
        
        try:
            if task_type == "cron":
                # 对于 cron 任务，尝试重新触发
                result = subprocess.run(
                    ["openclaw", "cron", "run", task_name],
                    capture_output=True, text=True, timeout=30
                )
                
                if result.returncode == 0:
                    return {"success": True, "message": "Task restarted"}
                else:
                    return {"success": False, "error": result.stderr}
            else:
                return {"success": False, "error": "Unknown task type"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_failed_tasks(self) -> List[Dict]:
        """获取失败任务列表"""
        return [
            {
                "task_id": task_id,
                "task_name": info["task_name"],
                "failure_count": info.get("failure_count", 0),
                "retry_count": info.get("retry_count", 0),
                "last_failure": info.get("last_failure"),
                "last_error": info.get("last_error", "")[:100],
                "status": info.get("status", "failed")
            }
            for task_id, info in self.state.get("failed_tasks", {}).items()
        ]
    
    def get_retry_stats(self) -> Dict:
        """获取重试统计"""
        total_retries = sum(
            info.get("retry_count", 0) 
            for info in self.state.get("failed_tasks", {}).values()
        )
        
        total_alerts = len(self.history.get("alerts", []))
        
        return {
            "failed_tasks": len(self.state.get("failed_tasks", {})),
            "pending_retries": len(self.state.get("retry_queue", [])),
            "total_retries": total_retries,
            "total_alerts": total_alerts,
            "max_retries_config": self.config.get("max_retries"),
            "alert_channels": self.config.get("alert_channels")
        }
    
    def clear_resolved(self, task_id: str = None):
        """清除已解决的任务"""
        if task_id:
            if task_id in self.state["failed_tasks"]:
                del self.state["failed_tasks"][task_id]
        else:
            # 清除所有已解决的任务
            resolved = [
                tid for tid, info in self.state["failed_tasks"].items()
                if info.get("retry_count", 0) >= self.config.get("max_retries", 3)
            ]
            for tid in resolved:
                del self.state["failed_tasks"][tid]
        
        self._save_state()
        return {"cleared": task_id or "all_resolved"}
    
    def update_config(self, new_config: Dict):
        """更新配置"""
        self.config = {**self.config, **new_config}
        self._save_config()
        return {"status": "updated", "config": self.config}
    
    def run(self) -> Dict:
        """运行重试管理器"""
        # 1. 检查关键任务状态
        critical_tasks = self.config.get("retry_tasks", [])
        checked = []
        
        for task_name in critical_tasks:
            status = self.check_task_status(task_name)
            checked.append(status)
            
            # 如果任务不活跃，记录失败
            if not status.get("found"):
                self.record_failure(
                    task_id=f"missing_{task_name}",
                    task_name=task_name,
                    error=f"Task not found in cron list",
                    task_type="cron"
                )
        
        # 2. 处理重试队列
        retry_result = self.process_retry_queue()
        
        # 3. 获取统计
        stats = self.get_retry_stats()
        
        return {
            "checked_tasks": len(checked),
            "task_statuses": checked,
            "retry_result": retry_result,
            "stats": stats,
            "timestamp": datetime.now().isoformat()
        }


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Task Retry Manager")
    parser.add_argument("command", choices=["run", "status", "config", "clear"],
                       help="Command to execute")
    parser.add_argument("--task-id", help="Task ID for clear command")
    parser.add_argument("--max-retries", type=int, help="Max retries setting")
    parser.add_argument("--retry-interval", type=int, help="Retry interval in seconds")
    
    args = parser.parse_args()
    manager = TaskRetryManager()
    
    if args.command == "run":
        result = manager.run()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "status":
        failed = manager.get_failed_tasks()
        stats = manager.get_retry_stats()
        print(json.dumps({
            "failed_tasks": failed,
            "stats": stats
        }, indent=2, ensure_ascii=False))
    
    elif args.command == "config":
        if args.max_retries or args.retry_interval:
            new_config = {}
            if args.max_retries:
                new_config["max_retries"] = args.max_retries
            if args.retry_interval:
                new_config["retry_interval"] = args.retry_interval
            result = manager.update_config(new_config)
            print(json.dumps(result, indent=2))
        else:
            print(json.dumps(manager.config, indent=2))
    
    elif args.command == "clear":
        result = manager.clear_resolved(args.task_id)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()