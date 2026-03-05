#!/usr/bin/env python3
"""
智能体任务结果聚合器
收集并汇总多智能体任务执行结果
"""

import json
import os
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("/root/.openclaw/workspace/ultron/data")
RESULT_FILE = DATA_DIR / "task_results.json"

class ResultCollector:
    def __init__(self):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        if not RESULT_FILE.exists():
            self._save({})
    
    def _load(self):
        return json.loads(RESULT_FILE.read_text())
    
    def _save(self, data):
        RESULT_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def collect(self, task_id: str, agent_id: str, result: str, status: str = "success", metadata: dict = None):
        """收集任务结果"""
        data = self._load()
        timestamp = datetime.now().isoformat()
        
        if task_id not in data:
            data[task_id] = {"results": [], "start_time": timestamp, "status": "running"}
        
        data[task_id]["results"].append({
            "agent_id": agent_id,
            "result": result,
            "status": status,
            "timestamp": timestamp,
            "metadata": metadata or {}
        })
        
        # 更新最终状态
        if all(r.get("status") == "success" for r in data[task_id]["results"]):
            data[task_id]["status"] = "success"
        elif any(r.get("status") == "failed" for r in data[task_id]["results"]):
            data[task_id]["status"] = "failed"
        
        data[task_id]["last_update"] = timestamp
        self._save(data)
        return {"task_id": task_id, "collected": len(data[task_id]["results"])}
    
    def get_summary(self, task_id: str = None):
        """获取结果摘要"""
        data = self._load()
        if task_id:
            return data.get(task_id, {})
        
        summary = {}
        for tid, info in data.items():
            summary[tid] = {
                "status": info.get("status"),
                "agent_count": len(info.get("results", [])),
                "start_time": info.get("start_time"),
                "last_update": info.get("last_update")
            }
        return summary
    
    def aggregate(self, task_id: str):
        """聚合任务的所有结果"""
        data = self._load()
        task = data.get(task_id, {})
        results = task.get("results", [])
        
        if not results:
            return {"error": "No results found"}
        
        # 按agent分组
        by_agent = {}
        for r in results:
            agent = r.get("agent_id", "unknown")
            if agent not in by_agent:
                by_agent[agent] = []
            by_agent[agent].append(r)
        
        return {
            "task_id": task_id,
            "total_results": len(results),
            "status": task.get("status", "unknown"),
            "by_agent": {k: len(v) for k, v in by_agent.items()},
            "results": results
        }

def main():
    import sys
    collector = ResultCollector()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  collect <task_id> <agent_id> <result> [status]")
        print("  summary [task_id]")
        print("  aggregate <task_id>")
        return
    
    cmd = sys.argv[1]
    
    if cmd == "collect" and len(sys.argv) >= 5:
        task_id = sys.argv[2]
        agent_id = sys.argv[3]
        result = sys.argv[4]
        status = sys.argv[5] if len(sys.argv) > 5 else "success"
        print(json.dumps(collector.collect(task_id, agent_id, result, status)))
    
    elif cmd == "summary":
        task_id = sys.argv[2] if len(sys.argv) > 2 else None
        print(json.dumps(collector.get_summary(task_id), indent=2, ensure_ascii=False))
    
    elif cmd == "aggregate" and len(sys.argv) > 2:
        print(json.dumps(collector.aggregate(sys.argv[2]), indent=2, ensure_ascii=False))
    
    else:
        print("Unknown command")

if __name__ == "__main__":
    main()