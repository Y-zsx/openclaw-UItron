#!/usr/bin/env python3
"""多智能体消息总线"""
import json
import os
from datetime import datetime
from pathlib import Path

QUEUE_FILE = Path(__file__).parent / "task_queue.json"

class MessageBus:
    def __init__(self):
        self.queue_file = QUEUE_FILE
        self._ensure_queue()
    
    def _ensure_queue(self):
        if not self.queue_file.exists():
            self._save({"tasks": [], "messages": []})
    
    def _load(self):
        with open(self.queue_file) as f:
            return json.load(f)
    
    def _save(self, data):
        with open(self.queue_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def publish(self, sender: str, recipient: str, message: str, task_type: str = "message"):
        """发布消息/任务"""
        data = self._load()
        entry = {
            "id": f"{len(data['tasks']) + len(data['messages']) + 1}",
            "sender": sender,
            "recipient": recipient,
            "message": message,
            "type": task_type,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        if task_type == "task":
            data["tasks"].append(entry)
        else:
            data["messages"].append(entry)
        
        self._save(data)
        return entry["id"]
    
    def subscribe(self, agent: str, message_type: str = "all"):
        """订阅消息"""
        data = self._load()
        return [m for m in data["messages"] 
                if message_type == "all" or m.get("type") == message_type]
    
    def get_tasks(self, agent: str = None):
        """获取任务列表"""
        data = self._load()
        if agent:
            return [t for t in data["tasks"] if t.get("recipient") == agent]
        return data["tasks"]
    
    def complete_task(self, task_id: str, result: str):
        """完成任务"""
        data = self._load()
        for task in data["tasks"]:
            if task["id"] == task_id:
                task["status"] = "completed"
                task["result"] = result
                task["completed_at"] = datetime.now().isoformat()
                break
        self._save(data)

if __name__ == "__main__":
    bus = MessageBus()
    # 测试
    bus.publish("monitor", "executor", "磁盘使用率过高", "task")
    bus.publish("system", "messenger", "系统正常", "message")
    print("消息总线测试通过")
    print(f"任务: {bus.get_tasks()}")