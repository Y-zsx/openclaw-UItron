#!/usr/bin/env python3
"""
多智能体协作框架 (Multi-Agent Collaboration Framework)
第12世: 设计多智能体协作架构

核心组件:
- CollaborationProtocol: 协作协议定义
- AgentNetwork: Agent网络拓扑
- TaskRouter: 任务路由与分发
- CollaborationStateMachine: 协作状态机
- MessageBroker: 消息中间件
"""

import asyncio
import json
import uuid
import time
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("multi-agent-collaboration")


class CollaborationPattern(Enum):
    """协作模式"""
    MASTER_SLAVE = "master_slave"      # 主从模式
    PEER_TO_PEER = "p2p"               # 点对点模式
    HIERARCHICAL = "hierarchical"      # 分层模式
    HUB_SPOKE = "hub_spoke"            # 中心辐射模式
    CHAIN = "chain"                    # 链式模式


class TaskStatus(Enum):
    """任务状态"""
    PENDING = "pending"
    ROUTING = "routing"
    PROCESSING = "processing"
    COLLABORATING = "collaborating"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class AgentCapability(Enum):
    """Agent能力枚举"""
    MONITOR = "monitor"
    EXECUTE = "execute"
    ANALYZE = "analyze"
    COMMUNICATE = "communicate"
    ORCHESTRATE = "orchestrate"
    LEARN = "learn"
    SECURE = "secure"
    NOTIFY = "notify"
    REPAIR = "repair"


@dataclass
class AgentInfo:
    """Agent信息"""
    agent_id: str
    name: str
    capabilities: List[AgentCapability]
    status: str = "idle"
    load: float = 0.0
    reliability: float = 1.0
    metadata: Dict = field(default_factory=dict)


@dataclass
class CollaborationTask:
    """协作任务"""
    task_id: str
    task_type: str
    description: str
    required_capabilities: List[AgentCapability]
    input_data: Dict
    context: Dict = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    assigned_agents: List[str] = field(default_factory=list)
    results: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    timeout: int = 300


@dataclass
class AgentMessage:
    """Agent间消息"""
    message_id: str
    sender_id: str
    receiver_id: str
    message_type: str
    payload: Dict
    correlation_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


class CollaborationProtocol:
    """协作协议"""
    
    PROTOCOLS = {
        "request_response": "请求-响应模式",
        "publish_subscribe": "发布-订阅模式",
        "event_driven": "事件驱动模式",
        "pipeline": "管道模式",
        "broadcast": "广播模式",
    }
    
    @staticmethod
    def create_message(sender: str, receiver: str, msg_type: str, 
                       payload: Dict, correlation_id: str = None) -> AgentMessage:
        """创建消息"""
        return AgentMessage(
            message_id=str(uuid.uuid4()),
            sender_id=sender,
            receiver_id=receiver,
            message_type=msg_type,
            payload=payload,
            correlation_id=correlation_id
        )
    
    @staticmethod
    def validate_message(msg: AgentMessage) -> bool:
        """验证消息"""
        return bool(msg.sender_id and msg.receiver_id and msg.message_type)


class AgentNetwork:
    """Agent网络拓扑"""
    
    def __init__(self):
        self.agents: Dict[str, AgentInfo] = {}
        self.connections: Dict[str, List[str]] = defaultdict(list)
        self.capability_index: Dict[AgentCapability, List[str]] = defaultdict(list)
    
    def register_agent(self, agent: AgentInfo):
        """注册Agent"""
        self.agents[agent.agent_id] = agent
        for cap in agent.capabilities:
            self.capability_index[cap].append(agent.agent_id)
        logger.info(f"注册Agent: {agent.name} ({agent.agent_id})")
    
    def connect_agents(self, agent1: str, agent2: str):
        """建立Agent连接"""
        if agent1 not in self.connections[agent1]:
            self.connections[agent1].append(agent2)
        if agent2 not in self.connections[agent2]:
            self.connections[agent2].append(agent1)
    
    def find_agents_by_capability(self, capability: AgentCapability) -> List[AgentInfo]:
        """按能力查找Agent"""
        agent_ids = self.capability_index.get(capability, [])
        return [self.agents[aid] for aid in agent_ids if aid in self.agents]
    
    def find_best_agent(self, capability: AgentCapability) -> Optional[AgentInfo]:
        """查找最优Agent(负载最低)"""
        agents = self.find_agents_by_capability(capability)
        if not agents:
            return None
        available = [a for a in agents if a.status != "busy"]
        if not available:
            return min(agents, key=lambda a: a.load)
        return min(available, key=lambda a: a.load)


class TaskRouter:
    """任务路由"""
    
    def __init__(self, network: AgentNetwork, pattern: CollaborationPattern):
        self.network = network
        self.pattern = pattern
        self.routes: Dict[str, Callable] = {}
        self._register_default_routes()
    
    def _register_default_routes(self):
        """注册默认路由策略"""
        self.routes["master_slave"] = self._route_master_slave
        self.routes["p2p"] = self._route_p2p
        self.routes["hierarchical"] = self._route_hierarchical
        self.routes["hub_spoke"] = self._route_hub_spoke
        self.routes["chain"] = self._route_chain
    
    def route_task(self, task: CollaborationTask) -> List[str]:
        """路由任务"""
        route_func = self.routes.get(self.pattern.value, self._route_master_slave)
        return route_func(task)
    
    def _route_master_slave(self, task: CollaborationTask) -> List[str]:
        """主从模式: 一个主Agent协调多个从Agent"""
        # 找编排Agent作为主
        orchestrators = self.network.find_agents_by_capability(AgentCapability.ORCHESTRATE)
        if not orchestrators:
            # 回退: 按能力匹配第一个
            agents = []
            for cap in task.required_capabilities:
                agent = self.network.find_best_agent(cap)
                if agent and agent.agent_id not in agents:
                    agents.append(agent.agent_id)
            return agents
        
        # 主Agent处理编排，从Agent处理具体任务
        main = orchestrators[0].agent_id
        workers = []
        for cap in task.required_capabilities:
            if cap != AgentCapability.ORCHESTRATE:
                agent = self.network.find_best_agent(cap)
                if agent:
                    workers.append(agent.agent_id)
        return [main] + workers
    
    def _route_p2p(self, task: CollaborationTask) -> List[str]:
        """点对点模式: 任务并行发送到多个Agent"""
        agents = []
        for cap in task.required_capabilities:
            agent = self.network.find_best_agent(cap)
            if agent and agent.agent_id not in agents:
                agents.append(agent.agent_id)
        return agents
    
    def _route_hierarchical(self, task: CollaborationTask) -> List[str]:
        """分层模式: 按层级路由"""
        # 层级1: 编排层
        orchestrators = self.network.find_agents_by_capability(AgentCapability.ORCHESTRATE)
        # 层级2: 执行层
        executors = self.network.find_agents_by_capability(AgentCapability.EXECUTE)
        # 层级3: 监控层
        monitors = self.network.find_agents_by_capability(AgentCapability.MONITOR)
        
        route = []
        if orchestrators:
            route.append(orchestrators[0].agent_id)
        route.extend([a.agent_id for a in executors[:2]])
        route.extend([a.agent_id for a in monitors[:1]])
        return route
    
    def _route_hub_spoke(self, task: CollaborationTask) -> List[str]:
        """中心辐射模式: 通过中心Agent转发"""
        # 通信Agent作为中心
        communicators = self.network.find_agents_by_capability(AgentCapability.COMMUNICATE)
        hub = communicators[0].agent_id if communicators else None
        
        agents = []
        for cap in task.required_capabilities:
            if cap != AgentCapability.COMMUNICATE:
                agent = self.network.find_best_agent(cap)
                if agent:
                    agents.append(agent.agent_id)
        
        if hub:
            return [hub] + agents
        return agents
    
    def _route_chain(self, task: CollaborationTask) -> List[str]:
        """链式模式: 任务依次经过各Agent"""
        agents = []
        for cap in task.required_capabilities:
            agent = self.network.find_best_agent(cap)
            if agent and agent.agent_id not in agents:
                agents.append(agent.agent_id)
        return agents


class CollaborationStateMachine:
    """协作状态机"""
    
    STATES = {
        "init": ["routing", "completed", "failed"],
        "routing": ["processing", "failed"],
        "processing": ["collaborating", "completed", "failed"],
        "collaborating": ["processing", "completed", "failed"],
        "completed": [],
        "failed": ["routing"],  # 可重试
        "timeout": ["routing"],  # 可重试
    }
    
    def __init__(self):
        self.task_states: Dict[str, str] = {}
        self.task_history: Dict[str, List[Dict]] = defaultdict(list)
    
    def transition(self, task_id: str, new_state: str) -> bool:
        """状态转换"""
        current = self.task_states.get(task_id, "init")
        allowed = self.STATES.get(current, [])
        
        if new_state in allowed:
            self.task_states[task_id] = new_state
            self.task_history[task_id].append({
                "state": new_state,
                "timestamp": time.time()
            })
            logger.info(f"任务 {task_id}: {current} -> {new_state}")
            return True
        
        logger.warning(f"任务 {task_id}: {current} -> {new_state} 不允许")
        return False
    
    def get_state(self, task_id: str) -> str:
        return self.task_states.get(task_id, "init")


class MessageBroker:
    """消息中间件"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[str]] = defaultdict(list)
        self.messages: List[AgentMessage] = []
        self.handlers: Dict[str, Callable] = {}
    
    def subscribe(self, agent_id: str, message_type: str):
        """订阅消息"""
        if agent_id not in self.subscribers[message_type]:
            self.subscribers[message_type].append(agent_id)
    
    def publish(self, message: AgentMessage):
        """发布消息"""
        self.messages.append(message)
        subscribers = self.subscribers.get(message.message_type, [])
        
        for subscriber in subscribers:
            handler = self.handlers.get(subscriber)
            if handler:
                handler(message)
    
    def register_handler(self, agent_id: str, handler: Callable):
        """注册处理器"""
        self.handlers[agent_id] = handler


class MultiAgentCollaboration:
    """多智能体协作框架"""
    
    def __init__(self, pattern: CollaborationPattern = CollaborationPattern.HIERARCHICAL):
        self.network = AgentNetwork()
        self.router = TaskRouter(self.network, pattern)
        self.state_machine = CollaborationStateMachine()
        self.broker = MessageBroker()
        self.tasks: Dict[str, CollaborationTask] = {}
        self.collaboration_handlers: Dict[str, Callable] = {}
        
        # 预注册系统Agent
        self._register_system_agents()
    
    def _register_system_agents(self):
        """注册系统Agent"""
        system_agents = [
            AgentInfo("monitor-01", "Monitor Agent", 
                     [AgentCapability.MONITOR, AgentCapability.NOTIFY]),
            AgentInfo("executor-01", "Executor Agent", 
                     [AgentCapability.EXECUTE, AgentCapability.REPAIR]),
            AgentInfo("analyzer-01", "Analyzer Agent", 
                     [AgentCapability.ANALYZE, AgentCapability.LEARN]),
            AgentInfo("communicator-01", "Communicator Agent", 
                     [AgentCapability.COMMUNICATE, AgentCapability.NOTIFY]),
            AgentInfo("orchestrator-01", "Orchestrator Agent", 
                     [AgentCapability.ORCHESTRATE]),
        ]
        
        for agent in system_agents:
            self.network.register_agent(agent)
            
        # 建立连接
        self.network.connect_agents("orchestrator-01", "monitor-01")
        self.network.connect_agents("orchestrator-01", "executor-01")
        self.network.connect_agents("orchestrator-01", "analyzer-01")
        self.network.connect_agents("communicator-01", "orchestrator-01")
    
    def register_agent(self, agent: AgentInfo):
        """注册自定义Agent"""
        self.network.register_agent(agent)
    
    def submit_task(self, task_type: str, description: str,
                   required_capabilities: List[AgentCapability],
                   input_data: Dict) -> str:
        """提交协作任务"""
        task = CollaborationTask(
            task_id=str(uuid.uuid4())[:8],
            task_type=task_type,
            description=description,
            required_capabilities=required_capabilities,
            input_data=input_data
        )
        
        self.tasks[task.task_id] = task
        self.state_machine.transition(task.task_id, "routing")
        
        # 路由任务
        assigned = self.router.route_task(task)
        task.assigned_agents = assigned
        task.status = TaskStatus.ROUTING
        
        logger.info(f"任务 {task.task_id} 路由到: {assigned}")
        
        # 同步执行任务 (简化版)
        self._execute_task_sync(task)
        
        return task.task_id
    
    def _execute_task_sync(self, task: CollaborationTask):
        """同步执行协作任务"""
        self.state_machine.transition(task.task_id, "processing")
        
        results = {}
        for agent_id in task.assigned_agents:
            agent = self.network.agents.get(agent_id)
            if not agent:
                continue
            
            # 模拟Agent执行
            result = self._call_agent_sync(agent, task)
            results[agent_id] = result
            
            # 发布任务完成事件
            msg = CollaborationProtocol.create_message(
                agent_id, "system", "task_complete",
                {"task_id": task.task_id, "result": result}
            )
            self.broker.publish(msg)
        
        task.results = results
        task.status = TaskStatus.COMPLETED
        self.state_machine.transition(task.task_id, "completed")
        
        logger.info(f"任务 {task.task_id} 完成")
    
    def _call_agent_sync(self, agent: AgentInfo, task: CollaborationTask) -> Dict:
        """同步调用Agent"""
        logger.info(f"Agent {agent.name} 处理任务 {task.task_id}")
        
        # 根据能力返回模拟结果
        if AgentCapability.MONITOR in agent.capabilities:
            return {"status": "monitored", "data": {"cpu": 45, "memory": 62}}
        elif AgentCapability.EXECUTE in agent.capabilities:
            return {"status": "executed", "output": "operation completed"}
        elif AgentCapability.ANALYZE in agent.capabilities:
            return {"status": "analyzed", "insights": ["normal", "no anomaly"]}
        elif AgentCapability.COMMUNICATE in agent.capabilities:
            return {"status": "notified", "recipients": 1}
        elif AgentCapability.ORCHESTRATE in agent.capabilities:
            return {"status": "orchestrated", "agents": task.assigned_agents}
        
        return {"status": "done"}
    

    
    def get_task_status(self, task_id: str) -> Dict:
        """获取任务状态"""
        task = self.tasks.get(task_id)
        if not task:
            return {"error": "task not found"}
        
        return {
            "task_id": task.task_id,
            "status": task.status.value,
            "assigned_agents": task.assigned_agents,
            "results": task.results,
            "state": self.state_machine.get_state(task_id)
        }
    
    def register_collaboration_handler(self, event: str, handler: Callable):
        """注册协作事件处理器"""
        self.collaboration_handlers[event] = handler
    
    def get_network_status(self) -> Dict:
        """获取网络状态"""
        return {
            "total_agents": len(self.network.agents),
            "agents": [
                {
                    "id": a.agent_id,
                    "name": a.name,
                    "capabilities": [c.value for c in a.capabilities],
                    "status": a.status,
                    "load": a.load
                }
                for a in self.network.agents.values()
            ]
        }


# CLI工具
def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="多智能体协作框架")
    parser.add_argument("--pattern", choices=["master_slave", "p2p", "hierarchical", 
                                               "hub_spoke", "chain"],
                       default="hierarchical", help="协作模式")
    parser.add_argument("--action", choices=["submit", "status", "network"],
                       default="network", help="操作")
    parser.add_argument("--task-type", help="任务类型")
    parser.add_argument("--capabilities", help="所需能力(逗号分隔)")
    parser.add_argument("--task-id", help="任务ID")
    
    args = parser.parse_args()
    
    pattern = CollaborationPattern(args.pattern)
    framework = MultiAgentCollaboration(pattern)
    
    if args.action == "network":
        status = framework.get_network_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
    
    elif args.action == "submit":
        caps = [AgentCapability(c.strip()) for c in args.capabilities.split(",")]
        task_id = framework.submit_task(
            args.task_type or "generic",
            "协作任务",
            caps,
            {"data": "test"}
        )
        print(f"任务已提交: {task_id}")
        time.sleep(2)
        print(json.dumps(framework.get_task_status(task_id), indent=2, ensure_ascii=False))
    
    elif args.action == "status":
        if args.task_id:
            print(json.dumps(framework.get_task_status(args.task_id), indent=2, ensure_ascii=False))
        else:
            print("需要 --task-id")


if __name__ == "__main__":
    main()