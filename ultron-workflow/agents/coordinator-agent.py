#!/usr/bin/env python3
"""
协调Agent (Coordinator Agent)
职责: 协调多智能体系统中的任务分配和流程控制

功能:
  - 任务分发: 将任务分配给合适的Agent
  - 流程控制: 管理Agent间的协作流程
  - 资源管理: 协调Agent资源使用
  - 冲突处理: 解决Agent间的冲突
  - 状态维护: 维护整体系统状态

接口:
  - dispatch(task) → DispatchResult
  - orchestrate(workflow) → WorkflowResult
  - resolve_conflict(agent_a, agent_b) → Resolution
  - get_system_status() → SystemStatus
"""

import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional

AGENT_DIR = Path(__file__).parent
STATE_FILE = AGENT_DIR / "coordinator-state.json"
TASKS_FILE = AGENT_DIR / "coordinator-tasks.json"
WORKFLOWS_FILE = AGENT_DIR / "coordinator-workflows.json"

def load_state():
    """加载协调器状态"""
    if STATE_FILE.exists():
        with open(STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        "agent_id": "agent-coordinator",
        "type": "coordinate",
        "status": "idle",
        "capabilities": ["task_dispatch", "workflow", "conflict_resolution", "resource_management"],
        "agents": {
            "monitor": {"status": "unknown", "capabilities": ["monitor"]},
            "analyzer": {"status": "unknown", "capabilities": ["analyze"]},
            "executor": {"status": "unknown", "capabilities": ["execute"]}
        },
        "last_heartbeat": datetime.now().isoformat(),
        "dispatch_count": 0,
        "workflow_count": 0
    }

def save_state(state):
    """保存协调器状态"""
    state["last_heartbeat"] = datetime.now().isoformat()
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def load_tasks():
    """加载任务队列"""
    if TASKS_FILE.exists():
        with open(TASKS_FILE, 'r') as f:
            return json.load(f)
    return {"pending": [], "dispatched": [], "completed": [], "failed": []}

def save_tasks(tasks):
    """保存任务队列"""
    with open(TASKS_FILE, 'w') as f:
        json.dump(tasks, f, indent=2)

def load_workflows():
    """加载工作流"""
    if WORKFLOWS_FILE.exists():
        with open(WORKFLOWS_FILE, 'r') as f:
            return json.load(f)
    return {"active": [], "completed": []}

def save_workflows(workflows):
    """保存工作流"""
    with open(WORKFLOWS_FILE, 'w') as f:
        json.dump(workflows, f, indent=2)

def select_agent(task: Dict) -> str:
    """根据任务类型选择合适的Agent"""
    task_type = task.get("type", "")
    
    # 任务类型到Agent的映射
    agent_mapping = {
        "monitor": "monitor",
        "analyze": "analyzer",
        "analysis": "analyzer",
        "execute": "executor",
        "run": "executor",
        "shell": "executor",
        "message": "executor"
    }
    
    # 优先级匹配
    for keyword, agent in agent_mapping.items():
        if keyword in task_type.lower():
            return agent
    
    # 默认选择executor
    return "executor"

def dispatch_task(task: Dict) -> Dict:
    """分发任务到合适的Agent"""
    state = load_state()
    tasks = load_tasks()
    
    task_id = task.get("task_id", str(uuid.uuid4()))
    task["task_id"] = task_id
    
    # 选择合适的Agent
    target_agent = task.get("agent", select_agent(task))
    task["target_agent"] = target_agent
    
    # 更新状态
    state["status"] = "dispatching"
    state["dispatch_count"] += 1
    
    # 添加到已分发队列
    dispatch_result = {
        "task_id": task_id,
        "task": task,
        "target_agent": target_agent,
        "dispatched_at": datetime.now().isoformat(),
        "status": "dispatched"
    }
    
    tasks["dispatched"].append(dispatch_result)
    
    # 模拟分发到目标Agent (实际会调用对应Agent的API)
    if target_agent == "executor":
        # 调用executor执行
        from pathlib import Path
        exec_agent = AGENT_DIR / "executor-agent.py"
        if exec_agent.exists():
            # 任务会在executor中执行
            dispatch_result["executed"] = True
    
    save_state(state)
    save_tasks(tasks)
    
    return {
        "task_id": task_id,
        "target_agent": target_agent,
        "status": "dispatched",
        "dispatched_at": dispatch_result["dispatched_at"]
    }

def orchestrate_workflow(workflow: Dict) -> Dict:
    """编排多步骤工作流"""
    state = load_state()
    workflows = load_workflows()
    
    workflow_id = workflow.get("workflow_id", str(uuid.uuid4()))
    steps = workflow.get("steps", [])
    
    state["status"] = "orchestrating"
    state["workflow_count"] += 1
    
    workflow_record = {
        "workflow_id": workflow_id,
        "workflow": workflow,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "current_step": 0,
        "step_results": []
    }
    
    # 按顺序执行各步骤
    for i, step in enumerate(steps):
        workflow_record["current_step"] = i
        
        # 分发步骤任务
        result = dispatch_task({
            "type": step.get("type", "execute"),
            "payload": step.get("payload", {}),
            "metadata": step.get("metadata", {})
        })
        
        workflow_record["step_results"].append({
            "step": i,
            "task_id": result["task_id"],
            "agent": result["target_agent"],
            "status": result["status"]
        })
        
        # 如果步骤失败，则停止
        if result.get("status") == "failed":
            workflow_record["status"] = "failed"
            break
    
    # 工作流完成
    if workflow_record["current_step"] == len(steps) - 1:
        workflow_record["status"] = "completed"
    
    workflow_record["completed_at"] = datetime.now().isoformat()
    
    workflows["completed"].append(workflow_record)
    state["status"] = "idle"
    
    save_state(state)
    save_workflows(workflows)
    
    return {
        "workflow_id": workflow_id,
        "status": workflow_record["status"],
        "steps_completed": workflow_record["current_step"] + 1,
        "total_steps": len(steps),
        "step_results": workflow_record["step_results"]
    }

def resolve_conflict(agent_a: str, agent_b: str, conflict: Dict) -> Dict:
    """解决Agent间的冲突"""
    conflict_type = conflict.get("type", "resource")
    resolution = {
        "conflict_id": str(uuid.uuid4()),
        "agents": [agent_a, agent_b],
        "conflict_type": conflict_type,
        "resolution": None,
        "resolved_at": datetime.now().isoformat()
    }
    
    # 简单的冲突解决策略
    if conflict_type == "resource":
        # 资源冲突: 优先级高的获得资源
        priority_a = conflict.get("priority_a", 0)
        priority_b = conflict.get("priority_b", 0)
        
        if priority_a >= priority_b:
            resolution["resolution"] = {
                "winner": agent_a,
                "loser": agent_b,
                "reason": "higher priority"
            }
        else:
            resolution["resolution"] = {
                "winner": agent_b,
                "loser": agent_a,
                "reason": "higher priority"
            }
    
    elif conflict_type == "task":
        # 任务冲突: 时间戳早的优先
        resolution["resolution"] = {
            "action": "sequential",
            "reason": "tasks will run sequentially"
        }
    
    return resolution

def get_system_status() -> Dict:
    """获取系统状态"""
    state = load_state()
    tasks = load_tasks()
    workflows = load_workflows()
    
    # 检查各Agent状态
    agent_status = {}
    for agent_name in ["monitor", "analyzer", "executor"]:
        agent_file = AGENT_DIR / f"{agent_name}-state.json"
        if agent_file.exists():
            try:
                with open(agent_file, 'r') as f:
                    agent_data = json.load(f)
                    agent_status[agent_name] = {
                        "status": agent_data.get("status", "unknown"),
                        "last_heartbeat": agent_data.get("last_heartbeat", "unknown")
                    }
            except:
                agent_status[agent_name] = {"status": "error", "last_heartbeat": "unknown"}
        else:
            agent_status[agent_name] = {"status": "not_found"}
    
    return {
        "coordinator": {
            "status": state["status"],
            "dispatch_count": state["dispatch_count"],
            "workflow_count": state["workflow_count"],
            "last_heartbeat": state["last_heartbeat"]
        },
        "agents": agent_status,
        "tasks": {
            "pending": len(tasks.get("pending", [])),
            "dispatched": len(tasks.get("dispatched", [])),
            "completed": len(tasks.get("completed", [])),
            "failed": len(tasks.get("failed", []))
        },
        "workflows": {
            "completed": len(workflows.get("completed", []))
        }
    }

def main():
    import sys
    
    if len(sys.argv) < 2:
        print(json.dumps({
            "error": "Usage: coordinator-agent.py <command> [args...]"
        }))
        return
    
    cmd = sys.argv[1]
    
    if cmd == "dispatch":
        task = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = dispatch_task(task)
        print(json.dumps(result))
        
    elif cmd == "orchestrate":
        workflow = json.loads(sys.argv[2]) if len(sys.argv) > 2 else {}
        result = orchestrate_workflow(workflow)
        print(json.dumps(result))
        
    elif cmd == "resolve":
        agent_a = sys.argv[2] if len(sys.argv) > 2 else "agent-a"
        agent_b = sys.argv[3] if len(sys.argv) > 3 else "agent-b"
        conflict = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
        result = resolve_conflict(agent_a, agent_b, conflict)
        print(json.dumps(result))
        
    elif cmd == "status":
        print(json.dumps(get_system_status()))
        
    elif cmd == "tasks":
        print(json.dumps(load_tasks()))
        
    elif cmd == "workflows":
        print(json.dumps(load_workflows()))
        
    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))

if __name__ == "__main__":
    main()