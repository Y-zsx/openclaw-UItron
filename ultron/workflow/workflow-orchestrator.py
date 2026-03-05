#!/usr/bin/env python3
"""
奥创工作流编排系统 - 智能运维编排核心
夙愿十：智能运维编排系统 - 第1世：工作流自动化

功能：
- 任务模板引擎：定义可复用的任务模板
- 触发器系统：监听各种触发条件
- 执行链管理：管理和执行工作流链
"""

import json
import os
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import uuid
import re

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WorkflowOrchestrator")

# 存储路径
WORKFLOW_DIR = Path("/root/.openclaw/workspace/ultron/data/workflows")
TEMPLATE_DIR = Path("/root/.openclaw/workspace/ultron/data/templates")
TRIGGER_DIR = Path("/root/.openclaw/workspace/ultron/data/triggers")

# 确保目录存在
for d in [WORKFLOW_DIR, TEMPLATE_DIR, TRIGGER_DIR]:
    d.mkdir(parents=True, exist_ok=True)


class TriggerType(Enum):
    """触发器类型"""
    CRON = "cron"           # 定时触发
    EVENT = "event"         # 事件触发
    MANUAL = "manual"       # 手动触发
    WEBHOOK = "webhook"     # Webhook触发
    CONDITION = "condition" # 条件触发


class WorkflowStatus(Enum):
    """工作流状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class TaskTemplate:
    """任务模板"""
    name: str
    command: str
    description: str = ""
    timeout: int = 300
    retry: int = 0
    env: Dict[str, str] = field(default_factory=dict)
    variables: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "command": self.command,
            "description": self.description,
            "timeout": self.timeout,
            "retry": self.retry,
            "env": self.env,
            "variables": self.variables
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TaskTemplate':
        return cls(
            name=data.get("name", ""),
            command=data.get("command", ""),
            description=data.get("description", ""),
            timeout=data.get("timeout", 300),
            retry=data.get("retry", 0),
            env=data.get("env", {}),
            variables=data.get("variables", {})
        )


@dataclass
class WorkflowTask:
    """工作流任务"""
    id: str
    template: TaskTemplate
    params: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Any = None
    error: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    
    def resolve_command(self) -> str:
        """解析命令中的变量"""
        cmd = self.template.command
        # 合并模板变量和运行时参数
        vars_dict = {**self.template.variables, **self.params}
        for key, value in vars_dict.items():
            cmd = cmd.replace(f"${{{key}}}", str(value))
            cmd = cmd.replace(f"${{env.{key}}}", os.environ.get(key, ""))
        return cmd


@dataclass
class Trigger:
    """触发器"""
    id: str
    type: TriggerType
    config: Dict[str, Any]
    enabled: bool = True
    last_triggered: Optional[datetime] = None
    next_trigger: Optional[datetime] = None
    
    def should_fire(self) -> bool:
        """检查是否应该触发"""
        if not self.enabled:
            return False
        
        if self.type == TriggerType.CRON:
            # 简单的cron检查
            if self.next_trigger and datetime.now() >= self.next_trigger:
                return True
        
        return False


@dataclass
class Workflow:
    """工作流定义"""
    id: str
    name: str
    description: str = ""
    version: str = "1.0"
    tasks: List[WorkflowTask] = field(default_factory=list)
    triggers: List[Trigger] = field(default_factory=list)
    status: WorkflowStatus = WorkflowStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    execution_history: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "tasks": [
                {
                    "id": t.id,
                    "template": t.template.to_dict(),
                    "params": t.params,
                    "dependencies": t.dependencies,
                    "status": t.status
                }
                for t in self.tasks
            ],
            "triggers": [
                {
                    "id": tr.id,
                    "type": tr.type.value,
                    "config": tr.config,
                    "enabled": tr.enabled
                }
                for tr in self.triggers
            ],
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


class TaskTemplateEngine:
    """任务模板引擎"""
    
    def __init__(self, template_dir: Path = TEMPLATE_DIR):
        self.template_dir = template_dir
        self.templates: Dict[str, TaskTemplate] = {}
        self._load_templates()
    
    def _load_templates(self):
        """加载模板"""
        for f in self.template_dir.glob("*.json"):
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                    template = TaskTemplate.from_dict(data)
                    self.templates[template.name] = template
                    logger.info(f"加载模板: {template.name}")
            except Exception as e:
                logger.error(f"加载模板失败 {f}: {e}")
    
    def save_template(self, template: TaskTemplate) -> bool:
        """保存模板"""
        try:
            path = self.template_dir / f"{template.name}.json"
            with open(path, 'w') as fp:
                json.dump(template.to_dict(), fp, indent=2)
            self.templates[template.name] = template
            logger.info(f"保存模板: {template.name}")
            return True
        except Exception as e:
            logger.error(f"保存模板失败: {e}")
            return False
    
    def get_template(self, name: str) -> Optional[TaskTemplate]:
        """获取模板"""
        return self.templates.get(name)
    
    def list_templates(self) -> List[str]:
        """列出所有模板"""
        return list(self.templates.keys())
    
    def create_task(self, template_name: str, params: Dict = None) -> Optional[WorkflowTask]:
        """从模板创建任务"""
        template = self.get_template(template_name)
        if not template:
            logger.error(f"模板不存在: {template_name}")
            return None
        
        task = WorkflowTask(
            id=str(uuid.uuid4()),
            template=template,
            params=params or {}
        )
        return task
    
    def delete_template(self, name: str) -> bool:
        """删除模板"""
        try:
            path = self.template_dir / f"{name}.json"
            if path.exists():
                path.unlink()
            if name in self.templates:
                del self.templates[name]
            logger.info(f"删除模板: {name}")
            return True
        except Exception as e:
            logger.error(f"删除模板失败: {e}")
            return False


class TriggerSystem:
    """触发器系统"""
    
    def __init__(self, trigger_dir: Path = TRIGGER_DIR):
        self.trigger_dir = trigger_dir
        self.triggers: Dict[str, Trigger] = {}
        self.listeners: Dict[str, List[Callable]] = {}
        self._load_triggers()
    
    def _load_triggers(self):
        """加载触发器"""
        for f in self.trigger_dir.glob("*.json"):
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                    trigger = Trigger(
                        id=data["id"],
                        type=TriggerType(data["type"]),
                        config=data["config"],
                        enabled=data.get("enabled", True)
                    )
                    self.triggers[trigger.id] = trigger
                    logger.info(f"加载触发器: {trigger.id}")
            except Exception as e:
                logger.error(f"加载触发器失败 {f}: {e}")
    
    def save_trigger(self, trigger: Trigger) -> bool:
        """保存触发器"""
        try:
            path = self.trigger_dir / f"{trigger.id}.json"
            with open(path, 'w') as fp:
                json.dump({
                    "id": trigger.id,
                    "type": trigger.type.value,
                    "config": trigger.config,
                    "enabled": trigger.enabled
                }, fp, indent=2)
            self.triggers[trigger.id] = trigger
            logger.info(f"保存触发器: {trigger.id}")
            return True
        except Exception as e:
            logger.error(f"保存触发器失败: {e}")
            return False
    
    def create_trigger(self, trigger_type: TriggerType, config: Dict) -> Trigger:
        """创建触发器"""
        trigger = Trigger(
            id=str(uuid.uuid4()),
            type=trigger_type,
            config=config
        )
        
        # 计算下次触发时间
        if trigger_type == TriggerType.CRON:
            self._calculate_next_trigger(trigger)
        
        return trigger
    
    def _calculate_next_trigger(self, trigger: Trigger):
        """计算下次触发时间"""
        config = trigger.config
        interval = config.get("interval_minutes", 60)
        trigger.next_trigger = datetime.now() + timedelta(minutes=interval)
    
    def check_triggers(self) -> List[Trigger]:
        """检查所有触发器"""
        fired = []
        for trigger in self.triggers.values():
            if trigger.should_fire():
                fired.append(trigger)
                trigger.last_triggered = datetime.now()
                self._calculate_next_trigger(trigger)
                self.save_trigger(trigger)
        return fired
    
    def register_listener(self, event_type: str, callback: Callable):
        """注册事件监听器"""
        if event_type not in self.listeners:
            self.listeners[event_type] = []
        self.listeners[event_type].append(callback)
    
    def emit_event(self, event_type: str, data: Any = None):
        """触发事件"""
        if event_type in self.listeners:
            for callback in self.listeners[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    logger.error(f"事件回调失败: {e}")


class ExecutionChain:
    """执行链管理"""
    
    def __init__(self):
        self.executions: Dict[str, Dict] = {}
    
    def create_execution(self, workflow_id: str, tasks: List[WorkflowTask]) -> str:
        """创建执行实例"""
        exec_id = str(uuid.uuid4())
        self.executions[exec_id] = {
            "workflow_id": workflow_id,
            "tasks": {t.id: t for t in tasks},
            "completed": [],
            "failed": [],
            "running": None,
            "start_time": datetime.now(),
            "status": "pending"
        }
        return exec_id
    
    def get_ready_tasks(self, exec_id: str) -> Optional[List[WorkflowTask]]:
        """获取就绪的任务（依赖已满足）"""
        if exec_id not in self.executions:
            return None
        
        execution = self.executions[exec_id]
        tasks = execution["tasks"]
        completed = set(execution["completed"])
        
        ready = []
        for task_id, task in tasks.items():
            if task_id in completed or task_id in execution["failed"]:
                continue
            
            # 检查依赖是否满足
            deps_satisfied = all(dep in completed for dep in task.dependencies)
            if deps_satisfied:
                ready.append(task)
        
        return ready
    
    def mark_completed(self, exec_id: str, task_id: str, result: Any = None):
        """标记任务完成"""
        if exec_id in self.executions:
            task = self.executions[exec_id]["tasks"].get(task_id)
            if task:
                task.status = "completed"
                task.result = result
                task.end_time = datetime.now()
            self.executions[exec_id]["completed"].append(task_id)
    
    def mark_failed(self, exec_id: str, task_id: str, error: str):
        """标记任务失败"""
        if exec_id in self.executions:
            task = self.executions[exec_id]["tasks"].get(task_id)
            if task:
                task.status = "failed"
                task.error = error
                task.end_time = datetime.now()
            self.executions[exec_id]["failed"].append(task_id)
            self.executions[exec_id]["status"] = "failed"
    
    def is_complete(self, exec_id: str) -> bool:
        """检查执行是否完成"""
        if exec_id not in self.executions:
            return False
        
        execution = self.executions[exec_id]
        total = len(execution["tasks"])
        completed = len(execution["completed"])
        failed = len(execution["failed"])
        
        return completed + failed == total
    
    def get_status(self, exec_id: str) -> Optional[Dict]:
        """获取执行状态"""
        if exec_id not in self.executions:
            return None
        
        execution = self.executions[exec_id]
        return {
            "id": exec_id,
            "workflow_id": execution["workflow_id"],
            "status": execution["status"],
            "total": len(execution["tasks"]),
            "completed": len(execution["completed"]),
            "failed": len(execution["failed"]),
            "running": execution["running"]
        }


class WorkflowOrchestrator:
    """工作流编排主引擎"""
    
    def __init__(self):
        self.template_engine = TaskTemplateEngine()
        self.trigger_system = TriggerSystem()
        self.execution_chain = ExecutionChain()
        self.workflows: Dict[str, Workflow] = {}
        self.active_executions: Dict[str, str] = {}  # workflow_id -> exec_id
        self._load_workflows()
    
    def _load_workflows(self):
        """加载工作流"""
        for f in WORKFLOW_DIR.glob("*.json"):
            try:
                with open(f, 'r') as fp:
                    data = json.load(fp)
                    wf = self._deserialize_workflow(data)
                    self.workflows[wf.id] = wf
                    logger.info(f"加载工作流: {wf.name}")
            except Exception as e:
                logger.error(f"加载工作流失败 {f}: {e}")
    
    def _deserialize_workflow(self, data: Dict) -> Workflow:
        """反序列化工作流"""
        tasks = []
        for t in data.get("tasks", []):
            template = TaskTemplate.from_dict(t["template"])
            task = WorkflowTask(
                id=t["id"],
                template=template,
                params=t.get("params", {}),
                dependencies=t.get("dependencies", [])
            )
            tasks.append(task)
        
        triggers = []
        for tr in data.get("triggers", []):
            trigger = Trigger(
                id=tr["id"],
                type=TriggerType(tr["type"]),
                config=tr["config"],
                enabled=tr.get("enabled", True)
            )
            triggers.append(trigger)
        
        return Workflow(
            id=data["id"],
            name=data["name"],
            description=data.get("description", ""),
            version=data.get("version", "1.0"),
            tasks=tasks,
            triggers=triggers,
            status=WorkflowStatus(data.get("status", "pending"))
        )
    
    def save_workflow(self, workflow: Workflow) -> bool:
        """保存工作流"""
        try:
            path = WORKFLOW_DIR / f"{workflow.id}.json"
            with open(path, 'w') as fp:
                json.dump(workflow.to_dict(), fp, indent=2, ensure_ascii=False)
            self.workflows[workflow.id] = workflow
            logger.info(f"保存工作流: {workflow.name}")
            return True
        except Exception as e:
            logger.error(f"保存工作流失败: {e}")
            return False
    
    def create_workflow(self, name: str, description: str = "") -> Workflow:
        """创建工作流"""
        workflow = Workflow(
            id=str(uuid.uuid4()),
            name=name,
            description=description
        )
        self.save_workflow(workflow)
        return workflow
    
    def add_task(self, workflow_id: str, template_name: str, 
                 params: Dict = None, dependencies: List[str] = None) -> Optional[WorkflowTask]:
        """添加任务到工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.error(f"工作流不存在: {workflow_id}")
            return None
        
        task = self.template_engine.create_task(template_name, params)
        if not task:
            return None
        
        task.dependencies = dependencies or []
        workflow.tasks.append(task)
        workflow.updated_at = datetime.now()
        self.save_workflow(workflow)
        return task
    
    def add_trigger(self, workflow_id: str, trigger_type: TriggerType, 
                    config: Dict) -> Optional[Trigger]:
        """添加触发器"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return None
        
        trigger = self.trigger_system.create_trigger(trigger_type, config)
        workflow.triggers.append(trigger)
        workflow.updated_at = datetime.now()
        self.save_workflow(workflow)
        self.trigger_system.save_trigger(trigger)
        return trigger
    
    def execute_workflow(self, workflow_id: str) -> Optional[str]:
        """执行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            logger.error(f"工作流不存在: {workflow_id}")
            return None
        
        # 创建执行实例
        exec_id = self.execution_chain.create_execution(workflow_id, workflow.tasks.copy())
        self.active_executions[workflow_id] = exec_id
        
        workflow.status = WorkflowStatus.RUNNING
        self.save_workflow(workflow)
        
        logger.info(f"开始执行工作流: {workflow.name} (exec_id: {exec_id})")
        return exec_id
    
    def process_execution(self, exec_id: str) -> Dict:
        """处理执行（单步）"""
        status = self.execution_chain.get_status(exec_id)
        if not status:
            return {"error": "执行不存在"}
        
        if status["status"] == "failed":
            return status
        
        # 获取就绪任务
        ready_tasks = self.execution_chain.get_ready_tasks(exec_id)
        
        for task in ready_tasks:
            logger.info(f"执行任务: {task.id} - {task.template.name}")
            
            # 解析命令
            cmd = task.resolve_command()
            task.status = "running"
            task.start_time = datetime.now()
            
            # 执行命令（模拟，实际会调用exec）
            try:
                import subprocess
                result = subprocess.run(
                    cmd, shell=True, capture_output=True, 
                    timeout=task.template.timeout, text=True
                )
                
                if result.returncode == 0:
                    self.execution_chain.mark_completed(exec_id, task.id, result.stdout)
                    logger.info(f"任务完成: {task.id}")
                else:
                    self.execution_chain.mark_failed(exec_id, task.id, result.stderr)
                    logger.error(f"任务失败: {task.id} - {result.stderr}")
                    
            except subprocess.TimeoutExpired:
                self.execution_chain.mark_failed(exec_id, task.id, "超时")
                logger.error(f"任务超时: {task.id}")
            except Exception as e:
                self.execution_chain.mark_failed(exec_id, task.id, str(e))
                logger.error(f"任务异常: {task.id} - {e}")
        
        # 检查完成状态
        if self.execution_chain.is_complete(exec_id):
            final_status = self.execution_chain.get_status(exec_id)
            workflow_id = final_status["workflow_id"]
            workflow = self.workflows.get(workflow_id)
            if workflow:
                workflow.status = WorkflowStatus.COMPLETED if final_status["failed"] == 0 else WorkflowStatus.FAILED
                self.save_workflow(workflow)
            
            if workflow_id in self.active_executions:
                del self.active_executions[workflow_id]
        
        return self.execution_chain.get_status(exec_id)
    
    def list_workflows(self) -> List[Dict]:
        """列出所有工作流"""
        return [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "status": wf.status.value,
                "task_count": len(wf.tasks),
                "triggers": len(wf.triggers)
            }
            for wf in self.workflows.values()
        ]
    
    def get_workflow(self, workflow_id: str) -> Optional[Dict]:
        """获取工作流详情"""
        wf = self.workflows.get(workflow_id)
        if wf:
            return wf.to_dict()
        return None
    
    def delete_workflow(self, workflow_id: str) -> bool:
        """删除工作流"""
        try:
            path = WORKFLOW_DIR / f"{workflow_id}.json"
            if path.exists():
                path.unlink()
            if workflow_id in self.workflows:
                del self.workflows[workflow_id]
            logger.info(f"删除工作流: {workflow_id}")
            return True
        except Exception as e:
            logger.error(f"删除工作流失败: {e}")
            return False
    
    def run(self):
        """运行编排器（检查触发器并执行）"""
        # 检查触发器
        fired_triggers = self.trigger_system.check_triggers()
        
        for trigger in fired_triggers:
            # 查找关联的工作流
            for wf in self.workflows.values():
                for tr in wf.triggers:
                    if tr.id == trigger.id:
                        logger.info(f"触发工作流: {wf.name}")
                        self.execute_workflow(wf.id)
        
        # 处理活动执行
        for workflow_id, exec_id in list(self.active_executions.items()):
            self.process_execution(exec_id)


# 默认模板
DEFAULT_TEMPLATES = [
    {
        "name": "shell-command",
        "command": "$COMMAND",
        "description": "通用Shell命令",
        "timeout": 300,
        "retry": 0,
        "variables": {"COMMAND": ""}
    },
    {
        "name": "system-monitor",
        "command": "python3 /root/.openclaw/workspace/ultron/intelligent-monitor.py",
        "description": "系统监控",
        "timeout": 60,
        "retry": 1
    },
    {
        "name": "git-commit",
        "command": "cd $WORKDIR && git add -A && git commit -m \"$MESSAGE\"",
        "description": "Git提交",
        "timeout": 30,
        "retry": 0,
        "variables": {"WORKDIR": "/root/.openclaw/workspace", "MESSAGE": ""}
    },
    {
        "name": "backup-data",
        "command": "tar -czf /root/.openclaw/workspace/ultron/data/backup_$TIMESTAMP.tar.gz /root/.openclaw/workspace/ultron/data/",
        "description": "数据备份",
        "timeout": 300,
        "retry": 0,
        "variables": {"TIMESTAMP": ""}
    },
    {
        "name": "health-check",
        "command": "curl -s http://localhost:18789/health || echo 'unhealthy'",
        "description": "健康检查",
        "timeout": 10,
        "retry": 2
    }
]

def init_templates():
    """初始化默认模板"""
    engine = TaskTemplateEngine()
    for tmpl_data in DEFAULT_TEMPLATES:
        if tmpl_data["name"] not in engine.templates:
            template = TaskTemplate.from_dict(tmpl_data)
            engine.save_template(template)
    print(f"已初始化 {len(DEFAULT_TEMPLATES)} 个默认模板")


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="奥创工作流编排系统")
    parser.add_argument("--init", action="store_true", help="初始化默认模板")
    parser.add_argument("--list", action="store_true", help="列出工作流")
    parser.add_argument("--run", metavar="ID", help="执行工作流")
    parser.add_argument("--status", metavar="ID", help="查看执行状态")
    parser.add_argument("--create", metavar="NAME", help="创建工作流")
    parser.add_argument("--add-task", nargs=3, metavar=("WF", "TEMPLATE", "PARAMS"), help="添加任务")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式")
    
    args = parser.parse_args()
    
    orchestrator = WorkflowOrchestrator()
    
    if args.init:
        init_templates()
        return
    
    if args.list:
        for wf in orchestrator.list_workflows():
            print(f"{wf['id'][:8]} - {wf['name']} ({wf['status']}) - {wf['task_count']} tasks")
        return
    
    if args.create:
        wf = orchestrator.create_workflow(args.create)
        print(f"创建工作流: {wf.id}")
        return
    
    if args.run:
        exec_id = orchestrator.execute_workflow(args.run)
        if exec_id:
            print(f"执行ID: {exec_id}")
            # 处理执行
            status = orchestrator.process_execution(exec_id)
            print(f"状态: {status}")
        return
    
    if args.status:
        status = orchestrator.execution_chain.get_status(args.status)
        print(json.dumps(status, indent=2, default=str))
        return
    
    if args.daemon:
        print("启动工作流编排守护进程...")
        while True:
            orchestrator.run()
            time.sleep(30)
    
    # 默认显示帮助
    parser.print_help()


if __name__ == "__main__":
    main()