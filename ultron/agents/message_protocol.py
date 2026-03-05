"""
Agent消息协议扩展与消息中间件优化
第58世: Agent协作协议扩展与消息中间件优化
"""
import json
import sqlite3
import threading
import hashlib
import time
from enum import Enum
from typing import Dict, List, Callable, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from datetime import datetime, timedelta
import uuid


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3


class DeliveryStatus(Enum):
    """投递状态"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


class MessageType(Enum):
    """扩展消息类型"""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_PROGRESS = "task_progress"
    HEARTBEAT = "heartbeat"
    STATE_SYNC = "state_sync"
    ROUTE_UPDATE = "route_update"
    FAULT_NOTIFY = "fault_notify"
    COLLABORATION = "collaboration"
    BROADCAST = "broadcast"
    ACK = "ack"


@dataclass
class ExtendedMessage:
    """扩展消息结构"""
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    message_type: str = ""
    sender: str = ""
    receiver: str = ""
    priority: int = MessagePriority.NORMAL.value
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    ttl: int = 3600  # 消息生存时间(秒)
    correlation_id: str = ""  # 关联消息ID
    reply_to: str = ""  # 回复地址
    headers: Dict[str, str] = field(default_factory=dict)
    delivery_status: str = DeliveryStatus.PENDING.value
    retry_count: int = 0
    max_retries: int = 3


class MessagePersistence:
    """消息持久化存储"""
    
    def __init__(self, db_path: str = "/tmp/ultron_messages.db"):
        self.db_path = db_path
        self._init_db()
        self._lock = threading.Lock()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                message_id TEXT PRIMARY KEY,
                message_type TEXT,
                sender TEXT,
                receiver TEXT,
                priority INTEGER,
                payload TEXT,
                timestamp TEXT,
                ttl INTEGER,
                correlation_id TEXT,
                reply_to TEXT,
                headers TEXT,
                delivery_status TEXT,
                retry_count INTEGER,
                max_retries INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_receiver ON messages(receiver)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_status ON messages(delivery_status)
        """)
        
        conn.commit()
        conn.close()
    
    def save(self, message: ExtendedMessage) -> bool:
        """保存消息"""
        with self._lock:
            try:
                conn = sqlite3.connect(self.db_path)
                cursor = conn.cursor()
                
                cursor.execute("""
                    INSERT OR REPLACE INTO messages 
                    (message_id, message_type, sender, receiver, priority, payload,
                     timestamp, ttl, correlation_id, reply_to, headers, delivery_status,
                     retry_count, max_retries)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.message_id,
                    message.message_type,
                    message.sender,
                    message.receiver,
                    message.priority,
                    json.dumps(message.payload),
                    message.timestamp,
                    message.ttl,
                    message.correlation_id,
                    message.reply_to,
                    json.dumps(message.headers),
                    message.delivery_status,
                    message.retry_count,
                    message.max_retries
                ))
                
                conn.commit()
                conn.close()
                return True
            except Exception as e:
                print(f"保存消息失败: {e}")
                return False
    
    def load_pending(self) -> List[ExtendedMessage]:
        """加载待投递消息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT * FROM messages 
            WHERE delivery_status = ? AND retry_count < max_retries
            ORDER BY priority DESC, timestamp ASC
        """, (DeliveryStatus.PENDING.value,))
        
        messages = []
        for row in cursor.fetchall():
            msg = ExtendedMessage(
                message_id=row[0],
                message_type=row[1],
                sender=row[2],
                receiver=row[3],
                priority=row[4],
                payload=json.loads(row[5]),
                timestamp=row[6],
                ttl=row[7],
                correlation_id=row[8],
                reply_to=row[9],
                headers=json.loads(row[10]),
                delivery_status=row[11],
                retry_count=row[12],
                max_retries=row[13]
            )
            messages.append(msg)
        
        conn.close()
        return messages
    
    def update_status(self, message_id: str, status: str):
        """更新投递状态"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE messages SET delivery_status = ? WHERE message_id = ?
        """, (status, message_id))
        conn.commit()
        conn.close()
    
    def cleanup_expired(self):
        """清理过期消息"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM messages 
            WHERE timestamp < datetime('now', '-' || (ttl / 86400.0) || ' days')
        """)
        conn.commit()
        conn.close()


class ReliableDelivery:
    """可靠投递机制"""
    
    def __init__(self, persistence: MessagePersistence):
        self.persistence = persistence
        self.pending_acks: Dict[str, float] = {}
        self.ack_timeout = 30  # ACK超时秒数
    
    def send_with_retry(self, message: ExtendedMessage) -> bool:
        """带重试的发送"""
        # 保存消息到持久化
        self.persistence.save(message)
        
        # 记录待确认
        self.pending_acks[message.message_id] = time.time()
        
        # 模拟发送 (实际会调用网络层)
        success = self._deliver(message)
        
        if success:
            self.persistence.update_status(
                message.message_id, 
                DeliveryStatus.DELIVERED.value
            )
            del self.pending_acks[message.message_id]
            return True
        else:
            # 增加重试计数
            message.retry_count += 1
            if message.retry_count < message.max_retries:
                # 延迟重试
                threading.Timer(
                    min(2 ** message.retry_count, 30),
                    self._retry_deliver,
                    args=(message,)
                ).start()
            else:
                self.persistence.update_status(
                    message.message_id,
                    DeliveryStatus.FAILED.value
                )
            return False
    
    def _deliver(self, message: ExtendedMessage) -> bool:
        """实际投递"""
        # 这里应该调用底层网络发送
        # 模拟成功
        return True
    
    def _retry_deliver(self, message: ExtendedMessage):
        """重试投递"""
        self.send_with_retry(message)
    
    def check_timeouts(self):
        """检查超时未确认的消息"""
        now = time.time()
        timeout_msgs = []
        
        for msg_id, send_time in list(self.pending_acks.items()):
            if now - send_time > self.ack_timeout:
                timeout_msgs.append(msg_id)
        
        for msg_id in timeout_msgs:
            # 重新发送
            messages = self.persistence.load_pending()
            for msg in messages:
                if msg.message_id == msg_id:
                    self.send_with_retry(msg)
                    break


class CrossClusterRouter:
    """跨集群消息路由"""
    
    def __init__(self):
        self.clusters: Dict[str, Dict] = {}
        self.routes: Dict[str, List[str]] = defaultdict(list)
        self.local_cluster: str = "default"
    
    def register_cluster(self, cluster_id: str, endpoints: List[str], 
                        metadata: Dict = None):
        """注册集群"""
        self.clusters[cluster_id] = {
            "endpoints": endpoints,
            "metadata": metadata or {},
            "status": "active",
            "last_heartbeat": datetime.now().isoformat()
        }
        self._update_routes()
    
    def remove_cluster(self, cluster_id: str):
        """移除集群"""
        if cluster_id in self.clusters:
            del self.clusters[cluster_id]
            self._update_routes()
    
    def route_message(self, target_cluster: str, message: ExtendedMessage) -> str:
        """路由消息到目标集群"""
        if target_cluster not in self.clusters:
            # 尝试最近集群
            target_cluster = self._find_nearest_cluster()
        
        cluster = self.clusters.get(target_cluster)
        if not cluster:
            return ""
        
        endpoint = cluster["endpoints"][0] if cluster["endpoints"] else ""
        
        # 添加路由头
        message.headers["X-Target-Cluster"] = target_cluster
        message.headers["X-Source-Cluster"] = self.local_cluster
        message.headers["X-Gateway-Endpoint"] = endpoint
        
        return endpoint
    
    def _update_routes(self):
        """更新路由表"""
        for cluster_id in self.clusters:
            self.routes[cluster_id] = [cluster_id]
    
    def _find_nearest_cluster(self) -> str:
        """查找最近集群"""
        if not self.clusters:
            return self.local_cluster
        return list(self.clusters.keys())[0]
    
    def get_cluster_status(self) -> Dict:
        """获取集群状态"""
        return {
            cluster_id: {
                "status": info["status"],
                "last_heartbeat": info["last_heartbeat"],
                "endpoint_count": len(info["endpoints"])
            }
            for cluster_id, info in self.clusters.items()
        }


class OptimizedMessageBroker:
    """优化版消息中间件 - 支持持久化、可靠投递、跨集群"""
    
    def __init__(self, cluster_id: str = "default"):
        self.cluster_id = cluster_id
        self.persistence = MessagePersistence()
        self.reliable_delivery = ReliableDelivery(self.persistence)
        self.cross_cluster_router = CrossClusterRouter()
        
        # 内存索引
        self.subscribers: Dict[str, List[str]] = defaultdict(list)
        self.handlers: Dict[str, Callable] = {}
        
        # 启动后台任务
        self._start_background_tasks()
    
    def _start_background_tasks(self):
        """启动后台任务"""
        # 超时检查
        def check_loop():
            self.reliable_delivery.check_timeouts()
            threading.Timer(10, check_loop).start()
        
        check_loop()
        
        # 过期清理
        def cleanup_loop():
            self.persistence.cleanup_expired()
            threading.Timer(300, cleanup_loop).start()
        
        cleanup_loop()
    
    def subscribe(self, agent_id: str, message_type: str):
        """订阅消息"""
        if agent_id not in self.subscribers[message_type]:
            self.subscribers[message_type].append(agent_id)
    
    def publish(self, message: ExtendedMessage, reliable: bool = True,
                cross_cluster: bool = False) -> bool:
        """发布消息"""
        message.sender = message.sender or self.cluster_id
        
        # 跨集群路由
        if cross_cluster and message.receiver:
            target = message.receiver.split("@")
            if len(target) > 1:
                cluster_id = target[0]
                self.cross_cluster_router.route_message(cluster_id, message)
        
        if reliable:
            return self.reliable_delivery.send_with_retry(message)
        else:
            # 直接投递
            return self._deliver_direct(message)
    
    def _deliver_direct(self, message: ExtendedMessage) -> bool:
        """直接投递"""
        self.persistence.save(message)
        
        subscribers = self.subscribers.get(message.message_type, [])
        for subscriber in subscribers:
            handler = self.handlers.get(subscriber)
            if handler:
                try:
                    handler(message)
                except Exception as e:
                    print(f"消息处理错误: {e}")
                    return False
        
        self.persistence.update_status(
            message.message_id,
            DeliveryStatus.DELIVERED.value
        )
        return True
    
    def register_handler(self, agent_id: str, handler: Callable):
        """注册处理器"""
        self.handlers[agent_id] = handler
    
    def send_ack(self, original_message: ExtendedMessage, success: bool):
        """发送确认"""
        ack = ExtendedMessage(
            message_type=MessageType.ACK.value,
            sender=self.cluster_id,
            receiver=original_message.sender,
            correlation_id=original_message.message_id,
            payload={"success": success}
        )
        self.publish(ack, reliable=True)
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        pending = self.persistence.load_pending()
        return {
            "cluster_id": self.cluster_id,
            "pending_count": len(pending),
            "subscribers": {k: len(v) for k, v in self.subscribers.items()},
            "clusters": self.cross_cluster_router.get_cluster_status()
        }


# 扩展消息协议工厂
class MessageProtocolFactory:
    """消息协议工厂"""
    
    @staticmethod
    def create_task_request(sender: str, task_id: str, 
                           payload: Dict) -> ExtendedMessage:
        """创建任务请求消息"""
        return ExtendedMessage(
            message_type=MessageType.TASK_REQUEST.value,
            sender=sender,
            priority=MessagePriority.HIGH.value,
            payload={"task_id": task_id, "data": payload},
            correlation_id=task_id
        )
    
    @staticmethod
    def create_task_response(sender: str, task_id: str,
                            result: Any) -> ExtendedMessage:
        """创建任务响应消息"""
        return ExtendedMessage(
            message_type=MessageType.TASK_RESPONSE.value,
            sender=sender,
            priority=MessagePriority.NORMAL.value,
            payload={"task_id": task_id, "result": result},
            correlation_id=task_id
        )
    
    @staticmethod
    def create_heartbeat(agent_id: str, status: Dict) -> ExtendedMessage:
        """创建心跳消息"""
        return ExtendedMessage(
            message_type=MessageType.HEARTBEAT.value,
            sender=agent_id,
            priority=MessagePriority.LOW.value,
            payload=status,
            ttl=60
        )
    
    @staticmethod
    def create_broadcast(sender: str, event: str, 
                        data: Dict) -> ExtendedMessage:
        """创建广播消息"""
        return ExtendedMessage(
            message_type=MessageType.BROADCAST.value,
            sender=sender,
            receiver="*",
            priority=MessagePriority.HIGH.value,
            payload={"event": event, "data": data}
        )


if __name__ == "__main__":
    # 测试
    broker = OptimizedMessageBroker("cluster-1")
    
    # 注册处理器
    def test_handler(msg: ExtendedMessage):
        print(f"收到消息: {msg.message_type} from {msg.sender}")
    
    broker.subscribe("executor-01", MessageType.TASK_REQUEST.value)
    broker.register_handler("executor-01", test_handler)
    
    # 创建并发送消息
    msg = MessageProtocolFactory.create_task_request(
        "orchestrator-01",
        "task-123",
        {"action": "execute", "script": "ls -la"}
    )
    
    result = broker.publish(msg, reliable=True)
    print(f"发送结果: {result}")
    print(f"统计: {broker.get_stats()}")