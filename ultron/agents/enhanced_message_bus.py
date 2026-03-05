#!/usr/bin/env python3
"""增强版消息总线 - 支持实时通信"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Callable, Optional
import threading

QUEUE_FILE = Path(__file__).parent / "task_queue.json"

class EnhancedMessageBus:
    def __init__(self):
        self.queue_file = QUEUE_FILE
        self._ensure_queue()
        self.callbacks: Dict[str, List[Callable]] = {}
        self.lock = threading.Lock()
    
    def _ensure_queue(self):
        if not self.queue_file.exists():
            self._save({"tasks": [], "messages": [], "events": []})
    
    def _load(self):
        with open(self.queue_file) as f:
            data = json.load(f)
            if "events" not in data:
                data["events"] = []
            return data
    
    def _save(self, data):
        if "events" not in data:
            data["events"] = []
        with open(self.queue_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def publish(self, sender: str, recipient: str, message: str, task_type: str = "message", payload: dict = None):
        """发布消息/任务/事件"""
        with self.lock:
            data = self._load()
            entry = {
                "id": f"{sender}->{recipient}:{len(data['tasks']) + len(data['messages'])}",
                "sender": sender,
                "recipient": recipient,
                "message": message,
                "type": task_type,
                "payload": payload or {},
                "timestamp": datetime.now().isoformat(),
                "status": "pending"
            }
            
            if task_type == "task":
                data["tasks"].append(entry)
            elif task_type == "event":
                data["events"].append(entry)
            else:
                data["messages"].append(entry)
            
            self._save(data)
            
            # 触发回调
            self._trigger_callback(recipient, entry)
            
            return entry["id"]
    
    def subscribe(self, agent: str, message_type: str = "all") -> List[dict]:
        """订阅消息"""
        data = self._load()
        return [m for m in data["messages"] 
                if message_type == "all" or m.get("type") == message_type]
    
    def on_message(self, agent: str, callback: Callable):
        """注册消息回调"""
        if agent not in self.callbacks:
            self.callbacks[agent] = []
        self.callbacks[agent].append(callback)
    
    def _trigger_callback(self, recipient: str, message: dict):
        """触发回调"""
        if recipient in self.callbacks:
            for cb in self.callbacks[recipient]:
                try:
                    cb(message)
                except Exception as e:
                    print(f"回调错误: {e}")
    
    def get_tasks(self, agent: str = None) -> List[dict]:
        """获取任务列表"""
        data = self._load()
        if agent:
            return [t for t in data["tasks"] if t.get("recipient") == agent]
        return data["tasks"]
    
    def get_events(self, agent: str = None) -> List[dict]:
        """获取事件列表"""
        data = self._load()
        if agent:
            return [e for e in data["events"] if e.get("recipient") == agent]
        return data["events"]
    
    def complete_task(self, task_id: str, result: str):
        """完成任务"""
        with self.lock:
            data = self._load()
            for task in data["tasks"]:
                if task["id"] == task_id:
                    task["status"] = "completed"
                    task["result"] = result
                    task["completed_at"] = datetime.now().isoformat()
                    break
            self._save(data)
    
    def broadcast(self, sender: str, message: str, task_type: str = "message"):
        """广播消息给所有Agent"""
        agents = ["executor", "analyzer", "orchestrator", "monitor", "learner", "messenger"]
        for agent in agents:
            if agent != sender:
                self.publish(sender, agent, message, task_type)

if __name__ == "__main__":
    bus = EnhancedMessageBus()
    # 测试
    bus.publish("monitor", "executor", "磁盘告警", "task", {"disk": 95})
    bus.publish("system", "messenger", "系统状态", "message", {"load": 0.5})
    bus.broadcast("orchestrator", "工作流启动", "event")
    print("增强消息总线测试通过")
    print(f"任务: {bus.get_tasks()}")
    print(f"事件: {bus.get_events()}")
