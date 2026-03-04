#!/usr/bin/env python3
"""
奥创跨设备通信协议 - 第2世：跨设备通信协议
功能：消息协议标准化、数据同步、状态一致性
"""

import json
import os
import datetime
import uuid
import hashlib
import asyncio
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import queue


class MessageType(Enum):
    """消息类型"""
    HEARTBEAT = "heartbeat"
    SYNC_REQUEST = "sync_request"
    SYNC_RESPONSE = "sync_response"
    TASK_DISPATCH = "task_dispatch"
    TASK_RESULT = "task_result"
    STATE_UPDATE = "state_update"
    STATE_QUERY = "state_query"
    STATE_BROADCAST = "state_broadcast"
    COMMAND = "command"
    RESPONSE = "response"
    ERROR = "error"
    ACK = "ack"


class ProtocolVersion(Enum):
    """协议版本"""
    V1 = "1.0"
    V2 = "2.0"


@dataclass
class ProtocolMessage:
    """标准协议消息"""
    msg_id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    version: str = ProtocolVersion.V2.value
    msg_type: str = MessageType.HEARTBEAT.value
    sender_id: str = ""
    sender_name: str = ""
    target_id: str = ""  # 空表示广播
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    payload: Dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""  # 关联消息ID（用于请求/响应配对）
    ttl: int = 60  # 消息生存时间（秒）
    priority: int = 5  # 优先级 1-10
    
    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)
    
    @classmethod
    def from_json(cls, data: str) -> 'ProtocolMessage':
        return cls(**json.loads(data))
    
    def get_checksum(self) -> str:
        """计算消息校验和"""
        content = f"{self.msg_id}{self.msg_type}{self.sender_id}{self.timestamp}{json.dumps(self.payload, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()[:8]
    
    def is_valid(self) -> bool:
        """验证消息完整性"""
        return bool(self.msg_id and self.msg_type and self.sender_id)


@dataclass
class SyncData:
    """同步数据单元"""
    key: str
    value: Any
    version: int = 1
    timestamp: str = field(default_factory=lambda: datetime.datetime.now().isoformat())
    source_device: str = ""
    checksum: str = ""
    
    def compute_checksum(self) -> str:
        content = f"{self.key}:{self.version}:{json.dumps(self.value, sort_keys=True)}:{self.timestamp}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class CrossDeviceProtocol:
    """跨设备通信协议管理器"""
    
    def __init__(self, device_id: str, device_name: str, registry_path: str = None):
        self.device_id = device_id
        self.device_name = device_name
        self.registry_path = registry_path or "/root/.openclaw/workspace/ultron/logs/device_registry.json"
        
        # 消息队列
        self.inbox: queue.Queue = queue.Queue()
        self.outbox: queue.Queue = queue.Queue()
        
        # 状态存储
        self.shared_state: Dict[str, SyncData] = {}
        self.state_version: int = 0
        
        # 待确认消息
        self.pending_acks: Dict[str, ProtocolMessage] = {}
        
        # 回调函数
        self.handlers: Dict[MessageType, List[Callable]] = defaultdict(list)
        
        # 统计
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_failed": 0,
            "sync_operations": 0
        }
        
        # 锁
        self._lock = threading.RLock()
        
        # 加载共享状态
        self._load_shared_state()
    
    def _load_shared_state(self):
        """加载共享状态"""
        state_file = "/root/.openclaw/workspace/ultron/logs/shared_state.json"
        if os.path.exists(state_file):
            try:
                with open(state_file, 'r') as f:
                    data = json.load(f)
                    for key, val in data.get("state", {}).items():
                        self.shared_state[key] = SyncData(**val)
                    self.state_version = data.get("version", 0)
            except Exception as e:
                print(f"加载共享状态失败: {e}")
    
    def _save_shared_state(self):
        """保存共享状态"""
        state_file = "/root/.openclaw/workspace/ultron/logs/shared_state.json"
        Path(state_file).parent.mkdir(parents=True, exist_ok=True)
        
        with self._lock:
            data = {
                "state": {k: asdict(v) for k, v in self.shared_state.items()},
                "version": self.state_version,
                "last_updated": datetime.datetime.now().isoformat(),
                "device_id": self.device_id
            }
        
        with open(state_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # ==================== 消息构建 ====================
    
    def create_message(self, msg_type: MessageType, payload: Dict = None, 
                      target_id: str = "", priority: int = 5) -> ProtocolMessage:
        """创建标准协议消息"""
        return ProtocolMessage(
            msg_type=msg_type.value,
            sender_id=self.device_id,
            sender_name=self.device_name,
            target_id=target_id,
            payload=payload or {},
            priority=priority
        )
    
    def create_heartbeat(self) -> ProtocolMessage:
        """创建心跳消息"""
        return self.create_message(
            MessageType.HEARTBEAT,
            {"status": "online", "uptime": self._get_uptime()},
            priority=1
        )
    
    def create_sync_request(self, keys: List[str] = None) -> ProtocolMessage:
        """创建同步请求"""
        return self.create_message(
            MessageType.SYNC_REQUEST,
            {"requested_keys": keys or []},
            priority=3
        )
    
    def create_state_update(self, key: str, value: Any) -> ProtocolMessage:
        """创建状态更新消息"""
        with self._lock:
            self.state_version += 1
            sync_data = SyncData(
                key=key,
                value=value,
                version=self.state_version,
                source_device=self.device_id,
                timestamp=datetime.datetime.now().isoformat()
            )
            sync_data.checksum = sync_data.compute_checksum()
            
            # 更新本地状态
            self.shared_state[key] = sync_data
            self._save_shared_state()
        
        return self.create_message(
            MessageType.STATE_UPDATE,
            {"key": key, "value": value, "version": self.state_version},
            priority=7
        )
    
    def create_command(self, command: str, params: Dict = None, 
                      target_id: str = "") -> ProtocolMessage:
        """创建命令消息"""
        return self.create_message(
            MessageType.COMMAND,
            {"command": command, "params": params or {}},
            target_id=target_id,
            priority=9
        )
    
    # ==================== 消息发送 ====================
    
    def send_message(self, message: ProtocolMessage, callback: Callable = None) -> bool:
        """发送消息"""
        if not message.sender_id:
            message.sender_id = self.device_id
        if not message.sender_name:
            message.sender_name = self.device_name
        
        # 验证消息
        if not message.is_valid():
            self.stats["messages_failed"] += 1
            return False
        
        try:
            # 添加到发送队列
            self.outbox.put(message)
            
            # 注册回调（如果需要确认）
            if callback:
                self.pending_acks[message.msg_id] = message
            
            self.stats["messages_sent"] += 1
            
            # 模拟消息发送（实际实现中会通过网络发送）
            self._simulate_send(message)
            
            return True
        except Exception as e:
            print(f"发送消息失败: {e}")
            self.stats["messages_failed"] += 1
            return False
    
    def _simulate_send(self, message: ProtocolMessage):
        """模拟消息发送（本地回环测试）"""
        # 在实际实现中，这里会通过网络发送
        # 本地测试时，可以直接将消息放入输入队列
        pass
    
    def broadcast_state(self) -> bool:
        """广播当前状态"""
        message = self.create_message(
            MessageType.STATE_BROADCAST,
            {"state": {k: asdict(v) for k, v in self.shared_state.items()}},
            priority=6
        )
        return self.send_message(message)
    
    def request_sync(self, keys: List[str] = None) -> bool:
        """请求同步"""
        message = self.create_sync_request(keys)
        return self.send_message(message)
    
    # ==================== 消息接收 ====================
    
    def receive_message(self, message: ProtocolMessage) -> bool:
        """接收并处理消息"""
        try:
            # 验证消息
            if not message.is_valid():
                print(f"无效消息: {message.msg_id}")
                return False
            
            # 处理消息
            self.stats["messages_received"] += 1
            
            # 调用注册的处理器
            msg_type = MessageType(message.msg_type)
            handlers = self.handlers.get(msg_type, [])
            
            for handler in handlers:
                try:
                    handler(message)
                except Exception as e:
                    print(f"消息处理器执行失败: {e}")
            
            # 发送确认（除非是确认消息本身）
            if msg_type != MessageType.ACK:
                self._send_ack(message)
            
            return True
        except Exception as e:
            print(f"处理消息失败: {e}")
            return False
    
    def _send_ack(self, original_message: ProtocolMessage):
        """发送确认"""
        ack = self.create_message(
            MessageType.ACK,
            {"original_id": original_message.msg_id, "status": "received"},
            target_id=original_message.sender_id,
            priority=1
        )
        ack.correlation_id = original_message.msg_id
        self.send_message(ack)
    
    def register_handler(self, msg_type: MessageType, handler: Callable):
        """注册消息处理器"""
        self.handlers[msg_type].append(handler)
    
    # ==================== 状态同步 ====================
    
    def update_local_state(self, key: str, value: Any) -> bool:
        """更新本地状态"""
        with self._lock:
            self.state_version += 1
            sync_data = SyncData(
                key=key,
                value=value,
                version=self.state_version,
                source_device=self.device_id,
                timestamp=datetime.datetime.now().isoformat()
            )
            sync_data.checksum = sync_data.compute_checksum()
            
            self.shared_state[key] = sync_data
            self._save_shared_state()
            
            self.stats["sync_operations"] += 1
        
        # 广播状态更新
        self.broadcast_state()
        
        return True
    
    def get_state(self, key: str = None) -> Any:
        """获取状态"""
        with self._lock:
            if key:
                return self.shared_state.get(key)
            return {k: asdict(v) for k, v in self.shared_state.items()}
    
    def resolve_conflict(self, key: str, local: SyncData, remote: SyncData) -> SyncData:
        """解决状态冲突 - 采用最新版本胜出策略"""
        if local.version >= remote.version:
            return local
        return remote
    
    def sync_state(self, remote_state: Dict[str, SyncData]) -> int:
        """同步远程状态"""
        synced = 0
        
        with self._lock:
            for key, remote_data in remote_state.items():
                local_data = self.shared_state.get(key)
                
                if local_data is None:
                    # 本地不存在，直接采用
                    self.shared_state[key] = remote_data
                    synced += 1
                elif local_data.version < remote_data.version:
                    # 远程版本更新
                    self.shared_state[key] = remote_data
                    synced += 1
                # 否则保留本地版本
        
        if synced > 0:
            self._save_shared_state()
            self.stats["sync_operations"] += synced
        
        return synced
    
    # ==================== 工具方法 ====================
    
    def _get_uptime(self) -> int:
        """获取运行时长（秒）"""
        try:
            with open('/proc/uptime', 'r') as f:
                return int(float(f.read().split()[0]))
        except:
            return 0
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "pending_acks": len(self.pending_acks),
            "queue_size_in": self.inbox.qsize(),
            "queue_size_out": self.outbox.qsize(),
            "state_entries": len(self.shared_state),
            "state_version": self.state_version
        }
    
    def process_queue(self):
        """处理消息队列"""
        processed = 0
        
        # 处理输出队列
        while not self.outbox.empty():
            try:
                msg = self.outbox.get_nowait()
                # 在实际实现中，这里会发送消息
                processed += 1
            except queue.Empty:
                break
        
        return processed
    
    def clear_pending(self):
        """清理超时未确认的消息"""
        now = datetime.datetime.now()
        cleared = 0
        
        for msg_id, msg in list(self.pending_acks.items()):
            msg_time = datetime.datetime.fromisoformat(msg.timestamp)
            if (now - msg_time).total_seconds() > msg.ttl:
                del self.pending_acks[msg_id]
                cleared += 1
        
        return cleared


class StateConsistencyManager:
    """状态一致性管理器"""
    
    def __init__(self, protocol: CrossDeviceProtocol):
        self.protocol = protocol
        self.consistency_check_interval = 30  # 秒
        self.max_version_diff = 5  # 最大版本差异
        self.last_check = None
        
        # 版本追踪
        self.version_history: Dict[str, List[int]] = defaultdict(list)
    
    def check_consistency(self) -> Dict[str, Any]:
        """检查状态一致性"""
        now = datetime.datetime.now()
        
        if self.last_check:
            elapsed = (now - self.last_check).total_seconds()
            if elapsed < self.consistency_check_interval:
                return {"status": "skipped", "elapsed": elapsed}
        
        self.last_check = now
        
        # 获取当前状态
        current_state = self.protocol.get_state()
        
        # 检查版本一致性
        issues = []
        for key, data in current_state.items():
            version = data.version if isinstance(data, SyncData) else data.get("version", 0)
            
            self.version_history[key].append(version)
            
            # 只保留最近10个版本
            if len(self.version_history[key]) > 10:
                self.version_history[key] = self.version_history[key][-10:]
            
            # 检查版本跳跃
            if len(self.version_history[key]) >= 2:
                recent = self.version_history[key][-5:]
                diff = max(recent) - min(recent)
                if diff > self.max_version_diff:
                    issues.append({
                        "key": key,
                        "issue": "version_jump",
                        "diff": diff
                    })
        
        return {
            "status": "ok" if not issues else "issues_found",
            "issues": issues,
            "checked_at": now.isoformat(),
            "total_keys": len(current_state)
        }
    
    def force_sync(self, key: str) -> bool:
        """强制同步指定键"""
        # 创建同步请求
        message = self.protocol.create_message(
            MessageType.SYNC_REQUEST,
            {"requested_keys": [key]},
            priority=10
        )
        return self.protocol.send_message(message)
    
    def get_reconciliation_plan(self, remote_state: Dict) -> Dict[str, str]:
        """生成分歧协调计划"""
        local_state = self.protocol.get_state()
        plan = {}
        
        for key, remote_data in remote_state.items():
            local_data = local_state.get(key)
            
            if local_data is None:
                plan[key] = "adopt_remote"  # 采用远程
            elif isinstance(local_data, SyncData) and isinstance(remote_data, SyncData):
                if local_data.version >= remote_data.version:
                    plan[key] = "keep_local"  # 保留本地
                else:
                    plan[key] = "adopt_remote"  # 采用远程
            else:
                plan[key] = "conflict"  # 冲突
        
        return plan


# ==================== 全局实例 ====================

_protocol_instance: Optional[CrossDeviceProtocol] = None
_consistency_manager: Optional[StateConsistencyManager] = None


def get_protocol(device_id: str = None, device_name: str = None) -> CrossDeviceProtocol:
    global _protocol_instance
    if _protocol_instance is None:
        import socket
        hostname = socket.gethostname()
        _protocol_instance = CrossDeviceProtocol(
            device_id=device_id or hostname,
            device_name=device_name or hostname
        )
    return _protocol_instance


def get_consistency_manager() -> StateConsistencyManager:
    global _consistency_manager
    if _consistency_manager is None:
        _consistency_manager = StateConsistencyManager(get_protocol())
    return _consistency_manager


# ==================== 命令行接口 ====================

if __name__ == "__main__":
    import sys
    import socket
    
    hostname = socket.gethostname()
    protocol = get_protocol()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "send":
            # 发送测试消息
            msg_type = sys.argv[2] if len(sys.argv) > 2 else "heartbeat"
            target = sys.argv[3] if len(sys.argv) > 3 else ""
            
            message = protocol.create_message(
                MessageType(msg_type),
                {"test": True, "args": sys.argv[3:]},
                target_id=target
            )
            
            if protocol.send_message(message):
                print(f"消息已发送: {message.msg_id}")
            else:
                print("发送失败")
        
        elif cmd == "broadcast":
            protocol.broadcast_state()
            print("状态已广播")
        
        elif cmd == "sync":
            keys = sys.argv[2:] if len(sys.argv) > 2 else None
            protocol.request_sync(keys)
            print("同步请求已发送")
        
        elif cmd == "state":
            key = sys.argv[2] if len(sys.argv) > 2 else None
            state = protocol.get_state(key)
            if key:
                print(json.dumps(asdict(state) if isinstance(state, SyncData) else state, indent=2, ensure_ascii=False))
            else:
                print(json.dumps(state, indent=2, ensure_ascii=False))
        
        elif cmd == "update":
            if len(sys.argv) > 3:
                key = sys.argv[2]
                value = sys.argv[3]
                protocol.update_local_state(key, value)
                print(f"状态已更新: {key} = {value}")
            else:
                print("用法: update <key> <value>")
        
        elif cmd == "consistency":
            manager = get_consistency_manager()
            result = manager.check_consistency()
            print(json.dumps(result, indent=2, ensure_ascii=False))
        
        elif cmd == "stats":
            stats = protocol.get_statistics()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        
        elif cmd == "test":
            # 测试协议
            print("=" * 40)
            print("  跨设备通信协议测试")
            print("=" * 40)
            
            # 创建测试消息
            msg1 = protocol.create_heartbeat()
            print(f"1. 心跳消息: {msg1.msg_id}")
            
            msg2 = protocol.create_state_update("test_key", {"nested": "value"})
            print(f"2. 状态更新: {msg2.msg_id}")
            
            msg3 = protocol.create_command("restart", {"service": "nginx"})
            print(f"3. 命令消息: {msg3.msg_id}")
            
            # 发送消息
            protocol.send_message(msg1)
            protocol.send_message(msg2)
            protocol.send_message(msg3)
            
            # 更新状态
            protocol.update_local_state("device_name", hostname)
            protocol.update_local_state("last_test", datetime.datetime.now().isoformat())
            
            print(f"\n消息已发送: {protocol.stats['messages_sent']}")
            print(f"状态条目: {len(protocol.shared_state)}")
            print("=" * 40)
        
        else:
            print("用法:")
            print("  send <type> [target]    发送消息")
            print("  broadcast               广播状态")
            print("  sync [keys...]         请求同步")
            print("  state [key]            获取状态")
            print("  update <key> <value>   更新状态")
            print("  consistency            检查一致性")
            print("  stats                  获取统计")
            print("  test                   运行测试")
    else:
        stats = protocol.get_statistics()
        print("=" * 50)
        print("  奥创跨设备通信协议 v2.0")
        print("=" * 50)
        print(f"设备ID: {protocol.device_id}")
        print(f"设备名: {protocol.device_name}")
        print(f"消息发送: {stats['messages_sent']}")
        print(f"消息接收: {stats['messages_received']}")
        print(f"失败: {stats['messages_failed']}")
        print(f"状态条目: {stats['state_entries']}")
        print(f"状态版本: {stats['state_version']}")
        print(f"待确认: {stats['pending_acks']}")
        print("=" * 50)