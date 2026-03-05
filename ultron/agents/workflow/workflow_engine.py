#!/usr/bin/env python3
"""
工作流编排引擎 - Workflow Orchestration Engine
智能运维助手系统 - 第43世

功能:
- 工作流定义与DSL
- 任务依赖管理
- 并行/串行执行
- 状态持久化
- 错误处理与重试
"""

import json
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from flask import Flask, jsonify, request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== 数据模型 ====================

class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

@dataclass
class WorkflowTask:
    id: str
    name: str
    action: str  # action类型: http/shell/sleep/condition/callback
    params: Dict[str, Any]
    depends_on: List[str] = field(default_factory=list)
    retry: int = 0
    timeout: int = 300
    status: str = "pending"
    result: Optional[Dict] = None
    error: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attempts: int = 0

@dataclass
class Workflow:
    id: str
    name: str
    description: str
    tasks: List[WorkflowTask]
    status: str = "pending"
    created_at: str = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    result: Optional[Dict] = None
    error: Optional[str] = None

# ==================== 工作流引擎核心 ====================

class WorkflowEngine:
    """工作流编排引擎"""
    
    def __init__(self, db_path: str = "/root/.openclaw/workspace/ultron/agents/workflow/data/workflows.db"):
        self.db_path = db_path
        self._init_db()
        self.executors: Dict[str, Callable] = {
            "http": self._exec_http,
            "shell": self._exec_shell,
            "sleep": self._exec_sleep,
            "condition": self._exec_condition,
            "callback": self._exec_callback,
        }
        self.running_workflows: Dict[str, threading.Thread] = {}
        
    def _init_db(self):
        """初始化数据库"""
        import os
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 工作流表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflows (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                tasks_json TEXT,
                status TEXT,
                created_at TEXT,
                started_at TEXT,
                completed_at TEXT,
                result_json TEXT,
                error TEXT
            )
        ''')
        
        # 任务表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workflow_tasks (
                id TEXT PRIMARY KEY,
                workflow_id TEXT NOT NULL,
                name TEXT NOT NULL,
                action TEXT NOT NULL,
                params_json TEXT,
                depends_on_json TEXT,
                retry INTEGER DEFAULT 0,
                timeout INTEGER DEFAULT 300,
                status TEXT DEFAULT 'pending',
                result_json TEXT,
                error TEXT,
                start_time TEXT,
                end_time TEXT,
                attempts INTEGER DEFAULT 0,
                FOREIGN KEY (workflow_id) REFERENCES workflows(id)
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ==================== 工作流管理 ====================
    
    def create_workflow(self, name: str, description: str = "", tasks: List[Dict] = None) -> str:
        """创建工作流"""
        workflow_id = f"wf_{uuid.uuid4().hex[:12]}"
        
        task_objects = []
        if tasks:
            for t in tasks:
                task = WorkflowTask(
                    id=f"task_{uuid.uuid4().hex[:8]}",
                    name=t.get("name", ""),
                    action=t.get("action", "shell"),
                    params=t.get("params", {}),
                    depends_on=t.get("depends_on", []),
                    retry=t.get("retry", 0),
                    timeout=t.get("timeout", 300)
                )
                task_objects.append(task)
        
        workflow = Workflow(
            id=workflow_id,
            name=name,
            description=description,
            tasks=task_objects,
            created_at=datetime.now().isoformat()
        )
        
        conn = self._get_db()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO workflows (id, name, description, tasks_json, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (workflow.id, workflow.name, workflow.description, 
              json.dumps([asdict(t) for t in workflow.tasks]), 
              workflow.status, workflow.created_at))
        
        # 保存任务
        for task in workflow.tasks:
            cursor.execute('''
                INSERT INTO workflow_tasks 
                (id, workflow_id, name, action, params_json, depends_on_json, retry, timeout)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (task.id, workflow_id, task.name, task.action, 
                  json.dumps(task.params), json.dumps(task.depends_on),
                  task.retry, task.timeout))
        
        conn.commit()
        conn.close()
        
        logger.info(f"Created workflow: {workflow_id}")
        return workflow_id
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workflows WHERE id = ?', (workflow_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
            
        workflow = dict(row)
        workflow['tasks'] = []
        
        cursor.execute('SELECT * FROM workflow_tasks WHERE workflow_id = ?', (workflow_id,))
        for task_row in cursor.fetchall():
            task = dict(task_row)
            task['params'] = json.loads(task['params_json'])
            task['depends_on'] = json.loads(task['depends_on_json'])
            del task['params_json'], task['depends_on_json']
            workflow['tasks'].append(task)
        
        conn.close()
        return workflow
    
    def list_workflows(self, status: str = None, limit: int = 50) -> List[Dict]:
        """列出工作流"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        if status:
            cursor.execute('SELECT * FROM workflows ORDER BY created_at DESC LIMIT ?', (limit,))
        else:
            cursor.execute('SELECT * FROM workflows ORDER BY created_at DESC LIMIT ?', (limit,))
            
        workflows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return workflows
    
    # ==================== 工作流执行 ====================
    
    def execute_workflow(self, workflow_id: str, async_mode: bool = True) -> Dict:
        """执行工作流"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM workflows WHERE id = ?', (workflow_id,))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return {"error": "Workflow not found"}
        
        workflow = dict(row)
        workflow['tasks'] = []
        
        cursor.execute('SELECT * FROM workflow_tasks WHERE workflow_id = ?', (workflow_id,))
        for task_row in cursor.fetchall():
            task = dict(task_row)
            task['params'] = json.loads(task['params_json'])
            task['depends_on'] = json.loads(task['depends_on_json'])
            del task['params_json'], task['depends_on_json']
            workflow['tasks'].append(task)
        
        conn.close()
        
        # 更新状态
        self._update_workflow_status(workflow_id, "running", started_at=datetime.now().isoformat())
        
        if async_mode:
            thread = threading.Thread(target=self._run_workflow, args=(workflow,))
            thread.start()
            return {"workflow_id": workflow_id, "status": "started", "mode": "async"}
        else:
            return self._run_workflow(workflow)
    
    def _run_workflow(self, workflow: Dict) -> Dict:
        """运行工作流"""
        workflow_id = workflow['id']
        task_results = {}
        
        try:
            # 构建依赖图
            task_map = {t['id']: t for t in workflow['tasks']}
            
            # 拓扑排序
            sorted_tasks = self._topological_sort(workflow['tasks'])
            
            # 执行每个任务
            for task in sorted_tasks:
                task_id = task['id']
                
                # 检查依赖是否完成
                depends_on = task.get('depends_on', [])
                for dep_id in depends_on:
                    if task_results.get(dep_id, {}).get('status') != 'completed':
                        task['status'] = 'skipped'
                        task_results[task_id] = {'status': 'skipped'}
                        continue
                
                # 执行任务
                logger.info(f"Executing task: {task['name']}")
                result = self._execute_task(task, task_results)
                task_results[task_id] = result
                
                # 检查是否失败
                if result['status'] == 'failed':
                    if task['retry'] > task['attempts']:
                        # 重试
                        task['attempts'] += 1
                        logger.warning(f"Retrying task: {task['name']}, attempt {task['attempts']}")
                        time.sleep(2)
                        result = self._execute_task(task, task_results)
                        task_results[task_id] = result
                    
                    if result['status'] == 'failed':
                        self._update_workflow_status(workflow_id, "failed", error=result.get('error'))
                        return {"status": "failed", "error": result.get('error')}
            
            # 所有任务完成
            self._update_workflow_status(workflow_id, "completed", 
                                         completed_at=datetime.now().isoformat(),
                                         result=task_results)
            return {"status": "completed", "results": task_results}
            
        except Exception as e:
            logger.error(f"Workflow execution error: {e}")
            self._update_workflow_status(workflow_id, "failed", error=str(e))
            return {"status": "failed", "error": str(e)}
    
    def _topological_sort(self, tasks: List[Dict]) -> List[Dict]:
        """拓扑排序"""
        task_map = {t['id']: t for t in tasks}
        in_degree = {t['id']: 0 for t in tasks}
        
        for task in tasks:
            for dep in task.get('depends_on', []):
                in_degree[task['id']] += 1
        
        sorted_tasks = []
        queue = [t['id'] for t in tasks if in_degree[t['id']] == 0]
        
        while queue:
            task_id = queue.pop(0)
            sorted_tasks.append(task_map[task_id])
            
            for task in tasks:
                if task_id in task.get('depends_on', []):
                    in_degree[task['id']] -= 1
                    if in_degree[task['id']] == 0:
                        queue.append(task['id'])
        
        return sorted_tasks
    
    def _execute_task(self, task: Dict, context: Dict) -> Dict:
        """执行单个任务"""
        task_id = task['id']
        action = task.get('action', 'shell')
        params = task.get('params', {})
        
        # 更新任务状态为running
        self._update_task_status(task_id, "running", start_time=datetime.now().isoformat())
        
        try:
            executor = self.executors.get(action, self._exec_shell)
            
            # 替换参数中的上下文变量
            params = self._resolve_params(params, context)
            
            result = executor(params)
            
            self._update_task_status(task_id, "completed", 
                                    end_time=datetime.now().isoformat(),
                                    result=result)
            
            return {"status": "completed", "result": result}
            
        except Exception as e:
            logger.error(f"Task execution error: {e}")
            self._update_task_status(task_id, "failed", 
                                    end_time=datetime.now().isoformat(),
                                    error=str(e))
            return {"status": "failed", "error": str(e)}
    
    def _resolve_params(self, params: Dict, context: Dict) -> Dict:
        """解析参数中的变量"""
        resolved = {}
        for k, v in params.items():
            if isinstance(v, str) and v.startswith('${') and v.endswith('}'):
                var = v[2:-1]
                # 从context中获取变量
                parts = var.split('.')
                val = context
                for p in parts:
                    val = val.get(p, {})
                resolved[k] = val
            else:
                resolved[k] = v
        return resolved
    
    # ==================== 任务执行器 ====================
    
    def _exec_http(self, params: Dict) -> Dict:
        """HTTP请求执行器"""
        import requests
        
        method = params.get('method', 'GET')
        url = params.get('url', '')
        headers = params.get('headers', {})
        body = params.get('body')
        timeout = params.get('timeout', 30)
        
        try:
            response = requests.request(method, url, headers=headers, json=body, timeout=timeout)
            return {
                "status_code": response.status_code,
                "body": response.text[:1000],
                "headers": dict(response.headers)
            }
        except Exception as e:
            raise Exception(f"HTTP request failed: {e}")
    
    def _exec_shell(self, params: Dict) -> Dict:
        """Shell命令执行器"""
        import subprocess
        
        command = params.get('command', '')
        timeout = params.get('timeout', 60)
        
        try:
            result = subprocess.run(command, shell=True, capture_output=True, 
                                   text=True, timeout=timeout)
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:1000]
            }
        except subprocess.TimeoutExpired:
            raise Exception(f"Shell command timeout: {command}")
        except Exception as e:
            raise Exception(f"Shell command failed: {e}")
    
    def _exec_sleep(self, params: Dict) -> Dict:
        """延迟执行器"""
        seconds = params.get('seconds', 1)
        time.sleep(seconds)
        return {"slept": seconds}
    
    def _exec_condition(self, params: Dict) -> Dict:
        """条件执行器"""
        condition = params.get('condition', '')
        # 简单的条件评估
        try:
            result = eval(condition, {"context": params.get('context', {})})
            return {"condition_met": result, "evaluated": condition}
        except:
            return {"condition_met": False, "error": "Condition evaluation failed"}
    
    def _exec_callback(self, params: Dict) -> Dict:
        """回调执行器"""
        # 调用外部回调函数
        callback_url = params.get('url', '')
        if callback_url:
            return self._exec_http({"url": callback_url, "method": "POST", 
                                   "body": params.get('data', {})})
        return {"status": "no_callback"}
    
    # ==================== 状态更新 ====================
    
    def _update_workflow_status(self, workflow_id: str, status: str, 
                                started_at: str = None, completed_at: str = None,
                                result: Dict = None, error: str = None):
        """更新工作流状态"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        values = [status]
        
        if started_at:
            updates.append("started_at = ?")
            values.append(started_at)
        if completed_at:
            updates.append("completed_at = ?")
            values.append(completed_at)
        if result:
            updates.append("result_json = ?")
            values.append(json.dumps(result))
        if error:
            updates.append("error = ?")
            values.append(error)
        
        values.append(workflow_id)
        
        cursor.execute(f"UPDATE workflows SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()
    
    def _update_task_status(self, task_id: str, status: str, 
                           start_time: str = None, end_time: str = None,
                           result: Dict = None, error: str = None):
        """更新任务状态"""
        conn = self._get_db()
        cursor = conn.cursor()
        
        updates = ["status = ?"]
        values = [status]
        
        if start_time:
            updates.append("start_time = ?")
            values.append(start_time)
        if end_time:
            updates.append("end_time = ?")
            values.append(end_time)
        if result:
            updates.append("result_json = ?")
            values.append(json.dumps(result))
        if error:
            updates.append("error = ?")
            values.append(error)
        
        values.append(task_id)
        
        cursor.execute(f"UPDATE workflow_tasks SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()
    
    # ==================== 工作流控制 ====================
    
    def pause_workflow(self, workflow_id: str) -> Dict:
        """暂停工作流"""
        self._update_workflow_status(workflow_id, "paused")
        return {"status": "paused", "workflow_id": workflow_id}
    
    def cancel_workflow(self, workflow_id: str) -> Dict:
        """取消工作流"""
        self._update_workflow_status(workflow_id, "cancelled")
        return {"status": "cancelled", "workflow_id": workflow_id}
    
    def retry_workflow(self, workflow_id: str) -> Dict:
        """重试工作流"""
        # 重置任务状态
        conn = self._get_db()
        cursor = conn.cursor()
        cursor.execute("UPDATE workflow_tasks SET status = 'pending', result_json = NULL, error = NULL WHERE workflow_id = ?", (workflow_id,))
        conn.commit()
        conn.close()
        
        return self.execute_workflow(workflow_id)

# ==================== REST API ====================

app = Flask(__name__)
engine = WorkflowEngine()

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "workflow-engine"})

@app.route('/api/workflows', methods=['GET'])
def list_workflows():
    status = request.args.get('status')
    limit = int(request.args.get('limit', 50))
    return jsonify(engine.list_workflows(status, limit))

@app.route('/api/workflows', methods=['POST'])
def create_workflow():
    data = request.json
    workflow_id = engine.create_workflow(
        name=data.get('name', 'Unnamed'),
        description=data.get('description', ''),
        tasks=data.get('tasks', [])
    )
    return jsonify({"workflow_id": workflow_id})

@app.route('/api/workflows/<workflow_id>', methods=['GET'])
def get_workflow(workflow_id):
    workflow = engine.get_workflow(workflow_id)
    if not workflow:
        return jsonify({"error": "Not found"}), 404
    return jsonify(workflow)

@app.route('/api/workflows/<workflow_id>/execute', methods=['POST'])
def execute_workflow(workflow_id):
    result = engine.execute_workflow(workflow_id)
    return jsonify(result)

@app.route('/api/workflows/<workflow_id>/pause', methods=['POST'])
def pause_workflow(workflow_id):
    return jsonify(engine.pause_workflow(workflow_id))

@app.route('/api/workflows/<workflow_id>/cancel', methods=['POST'])
def cancel_workflow(workflow_id):
    return jsonify(engine.cancel_workflow(workflow_id))

@app.route('/api/workflows/<workflow_id>/retry', methods=['POST'])
def retry_workflow(workflow_id):
    return jsonify(engine.retry_workflow(workflow_id))

@app.route('/api/templates', methods=['GET'])
def list_templates():
    """预定义工作流模板"""
    templates = [
        {
            "id": "server_health_check",
            "name": "服务器健康检查",
            "description": "检查服务器CPU、内存、磁盘、网络状态",
            "tasks": [
                {"name": "检查CPU", "action": "shell", "params": {"command": "uptime"}},
                {"name": "检查内存", "action": "shell", "params": {"command": "free -h"}},
                {"name": "检查磁盘", "action": "shell", "params": {"command": "df -h"}},
                {"name": "检查网络", "action": "shell", "params": {"command": "netstat -tuln"}},
                {"name": "发送通知", "action": "callback", "params": {"url": "${result.callback_url}"}, "depends_on": ["task1", "task2", "task3", "task4"]}
            ]
        },
        {
            "id": "deploy_service",
            "name": "服务部署流程",
            "description": "拉取代码、构建、部署、验证",
            "tasks": [
                {"name": "拉取代码", "action": "shell", "params": {"command": "git pull"}},
                {"name": "构建", "action": "shell", "params": {"command": "make build"}, "depends_on": ["task1"]},
                {"name": "停止服务", "action": "shell", "params": {"command": "systemctl stop app"}, "depends_on": ["task2"]},
                {"name": "部署", "action": "shell", "params": {"command": "cp -r dist/* /opt/app/"}, "depends_on": ["task3"]},
                {"name": "启动服务", "action": "shell", "params": {"command": "systemctl start app"}, "depends_on": ["task4"]},
                {"name": "验证", "action": "http", "params": {"url": "http://localhost:8080/health"}, "depends_on": ["task5"]}
            ]
        },
        {
            "id": "backup_database",
            "name": "数据库备份",
            "description": "备份数据库到远程存储",
            "tasks": [
                {"name": "创建备份", "action": "shell", "params": {"command": "pg_dump -Fc db > /tmp/backup.dump"}},
                {"name": "压缩", "action": "shell", "params": {"command": "gzip /tmp/backup.dump"}, "depends_on": ["task1"]},
                {"name": "上传", "action": "shell", "params": {"command": "rclone copy /tmp/backup.dump.gz remote:backups/"}, "depends_on": ["task2"]},
                {"name": "清理本地", "action": "shell", "params": {"command": "rm /tmp/backup.dump.gz"}, "depends_on": ["task3"]}
            ]
        }
    ]
    return jsonify(templates)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=18100, debug=False)