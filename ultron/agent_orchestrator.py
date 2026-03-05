#!/usr/bin/env python3
"""
Agent编排器 - 第48世
实现多Agent工作流编排、任务调度、协作管理
"""

import json
import time
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any
import threading
import queue

ORCHESTRATOR_STATE_FILE = "/root/.openclaw/workspace/ultron/data/orchestrator_state.json"

class AgentOrchestrator:
    def __init__(self):
        self.state = self._load_state()
        self.task_queue = queue.Queue()
        self.workers = {}
        self.lock = threading.Lock()
        self.running = True
        
        # 启动任务处理线程
        self.worker_thread = threading.Thread(target=self._process_tasks, daemon=True)
        self.worker_thread.start()
    
    def _load_state(self) -> Dict:
        """加载状态"""
        import os
        os.makedirs(os.path.dirname(ORCHESTRATOR_STATE_FILE), exist_ok=True)
        if os.path.exists(ORCHESTRATOR_STATE_FILE):
            with open(ORCHESTRATOR_STATE_FILE, 'r') as f:
                return json.load(f)
        return {
            "workflows": {},
            "tasks": {},
            "executions": {},
            "last_update": datetime.now().isoformat()
        }
    
    def _save_state(self):
        """保存状态"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(ORCHESTRATOR_STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def create_workflow(self, name: str, steps: List[Dict]) -> Dict:
        """创建工作流"""
        with self.lock:
            workflow_id = str(uuid.uuid4())[:8]
            workflow = {
                "id": workflow_id,
                "name": name,
                "steps": steps,
                "created_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            self.state["workflows"][workflow_id] = workflow
            self._save_state()
            
            return {"status": "success", "workflow": workflow}
    
    def register_agent(self, agent_id: str, capabilities: List[str], endpoint: str) -> Dict:
        """注册Agent到编排器"""
        with self.lock:
            self.workers[agent_id] = {
                "id": agent_id,
                "capabilities": capabilities,
                "endpoint": endpoint,
                "status": "available",
                "registered_at": datetime.now().isoformat(),
                "tasks_completed": 0
            }
            return {"status": "success", "agent": self.workers[agent_id]}
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取Agent信息"""
        return self.workers.get(agent_id)
    
    def list_agents(self) -> List[Dict]:
        """列出所有Agent"""
        return list(self.workers.values())
    
    def find_agent(self, capability: str) -> Optional[Dict]:
        """查找具有特定能力的Agent"""
        for agent in self.workers.values():
            if capability in agent.get("capabilities", []) and agent["status"] == "available":
                return agent
        return None
    
    def submit_task(self, workflow_id: str, inputs: Dict, agent_id: Optional[str] = None) -> Dict:
        """提交任务到工作流"""
        with self.lock:
            if workflow_id not in self.state["workflows"]:
                return {"status": "error", "message": "Workflow not found"}
            
            task_id = str(uuid.uuid4())[:8]
            task = {
                "id": task_id,
                "workflow_id": workflow_id,
                "agent_id": agent_id,
                "inputs": inputs,
                "status": "pending",
                "created_at": datetime.now().isoformat(),
                "steps_completed": 0,
                "results": {}
            }
            
            self.state["tasks"][task_id] = task
            self.task_queue.put(task_id)
            self._save_state()
            
            return {"status": "success", "task_id": task_id}
    
    def execute_workflow(self, workflow_id: str, inputs: Dict) -> Dict:
        """执行工作流"""
        workflow = self.state["workflows"].get(workflow_id)
        if not workflow:
            return {"status": "error", "message": "Workflow not found"}
        
        execution_id = str(uuid.uuid4())[:8]
        execution = {
            "id": execution_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "inputs": inputs,
            "status": "running",
            "started_at": datetime.now().isoformat(),
            "steps": [],
            "current_step": 0,
            "total_steps": len(workflow["steps"])
        }
        
        self.state["executions"][execution_id] = execution
        
        # 逐步执行工作流
        results = {}
        for i, step in enumerate(workflow["steps"]):
            execution["current_step"] = i
            execution["steps"].append({
                "step": i,
                "name": step.get("name", f"step_{i}"),
                "status": "running"
            })
            
            # 查找合适的Agent
            agent = None
            if "requires_agent" in step:
                agent = self.find_agent(step["requires_agent"])
            
            if agent:
                # 模拟Agent执行
                step_result = self._execute_step(step, inputs, results, agent)
            else:
                step_result = self._execute_step(step, inputs, results, None)
            
            results[step.get("name", f"step_{i}")] = step_result
            execution["steps"][i]["status"] = "completed"
            execution["steps"][i]["result"] = step_result
            
            # 检查步骤失败
            if step_result.get("status") == "failed":
                execution["status"] = "failed"
                execution["error"] = step_result.get("error", "Step failed")
                break
        
        if execution["status"] == "running":
            execution["status"] = "completed"
            execution["completed_at"] = datetime.now().isoformat()
        
        execution["results"] = results
        self._save_state()
        
        return {"status": "success", "execution": execution}
    
    def _execute_step(self, step: Dict, inputs: Dict, previous_results: Dict, agent: Optional[Dict]) -> Dict:
        """执行单个步骤"""
        step_type = step.get("type", "transform")
        
        if step_type == "transform":
            # 数据转换
            data = inputs.get("data", {})
            data.update(previous_results)
            return {"status": "success", "output": data}
        
        elif step_type == "agent":
            # Agent执行
            if agent:
                agent["tasks_completed"] = agent.get("tasks_completed", 0) + 1
                return {
                    "status": "success",
                    "output": {"agent": agent["id"], "processed": True},
                    "agent_id": agent["id"]
                }
            return {"status": "failed", "error": "No suitable agent found"}
        
        elif step_type == "condition":
            # 条件分支
            condition = step.get("condition", "true")
            return {"status": "success", "branch": "true" if condition == "true" else "false"}
        
        elif step_type == "aggregate":
            # 聚合结果
            sources = step.get("sources", [])
            aggregated = {}
            for src in sources:
                if src in previous_results:
                    aggregated[src] = previous_results[src]
            return {"status": "success", "output": aggregated}
        
        return {"status": "success", "output": {}}
    
    def _process_tasks(self):
        """后台任务处理器"""
        while self.running:
            try:
                task_id = self.task_queue.get(timeout=1)
                self._execute_task(task_id)
            except queue.Empty:
                continue
            except Exception as e:
                print(f"Task processing error: {e}")
    
    def _execute_task(self, task_id: str):
        """执行单个任务"""
        with self.lock:
            task = self.state["tasks"].get(task_id)
            if not task:
                return
            
            task["status"] = "running"
            task["started_at"] = datetime.now().isoformat()
            self._save_state()
        
        # 执行工作流
        result = self.execute_workflow(task["workflow_id"], task["inputs"])
        
        with self.lock:
            task["status"] = "completed"
            task["completed_at"] = datetime.now().isoformat()
            task["result"] = result
            self._save_state()
    
    def get_execution(self, execution_id: str) -> Dict:
        """获取执行状态"""
        return self.state["executions"].get(execution_id, {})
    
    def list_executions(self, workflow_id: Optional[str] = None) -> List[Dict]:
        """列出执行记录"""
        executions = list(self.state["executions"].values())
        if workflow_id:
            executions = [e for e in executions if e["workflow_id"] == workflow_id]
        return executions
    
    def cancel_execution(self, execution_id: str) -> Dict:
        """取消执行"""
        with self.lock:
            execution = self.state["executions"].get(execution_id)
            if not execution:
                return {"status": "error", "message": "Execution not found"}
            
            if execution["status"] == "running":
                execution["status"] = "cancelled"
                execution["cancelled_at"] = datetime.now().isoformat()
                self._save_state()
            
            return {"status": "success", "execution": execution}

# Flask API
from flask import Flask, request, jsonify

app = Flask(__name__)
orchestrator = AgentOrchestrator()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok", "service": "agent-orchestrator"})

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    return jsonify(list(orchestrator.state["workflows"].values()))

@app.route('/api/workflows', methods=['POST'])
def create_workflow():
    data = request.json
    name = data.get('name')
    steps = data.get('steps', [])
    return jsonify(orchestrator.create_workflow(name, steps))

@app.route('/api/workflows/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    return jsonify(orchestrator.state["workflows"].get(workflow_id, {}))

@app.route('/api/workflows/<workflow_id>/execute', methods=['POST'])
def execute_workflow(workflow_id):
    inputs = request.json or {}
    return jsonify(orchestrator.execute_workflow(workflow_id, inputs))

@app.route('/api/agents', methods=['GET'])
def list_agents():
    return jsonify(orchestrator.list_agents())

@app.route('/api/agents', methods=['POST'])
def register_agent():
    data = request.json
    return jsonify(orchestrator.register_agent(
        data.get('agent_id'),
        data.get('capabilities', []),
        data.get('endpoint', '')
    ))

@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    return jsonify(orchestrator.get_agent(agent_id) or {"error": "Agent not found"})

@app.route('/api/agents/find', methods=['GET'])
def find_agent():
    capability = request.args.get('capability')
    return jsonify(orchestrator.find_agent(capability) or {"error": "Agent not found"})

@app.route('/api/tasks', methods=['GET'])
def list_tasks():
    return jsonify(list(orchestrator.state["tasks"].values()))

@app.route('/api/tasks', methods=['POST'])
def submit_task():
    data = request.json
    return jsonify(orchestrator.submit_task(
        data.get('workflow_id'),
        data.get('inputs', {}),
        data.get('agent_id')
    ))

@app.route('/api/tasks/<task_id>', methods=['GET'])
def get_task(task_id):
    return jsonify(orchestrator.state["tasks"].get(task_id, {}))

@app.route('/api/executions', methods=['GET'])
def list_executions():
    workflow_id = request.args.get('workflow_id')
    return jsonify(orchestrator.list_executions(workflow_id))

@app.route('/api/executions/<execution_id>', methods=['GET'])
def get_execution(execution_id):
    return jsonify(orchestrator.get_execution(execution_id))

@app.route('/api/executions/<execution_id>/cancel', methods=['POST'])
def cancel_execution(execution_id):
    return jsonify(orchestrator.cancel_execution(execution_id))

if __name__ == '__main__':
    print("🎬 Agent Orchestrator starting on port 8097...")
    app.run(host='0.0.0.0', port=8097, debug=False)