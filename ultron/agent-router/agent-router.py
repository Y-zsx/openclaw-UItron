#!/usr/bin/env python3
"""
Agent服务智能路由系统
Intelligent Routing System for Agent Services
"""

import json
import time
import hashlib
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from datetime import datetime
import requests

PORT = 18311

# 路由配置
ROUTE_CONFIG = {
    "rules": [
        {
            "id": "rule_user_affinity",
            "name": "用户亲和性路由",
            "condition": "header:X-User-ID",
            "strategy": "sticky_session",
            "target_groups": ["premium", "standard"],
            "enabled": True
        },
        {
            "id": "rule_request_type",
            "name": "请求类型路由",
            "condition": "query:type",
            "strategy": "path_based",
            "target_groups": {
                "chat": ["standard"],
                "code": ["premium", "high_perf"],
                "analysis": ["high_perf"]
            },
            "enabled": True
        },
        {
            "id": "rule_region",
            "name": "区域路由",
            "condition": "header:X-Region",
            "strategy": "geo_based",
            "target_groups": {
                "cn": ["cn_primary", "cn_backup"],
                "us": ["us_primary", "us_backup"],
                "eu": ["eu_primary"]
            },
            "enabled": True
        },
        {
            "id": "rule_load",
            "name": "负载均衡路由",
            "condition": "always",
            "strategy": "least_load",
            "target_groups": ["premium", "standard", "high_perf"],
            "enabled": True
        }
    ],
    "target_groups": {
        "premium": ["localhost:8001", "localhost:8002"],
        "standard": ["localhost:8003", "localhost:8004", "localhost:8005"],
        "high_perf": ["localhost:8006"],
        "cn_primary": ["localhost:8010"],
        "cn_backup": ["localhost:8011"],
        "us_primary": ["localhost:8020"],
        "us_backup": ["localhost:8021"],
        "eu_primary": ["localhost:8030"]
    }
}

# 路由统计
ROUTING_STATS = {
    "total_requests": 0,
    "by_rule": {},
    "by_target_group": {},
    "by_target": {}
}

# 目标组负载状态
GROUP_LOAD = {group: {"active": 0, "total": 0, "latency": 0} for group in ROUTE_CONFIG["target_groups"]}

class RoutingHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # 禁用日志
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "service": "agent-router", "port": PORT}).encode())
            
        elif path == "/routes":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(ROUTE_CONFIG, indent=2, ensure_ascii=False).encode())
            
        elif path == "/stats":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            stats = {
                "routing_stats": ROUTING_STATS,
                "group_load": GROUP_LOAD,
                "timestamp": datetime.now().isoformat()
            }
            self.wfile.write(json.dumps(stats, indent=2, ensure_ascii=False).encode())
            
        elif path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({
                "service": "Agent智能路由系统",
                "port": PORT,
                "endpoints": ["/health", "/routes", "/stats", "/route/analyze", "/route/test"]
            }).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path == "/route/analyze" or path == "/route/test":
            length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length > 0 else "{}"
            try:
                request_data = json.loads(body) if body else {}
            except:
                request_data = {}
            
            # 分析路由决策
            result = self.analyze_routing(request_data)
            
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(result, indent=2, ensure_ascii=False).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def analyze_routing(self, request_data):
        """分析路由决策"""
        global ROUTING_STATS
        
        headers = request_data.get("headers", {})
        query = request_data.get("query", {})
        path = request_data.get("path", "/")
        
        matched_rules = []
        selected_group = None
        selected_targets = []
        
        # 按优先级匹配规则
        for rule in ROUTE_CONFIG["rules"]:
            if not rule.get("enabled", True):
                continue
            
            rule_id = rule["id"]
            strategy = rule["strategy"]
            
            # 匹配规则
            if rule["condition"] == "always":
                matched_rules.append({"rule": rule_id, "name": rule["name"], "matched": True})
                selected_group = self.apply_strategy(rule, headers, query)
                if selected_group:
                    break
            else:
                # 检查条件
                cond = rule["condition"]
                if cond.startswith("header:"):
                    header_name = cond[7:]
                    if header_name in headers:
                        matched_rules.append({"rule": rule_id, "name": rule["name"], "matched": True, "value": headers[header_name]})
                        selected_group = self.apply_strategy(rule, headers, query)
                        if selected_group:
                            break
                elif cond.startswith("query:"):
                    query_param = cond[6:]
                    if query_param in query:
                        matched_rules.append({"rule": rule_id, "name": rule["name"], "matched": True, "value": query[query_param]})
                        selected_group = self.apply_strategy(rule, headers, query)
                        if selected_group:
                            break
        
        # 获取目标列表
        if selected_group and selected_group in ROUTE_CONFIG["target_groups"]:
            selected_targets = ROUTE_CONFIG["target_groups"][selected_group]
        
        # 更新统计
        ROUTING_STATS["total_requests"] += 1
        for r in matched_rules:
            rule_id = r["rule"]
            ROUTING_STATS["by_rule"][rule_id] = ROUTING_STATS["by_rule"].get(rule_id, 0) + 1
        if selected_group:
            ROUTING_STATS["by_target_group"][selected_group] = ROUTING_STATS["by_target_group"].get(selected_group, 0) + 1
        
        return {
            "request": {
                "path": path,
                "headers": headers,
                "query": query
            },
            "matched_rules": matched_rules,
            "selected_group": selected_group,
            "selected_targets": selected_targets,
            "strategy": strategy if matched_rules else "default",
            "timestamp": datetime.now().isoformat()
        }
    
    def apply_strategy(self, rule, headers, query):
        """应用路由策略"""
        strategy = rule["strategy"]
        target_groups = rule.get("target_groups", {})
        
        if strategy == "sticky_session":
            user_id = headers.get("X-User-ID")
            if user_id:
                # 基于用户ID的哈希选择
                hash_val = int(hashlib.md5(user_id.encode()).hexdigest(), 16)
                groups = list(target_groups) if isinstance(target_groups, list) else list(target_groups.keys())
                return groups[hash_val % len(groups)]
            return groups[0] if isinstance(groups, list) else list(groups.keys())[0]
        
        elif strategy == "path_based":
            req_type = query.get("type", ["default"])[0]
            if isinstance(target_groups, dict):
                return target_groups.get(req_type, target_groups.get("default", []))[0] if target_groups.get(req_type) else None
            return target_groups[0] if target_groups else None
        
        elif strategy == "geo_based":
            region = headers.get("X-Region", "default")
            if isinstance(target_groups, dict):
                return target_groups.get(region, target_groups.get("default", []))[0] if target_groups.get(region) else None
            return target_groups[0] if target_groups else None
        
        elif strategy == "least_load":
            # 选择负载最低的组
            if isinstance(target_groups, list):
                min_load = float("inf")
                selected = None
                for group in target_groups:
                    load = GROUP_LOAD[group]["active"] / max(GROUP_LOAD[group]["total"], 1)
                    if load < min_load:
                        min_load = load
                        selected = group
                return selected
            return target_groups[0] if target_groups else None
        
        return target_groups[0] if isinstance(target_groups, list) else list(target_groups.keys())[0] if target_groups else None

def run_server():
    server = HTTPServer(("", PORT), RoutingHandler)
    print(f"🤖 Agent智能路由系统运行在端口 {PORT}")
    print(f"   - /health 健康检查")
    print(f"   - /routes 路由配置")
    print(f"   - /stats 路由统计")
    print(f"   - /route/analyze 路由分析")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
