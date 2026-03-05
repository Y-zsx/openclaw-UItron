#!/usr/bin/env python3
"""
分布式追踪与监控增强API服务
功能：
- 分布式请求追踪
- 跨Agent调用链分析
- 性能指标聚合
- 分布式拓扑可视化
- 异常追踪与告警
"""

import json
import os
import sys
import subprocess
import psutil
import time
import uuid
import threading
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from collections import defaultdict
import traceback

# 配置
PORT = 18134
STATE_FILE = "/root/.openclaw/workspace/ultron-workflow/state.json"

class DistributedTracer:
    def __init__(self):
        self.traces = {}  # trace_id -> trace
        self.spans = defaultdict(list)  # trace_id -> list of spans
        self.metrics = defaultdict(lambda: {"count": 0, "total_time": 0, "errors": 0})
        self.trace_ttl = 3600  # 追踪数据保留1小时
        self.lock = threading.Lock()
        
    def create_trace(self, service_name, operation, metadata=None):
        """创建新的追踪链"""
        trace_id = str(uuid.uuid4())[:16]
        span_id = str(uuid.uuid4())[:8]
        
        trace = {
            "trace_id": trace_id,
            "service_name": service_name,
            "operation": operation,
            "start_time": datetime.now().isoformat(),
            "status": "started",
            "metadata": metadata or {},
            "spans": []
        }
        
        span = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_id": None,
            "service_name": service_name,
            "operation": operation,
            "start_time": datetime.now().isoformat(),
            "status": "started",
            "duration_ms": 0,
            "metadata": metadata or {}
        }
        
        with self.lock:
            self.traces[trace_id] = trace
            self.spans[trace_id].append(span)
        
        return {"trace_id": trace_id, "span_id": span_id}
    
    def add_span(self, trace_id, parent_span_id, service_name, operation, metadata=None):
        """添加子Span"""
        span_id = str(uuid.uuid4())[:8]
        
        span = {
            "span_id": span_id,
            "trace_id": trace_id,
            "parent_id": parent_span_id,
            "service_name": service_name,
            "operation": operation,
            "start_time": datetime.now().isoformat(),
            "status": "started",
            "duration_ms": 0,
            "metadata": metadata or {}
        }
        
        with self.lock:
            if trace_id in self.spans:
                self.spans[trace_id].append(span)
        
        return span_id
    
    def end_span(self, trace_id, span_id, status="ok", error=None):
        """结束Span"""
        with self.lock:
            if trace_id in self.spans:
                for span in self.spans[trace_id]:
                    if span["span_id"] == span_id:
                        span["end_time"] = datetime.now().isoformat()
                        span["status"] = status
                        if error:
                            span["error"] = error
                        
                        # 计算持续时间
                        start = datetime.fromisoformat(span["start_time"])
                        end = datetime.fromisoformat(span["end_time"])
                        span["duration_ms"] = round((end - start).total_seconds() * 1000, 2)
                        
                        # 更新指标
                        key = f"{span['service_name']}:{span['operation']}"
                        self.metrics[key]["count"] += 1
                        self.metrics[key]["total_time"] += span["duration_ms"]
                        if status != "ok":
                            self.metrics[key]["errors"] += 1
                        
                        break
    
    def end_trace(self, trace_id, status="ok"):
        """结束追踪链"""
        with self.lock:
            if trace_id in self.traces:
                self.traces[trace_id]["end_time"] = datetime.now().isoformat()
                self.traces[trace_id]["status"] = status
                
                # 计算总持续时间
                start = datetime.fromisoformat(self.traces[trace_id]["start_time"])
                end = datetime.fromisoformat(self.traces[trace_id]["end_time"])
                self.traces[trace_id]["duration_ms"] = round((end - start).total_seconds() * 1000, 2)
                
                # 添加所有spans到trace
                self.traces[trace_id]["spans"] = self.spans.get(trace_id, [])
    
    def get_trace(self, trace_id):
        """获取追踪详情"""
        with self.lock:
            return self.traces.get(trace_id)
    
    def get_recent_traces(self, limit=50):
        """获取最近的追踪列表"""
        with self.lock:
            traces = list(self.traces.values())
            traces.sort(key=lambda x: x.get("start_time", ""), reverse=True)
            return traces[:limit]
    
    def get_trace_tree(self, trace_id):
        """获取追踪的树形结构"""
        with self.lock:
            spans = self.spans.get(trace_id, [])
            if not spans:
                return None
            
            # 构建树
            span_map = {s["span_id"]: s for s in spans}
            root_spans = [s for s in spans if s.get("parent_id") is None]
            
            def build_tree(span, depth=0):
                result = {
                    "span_id": span["span_id"],
                    "service": span["service_name"],
                    "operation": span["operation"],
                    "duration_ms": span.get("duration_ms", 0),
                    "status": span.get("status", "unknown"),
                    "depth": depth,
                    "children": []
                }
                
                # 找子spans
                for s in spans:
                    if s.get("parent_id") == span["span_id"]:
                        result["children"].append(build_tree(s, depth + 1))
                
                return result
            
            return {
                "trace_id": trace_id,
                "roots": [build_tree(s) for s in root_spans]
            }
    
    def get_service_topology(self):
        """获取服务拓扑关系"""
        topology = {
            "nodes": {},
            "edges": []
        }
        
        with self.lock:
            # 统计服务关系
            service_calls = defaultdict(lambda: defaultdict(int))
            
            for trace_id, spans in self.spans.items():
                for span in spans:
                    service = span["service_name"]
                    if service not in topology["nodes"]:
                        topology["nodes"][service] = {
                            "name": service,
                            "call_count": 0,
                            "error_count": 0,
                            "avg_duration_ms": 0
                        }
                    
                    topology["nodes"][service]["call_count"] += 1
                    if span.get("status") != "ok":
                        topology["nodes"][service]["error_count"] += 1
                    
                    # 记录调用关系
                    if span.get("parent_id"):
                        parent_span = next((s for s in spans if s["span_id"] == span["parent_id"]), None)
                        if parent_span:
                            parent_service = parent_span["service_name"]
                            service_calls[parent_service][service] += 1
            
            # 构建边
            for from_service, calls in service_calls.items():
                for to_service, count in calls.items():
                    if from_service != to_service:
                        topology["edges"].append({
                            "from": from_service,
                            "to": to_service,
                            "count": count
                        })
            
            # 计算平均响应时间
            for key, m in self.metrics.items():
                service, op = key.split(":", 1)
                if service in topology["nodes"] and m["count"] > 0:
                    topology["nodes"][service]["avg_duration_ms"] = round(m["total_time"] / m["count"], 2)
        
        return topology
    
    def get_aggregated_metrics(self):
        """获取聚合指标"""
        with self.lock:
            result = {
                "total_traces": len(self.traces),
                "total_spans": sum(len(s) for s in self.spans.values()),
                "active_traces": sum(1 for t in self.traces.values() if t["status"] == "started"),
                "services": {},
                "timestamp": datetime.now().isoformat()
            }
            
            # 按服务聚合
            for key, m in self.metrics.items():
                service, op = key.split(":", 1)
                if service not in result["services"]:
                    result["services"][service] = {
                        "call_count": 0,
                        "total_time_ms": 0,
                        "errors": 0,
                        "operations": {}
                    }
                
                result["services"][service]["call_count"] += m["count"]
                result["services"][service]["total_time_ms"] += m["total_time"]
                result["services"][service]["errors"] += m["errors"]
                result["services"][service]["operations"][op] = {
                    "count": m["count"],
                    "avg_duration_ms": round(m["total_time"] / m["count"], 2) if m["count"] > 0 else 0,
                    "errors": m["errors"]
                }
            
            # 计算错误率
            for service, data in result["services"].items():
                if data["call_count"] > 0:
                    data["error_rate"] = round(data["errors"] / data["call_count"] * 100, 2)
                else:
                    data["error_rate"] = 0
            
            return result
    
    def get_error_traces(self, limit=20):
        """获取异常追踪"""
        with self.lock:
            errors = []
            for trace in self.traces.values():
                if trace.get("status") != "ok":
                    errors.append(trace)
            
            errors.sort(key=lambda x: x.get("start_time", ""), reverse=True)
            return errors[:limit]
    
    def cleanup_old_traces(self):
        """清理过期追踪"""
        with self.lock:
            cutoff = datetime.now() - timedelta(seconds=self.trace_ttl)
            to_remove = []
            
            for trace_id, trace in self.traces.items():
                try:
                    trace_time = datetime.fromisoformat(trace["start_time"])
                    if trace_time < cutoff:
                        to_remove.append(trace_id)
                except:
                    pass
            
            for trace_id in to_remove:
                del self.traces[trace_id]
                if trace_id in self.spans:
                    del self.spans[trace_id]
            
            return len(to_remove)

# 全局追踪器
tracer = DistributedTracer()

# 自动生成模拟追踪数据（用于演示）
def generate_demo_traces():
    """生成演示追踪数据"""
    services = ["api-gateway", "agent-scheduler", "task-executor", "data-processor", "notification-service"]
    operations = {
        "api-gateway": ["handle_request", "authenticate", "route"],
        "agent-scheduler": ["schedule_task", "allocate_resource", "check_capacity"],
        "task-executor": ["execute_task", "validate_result", "cleanup"],
        "data-processor": ["transform_data", "aggregate", "store"],
        "notification-service": ["send_alert", "push_notification", "send_email"]
    }
    
    # 创建几个演示追踪
    for i in range(5):
        service = services[i % len(services)]
        op = operations[service][0]
        
        result = tracer.create_trace(service, op, {"demo": True, "index": i})
        trace_id = result["trace_id"]
        span_id = result["span_id"]
        
        # 添加子span
        for j in range(2):
            child_service = services[(i + j + 1) % len(services)]
            child_op = operations[child_service][0]
            child_span_id = tracer.add_span(trace_id, span_id, child_service, child_op)
            
            time.sleep(0.01)
            tracer.end_span(trace_id, child_span_id, "ok")
        
        time.sleep(0.02)
        tracer.end_span(trace_id, span_id, "ok")
        tracer.end_trace(trace_id, "ok")

# 启动时生成演示数据
generate_demo_traces()

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/" or path == "/traces":
            # 获取追踪列表
            limit = int(params.get("limit", [50])[0])
            self.send_json(tracer.get_recent_traces(limit))
        elif path == "/trace" and "id" in params:
            # 获取单个追踪
            trace_id = params["id"][0]
            tree = params.get("tree", ["false"])[0] == "true"
            
            if tree:
                self.send_json(tracer.get_trace_tree(trace_id))
            else:
                self.send_json(tracer.get_trace(trace_id))
        elif path == "/topology":
            self.send_json(tracer.get_service_topology())
        elif path == "/metrics":
            self.send_json(tracer.get_aggregated_metrics())
        elif path == "/errors":
            limit = int(params.get("limit", [20])[0])
            self.send_json(tracer.get_error_traces(limit))
        elif path == "/cleanup":
            cleaned = tracer.cleanup_old_traces()
            self.send_json({"cleaned": cleaned, "timestamp": datetime.now().isoformat()})
        else:
            self.send_error(404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == "/trace/start":
            # 开始新追踪
            service = data.get("service", "unknown")
            operation = data.get("operation", "unknown")
            metadata = data.get("metadata", {})
            result = tracer.create_trace(service, operation, metadata)
            self.send_json({"success": True, **result})
        elif path == "/span/start":
            # 开始新span
            trace_id = data.get("trace_id")
            parent_span_id = data.get("parent_span_id")
            service = data.get("service", "unknown")
            operation = data.get("operation", "unknown")
            metadata = data.get("metadata", {})
            
            if not trace_id:
                self.send_json({"success": False, "error": "trace_id required"})
                return
            
            span_id = tracer.add_span(trace_id, parent_span_id, service, operation, metadata)
            self.send_json({"success": True, "span_id": span_id})
        elif path == "/span/end":
            # 结束span
            trace_id = data.get("trace_id")
            span_id = data.get("span_id")
            status = data.get("status", "ok")
            error = data.get("error")
            
            if not trace_id or not span_id:
                self.send_json({"success": False, "error": "trace_id and span_id required"})
                return
            
            tracer.end_span(trace_id, span_id, status, error)
            self.send_json({"success": True})
        elif path == "/trace/end":
            # 结束追踪
            trace_id = data.get("trace_id")
            status = data.get("status", "ok")
            
            if not trace_id:
                self.send_json({"success": False, "error": "trace_id required"})
                return
            
            tracer.end_trace(trace_id, status)
            self.send_json({"success": True})
        else:
            self.send_error(404)
    
    def send_json(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())

def run_server():
    # 启动后台清理线程
    def cleanup_thread():
        while True:
            time.sleep(300)  # 每5分钟清理一次
            tracer.cleanup_old_traces()
    
    cleanup = threading.Thread(target=cleanup_thread, daemon=True)
    cleanup.start()
    
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"📊 分布式追踪API启动: http://0.0.0.0:{PORT}")
    print(f"   追踪列表: http://0.0.0.0:{PORT}/traces")
    print(f"   单个追踪: http://0.0.0.0:{PORT}/trace?id=xxx")
    print(f"   追踪树: http://0.0.0.0:{PORT}/trace?id=xxx&tree=true")
    print(f"   服务拓扑: http://0.0.0.0:{PORT}/topology")
    print(f"   聚合指标: http://0.0.0.0:{PORT}/metrics")
    print(f"   异常追踪: http://0.0.0.0:{PORT}/errors")
    print(f"   开始追踪(POST): POST /trace/start")
    print(f"   开始Span(POST): POST /span/start")
    print(f"   结束Span(POST): POST /span/end")
    print(f"   结束追踪(POST): POST /trace/end")
    server.serve_forever()

if __name__ == "__main__":
    run_server()