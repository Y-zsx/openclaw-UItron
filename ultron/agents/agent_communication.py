#!/usr/bin/env python3
"""Agent通信增强模块
实现消息确认、重试机制、消息队列和通信监控
"""
import json
import asyncio
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
import threading

class MessageStatus(Enum):
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    ACKNOWLEDGED = "acknowledged"
    FAILED = "failed"
    TIMEOUT = "timeout"

class DeliveryMode(Enum):
    AT_LEAST_ONCE = "at_least_once"  # 至少一次（重试）
    AT_MOST_ONCE = "at_most_once"    # 至多一次（不重试）
    EXACTLY_ONCE = "exactly_once"    # 恰好一次（需要确认）

@dataclass
class MessageEnvelope:
    """消息信封"""
    id: str
    from_agent: str
    to_agent: str
    content: Any
    priority: int = 1
    protocol: str = "sync"
    status: MessageStatus = MessageStatus.PENDING
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sent_at: Optional[str] = None
    delivered_at: Optional[str] = None
    acknowledged_at: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    ttl: int = 300  # 消息生存时间（秒）
    correlation_id: Optional[str] = None  # 用于消息追踪

class AgentCommunicationManager:
    """Agent通信管理器 - 负责消息传递、确认和重试"""
    
    def __init__(self, storage_path: str = None):
        if storage_path is None:
            storage_path = Path(__file__).parent / "communication_state.json"
        self.storage_path = Path(storage_path)
        
        # 消息队列
        self.pending_messages: Dict[str, MessageEnvelope] = {}
        self.in_flight_messages: Dict[str, MessageEnvelope] = {}
        self.delivered_messages: Dict[str, MessageEnvelope] = {}
        
        # 通信统计
        self.stats = {
            "total_sent": 0,
            "total_delivered": 0,
            "total_acknowledged": 0,
            "total_failed": 0,
            "total_retries": 0,
            "average_latency_ms": 0,
            "messages_by_priority": {0: 0, 1: 0, 2: 0, 3: 0}
        }
        
        # 回调函数
        self.callbacks: Dict[str, Callable] = {}
        
        # Agent路由表
        self.routes = {
            "monitor": ["analyzer", "executor", "coordinator", "communicator"],
            "analyzer": ["executor", "coordinator", "communicator", "monitor"],
            "executor": ["analyzer", "coordinator", "communicator", "monitor"],
            "coordinator": ["monitor", "analyzer", "executor", "communicator"],
            "communicator": ["monitor", "analyzer", "executor", "coordinator"]
        }
        
        # 消息处理器
        self.handlers: Dict[str, Callable] = {}
        
        self._load_state()
        self._start_retry_worker()
        
        print(f"[CommunicationMgr] 通信管理器初始化完成")
    
    def _load_state(self):
        """加载状态"""
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text())
                self.stats.update(data.get("stats", {}))
            except Exception as e:
                print(f"[CommunicationMgr] 状态加载失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        data = {"stats": self.stats, "last_update": datetime.now().isoformat()}
        self.storage_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    
    def register_route(self, from_agent: str, to_agents: List[str]):
        """注册路由"""
        self.routes[from_agent] = to_agents
    
    def register_handler(self, agent_name: str, handler: Callable):
        """注册消息处理器"""
        self.handlers[agent_name] = handler
    
    def register_callback(self, event: str, callback: Callable):
        """注册事件回调"""
        self.callbacks[event] = callback
    
    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        content: Any,
        priority: int = 1,
        delivery_mode: DeliveryMode = DeliveryMode.AT_LEAST_ONCE,
        correlation_id: str = None
    ) -> str:
        """发送消息"""
        # 验证路由
        valid_routes = self.routes.get(from_agent, [])
        if to_agent not in valid_routes and to_agent != "broadcast":
            print(f"[CommunicationMgr] ⚠️ 无效路由: {from_agent} -> {to_agent}")
            return None
        
        # 创建消息
        msg_id = f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        envelope = MessageEnvelope(
            id=msg_id,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            priority=priority,
            correlation_id=correlation_id or msg_id
        )
        
        # 根据投递模式处理
        if delivery_mode == DeliveryMode.AT_MOST_ONCE:
            # 直接发送，不重试
            self._deliver_message(envelope)
            return msg_id
        else:
            # 加入待发送队列
            self.pending_messages[msg_id] = envelope
            self.stats["messages_by_priority"][priority] = self.stats["messages_by_priority"].get(priority, 0) + 1
            return msg_id
    
    def _deliver_message(self, envelope: MessageEnvelope):
        """投递消息"""
        # 调用处理器
        handler = self.handlers.get(envelope.to_agent)
        if handler:
            try:
                handler(envelope)
                envelope.status = MessageStatus.DELIVERED
                envelope.delivered_at = datetime.now().isoformat()
                self.stats["total_delivered"] += 1
            except Exception as e:
                print(f"[CommunicationMgr] ❌ 消息投递失败: {e}")
                envelope.status = MessageStatus.FAILED
                self.stats["total_failed"] += 1
        else:
            # 没有处理器，标记为已发送
            envelope.status = MessageStatus.SENT
            envelope.sent_at = datetime.now().isoformat()
            self.stats["total_sent"] += 1
        
        self._save_state()
    
    def acknowledge_message(self, message_id: str) -> bool:
        """确认消息"""
        # 先检查pending_messages
        if message_id in self.pending_messages:
            msg = self.pending_messages[message_id]
            msg.status = MessageStatus.ACKNOWLEDGED
            msg.acknowledged_at = datetime.now().isoformat()
            self.delivered_messages[message_id] = msg
            del self.pending_messages[message_id]
            self.stats["total_acknowledged"] += 1
            self._save_state()
            return True
        
        # 检查in_flight_messages
        if message_id in self.in_flight_messages:
            msg = self.in_flight_messages[message_id]
            msg.status = MessageStatus.ACKNOWLEDGED
            msg.acknowledged_at = datetime.now().isoformat()
            self.delivered_messages[message_id] = msg
            del self.in_flight_messages[message_id]
            self.stats["total_acknowledged"] += 1
            self._save_state()
            
            # 触发回调
            if "message_acknowledged" in self.callbacks:
                self.callbacks["message_acknowledged"](msg)
            return True
        return False
    
    def _start_retry_worker(self):
        """启动重试工作线程"""
        def worker():
            while True:
                time.sleep(5)  # 每5秒检查一次
                self._process_retry()
        
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
    
    def _process_retry(self):
        """处理重试"""
        now = datetime.now()
        for msg_id, envelope in list(self.pending_messages.items()):
            # 检查TTL
            created = datetime.fromisoformat(envelope.created_at)
            if (now - created).total_seconds() > envelope.ttl:
                envelope.status = MessageStatus.TIMEOUT
                self.stats["total_failed"] += 1
                del self.pending_messages[msg_id]
                continue
            
            # 投递消息
            self._deliver_message(envelope)
            if envelope.status in [MessageStatus.SENT, MessageStatus.DELIVERED]:
                self.in_flight_messages[msg_id] = envelope
                del self.pending_messages[msg_id]
    
    def retry_message(self, message_id: str) -> bool:
        """手动重试消息"""
        if message_id in self.in_flight_messages:
            envelope = self.in_flight_messages[message_id]
            if envelope.retry_count < envelope.max_retries:
                envelope.retry_count += 1
                envelope.status = MessageStatus.PENDING
                self.pending_messages[message_id] = envelope
                del self.in_flight_messages[message_id]
                self.stats["total_retries"] += 1
                return True
        return False
    
    def get_message_status(self, message_id: str) -> Optional[MessageStatus]:
        """获取消息状态"""
        for msg in list(self.pending_messages.values()) + list(self.in_flight_messages.values()) + list(self.delivered_messages.values()):
            if msg.id == message_id:
                return msg.status
        return None
    
    def get_stats(self) -> Dict:
        """获取通信统计"""
        return {
            "stats": self.stats,
            "pending_count": len(self.pending_messages),
            "in_flight_count": len(self.in_flight_messages),
            "delivered_count": len(self.delivered_messages),
            "timestamp": datetime.now().isoformat()
        }
    
    def broadcast(self, from_agent: str, content: Any, priority: int = 1) -> List[str]:
        """广播消息"""
        valid_routes = self.routes.get(from_agent, [])
        message_ids = []
        for agent in valid_routes:
            msg_id = self.send_message(from_agent, agent, content, priority)
            if msg_id:
                message_ids.append(msg_id)
        return message_ids
    
    def test_communication(self) -> Dict:
        """测试通信功能"""
        results = {}
        
        # 测试1: 发送消息
        msg_id = self.send_message("coordinator", "communicator", {"type": "test"})
        results["send_message"] = "OK" if msg_id else "FAIL"
        
        # 测试2: 消息状态查询
        if msg_id:
            status = self.get_message_status(msg_id)
            results["get_status"] = "OK" if status else "FAIL"
        
        # 测试3: 消息确认
        if msg_id:
            ack_result = self.acknowledge_message(msg_id)
            results["acknowledge"] = "OK" if ack_result else "FAIL"
        
        # 测试4: 广播
        broadcast_ids = self.broadcast("coordinator", {"type": "broadcast_test"})
        results["broadcast"] = "OK" if len(broadcast_ids) > 0 else "FAIL"
        
        # 测试5: 统计功能
        stats = self.get_stats()
        results["stats"] = "OK" if "stats" in stats else "FAIL"
        
        passed = sum(1 for v in results.values() if v == "OK")
        results["summary"] = f"{passed}/{len(results)} tests passed"
        
        return results


# 全局实例
_comm_manager = None

def get_communication_manager() -> AgentCommunicationManager:
    """获取全局通信管理器实例"""
    global _comm_manager
    if _comm_manager is None:
        _comm_manager = AgentCommunicationManager()
    return _comm_manager


if __name__ == "__main__":
    mgr = AgentCommunicationManager()
    
    print("=== Agent Communication Manager Test ===")
    results = mgr.test_communication()
    for k, v in results.items():
        print(f"  {k}: {v}")
    
    print(f"\n=== Communication Stats ===")
    stats = mgr.get_stats()
    print(f"  Total Sent: {stats['stats']['total_sent']}")
    print(f"  Total Delivered: {stats['stats']['total_delivered']}")
    print(f"  Total Acknowledged: {stats['stats']['total_acknowledged']}")
    print(f"  Total Failed: {stats['stats']['total_failed']}")