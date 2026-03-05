#!/usr/bin/env python3
"""
星际智能体系统 (Interstellar Agents)
奥创夙愿二十七第2世 - 跨星际协作核心组件

功能：
- 分布式星际智能体架构
- 自治智能体生命周期管理
- 跨光年延迟的智能决策
- 智能体协作与通信协议
- 动态能力适应与学习
"""

import asyncio
import json
import time
import uuid
import random
import hashlib
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Any, Callable, Tuple
from enum import Enum, auto
from collections import defaultdict
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("InterstellarAgents")


class AgentState(Enum):
    """智能体状态"""
    DORMANT = auto()      # 休眠状态
    AWAKENING = auto()    # 唤醒中
    ACTIVE = auto()       # 活跃
    NEGOTIATING = auto()  # 协商中
    EXECUTING = auto()    # 执行任务
    WAITING = auto()      # 等待响应
    LEARNING = auto()     # 学习中
    HIBERNATING = auto()  # 冬眠（长距离通信时）


class AgentCapability(Enum):
    """智能体能力类型"""
    NAVIGATION = auto()       # 导航
    COMMUNICATION = auto()    # 通信
    ANALYSIS = auto()         # 分析
    DECISION = auto()         # 决策
    EXECUTION = auto()        # 执行
    LEARNING = auto()         # 学习
    ADAPTATION = auto()       # 适应
    NEGOTIATION = auto()      # 协商
    PREDICTION = auto()       # 预测
    COORDINATION = auto()     # 协调


class TaskUrgency(Enum):
    """任务紧急程度"""
    CRITICAL = 1   # 紧急
    HIGH = 2       # 高
    NORMAL = 3     # 正常
    LOW = 4        # 低
    BACKGROUND = 5 # 后台


@dataclass
class Position:
    """星际位置"""
    x: float
    y: float
    z: float
    system: str = ""
    galaxy: str = ""
    
    def distance_to(self, other: 'Position') -> float:
        """计算到另一个位置的距离（光年）"""
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return (dx*dx + dy*dy + dz*dz) ** 0.5
    
    def light_years_to(self, other: 'Position') -> float:
        """光年距离（简化模型：1单位=1光年）"""
        return self.distance_to(other)


@dataclass
class AgentCapabilityProfile:
    """智能体能力画像"""
    navigation: float = 0.5      # 0-1 导航能力
    communication: float = 0.5   # 0-1 通信能力
    analysis: float = 0.5        # 0-1 分析能力
    decision: float = 0.5        # 0-1 决策能力
    execution: float = 0.5       # 0-1 执行能力
    learning: float = 0.5        # 0-1 学习能力
    adaptation: float = 0.5      # 0-1 适应能力
    negotiation: float = 0.5     # 0-1 协商能力
    prediction: float = 0.5      # 0-1 预测能力
    coordination: float = 0.5    # 0-1 协调能力
    
    def get_capability(self, cap: AgentCapability) -> float:
        """获取指定能力值"""
        return getattr(self, cap.name.lower(), 0.5)
    
    def set_capability(self, cap: AgentCapability, value: float):
        """设置指定能力值"""
        setattr(self, cap.name.lower(), max(0.0, min(1.0, value)))
    
    def similarity_to(self, other: 'AgentCapabilityProfile') -> float:
        """计算与另一个能力画像的相似度"""
        total = 0
        for cap in AgentCapability:
            diff = abs(self.get_capability(cap) - other.get_capability(cap))
            total += (1 - diff)
        return total / len(AgentCapability)
    
    def can_handle_task(self, requirements: Dict[AgentCapability, float]) -> bool:
        """检查是否能满足任务需求"""
        for cap, min_level in requirements.items():
            if self.get_capability(cap) < min_level:
                return False
        return True


@dataclass
class InterstellarTask:
    """星际任务"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    requirements: Dict[AgentCapability, float] = field(default_factory=dict)
    urgency: TaskUrgency = TaskUrgency.NORMAL
    deadline: float = 0  # 时间戳
    estimated_duration: float = 0  # 预计持续时间（秒）
    priority_score: float = 0
    source_position: Position = None
    target_position: Position = None
    subtasks: List['InterstellarTask'] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    resources_needed: Dict[str, float] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_priority(self, current_time: float) -> float:
        """计算优先级分数"""
        base_score = (6 - self.urgency.value) * 20  # 紧急程度基础分
        
        # 截止时间紧迫性
        if self.deadline > 0:
            time_left = self.deadline - current_time
            if time_left <= 0:
                base_score += 100  # 已过期
            elif time_left < 3600:  # 1小时内
                base_score += 50
            elif time_left < 86400:  # 1天内
                base_score += 20
        
        # 任务复杂度加分
        complexity = len(self.requirements) * 5
        base_score += complexity
        
        self.priority_score = base_score
        return base_score


@dataclass
class AgentMessage:
    """智能体消息"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str = ""
    sender_position: Position = None
    recipient_id: str = ""
    message_type: str = "info"
    content: Any = None
    timestamp: float = field(default_factory=time.time)
    delivery_time: float = 0  # 预计送达时间
    acknowledged: bool = False
    in_reply_to: str = ""
    thread_id: str = ""
    priority: int = 3
    
    def calculate_delivery_time(self, distance: float) -> float:
        """计算传递时间（光年距离/光速 = 年，这里简化为秒）"""
        self.delivery_time = distance + self.timestamp
        return self.delivery_time


class InterstellarAgent:
    """星际智能体"""
    
    def __init__(
        self,
        agent_id: str,
        position: Position,
        capabilities: AgentCapabilityProfile = None,
        name: str = ""
    ):
        self.id = agent_id
        self.name = name or f"Agent_{agent_id[:8]}"
        self.position = position
        self.capabilities = capabilities or AgentCapabilityProfile()
        self.state = AgentState.DORMANT
        
        # 任务管理
        self.current_task: Optional[InterstellarTask] = None
        self.task_queue: List[InterstellarTask] = []
        self.completed_tasks: List[InterstellarTask] = []
        self.failed_tasks: List[InterstellarTask] = []
        
        # 协作网络
        self.known_agents: Dict[str, 'InterstellarAgent'] = {}
        self.message_queue: List[AgentMessage] = []
        self.sent_messages: List[AgentMessage] = []
        
        # 学习与适应
        self.learned_patterns: Dict[str, Any] = {}
        self.performance_history: List[Dict[str, Any]] = []
        self.knowledge_base: Dict[str, Any] = {}
        
        # 资源
        self.energy: float = 100.0
        self.computational_power: float = 100.0
        self.storage: float = 100.0
        
        # 统计
        self.tasks_completed = 0
        self.tasks_failed = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.collaborations = 0
        
        self.lock = threading.RLock()
    
    def awaken(self):
        """唤醒智能体"""
        with self.lock:
            self.state = AgentState.AWAKENING
            logger.info(f"{self.name} 正在唤醒...")
            time.sleep(0.1)  # 模拟唤醒过程
            self.state = AgentState.ACTIVE
            logger.info(f"{self.name} 已唤醒，位于 {self.position.system}")
    
    def hibernate(self):
        """冬眠智能体"""
        with self.lock:
            if self.current_task:
                logger.warning(f"{self.name} 有未完成任务，进入强制冬眠")
            self.state = AgentState.HIBERNATING
            logger.info(f"{self.name} 进入冬眠状态")
    
    def receive_message(self, message: AgentMessage):
        """接收消息"""
        with self.lock:
            self.message_queue.append(message)
            self.messages_received += 1
            logger.debug(f"{self.name} 收到消息: {message.id}")
    
    def send_message(self, recipient: 'InterstellarAgent', content: Any, 
                     msg_type: str = "info") -> AgentMessage:
        """发送消息"""
        with self.lock:
            distance = self.position.light_years_to(recipient.position)
            message = AgentMessage(
                sender_id=self.id,
                sender_position=Position(self.position.x, self.position.y, self.position.z),
                recipient_id=recipient.id,
                message_type=msg_type,
                content=content
            )
            message.calculate_delivery_time(distance)
            
            self.sent_messages.append(message)
            self.messages_sent += 1
            
            # 模拟消息传递延迟
            if distance < 0.1:
                recipient.receive_message(message)
            else:
                # 长距离通信需要通过路由
                pass
            
            return message
    
    def add_task(self, task: InterstellarTask):
        """添加任务到队列"""
        with self.lock:
            task.calculate_priority(time.time())
            self.task_queue.append(task)
            self.task_queue.sort(key=lambda t: t.priority_score, reverse=True)
            logger.info(f"{self.name} 收到任务: {task.name} (优先级: {task.priority_score})")
    
    def assign_task(self, task: InterstellarTask) -> bool:
        """分配任务给智能体"""
        with self.lock:
            if not self.capabilities.can_handle_task(task.requirements):
                logger.warning(f"{self.name} 能力不足，无法执行任务 {task.name}")
                return False
            
            if self.state == AgentState.HIBERNATING:
                self.awaken()
            
            self.current_task = task
            self.state = AgentState.EXECUTING
            logger.info(f"{self.name} 开始执行任务: {task.name}")
            return True
    
    def complete_task(self, success: bool = True):
        """完成任务"""
        with self.lock:
            if self.current_task:
                if success:
                    self.completed_tasks.append(self.current_task)
                    self.tasks_completed += 1
                    logger.info(f"{self.name} 完成任务: {self.current_task.name}")
                    
                    # 学习机制
                    self._learn_from_task(self.current_task)
                else:
                    self.failed_tasks.append(self.current_task)
                    self.tasks_failed += 1
                    logger.error(f"{self.name} 任务失败: {self.current_task.name}")
                
                self.current_task = None
            
            # 获取下一个任务
            if self.task_queue:
                next_task = self.task_queue.pop(0)
                self.assign_task(next_task)
            else:
                self.state = AgentState.ACTIVE
    
    def _learn_from_task(self, task: InterstellarTask):
        """从任务中学习"""
        pattern_key = hashlib.md5(
            f"{task.name}:{list(task.requirements.keys())}".encode()
        ).hexdigest()
        
        if pattern_key not in self.learned_patterns:
            self.learned_patterns[pattern_key] = {
                "task_name": task.name,
                "count": 0,
                "success_rate": 0,
                "avg_duration": 0
            }
        
        pattern = self.learned_patterns[pattern_key]
        pattern["count"] += 1
        
        # 更新成功率
        total = pattern["count"]
        pattern["success_rate"] = (
            (pattern["success_rate"] * (total - 1) + 1) / total
        )
    
    def request_collaboration(self, other: 'InterstellarAgent', 
                              task: InterstellarTask) -> bool:
        """请求协作"""
        with self.lock:
            message = self.send_message(
                other,
                {
                    "type": "collaboration_request",
                    "task": {
                        "id": task.id,
                        "name": task.name,
                        "requirements": {k.name: v for k, v in task.requirements.items()}
                    }
                },
                "request"
            )
            
            self.state = AgentState.NEGOTIATING
            self.collaborations += 1
            return True
    
    def evaluate_collaboration(self, other: 'InterstellarAgent') -> float:
        """评估与另一个智能体的协作潜力"""
        capability_similarity = self.capabilities.similarity_to(other.capabilities)
        
        # 距离因素（越近越好协作）
        distance = self.position.light_years_to(other.position)
        distance_factor = max(0, 1 - distance / 100)  # 100光年内有效
        
        # 历史协作成功率
        # (这里简化，实际应从知识库查询)
        history_factor = 0.8
        
        return (capability_similarity * 0.4 + distance_factor * 0.3 + history_factor * 0.3)
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能体状态"""
        with self.lock:
            return {
                "id": self.id,
                "name": self.name,
                "state": self.state.name,
                "position": {
                    "x": self.position.x,
                    "y": self.position.y,
                    "z": self.position.z,
                    "system": self.position.system,
                    "galaxy": self.position.galaxy
                },
                "capabilities": {
                    cap.name.lower(): self.capabilities.get_capability(cap)
                    for cap in AgentCapability
                },
                "current_task": self.current_task.name if self.current_task else None,
                "queue_size": len(self.task_queue),
                "energy": self.energy,
                "computational_power": self.computational_power,
                "stats": {
                    "tasks_completed": self.tasks_completed,
                    "tasks_failed": self.tasks_failed,
                    "messages_sent": self.messages_sent,
                    "messages_received": self.messages_received,
                    "collaborations": self.collaborations
                }
            }


class InterstellarAgentNetwork:
    """星际智能体网络"""
    
    def __init__(self, network_id: str = "default"):
        self.id = network_id
        self.agents: Dict[str, InterstellarAgent] = {}
        self.tasks: Dict[str, InterstellarTask] = {}
        self.message_history: List[AgentMessage] = []
        
        # 网络拓扑
        self.neighbor_map: Dict[str, Set[str]] = defaultdict(set)
        
        # 路由表
        self.routing_table: Dict[str, Dict[str, float]] = {}
        
        # 协作调度器
        self.collaboration_scheduler: Optional[asyncio.Task] = None
        
        self.lock = threading.RLock()
    
    def register_agent(self, agent: InterstellarAgent):
        """注册智能体"""
        with self.lock:
            self.agents[agent.id] = agent
            self._update_topology(agent)
            logger.info(f"智能体 {agent.name} 已注册到网络")
    
    def unregister_agent(self, agent_id: str):
        """注销智能体"""
        with self.lock:
            if agent_id in self.agents:
                agent = self.agents[agent_id]
                agent.hibernate()
                del self.agents[agent_id]
                self._rebuild_topology()
                logger.info(f"智能体 {agent_id} 已注销")
    
    def _update_topology(self, agent: InterstellarAgent):
        """更新网络拓扑"""
        for other_id, other in self.agents.items():
            if other_id != agent.id:
                distance = agent.position.light_years_to(other.position)
                # 100光年内的智能体视为邻居
                if distance < 100:
                    self.neighbor_map[agent.id].add(other_id)
                    self.neighbor_map[other_id].add(agent.id)
                    
                    # 更新路由表
                    self._update_route(agent.id, other_id, distance)
    
    def _update_route(self, from_id: str, to_id: str, distance: float):
        """更新路由表"""
        if from_id not in self.routing_table:
            self.routing_table[from_id] = {}
        self.routing_table[from_id][to_id] = distance
    
    def _rebuild_topology(self):
        """重建网络拓扑"""
        self.neighbor_map.clear()
        self.routing_table.clear()
        for agent in self.agents.values():
            self._update_topology(agent)
    
    def find_nearest_agent(self, position: Position, 
                          min_capabilities: Dict[AgentCapability, float] = None,
                          exclude_ids: Set[str] = None) -> Optional[InterstellarAgent]:
        """查找最近的满足能力的智能体"""
        exclude_ids = exclude_ids or set()
        
        candidates = []
        for agent in self.agents.values():
            if agent.id in exclude_ids:
                continue
            if agent.state == AgentState.HIBERNATING:
                continue
            
            # 能力检查
            if min_capabilities:
                if not agent.capabilities.can_handle_task(min_capabilities):
                    continue
            
            distance = position.light_years_to(agent.position)
            candidates.append((distance, agent))
        
        if not candidates:
            return None
        
        candidates.sort(key=lambda x: x[0])
        return candidates[0][1]
    
    def find_agents_for_task(self, task: InterstellarTask, 
                            max_agents: int = 5) -> List[InterstellarAgent]:
        """为任务查找合适的智能体"""
        candidates = []
        
        for agent in self.agents.values():
            if agent.state == AgentState.HIBERNATING:
                continue
            
            if not agent.capabilities.can_handle_task(task.requirements):
                continue
            
            # 计算任务与智能体的匹配度
            distance = 0
            if task.target_position:
                distance = agent.position.light_years_to(task.target_position)
            
            # 能力匹配度
            capability_score = sum(
                agent.capabilities.get_capability(cap)
                for cap in task.requirements.keys()
            ) / len(task.requirements)
            
            # 可用性分数
            availability_score = 1.0 if not agent.current_task else 0.3
            
            # 综合评分
            total_score = capability_score * 0.5 + availability_score * 0.3 + (1 - distance/100) * 0.2
            
            candidates.append((total_score, agent))
        
        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_agents]]
    
    def create_task(self, name: str, description: str,
                   requirements: Dict[AgentCapability, float],
                   target_position: Position = None,
                   urgency: TaskUrgency = TaskUrgency.NORMAL,
                   deadline: float = 0) -> InterstellarTask:
        """创建星际任务"""
        task = InterstellarTask(
            name=name,
            description=description,
            requirements=requirements,
            target_position=target_position,
            urgency=urgency,
            deadline=deadline
        )
        
        with self.lock:
            self.tasks[task.id] = task
        
        logger.info(f"创建任务: {task.name} (ID: {task.id})")
        return task
    
    def dispatch_task(self, task: InterstellarTask) -> bool:
        """分发任务"""
        suitable_agents = self.find_agents_for_task(task)
        
        if not suitable_agents:
            logger.warning(f"找不到合适的智能体执行任务: {task.name}")
            return False
        
        # 选择最佳智能体
        best_agent = suitable_agents[0]
        success = best_agent.assign_task(task)
        
        if success:
            logger.info(f"任务 {task.name} 已分配给 {best_agent.name}")
        
        return success
    
    def broadcast_message(self, sender: InterstellarAgent, content: Any,
                         msg_type: str = "broadcast"):
        """广播消息"""
        with self.lock:
            message = AgentMessage(
                sender_id=sender.id,
                sender_position=Position(sender.position.x, sender.position.y, sender.position.z),
                recipient_id="*",  # 广播标识
                message_type=msg_type,
                content=content
            )
            
            # 发送给所有邻居
            neighbors = self.neighbor_map.get(sender.id, set())
            for neighbor_id in neighbors:
                if neighbor_id in self.agents:
                    self.agents[neighbor_id].receive_message(message)
            
            self.message_history.append(message)
            logger.debug(f"{sender.name} 广播消息到 {len(neighbors)} 个邻居")
    
    def route_message(self, from_id: str, to_id: str, message: AgentMessage) -> List[str]:
        """消息路由（返回路径）"""
        if from_id not in self.routing_table:
            return []
        
        # 简单的距离最优路由
        path = [from_id]
        current = from_id
        visited = {from_id}
        
        for _ in range(100):  # 最多100跳
            if current == to_id:
                return path
            
            # 找最近的下一跳
            next_hops = self.routing_table.get(current, {})
            candidates = [
                (dist, node) for node, dist in next_hops.items()
                if node not in visited
            ]
            
            if not candidates:
                break
            
            candidates.sort()
            _, next_node = candidates[0]
            
            path.append(next_node)
            visited.add(next_node)
            current = next_node
        
        return path if current == to_id else []
    
    def get_network_status(self) -> Dict[str, Any]:
        """获取网络状态"""
        with self.lock:
            total_tasks = len(self.tasks)
            active_agents = sum(
                1 for a in self.agents.values() 
                if a.state == AgentState.ACTIVE or a.state == AgentState.EXECUTING
            )
            
            return {
                "network_id": self.id,
                "total_agents": len(self.agents),
                "active_agents": active_agents,
                "total_tasks": total_tasks,
                "completed_tasks": sum(len(a.completed_tasks) for a in self.agents.values()),
                "total_messages": len(self.message_history),
                "neighbors_count": {
                    agent_id: len(neighbors)
                    for agent_id, neighbors in self.neighbor_map.items()
                }
            }
    
    def start_collaboration_scheduler(self):
        """启动协作调度器"""
        if self.collaboration_scheduler and not self.collaboration_scheduler.done():
            return
        
        async def scheduler_loop():
            while True:
                await asyncio.sleep(5)
                await self._collaboration_loop()
        
        self.collaboration_scheduler = asyncio.create_task(scheduler_loop())
        logger.info("协作调度器已启动")
    
    async def _collaboration_loop(self):
        """协作循环"""
        # 查找可以协作的任务
        high_priority_tasks = [
            t for t in self.tasks.values()
            if t.urgency == TaskUrgency.CRITICAL or t.urgency == TaskUrgency.HIGH
        ]
        
        for task in high_priority_tasks:
            # 检查是否有智能体可以处理
            suitable = self.find_agents_for_task(task, max_agents=3)
            if len(suitable) >= 2:
                # 可以形成协作
                logger.info(f"任务 {task.name} 可以由 {len(suitable)} 个智能体协作处理")


class InterstellarFederation:
    """星际智能体联邦 - 跨星际协作组织"""
    
    def __init__(self, federation_id: str):
        self.id = federation_id
        self.networks: Dict[str, InterstellarAgentNetwork] = {}
        self.federation_agents: Dict[str, InterstellarAgent] = {}
        
        # 联邦策略
        self.resource_sharing_policy = "balanced"  # balanced, greedy, generous
        self.task_allocation_strategy = "capability_based"  # capability_based, nearest, random
        
        # 联邦知识库
        self.federation_knowledge: Dict[str, Any] = {}
        
        self.lock = threading.RLock()
    
    def join_network(self, network: InterstellarAgentNetwork):
        """网络加入联邦"""
        with self.lock:
            self.networks[network.id] = network
            logger.info(f"网络 {network.id} 已加入联邦 {self.id}")
    
    def leave_network(self, network_id: str):
        """网络离开联邦"""
        with self.lock:
            if network_id in self.networks:
                del self.networks[network_id]
                logger.info(f"网络 {network_id} 已离开联邦")
    
    def federated_task_allocation(self, task: InterstellarTask) -> Optional[InterstellarAgent]:
        """联邦任务分配"""
        best_agent = None
        best_score = -1
        
        for network in self.networks.values():
            candidates = network.find_agents_for_task(task, max_agents=3)
            
            for agent in candidates:
                # 计算联邦级别的评分
                score = self._calculate_federated_score(agent, task)
                
                if score > best_score:
                    best_score = score
                    best_agent = agent
        
        if best_agent:
            logger.info(f"联邦任务分配: {task.name} -> {best_agent.name}")
        
        return best_agent
    
    def _calculate_federated_score(self, agent: InterstellarAgent, 
                                   task: InterstellarTask) -> float:
        """计算联邦级别的评分"""
        # 基础能力评分
        capability_score = sum(
            agent.capabilities.get_capability(cap)
            for cap in task.requirements.keys()
        ) / max(1, len(task.requirements))
        
        # 负载评分
        load_score = 1.0 if not agent.current_task else 0.5
        
        # 能量评分
        energy_score = agent.energy / 100.0
        
        # 协作历史评分
        collaboration_score = min(1.0, agent.collaborations / 10.0)
        
        return capability_score * 0.4 + load_score * 0.2 + energy_score * 0.2 + collaboration_score * 0.2
    
    def cross_network_collaboration(self, task: InterstellarTask,
                                   source_network_id: str) -> bool:
        """跨网络协作"""
        if source_network_id not in self.networks:
            return False
        
        source_network = self.networks[source_network_id]
        
        # 尝试在不同网络中找到合适的智能体
        other_networks = [n for n in self.networks.keys() if n != source_network_id]
        
        for network_id in other_networks:
            network = self.networks[network_id]
            candidates = network.find_agents_for_task(task, max_agents=2)
            
            if candidates:
                # 建立跨网络协作
                source_agents = source_network.find_agents_for_task(task, max_agents=2)
                
                if source_agents:
                    logger.info(f"跨网络协作建立: {source_network_id} <-> {network_id}")
                    return True
        
        return False


# 演示代码
def demo():
    """演示星际智能体系统"""
    logger.info("=" * 60)
    logger.info("星际智能体系统演示")
    logger.info("=" * 60)
    
    # 创建智能体网络
    network = InterstellarAgentNetwork("alpha-centauri-network")
    
    # 创建智能体
    capabilities_navigator = AgentCapabilityProfile(
        navigation=0.9, communication=0.7, analysis=0.6,
        decision=0.7, execution=0.8, learning=0.6
    )
    
    capabilities_analyzer = AgentCapabilityProfile(
        navigation=0.4, communication=0.8, analysis=0.9,
        decision=0.8, execution=0.5, learning=0.9
    )
    
    capabilities_executor = AgentCapabilityProfile(
        navigation=0.6, communication=0.6, analysis=0.5,
        decision=0.6, execution=0.9, learning=0.7
    )
    
    agent1 = InterstellarAgent(
        agent_id="agent-001",
        position=Position(0, 0, 0, "Sol", "MilkyWay"),
        capabilities=capabilities_navigator,
        name="Navigator-1"
    )
    
    agent2 = InterstellarAgent(
        agent_id="agent-002",
        position=Position(4, 2, 0, "Alpha-Centauri", "MilkyWay"),
        capabilities=capabilities_analyzer,
        name="Analyzer-1"
    )
    
    agent3 = InterstellarAgent(
        agent_id="agent-003",
        position=Position(2, 5, 1, "Proxima", "MilkyWay"),
        capabilities=capabilities_executor,
        name="Executor-1"
    )
    
    # 注册智能体
    for agent in [agent1, agent2, agent3]:
        network.register_agent(agent)
        agent.awaken()
    
    # 创建任务
    task = network.create_task(
        name="星际探测任务",
        description="探索未知星域并收集数据",
        requirements={
            AgentCapability.NAVIGATION: 0.7,
            AgentCapability.ANALYSIS: 0.6,
            AgentCapability.EXECUTION: 0.5
        },
        target_position=Position(10, 10, 5, "Unknown"),
        urgency=TaskUrgency.HIGH,
        deadline=time.time() + 86400
    )
    
    # 分发任务
    network.dispatch_task(task)
    
    # 智能体协作
    agent1.request_collaboration(agent2, task)
    
    # 网络状态
    status = network.get_network_status()
    logger.info(f"网络状态: {json.dumps(status, indent=2, default=str)}")
    
    # 联邦演示
    federation = InterstellarFederation("milky-way-federation")
    federation.join_network(network)
    
    federated_task = network.create_task(
        name="联邦探测任务",
        description="需要跨网络协作的探测任务",
        requirements={
            AgentCapability.NAVIGATION: 0.8,
            AgentCapability.COMMUNICATION: 0.8,
            AgentCapability.COORDINATION: 0.7
        }
    )
    
    federation.federated_task_allocation(federated_task)
    
    logger.info("=" * 60)
    logger.info("演示完成")
    logger.info("=" * 60)


if __name__ == "__main__":
    demo()