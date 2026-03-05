#!/usr/bin/env python3
"""
Agent协作网络任务队列与消息传递系统CLI
统一入口：任务提交、状态查询、消息传递
"""
import argparse
import json
import sys
import uuid
from datetime import datetime
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))

from multi_agent_collaboration import (
    AgentNetwork, TaskRouter, CollaborationStateMachine,
    MessageBroker, AgentInfo, AgentCapability, CollaborationTask,
    CollaborationPattern, TaskStatus
)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

NETWORK_FILE = DATA_DIR / "collab_network.json"
BROKER_FILE = DATA_DIR / "collab_broker.json"
TASKS_FILE = DATA_DIR / "collab_tasks.json"


class CollabSystem:
    """统一协作系统"""
    
    def __init__(self):
        self.network = AgentNetwork()
        self.router = TaskRouter(self.network, pattern=CollaborationPattern.HIERARCHICAL)
        self.broker = MessageBroker()
        self.state_machine = CollaborationStateMachine()
        self._load_state()
    
    def _load_state(self):
        """加载持久化状态"""
        # Load network
        if NETWORK_FILE.exists():
            with open(NETWORK_FILE) as f:
                data = json.load(f)
                for agent_id, info in data.get('agents', {}).items():
                    # Convert capabilities from strings to enums
                    if 'capabilities' in info and isinstance(info['capabilities'][0], str):
                        info['capabilities'] = [AgentCapability(c) for c in info['capabilities']]
                    self.network.register_agent(AgentInfo(**info))
        
        # Load broker state
        if BROKER_FILE.exists():
            with open(BROKER_FILE) as f:
                self.broker.__dict__.update(json.load(f))
        
        # Load tasks
        if TASKS_FILE.exists():
            with open(TASKS_FILE) as f:
                self.tasks = json.load(f)
        else:
            self.tasks = {}
    
    def _save_state(self):
        """保存状态"""
        # Save network
        network_data = {
            'agents': {
                aid: {
                    'agent_id': a.agent_id,
                    'name': a.name,
                    'capabilities': [c.value for c in a.capabilities],
                    'status': a.status,
                    'load': a.load,
                    'reliability': a.reliability,
                    'metadata': a.metadata
                }
                for aid, a in self.network.agents.items()
            }
        }
        with open(NETWORK_FILE, 'w') as f:
            json.dump(network_data, f, indent=2)
        
        # Save broker - convert AgentMessage to dict
        messages_data = []
        for m in getattr(self.broker, 'messages', []):
            if hasattr(m, '__dict__'):
                messages_data.append({
                    'message_id': m.message_id,
                    'sender_id': m.sender_id,
                    'receiver_id': m.receiver_id,
                    'message_type': m.message_type,
                    'payload': m.payload,
                    'correlation_id': m.correlation_id,
                    'timestamp': m.timestamp
                })
        
        broker_data = {
            'messages': messages_data,
            'subscribers': {k: list(v) for k, v in getattr(self.broker, 'subscribers', {}).items()}
        }
        with open(BROKER_FILE, 'w') as f:
            json.dump(broker_data, f, indent=2)
        
        # Save tasks
        with open(TASKS_FILE, 'w') as f:
            json.dump(self.tasks, f, indent=2)
    
    def register_agent(self, name: str, capabilities: list) -> str:
        """注册Agent"""
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        caps = [AgentCapability(c) for c in capabilities]
        agent = AgentInfo(agent_id, name, caps)
        self.network.register_agent(agent)
        self._save_state()
        return agent_id
    
    def submit_task(self, task_type: str, description: str, 
                    capabilities: list, input_data: dict = None) -> str:
        """提交任务"""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        required_caps = [AgentCapability(c) for c in capabilities]
        
        task = CollaborationTask(
            task_id=task_id,
            task_type=task_type,
            description=description,
            required_capabilities=required_caps,
            input_data=input_data or {}
        )
        
        # Route to agents
        assigned = self.router.route_task(task)
        
        # Store task
        self.tasks[task_id] = {
            'task_id': task_id,
            'type': task_type,
            'description': description,
            'capabilities': capabilities,
            'assigned': assigned,
            'status': 'routing',
            'created_at': datetime.now().isoformat()
        }
        
        self._save_state()
        return task_id
    
    def send_message(self, sender: str, receiver: str, 
                     msg_type: str, payload: dict) -> str:
        """发送消息"""
        import uuid
        from multi_agent_collaboration import AgentMessage
        
        message = AgentMessage(
            message_id=f"msg-{uuid.uuid4().hex[:8]}",
            sender_id=sender,
            receiver_id=receiver,
            message_type=msg_type,
            payload=payload
        )
        
        self.broker.publish(message)
        self._save_state()
        return message.message_id
    
    def get_task_status(self, task_id: str) -> dict:
        """获取任务状态"""
        return self.tasks.get(task_id, {'error': 'Task not found'})
    
    def list_agents(self) -> list:
        """列出所有Agent"""
        return [
            {
                'id': a.agent_id,
                'name': a.name,
                'capabilities': [c.value for c in a.capabilities],
                'status': a.status,
                'load': a.load
            }
            for a in self.network.agents.values()
        ]
    
    def get_messages(self, channel: str = None) -> list:
        """获取消息"""
        messages = []
        for m in getattr(self.broker, 'messages', []):
            if hasattr(m, '__dict__'):
                messages.append({
                    'message_id': m.message_id,
                    'sender_id': m.sender_id,
                    'receiver_id': m.receiver_id,
                    'message_type': m.message_type,
                    'payload': m.payload,
                    'timestamp': m.timestamp
                })
        if channel:
            return [m for m in messages if m.get('receiver_id') == channel]
        return messages
    
    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            'agents': len(self.network.agents),
            'tasks': len(self.tasks),
            'messages': len(getattr(self.broker, 'messages', [])),
            'subscribers': len(getattr(self.broker, 'subscribers', {}))
        }


def main():
    parser = argparse.ArgumentParser(description='Agent协作系统CLI')
    parser.add_argument('--json', action='store_true', help='JSON输出')
    
    sub = parser.add_subparsers(dest='cmd', help='命令')
    
    # Register agent
    sub.add_parser('register', help='注册Agent')
    sub.add_parser('agents', help='列出Agent')
    sub.add_parser('stats', help='系统统计')
    
    # Task commands
    task_parser = sub.add_parser('submit', help='提交任务')
    task_parser.add_argument('--type', required=True, help='任务类型')
    task_parser.add_argument('--desc', required=True, help='任务描述')
    task_parser.add_argument('--caps', required=True, help='所需能力(逗号分隔)')
    task_parser.add_argument('--data', help='输入数据(JSON)')
    
    # Message commands
    msg_parser = sub.add_parser('message', help='发送消息')
    msg_parser.add_argument('--from', dest='sender', required=True, help='发送者')
    msg_parser.add_argument('--to', dest='receiver', required=True, help='接收者')
    msg_parser.add_argument('--type', required=True, help='消息类型')
    msg_parser.add_argument('--payload', required=True, help='消息内容(JSON)')
    
    # Query commands
    sub.add_parser('messages', help='查看消息')
    sub.add_parser('tasks', help='列出任务')
    
    args = parser.parse_args()
    
    collab = CollabSystem()
    
    if args.cmd == 'register':
        # Interactive registration
        name = input('Agent名称: ').strip()
        caps_input = input('能力(monitor,execute,analyze,communicate,orchestrate): ').strip()
        capabilities = [c.strip() for c in caps_input.split(',')]
        agent_id = collab.register_agent(name, capabilities)
        print(f"✅ Agent注册成功: {agent_id}")
    
    elif args.cmd == 'agents':
        agents = collab.list_agents()
        if args.json:
            print(json.dumps(agents, indent=2, ensure_ascii=False))
        else:
            for a in agents:
                print(f"  {a['id']}: {a['name']} ({a['status']}) - {a['capabilities']}")
    
    elif args.cmd == 'stats':
        stats = collab.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print(f"  Agents: {stats['agents']}")
            print(f"  Tasks: {stats['tasks']}")
            print(f"  Messages: {stats['messages']}")
            print(f"  Subscribers: {stats['subscribers']}")
    
    elif args.cmd == 'submit':
        capabilities = [c.strip() for c in args.caps.split(',')]
        input_data = json.loads(args.data) if args.data else {}
        task_id = collab.submit_task(args.type, args.desc, capabilities, input_data)
        task = collab.get_task_status(task_id)
        if args.json:
            print(json.dumps(task, indent=2, ensure_ascii=False))
        else:
            print(f"✅ 任务已提交: {task_id}")
            print(f"   分配给: {task.get('assigned', [])}")
    
    elif args.cmd == 'message':
        payload = json.loads(args.payload)
        msg_id = collab.send_message(args.sender, args.receiver, args.type, payload)
        if args.json:
            print(json.dumps({'message_id': msg_id}, indent=2))
        else:
            print(f"✅ 消息已发送: {msg_id}")
    
    elif args.cmd == 'messages':
        messages = collab.get_messages()
        if args.json:
            print(json.dumps(messages, indent=2, ensure_ascii=False))
        else:
            for m in messages[-10:]:
                print(f"  {m.get('timestamp', '')} [{m.get('message_type', '')}] {m.get('sender_id', '')} → {m.get('receiver_id', '')}")
    
    elif args.cmd == 'tasks':
        tasks = list(collab.tasks.values())
        if args.json:
            print(json.dumps(tasks, indent=2, ensure_ascii=False))
        else:
            for t in tasks:
                print(f"  {t['task_id']}: {t['type']} - {t['status']} (分配: {t.get('assigned', [])})")
    
    else:
        parser.print_help()


if __name__ == "__main__":
    main()