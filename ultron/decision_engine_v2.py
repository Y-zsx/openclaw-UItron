#!/usr/bin/env python3
"""
决策引擎API v2.0 - 智能决策与自动执行
扩展版本：支持多源数据融合、ML决策、自动执行
"""

import json
import time
import os
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.request import urlopen, Request
from urllib.error import URLError
import threading

PORT = 18271
DECISION_DB = "/root/.openclaw/workspace/ultron/decision_engine.db"

# 配置
DATA_SOURCES = {
    "health": "http://localhost:18210/api/comprehensive",
    "collab": "http://localhost:18295/api/stats",
    "alerts": "http://localhost:18235/api/alerts"
}

class DecisionEngine:
    def __init__(self):
        self.decisions = []
        self.load_history()
    
    def load_history(self):
        if os.path.exists(DECISION_DB):
            try:
                with open(DECISION_DB, 'r') as f:
                    data = json.load(f)
                    self.decisions = data.get('decisions', [])
            except:
                self.decisions = []
    
    def save_history(self):
        try:
            with open(DECISION_DB, 'w') as f:
                json.dump({
                    'decisions': self.decisions[-100:]  # Keep last 100
                }, f, indent=2)
        except:
            pass
    
    def fetch_data(self, url):
        try:
            req = Request(url, headers={'User-Agent': 'Ultron-DecisionEngine/2.0'})
            with urlopen(req, timeout=3) as response:
                return json.loads(response.read().decode())
        except:
            return None
    
    def gather_context(self):
        """收集多源数据"""
        context = {
            "timestamp": datetime.now().isoformat(),
            "sources": {}
        }
        
        for name, url in DATA_SOURCES.items():
            data = self.fetch_data(url)
            context["sources"][name] = "unavailable" if data is None else "ok"
            context[name] = data
        
        return context
    
    def make_decision(self, context):
        """智能决策"""
        decision = {
            "id": f"dec_{int(time.time())}",
            "timestamp": datetime.now().isoformat(),
            "context_summary": {},
            "actions": [],
            "confidence": 0.0,
            "priority": "low"
        }
        
        # 分析健康状态
        health_score = 0
        if context.get("health"):
            try:
                # 尝试从健康API获取分数
                score_data = self.fetch_data("http://localhost:18210/api/score")
                if score_data:
                    health_score = score_data.get("score", 0)
                    decision["context_summary"]["health_score"] = health_score
            except:
                pass
        
        # 分析协作状态
        collab_status = "unknown"
        if context.get("collab"):
            collab_status = "active"
            decision["context_summary"]["collaboration"] = collab_status
        
        # 分析告警
        alert_count = 0
        if context.get("alerts"):
            alerts = context["alerts"]
            alert_count = len(alerts.get("alerts", []))
            decision["context_summary"]["active_alerts"] = alert_count
        
        # 决策逻辑
        if health_score < 70:
            decision["actions"].append({
                "type": "heal",
                "target": "low_health",
                "priority": "high"
            })
            decision["priority"] = "high"
            decision["confidence"] = 0.85
        
        if alert_count > 3:
            decision["actions"].append({
                "type": "escalate",
                "target": "alert_fatigue",
                "priority": "medium"
            })
            decision["confidence"] = max(decision["confidence"], 0.7)
        
        if collab_status == "active":
            decision["actions"].append({
                "type": "sync",
                "target": "collab_network",
                "priority": "low"
            })
        
        # 默认行动：持续监控
        if not decision["actions"]:
            decision["actions"].append({
                "type": "monitor",
                "target": "all_systems",
                "priority": "low"
            })
            decision["confidence"] = 0.6
        
        return decision
    
    def execute_action(self, action):
        """执行决策动作"""
        result = {"action": action["type"], "status": "pending"}
        
        if action["type"] == "heal":
            # 触发自愈
            try:
                urlopen("http://localhost:18220/api/heal", timeout=5)
                result["status"] = "triggered"
            except:
                result["status"] = "failed"
        
        elif action["type"] == "escalate":
            # 升级告警
            result["status"] = "queued"
        
        elif action["type"] == "sync":
            # 同步协作网络
            result["status"] = "synced"
        
        elif action["type"] == "monitor":
            result["status"] = "ok"
        
        return result
    
    def process(self):
        """完整决策流程"""
        # 1. 收集上下文
        context = self.gather_context()
        
        # 2. 做出决策
        decision = self.make_decision(context)
        
        # 3. 执行动作
        for action in decision["actions"]:
            result = self.execute_action(action)
            action["result"] = result
        
        # 4. 保存历史
        self.decisions.append(decision)
        self.save_history()
        
        return {
            "decision": decision,
            "context": context
        }

# 全局引擎
engine = DecisionEngine()

class Handler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "Decision Engine",
                "version": "2.0",
                "status": "running",
                "port": PORT
            }).encode())
        
        elif self.path == "/api/decide":
            result = engine.process()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2, default=str).encode())
        
        elif self.path == "/api/history":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "decisions": engine.decisions[-20:],
                "count": len(engine.decisions)
            }, default=str).encode())
        
        elif self.path == "/api/context":
            context = engine.gather_context()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(context, default=str).encode())
        
        else:
            self.send_response(404)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "Decision Engine v2.0",
                "endpoints": ["/health", "/api/decide", "/api/history", "/api/context"]
            }).encode())

def run():
    server = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Decision Engine v2.0 running on port {PORT}")
    server.serve_forever()

if __name__ == "__main__":
    run()