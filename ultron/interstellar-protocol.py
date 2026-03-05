#!/usr/bin/env python3
"""
星际通信协议 (Interstellar Communication Protocol)
处理光年级别延迟下的可靠通信

功能:
- 消息编解码
- 延迟容忍网络
- 星际路由协议
- 时间戳同步
"""

import json
import time
import hashlib
import struct
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import asyncio


class MessageType(Enum):
    """消息类型"""
    DATA = 0x01           # 数据消息
    ACK = 0x02            # 确认消息
    NACK = 0x03           # 否定确认
    ROUTE_REQUEST = 0x10  # 路由请求
    ROUTE_REPLY = 0x11    # 路由回复
    PING = 0x20           # 延迟探测
    PONG = 0x21           # 延迟响应
    SYNC = 0x30           # 时间同步
    HEARTBEAT = 0x40      # 心跳


class Priority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3
    EMERGENCY = 4


@dataclass
class InterstellarMessage:
    """星际消息结构"""
    msg_type: MessageType
    priority: Priority
    source_id: str
    dest_id: str
    payload: Dict[str, Any]
    message_id: str = field(default_factory=lambda: hashlib.sha256(str(time.time()).encode()).hexdigest()[:16])
    timestamp: float = field(default_factory=time.time)
    hop_count: int = 0
    max_hops: int = 50
    ttl: int = 3600  # 默认1小时
    sequence_num: int = 0
    correlation_id: Optional[str] = None
    
    def to_bytes(self) -> bytes:
        """序列化为字节流"""
        data = {
            'type': self.msg_type.value,
            'priority': self.priority.value,
            'source': self.source_id,
            'dest': self.dest_id,
            'payload': self.payload,
            'id': self.message_id,
            'ts': self.timestamp,
            'hop': self.hop_count,
            'max_hop': self.max_hops,
            'ttl': self.ttl,
            'seq': self.sequence_num,
            'corr': self.correlation_id
        }
        json_str = json.dumps(data, separators=(',', ':'))
        return json_str.encode('utf-8')
    
    @classmethod
    def from_bytes(cls, data: bytes) -> 'InterstellarMessage':
        """从字节流反序列化"""
        json_str = data.decode('utf-8')
        d = json.loads(json_str)
        return cls(
            msg_type=MessageType(d['type']),
            priority=Priority(d['priority']),
            source_id=d['source'],
            dest_id=d['dest'],
            payload=d['payload'],
            message_id=d['id'],
            timestamp=d['ts'],
            hop_count=d['hop'],
            max_hops=d['max_hop'],
            ttl=d['ttl'],
            sequence_num=d['seq'],
            correlation_id=d.get('corr')
        )


@dataclass
class NodeInfo:
    """星际节点信息"""
    node_id: str
    position: Tuple[float, float, float]  # 3D坐标 (光年)
    distance_to_earth: float  # 到地球距离（光年）
    bandwidth: float  # Mbps
    latency: float  # 光秒
    reliability: float  # 0-1
    last_seen: float = field(default_factory=time.time)
    neighbors: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    load: float = 0.0  # 0-1


class InterstellarProtocol:
    """星际通信协议栈"""
    
    # 光速 (km/s)
    SPEED_OF_LIGHT = 299792.458
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.nodes: Dict[str, NodeInfo] = {}
        self.pending_acks: Dict[str, float] = {}
        self.message_buffer: deque = deque(maxlen=10000)
        self.sequence_counter = 0
        self.routing_table: Dict[str, List[str]] = {}
        
    def calculate_distance(self, pos1: Tuple[float, float, float], 
                          pos2: Tuple[float, float, float]) -> float:
        """计算两点间距离（光年）"""
        dx = pos2[0] - pos1[0]
        dy = pos2[1] - pos1[1]
        dz = pos2[2] - pos1[2]
        return (dx**2 + dy**2 + dz**2) ** 0.5
    
    def calculate_latency(self, distance_ly: float) -> float:
        """计算光年距离对应的延迟（秒）"""
        # 光年转光秒: 1光年 = 365.25 * 24 * 3600 光秒
        light_seconds_per_year = 365.25 * 24 * 3600
        return distance_ly * light_seconds_per_year
    
    def register_node(self, node_info: NodeInfo) -> None:
        """注册星际节点"""
        self.nodes[node_info.node_id] = node_info
        self._update_routing()
    
    def _update_routing(self) -> None:
        """更新路由表"""
        self.routing_table.clear()
        for node_id in self.nodes:
            self.routing_table[node_id] = self._find_route(node_id)
    
    def _find_route(self, dest_id: str) -> List[str]:
        """使用Dijkstra算法查找最优路由"""
        if dest_id not in self.nodes:
            return []
        
        # 简单实现：BFS找最短路径
        visited = set()
        queue = [(self.node_id, [self.node_id])]
        
        while queue:
            current, path = queue.pop(0)
            if current == dest_id:
                return path[1:]  # 排除起点
            
            if current in visited:
                continue
            visited.add(current)
            
            for neighbor in self.nodes.get(current, NodeInfo("", (0,0,0), 0, 0, 0, 0)).neighbors:
                if neighbor not in visited:
                    queue.append((neighbor, path + [neighbor]))
        
        return []
    
    def create_message(self, msg_type: MessageType, dest_id: str,
                      payload: Dict[str, Any], priority: Priority = Priority.NORMAL) -> InterstellarMessage:
        """创建星际消息"""
        self.sequence_counter += 1
        return InterstellarMessage(
            msg_type=msg_type,
            priority=priority,
            source_id=self.node_id,
            dest_id=dest_id,
            payload=payload,
            sequence_num=self.sequence_counter
        )
    
    def send_message(self, message: InterstellarMessage) -> Tuple[bool, str]:
        """发送消息"""
        # 检查目标节点
        if message.dest_id not in self.nodes:
            # 尝试通过路由发送
            route = self.routing_table.get(message.dest_id, [])
            if route:
                next_hop = route[0]
                message.hop_count += 1
                if message.hop_count > message.max_hops:
                    return False, "Max hops exceeded"
                return self._forward_to_hop(message, next_hop)
            return False, "Destination unknown"
        
        # 直接发送
        return self._deliver_message(message)
    
    def _forward_to_hop(self, message: InterstellarMessage, next_hop: str) -> Tuple[bool, str]:
        """转发到下一跳"""
        # 模拟发送
        hop_node = self.nodes.get(next_hop)
        if not hop_node:
            return False, f"Next hop {next_hop} not found"
        
        # 计算延迟
        my_pos = self.nodes.get(self.node_id, NodeInfo("", (0,0,0), 0, 0, 0, 0)).position
        hop_pos = hop_node.position
        distance = self.calculate_distance(my_pos, hop_pos)
        latency = self.calculate_latency(distance)
        
        # 记录ACK超时
        self.pending_acks[message.message_id] = time.time() + latency * 2
        
        return True, f"Forwarded to {next_hop}, latency: {latency:.2f}s"
    
    def _deliver_message(self, message: InterstellarMessage) -> Tuple[bool, str]:
        """交付消息到目标"""
        target = self.nodes.get(message.dest_id)
        if not target:
            return False, "Target node not found"
        
        # 计算实际延迟
        my_pos = self.nodes.get(self.node_id, NodeInfo("", (0,0,0), 0, 0, 0, 0)).position
        distance = self.calculate_distance(my_pos, target.position)
        latency = self.calculate_latency(distance)
        
        # 添加到缓冲区
        self.message_buffer.append(message)
        
        return True, f"Delivered in {latency:.2f}s"
    
    def receive_message(self, data: bytes) -> Optional[InterstellarMessage]:
        """接收并解析消息"""
        try:
            message = InterstellarMessage.from_bytes(data)
            
            # TTL检查
            if time.time() - message.timestamp > message.ttl:
                return None
            
            return message
        except Exception as e:
            return None
    
    def create_ack(self, original_msg: InterstellarMessage) -> InterstellarMessage:
        """创建确认消息"""
        return InterstellarMessage(
            msg_type=MessageType.ACK,
            priority=Priority.HIGH,
            source_id=self.node_id,
            dest_id=original_msg.source_id,
            payload={'acked_id': original_msg.message_id},
            correlation_id=original_msg.message_id
        )
    
    def check_pending_acks(self) -> List[str]:
        """检查超时的ACK"""
        current_time = time.time()
        timeout_acks = []
        
        for msg_id, timeout_time in list(self.pending_acks.items()):
            if current_time > timeout_time:
                timeout_acks.append(msg_id)
                del self.pending_acks[msg_id]
        
        return timeout_acks
    
    def get_network_stats(self) -> Dict[str, Any]:
        """获取网络统计"""
        return {
            'total_nodes': len(self.nodes),
            'routing_entries': len(self.routing_table),
            'pending_acks': len(self.pending_acks),
            'buffer_size': len(self.message_buffer),
            'sequence_num': self.sequence_counter
        }


class DelayTolerantNetwork:
    """延迟容忍网络 (DTN) 实现"""
    
    def __init__(self, protocol: InterstellarProtocol):
        self.protocol = protocol
        self.bundle_store: Dict[str, InterstellarMessage] = {}
        self.contact_schedule: List[Dict] = []
        
    def store_bundle(self, message: InterstellarMessage) -> str:
        """存储消息bundle用于延迟传输"""
        bundle_id = f"bundle_{message.message_id}"
        self.bundle_store[bundle_id] = message
        return bundle_id
    
    def get_bundle(self, bundle_id: str) -> Optional[InterstellarMessage]:
        """获取存储的bundle"""
        return self.bundle_store.get(bundle_id)
    
    def delete_bundle(self, bundle_id: str) -> bool:
        """删除已送达的bundle"""
        if bundle_id in self.bundle_store:
            del self.bundle_store[bundle_id]
            return True
        return False
    
    def add_contact(self, node_id: str, start_time: float, 
                   duration: float, bandwidth: float) -> None:
        """添加接触计划（节点可见的时间窗口）"""
        self.contact_schedule.append({
            'node': node_id,
            'start': start_time,
            'end': start_time + duration,
            'bandwidth': bandwidth
        })
    
    def get_available_contacts(self, current_time: float) -> List[Dict]:
        """获取当前可用的接触"""
        return [c for c in self.contact_schedule 
                if c['start'] <= current_time <= c['end']]
    
    def estimate_delivery_time(self, dest_id: str) -> Optional[float]:
        """估计到目的地的预计送达时间"""
        if dest_id in self.protocol.routing_table:
            route = self.protocol.routing_table[dest_id]
            if not route:
                return None
            
            total_latency = 0
            my_pos = self.protocol.nodes.get(self.protocol.node_id, 
                NodeInfo("", (0,0,0), 0, 0, 0, 0)).position
            
            for hop_id in route:
                hop_node = self.protocol.nodes.get(hop_id)
                if hop_node:
                    distance = self.protocol.calculate_distance(my_pos, hop_node.position)
                    total_latency += self.protocol.calculate_latency(distance)
                    my_pos = hop_node.position
            
            return total_latency
        return None


def demo():
    """演示星际通信协议"""
    print("=" * 60)
    print("星际通信协议演示")
    print("=" * 60)
    
    # 创建协议栈
    protocol = InterstellarProtocol("earth")
    
    # 注册星际节点
    nodes_data = [
        ("proxima", (4.24, 0, 0), 4.24, 100, 0.95),      # 比邻星 (4.24光年)
        ("trappist", (39.5, 0, 0), 39.5, 50, 0.88),      # TRAPPIST-1 (39.5光年)
        ("gliese", (20.3, 5.2, 0), 21.0, 75, 0.92),      # Gliese 667 (21光年)
        ("kepler", (500, 300, 100), 583, 20, 0.75),      # 开普勒区域 (583光年)
    ]
    
    for node_id, pos, dist, bw, rel in nodes_data:
        node = NodeInfo(node_id, pos, dist, bw, 
                       protocol.calculate_latency(dist), rel,
                       neighbors=["earth"] if dist < 50 else [])
        protocol.register_node(node)
    
    print(f"\n已注册 {len(protocol.nodes)} 个星际节点")
    
    # 创建并发送消息
    msg = protocol.create_message(
        MessageType.DATA,
        "proxima",
        {"content": "Hello from Earth!", "type": "greeting"},
        Priority.HIGH
    )
    
    print(f"\n创建消息: {msg.message_id}")
    print(f"  类型: {msg.msg_type.name}")
    print(f"  优先级: {msg.priority.name}")
    print(f"  目标: {msg.dest_id}")
    print(f"  载荷: {msg.payload}")
    
    # 发送
    success, result = protocol.send_message(msg)
    print(f"\n发送结果: {success} - {result}")
    
    # 模拟接收
    received = protocol.receive_message(msg.to_bytes())
    if received:
        print(f"接收验证: ✓ 消息完整")
    
    # 网络统计
    stats = protocol.get_network_stats()
    print(f"\n网络统计:")
    for k, v in stats.items():
        print(f"  {k}: {v}")
    
    # 延迟容忍网络演示
    dtn = DelayTolerantNetwork(protocol)
    bundle_id = dtn.store_bundle(msg)
    print(f"\nDTN存储Bundle: {bundle_id}")
    
    # 估计送达时间
    delivery_time = dtn.estimate_delivery_time("proxima")
    if delivery_time:
        print(f"预计送达时间: {delivery_time/3600/24:.2f} 天")
    
    print("\n" + "=" * 60)
    print("演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()