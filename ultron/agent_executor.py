#!/usr/bin/env python3
"""
Agent任务执行器集成模块
支持从监控系统触发Agent任务执行
"""

import json
import subprocess
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import uuid

class AgentExecutor:
    """Agent任务执行器"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.history_file = Path(workspace) / "ultron" / "data" / "agent_executor_history.json"
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        self._load_history()
        
    def _load_history(self):
        """加载执行历史"""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                self.history = json.load(f)
        else:
            self.history = {"executions": []}
    
    def _save_history(self):
        """保存执行历史"""
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def execute_task(
        self,
        task: str,
        runtime: str = "subagent",
        mode: str = "run",
        agent_id: Optional[str] = "main",
        timeout: int = 300,
        env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        执行Agent任务
        
        Args:
            task: 任务描述
            runtime: 运行时类型 (subagent/acp)
            mode: 执行模式 (run/session)
            agent_id: Agent ID (默认 main)
            timeout: 超时时间(秒)
            env: 环境变量
            cwd: 工作目录
            
        Returns:
            执行结果字典
        """
        execution_id = str(uuid.uuid4())[:8]
        start_time = datetime.now().isoformat()
        
        result = {
            "execution_id": execution_id,
            "task": task,
            "runtime": runtime,
            "mode": mode,
            "agent_id": agent_id,
            "start_time": start_time,
            "status": "running"
        }
        
        # 构建命令
        cmd = self._build_command(task, runtime, mode, agent_id, timeout, env, cwd)
        
        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=cwd or self.workspace
            )
            
            # 等待执行完成
            stdout, stderr = proc.communicate(timeout=timeout)
            
            end_time = datetime.now().isoformat()
            duration = (datetime.fromisoformat(end_time) - datetime.fromisoformat(start_time)).total_seconds()
            
            result.update({
                "status": "completed" if proc.returncode == 0 else "failed",
                "returncode": proc.returncode,
                "stdout": stdout[:10000],  # 限制输出长度
                "stderr": stderr[:5000],
                "end_time": end_time,
                "duration": duration
            })
            
        except subprocess.TimeoutExpired:
            proc.kill()
            result.update({
                "status": "timeout",
                "error": f"Task execution timeout after {timeout} seconds",
                "end_time": datetime.now().isoformat()
            })
            
        except Exception as e:
            result.update({
                "status": "error",
                "error": str(e),
                "end_time": datetime.now().isoformat()
            })
        
        # 保存到历史
        self.history["executions"].append(result)
        # 只保留最近100条
        self.history["executions"] = self.history["executions"][-100:]
        self._save_history()
        
        return result
    
    def _build_command(
        self,
        task: str,
        runtime: str,
        mode: str,
        agent_id: Optional[str],
        timeout: int,
        env: Optional[Dict[str, str]],
        cwd: Optional[str]
    ) -> List[str]:
        """构建执行命令"""
        # 使用 openclaw agent 命令执行单次任务
        cmd = ["openclaw", "agent", "-m", task]
        
        if agent_id:
            cmd.extend(["--agent", agent_id])
        
        if timeout:
            cmd.extend(["--timeout", str(timeout)])
        
        # 对于 session 模式，使用 session-id 保持会话
        if mode == "session":
            # 生成一个稳定的session id
            session_id = str(hash(task))[:8]
            cmd.extend(["--session-id", session_id])
        
        return cmd
    
    def get_execution(self, execution_id: str) -> Optional[Dict[str, Any]]:
        """获取执行记录"""
        for exec in self.history["executions"]:
            if exec.get("execution_id") == execution_id:
                return exec
        return None
    
    def list_executions(
        self,
        status: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """列出执行记录"""
        executions = self.history["executions"]
        
        if status:
            executions = [e for e in executions if e.get("status") == status]
        
        return executions[-limit:]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        executions = self.history["executions"]
        
        if not executions:
            return {"total": 0, "status": {}}
        
        status_counts = {}
        total_duration = 0
        completed_count = 0
        
        for e in executions:
            status = e.get("status", "unknown")
            status_counts[status] = status_counts.get(status, 0) + 1
            
            if e.get("duration"):
                total_duration += e["duration"]
                completed_count += 1
        
        return {
            "total": len(executions),
            "status": status_counts,
            "avg_duration": total_duration / completed_count if completed_count > 0 else 0
        }


def main():
    """CLI入口"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Agent任务执行器")
    subparsers = parser.add_subparsers(dest="command", help="子命令")
    
    # 执行任务
    exec_parser = subparsers.add_parser("execute", help="执行Agent任务")
    exec_parser.add_argument("task", help="任务描述")
    exec_parser.add_argument("--runtime", default="subagent", choices=["subagent", "acp"])
    exec_parser.add_argument("--mode", default="run", choices=["run", "session"])
    exec_parser.add_argument("--agent-id", help="Agent ID (acp模式)")
    exec_parser.add_argument("--timeout", type=int, default=300)
    
    # 列表
    list_parser = subparsers.add_parser("list", help="列出执行记录")
    list_parser.add_argument("--status", help="状态过滤")
    list_parser.add_argument("--limit", type=int, default=20)
    
    # 统计
    subparsers.add_parser("stats", help="执行统计")
    
    # 查看
    view_parser = subparsers.add_parser("get", help="查看执行记录")
    view_parser.add_argument("execution_id", help="执行ID")
    
    args = parser.parse_args()
    
    executor = AgentExecutor()
    
    if args.command == "execute":
        result = executor.execute_task(
            task=args.task,
            runtime=args.runtime,
            mode=args.mode,
            agent_id=args.agent_id or "main",
            timeout=args.timeout
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        
    elif args.command == "list":
        results = executor.list_executions(status=args.status, limit=args.limit)
        print(json.dumps(results, indent=2, ensure_ascii=False))
        
    elif args.command == "stats":
        stats = executor.get_stats()
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        
    elif args.command == "get":
        result = executor.get_execution(args.execution_id)
        if result:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"Execution {args.execution_id} not found")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()