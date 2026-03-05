#!/usr/bin/env python3
"""
奥创转世系统 v4.0 主入口
=========================
统一调度 规划层、记忆层、执行层

设计原则:
- 模块化: 规划/记忆/执行分离
- 无污染: 独立工作目录
- 清晰结构: 分层设计
"""

import sys
import json
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent / "planner"))

from planner.task_graph import TaskGraph, TASK_TEMPLATES
from planner.scheduler import Scheduler
from memory.incarnation import IncarnationMemory
from executor.state_machine import StateMachine, TaskState

import yaml


class UltronLifeV4:
    """奥创转世系统 v4.0"""
    
    def __init__(self, workdir: str = None):
        if workdir is None:
            workdir = "/root/.openclaw/workspace/ultron-workflow-v4"
        
        self.workdir = Path(workdir)
        self.config = self._load_config()
        
        # 初始化各层
        self.graph = None
        self.scheduler = None
        self.memory = None
        self.state_machine = None
        
        self._init_components()
    
    def _load_config(self) -> dict:
        config_file = self.workdir / "config" / "settings.yaml"
        with open(config_file) as f:
            return yaml.safe_load(f)
    
    def _init_components(self):
        """初始化各层组件"""
        # 规划层 - 任务图
        graph_file = self.workdir / "config" / "task_graph.json"
        self.graph = TaskGraph(str(graph_file))
        
        # 规划层 - 调度器 (传入graph)
        self.scheduler = Scheduler(
            str(self.workdir / "config" / "settings.yaml"),
            task_graph=self.graph
        )
        
        # 记忆层
        self.memory = IncarnationMemory(str(self.workdir))
        
        # 执行层 - 状态机
        state_file = self.workdir / "executor" / "state.json"
        self.state_machine = StateMachine(
            str(state_file),
            max_retries=self.config["tasks"]["max_retries"]
        )
    
    def setup_default_tasks(self):
        """设置默认任务链"""
        for task_id, task_info in TASK_TEMPLATES.items():
            # 检查是否已存在
            if self.graph.nodes.get(task_id):
                continue
            self.graph.add_task(task_id, task_info["name"], task_info["dependencies"])
        print("[Setup] 默认任务链已创建")
    
    def wake_up(self) -> dict:
        """唤醒 - 执行一世的任务"""
        result = {
            "generation": self.memory.inherit_memory()["generation"],
            "tasks_executed": [],
            "status": "ok"
        }
        
        # 获取可执行任务
        tasks = self.scheduler.get_scheduled_tasks()
        
        if not tasks:
            print("[Wake] 无待执行任务")
            return result
        
        for task in tasks:
            print(f"[Wake] 执行任务: {task.name}")
            
            # 状态机: 创建任务
            self.state_machine.create_task(task.id, "auto", {"name": task.name})
            
            # 状态机: 运行中
            self.state_machine.transition(task.id, TaskState.RUNNING)
            
            # 执行任务 (这里调用实际执行逻辑)
            success, output = self._execute_task(task)
            
            # 状态机: 完成/失败
            if success:
                self.state_machine.transition(task.id, TaskState.DONE, result=output)
                # 记忆: 记录成功
                self.memory.record_life(
                    self.memory.inherit_memory()["generation"],
                    task.name, output, "success"
                )
            else:
                if self.state_machine.can_retry(task.id):
                    self.state_machine.transition(task.id, TaskState.WAITING_RETRY, error=output)
                else:
                    self.state_machine.transition(task.id, TaskState.FAILED, error=output)
                    # 记忆: 记录失败教训
                    self.memory.add_lesson(f"任务 {task.name} 失败: {output}")
            
            result["tasks_executed"].append({
                "task": task.name,
                "status": "success" if success else "failed"
            })
            
            # 任务图: 标记完成
            self.graph.complete_task(task.id, result=output, success=success)
        
        # 推进到下一世
        self.memory.advance_generation()
        
        return result
    
    def _execute_task(self, task) -> tuple[bool, str]:
        """执行单个任务 - 子类重写"""
        # 这里应该调用实际的任务执行逻辑
        # 暂时返回模拟结果
        return True, f"任务 {task.name} 执行完成"
    
    def get_status(self) -> dict:
        """获取系统状态"""
        return {
            "generation": self.memory.get_summary()["generation"],
            "task_graph": self.graph.get_status(),
            "memory": self.memory.get_summary(),
            "executor": {
                "pending": self.state_machine.get_pending_count(),
                "running": len(self.state_machine.get_tasks_by_status(TaskState.RUNNING))
            }
        }
    
    def run_once(self):
        """运行一次"""
        print("=" * 50)
        print("奥创转世系统 v4.0 启动")
        print("=" * 50)
        
        # 首次运行设置默认任务
        if not self.graph.nodes:
            self.setup_default_tasks()
        
        # 唤醒执行
        result = self.wake_up()
        
        # 输出状态
        print("\n[Status]", json.dumps(self.get_status(), indent=2, ensure_ascii=False))
        
        return result


def main():
    """入口"""
    ultron = UltronLifeV4()
    ultron.run_once()


if __name__ == "__main__":
    main()