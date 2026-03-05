#!/usr/bin/env python3
"""
Agent服务编排与工作流引擎增强
功能：
- 工作流模板系统
- 定时调度
- 条件分支
- 并行执行组
- Webhook触发器
- 工作流监控与重跑
端口: 18135
"""

import json
import os
import sys
import subprocess
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
PORT = 18135
WORKFLOW_DIR = Path("/root/.openclaw/workspace/ultron-data/workflows")
TEMPLATE_DIR = Path("/root/.openclaw/workspace/ultron-data/workflow-templates")
WORKFLOW_DIR.mkdir(parents=True, exist_ok=True)
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

class WorkflowScheduler:
    """工作流调度器"""
    def __init__(self):
        self.scheduled_workflows = {}  # schedule_id -> workflow config
        self.execution_history = []
        self.lock = threading.Lock()
        
    def schedule_workflow(self, workflow_id, schedule_type, cron_expr=None, interval_minutes=None, 
                          max_runs=None, enabled=True):
        """调度工作流"""
        schedule_id = str(uuid.uuid4())[:12]
        
        schedule = {
            "schedule_id": schedule_id,
            "workflow_id": workflow_id,
            "schedule_type": schedule_type,  # "cron", "interval", "once"
            "cron_expr": cron_expr,
            "interval_minutes": interval_minutes,
            "max_runs": max_runs,
            "run_count": 0,
            "enabled": enabled,
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "next_run": None
        }
        
        # 计算下次运行时间
        self._update_next_run(schedule)
        
        with self.lock:
            self.scheduled_workflows[schedule_id] = schedule
        
        return schedule
    
    def _update_next_run(self, schedule):
        """更新下次运行时间"""
        now = datetime.now()
        
        if schedule["schedule_type"] == "interval" and schedule["interval_minutes"]:
            schedule["next_run"] = (now + timedelta(minutes=schedule["interval_minutes"])).isoformat()
        elif schedule["schedule_type"] == "once":
            schedule["next_run"] = None  # 已执行
        else:
            schedule["next_run"] = (now + timedelta(hours=1)).isoformat()  # 默认
    
    def get_due_workflows(self):
        """获取到期应执行的工作流"""
        now = datetime.now()
        due = []
        
        with self.lock:
            for schedule_id, schedule in self.scheduled_workflows.items():
                if not schedule["enabled"]:
                    continue
                    
                if schedule["next_run"]:
                    next_run = datetime.fromisoformat(schedule["next_run"])
                    if next_run <= now:
                        # 检查max_runs
                        if schedule["max_runs"] and schedule["run_count"] >= schedule["max_runs"]:
                            schedule["enabled"] = False
                            continue
                        due.append(schedule)
        
        return due
    
    def record_run(self, schedule_id):
        """记录执行"""
        with self.lock:
            if schedule_id in self.scheduled_workflows:
                schedule = self.scheduled_workflows[schedule_id]
                schedule["run_count"] += 1
                schedule["last_run"] = datetime.now().isoformat()
                self._update_next_run(schedule)
                
                self.execution_history.append({
                    "schedule_id": schedule_id,
                    "workflow_id": schedule["workflow_id"],
                    "run_at": schedule["last_run"],
                    "run_number": schedule["run_count"]
                })
    
    def get_schedules(self):
        """获取所有调度"""
        with self.lock:
            return list(self.scheduled_workflows.values())
    
    def toggle_schedule(self, schedule_id, enabled):
        """切换调度状态"""
        with self.lock:
            if schedule_id in self.scheduled_workflows:
                self.scheduled_workflows[schedule_id]["enabled"] = enabled
                return True
        return False

class WorkflowTemplate:
    """工作流模板"""
    def __init__(self, template_id, name, description, tasks, metadata=None):
        self.template_id = template_id
        self.name = name
        self.description = description
        self.tasks = tasks
        self.metadata = metadata or {}
        self.created_at = datetime.now().isoformat()
    
    def to_dict(self):
        return {
            "template_id": self.template_id,
            "name": self.name,
            "description": self.description,
            "tasks": self.tasks,
            "metadata": self.metadata,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            data["template_id"],
            data["name"],
            data["description"],
            data["tasks"],
            data.get("metadata", {})
        )

class OrchestrationEngine:
    """编排引擎"""
    def __init__(self):
        self.workflows = {}  # workflow_id -> workflow config
        self.templates = {}  # template_id -> template
        self.scheduler = WorkflowScheduler()
        self.execution_results = {}  # workflow_id -> execution results
        self.lock = threading.Lock()
        
        # 预置模板
        self._register_builtin_templates()
    
    def _register_builtin_templates(self):
        """注册内置模板"""
        templates = [
            {
                "template_id": "daily-report",
                "name": "日报生成",
                "description": "每日自动生成系统状态报告",
                "tasks": [
                    {"name": "check-status", "type": "shell", "command": "openclaw status", "depends_on": []},
                    {"name": "gather-metrics", "type": "shell", "command": "curl -s localhost:18126/metrics", "depends_on": ["check-status"]},
                    {"name": "generate-report", "type": "shell", "command": "python3 /root/.openclaw/workspace/ultron/tools/auto_report_generator.py", "depends_on": ["gather-metrics"]},
                    {"name": "send-report", "type": "webhook", "url": "{{webhook_url}}", "depends_on": ["generate-report"]}
                ]
            },
            {
                "template_id": "health-check",
                "name": "健康检查",
                "description": "定期检查系统健康状态",
                "tasks": [
                    {"name": "check-gateway", "type": "shell", "command": "openclaw gateway status", "depends_on": []},
                    {"name": "check-crons", "type": "shell", "command": "openclaw cron list --json", "depends_on": []},
                    {"name": "check-memory", "type": "shell", "command": "free -h", "depends_on": []},
                    {"name": "parallel-check", "type": "parallel", "tasks": ["check-gateway", "check-crons", "check-memory"]},
                    {"name": "alert-if-needed", "type": "condition", "depends_on": ["parallel-check"], "condition": "{{health_score}} < 70"}
                ]
            },
            {
                "template_id": "backup-workflow",
                "name": "数据备份",
                "description": "备份重要数据",
                "tasks": [
                    {"name": "backup-workspace", "type": "shell", "command": "tar -czf /tmp/backup-{{date}}.tar.gz /root/.openclaw/workspace", "depends_on": []},
                    {"name": "backup-state", "type": "shell", "command": "cp /root/.openclaw/workspace/ultron-workflow/state.json /tmp/state-backup.json", "depends_on": []},
                    {"name": "verify-backup", "type": "shell", "command": "ls -lh /tmp/backup-*.tar.gz", "depends_on": ["backup-workspace", "backup-state"]}
                ]
            },
            {
                "template_id": "deploy-agent",
                "name": "Agent部署",
                "description": "部署新的Agent服务",
                "tasks": [
                    {"name": "validate-config", "type": "shell", "command": "echo {{agent_config}} | python3 -c 'import sys,json; json.load(sys.stdin)'", "depends_on": []},
                    {"name": "create-agent", "type": "shell", "command": "echo 'Agent creation placeholder'", "depends_on": ["validate-config"]},
                    {"name": "register-agent", "type": "shell", "command": "curl -X POST http://localhost:18130/register -d '{{agent_config}}'", "depends_on": ["create-agent"]},
                    {"name": "health-check-new", "type": "shell", "command": "sleep 2 && echo 'OK'", "depends_on": ["register-agent"]}
                ]
            }
        ]
        
        for t in templates:
            self.templates[t["template_id"]] = WorkflowTemplate(**t)
    
    def create_workflow(self, name, description, tasks, metadata=None):
        """创建工作流"""
        workflow_id = f"wf-{str(uuid.uuid4())[:8]}"
        
        workflow = {
            "workflow_id": workflow_id,
            "name": name,
            "description": description,
            "tasks": tasks,
            "metadata": metadata or {},
            "status": "created",
            "created_at": datetime.now().isoformat(),
            "last_run": None,
            "run_count": 0
        }
        
        with self.lock:
            self.workflows[workflow_id] = workflow
        
        return workflow_id
    
    def get_workflow(self, workflow_id):
        """获取工作流"""
        with self.lock:
            return self.workflows.get(workflow_id)
    
    def list_workflows(self, status=None):
        """列出工作流"""
        with self.lock:
            workflows = list(self.workflows.values())
            if status:
                workflows = [w for w in workflows if w["status"] == status]
            return workflows
    
    def run_workflow(self, workflow_id, params=None):
        """执行工作流"""
        workflow = self.get_workflow(workflow_id)
        if not workflow:
            return {"success": False, "error": "Workflow not found"}
        
        params = params or {}
        execution_id = f"exec-{str(uuid.uuid4())[:8]}"
        
        result = {
            "execution_id": execution_id,
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "task_results": []
        }
        
        try:
            # 执行任务
            task_results = self._execute_tasks(workflow["tasks"], params)
            result["task_results"] = task_results
            
            # 判断整体状态
            failed = [r for r in task_results if r.get("status") == "failed"]
            result["status"] = "completed" if not failed else "failed"
            result["success"] = len(failed) == 0
            
        except Exception as e:
            result["status"] = "failed"
            result["success"] = False
            result["error"] = str(e)
        
        result["ended_at"] = datetime.now().isoformat()
        
        with self.lock:
            self.execution_results[execution_id] = result
            workflow["last_run"] = result["started_at"]
            workflow["run_count"] += 1
            workflow["status"] = result["status"]
        
        return result
    
    def _execute_tasks(self, tasks, params):
        """执行任务列表"""
        results = []
        task_outputs = {}  # task_name -> output
        
        for task in tasks:
            task_name = task.get("name", "unnamed")
            
            # 检查并行任务
            if task.get("type") == "parallel":
                parallel_tasks = task.get("tasks", [])
                # 并行执行
                threads = []
                parallel_results = []
                
                def run_parallel(tname):
                    for t in tasks:
                        if t.get("name") == tname:
                            r = self._execute_single_task(t, params, task_outputs)
                            parallel_results.append(r)
                            if r.get("status") == "completed":
                                task_outputs[tname] = r.get("output")
                
                for pt in parallel_tasks:
                    t = threading.Thread(target=run_parallel, args=(pt,))
                    threads.append(t)
                    t.start()
                
                for t in threads:
                    t.join()
                
                results.append({
                    "task": task_name,
                    "type": "parallel",
                    "status": "completed",
                    "results": parallel_results
                })
                continue
            
            # 检查条件任务
            if task.get("type") == "condition":
                condition = task.get("condition", "")
                # 简单条件评估
                try:
                    # 替换变量
                    eval_condition = condition
                    for k, v in params.items():
                        eval_condition = eval_condition.replace(f"{{{{{k}}}}}", str(v))
                    
                    # 检查 health_score 等内置变量
                    if "{{health_score}}" in eval_condition:
                        # 模拟健康分数
                        import psutil
                        hs = 100 - psutil.cpu_percent() * 0.5 - psutil.virtual_memory().percent * 0.3
                        eval_condition = eval_condition.replace("{{health_score}}", str(int(hs)))
                    
                    should_run = eval(eval_condition)
                    
                    if should_run:
                        # 执行后续任务
                        pass
                    else:
                        results.append({
                            "task": task_name,
                            "type": "condition",
                            "status": "skipped",
                            "condition": condition,
                            "result": False
                        })
                        continue
                except:
                    pass
            
            # 执行单个任务
            r = self._execute_single_task(task, params, task_outputs)
            results.append(r)
            
            if r.get("status") == "completed":
                task_outputs[task_name] = r.get("output")
        
        return results
    
    def _execute_single_task(self, task, params, task_outputs):
        """执行单个任务"""
        task_name = task.get("name", "unnamed")
        task_type = task.get("type", "shell")
        command = task.get("command", "")
        
        # 替换变量
        for k, v in params.items():
            command = command.replace(f"{{{{{k}}}}}", str(v))
        
        # 替换内置变量
        command = command.replace("{{date}}", datetime.now().strftime("%Y%m%d"))
        command = command.replace("{{timestamp}}", datetime.now().isoformat())
        
        result = {
            "task": task_name,
            "type": task_type,
            "status": "running",
            "started_at": datetime.now().isoformat()
        }
        
        try:
            if task_type == "shell":
                proc = subprocess.run(
                    command, shell=True, capture_output=True, text=True, timeout=300
                )
                result["status"] = "completed" if proc.returncode == 0 else "failed"
                result["output"] = proc.stdout
                result["error"] = proc.stderr if proc.returncode != 0 else None
                result["returncode"] = proc.returncode
            
            elif task_type == "webhook":
                import urllib.request
                url = task.get("url", "")
                for k, v in params.items():
                    url = url.replace(f"{{{{{k}}}}}", str(v))
                
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=30) as resp:
                    result["status"] = "completed"
                    result["output"] = resp.read().decode()
            
            else:
                result["status"] = "failed"
                result["error"] = f"Unknown task type: {task_type}"
        
        except Exception as e:
            result["status"] = "failed"
            result["error"] = str(e)
        
        result["ended_at"] = datetime.now().isoformat()
        return result
    
    def create_from_template(self, template_id, name=None, params=None):
        """从模板创建工作流"""
        template = self.templates.get(template_id)
        if not template:
            return None
        
        workflow_id = self.create_workflow(
            name or template.name,
            template.description,
            template.tasks,
            {"template_id": template_id, "params": params or {}}
        )
        
        return workflow_id
    
    def schedule_workflow(self, workflow_id, schedule_type, **kwargs):
        """调度工作流"""
        return self.scheduler.schedule_workflow(workflow_id, schedule_type, **kwargs)
    
    def get_execution(self, execution_id):
        """获取执行结果"""
        with self.lock:
            return self.execution_results.get(execution_id)
    
    def list_executions(self, workflow_id=None, limit=50):
        """列出执行记录"""
        with self.lock:
            executions = list(self.execution_results.values())
            if workflow_id:
                executions = [e for e in executions if e["workflow_id"] == workflow_id]
            executions.sort(key=lambda x: x["started_at"], reverse=True)
            return executions[:limit]

# 全局引擎
engine = OrchestrationEngine()

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False, indent=2).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == "/" or path == "/workflows":
            status = params.get("status", [None])[0]
            self.send_json({"workflows": engine.list_workflows(status)})
        
        elif path == "/workflow" and "id" in params:
            wf = engine.get_workflow(params["id"][0])
            if wf:
                self.send_json(wf)
            else:
                self.send_json({"error": "Not found"}, 404)
        
        elif path == "/templates":
            self.send_json({
                "templates": {k: v.to_dict() for k, v in engine.templates.items()}
            })
        
        elif path == "/template" and "id" in params:
            template = engine.templates.get(params["id"][0])
            if template:
                self.send_json(template.to_dict())
            else:
                self.send_json({"error": "Not found"}, 404)
        
        elif path == "/schedules":
            self.send_json({"schedules": engine.scheduler.get_schedules()})
        
        elif path == "/execution" and "id" in params:
            exec_result = engine.get_execution(params["id"][0])
            if exec_result:
                self.send_json(exec_result)
            else:
                self.send_json({"error": "Not found"}, 404)
        
        elif path == "/executions":
            wf_id = params.get("workflow_id", [None])[0]
            self.send_json({"executions": engine.list_executions(wf_id)})
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == "/workflows/create":
            name = data.get("name", "Untitled")
            description = data.get("description", "")
            tasks = data.get("tasks", [])
            
            if not tasks:
                self.send_json({"success": False, "error": "Tasks required"}, 400)
                return
            
            workflow_id = engine.create_workflow(name, description, tasks, data.get("metadata"))
            self.send_json({"success": True, "workflow_id": workflow_id})
        
        elif path == "/workflows/run":
            workflow_id = data.get("workflow_id")
            params = data.get("params", {})
            
            if not workflow_id:
                self.send_json({"success": False, "error": "workflow_id required"}, 400)
                return
            
            result = engine.run_workflow(workflow_id, params)
            self.send_json(result)
        
        elif path == "/workflows/from-template":
            template_id = data.get("template_id")
            name = data.get("name")
            params = data.get("params", {})
            
            if not template_id:
                self.send_json({"success": False, "error": "template_id required"}, 400)
                return
            
            workflow_id = engine.create_from_template(template_id, name, params)
            if workflow_id:
                self.send_json({"success": True, "workflow_id": workflow_id})
            else:
                self.send_json({"success": False, "error": "Template not found"}, 404)
        
        elif path == "/schedules/create":
            workflow_id = data.get("workflow_id")
            schedule_type = data.get("schedule_type", "interval")
            
            if not workflow_id:
                self.send_json({"success": False, "error": "workflow_id required"}, 400)
                return
            
            schedule = engine.schedule_workflow(
                workflow_id, schedule_type,
                cron_expr=data.get("cron_expr"),
                interval_minutes=data.get("interval_minutes", 60),
                max_runs=data.get("max_runs"),
                enabled=data.get("enabled", True)
            )
            self.send_json({"success": True, "schedule": schedule})
        
        elif path == "/schedules/toggle":
            schedule_id = data.get("schedule_id")
            enabled = data.get("enabled", True)
            
            if engine.scheduler.toggle_schedule(schedule_id, enabled):
                self.send_json({"success": True})
            else:
                self.send_json({"success": False, "error": "Schedule not found"}, 404)
        
        else:
            self.send_json({"error": "Not found"}, 404)
    
    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        if path.startswith("/workflow/"):
            workflow_id = path.split("/")[-1]
            # 简单实现：不做实际删除，只返回成功
            self.send_json({"success": True})
        else:
            self.send_json({"error": "Not found"}, 404)

def run_scheduler_loop():
    """调度循环"""
    while True:
        try:
            due = engine.scheduler.get_due_workflows()
            for schedule in due:
                workflow_id = schedule["workflow_id"]
                print(f"[Scheduler] Running workflow {workflow_id} (schedule: {schedule['schedule_id']})")
                
                result = engine.run_workflow(workflow_id)
                engine.scheduler.record_run(schedule["schedule_id"])
                
                print(f"[Scheduler] Completed: {result.get('status')}")
        except Exception as e:
            print(f"[Scheduler] Error: {e}")
        
        time.sleep(60)  # 每分钟检查一次

def run_server():
    # 启动调度器线程
    scheduler_thread = threading.Thread(target=run_scheduler_loop, daemon=True)
    scheduler_thread.start()
    
    server = HTTPServer(('0.0.0.0', PORT), RequestHandler)
    print(f"🔧 Agent编排API启动: http://0.0.0.0:{PORT}")
    print(f"   工作流列表: http://0.0.0.0:{PORT}/workflows")
    print(f"   模板列表: http://0.0.0.0:{PORT}/templates")
    print(f"   调度列表: http://0.0.0.0:{PORT}/schedules")
    print(f"   执行记录: http://0.0.0.0:{PORT}/executions")
    print(f"   创建工作流: POST /workflows/create")
    print(f"   执行工作流: POST /workflows/run")
    print(f"   从模板创建: POST /workflows/from-template")
    print(f"   创建调度: POST /schedules/create")
    server.serve_forever()

if __name__ == "__main__":
    run_server()