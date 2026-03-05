#!/usr/bin/env python3
"""Communicator Agent - 通信协调Agent
负责多Agent系统中的消息传递、协议转换和通信协调
"""
import json
import sys
import asyncio
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from enum import Enum

sys.path.insert(0, str(Path(__file__).parent))
from message_bus import MessageBus

class MessagePriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    URGENT = 3

class CommunicationProtocol(Enum):
    SYNC = "sync"        # 同步通信
    ASYNC = "async"      # 异步通信
    BROADCAST = "broadcast"  # 广播
    PIPELINE = "pipeline"    # 流水线

class CommunicatorAgent:
    """通信协调Agent - 负责多Agent系统的消息传递和协调"""
    
    def __init__(self):
        self.name = "communicator"
        self.bus = MessageBus()
        self.state_file = Path(__file__).parent / "communicator_state.json"
        self.protocol_file = Path(__file__).parent / "communicator_protocol.json"
        
        # Agent通信路由表
        self.routes = {
            "monitor": ["analyzer", "executor", "coordinator"],
            "analyzer": ["executor", "coordinator", "communicator"],
            "executor": ["analyzer", "coordinator", "communicator"],
            "coordinator": ["monitor", "analyzer", "executor", "communicator"],
            "communicator": ["monitor", "analyzer", "executor", "coordinator"]
        }
        
        # 通信统计
        self.stats = {
            "messages_sent": 0,
            "messages_received": 0,
            "messages_routed": 0,
            "protocols_used": {},
            "failed_deliveries": 0
        }
        
        self._load_state()
        print(f"[Communicator] Agent初始化完成")
    
    def _load_state(self):
        """加载状态"""
        if self.state_file.exists():
            try:
                state = json.loads(self.state_file.read_text())
                self.stats.update(state.get("stats", {}))
            except:
                pass
    
    def _save_state(self):
        """保存状态"""
        state = {
            "stats": self.stats,
            "last_update": datetime.now().isoformat()
        }
        self.state_file.write_text(json.dumps(state, indent=2, ensure_ascii=False))
    
    def register_route(self, from_agent: str, to_agents: List[str]):
        """注册通信路由"""
        self.routes[from_agent] = to_agents
        print(f"[Communicator] 路由已注册: {from_agent} -> {to_agents}")
    
    def get_valid_routes(self, from_agent: str) -> List[str]:
        """获取有效的通信路由"""
        return self.routes.get(from_agent, [])
    
    def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message: Any,
        priority: MessagePriority = MessagePriority.NORMAL,
        protocol: CommunicationProtocol = CommunicationProtocol.SYNC
    ) -> Dict:
        """发送消息"""
        # 验证路由
        valid_routes = self.get_valid_routes(from_agent)
        if to_agent not in valid_routes and to_agent != "broadcast":
            print(f"[Communicator] ⚠️ 无效路由: {from_agent} -> {to_agent}")
            self.stats["failed_deliveries"] += 1
            return {"status": "failed", "reason": "invalid_route"}
        
        # 构建消息
        envelope = {
            "id": f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            "from": from_agent,
            "to": to_agent,
            "message": message,
            "priority": priority.value,
            "protocol": protocol.value,
            "timestamp": datetime.now().isoformat(),
            "hops": 0
        }
        
        # 发送消息
        try:
            if protocol == CommunicationProtocol.BROADCAST:
                # 广播模式
                for agent in valid_routes:
                    self._deliver_message(envelope.copy(), agent)
            else:
                # 单播模式
                self._deliver_message(envelope, to_agent)
            
            self.stats["messages_sent"] += 1
            self._save_state()
            
            return {"status": "sent", "message_id": envelope["id"]}
        except Exception as e:
            print(f"[Communicator] ❌ 消息发送失败: {e}")
            self.stats["failed_deliveries"] += 1
            return {"status": "failed", "error": str(e)}
    
    def _deliver_message(self, envelope: Dict, to_agent: str):
        """投递消息"""
        from_agent = envelope.get("from", "communicator")
        message_content = envelope.get("message", {})
        
        # 通过消息总线发送 (sender, recipient, message, task_type)
        self.bus.publish(from_agent, to_agent, json.dumps(message_content), "message")
        
        print(f"[Communicator] 📤 消息已投递: {envelope['from']} -> {to_agent} (protocol: {envelope['protocol']})")
        
        # 更新统计
        protocol = envelope["protocol"]
        self.stats["protocols_used"][protocol] = self.stats["protocols_used"].get(protocol, 0) + 1
    
    def receive_messages(self, agent_name: str) -> List[Dict]:
        """接收消息"""
        messages = self.bus.subscribe(f"agent.{agent_name}")
        self.stats["messages_received"] += len(messages)
        return messages
    
    def route_message(self, message: Dict) -> Dict:
        """路由消息 - 智能消息分发"""
        # 检查消息是否需要路由
        to_agent = message.get("to")
        from_agent = message.get("from")
        
        if not to_agent or to_agent == "broadcast":
            # 广播
            valid_routes = self.get_valid_routes(from_agent)
            for agent in valid_routes:
                self._deliver_message(message.copy(), agent)
            self.stats["messages_routed"] += len(valid_routes)
            return {"status": "broadcast", "count": len(valid_routes)}
        
        # 单播
        result = self.send_message(
            from_agent=from_agent,
            to_agent=to_agent,
            message=message.get("message"),
            priority=MessagePriority(message.get("priority", 1)),
            protocol=CommunicationProtocol(message.get("protocol", "sync"))
        )
        
        if result["status"] == "sent":
            self.stats["messages_routed"] += 1
        
        return result
    
    def get_communication_stats(self) -> Dict:
        """获取通信统计"""
        return {
            "stats": self.stats,
            "routes": self.routes,
            "timestamp": datetime.now().isoformat()
        }
    
    def test_communication(self) -> Dict:
        """测试通信功能"""
        results = {}
        
        # 测试1: 基本消息发送
        result1 = self.send_message(
            from_agent="coordinator",
            to_agent="communicator",
            message={"type": "test", "content": "ping"}
        )
        results["basic_send"] = "OK" if result1["status"] == "sent" else "FAIL"
        
        # 测试2: 路由功能
        result2 = self.send_message(
            from_agent="monitor",
            to_agent="analyzer",
            message={"type": "test", "content": "route_test"}
        )
        results["routing"] = "OK" if result2["status"] == "sent" else "FAIL"
        
        # 测试3: 消息接收
        messages = self.receive_messages("communicator")
        results["receive"] = "OK" if isinstance(messages, list) else "FAIL"
        
        # 测试4: 统计功能
        stats = self.get_communication_stats()
        results["stats"] = "OK" if "stats" in stats else "FAIL"
        
        passed = sum(1 for v in results.values() if v == "OK")
        results["summary"] = f"{passed}/4 tests passed"
        
        return results
    
    def run(self):
        """运行Communicator Agent"""
        print(f"[Communicator] Agent运行中...")
        
        # 测试通信功能
        test_results = self.test_communication()
        
        print(f"[Communicator] 测试结果: {test_results['summary']}")
        
        # 输出通信统计
        stats = self.get_communication_stats()
        print(f"[Communicator] 📊 通信统计: {stats['stats']['messages_sent']} 发送, {stats['stats']['messages_received']} 接收")
        
        return test_results


if __name__ == "__main__":
    agent = CommunicatorAgent()
    result = agent.run()
    
    # 输出结果
    print("\n=== Communicator Agent Test Results ===")
    for k, v in result.items():
        print(f"  {k}: {v}")