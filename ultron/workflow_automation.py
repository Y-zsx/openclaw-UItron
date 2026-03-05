#!/usr/bin/env python3
"""自动化工作流引擎"""
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

# 添加agents目录
sys.path.insert(0, str(Path(__file__).parent / "agents"))

from enhanced_message_bus import EnhancedMessageBus
from monitor_agent import MonitorAgent
from orchestrator_agent import OrchestratorAgent
from executor_agent import ExecutorAgent

class WorkflowEngine:
    def __init__(self):
        self.bus = EnhancedMessageBus()
        self.agents = {
            "monitor": MonitorAgent(),
            "orchestrator": OrchestratorAgent(),
            "executor": ExecutorAgent()
        }
        self.running = False
    
    def start(self):
        """启动工作流引擎"""
        self.running = True
        print(f"[Workflow] 引擎启动 at {datetime.now().isoformat()}")
        
        # 注册消息回调
        self.bus.on_message("workflow", self.handle_message)
        
        # 启动工作流循环
        self.run_workflow_cycle()
    
    def handle_message(self, message):
        """处理收到的消息"""
        print(f"[Workflow] 收到消息: {message}")
        
        if message.get("type") == "task":
            self.execute_task(message)
        elif message.get("type") == "event":
            self.handle_event(message)
    
    def execute_task(self, task):
        """执行任务"""
        print(f"[Workflow] 执行任务: {task['message']}")
        # 转发给executor
        result = self.bus.complete_task(task["id"], "executed")
        print(f"[Workflow] 任务完成: {task['id']}")
    
    def handle_event(self, event):
        """处理事件"""
        print(f"[Workflow] 处理事件: {event['message']}")
    
    def run_workflow_cycle(self):
        """运行一个工作流周期"""
        # 1. 监控系统状态
        status = self.agents["monitor"].check_system()
        print(f"[Workflow] 系统状态: {status}")
        
        # 2. 如果有告警，发布任务
        alerts = self.agents["monitor"].should_alert(status)
        if alerts:
            self.bus.publish(
                "workflow",
                "executor",
                f"告警处理: {', '.join(alerts)}",
                "task",
                {"status": status, "alerts": alerts}
            )
        
        # 3. 广播工作流状态
        self.bus.publish(
            "workflow",
            "all",
            "工作流周期完成",
            "event",
            {"status": "completed", "timestamp": datetime.now().isoformat()}
        )
        
        print(f"[Workflow] 周期完成")

if __name__ == "__main__":
    engine = WorkflowEngine()
    engine.run_workflow_cycle()
