#!/usr/bin/env python3
"""
工作流引擎 API 服务
端口: 8099
"""

import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

sys.path.insert(0, "/root/.openclaw/workspace/ultron/tools/workflow-engine")
from workflow_engine import WorkflowEngine, get_engine, TaskStatus, WorkflowStatus

PORT = 8099

class WorkflowAPIHandler(BaseHTTPRequestHandler):
    engine: WorkflowEngine = get_engine()
    
    def log_message(self, format, *args):
        pass  # 静默日志
    
    def send_json(self, status: int, data: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        
        if path == "/health":
            self.send_json(200, {"status": "ok", "service": "workflow-engine", "port": PORT})
        
        elif path == "/workflows":
            workflows = self.engine.list_workflows()
            self.send_json(200, {"workflows": workflows, "count": len(workflows)})
        
        elif path.startswith("/workflow/"):
            workflow_id = path.split("/")[-1]
            status = self.engine.get_workflow_status(workflow_id)
            if status:
                self.send_json(200, status)
            else:
                self.send_json(404, {"error": "Workflow not found"})
        
        elif path == "/types":
            self.send_json(200, {
                "task_types": ["shell", "http"],
                "statuses": {
                    "task": [s.value for s in TaskStatus],
                    "workflow": [s.value for s in WorkflowStatus]
                }
            })
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length).decode("utf-8")
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == "/workflows/create":
            name = data.get("name", "Untitled")
            description = data.get("description", "")
            tasks = data.get("tasks", [])
            
            if not tasks:
                self.send_json(400, {"error": "Tasks required"})
                return
            
            workflow_id = self.engine.create_workflow(name, description, tasks)
            self.send_json(201, {"success": True, "workflow_id": workflow_id})
        
        elif path == "/workflows/run":
            workflow_id = data.get("workflow_id")
            if not workflow_id:
                self.send_json(400, {"error": "workflow_id required"})
                return
            
            result = self.engine.run_workflow(workflow_id)
            if result.get("success"):
                self.send_json(200, result)
            else:
                self.send_json(400, result)
        
        elif path == "/workflows/cancel":
            workflow_id = data.get("workflow_id")
            if self.engine.cancel_workflow(workflow_id):
                self.send_json(200, {"success": True})
            else:
                self.send_json(400, {"error": "Cannot cancel"})
        
        else:
            self.send_json(404, {"error": "Not found"})
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/workflow/"):
            workflow_id = path.split("/")[-1]
            if self.engine.delete_workflow(workflow_id):
                self.send_json(200, {"success": True})
            else:
                self.send_json(404, {"error": "Not found"})
        else:
            self.send_json(404, {"error": "Not found"})


def run_server():
    server = HTTPServer(("0.0.0.0", PORT), WorkflowAPIHandler)
    print(f"[Workflow API] Started on port {PORT}")
    sys.stdout.flush()
    server.serve_forever()


if __name__ == "__main__":
    # 后台启动
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    time.sleep(1)
    
    # 等待
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass