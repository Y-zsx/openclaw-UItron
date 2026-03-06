#!/usr/bin/env python3
"""
智能决策引擎增强版 - 第175世
增强功能:
1. 决策预测 - 基于历史数据预测未来决策需求
2. 置信度评估 - 为每个决策计算置信度
3. 决策优化建议 - 基于反馈学习给出优化建议
4. 决策审计 - 完整决策追踪
"""

import json
import time
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

DB_PATH = "/root/.openclaw/workspace/ultron-workflow/decision_engine/enhanced_decisions.db"
import os
os.makedirs("/root/.openclaw/workspace/ultron-workflow/decision_engine", exist_ok=True)

def init_db():
    """初始化增强决策数据库"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # 决策历史表
    c.execute('''CREATE TABLE IF NOT EXISTS decision_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        decision_type TEXT NOT NULL,
        context TEXT,
        decision TEXT NOT NULL,
        confidence REAL,
        risk_level INTEGER,
        executed INTEGER DEFAULT 0,
        result TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 预测表
    c.execute('''CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prediction_type TEXT NOT NULL,
        predicted_value TEXT,
        confidence REAL,
        actual_value TEXT,
        accuracy REAL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    # 优化建议表
    c.execute('''CREATE TABLE IF NOT EXISTS optimization_suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        suggestion_type TEXT NOT NULL,
        suggestion TEXT NOT NULL,
        impact REAL,
        accepted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    return conn

class DecisionPredictor:
    """决策预测器 - 基于历史模式预测未来决策需求"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def predict(self, decision_type, context):
        """预测特定类型决策的未来趋势"""
        c = self.conn.cursor()
        
        # 获取过去7天同类型决策
        c.execute('''SELECT decision, COUNT(*) as cnt 
                     FROM decision_history 
                     WHERE decision_type = ? AND created_at > datetime('now', '-7 days')
                     GROUP BY decision ORDER BY cnt DESC LIMIT 5''',
                  (decision_type,))
        patterns = c.fetchall()
        
        # 获取决策频率
        c.execute('''SELECT COUNT(*) FROM decision_history 
                     WHERE decision_type = ? AND created_at > datetime('now', '-24 hours')''',
                  (decision_type,))
        daily_count = c.fetchone()[0] or 0
        
        # 计算置信度
        confidence = min(0.95, 0.5 + (len(patterns) * 0.1))
        
        return {
            "predicted_decisions": [{"decision": p[0], "count": p[1]} for p in patterns],
            "daily_frequency": daily_count,
            "confidence": confidence,
            "recommendation": "high_activity" if daily_count > 10 else "normal"
        }


class ConfidenceEvaluator:
    """决策置信度评估器"""
    
    def __init__(self, conn):
        self.conn = conn
        self.weights = {
            "historical_success": 0.3,
            "risk_level": 0.25,
            "context_clarity": 0.25,
            "data_availability": 0.2
        }
    
    def evaluate(self, decision_type, context, risk_level):
        """评估决策置信度"""
        c = self.conn.cursor()
        
        # 历史成功率
        c.execute('''SELECT COUNT(*), SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END)
                     FROM decision_history 
                     WHERE decision_type = ? AND executed = 1''',
                  (decision_type,))
        total, successes = c.fetchone()
        historical_success = (successes / total) if total > 0 else 0.5
        
        # 上下文清晰度
        context_clarity = 0.8 if context else 0.4
        
        # 数据可用性
        data_availability = 0.9 if len(context or {}) > 3 else 0.6
        
        # 综合置信度
        confidence = (
            historical_success * self.weights["historical_success"] +
            (1 - risk_level / 10) * self.weights["risk_level"] +
            context_clarity * self.weights["context_clarity"] +
            data_availability * self.weights["data_availability"]
        )
        
        return {
            "confidence": round(confidence * 100, 1),
            "factors": {
                "historical_success": round(historical_success * 100, 1),
                "risk_alignment": round((1 - risk_level / 10) * 100, 1),
                "context_clarity": round(context_clarity * 100, 1),
                "data_availability": round(data_availability * 100, 1)
            },
            "level": "high" if confidence > 0.8 else "medium" if confidence > 0.5 else "low"
        }


class OptimizationEngine:
    """决策优化引擎 - 基于反馈学习给出优化建议"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def generate_suggestions(self, decision_type=None):
        """生成优化建议"""
        c = self.conn.cursor()
        
        suggestions = []
        
        # 分析低成功率决策
        c.execute('''SELECT decision_type, COUNT(*) as total,
                     SUM(CASE WHEN result = 'success' THEN 1 ELSE 0 END) as successes
                     FROM decision_history 
                     WHERE executed = 1 AND created_at > datetime('now', '-7 days')
                     GROUP BY decision_type''')
        
        for row in c.fetchall():
            dtype, total, successes = row
            if total >= 3:
                success_rate = successes / total
                if success_rate < 0.6:
                    suggestions.append({
                        "type": "low_success_rate",
                        "decision_type": dtype,
                        "suggestion": f"决策类型 '{dtype}' 成功率仅 {success_rate*100:.1f}%, 建议优化决策逻辑",
                        "impact": 1 - success_rate,
                        "priority": "high"
                    })
                elif success_rate > 0.9:
                    suggestions.append({
                        "type": "high_success_rate",
                        "decision_type": dtype,
                        "suggestion": f"决策类型 '{dtype}' 表现优秀, 可考虑推广到其他场景",
                        "impact": 0.3,
                        "priority": "low"
                    })
        
        # 分析频繁决策
        c.execute('''SELECT decision_type, COUNT(*) as cnt
                     FROM decision_history 
                     WHERE created_at > datetime('now', '-24 hours')
                     GROUP BY decision_type HAVING cnt > 20''')
        
        for row in c.fetchall():
            dtype, cnt = row
            suggestions.append({
                "type": "high_frequency",
                "decision_type": dtype,
                "suggestion": f"决策类型 '{dtype}' 24小时内执行{cnt}次, 考虑合并或自动化",
                "impact": 0.5,
                "priority": "medium"
            })
        
        # 保存建议
        for s in suggestions:
            c.execute('''INSERT INTO optimization_suggestions (suggestion_type, suggestion, impact)
                         VALUES (?, ?, ?)''', (s["type"], s["suggestion"], s["impact"]))
        
        self.conn.commit()
        
        return {
            "suggestions": sorted(suggestions, key=lambda x: x["impact"], reverse=True),
            "count": len(suggestions)
        }


class DecisionAuditor:
    """决策审计器 - 完整决策追踪"""
    
    def __init__(self, conn):
        self.conn = conn
    
    def log_decision(self, decision_type, context, decision, confidence, risk_level):
        """记录决策"""
        c = self.conn.cursor()
        c.execute('''INSERT INTO decision_history 
                     (decision_type, context, decision, confidence, risk_level)
                     VALUES (?, ?, ?, ?, ?)''',
                  (decision_type, json.dumps(context), decision, confidence, risk_level))
        self.conn.commit()
        return c.lastrowid
    
    def execute_decision(self, decision_id, result):
        """记录决策执行结果"""
        c = self.conn.cursor()
        c.execute('''UPDATE decision_history 
                     SET executed = 1, result = ? WHERE id = ?''',
                  (result, decision_id))
        self.conn.commit()
    
    def get_audit_trail(self, decision_id=None, limit=20):
        """获取审计追踪"""
        c = self.conn.cursor()
        
        if decision_id:
            c.execute('''SELECT * FROM decision_history WHERE id = ?''', (decision_id,))
        else:
            c.execute('''SELECT * FROM decision_history ORDER BY created_at DESC LIMIT ?''', (limit,))
        
        columns = [desc[0] for desc in c.description]
        results = []
        for row in c.fetchall():
            results.append(dict(zip(columns, row)))
        
        return results


class DecisionEnhancedHandler(BaseHTTPRequestHandler):
    """增强决策引擎HTTP处理器"""
    
    conn = init_db()
    predictor = DecisionPredictor(conn)
    evaluator = ConfidenceEvaluator(conn)
    optimizer = OptimizationEngine(conn)
    auditor = DecisionAuditor(conn)
    
    def log_message(self, format, *args):
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/health":
            self.send_json({"service": "decision-enhanced", "status": "ok", "version": "3.0"})
        
        elif path == "/api/predict":
            dtype = params.get("type", ["general"])[0]
            context = json.loads(params.get("context", ["{}"])[0])
            result = self.predictor.predict(dtype, context)
            self.send_json(result)
        
        elif path == "/api/confidence":
            dtype = params.get("type", ["general"])[0]
            context = json.loads(params.get("context", ["{}"])[0])
            risk = int(params.get("risk", ["5"])[0])
            result = self.evaluator.evaluate(dtype, context, risk)
            self.send_json(result)
        
        elif path == "/api/optimize":
            dtype = params.get("type", [None])[0]
            result = self.optimizer.generate_suggestions(dtype)
            self.send_json(result)
        
        elif path == "/api/audit":
            did = params.get("id", [None])[0]
            limit = int(params.get("limit", [20])[0])
            result = self.auditor.get_audit_trail(did, limit)
            self.send_json({"audits": result, "count": len(result)})
        
        elif path == "/api/stats":
            c = self.conn.cursor()
            c.execute("SELECT COUNT(*) FROM decision_history")
            total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM decision_history WHERE executed = 1")
            executed = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM optimization_suggestions WHERE accepted = 0")
            pending_suggestions = c.fetchone()[0]
            self.send_json({
                "total_decisions": total,
                "executed_decisions": executed,
                "execution_rate": round(executed/total*100, 1) if total > 0 else 0,
                "pending_suggestions": pending_suggestions
            })
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else "{}"
        data = json.loads(body) if body else {}
        
        if path == "/api/decision":
            # 创建决策并自动评估置信度
            dtype = data.get("type", "general")
            context = data.get("context", {})
            decision = data.get("decision", "")
            risk_level = data.get("risk_level", 5)
            
            # 评估置信度
            confidence_data = self.evaluator.evaluate(dtype, context, risk_level)
            
            # 记录决策
            decision_id = self.auditor.log_decision(
                dtype, context, decision, 
                confidence_data["confidence"], risk_level
            )
            
            # 记录预测
            c = self.conn.cursor()
            c.execute('''INSERT INTO predictions (prediction_type, predicted_value, confidence)
                         VALUES (?, ?, ?)''',
                      (dtype, decision, confidence_data["confidence"]))
            self.conn.commit()
            
            self.send_json({
                "decision_id": decision_id,
                "decision": decision,
                "confidence": confidence_data,
                "auto_approved": confidence_data["confidence"] > 70
            })
        
        elif path == "/api/execute":
            # 执行决策
            decision_id = data.get("decision_id")
            result = data.get("result", "success")
            self.auditor.execute_decision(decision_id, result)
            self.send_json({"status": "executed", "decision_id": decision_id})
        
        elif path == "/api/optimize/accept":
            # 接受优化建议
            suggestion_id = data.get("suggestion_id")
            c = self.conn.cursor()
            c.execute("UPDATE optimization_suggestions SET accepted = 1 WHERE id = ?", (suggestion_id,))
            self.conn.commit()
            self.send_json({"status": "accepted", "suggestion_id": suggestion_id})
        
        else:
            self.send_json({"error": "Not found"}, 404)


def run_server(port=18255):
    """运行增强决策引擎服务"""
    server = HTTPServer(("0.0.0.0", port), DecisionEnhancedHandler)
    print(f"Decision Enhanced Engine running on port {port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server()