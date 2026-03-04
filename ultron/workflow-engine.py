#!/usr/bin/env python3
"""
奥创工作流编排系统 - 第3世：工作流编排
功能：多设备协同工作流、自动化任务链、故障转移机制
"""

import json
import os
import datetime
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
from queue import Queue
import threading


class WorkflowStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class WorkflowStep:
    """工作流步骤"""
    step_id: str
    name: str
    command: str
    target_device: str
    retry_count: int
    timeout: int  # 秒
    status: str
    result: Optional[Dict]
    error: Optional[str]
    started_at: Optional[str]
    completed_at: Optional[str]


@dataclass
class Workflow:
    """工作流定义"""
    workflow_id: str
    name: str
    description: str
    steps: List[WorkflowStep]
    status: str
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    current_step: int
    on_failure: str  # continue, stop, fallback
    metadata: Dict[str, Any]


class WorkflowEngine:
    """工作流引擎"""
    
    def __init__(self, workflow_path: str = None):
        self.workflow_path = workflow_path or "/root/.openclaw/workspace/ultron/logs/workflows.json"
        self.workflows: Dict[str, Workflow] = {}
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: Dict[str, Callable] = {}
        self._load_workflows()
    
    def _load_workflows(self):
        """加载工作流"""
        if os.path.exists(self.workflow_path):
            try:
                with open(self.workflow_path, 'r') as f:
                    data = json.load(f)
                    for w in data.get("workflows", []):
                        steps = [WorkflowStep(**s) for s in w.get("steps", [])]
                        w["steps"] = steps
                        self.workflows[w["workflow_id"]] = Workflow(**w)
            except Exception as e:
                print(f"加载工作流失败: {e}")
    
    def _save_workflows(self):
        """保存工作流"""
        Path(self.workflow_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 转换步骤为字典
        workflows_data = []
        for w in self.workflows.values():
            wf_dict = asdict(w)
            workflows_data.append(wf_dict)
        
        data = {
            "workflows": workflows_data,
            "last_updated": datetime.datetime.now().isoformat()
        }
        with open(self.workflow_path, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def create_workflow(self, name: str, description: str = "",
                       on_failure: str = "stop") -> str:
        """创建工作流"""
        workflow_id = str(uuid.uuid4())[:8]
        
        workflow = Workflow(
            workflow_id=workflow_id,
            name=name,
            description=description,
            steps=[],
            status=WorkflowStatus.PENDING.value,
            created_at=datetime.datetime.now().isoformat(),
            started_at=None,
            completed_at=None,
            current_step=0,
            on_failure=on_failure,
            metadata={}
        )
        
        with self._lock:
            self.workflows[workflow_id] = workflow
            self._save_workflows()
        
        return workflow_id
    
    def add_step(self, workflow_id: str, name: str, command: str,
                target_device: str = "local", retry_count: int = 0,
                timeout: int = 300) -> Optional[str]:
        """添加步骤"""
        if workflow_id not in self.workflows:
            return None
        
        step_id = str(uuid.uuid4())[:8]
        
        step = WorkflowStep(
            step_id=step_id,
            name=name,
            command=command,
            target_device=target_device,
            retry_count=retry_count,
            timeout=timeout,
            status=StepStatus.PENDING.value,
            result=None,
            error=None,
            started_at=None,
            completed_at=None
        )
        
        workflow = self.workflows[workflow_id]
        workflow.steps.append(step)
        self._save_workflows()
        
        return step_id
    
    def start_workflow(self, workflow_id: str) -> bool:
        """启动工作流"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        if workflow.status not in [WorkflowStatus.PENDING.value, 
                                   WorkflowStatus.PAUSED.value]:
            return False
        
        workflow.status = WorkflowStatus.RUNNING.value
        workflow.started_at = datetime.datetime.now().isoformat()
        workflow.current_step = 0
        
        # 重置所有步骤状态
        for step in workflow.steps:
            step.status = StepStatus.PENDING.value
        
        self._save_workflows()
        
        # 异步执行
        thread = threading.Thread(
            target=self._execute_workflow, 
            args=(workflow_id,),
            daemon=True
        )
        thread.start()
        
        return True
    
    def _execute_workflow(self, workflow_id: str):
        """执行工作流"""
        workflow = self.workflows.get(workflow_id)
        if not workflow:
            return
        
        print(f"开始执行工作流: {workflow.name}")
        
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step = i
                self._save_workflows()
                
                # 执行步骤
                success = self._execute_step(workflow, step)
                
                if not success:
                    if workflow.on_failure == "stop":
                        workflow.status = WorkflowStatus.FAILED.value
                        workflow.completed_at = datetime.datetime.now().isoformat()
                        print(f"工作流失败: {workflow.name}")
                        break
                    elif workflow.on_failure == "continue":
                        print(f"步骤失败，继续执行: {step.name}")
                        continue
                    elif workflow.on_failure == "fallback":
                        # 执行回退步骤（如果存在）
                        print(f"执行回退机制: {workflow.name}")
                        break
                else:
                    step.status = StepStatus.COMPLETED.value
                    step.completed_at = datetime.datetime.now().isoformat()
            else:
                # 所有步骤完成
                workflow.status = WorkflowStatus.COMPLETED.value
                workflow.completed_at = datetime.datetime.now().isoformat()
                print(f"工作流完成: {workflow.name}")
                
                # 触发完成回调
                if workflow_id in self._callbacks:
                    self._callbacks[workflow_id](workflow)
        
        except Exception as e:
            workflow.status = WorkflowStatus.FAILED.value
            workflow.error = str(e)
            workflow.completed_at = datetime.datetime.now().isoformat()
            print(f"工作流异常: {workflow.name} - {e}")
        
        finally:
            self._save_workflows()
    
    def _execute_step(self, workflow: Workflow, step: WorkflowStep) -> bool:
        """执行单个步骤"""
        print(f"  执行步骤: {step.name}")
        
        step.status = StepStatus.RUNNING.value
        step.started_at = datetime.datetime.now().isoformat()
        
        for attempt in range(step.retry_count + 1):
            try:
                # 执行命令（简化版：使用subprocess）
                import subprocess
                result = subprocess.run(
                    step.command,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=step.timeout
                )
                
                step.result = {
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr
                }
                
                if result.returncode == 0:
                    step.status = StepStatus.COMPLETED.value
                    step.completed_at = datetime.datetime.now().isoformat()
                    return True
                else:
                    step.error = f"Exit code: {result.returncode}"
            
            except subprocess.TimeoutExpired:
                step.error = "Timeout"
            except Exception as e:
                step.error = str(e)
            
            if attempt < step.retry_count:
                print(f"    重试 {attempt + 1}/{step.retry_count}")
                step.status = StepStatus.RUNNING.value
        
        step.status = StepStatus.FAILED.value
        step.completed_at = datetime.datetime.now().isoformat()
        return False
    
    def pause_workflow(self, workflow_id: str) -> bool:
        """暂停工作流"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        if workflow.status != WorkflowStatus.RUNNING.value:
            return False
        
        workflow.status = WorkflowStatus.PAUSED.value
        self._save_workflows()
        return True
    
    def resume_workflow(self, workflow_id: str) -> bool:
        """恢复工作流"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        if workflow.status != WorkflowStatus.PAUSED.value:
            return False
        
        workflow.status = WorkflowStatus.RUNNING.value
        self._save_workflows()
        
        # 继续执行
        thread = threading.Thread(
            target=self._execute_workflow,
            args=(workflow_id,),
            daemon=True
        )
        thread.start()
        
        return True
    
    def cancel_workflow(self, workflow_id: str) -> bool:
        """取消工作流"""
        if workflow_id not in self.workflows:
            return False
        
        workflow = self.workflows[workflow_id]
        if workflow.status in [WorkflowStatus.COMPLETED.value,
                               WorkflowStatus.FAILED.value,
                               WorkflowStatus.CANCELLED.value]:
            return False
        
        workflow.status = WorkflowStatus.CANCELLED.value
        workflow.completed_at = datetime.datetime.now().isoformat()
        self._save_workflows()
        return True
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """获取工作流"""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self, status: str = None) -> List[Workflow]:
        """列出工作流"""
        workflows = list(self.workflows.values())
        
        if status:
            workflows = [w for w in workflows if w.status == status]
        
        workflows.sort(key=lambda w: w.created_at, reverse=True)
        return workflows
    
    def register_callback(self, workflow_id: str, callback: Callable):
        """注册完成回调"""
        self._callbacks[workflow_id] = callback
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        total = len(self.workflows)
        by_status = {}
        
        for w in self.workflows.values():
            by_status[w.status] = by_status.get(w.status, 0) + 1
        
        return {
            "total_workflows": total,
            "by_status": by_status,
            "last_updated": datetime.datetime.now().isoformat()
        }


# 全局实例
_workflow_engine: Optional[WorkflowEngine] = None

def get_workflow_engine() -> WorkflowEngine:
    global _workflow_engine
    if _workflow_engine is None:
        _workflow_engine = WorkflowEngine()
    return _workflow_engine


if __name__ == "__main__":
    import sys
    
    engine = get_workflow_engine()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "create":
            if len(sys.argv) > 2:
                wf_id = engine.create_workflow(sys.argv[2], " ".join(sys.argv[3:]) if len(sys.argv) > 3 else "")
                print(f"工作流已创建: {wf_id}")
            else:
                print("用法: create <name> [description]")
        
        elif cmd == "add":
            # add <workflow_id> <step_name> <command>
            if len(sys.argv) > 4:
                step_id = engine.add_step(
                    sys.argv[2],
                    sys.argv[3],
                    sys.argv[4]
                )
                print(f"步骤已添加: {step_id}")
            else:
                print("用法: add <workflow_id> <step_name> <command>")
        
        elif cmd == "start":
            if len(sys.argv) > 2:
                if engine.start_workflow(sys.argv[2]):
                    print(f"工作流已启动: {sys.argv[2]}")
                else:
                    print("启动失败")
            else:
                print("用法: start <workflow_id>")
        
        elif cmd == "list":
            workflows = engine.list_workflows()
            print(f"工作流数: {len(workflows)}")
            for w in workflows[:10]:
                print(f"  [{w.status}] {w.name} ({len(w.steps)} steps)")
        
        elif cmd == "status":
            stats = engine.get_statistics()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        elif cmd == "info":
            if len(sys.argv) > 2:
                wf = engine.get_workflow(sys.argv[2])
                if wf:
                    print(f"工作流: {wf.name}")
                    print(f"状态: {wf.status}")
                    print(f"步骤: {len(wf.steps)}")
                    for i, s in enumerate(wf.steps):
                        print(f"  {i+1}. [{s.status}] {s.name}")
                else:
                    print("工作流不存在")
            else:
                print("用法: info <workflow_id>")
        
        else:
            print("用法: workflow.py [create|add|start|list|status|info]")
    else:
        stats = engine.get_statistics()
        print("=" * 40)
        print("  奥创工作流引擎 v1.0")
        print("=" * 40)
        print(f"总工作流: {stats['total_workflows']}")
        print(f"运行中: {stats['by_status'].get('running', 0)}")
        print(f"已完成: {stats['by_status'].get('completed', 0)}")
        print(f"失败: {stats['by_status'].get('failed', 0)}")
        print("=" * 40)