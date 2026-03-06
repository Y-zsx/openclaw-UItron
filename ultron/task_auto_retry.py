#!/usr/bin/env python3
"""
任务自动重试模块
实现任务失败后的自动重试机制
"""

import json
import time
import sqlite3
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from collections import defaultdict
import uuid
import asyncio

WORKSPACE = "/root/.openclaw/workspace"
DATA_DIR = Path(WORKSPACE) / "ultron" / "data"


class TaskAutoRetry:
    """任务自动重试器"""
    
    def __init__(
        self,
        workspace: str = WORKSPACE,
        max_retries: int = 5,
        base_delay: int = 30,  # 基础延迟秒数
        max_delay: int = 300,  # 最大延迟秒数
        exponential_backoff: bool = True,
        jitter: bool = True
    ):
        self.workspace = workspace
        self.data_dir = Path(workspace) / "ultron" / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_backoff = exponential_backoff
        self.jitter = jitter
        
        self.db_path = self.data_dir / "task_retry.db"
        self._init_db()
        
        # 重试任务队列
        self.pending_retries: Dict[str, Dict] = {}
        
        # 执行回调
        self.execute_callback: Optional[Callable] = None
        
        # 重试统计
        self.stats = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "abandoned": 0
        }
        
        # 后台调度器
        self.scheduler_thread: Optional[threading.Thread] = None
        self.running = False
        
        self._load_stats()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 重试任务表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retry_tasks (
                task_id TEXT PRIMARY KEY,
                original_task_id TEXT,
                agent_id TEXT NOT NULL,
                task_data TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                max_retries INTEGER DEFAULT 5,
                status TEXT DEFAULT 'pending',
                scheduled_at TEXT,
                last_attempt TEXT,
                created_at TEXT NOT NULL,
                completed_at TEXT,
                error TEXT
            )
        """)
        
        # 重试历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retry_history (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL,
                attempt_number INTEGER NOT NULL,
                status TEXT NOT NULL,
                error TEXT,
                duration REAL,
                created_at TEXT NOT NULL
            )
        """)
        
        # 配置表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS retry_config (
                task_pattern TEXT PRIMARY KEY,
                max_retries INTEGER,
                base_delay INTEGER,
                enabled INTEGER DEFAULT 1
            )
        """)
        
        conn.commit()
        conn.close()
    
    def _load_stats(self):
        """加载统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM retry_history WHERE status = 'success'")
        self.stats["successful_retries"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM retry_history WHERE status = 'failed'")
        self.stats["failed_retries"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM retry_tasks WHERE status = 'abandoned'")
        self.stats["abandoned"] = cursor.fetchone()[0]
        
        self.stats["total_retries"] = (
            self.stats["successful_retries"] + 
            self.stats["failed_retries"] + 
            self.stats["abandoned"]
        )
        
        conn.close()
    
    def set_execute_callback(self, callback: Callable):
        """设置任务执行回调"""
        self.execute_callback = callback
    
    def _calculate_delay(self, retry_count: int) -> int:
        """计算重试延迟"""
        if self.exponential_backoff:
            delay = self.base_delay * (2 ** retry_count)
        else:
            delay = self.base_delay
        
        # 限制最大延迟
        delay = min(delay, self.max_delay)
        
        # 添加抖动
        if self.jitter:
            import random
            delay = delay * (0.5 + random.random() * 0.5)
        
        return int(delay)
    
    def schedule_retry(
        self,
        task_id: str,
        agent_id: str,
        task_data: Dict,
        retry_count: int = 0,
        max_retries: int = None,
        delay: int = None
    ) -> str:
        """安排重试"""
        if max_retries is None:
            max_retries = self.max_retries
        
        if delay is None:
            delay = self._calculate_delay(retry_count)
        
        scheduled_at = datetime.now() + timedelta(seconds=delay)
        
        retry_id = str(uuid.uuid4())
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO retry_tasks 
            (task_id, agent_id, task_data, retry_count, max_retries, status, scheduled_at, created_at)
            VALUES (?, ?, ?, ?, ?, 'pending', ?, ?)
        """, (
            task_id,
            agent_id,
            json.dumps(task_data),
            retry_count,
            max_retries,
            scheduled_at.isoformat(),
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # 添加到内存队列
        self.pending_retries[task_id] = {
            "retry_id": retry_id,
            "task_id": task_id,
            "agent_id": agent_id,
            "task_data": task_data,
            "retry_count": retry_count,
            "max_retries": max_retries,
            "scheduled_at": scheduled_at,
            "status": "pending"
        }
        
        return retry_id
    
    def cancel_retry(self, task_id: str) -> bool:
        """取消重试"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM retry_tasks WHERE task_id = ?", (task_id,))
        affected = cursor.rowcount
        
        conn.commit()
        conn.close()
        
        if task_id in self.pending_retries:
            del self.pending_retries[task_id]
        
        return affected > 0
    
    def get_retry_status(self, task_id: str) -> Optional[Dict]:
        """获取重试状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, agent_id, retry_count, max_retries, status, 
                   scheduled_at, last_attempt, error, created_at
            FROM retry_tasks WHERE task_id = ?
        """, (task_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return {
            "task_id": row[0],
            "agent_id": row[1],
            "retry_count": row[2],
            "max_retries": row[3],
            "status": row[4],
            "scheduled_at": row[5],
            "last_attempt": row[6],
            "error": row[7],
            "created_at": row[8]
        }
    
    def get_pending_retries(self) -> List[Dict]:
        """获取待重试任务"""
        now = datetime.now()
        result = []
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT task_id, agent_id, task_data, retry_count, max_retries, scheduled_at
            FROM retry_tasks 
            WHERE status = 'pending' AND scheduled_at <= ?
            ORDER BY scheduled_at
        """, (now.isoformat(),))
        
        for row in cursor.fetchall():
            result.append({
                "task_id": row[0],
                "agent_id": row[1],
                "task_data": json.loads(row[2]),
                "retry_count": row[3],
                "max_retries": row[4],
                "scheduled_at": row[5]
            })
        
        conn.close()
        return result
    
    def record_attempt(
        self,
        task_id: str,
        attempt_number: int,
        status: str,
        error: str = None,
        duration: float = None
    ):
        """记录重试尝试"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 更新任务状态
        if status == "success":
            cursor.execute("""
                UPDATE retry_tasks 
                SET status = 'completed', completed_at = ?, last_attempt = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), task_id))
        elif status == "failed":
            cursor.execute("""
                UPDATE retry_tasks 
                SET last_attempt = ?, error = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), error, task_id))
        elif status == "abandoned":
            cursor.execute("""
                UPDATE retry_tasks 
                SET status = 'abandoned', completed_at = ?, last_attempt = ?, error = ?
                WHERE task_id = ?
            """, (datetime.now().isoformat(), datetime.now().isoformat(), error, task_id))
        
        # 记录历史
        cursor.execute("""
            INSERT INTO retry_history (id, task_id, attempt_number, status, error, duration, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()),
            task_id,
            attempt_number,
            status,
            error,
            duration,
            datetime.now().isoformat()
        ))
        
        conn.commit()
        conn.close()
        
        # 更新统计
        self.stats["total_retries"] += 1
        if status == "success":
            self.stats["successful_retries"] += 1
        elif status == "failed":
            self.stats["failed_retries"] += 1
        elif status == "abandoned":
            self.stats["abandoned"] += 1
    
    def execute_retry(self, task_info: Dict) -> Dict:
        """执行重试任务"""
        task_id = task_info["task_id"]
        agent_id = task_info["agent_id"]
        task_data = task_info["task_data"]
        retry_count = task_info["retry_count"]
        
        start_time = time.time()
        
        try:
            # 调用执行回调
            if self.execute_callback:
                result = self.execute_callback(
                    task_id=task_id,
                    agent_id=agent_id,
                    task_data=task_data,
                    retry_count=retry_count
                )
            else:
                result = {"status": "no_callback", "message": "No execute callback set"}
            
            duration = time.time() - start_time
            
            if result.get("success", False):
                self.record_attempt(task_id, retry_count + 1, "success", duration=duration)
                if task_id in self.pending_retries:
                    del self.pending_retries[task_id]
                return {"success": True, "result": result}
            else:
                error = result.get("error", "Unknown error")
                self.record_attempt(task_id, retry_count + 1, "failed", error=error, duration=duration)
                
                # 检查是否需要继续重试
                if retry_count + 1 < task_info["max_retries"]:
                    # 安排下一次重试
                    self.schedule_retry(
                        task_id=task_id,
                        agent_id=agent_id,
                        task_data=task_data,
                        retry_count=retry_count + 1,
                        max_retries=task_info["max_retries"]
                    )
                else:
                    self.record_attempt(
                        task_id, 
                        retry_count + 1, 
                        "abandoned", 
                        error=f"Max retries ({task_info['max_retries']}) exceeded"
                    )
                
                return {"success": False, "error": error}
                
        except Exception as e:
            duration = time.time() - start_time
            error = str(e)
            self.record_attempt(task_id, retry_count + 1, "failed", error=error, duration=duration)
            
            # 继续重试
            if retry_count + 1 < task_info["max_retries"]:
                self.schedule_retry(
                    task_id=task_id,
                    agent_id=agent_id,
                    task_data=task_data,
                    retry_count=retry_count + 1,
                    max_retries=task_info["max_retries"]
                )
            
            return {"success": False, "error": error}
    
    def start_scheduler(self):
        """启动重试调度器"""
        if self.running:
            return
        
        self.running = True
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        print("[TaskAutoRetry] Scheduler started")
    
    def stop_scheduler(self):
        """停止重试调度器"""
        self.running = False
        if self.scheduler_thread:
            self.scheduler_thread.join(timeout=5)
        print("[TaskAutoRetry] Scheduler stopped")
    
    def _scheduler_loop(self):
        """调度器循环"""
        while self.running:
            try:
                # 获取待执行的重试任务
                pending = self.get_pending_retries()
                
                for task_info in pending:
                    print(f"[TaskAutoRetry] Executing retry for task: {task_info['task_id']}")
                    self.execute_retry(task_info)
                
            except Exception as e:
                print(f"[TaskAutoRetry] Scheduler error: {e}")
            
            time.sleep(5)  # 每5秒检查一次
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取重试统计"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 当前待重试
        cursor.execute("SELECT COUNT(*) FROM retry_tasks WHERE status = 'pending'")
        pending = cursor.fetchone()[0]
        
        # 进行中
        cursor.execute("SELECT COUNT(*) FROM retry_tasks WHERE status = 'running'")
        running = cursor.fetchone()[0]
        
        # 今日重试
        today = datetime.now().date().isoformat()
        cursor.execute("SELECT COUNT(*) FROM retry_history WHERE created_at LIKE ?", (f"{today}%",))
        today_retries = cursor.fetchone()[0]
        
        # 今日成功
        cursor.execute("""
            SELECT COUNT(*) FROM retry_history 
            WHERE status = 'success' AND created_at LIKE ?
        """, (f"{today}%",))
        today_success = cursor.fetchone()[0]
        
        # 今日失败
        cursor.execute("""
            SELECT COUNT(*) FROM retry_history 
            WHERE status = 'failed' AND created_at LIKE ?
        """, (f"{today}%",))
        today_failed = cursor.fetchone()[0]
        
        conn.close()
        
        success_rate = 0
        if today_retries > 0:
            success_rate = round(today_success / today_retries * 100, 2)
        
        return {
            "pending": pending,
            "running": running,
            "total_retries": self.stats["total_retries"],
            "successful_retries": self.stats["successful_retries"],
            "failed_retries": self.stats["failed_retries"],
            "abandoned": self.stats["abandoned"],
            "today": {
                "retries": today_retries,
                "success": today_success,
                "failed": today_failed,
                "success_rate": success_rate
            }
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="任务自动重试")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 安排重试
    schedule_parser = subparsers.add_parser("schedule", help="安排重试")
    schedule_parser.add_argument("--task-id", required=True)
    schedule_parser.add_argument("--agent-id", required=True)
    schedule_parser.add_argument("--task-data", required=True, help="JSON格式的任务数据")
    schedule_parser.add_argument("--retry-count", type=int, default=0)
    schedule_parser.add_argument("--max-retries", type=int, default=5)
    schedule_parser.add_argument("--delay", type=int, help="延迟秒数")
    
    # 取消重试
    cancel_parser = subparsers.add_parser("cancel", help="取消重试")
    cancel_parser.add_argument("--task-id", required=True)
    
    # 查看重试状态
    status_parser = subparsers.add_parser("status", help="查看重试状态")
    status_parser.add_argument("--task-id", required=True)
    
    # 查看待重试任务
    subparsers.add_parser("pending", help="查看待重试任务")
    
    # 统计
    subparsers.add_parser("stats", help="查看重试统计")
    
    # 启动调度器
    subparsers.add_parser("start", help="启动重试调度器")
    
    # 停止调度器
    subparsers.add_parser("stop", help="停止重试调度器")
    
    args = parser.parse_args()
    
    retry_system = TaskAutoRetry()
    
    if args.command == "schedule":
        import json
        task_data = json.loads(args.task_data)
        retry_id = retry_system.schedule_retry(
            task_id=args.task_id,
            agent_id=args.agent_id,
            task_data=task_data,
            retry_count=args.retry_count,
            max_retries=args.max_retries,
            delay=args.delay
        )
        print(f"Retry scheduled: {retry_id}")
    
    elif args.command == "cancel":
        if retry_system.cancel_retry(args.task_id):
            print("Retry cancelled")
        else:
            print("Retry not found")
    
    elif args.command == "status":
        status = retry_system.get_retry_status(args.task_id)
        if status:
            print(json.dumps(status, indent=2, ensure_ascii=False))
        else:
            print("No retry info found")
    
    elif args.command == "pending":
        pending = retry_system.get_pending_retries()
        print(json.dumps(pending, indent=2, ensure_ascii=False))
    
    elif args.command == "stats":
        stats = retry_system.get_statistics()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
    
    elif args.command == "start":
        retry_system.start_scheduler()
    
    elif args.command == "stop":
        retry_system.stop_scheduler()
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()