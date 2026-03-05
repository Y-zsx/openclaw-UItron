#!/usr/bin/env python3
"""
跨系统工作流自动化引擎
集成决策引擎、工作流引擎、Agent网络、Agent执行器
"""

import json
import asyncio
import aiohttp
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# ============ 配置 ============
SERVICES = {
    "decision_engine": "http://localhost:18120",
    "decision_automation": "http://localhost:18128",
    "workflow_engine": "http://localhost:18100",
    "agent_network": "http://localhost:18150",
    "agent_executor": "http://localhost:8096",
}

DB_PATH = "/root/.openclaw/workspace/ultron/cross_system/workflows.db"

# ============ 数据模型 ============
class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class StepType(Enum):
    DECISION = "decision"       # 决策引擎
    WORKFLOW = "workflow"       # 工作流引擎
    AGENT_TASK = "agent_task"   # Agent任务
    CONDITION = "condition"     # 条件判断
    NOTIFY = "notify"           # 通知

@dataclass
class CrossSystemWorkflow:
    id: str
    name: str
    description: str
    steps: List[Dict]
    status: str
    created_at: str
    updated_at: str
    last_run: Optional[str] = None

@dataclass
class WorkflowExecution:
    id: str
    workflow_id: str
    status: str
    started_at: str
    completed_at: Optional[str] = None
    step_results: List[Dict] = None
    error: Optional[str] = None

# ============ 数据库 ============
def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 跨系统工作流表
    c.execute('''CREATE TABLE IF NOT EXISTS workflows (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        steps TEXT NOT NULL,
        status TEXT DEFAULT 'active',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        last_run TEXT
    )''')
    
    # 执行记录表
    c.execute('''CREATE TABLE IF NOT EXISTS executions (
        id TEXT PRIMARY KEY,
        workflow_id TEXT NOT NULL,
        status TEXT DEFAULT 'pending',
        started_at TEXT NOT NULL,
        completed_at TEXT,
        step_results TEXT,
        error TEXT,
        FOREIGN KEY (workflow_id) REFERENCES workflows(id)
    )''')
    
    # 执行历史表
    c.execute('''CREATE TABLE IF NOT EXISTS execution_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        workflow_id TEXT NOT NULL,
        execution_id TEXT NOT NULL,
        step_index INTEGER,
        step_type TEXT,
        step_name TEXT,
        input_data TEXT,
        output_data TEXT,
        status TEXT,
        duration_ms INTEGER,
        executed_at TEXT NOT NULL
    )''')
    
    conn.commit()
    return conn

# ============ 服务调用 ============
async def call_service(url: str, method: str = "GET", data: Any = None, timeout: int = 30) -> Dict:
    """调用服务API"""
    try:
        async with aiohttp.ClientSession() as session:
            if method == "GET":
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return {"status": resp.status, "data": await resp.json() if resp.status == 200 else {}}
            elif method == "POST":
                async with session.post(url, json=data, timeout=aiohttp.ClientTimeout(total=timeout)) as resp:
                    return {"status": resp.status, "data": await resp.json() if resp.status == 200 else {}}
    except Exception as e:
        return {"status": 0, "error": str(e)}

async def execute_decision(context: Dict) -> Dict:
    """执行决策"""
    url = f"{SERVICES['decision_engine']}/decide"
    result = await call_service(url, "POST", {"context": context})
    return result

async def trigger_workflow(workflow_name: str, params: Dict) -> Dict:
    """触发工作流"""
    url = f"{SERVICES['workflow_engine']}/api/workflows/{workflow_name}/execute"
    result = await call_service(url, "POST", params)
    return result

async def submit_agent_task(agent_type: str, task: Dict) -> Dict:
    """提交Agent任务"""
    url = f"{SERVICES['agent_executor']}/api/execute"
    result = await call_service(url, "POST", {
        "agent_type": agent_type,
        "task": task
    })
    return result

async def check_condition(condition: Dict) -> bool:
    """评估条件"""
    op = condition.get("op", "eq")
    lhs = condition.get("lhs")
    rhs = condition.get("rhs")
    
    if op == "eq":
        return lhs == rhs
    elif op == "ne":
        return lhs != rhs
    elif op == "gt":
        return lhs > rhs
    elif op == "lt":
        return lhs < rhs
    elif op == "gte":
        return lhs >= rhs
    elif op == "lte":
        return lhs <= rhs
    elif op == "in":
        return lhs in rhs
    return False

# ============ 核心执行引擎 ============
class CrossSystemExecutor:
    """跨系统工作流执行器"""
    
    def __init__(self):
        pass  # 连接将在每个请求中创建
    
    def _get_conn(self):
        """获取线程安全的数据库连接"""
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        return conn
    
    async def execute_workflow(self, workflow_id: str, input_data: Dict = None) -> Dict:
        """执行跨系统工作流"""
        # 获取工作流定义
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = c.fetchone()
        
        if not row:
            return {"error": f"Workflow {workflow_id} not found"}
        
        workflow = {
            "id": row[0],
            "name": row[1],
            "description": row[2],
            "steps": json.loads(row[3]),
            "status": row[4],
            "created_at": row[5],
            "updated_at": row[6],
            "last_run": row[7]
        }
        
        # 创建执行记录
        execution_id = f"exec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        started_at = datetime.now().isoformat()
        
        c.execute("""INSERT INTO executions (id, workflow_id, status, started_at, step_results)
                      VALUES (?, ?, ?, ?, ?)""",
                  (execution_id, workflow_id, "running", started_at, "[]"))
        self._get_conn().commit()
        
        step_results = []
        context = input_data or {}
        error = None
        
        try:
            for i, step in enumerate(workflow["steps"]):
                step_start = datetime.now()
                step_result = await self._execute_step(step, context, step_results)
                step_duration = int((datetime.now() - step_start).total_seconds() * 1000)
                
                # 记录执行历史
                c.execute("""INSERT INTO execution_history 
                            (workflow_id, execution_id, step_index, step_type, step_name, 
                             input_data, output_data, status, duration_ms, executed_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                          (workflow_id, execution_id, i, step.get("type"), step.get("name"),
                           json.dumps(step.get("input", {})), json.dumps(step_result),
                           step_result.get("status", "success"), step_duration, started_at))
                
                if step_result.get("status") == "failed":
                    error = step_result.get("error", "Step failed")
                    break
                
                # 更新上下文
                if step_result.get("output"):
                    context.update(step_result["output"])
                
                step_results.append(step_result)
                self._get_conn().commit()
            
            status = "completed" if not error else "failed"
            
        except Exception as e:
            error = str(e)
            status = "failed"
        
        # 更新执行记录
        completed_at = datetime.now().isoformat()
        c.execute("""UPDATE executions SET status = ?, completed_at = ?, 
                      step_results = ?, error = ? WHERE id = ?""",
                  (status, completed_at, json.dumps(step_results), error, execution_id))
        
        # 更新工作流最后运行时间
        c.execute("UPDATE workflows SET last_run = ? WHERE id = ?", (completed_at, workflow_id))
        self._get_conn().commit()
        
        return {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "status": status,
            "step_results": step_results,
            "context": context,
            "error": error
        }
    
    async def _execute_step(self, step: Dict, context: Dict, previous_results: List) -> Dict:
        """执行单个步骤"""
        step_type = step.get("type")
        
        if step_type == "decision":
            return await self._execute_decision_step(step, context)
        elif step_type == "workflow":
            return await self._execute_workflow_step(step, context)
        elif step_type == "agent_task":
            return await self._execute_agent_task_step(step, context)
        elif step_type == "condition":
            return await self._execute_condition_step(step, context)
        elif step_type == "notify":
            return await self._execute_notify_step(step, context)
        else:
            return {"status": "failed", "error": f"Unknown step type: {step_type}"}
    
    async def _execute_decision_step(self, step: Dict, context: Dict) -> Dict:
        """执行决策步骤"""
        input_data = step.get("input", {})
        # 合并上下文
        input_data.update({k: v for k, v in context.items() if k in input_data.get("use_context", [])})
        
        result = await execute_decision(input_data)
        
        if result.get("status") == 200:
            return {
                "status": "success",
                "output": {"decision": result.get("data", {})}
            }
        return {"status": "failed", "error": result.get("error", "Decision failed")}
    
    async def _execute_workflow_step(self, step: Dict, context: Dict) -> Dict:
        """执行工作流步骤"""
        workflow_name = step.get("workflow_name")
        params = step.get("params", {})
        # 合并上下文
        params.update({k: v for k, v in context.items()})
        
        result = await trigger_workflow(workflow_name, params)
        
        if result.get("status") == 200:
            return {
                "status": "success",
                "output": {"workflow_result": result.get("data", {})}
            }
        return {"status": "failed", "error": result.get("error", "Workflow failed")}
    
    async def _execute_agent_task_step(self, step: Dict, context: Dict) -> Dict:
        """执行Agent任务步骤"""
        agent_type = step.get("agent_type")
        task = step.get("task", {})
        # 合并上下文
        task.update({k: v for k, v in context.items()})
        
        result = await submit_agent_task(agent_type, task)
        
        if result.get("status") == 200:
            return {
                "status": "success",
                "output": {"task_result": result.get("data", {})}
            }
        return {"status": "failed", "error": result.get("error", "Agent task failed")}
    
    async def _execute_condition_step(self, step: Dict, context: Dict) -> Dict:
        """执行条件步骤"""
        condition = step.get("condition", {})
        # 解析上下文变量
        for k, v in condition.items():
            if isinstance(v, str) and v.startswith("$"):
                var_name = v[1:]
                condition[k] = context.get(var_name, v)
        
        passed = await check_condition(condition)
        
        return {
            "status": "success",
            "output": {"condition_passed": passed}
        }
    
    async def _execute_notify_step(self, step: Dict, context: Dict) -> Dict:
        """执行通知步骤"""
        # 简化实现：记录通知
        return {
            "status": "success",
            "output": {"notification_sent": True}
        }
    
    def create_workflow(self, name: str, description: str, steps: List[Dict]) -> str:
        """创建工作流"""
        workflow_id = f"ws_{name.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        now = datetime.now().isoformat()
        
        c = self._get_conn().cursor()
        c.execute("""INSERT INTO workflows (id, name, description, steps, status, created_at, updated_at)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                  (workflow_id, name, description, json.dumps(steps), "active", now, now))
        self._get_conn().commit()
        
        return workflow_id
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM workflows ORDER BY created_at DESC")
        rows = c.fetchall()
        
        return [{
            "id": r[0], "name": r[1], "description": r[2],
            "steps": json.loads(r[3]), "status": r[4],
            "created_at": r[5], "updated_at": r[6], "last_run": r[7]
        } for r in rows]
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        c = self._get_conn().cursor()
        c.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
        row = c.fetchone()
        
        if not row:
            return None
        
        return {
            "id": row[0], "name": row[1], "description": row[2],
            "steps": json.loads(row[3]), "status": row[4],
            "created_at": row[5], "updated_at": row[6], "last_run": row[7]
        }
    
    def get_executions(self, workflow_id: str = None) -> List[Dict]:
        """获取执行记录"""
        c = self._get_conn().cursor()
        if workflow_id:
            c.execute("SELECT * FROM executions WHERE workflow_id = ? ORDER BY started_at DESC", (workflow_id,))
        else:
            c.execute("SELECT * FROM executions ORDER BY started_at DESC LIMIT 50")
        
        rows = c.fetchall()
        return [{
            "id": r[0], "workflow_id": r[1], "status": r[2],
            "started_at": r[3], "completed_at": r[4],
            "step_results": json.loads(r[5]) if r[5] else [],
            "error": r[6]
        } for r in rows]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        c = self._get_conn().cursor()
        
        c.execute("SELECT COUNT(*) FROM workflows")
        total_workflows = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM executions")
        total_executions = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM executions WHERE status = 'completed'")
        completed = c.fetchone()[0]
        
        c.execute("SELECT COUNT(*) FROM executions WHERE status = 'failed'")
        failed = c.fetchone()[0]
        
        return {
            "total_workflows": total_workflows,
            "total_executions": total_executions,
            "completed": completed,
            "failed": failed,
            "success_rate": round(completed / total_executions * 100, 1) if total_executions > 0 else 0
        }

# ============ 预设工作流模板 ============
PRESET_WORKFLOWS = [
    {
        "name": "智能告警处理",
        "description": "接收告警→决策分析→自动处理→通知结果",
        "steps": [
            {"type": "decision", "name": "分析告警", "input": {"alert": "$alert", "use_context": []}},
            {"type": "condition", "name": "需要自动处理", "condition": {"decision.risk_level": 7, "op": "gte"}},
            {"type": "agent_task", "name": "执行修复", "agent_type": "executor", "task": {"command": "$decision.action"}},
            {"type": "notify", "name": "通知结果"}
        ]
    },
    {
        "name": "健康检查与自愈",
        "description": "检查系统健康→决策→自动修复→验证",
        "steps": [
            {"type": "decision", "name": "健康评估", "input": {"context": {}, "use_context": []}},
            {"type": "condition", "name": "需要修复", "condition": {"decision.need_repair": True, "op": "eq"}},
            {"type": "workflow", "name": "执行修复流程", "workflow_name": "health_check_repair"},
            {"type": "decision", "name": "验证修复", "input": {"context": {}, "use_context": []}}
        ]
    },
    {
        "name": "批量任务处理",
        "description": "分析任务→分发到Agent网络→汇总结果",
        "steps": [
            {"type": "decision", "name": "任务规划", "input": {"task": "$task", "use_context": []}},
            {"type": "agent_task", "name": "分发任务", "agent_type": "orchestrator", "task": {"tasks": "$decision.sub_tasks"}},
            {"type": "decision", "name": "结果汇总", "input": {"results": "$task_result", "use_context": []}},
            {"type": "notify", "name": "通知完成"}
        ]
    }
]

# ============ Flask API ============
from flask import Flask, request, jsonify

app = Flask(__name__)
executor = CrossSystemExecutor()

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"service": "cross-system-workflow", "status": "healthy"})

@app.route("/api/workflows", methods=["GET"])
def list_workflows():
    return jsonify(executor.list_workflows())

@app.route("/api/workflows", methods=["POST"])
def create_workflow():
    data = request.json
    workflow_id = executor.create_workflow(
        data["name"], data.get("description", ""), data.get("steps", [])
    )
    return jsonify({"id": workflow_id})

@app.route("/api/workflows/<workflow_id>", methods=["GET"])
def get_workflow(workflow_id):
    workflow = executor.get_workflow(workflow_id)
    if not workflow:
        return jsonify({"error": "Not found"}), 404
    return jsonify(workflow)

@app.route("/api/workflows/<workflow_id>/execute", methods=["POST"])
async def execute_workflow(workflow_id):
    input_data = request.json or {}
    result = await executor.execute_workflow(workflow_id, input_data)
    return jsonify(result)

@app.route("/api/executions", methods=["GET"])
def list_executions():
    workflow_id = request.args.get("workflow_id")
    return jsonify(executor.get_executions(workflow_id))

@app.route("/api/stats", methods=["GET"])
def get_stats():
    return jsonify(executor.get_stats())

@app.route("/api/services/status", methods=["GET"])
async def services_status():
    """检查所有集成服务的状态"""
    results = {}
    for name, url in SERVICES.items():
        result = await call_service(f"{url}/health")
        results[name] = {
            "status": "online" if result.get("status") == 200 else "offline",
            "url": url
        }
    return jsonify(results)

@app.route("/api/templates", methods=["GET"])
def list_templates():
    """列出预设模板"""
    return jsonify(PRESET_WORKFLOWS)

@app.route("/api/templates/<name>/create", methods=["POST"])
def create_from_template(name):
    """从模板创建工作流"""
    template = next((t for t in PRESET_WORKFLOWS if t["name"] == name), None)
    if not template:
        return jsonify({"error": "Template not found"}), 404
    
    workflow_id = executor.create_workflow(
        template["name"], template["description"], template["steps"]
    )
    return jsonify({"id": workflow_id, "template": template["name"]})

if __name__ == "__main__":
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 18131
    
    # 初始化预设工作流
    for template in PRESET_WORKFLOWS:
        existing = executor.list_workflows()
        if not any(w["name"] == template["name"] for w in existing):
            executor.create_workflow(template["name"], template["description"], template["steps"])
    
    print("=== 跨系统工作流自动化引擎 ===")
    print(f"服务端口: {port}")
    print(f"数据库: {DB_PATH}")
    print(f"预设模板: {len(PRESET_WORKFLOWS)} 个")
    
    app.run(host="0.0.0.0", port=port, debug=False)