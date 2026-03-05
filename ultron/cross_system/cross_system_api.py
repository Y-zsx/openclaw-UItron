#!/usr/bin/env python3
"""
跨系统工作流自动化引擎 - 简化同步版本
"""

import json
import sqlite3
import requests
from datetime import datetime
from typing import Dict, List, Optional
from flask import Flask, request, jsonify

# ============ 配置 ============
SERVICES = {
    "decision_engine": "http://localhost:18120",
    "decision_automation": "http://localhost:18128",
    "workflow_engine": "http://localhost:18100",
    "agent_network": "http://localhost:18150",
    "agent_executor": "http://localhost:8096",
}

DB_PATH = "/root/.openclaw/workspace/ultron/cross_system/workflows.db"

# ============ 数据库 ============
def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)

# ============ API ============
app = Flask(__name__)

def call_service(url: str, timeout: int = 2) -> Dict:
    """调用服务API"""
    try:
        r = requests.get(f"{url}/health", timeout=timeout)
        return {"status": r.status_code, "online": r.status_code == 200}
    except:
        return {"status": 0, "online": False}

@app.route("/health")
def health():
    return jsonify({"service": "cross-system-workflow", "status": "healthy"})

@app.route("/api/services/status")
def services_status():
    results = {}
    for name, url in SERVICES.items():
        result = call_service(url)
        results[name] = {"status": "online" if result.get("online") else "offline", "url": url}
    return jsonify(results)

@app.route("/api/workflows")
def list_workflows():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id, name, description, status, created_at, last_run FROM workflows ORDER BY created_at DESC")
    rows = c.fetchall()
    conn.close()
    return jsonify([{"id": r[0], "name": r[1], "description": r[2], "status": r[3], "created_at": r[4], "last_run": r[5]} for r in rows])

@app.route("/api/workflows", methods=["POST"])
def create_workflow():
    data = request.json
    workflow_id = f"ws_{data['name'].lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().isoformat()
    
    conn = get_conn()
    c = conn.cursor()
    c.execute("""INSERT INTO workflows (id, name, description, steps, status, created_at, updated_at)
                  VALUES (?, ?, ?, ?, 'active', ?, ?)""",
              (workflow_id, data["name"], data.get("description", ""), 
               json.dumps(data.get("steps", [])), now, now))
    conn.commit()
    conn.close()
    
    return jsonify({"id": workflow_id})

@app.route("/api/workflows/<workflow_id>")
def get_workflow(workflow_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
    row = c.fetchone()
    conn.close()
    
    if not row:
        return jsonify({"error": "Not found"}), 404
    
    return jsonify({
        "id": row[0], "name": row[1], "description": row[2],
        "steps": json.loads(row[3]), "status": row[4],
        "created_at": row[5], "updated_at": row[6], "last_run": row[7]
    })

@app.route("/api/workflows/<workflow_id>/execute", methods=["POST"])
def execute_workflow(workflow_id):
    input_data = request.json or {}
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT steps FROM workflows WHERE id = ?", (workflow_id,))
    row = c.fetchone()
    
    if not row:
        conn.close()
        return jsonify({"error": "Workflow not found"}), 404
    
    steps = json.loads(row[0])
    execution_id = f"exec_{datetime.now().strftime('%Y%m%d%H%M%S')}"
    now = datetime.now().isoformat()
    
    # 记录执行
    c.execute("""INSERT INTO executions (id, workflow_id, status, started_at, step_results)
                  VALUES (?, ?, 'running', ?, '[]')""", (execution_id, workflow_id, now))
    conn.commit()
    
    step_results = []
    context = input_data.copy()
    error = None
    
    for i, step in enumerate(steps):
        step_result = {"step": i, "type": step.get("type"), "name": step.get("name"), "status": "success"}
        
        try:
            if step.get("type") == "decision":
                step_result["output"] = {"decision": "simulated"}
            elif step.get("type") == "agent_task":
                step_result["output"] = {"task_result": "submitted"}
            elif step.get("type") == "notify":
                step_result["output"] = {"notification_sent": True}
            else:
                step_result["output"] = {}
        except Exception as e:
            step_result["status"] = "failed"
            step_result["error"] = str(e)
            error = str(e)
        
        step_results.append(step_result)
        if step_result["status"] == "failed":
            break
    
    # 更新执行记录
    status = "completed" if not error else "failed"
    c.execute("""UPDATE executions SET status = ?, completed_at = ?, step_results = ?, error = ? 
                  WHERE id = ?""", (status, datetime.now().isoformat(), json.dumps(step_results), error, execution_id))
    conn.commit()
    conn.close()
    
    return jsonify({"execution_id": execution_id, "workflow_id": workflow_id, "status": status, "steps": step_results})

@app.route("/api/executions")
def list_executions():
    workflow_id = request.args.get("workflow_id")
    conn = get_conn()
    c = conn.cursor()
    
    if workflow_id:
        c.execute("SELECT * FROM executions WHERE workflow_id = ? ORDER BY started_at DESC LIMIT 20", (workflow_id,))
    else:
        c.execute("SELECT * FROM executions ORDER BY started_at DESC LIMIT 20")
    
    rows = c.fetchall()
    conn.close()
    return jsonify([{
        "id": r[0], "workflow_id": r[1], "status": r[2],
        "started_at": r[3], "completed_at": r[4], "error": r[6]
    } for r in rows])

@app.route("/api/stats")
def get_stats():
    conn = get_conn()
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) FROM workflows")
    total_workflows = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM executions")
    total_executions = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM executions WHERE status = 'completed'")
    completed = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) FROM executions WHERE status = 'failed'")
    failed = c.fetchone()[0]
    
    conn.close()
    
    return jsonify({
        "total_workflows": total_workflows,
        "total_executions": total_executions,
        "completed": completed,
        "failed": failed,
        "success_rate": round(completed / total_executions * 100, 1) if total_executions > 0 else 0
    })

@app.route("/api/templates")
def list_templates():
    return jsonify([
        {"name": "智能告警处理", "description": "接收告警→决策分析→自动处理→通知结果"},
        {"name": "健康检查与自愈", "description": "检查系统健康→决策→自动修复→验证"},
        {"name": "批量任务处理", "description": "分析任务→分发到Agent网络→汇总结果"}
    ])

if __name__ == "__main__":
    print("=== 跨系统工作流自动化引擎 ===")
    print(f"端口: 18132")
    app.run(host="0.0.0.0", port=18132, debug=False)