#!/usr/bin/env python3
"""
执行Agent (Executor Agent)
职责: 执行具体操作任务
接口:
  - execute(task) → TaskResult
  - cancel(task_id) → boolean
  - get_queue() → TaskList
"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

AGENT_DIR = Path(__file__).parent
STATE_FILE = AGENT_DIR / "executor-state.json"
QUEUE_FILE = AGENT_DIR / "executor-queue.json"

DEFAULT_TIMEOUT = 300
DEFAULT_RETRY = 3

def load_state():
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "agent_id": "agent-executor",
        "type": "execute",
        "status": "idle",
        "capabilities": ["shell", "message", "browser", "http"],
        "last_heartbeat": datetime.now().isoformat(),
        "executing": None,
        "results": {}
    }

def save_state(state):
    state["last_heartbeat"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_queue():
    if QUEUE_FILE.exists():
        with open(QUEUE_FILE, 'r') as f:
            return json.load(f)
    return {"pending": [], "completed": [], "failed": []}

def save_queue(queue):
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)

def execute_task(task):
    """执行具体任务"""
    state = load_state()
    queue = load_queue()
    
    task_id = task.get("task_id", str(uuid.uuid4()))
    task_type = task.get("type", "execute")
    payload = task.get("payload", {})
    timeout = task.get("timeout", DEFAULT_TIMEOUT)
    retry = task.get("retry", DEFAULT_RETRY)
    
    state["status"] = "busy"
    state["executing"] = task_id
    save_state(state)
    
    start_time = time.time()
    result = {
        "task_id": task_id,
        "status": "failed",
        "output": {},
        "error": None,
        "duration_ms": 0,
        "retry_count": 0
    }
    
    try:
        # 根据任务类型执行
        action = payload.get("action", "")
        
        if action == "shell":
            import subprocess
            cmd = payload.get("command", "")
            proc = subprocess.run(
                cmd, shell=True, 
                capture_output=True, 
                text=True,
                timeout=timeout
            )
            result["output"] = {
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
            result["status"] = "success" if proc.returncode == 0 else "failed"
            
        elif action == "message":
            # 消息发送任务
            result["output"] = {
                "message": "Message task queued",
                "target": payload.get("target"),
                "content": payload.get("content")
            }
            result["status"] = "success"
            
        elif action == "http":
            import urllib.request
            url = payload.get("url", "")
            method = payload.get("method", "GET")
            data = payload.get("data")
            
            req = urllib.request.Request(url, method=method)
            if data:
                req.data = json.dumps(data).encode()
                
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                result["output"] = {
                    "status": resp.status,
                    "body": resp.read().decode()
                }
                result["status"] = "success"
                
        else:
            result["error"] = f"Unknown action: {action}"
            
    except subprocess.TimeoutExpired:
        result["error"] = f"Task timeout after {timeout}s"
        result["status"] = "timeout"
    except Exception as e:
        result["error"] = str(e)
        
    finally:
        result["duration_ms"] = int((time.time() - start_time) * 1000)
        state["status"] = "idle"
        state["executing"] = None
        state["results"][task_id] = result
        save_state(state)
        
        # 更新队列
        queue["completed"].append({
            "task_id": task_id,
            "result": result,
            "completed_at": datetime.now().isoformat()
        })
        save_queue(queue)
    
    return result

def cancel_task(task_id):
    """取消任务"""
    state = load_state()
    if state["executing"] == task_id:
        state["executing"] = None
        state["status"] = "idle"
        save_state(state)
        return True
    return False

def get_queue():
    """获取任务队列"""
    return load_queue()

def get_status():
    """获取Agent状态"""
    return load_state()

def main():
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: executor-agent.py <command> [args...]"
        }))
        return
    
    cmd = sys.argv[1]
    
    if cmd == "execute":
        task = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = execute_task(task)
        print(json.dumps(result))
        
    elif cmd == "cancel":
        task_id = sys.argv[2] if len(sys.argv) > 2 else ""
        success = cancel_task(task_id)
        print(json.dumps({"success": success}))
        
    elif cmd == "queue":
        print(json.dumps(get_queue()))
        
    elif cmd == "status":
        print(json.dumps(get_status()))
        
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))

if __name__ == "__main__":
    main()