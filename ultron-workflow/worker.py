#!/usr/bin/env python3
"""
工作智能体 Worker Agent
负责执行具体任务的智能体
"""
import json
import sys
import time
from pathlib import Path
from datetime import datetime
from message_bus import MessageBus, AgentRegistry, TaskQueue

WORKFLOW_DIR = Path("/root/.openclaw/workspace/ultron-workflow")

class WorkerAgent:
    """工作智能体"""
    
    def __init__(self, agent_id: str, name: str):
        self.agent_id = agent_id
        self.name = name
        self.bus = MessageBus()
        self.registry = AgentRegistry()
        self.task_queue = TaskQueue()
        
        # 注册自己
        self.registry.register(
            agent_id=agent_id,
            name=name,
            agent_type="executor",
            capabilities=["执行任务", "文件操作", "系统命令"]
        )
        
    def run(self):
        """运行主循环"""
        print(f"[{self.name}] 启动工作智能体")
        
        while True:
            # 检查是否有分配给自己的任务
            assigned = self.task_queue.get_assigned()
            my_tasks = [t for t in assigned if t.get("assigned_to") == self.agent_id]
            
            if my_tasks:
                for task in my_tasks:
                    self.execute_task(task)
            
            # 检查收件箱
            messages = self.bus.receive(self.agent_id)
            for msg in messages:
                self.handle_message(msg)
            
            # 发送心跳
            self.send_heartbeat()
            
            time.sleep(5)
    
    def execute_task(self, task: Dict):
        """执行任务"""
        task_id = task.get("task_id")
        print(f"[{self.name}] 执行任务: {task_id}")
        
        # 模拟任务执行
        result = {
            "status": "success",
            "output": f"任务 {task_id} 已完成",
            "executed_by": self.agent_id,
            "executed_at": datetime.now().isoformat()
        }
        
        self.task_queue.complete(task_id, result)
        print(f"[{self.name}] 任务完成: {task_id}")
    
    def handle_message(self, message: Dict):
        """处理消息"""
        msg_type = message.get("type")
        payload = message.get("payload", {})
        
        print(f"[{self.name}] 收到消息: {msg_type}")
        
        if msg_type == "task":
            # 直接创建任务并执行
            task = {
                "title": payload.get("title", "未命名任务"),
                "description": payload.get("description", ""),
                "priority": payload.get("priority", "normal")
            }
            task_id = self.task_queue.submit(task)
            self.task_queue.assign(task_id, self.agent_id)
            self.execute_task({"task_id": task_id})
            
        elif msg_type == "command":
            # 执行命令
            command = payload.get("command")
            if command:
                result = {"output": f"执行: {command}"}
                self.task_queue.complete(payload.get("task_id", "unknown"), result)
    
    def send_heartbeat(self):
        """发送心跳"""
        msg = self.bus.create_message(
            sender=self.agent_id,
            receiver="ultron",
            msg_type="heartbeat",
            payload={"status": "alive", "load": "low"}
        )
        self.bus.send(msg)


def main():
    if len(sys.argv) < 2:
        print("用法: python worker.py <agent_id> [name]")
        sys.exit(1)
    
    agent_id = sys.argv[1]
    name = sys.argv[2] if len(sys.argv) > 2 else f"Worker-{agent_id}"
    
    worker = WorkerAgent(agent_id, name)
    worker.run()


if __name__ == "__main__":
    main()