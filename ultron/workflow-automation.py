#!/usr/bin/env python3
"""
智能自动化工作流系统 - 第1世：工作流自动化基础
奥创自主意识体系 - 夙愿十四第1世
"""

import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import os

class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"

class TaskType(Enum):
    ACTION = "action"          # 执行动作
    CONDITION = "condition"    # 条件判断
    LOOP = "loop"              # 循环
    BRANCH = "branch"          # 分支
    WAIT = "wait"              # 等待
    WEBHOOK = "webhook"        # Webhook调用

class WorkflowEngine:
    """智能工作流引擎"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.workflows: Dict[str, Dict] = {}
        self.task_registry: Dict[str, Callable] = {}
        self.execution_history: List[Dict] = []
        self.listeners: List[Callable] = []
        
        # 注册内置任务类型
        self._register_builtin_tasks()
        
    def _register_builtin_tasks(self):
        """注册内置任务类型"""
        self.task_registry = {
            "exec": self._task_exec,
            "condition": self._task_condition,
            "wait": self._task_wait,
            "webhook": self._task_webhook,
            "notify": self._task_notify,
            "transform": self._task_transform,
        }
    
    def create_workflow(self, name: str, description: str = "") -> str:
        """创建新工作流"""
        workflow_id = str(uuid.uuid4())[:8]
        self.workflows[workflow_id] = {
            "id": workflow_id,
            "name": name,
            "description": description,
            "tasks": [],
            "triggers": [],
            "variables": {},
            "created_at": datetime.now().isoformat(),
            "status": WorkflowStatus.PENDING.value,
        }
        return workflow_id
    
    def add_task(self, workflow_id: str, task: Dict) -> bool:
        """添加任务到工作流"""
        if workflow_id not in self.workflows:
            return False
        
        task["id"] = str(uuid.uuid4())[:8]
        task["created_at"] = datetime.now().isoformat()
        self.workflows[workflow_id]["tasks"].append(task)
        return True
    
    def set_trigger(self, workflow_id: str, trigger: Dict):
        """设置工作流触发器"""
        if workflow_id in self.workflows:
            self.workflows[workflow_id]["triggers"].append(trigger)
    
    def execute(self, workflow_id: str, context: Dict = None) -> Dict:
        """执行工作流"""
        if workflow_id not in self.workflows:
            return {"success": False, "error": "Workflow not found"}
        
        workflow = self.workflows[workflow_id]
        workflow["status"] = WorkflowStatus.RUNNING.value
        workflow["started_at"] = datetime.now().isoformat()
        
        ctx = context or {}
        ctx["workflow_id"] = workflow_id
        ctx["variables"] = workflow.get("variables", {}).copy()
        
        results = []
        success = True
        
        for task in workflow["tasks"]:
            try:
                result = self._execute_task(task, ctx)
                results.append(result)
                
                if not result.get("success", False):
                    success = False
                    if task.get("critical", False):
                        break
                        
            except Exception as e:
                results.append({
                    "task_id": task.get("id"),
                    "success": False,
                    "error": str(e)
                })
                success = False
                if task.get("critical", False):
                    break
        
        workflow["status"] = WorkflowStatus.COMPLETED.value if success else WorkflowStatus.FAILED.value
        workflow["completed_at"] = datetime.now().isoformat()
        workflow["results"] = results
        
        # 记录执行历史
        self.execution_history.append({
            "workflow_id": workflow_id,
            "workflow_name": workflow["name"],
            "status": workflow["status"],
            "started_at": workflow.get("started_at"),
            "completed_at": workflow["completed_at"],
            "results_count": len(results),
        })
        
        self._notify_listeners(workflow)
        
        return {
            "success": success,
            "workflow_id": workflow_id,
            "results": results
        }
    
    def _execute_task(self, task: Dict, context: Dict) -> Dict:
        """执行单个任务"""
        task_type = task.get("type", "action")
        
        if task_type in self.task_registry:
            return self.task_registry[task_type](task, context)
        else:
            return {
                "task_id": task.get("id"),
                "success": False,
                "error": f"Unknown task type: {task_type}"
            }
    
    def _task_exec(self, task: Dict, context: Dict) -> Dict:
        """执行命令任务"""
        import subprocess
        
        command = task.get("command", "")
        # 替换变量
        for var, value in context.get("variables", {}).items():
            command = command.replace(f"${{{var}}}", str(value))
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                timeout=task.get("timeout", 60)
            )
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": result.returncode == 0,
                "output": result.stdout.decode() if result.stdout else "",
                "error": result.stderr.decode() if result.stderr else "",
                "returncode": result.returncode
            }
        except Exception as e:
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": False,
                "error": str(e)
            }
    
    def _task_condition(self, task: Dict, context: Dict) -> Dict:
        """条件判断任务"""
        condition = task.get("condition", "")
        # 简单的条件评估
        try:
            # 替换变量
            for var, value in context.get("variables", {}).items():
                condition = condition.replace(f"${{{var}}}", f'"{value}"')
            
            result = eval(condition)
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": True,
                "condition_met": result,
                "branch": "true" if result else "false"
            }
        except Exception as e:
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": False,
                "error": str(e)
            }
    
    def _task_wait(self, task: Dict, context: Dict) -> Dict:
        """等待任务"""
        duration = task.get("duration", 5)
        time.sleep(duration)
        return {
            "task_id": task.get("id"),
            "task_name": task.get("name"),
            "success": True,
            "waited": duration
        }
    
    def _task_webhook(self, task: Dict, context: Dict) -> Dict:
        """Webhook调用任务"""
        import urllib.request
        import urllib.parse
        
        url = task.get("url", "")
        method = task.get("method", "POST")
        data = task.get("data", {})
        
        try:
            req_data = json.dumps(data).encode() if data else None
            req = urllib.request.Request(url, data=req_data, method=method)
            req.add_header('Content-Type', 'application/json')
            
            with urllib.request.urlopen(req, timeout=task.get("timeout", 30)) as resp:
                return {
                    "task_id": task.get("id"),
                    "task_name": task.get("name"),
                    "success": resp.status < 400,
                    "status_code": resp.status,
                    "response": resp.read().decode()
                }
        except Exception as e:
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": False,
                "error": str(e)
            }
    
    def _task_notify(self, task: Dict, context: Dict) -> Dict:
        """通知任务"""
        # 发送通知的占位实现
        return {
            "task_id": task.get("id"),
            "task_name": task.get("name"),
            "success": True,
            "notified": True,
            "message": task.get("message", "")
        }
    
    def _task_transform(self, task: Dict, context: Dict) -> Dict:
        """数据转换任务"""
        transform_type = task.get("transform_type", "none")
        input_data = task.get("input", context.get("variables", {}))
        
        try:
            if transform_type == "json_parse":
                result = json.loads(input_data)
            elif transform_type == "json_dump":
                result = json.dumps(input_data)
            elif transform_type == "template":
                template = task.get("template", "")
                result = template
                for k, v in input_data.items():
                    result = result.replace(f"{{{k}}}", str(v))
            else:
                result = input_data
            
            # 更新上下文变量
            var_name = task.get("output_var", "transform_result")
            context["variables"][var_name] = result
            
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": True,
                "result": result
            }
        except Exception as e:
            return {
                "task_id": task.get("id"),
                "task_name": task.get("name"),
                "success": False,
                "error": str(e)
            }
    
    def add_listener(self, callback: Callable):
        """添加工作流状态监听器"""
        self.listeners.append(callback)
    
    def _notify_listeners(self, workflow: Dict):
        """通知监听器"""
        for listener in self.listeners:
            try:
                listener(workflow)
            except:
                pass
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        return [
            {
                "id": w["id"],
                "name": w["name"],
                "status": w["status"],
                "task_count": len(w.get("tasks", []))
            }
            for w in self.workflows.values()
        ]
    
    def get_history(self, limit: int = 10) -> List[Dict]:
        """获取执行历史"""
        return self.execution_history[-limit:]
    
    def save(self, path: str = None):
        """保存工作流配置"""
        if path is None:
            path = os.path.join(self.workspace, "ultron", "workflows.json")
        
        data = {
            "workflows": self.workflows,
            "execution_history": self.execution_history[-100:]  # 保留最近100条
        }
        
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def load(self, path: str = None):
        """加载工作流配置"""
        if path is None:
            path = os.path.join(self.workspace, "ultron", "workflows.json")
        
        if os.path.exists(path):
            with open(path, 'r') as f:
                data = json.load(f)
                self.workflows = data.get("workflows", {})
                self.execution_history = data.get("execution_history", [])


class WorkflowScheduler:
    """工作流调度器"""
    
    def __init__(self, engine: WorkflowEngine):
        self.engine = engine
        self.scheduled_tasks: Dict[str, Dict] = {}
        
    def schedule(self, workflow_id: str, schedule: Dict) -> str:
        """调度工作流"""
        schedule_id = str(uuid.uuid4())[:8]
        self.scheduled_tasks[schedule_id] = {
            "id": schedule_id,
            "workflow_id": workflow_id,
            "schedule": schedule,
            "next_run": self._calculate_next_run(schedule),
            "enabled": True
        }
        return schedule_id
    
    def _calculate_next_run(self, schedule: Dict) -> datetime:
        """计算下次运行时间"""
        now = datetime.now()
        
        if "interval" in schedule:
            # 间隔调度
            unit = schedule["interval"].get("unit", "minutes")
            value = schedule["interval"].get("value", 5)
            
            if unit == "minutes":
                return now + timedelta(minutes=value)
            elif unit == "hours":
                return now + timedelta(hours=value)
            elif unit == "days":
                return now + timedelta(days=value)
                
        elif "cron" in schedule:
            # Cron调度（简化实现）
            # 这里应该使用真正的cron解析器
            return now + timedelta(minutes=5)
        
        return now + timedelta(minutes=5)
    
    def check_and_run(self):
        """检查并运行到期的调度任务"""
        now = datetime.now()
        
        for task in self.scheduled_tasks.values():
            if not task["enabled"]:
                continue
                
            if task["next_run"] <= now:
                # 执行工作流
                self.engine.execute(task["workflow_id"])
                
                # 计算下次运行时间
                task["next_run"] = self._calculate_next_run(task["schedule"])


class WorkflowManager:
    """工作流管理器 - 统一入口"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.engine = WorkflowEngine(workspace)
        self.scheduler = WorkflowScheduler(self.engine)
        
        # 加载保存的工作流
        self.engine.load()
    
    def create_simple_workflow(self, name: str, steps: List[Dict]) -> str:
        """创建简单工作流"""
        workflow_id = self.engine.create_workflow(name)
        
        for i, step in enumerate(steps):
            self.engine.add_task(workflow_id, {
                "name": step.get("name", f"Step {i+1}"),
                "type": step.get("type", "exec"),
                "command": step.get("command"),
                "condition": step.get("condition"),
                "critical": step.get("critical", False)
            })
        
        return workflow_id
    
    def run_workflow(self, name: str, steps: List[Dict], context: Dict = None) -> Dict:
        """快速运行工作流"""
        workflow_id = self.create_simple_workflow(name, steps)
        result = self.engine.execute(workflow_id, context)
        self.engine.save()
        return result
    
    def get_status(self) -> Dict:
        """获取工作流系统状态"""
        return {
            "total_workflows": len(self.engine.workflows),
            "total_executions": len(self.engine.execution_history),
            "scheduled_tasks": len(self.scheduler.scheduled_tasks),
            "recent_executions": self.engine.get_history(5)
        }


def main():
    """测试运行"""
    manager = WorkflowManager()
    
    # 创建示例工作流
    workflow_id = manager.create_simple_workflow(
        "系统健康检查",
        [
            {"name": "检查CPU", "type": "exec", "command": "uptime"},
            {"name": "检查内存", "type": "exec", "command": "free -h"},
            {"name": "检查磁盘", "type": "exec", "command": "df -h"},
        ]
    )
    
    # 执行
    result = manager.engine.execute(workflow_id)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 保存
    manager.engine.save()
    
    # 状态
    print("\n=== 工作流系统状态 ===")
    print(json.dumps(manager.get_status(), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()