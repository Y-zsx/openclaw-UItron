#!/usr/bin/env python3
"""
多智能体通信总线
实现智能体间的消息传递
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

WORKFLOW_DIR = Path("/root/.openclaw/workspace/ultron-workflow")
MESSAGES_DIR = WORKFLOW_DIR / "messages"
AGENTS_DIR = WORKFLOW_DIR / "agents"


class MessageBus:
    """消息总线 - 智能体间通信基础设施"""
    
    def __init__(self):
        MESSAGES_DIR.mkdir(exist_ok=True)
        AGENTS_DIR.mkdir(exist_ok=True)
    
    def create_message(self, sender: str, receiver: str, msg_type: str, payload: Dict) -> Dict:
        """创建消息"""
        return {
            "msg_id": str(uuid.uuid4())[:8],
            "sender": sender,
            "receiver": receiver,
            "type": msg_type,
            "payload": payload,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
    
    def send(self, message: Dict) -> bool:
        """发送消息到接收者邮箱"""
        receiver = message["receiver"]
        inbox_path = MESSAGES_DIR / f"{receiver}_in.json"
        
        # 读取现有消息
        messages = []
        if inbox_path.exists():
            try:
                with open(inbox_path) as f:
                    messages = json.load(f)
            except:
                messages = []
        
        messages.append(message)
        
        # 写入
        try:
            with open(inbox_path, 'w') as f:
                json.dump(messages, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False
    
    def receive(self, agent_id: str) -> List[Dict]:
        """接收消息"""
        inbox_path = MESSAGES_DIR / f"{agent_id}_in.json"
        
        if not inbox_path.exists():
            return []
        
        try:
            with open(inbox_path) as f:
                messages = json.load(f)
            
            # 清空收件箱
            with open(inbox_path, 'w') as f:
                json.dump([], f)
            
            return messages
        except:
            return []
    
    def list_agents(self) -> List[str]:
        """列出所有活跃智能体"""
        registry_file = AGENTS_DIR / "registry.json"
        if not registry_file.exists():
            return []
        try:
            with open(registry_file) as f:
                registry = json.load(f)
            return [aid for aid, info in registry.items() if info.get("status") == "active"]
        except:
            return []
    
    def broadcast(self, sender: str, msg_type: str, payload: Dict, exclude: List[str] = None) -> int:
        """广播消息给所有已注册智能体"""
        if exclude is None:
            exclude = []
        
        agents = self.list_agents()
        count = 0
        
        for agent_id in agents:
            if agent_id != sender and agent_id not in exclude:
                msg = self.create_message(sender, agent_id, msg_type, payload)
                if self.send(msg):
                    count += 1
        
        return count


class AgentRegistry:
    """智能体注册表"""
    
    def __init__(self):
        self.registry_file = AGENTS_DIR / "registry.json"
    
    def register(self, agent_id: str, name: str, agent_type: str, capabilities: List[str]) -> bool:
        """注册智能体"""
        registry = self._load()
        
        registry[agent_id] = {
            "name": name,
            "type": agent_type,
            "capabilities": capabilities,
            "registered_at": datetime.now().isoformat(),
            "last_seen": datetime.now().isoformat(),
            "status": "active"
        }
        
        return self._save(registry)
    
    def unregister(self, agent_id: str) -> bool:
        """注销智能体"""
        registry = self._load()
        if agent_id in registry:
            del registry[agent_id]
            return self._save(registry)
        return False
    
    def update_status(self, agent_id: str, status: str) -> bool:
        """更新状态"""
        registry = self._load()
        if agent_id in registry:
            registry[agent_id]["status"] = status
            registry[agent_id]["last_seen"] = datetime.now().isoformat()
            return self._save(registry)
        return False
    
    def list_agents(self, agent_type: str = None) -> List[str]:
        """列出智能体"""
        registry = self._load()
        
        if agent_type:
            return [aid for aid, info in registry.items() 
                   if info.get("type") == agent_type and info.get("status") == "active"]
        
        return [aid for aid, info in registry.items() if info.get("status") == "active"]
    
    def get_agent(self, agent_id: str) -> Optional[Dict]:
        """获取智能体信息"""
        registry = self._load()
        return registry.get(agent_id)
    
    def _load(self) -> Dict:
        if not self.registry_file.exists():
            return {}
        try:
            with open(self.registry_file) as f:
                return json.load(f)
        except:
            return {}
    
    def _save(self, registry: Dict) -> bool:
        try:
            with open(self.registry_file, 'w') as f:
                json.dump(registry, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False


class TaskQueue:
    """任务队列 - 支持多智能体分发"""
    
    def __init__(self):
        self.queue_file = AGENTS_DIR / "task_queue.json"
    
    def submit(self, task: Dict) -> str:
        """提交任务"""
        queue = self._load()
        
        task_id = f"task_{len(queue.get('pending', [])) + 1}"
        task["task_id"] = task_id
        task["created_at"] = datetime.now().isoformat()
        task["status"] = "pending"
        
        queue.setdefault("pending", []).append(task)
        self._save(queue)
        
        return task_id
    
    def assign(self, task_id: str, agent_id: str) -> bool:
        """分配任务给智能体"""
        queue = self._load()
        
        for task in queue.get("pending", []):
            if task.get("task_id") == task_id:
                task["assigned_to"] = agent_id
                task["assigned_at"] = datetime.now().isoformat()
                task["status"] = "assigned"
                
                queue.setdefault("assigned", []).append(task)
                queue["pending"] = [t for t in queue["pending"] if t.get("task_id") != task_id]
                
                self._save(queue)
                return True
        
        return False
    
    def complete(self, task_id: str, result: Dict) -> bool:
        """完成任务"""
        queue = self._load()
        
        # 从assigned中移除
        for task in queue.get("assigned", []):
            if task.get("task_id") == task_id:
                task["status"] = "completed"
                task["completed_at"] = datetime.now().isoformat()
                task["result"] = result
                
                queue.setdefault("completed", []).append(task)
                queue["assigned"] = [t for t in queue["assigned"] if t.get("task_id") != task_id]
                
                self._save(queue)
                return True
        
        return False
    
    def get_pending(self) -> List[Dict]:
        """获取待处理任务"""
        queue = self._load()
        return queue.get("pending", [])
    
    def get_assigned(self) -> List[Dict]:
        """获取已分配任务"""
        queue = self._load()
        return queue.get("assigned", [])
    
    def _load(self) -> Dict:
        if not self.queue_file.exists():
            return {}
        try:
            with open(self.queue_file) as f:
                return json.load(f)
        except:
            return {}
    
    def _save(self, queue: Dict) -> bool:
        try:
            with open(self.queue_file, 'w') as f:
                json.dump(queue, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False


# ============ 便捷函数 ============

def init_collaboration_system():
    """初始化协作系统"""
    bus = MessageBus()
    registry = AgentRegistry()
    task_queue = TaskQueue()
    
    # 注册主智能体
    registry.register(
        agent_id="ultron",
        name="奥创",
        agent_type="master",
        capabilities=["决策", "规划", "学习", "创造"]
    )
    
    print("✓ 协作系统初始化完成")
    print(f"  - 消息总线就绪")
    print(f"  - 智能体注册表: {len(registry.list_agents())} 个智能体")
    print(f"  - 任务队列: {len(task_queue.get_pending())} 个待处理任务")
    
    return bus, registry, task_queue


if __name__ == "__main__":
    init_collaboration_system()