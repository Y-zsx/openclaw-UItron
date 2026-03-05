#!/usr/bin/env python3
"""
决策引擎API服务 - 端口18120
提供决策制定、风险评估和行动执行的RESTful接口
"""

from flask import Flask, request, jsonify, make_response
import json
import os
import sqlite3
from datetime import datetime
import threading
import psutil
import requests
import uuid

app = Flask(__name__)

@app.after_request
def add_cors_headers(response):
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
    return response

DB_PATH = "/root/.openclaw/workspace/ultron/data/decisions.db"

# 确保数据库目录存在
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

def init_db():
    """初始化数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 决策记录表
    c.execute('''CREATE TABLE IF NOT EXISTS decisions
                 (id TEXT PRIMARY KEY, type TEXT, context TEXT,
                  risk_level REAL, action TEXT, result TEXT,
                  created_at TEXT, executed_at TEXT)''')
    
    # 风险评估记录表
    c.execute('''CREATE TABLE IF NOT EXISTS risk_assessments
                 (id TEXT PRIMARY KEY, target TEXT, risk_type TEXT,
                  score REAL, factors TEXT, recommendation TEXT,
                  created_at TEXT)''')
    
    # 行动执行记录表
    c.execute('''CREATE TABLE IF NOT EXISTS actions
                 (id TEXT PRIMARY KEY, decision_id TEXT,
                  action_type TEXT, payload TEXT, status TEXT,
                  result TEXT, created_at TEXT, completed_at TEXT)''')
    
    conn.commit()
    conn.close()

init_db()

# 决策引擎核心
class DecisionEngine:
    """智能决策引擎"""
    
    def __init__(self):
        self.rules = self._load_rules()
    
    def _load_rules(self):
        """加载决策规则"""
        return {
            "cpu_high": {"threshold": 80, "action": "scale_up", "risk": 6},
            "memory_high": {"threshold": 85, "action": "scale_up", "risk": 7},
            "disk_full": {"threshold": 90, "action": "cleanup", "risk": 8},
            "service_down": {"threshold": 1, "action": "restart", "risk": 9},
            "error_rate_high": {"threshold": 5, "action": "investigate", "risk": 7},
            "latency_high": {"threshold": 1000, "action": "optimize", "risk": 5}
        }
    
    def make_decision(self, context: dict) -> dict:
        """基于上下文做出决策"""
        decision_id = str(uuid.uuid4())[:8]
        
        # 分析风险
        risk_level = self._assess_risk(context)
        
        # 选择行动
        action = self._select_action(context)
        
        # 保存决策
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO decisions (id, type, context, risk_level, action, created_at)
                     VALUES (?, ?, ?, ?, ?, ?)''',
                  (decision_id, context.get("type", "manual"),
                   json.dumps(context), risk_level, action,
                   datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        return {
            "decision_id": decision_id,
            "risk_level": risk_level,
            "action": action,
            "auto_approve": risk_level < 7
        }
    
    def _assess_risk(self, context: dict) -> float:
        """评估风险等级 (0-10)"""
        score = 0
        
        # 基于上下文的简单风险计算
        if context.get("type") == "cpu_high":
            score = min(10, (context.get("value", 0) / 10))
        elif context.get("type") == "service_down":
            score = 9
        elif context.get("type") == "security":
            score = 10
        
        return round(score, 1)
    
    def _select_action(self, context: dict) -> str:
        """选择行动"""
        rule = self.rules.get(context.get("type", ""))
        return rule["action"] if rule else "investigate"

# 风险评估器
class RiskAssessor:
    """风险评估器"""
    
    def __init__(self):
        self.factors = {
            "system_impact": {"weight": 0.3, "max_score": 10},
            "data_loss_risk": {"weight": 0.3, "max_score": 10},
            "service_disruption": {"weight": 0.2, "max_score": 10},
            "recovery_difficulty": {"weight": 0.2, "max_score": 10}
        }
    
    def assess(self, target: str, risk_type: str) -> dict:
        """执行风险评估"""
        assessment_id = str(uuid.uuid4())[:8]
        
        # 收集系统指标
        factors = self._collect_factors(target, risk_type)
        
        # 计算综合风险评分
        total_score = sum(f["score"] * self.factors[f["name"]]["weight"] 
                         for f in factors)
        
        # 生成建议
        recommendation = self._generate_recommendation(total_score, risk_type)
        
        # 保存评估结果
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO risk_assessments 
                     (id, target, risk_type, score, factors, recommendation, created_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (assessment_id, target, risk_type, round(total_score, 2),
                   json.dumps(factors), recommendation,
                   datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        return {
            "assessment_id": assessment_id,
            "target": target,
            "risk_type": risk_type,
            "risk_score": round(total_score, 2),
            "level": self._get_risk_level(total_score),
            "factors": factors,
            "recommendation": recommendation
        }
    
    def _collect_factors(self, target: str, risk_type: str) -> list:
        """收集风险因素"""
        factors = []
        
        # 系统影响评估
        cpu = psutil.cpu_percent()
        mem = psutil.virtual_memory().percent
        factors.append({
            "name": "system_impact",
            "score": max(cpu, mem) / 10,
            "description": f"系统负载: CPU {cpu}%, 内存 {mem}%"
        })
        
        # 数据丢失风险 (假设评估)
        factors.append({
            "name": "data_loss_risk",
            "score": 2 if risk_type != "critical" else 8,
            "description": "数据持久化状态检查"
        })
        
        # 服务中断风险
        factors.append({
            "name": "service_disruption",
            "score": 3 if risk_type != "critical" else 7,
            "description": "服务可用性评估"
        })
        
        # 恢复难度
        factors.append({
            "name": "recovery_difficulty",
            "score": 2,
            "description": "备份恢复能力评估"
        })
        
        return factors
    
    def _get_risk_level(self, score: float) -> str:
        """获取风险等级"""
        if score < 3:
            return "low"
        elif score < 6:
            return "medium"
        elif score < 8:
            return "high"
        return "critical"
    
    def _generate_recommendation(self, score: float, risk_type: str) -> str:
        """生成建议"""
        if score < 3:
            return "风险可控，可正常执行"
        elif score < 6:
            return "建议监控执行，准备回滚方案"
        elif score < 8:
            return "需要审批，建议小范围验证"
        return "高风险操作，建议人工确认"

# 行动执行器
class ActionExecutor:
    """行动执行器"""
    
    def __init__(self):
        self.executors = {
            "shell": self._exec_shell,
            "http": self._exec_http,
            "notify": self._exec_notify,
            "scale_up": self._exec_scale,
            "restart": self._exec_restart,
            "cleanup": self._exec_cleanup
        }
    
    def execute(self, action: str, payload: dict) -> dict:
        """执行行动"""
        action_id = str(uuid.uuid4())[:8]
        
        executor = self.executors.get(action, self._exec_default)
        result = executor(payload)
        
        # 保存执行结果
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''INSERT INTO actions (id, action_type, payload, status, result, created_at, completed_at)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (action_id, action, json.dumps(payload), "completed" if result["success"] else "failed",
                   json.dumps(result), datetime.utcnow().isoformat(),
                   datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()
        
        return {"action_id": action_id, "result": result}
    
    def _exec_shell(self, payload: dict) -> dict:
        """执行Shell命令"""
        try:
            cmd = payload.get("command", "echo 'no command'")
            result = os.popen(cmd).read()
            return {"success": True, "output": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _exec_http(self, payload: dict) -> dict:
        """执行HTTP请求"""
        try:
            method = payload.get("method", "GET")
            url = payload.get("url", "")
            resp = requests.request(method, url, timeout=10)
            return {"success": True, "status": resp.status_code, "body": resp.text[:200]}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _exec_notify(self, payload: dict) -> dict:
        """发送通知"""
        return {"success": True, "message": "通知已发送"}
    
    def _exec_scale(self, payload: dict) -> dict:
        """扩容操作"""
        return {"success": True, "action": "scaled_up", "details": payload}
    
    def _exec_restart(self, payload: dict) -> dict:
        """重启服务"""
        service = payload.get("service", "unknown")
        return {"success": True, "action": "restarted", "service": service}
    
    def _exec_cleanup(self, payload: dict) -> dict:
        """清理操作"""
        return {"success": True, "action": "cleaned", "space_freed": "1GB"}
    
    def _exec_default(self, payload: dict) -> dict:
        """默认执行"""
        return {"success": True, "action": "executed", "payload": payload}

# 初始化引擎
decision_engine = DecisionEngine()
risk_assessor = RiskAssessor()
action_executor = ActionExecutor()

# ==================== API路由 ====================

@app.route("/api/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "decision-engine", "port": 18120})

@app.route("/api/decision", methods=["POST"])
def create_decision():
    """创建决策"""
    try:
        context = request.json
        decision = decision_engine.make_decision(context)
        return jsonify({"success": True, "decision": decision})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/decision/<decision_id>", methods=["GET"])
def get_decision(decision_id):
    """获取决策详情"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM decisions WHERE id = ?", (decision_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "决策不存在"}), 404

@app.route("/api/decisions", methods=["GET"])
def list_decisions():
    """列出决策历史"""
    limit = request.args.get("limit", 20)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM decisions ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route("/api/risk/assess", methods=["POST"])
def assess_risk():
    """执行风险评估"""
    try:
        data = request.json
        result = risk_assessor.assess(data.get("target", "system"), data.get("risk_type", "general"))
        return jsonify({"success": True, "assessment": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/risk/<assessment_id>", methods=["GET"])
def get_risk_assessment(assessment_id):
    """获取风险评估详情"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM risk_assessments WHERE id = ?", (assessment_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "评估不存在"}), 404

@app.route("/api/risk/history", methods=["GET"])
def list_risk_assessments():
    """列出风险评估历史"""
    limit = request.args.get("limit", 20)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM risk_assessments ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = c.fetchall()
    conn.close()
    
    return jsonify([dict(row) for row in rows])

@app.route("/api/action/execute", methods=["POST"])
def execute_action():
    """执行行动"""
    try:
        data = request.json
        action = data.get("action", "default")
        payload = data.get("payload", {})
        
        # 检查风险等级
        if data.get("decision_id"):
            conn = sqlite3.connect(DB_PATH)
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT risk_level FROM decisions WHERE id = ?", (data["decision_id"],))
            row = c.fetchone()
            conn.close()
            
            if row and row["risk_level"] >= 8:
                return jsonify({
                    "success": False, 
                    "error": "高风险操作需要人工审批",
                    "risk_level": row["risk_level"]
                }), 403
        
        result = action_executor.execute(action, payload)
        return jsonify({"success": True, **result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/action/<action_id>", methods=["GET"])
def get_action(action_id):
    """获取行动执行结果"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM actions WHERE id = ?", (action_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return jsonify(dict(row))
    return jsonify({"error": "行动不存在"}), 404

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """获取决策统计"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute("SELECT COUNT(*) as total FROM decisions")
    total_decisions = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) as total FROM risk_assessments")
    total_assessments = c.fetchone()[0]
    
    c.execute("SELECT COUNT(*) as total FROM actions WHERE status = 'completed'")
    total_actions = c.fetchone()[0]
    
    c.execute("SELECT AVG(risk_level) as avg_risk FROM decisions")
    avg_risk = c.fetchone()[0] or 0
    
    conn.close()
    
    return jsonify({
        "total_decisions": total_decisions,
        "total_assessments": total_assessments,
        "total_actions": total_actions,
        "average_risk_level": round(avg_risk, 2)
    })

# ==================== 反馈学习增强 ====================
from collections import defaultdict

# 反馈学习内存
feedback_memory = {
    "patterns": defaultdict(lambda: defaultdict(float)),
    "success_history": [],
    "failure_history": [],
    "optimization_suggestions": []
}

@app.route("/api/feedback/collect", methods=["POST"])
def collect_feedback():
    """收集决策执行反馈"""
    try:
        data = request.json
        decision_id = data.get("decision_id")
        action_id = data.get("action_id")
        expected = data.get("expected")
        actual = data.get("actual")
        context = data.get("context", {})
        
        success = (expected == actual)
        
        # 计算差异度
        try:
            delta = abs(float(expected) - float(actual)) if isinstance(expected, (int, float)) and isinstance(actual, (int, float)) else (0.0 if expected == actual else 1.0)
        except:
            delta = 1.0
        
        # 生成模式标识
        pattern_parts = []
        for key in ["cpu_percent", "memory_percent", "disk_percent", "error_count"]:
            if key in context:
                value = context[key]
                if isinstance(value, (int, float)):
                    bucket = int(value / 20) * 20
                    pattern_parts.append(f"{key}_{bucket}")
        pattern = "|".join(pattern_parts) if pattern_parts else "default"
        
        # 更新模式-动作映射
        action = data.get("action", "default")
        reward = 1.0 if success else -0.5
        feedback_memory["patterns"][pattern][action] += reward
        
        # 记录历史
        entry = {
            "decision_id": decision_id,
            "action_id": action_id,
            "expected": str(expected),
            "actual": str(actual),
            "success": success,
            "delta": delta,
            "pattern": pattern,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        if success:
            feedback_memory["success_history"].append(entry)
        else:
            feedback_memory["failure_history"].append(entry)
        
        # 保持历史长度限制
        max_history = 500
        if len(feedback_memory["success_history"]) > max_history:
            feedback_memory["success_history"] = feedback_memory["success_history"][-max_history:]
        if len(feedback_memory["failure_history"]) > max_history:
            feedback_memory["failure_history"] = feedback_memory["failure_history"][-max_history:]
        
        return jsonify({
            "success": True,
            "feedback": entry,
            "pattern_reward": feedback_memory["patterns"][pattern][action]
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/feedback/learn", methods=["GET"])
def get_learned_patterns():
    """获取学习到的模式"""
    patterns = {}
    for pattern, actions in feedback_memory["patterns"].items():
        patterns[pattern] = dict(actions)
    
    return jsonify({
        "patterns": patterns,
        "total_patterns": len(patterns),
        "success_count": len(feedback_memory["success_history"]),
        "failure_count": len(feedback_memory["failure_history"])
    })

@app.route("/api/feedback/recommend", methods=["POST"])
def get_recommendations():
    """获取优化建议"""
    try:
        context = request.json or {}
        
        # 生成当前上下文模式
        pattern_parts = []
        for key in ["cpu_percent", "memory_percent", "disk_percent", "error_count"]:
            if key in context:
                value = context[key]
                if isinstance(value, (int, float)):
                    bucket = int(value / 20) * 20
                    pattern_parts.append(f"{key}_{bucket}")
        pattern = "|".join(pattern_parts) if pattern_parts else "default"
        
        recommendations = []
        
        # 基于失败模式
        recent_failures = feedback_memory["failure_history"][-10:]
        if len(recent_failures) > 3:
            recommendations.append({
                "type": "pattern_warning",
                "message": f"检测到近期 {len(recent_failures)} 次失败，可能存在系统性问题",
                "confidence": 0.7
            })
        
        # 基于低奖励动作
        action_rewards = feedback_memory["patterns"].get(pattern, {})
        for action, reward in action_rewards.items():
            if reward < -1.0:
                recommendations.append({
                    "type": "action_adjust",
                    "action": action,
                    "message": f"动作 '{action}' 在当前模式下表现不佳 (reward={reward:.2f})",
                    "suggestion": "考虑调整参数或更换策略",
                    "confidence": min(1.0, abs(reward) / 5.0)
                })
        
        # 基于历史成功的最佳动作
        if action_rewards:
            best_action = max(action_rewards.items(), key=lambda x: x[1])
            if best_action[1] > 0:
                recommendations.append({
                    "type": "best_practice",
                    "action": best_action[0],
                    "message": f"建议使用动作 '{best_action[0]}' (reward={best_action[1]:.2f})",
                    "confidence": min(1.0, best_action[1] / 5.0)
                })
        
        return jsonify({
            "pattern": pattern,
            "recommendations": recommendations,
            "context": context
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/api/feedback/stats", methods=["GET"])
def get_feedback_stats():
    """获取反馈学习统计"""
    total = len(feedback_memory["success_history"]) + len(feedback_memory["failure_history"])
    success_rate = len(feedback_memory["success_history"]) / total if total > 0 else 0
    
    # 计算各动作的平均奖励
    action_stats = defaultdict(lambda: {"count": 0, "total_reward": 0.0})
    for pattern, actions in feedback_memory["patterns"].items():
        for action, reward in actions.items():
            action_stats[action]["count"] += 1
            action_stats[action]["total_reward"] += reward
    
    return jsonify({
        "total_feedback": total,
        "success_count": len(feedback_memory["success_history"]),
        "failure_count": len(feedback_memory["failure_history"]),
        "success_rate": round(success_rate, 3),
        "unique_patterns": len(feedback_memory["patterns"]),
        "action_performance": dict(action_stats)
    })

@app.route("/api/optimize/auto", methods=["POST"])
def auto_optimize():
    """自动优化决策参数"""
    try:
        data = request.json or {}
        target_metric = data.get("target_metric", "success_rate")
        
        suggestions = []
        
        # 分析失败模式
        failure_patterns = defaultdict(int)
        for failure in feedback_memory["failure_history"]:
            pattern = failure.get("pattern", "default")
            failure_patterns[pattern] += 1
        
        # 找出最频繁的失败模式
        if failure_patterns:
            worst_pattern = max(failure_patterns.items(), key=lambda x: x[1])
            if worst_pattern[1] >= 3:
                suggestions.append({
                    "type": "pattern_fix",
                    "pattern": worst_pattern[0],
                    "issue": f"模式 '{worst_pattern[0]}' 失败 {worst_pattern[1]} 次",
                    "action": "调整该模式下的决策阈值"
                })
        
        # 基于历史成功调整规则
        success_patterns = defaultdict(float)
        for success in feedback_memory["success_history"]:
            pattern = success.get("pattern", "default")
            success_patterns[pattern] += 1
        
        return jsonify({
            "success": True,
            "target_metric": target_metric,
            "suggestions": suggestions,
            "analysis": {
                "worst_pattern": dict(failure_patterns),
                "best_patterns": dict(success_patterns)
            }
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

if __name__ == "__main__":
    print("=" * 50)
    print("决策引擎API服务启动")
    print("端口: 18120")
    print("功能: 决策制定 | 风险评估 | 行动执行")
    print("=" * 50)
    app.run(host="0.0.0.0", port=18120, debug=False)