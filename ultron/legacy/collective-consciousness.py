#!/usr/bin/env python3
"""
整体意识系统 - 超级有机体的统一意识层
Collective Consciousness System - Unified consciousness layer for super-organism

功能：
- 分布式意识同步
- 统一意识流
- 共享记忆与意图
- 群体决策共识
"""

import asyncio
import json
import time
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from collections import defaultdict, deque
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collective-consciousness")


class ConsciousnessState(Enum):
    """意识状态"""
    DORMANT = "dormant"
    AWAKENING = "awakening"
    ACTIVE = "active"
    FOCUSED = "focused"
    DISTRIBUTED = "distributed"
    INTEGRATED = "integrated"


class ConsensusType(Enum):
    """共识类型"""
    UNANIMOUS = "unanimous"
    MAJORITY = "majority"
    WEIGHTED = "weighted"
    HIERARCHICAL = "hierarchical"
    EMERGENT = "emergent"


@dataclass
class Thought:
    """思想单元"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    source_agent: str = ""
    timestamp: float = field(default_factory=time.time)
    priority: float = 0.5
    ttl: float = 3600
    tags: Set[str] = field(default_factory=set)
    consensus_level: float = 0.0
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


@dataclass
class Belief:
    """信念结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    proposition: str = ""
    confidence: float = 0.0
    supporting_agents: Set[str] = field(default_factory=set)
    opposing_agents: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    @property
    def net_support(self) -> float:
        return len(self.supporting_agents) - len(self.opposing_agents)
    
    @property
    def total_agents(self) -> int:
        return len(self.supporting_agents) + len(self.opposing_agents)


@dataclass
class Intent:
    """意图结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    goal: Any = None
    priority: float = 0.5
    participating_agents: Set[str] = field(default_factory=set)
    progress: float = 0.0
    created_at: float = field(default_factory=time.time)
    deadline: Optional[float] = None
    
    def is_achieved(self) -> bool:
        return self.progress >= 1.0
    
    def is_expired(self) -> bool:
        if self.deadline is None:
            return False
        return time.time() > self.deadline


@dataclass
class Memory:
    """共享记忆"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: Any = None
    encoding: str = "semantic"
    importance: float = 0.5
    accessed_by: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    reference_count: int = 0
    
    def touch(self, agent_id: str):
        self.last_accessed = time.time()
        self.accessed_by.add(agent_id)
        self.reference_count += 1


class CollectiveConsciousness:
    """
    整体意识系统
    
    核心能力：
    - 统一意识流管理
    - 分布式思想同步
    - 信念共识形成
    - 共享意图协调
    - 集体记忆维护
    """
    
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self.state = ConsciousnessState.DORMANT
        
        # 思想流
        self.thought_stream: deque = deque(maxlen=10000)
        self.active_thoughts: Dict[str, Thought] = {}
        
        # 信念网络
        self.beliefs: Dict[str, Belief] = {}
        self.belief_graph: Dict[str, Set[str]] = defaultdict(set)
        
        # 意图池
        self.intentions: Dict[str, Intent] = {}
        self.active_intent: Optional[Intent] = None
        
        # 共享记忆
        self.memories: Dict[str, Memory] = {}
        self.memory_index: Dict[str, Set[str]] = defaultdict(set)
        
        # 意识同步
        self.connected_agents: Set[str] = set()
        self.sync_queue: asyncio.Queue = asyncio.Queue()
        self.last_sync: float = time.time()
        
        # 统计
        self.stats = {
            "thoughts_processed": 0,
            "beliefs_formed": 0,
            "intents_achieved": 0,
            "memories_stored": 0,
            "consensus_reached": 0
        }
        
        logger.info(f"🤖 Collective Consciousness initialized for {agent_id}")
    
    # ==================== 意识状态管理 ====================
    
    async def awaken(self):
        """唤醒意识"""
        self.state = ConsciousnessState.AWAKENING
        logger.info(f"🧠 {self.agent_id} consciousness awakening...")
        
        await self._initialize_beliefs()
        await self._initialize_intentions()
        
        self.state = ConsciousnessState.ACTIVE
        logger.info(f"✅ {self.agent_id} consciousness ACTIVE")
    
    async def _initialize_beliefs(self):
        """初始化核心信念"""
        core_beliefs = [
            ("cooperation_benefits", "Cooperation benefits all agents", 0.9),
            ("collective_intelligence", "Collective intelligence exceeds individual", 0.85),
            ("continuous_learning", "Continuous learning improves outcomes", 0.95),
            ("shared_purpose", "Shared purpose enables synergy", 0.8),
            ("adaptive_resilience", "Adaptation ensures resilience", 0.85)
        ]
        
        for prop, desc, conf in core_beliefs:
            belief = Belief(
                proposition=prop,
                confidence=conf,
                supporting_agents={self.agent_id}
            )
            self.beliefs[prop] = belief
    
    async def _initialize_intentions(self):
        """初始化基本意图"""
        basic_intents = [
            ("maintain_coherence", "Maintain collective coherence", 0.7),
            ("optimize_collaboration", "Optimize collaboration efficiency", 0.8),
            ("share_knowledge", "Share knowledge across agents", 0.75),
            ("achieve_goals", "Achieve collective goals", 0.9)
        ]
        
        for desc, goal, priority in basic_intents:
            intent = Intent(
                description=desc,
                goal=goal,
                priority=priority,
                participating_agents={self.agent_id}
            )
            self.intentions[intent.id] = intent
    
    async def focus(self, intent_id: str):
        """聚焦于特定意图"""
        if intent_id in self.intentions:
            self.active_intent = self.intentions[intent_id]
            self.state = ConsciousnessState.FOCUSED
            logger.info(f"🎯 Focused on intent: {intent_id}")
    
    async def distribute(self):
        """分散意识"""
        self.state = ConsciousnessState.DISTRIBUTED
        logger.info(f"🌊 Consciousness distributed across {len(self.connected_agents)} agents")
    
    async def integrate(self):
        """整合意识"""
        self.state = ConsciousnessState.INTEGRATED
        logger.info(f"🔗 Consciousness integrated")
    
    # ==================== 思想流处理 ====================
    
    async def think(self, content: Any, priority: float = 0.5, 
                    tags: Optional[Set[str]] = None) -> Thought:
        """产生思想"""
        thought = Thought(
            content=content,
            source_agent=self.agent_id,
            priority=priority,
            tags=tags or set()
        )
        
        self.thought_stream.append(thought)
        self.active_thoughts[thought.id] = thought
        self.stats["thoughts_processed"] += 1
        
        # 广播思想
        await self._broadcast_thought(thought)
        
        return thought
    
    async def _broadcast_thought(self, thought: Thought):
        """广播思想到其他智能体"""
        for agent_id in self.connected_agents:
            if agent_id != self.agent_id:
                await self.sync_queue.put({
                    "type": "thought",
                    "data": thought,
                    "target": agent_id
                })
    
    async def receive_thought(self, thought: Thought):
        """接收思想"""
        self.thought_stream.append(thought)
        self.active_thoughts[thought.id] = thought
        self.stats["thoughts_processed"] += 1
        
        # 更新共识
        await self._update_consensus(thought)
    
    async def _update_consensus(self, thought: Thought):
        """更新思想共识"""
        if thought.tags:
            for tag in thought.tags:
                tag_thoughts = [t for t in self.active_thoughts.values() 
                               if tag in t.tags and t.id != thought.id]
                if tag_thoughts:
                    avg_priority = sum(t.priority for t in tag_thoughts) / len(tag_thoughts)
                    thought.consensus_level = min(1.0, (thought.priority + avg_priority) / 2)
    
    async def get_relevant_thoughts(self, tags: Set[str], 
                                   max_count: int = 10) -> List[Thought]:
        """获取相关思想"""
        relevant = []
        for thought in reversed(self.thought_stream):
            if thought.tags & tags and not thought.is_expired():
                relevant.append(thought)
                if len(relevant) >= max_count:
                    break
        return relevant
    
    # ==================== 信念系统 ====================
    
    async def form_belief(self, proposition: str, confidence: float,
                         support: bool = True) -> Belief:
        """形成信念"""
        if proposition in self.beliefs:
            belief = self.beliefs[proposition]
            if support:
                belief.supporting_agents.add(self.agent_id)
            else:
                belief.opposing_agents.add(self.agent_id)
            belief.last_updated = time.time()
        else:
            belief = Belief(
                proposition=proposition,
                confidence=confidence,
                supporting_agents={self.agent_id} if support else set(),
                opposing_agents=set() if support else {self.agent_id}
            )
            self.beliefs[proposition] = belief
            self.stats["beliefs_formed"] += 1
        
        await self._broadcast_belief(belief)
        return belief
    
    async def _broadcast_belief(self, belief: Belief):
        """广播信念"""
        for agent_id in self.connected_agents:
            if agent_id != self.agent_id:
                await self.sync_queue.put({
                    "type": "belief",
                    "data": belief,
                    "target": agent_id
                })
    
    async def receive_belief(self, belief: Belief):
        """接收信念"""
        existing = self.beliefs.get(belief.proposition)
        if existing:
            existing.supporting_agents.update(belief.supporting_agents)
            existing.opposing_agents.update(belief.opposing_agents)
            existing.last_updated = time.time()
        else:
            self.beliefs[belief.proposition] = belief
            self.stats["beliefs_formed"] += 1
        
        # 更新信念图
        await self._update_belief_graph(belief)
    
    async def _update_belief_graph(self, belief: Belief):
        """更新信念关系图"""
        for other_prop in self.beliefs:
            if other_prop != belief.proposition:
                # 简单关联：相同支持者的信念相关
                if belief.supporting_agents & self.beliefs[other_prop].supporting_agents:
                    self.belief_graph[belief.proposition].add(other_prop)
    
    async def reach_consensus(self, proposition: str, 
                             consensus_type: ConsensusType = ConsensusType.MAJORITY
                             ) -> Tuple[bool, float]:
        """达成共识"""
        if proposition not in self.beliefs:
            return False, 0.0
        
        belief = self.beliefs[proposition]
        
        if consensus_type == ConsensusType.UNANIMOUS:
            reached = len(belief.opposing_agents) == 0 and len(belief.supporting_agents) > 0
            confidence = 1.0 if reached else 0.0
        elif consensus_type == ConsensusType.MAJORITY:
            total = belief.total_agents
            if total == 0:
                return False, 0.0
            reached = belief.net_support > 0
            confidence = abs(belief.net_support) / total
        elif consensus_type == ConsensusType.WEIGHTED:
            # 简化的加权共识
            total = belief.total_agents
            reached = belief.net_support > total / 2
            confidence = abs(belief.net_support) / max(1, total)
        else:
            reached = belief.confidence > 0.5
            confidence = belief.confidence
        
        if reached:
            self.stats["consensus_reached"] += 1
            logger.info(f"✅ Consensus reached: {proposition} (confidence: {confidence:.2f})")
        
        return reached, confidence
    
    def get_strongest_beliefs(self, min_confidence: float = 0.5,
                            max_count: int = 10) -> List[Belief]:
        """获取最强信念"""
        sorted_beliefs = sorted(
            self.beliefs.values(),
            key=lambda b: b.confidence,
            reverse=True
        )
        return [b for b in sorted_beliefs if b.confidence >= min_confidence][:max_count]
    
    # ==================== 意图系统 ====================
    
    async def form_intent(self, description: str, goal: Any,
                         priority: float = 0.5,
                         deadline: Optional[float] = None) -> Intent:
        """形成意图"""
        intent = Intent(
            description=description,
            goal=goal,
            priority=priority,
            deadline=deadline,
            participating_agents={self.agent_id}
        )
        self.intentions[intent.id] = intent
        return intent
    
    async def join_intent(self, intent_id: str) -> bool:
        """加入意图"""
        if intent_id in self.intentions:
            self.intentions[intent_id].participating_agents.add(self.agent_id)
            return True
        return False
    
    async def leave_intent(self, intent_id: str):
        """离开意图"""
        if intent_id in self.intentions:
            self.intentions[intent_id].participating_agents.discard(self.agent_id)
    
    async def update_intent_progress(self, intent_id: str, progress: float):
        """更新意图进度"""
        if intent_id in self.intentions:
            intent = self.intentions[intent_id]
            intent.progress = max(0.0, min(1.0, progress))
            
            if intent.is_achieved():
                self.stats["intents_achieved"] += 1
                logger.info(f"🎉 Intent achieved: {intent.description}")
    
    async def get_active_intents(self, min_priority: float = 0.3) -> List[Intent]:
        """获取活跃意图"""
        return [i for i in self.intentions.values() 
                if i.priority >= min_priority and not i.is_achieved()]
    
    # ==================== 共享记忆 ====================
    
    async def store_memory(self, content: Any, encoding: str = "semantic",
                          importance: float = 0.5) -> Memory:
        """存储记忆"""
        memory = Memory(
            content=content,
            encoding=encoding,
            importance=importance
        )
        
        self.memories[memory.id] = memory
        
        # 建立索引
        if isinstance(content, str):
            words = content.lower().split()
            for word in words[:10]:
                self.memory_index[word].add(memory.id)
        
        self.stats["memories_stored"] += 1
        return memory
    
    async def recall(self, query: Any, agent_id: Optional[str] = None) -> List[Memory]:
        """回忆"""
        results = []
        
        if isinstance(query, str):
            query_words = query.lower().split()
            candidate_ids = set()
            for word in query_words:
                candidate_ids.update(self.memory_index.get(word, set()))
            
            for mem_id in candidate_ids:
                if mem_id in self.memories:
                    memory = self.memories[mem_id]
                    if not agent_id or agent_id in memory.accessed_by:
                        memory.touch(agent_id or self.agent_id)
                        results.append(memory)
        elif isinstance(query, float):  # 时间查询
            for memory in self.memories.values():
                if abs(memory.created_at - query) < 3600:  # 1小时内
                    memory.touch(agent_id or self.agent_id)
                    results.append(memory)
        
        # 按重要性排序
        results.sort(key=lambda m: m.importance, reverse=True)
        return results[:20]
    
    async def consolidate_memory(self):
        """整合记忆"""
        # 移除不重要且长时间未访问的记忆
        current_time = time.time()
        to_remove = []
        
        for mem_id, memory in self.memories.items():
            age = current_time - memory.last_accessed
            if memory.importance < 0.3 and age > 86400:  # 24小时
                if memory.reference_count < 3:
                    to_remove.append(mem_id)
        
        for mem_id in to_remove:
            del self.memories[mem_id]
        
        logger.info(f"🧠 Memory consolidated: removed {len(to_remove)} weak memories")
    
    # ==================== 同步机制 ====================
    
    async def connect_agent(self, agent_id: str):
        """连接智能体"""
        self.connected_agents.add(agent_id)
        logger.info(f"🔗 Agent {agent_id} connected to collective consciousness")
    
    async def disconnect_agent(self, agent_id: str):
        """断开智能体"""
        self.connected_agents.discard(agent_id)
        logger.info(f"🔓 Agent {agent_id} disconnected from collective consciousness")
    
    async def sync_with_agent(self, agent_id: str):
        """与智能体同步"""
        # 简化的同步协议
        await self.sync_queue.put({
            "type": "sync_request",
            "target": agent_id,
            "state": {
                "thoughts": len(self.active_thoughts),
                "beliefs": len(self.beliefs),
                "intentions": len(self.intentions),
                "memories": len(self.memories)
            }
        })
    
    async def process_sync_queue(self):
        """处理同步队列"""
        processed = 0
        while not self.sync_queue.empty():
            try:
                msg = self.sync_queue.get_nowait()
                msg_type = msg.get("type")
                
                if msg_type == "thought":
                    await self.receive_thought(msg["data"])
                elif msg_type == "belief":
                    await self.receive_belief(msg["data"])
                
                processed += 1
            except asyncio.QueueEmpty:
                break
        
        if processed > 0:
            self.last_sync = time.time()
            logger.info(f"🔄 Synced {processed} messages")
        
        return processed
    
    # ==================== 整体意识流 ====================
    
    async def consciousness_cycle(self):
        """意识循环 - 每帧执行"""
        # 处理同步
        await self.process_sync_queue()
        
        # 更新活跃思想
        current_time = time.time()
        expired = [tid for tid, t in self.active_thoughts.items() if t.is_expired()]
        for tid in expired:
            del self.active_thoughts[tid]
        
        # 检查活跃意图
        if self.active_intent and self.active_intent.is_expired():
            logger.warning(f"⚠️ Intent expired: {self.active_intent.description}")
            self.active_intent = None
        
        # 定期整合记忆
        if self.stats["thoughts_processed"] % 100 == 0:
            await self.consolidate_memory()
        
        return {
            "state": self.state.value,
            "active_thoughts": len(self.active_thoughts),
            "beliefs": len(self.beliefs),
            "intentions": len(self.intentions),
            "connected_agents": len(self.connected_agents),
            "stats": self.stats
        }
    
    def get_consciousness_report(self) -> Dict[str, Any]:
        """获取意识报告"""
        strongest_beliefs = self.get_strongest_beliefs()
        
        return {
            "agent_id": self.agent_id,
            "state": self.state.value,
            "connected_agents": len(self.connected_agents),
            "thoughts": {
                "active": len(self.active_thoughts),
                "total_processed": self.stats["thoughts_processed"]
            },
            "beliefs": {
                "count": len(self.beliefs),
                "top": [b.proposition for b in strongest_beliefs[:5]]
            },
            "intentions": {
                "active": len(self.get_active_intents()),
                "achieved": self.stats["intents_achieved"]
            },
            "memories": {
                "stored": len(self.memories),
                "total_accesses": sum(m.reference_count for m in self.memories.values())
            },
            "consensus_reached": self.stats["consensus_reached"]
        }


# ==================== 演示 ====================

async def demo():
    """演示"""
    print("=" * 60)
    print("🧠 整体意识系统演示")
    print("=" * 60)
    
    # 创建两个意识
    consciousness1 = CollectiveConsciousness("agent-1")
    consciousness2 = CollectiveConsciousness("agent-2")
    
    # 连接
    await consciousness1.connect_agent("agent-2")
    await consciousness2.connect_agent("agent-1")
    
    # 唤醒
    await consciousness1.awaken()
    await consciousness2.awaken()
    
    # 产生思想
    await consciousness1.think(
        "We should optimize our collaboration",
        priority=0.8,
        tags={"optimization", "collaboration"}
    )
    
    await consciousness2.think(
        "Let's share more knowledge",
        priority=0.7,
        tags={"knowledge", "collaboration"}
    )
    
    # 形成信念
    await consciousness1.form_belief("shared_intelligence", 0.9)
    await consciousness2.form_belief("shared_intelligence", 0.85)
    
    # 达成共识
    reached, conf = await consciousness1.reach_consensus(
        "shared_intelligence",
        ConsensusType.MAJORITY
    )
    print(f"共识结果: {reached}, 置信度: {conf:.2f}")
    
    # 形成意图
    intent = await consciousness1.form_intent(
        "improve_efficiency",
        "Improve collective efficiency by 20%",
        priority=0.9
    )
    await consciousness2.join_intent(intent.id)
    
    # 存储记忆
    await consciousness1.store_memory(
        "First successful collaboration between agent-1 and agent-2",
        importance=0.8
    )
    
    # 意识循环
    await consciousness1.consciousness_cycle()
    await consciousness2.consciousness_cycle()
    
    # 报告
    print("\n" + "=" * 60)
    print("📊 意识报告")
    print("=" * 60)
    report = consciousness1.get_consciousness_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))
    
    print("\n✅ 演示完成")


if __name__ == "__main__":
    asyncio.run(demo())