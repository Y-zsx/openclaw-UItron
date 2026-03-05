#!/usr/bin/env python3
"""
审计日志与合规系统Web面板
端口: 8092
"""

from flask import Flask, jsonify, request
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from audit_logger import get_logger
from compliance import ComplianceChecker

app = Flask(__name__)
logger = get_logger()
checker = ComplianceChecker()

@app.route("/health")
def health():
    return jsonify({"status": "ok", "service": "audit-system"})

@app.route("/logs")
def get_logs():
    """获取审计日志"""
    event_type = request.args.get("event_type")
    agent_id = request.args.get("agent_id")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    status = request.args.get("status")
    limit = int(request.args.get("limit", 100))
    
    logs = logger.query(
        event_type=event_type,
        agent_id=agent_id,
        start_time=start_time,
        end_time=end_time,
        status=status,
        limit=limit
    )
    
    return jsonify({"logs": logs, "count": len(logs)})

@app.route("/stats")
def get_stats():
    """获取统计信息"""
    return jsonify(logger.get_stats())

@app.route("/compliance/check", methods=["POST"])
def compliance_check():
    """运行合规检查"""
    result = checker.run_all_checks()
    return jsonify(result)

@app.route("/compliance/rules")
def compliance_rules():
    """获取合规规则列表"""
    return jsonify({"rules": [
        {"id": r["id"], "name": r["name"], "severity": r["severity"]}
        for r in checker.rules
    ]})

@app.route("/log", methods=["POST"])
def add_log():
    """手动添加日志"""
    data = request.json
    log_id = logger.log(
        event_type=data.get("event_type", "MANUAL"),
        action=data.get("action", "LOG"),
        status=data.get("status", "INFO"),
        agent_id=data.get("agent_id"),
        resource=data.get("resource"),
        details=data.get("details")
    )
    return jsonify({"log_id": log_id, "status": "created"})

# 便捷端点
@app.route("/log/auth", methods=["POST"])
def log_auth():
    data = request.json
    log_id = logger.log_auth(
        agent_id=data.get("agent_id"),
        action=data.get("action", "LOGIN"),
        status=data.get("status", "SUCCESS"),
        details=data.get("details")
    )
    return jsonify({"log_id": log_id})

@app.route("/log/task", methods=["POST"])
def log_task():
    data = request.json
    log_id = logger.log_task(
        agent_id=data.get("agent_id"),
        task_id=data.get("task_id"),
        action=data.get("action", "CREATE"),
        status=data.get("status", "SUCCESS"),
        details=data.get("details")
    )
    return jsonify({"log_id": log_id})

@app.route("/log/comm", methods=["POST"])
def log_comm():
    data = request.json
    log_id = logger.log_communication(
        from_agent=data.get("from_agent"),
        to_agent=data.get("to_agent"),
        action=data.get("action", "SEND"),
        status=data.get("status", "SUCCESS"),
        details=data.get("details")
    )
    return jsonify({"log_id": log_id})


if __name__ == "__main__":
    print("🚀 审计系统启动: http://0.0.0.0:8092")
    app.run(host="0.0.0.0", port=8092, debug=False)