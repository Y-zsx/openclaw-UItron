#!/usr/bin/env python3
"""
实时协作引擎 - 第38世产出
实时消息同步、协作状态管理、跨维度数据交换

功能：
1. 实时消息同步 - WebSocket消息推送、消息队列、消息确认
2. 协作状态管理 - 分布式状态同步、冲突解决、状态版本控制
3. 跨维度数据交换 - 多协议转换、格式适配、数据路由

作者: 奥创 (Ultron)
版本: 1.0
"""

import asyncio
import json
import time
import hashlib
import uuid
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
from collections import defaultdict
from datetime import datetime
import threading

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RealTimeCollaboration")


class MessageType(Enum):
    """消息类型"""
    SYNC = "sync"                    # 同步消息
    BROADCAST = "broadcast"          # 广播消息
    DIRECT = "direct"                # 直接消息
    ACK = "ack"                      # 确认消息
    HEARTBEAT = "heartbeat"          # 心跳
    STATE_UPDATE = "state_update"    # 状态更新
    STATE_REQUEST = "state_request"  # 状态请求
    STATE_RESPONSE = "state_response" # 状态响应


class CollaborationState(Enum):
    """协作状态"""
    IDLE = "idle"
    ACTIVE = "active"
    SYNCING = "syncing"
    CONFLICT = "conflict"
    ERROR = "error"


class SyncStrategy(Enum):
    """同步策略"""
    EAGER = "eager"          # 立即同步
    LAZY = "lazy"            # 延迟同步
    CRDT = "crdt"            # CRDT最终一致
    THREE_WAY = "three_way"  # 三方合并


@dataclass
class Message:
    """消息结构"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: str = MessageType.SYNC.value
    sender: str = ""
    receiver: str = ""
    channel: str = "default"
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    version: int = 1
    ack_required: bool = True
    ttl: int = 300  # 5分钟TTL

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict) -> 'Message':
        return cls(**data)

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl


@dataclass
class StateVersion:
    """状态版本"""
    version: int
    state: Dict[str, Any]
    timestamp: float
    actor: str
    checksum: str


@dataclass
class Channel:
    """协作通道"""
    id: str
    name: str
    members: Set[str] = field(default_factory=set)
    state: Dict[str, Any] = field(default_factory=dict)
    versions: List[StateVersion] = field(default_factory=list)
    sync_strategy: str = SyncStrategy.EAGER.value
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


class RealTimeMessageSync:
    """实时消息同步引擎"""

    def __init__(self):
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.pending_acks: Dict[str, asyncio.Future] = {}
        self.subscribers: Dict[str, Set[Callable]] = defaultdict(set)
        self.message_history: Dict[str, List[Message]] = defaultdict(list)
        self.max_history = 1000
        self.running = False

    async def publish(self, message: Message) -> str:
        """发布消息"""
        # 存储到历史
        channel = message.channel
        self.message_history[channel].append(message)
        
        # 限制历史大小
        if len(self.message_history[channel]) > self.max_history:
            self.message_history[channel] = self.message_history[channel][-self.max_history:]

        # 通知订阅者
        for callback in self.subscribers.get(channel, set()):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")

        # 如果需要ACK，添加等待
        if message.ack_required:
            future = asyncio.Future()
            self.pending_acks[message.id] = future
            
            # 设置超时
            try:
                await asyncio.wait_for(future, timeout=message.ttl)
            except asyncio.TimeoutError:
                logger.warning(f"Message {message.id} ack timeout")
                self.pending_acks.pop(message.id, None)

        return message.id

    async def subscribe(self, channel: str, callback: Callable):
        """订阅频道"""
        self.subscribers[channel].add(callback)

    async def unsubscribe(self, channel: str, callback: Callable):
        """取消订阅"""
        self.subscribers[channel].discard(callback)

    async def acknowledge(self, message_id: str, success: bool = True):
        """确认消息"""
        future = self.pending_acks.pop(message_id, None)
        if future and not future.done():
            future.set_result(success)

    async def broadcast(self, channel: str, payload: Dict, sender: str) -> str:
        """广播消息"""
        message = Message(
            type=MessageType.BROADCAST.value,
            sender=sender,
            channel=channel,
            payload=payload
        )
        return await self.publish(message)

    async def send_direct(self, receiver: str, payload: Dict, sender: str) -> str:
        """直接发送消息"""
        message = Message(
            type=MessageType.DIRECT.value,
            sender=sender,
            receiver=receiver,
            payload=payload
        )
        return await self.publish(message)

    def get_history(self, channel: str, limit: int = 100) -> List[Message]:
        """获取消息历史"""
        history = self.message_history.get(channel, [])
        return history[-limit:]

    async def start(self):
        """启动消息同步"""
        self.running = True
        logger.info("Real-time message sync started")

    async def stop(self):
        """停止消息同步"""
        self.running = False
        logger.info("Real-time message sync stopped")


class CollaborationStateManager:
    """协作状态管理器"""

    def __init__(self):
        self.channels: Dict[str, Channel] = {}
        self.local_state: Dict[str, Any] = {}
        self.version_vector: Dict[str, int] = defaultdict(int)
        self.conflict_resolvers: Dict[str, Callable] = {}
        self.state_listeners: Set[Callable] = set()

    def create_channel(self, channel_id: str, name: str, 
                      sync_strategy: SyncStrategy = SyncStrategy.EAGER) -> Channel:
        """创建通道"""
        channel = Channel(
            id=channel_id,
            name=name,
            sync_strategy=sync_strategy.value
        )
        self.channels[channel_id] = channel
        logger.info(f"Created channel: {name}")
        return channel

    def join_channel(self, channel_id: str, member: str):
        """加入通道"""
        if channel_id in self.channels:
            self.channels[channel_id].members.add(member)
            logger.info(f"Member {member} joined channel {channel_id}")

    def leave_channel(self, channel_id: str, member: str):
        """离开通道"""
        if channel_id in self.channels:
            self.channels[channel_id].members.discard(member)
            logger.info(f"Member {member} left channel {channel_id}")

    def update_state(self, channel_id: str, state: Dict[str, Any], 
                    actor: str, expected_version: Optional[int] = None) -> bool:
        """更新状态"""
        if channel_id not in self.channels:
            logger.error(f"Channel {channel_id} not found")
            return False

        channel = self.channels[channel_id]
        
        # 版本检查
        current_version = self.version_vector.get(channel_id, 0)
        if expected_version is not None and expected_version != current_version:
            logger.warning(f"Version mismatch: expected {expected_version}, got {current_version}")
            
            # 尝试冲突解决
            if channel.sync_strategy == SyncStrategy.CRDT.value:
                return self._merge_state_crdt(channel, state, actor)
            elif channel.sync_strategy == SyncStrategy.THREE_WAY.value:
                return self._merge_state_three_way(channel, state, actor, expected_version)
        
        # 更新版本
        self.version_vector[channel_id] = current_version + 1
        version = self.version_vector[channel_id]
        
        # 创建版本记录
        state_version = StateVersion(
            version=version,
            state=state.copy(),
            timestamp=time.time(),
            actor=actor,
            checksum=self._compute_checksum(state)
        )
        
        # 更新通道状态
        channel.state = state.copy()
        channel.versions.append(state_version)
        channel.updated_at = time.time()
        
        # 限制版本历史
        if len(channel.versions) > 100:
            channel.versions = channel.versions[-100:]

        # 通知监听器
        for listener in self.state_listeners:
            try:
                listener(channel_id, state, version)
            except Exception as e:
                logger.error(f"State listener error: {e}")

        logger.info(f"State updated for channel {channel_id}, version {version}")
        return True

    def _compute_checksum(self, state: Dict) -> str:
        """计算状态校验和"""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.md5(state_str.encode()).hexdigest()

    def _merge_state_crdt(self, channel: Channel, new_state: Dict, actor: str) -> bool:
        """CRDT合并策略"""
        # 简单的LWW (Last-Writer-Wins) 合并
        current_state = channel.state.copy()
        for key, value in new_state.items():
            # 对于字典类型，递归合并
            if isinstance(value, dict) and key in current_state:
                current_state[key] = {**current_state[key], **value}
            else:
                current_state[key] = value
        
        return self.update_state(channel.id, current_state, actor)

    def _merge_state_three_way(self, channel: Channel, new_state: Dict, 
                               actor: str, expected_version: int) -> bool:
        """三方合并策略"""
        # 找到共同祖先
        ancestor = None
        for v in channel.versions:
            if v.version == expected_version:
                ancestor = v.state
                break
        
        if ancestor is None:
            # 无法找到祖先，直接覆盖
            return self.update_state(channel.id, new_state, actor)

        # 三方合并
        current_state = channel.state
        
        # 简单策略：合并所有键，冲突时用最新值
        merged = ancestor.copy()
        
        # 从祖先到当前状态的变化
        for key in current_state:
            if key not in new_state and key in ancestor:
                merged[key] = current_state[key]
        
        # 新状态的变化
        for key, value in new_state.items():
            merged[key] = value
        
        return self.update_state(channel.id, merged, actor)

    def get_state(self, channel_id: str) -> Optional[Dict]:
        """获取状态"""
        if channel_id in self.channels:
            return self.channels[channel_id].state.copy()
        return None

    def get_version(self, channel_id: str) -> int:
        """获取版本号"""
        return self.version_vector.get(channel_id, 0)

    def get_history(self, channel_id: str, limit: int = 10) -> List[StateVersion]:
        """获取版本历史"""
        if channel_id in self.channels:
            versions = self.channels[channel_id].versions
            return versions[-limit:]
        return []

    def add_state_listener(self, listener: Callable):
        """添加状态监听器"""
        self.state_listeners.add(listener)

    def resolve_conflict(self, channel_id: str, resolver: Callable):
        """注册冲突解决器"""
        self.conflict_resolvers[channel_id] = resolver


class CrossDimensionalDataExchange:
    """跨维度数据交换引擎"""

    def __init__(self):
        self.protocol_adapters: Dict[str, Any] = {}
        self.format_converters: Dict[str, Callable] = {}
        self.data_routes: Dict[str, List[str]] = defaultdict(list)
        self.data_transformers: Dict[str, Callable] = {}
        self.exchange_history: List[Dict] = []
        self.max_history = 500

    def register_protocol_adapter(self, protocol: str, adapter: Any):
        """注册协议适配器"""
        self.protocol_adapters[protocol] = adapter
        logger.info(f"Registered protocol adapter: {protocol}")

    def register_format_converter(self, format_from: str, format_to: str, 
                                  converter: Callable):
        """注册格式转换器"""
        key = f"{format_from}_to_{format_to}"
        self.format_converters[key] = converter

    def add_route(self, source: str, destination: str, 
                 transformer: Optional[Callable] = None):
        """添加数据路由"""
        self.data_routes[source].append(destination)
        if transformer:
            self.data_transformers[f"{source}_to_{destination}"] = transformer
        logger.info(f"Added route: {source} -> {destination}")

    async def send_data(self, source: str, destination: str, 
                       data: Any, format_hint: Optional[str] = None) -> bool:
        """发送数据"""
        try:
            # 格式转换
            if format_hint:
                converted = await self._convert_format(data, format_hint)
            else:
                converted = data

            # 数据转换
            transform_key = f"{source}_to_{destination}"
            if transform_key in self.data_transformers:
                converted = self.data_transformers[transform_key](converted)

            # 使用目标协议适配器发送
            if destination in self.protocol_adapters:
                adapter = self.protocol_adapters[destination]
                if hasattr(adapter, 'send'):
                    await adapter.send(converted)

            # 记录历史
            self._record_exchange(source, destination, data, converted)
            
            logger.info(f"Data sent from {source} to {destination}")
            return True

        except Exception as e:
            logger.error(f"Data exchange error: {e}")
            return False

    async def _convert_format(self, data: Any, target_format: str) -> Any:
        """格式转换"""
        # 检测当前格式
        current_format = self._detect_format(data)
        
        if current_format == target_format:
            return data

        converter_key = f"{current_format}_to_{target_format}"
        if converter_key in self.format_converters:
            converter = self.format_converters[converter_key]
            if asyncio.iscoroutinefunction(converter):
                return await converter(data)
            return converter(data)
        
        # 默认尝试JSON序列化
        return json.dumps(data) if not isinstance(data, str) else data

    def _detect_format(self, data: Any) -> str:
        """检测数据格式"""
        if isinstance(data, dict):
            return "json"
        elif isinstance(data, str):
            try:
                json.loads(data)
                return "json"
            except:
                return "text"
        elif isinstance(data, bytes):
            return "binary"
        return "unknown"

    async def broadcast_data(self, source: str, data: Any) -> Dict[str, bool]:
        """广播数据到所有路由"""
        results = {}
        for destination in self.data_routes.get(source, []):
            success = await self.send_data(source, destination, data)
            results[destination] = success
        return results

    def _record_exchange(self, source: str, destination: str, 
                        original: Any, transformed: Any):
        """记录交换历史"""
        record = {
            "timestamp": time.time(),
            "source": source,
            "destination": destination,
            "original_type": type(original).__name__,
            "transformed_type": type(transformed).__name__
        }
        self.exchange_history.append(record)
        
        if len(self.exchange_history) > self.max_history:
            self.exchange_history = self.exchange_history[-self.max_history:]

    def get_exchange_stats(self) -> Dict:
        """获取交换统计"""
        if not self.exchange_history:
            return {"total": 0, "by_source": {}, "by_destination": {}}

        by_source = defaultdict(int)
        by_destination = defaultdict(int)

        for record in self.exchange_history:
            by_source[record["source"]] += 1
            by_destination[record["destination"]] += 1

        return {
            "total": len(self.exchange_history),
            "by_source": dict(by_source),
            "by_destination": dict(by_destination)
        }


class RealTimeCollaborationEngine:
    """实时协作引擎 - 主类"""

    def __init__(self):
        self.message_sync = RealTimeMessageSync()
        self.state_manager = CollaborationStateManager()
        self.data_exchange = CrossDimensionalDataExchange()
        self.peers: Dict[str, Dict] = {}
        self.running = False
        self.engine_id = str(uuid.uuid4())[:8]

    async def initialize(self):
        """初始化引擎"""
        await self.message_sync.start()
        self.running = True
        logger.info(f"Real-time Collaboration Engine initialized: {self.engine_id}")

    async def shutdown(self):
        """关闭引擎"""
        await self.message_sync.stop()
        self.running = False
        logger.info("Real-time Collaboration Engine stopped")

    async def create_collaboration_channel(self, channel_id: str, name: str,
                                          sync_strategy: SyncStrategy = SyncStrategy.EAGER) -> Channel:
        """创建协作通道"""
        channel = self.state_manager.create_channel(channel_id, name, sync_strategy)
        
        # 自动订阅消息
        await self.message_sync.subscribe(channel_id, lambda m: self._on_message(m, channel_id))
        
        return channel

    async def join_collaboration(self, channel_id: str, peer_id: str, 
                                 peer_info: Optional[Dict] = None):
        """加入协作"""
        self.state_manager.join_channel(channel_id, peer_id)
        self.peers[peer_id] = peer_info or {}
        
        # 广播加入消息
        await self.message_sync.broadcast(
            channel_id,
            {"type": "peer_joined", "peer_id": peer_id},
            "system"
        )

    async def leave_collaboration(self, channel_id: str, peer_id: str):
        """离开协作"""
        self.state_manager.leave_channel(channel_id, peer_id)
        self.peers.pop(peer_id, None)
        
        # 广播离开消息
        await self.message_sync.broadcast(
            channel_id,
            {"type": "peer_left", "peer_id": peer_id},
            "system"
        )

    async def update_collaboration_state(self, channel_id: str, state: Dict,
                                        actor: str) -> bool:
        """更新协作状态"""
        # 更新状态
        success = self.state_manager.update_state(channel_id, state, actor)
        
        if success:
            # 广播状态更新
            await self.message_sync.broadcast(
                channel_id,
                {"type": "state_updated", "actor": actor, "state": state},
                actor
            )
        
        return success

    async def sync_state(self, channel_id: str, peer_id: str) -> bool:
        """同步状态到对等节点"""
        state = self.state_manager.get_state(channel_id)
        version = self.state_manager.get_version(channel_id)
        
        if state:
            # 通过数据交换发送
            await self.data_exchange.send_data(
                channel_id,
                peer_id,
                {
                    "type": "state_sync",
                    "channel_id": channel_id,
                    "state": state,
                    "version": version
                }
            )
            return True
        return False

    async def exchange_data(self, source: str, destination: str, 
                           data: Any) -> bool:
        """跨维度数据交换"""
        return await self.data_exchange.send_data(source, destination, data)

    def get_channel_info(self, channel_id: str) -> Optional[Dict]:
        """获取通道信息"""
        channel = self.state_manager.channels.get(channel_id)
        if not channel:
            return None
        
        return {
            "id": channel.id,
            "name": channel.name,
            "members": list(channel.members),
            "member_count": len(channel.members),
            "version": self.state_manager.get_version(channel_id),
            "sync_strategy": channel.sync_strategy,
            "created_at": channel.created_at,
            "updated_at": channel.updated_at
        }

    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            "engine_id": self.engine_id,
            "channels": len(self.state_manager.channels),
            "peers": len(self.peers),
            "message_history_size": sum(
                len(h) for h in self.message_sync.message_history.values()
            ),
            "pending_acks": len(self.message_sync.pending_acks),
            "data_exchange_stats": self.data_exchange.get_exchange_stats()
        }

    async def _on_message(self, message: Message, channel_id: str):
        """消息处理回调"""
        if message.type == MessageType.STATE_UPDATE.value:
            # 处理状态更新
            await self.state_manager.update_state(
                channel_id,
                message.payload.get("state", {}),
                message.sender
            )
        elif message.type == MessageType.STATE_REQUEST.value:
            # 处理状态请求
            state = self.state_manager.get_state(channel_id)
            version = self.state_manager.get_version(channel_id)
            
            response = Message(
                type=MessageType.STATE_RESPONSE.value,
                sender="system",
                receiver=message.sender,
                channel=channel_id,
                payload={
                    "state": state,
                    "version": version
                }
            )
            await self.message_sync.publish(response)


async def demo():
    """演示函数"""
    print("=" * 60)
    print("实时协作引擎演示")
    print("=" * 60)
    
    # 创建引擎
    engine = RealTimeCollaborationEngine()
    await engine.initialize()
    
    # 创建协作通道
    channel = await engine.create_collaboration_channel(
        "project-alpha",
        "Project Alpha Collaboration",
        SyncStrategy.CRDT
    )
    print(f"\n✓ 创建通道: {channel.name}")
    
    # 模拟用户加入
    await engine.join_collaboration("project-alpha", "user_1", {"name": "Alice"})
    await engine.join_collaboration("project-alpha", "user_2", {"name": "Bob"})
    print("✓ 用户加入通道")
    
    # 更新状态
    await engine.update_collaboration_state(
        "project-alpha",
        {"task": "design", "progress": 50, "assignee": "user_1"},
        "user_1"
    )
    print("✓ 状态更新")
    
    # 广播消息
    await engine.message_sync.broadcast(
        "project-alpha",
        {"content": "Hello team!", "from": "user_1"},
        "user_1"
    )
    print("✓ 消息广播")
    
    # 添加数据路由
    engine.data_exchange.add_route("project-alpha", "external-api")
    print("✓ 数据路由配置")
    
    # 数据交换
    await engine.exchange_data("project-alpha", "external-api", 
                               {"event": "update", "data": {"key": "value"}})
    print("✓ 跨维度数据交换")
    
    # 获取统计
    stats = engine.get_statistics()
    print(f"\n引擎统计: {json.dumps(stats, indent=2)}")
    
    # 获取通道信息
    info = engine.get_channel_info("project-alpha")
    print(f"\n通道信息: {json.dumps(info, indent=2)}")
    
    # 关闭引擎
    await engine.shutdown()
    print("\n✓ 引擎已关闭")


if __name__ == "__main__":
    asyncio.run(demo())