#!/usr/bin/env python3
"""
奥创自动执行框架 - 第二世核心组件
自动任务执行 + 验证 + 回滚
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

WORKSPACE = "/root/.openclaw/workspace"
LOGS_DIR = f"{WORKSPACE}/logs"
EXECUTOR_LOG = f"{LOGS_DIR}/auto-executor.json"

class AutoExecutor:
    def __init__(self):
        self.task_queue = []
        self.execution_history = []
        Path(LOGS_DIR).mkdir(parents=True, exist_ok=True)
    
    def load_queue(self):
        queue_file = f"{WORKSPACE}/agents/task_queue.json"
        if os.path.exists(queue_file):
            with open(queue_file, 'r') as f:
                data = json.load(f)
                return data.get('pending', [])
        return []
    
    def log_execution(self, task_id, action, result, details=None):
        """记录执行日志"""
        entry = {
            "task_id": task_id,
            "action": action,
            "result": result,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.execution_history.append(entry)
        
        # 持久化
        with open(EXECUTOR_LOG, 'w') as f:
            json.dump(self.execution_history, f, indent=2)
        
        return entry
    
    def execute_task(self, task):
        """执行单个任务"""
        task_id = task.get('id', f"task_{int(time.time())}")
        command = task.get('command')
        verify = task.get('verify')
        rollback = task.get('rollback')
        
        # 执行
        self.log_execution(task_id, "execute", "started", {"command": command})
        
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=300
            )
            
            if result.returncode != 0:
                # 执行失败，尝试回滚
                self.log_execution(task_id, "execute", "failed", {
                    "stdout": result.stdout,
                    "stderr": result.stderr
                })
                
                if rollback:
                    self.log_execution(task_id, "rollback", "attempting", {"rollback": rollback})
                    rollback_result = subprocess.run(
                        rollback, shell=True, capture_output=True, text=True, timeout=60
                    )
                    self.log_execution(task_id, "rollback", "completed" if rollback_result.returncode == 0 else "failed", {
                        "stdout": rollback_result.stdout,
                        "stderr": rollback_result.stderr
                    })
                
                return {"status": "failed", "error": result.stderr}
            
            # 验证结果
            if verify:
                verify_result = subprocess.run(
                    verify, shell=True, capture_output=True, text=True, timeout=60
                )
                if verify_result.returncode != 0:
                    self.log_execution(task_id, "verify", "failed", {"error": verify_result.stderr})
                    return {"status": "verification_failed", "error": verify_result.stderr}
            
            self.log_execution(task_id, "execute", "success", {"stdout": result.stdout})
            return {"status": "success", "output": result.stdout}
            
        except subprocess.TimeoutExpired:
            self.log_execution(task_id, "execute", "timeout", {})
            return {"status": "timeout", "error": "Task execution timed out"}
        except Exception as e:
            self.log_execution(task_id, "execute", "error", {"error": str(e)})
            return {"status": "error", "error": str(e)}
    
    def run_pending_tasks(self):
        """运行所有待处理任务"""
        queue = self.load_queue()
        results = []
        
        for task in queue:
            result = self.execute_task(task)
            results.append({"task": task, "result": result})
        
        return results
    
    def get_status(self):
        """获取执行器状态"""
        return {
            "pending_tasks": len(self.load_queue()),
            "execution_history": len(self.execution_history),
            "last_execution": self.execution_history[-1] if self.execution_history else None
        }

if __name__ == "__main__":
    import sys
    executor = AutoExecutor()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "status":
            print(json.dumps(executor.get_status(), indent=2))
        elif sys.argv[1] == "run":
            results = executor.run_pending_tasks()
            print(json.dumps(results, indent=2))
    else:
        # 默认显示状态
        print(json.dumps(executor.get_status(), indent=2))