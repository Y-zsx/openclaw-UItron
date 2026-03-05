#!/usr/bin/env python3
"""
跨维度智能交互网络 - 多协议适配器
Multi-Protocol Adapters

支持：WebSocket, HTTP, MQTT, gRPC
"""

import asyncio
import json
import time
import ssl
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger("ProtocolAdapters")


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class ProtocolMessage:
    """协议消息格式"""
    id: str
    type: str
    payload: Any
    metadata: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class ConnectionConfig:
    """连接配置"""
    host: str
    port: int
    ssl: bool = False
    timeout: int = 30
    retry_interval: int = 5
    max_retries: int = 10
    heartbeat_interval: int = 30


class ProtocolHandler(ABC):
    """协议处理器基类"""
    
    def __init__(self, config: ConnectionConfig):
        self.config = config
        self.state = ConnectionState.DISCONNECTED
        self.handlers: Dict[str, Callable] = {}
        self.heartbeat_task: Optional[asyncio.Task] = None
    
    @abstractmethod
    async def connect(self) -> bool:
        pass
    
    @abstractmethod
    async def disconnect(self):
        pass
    
    @abstractmethod
    async def send(self, message: ProtocolMessage) -> bool:
        pass
    
    @abstractmethod
    async def receive(self) -> Optional[ProtocolMessage]:
        pass
    
    def register_handler(self, msg_type: str, handler: Callable):
        self.handlers[msg_type] = handler
    
    async def start_heartbeat(self):
        """启动心跳"""
        async def heartbeat():
            while self.state == ConnectionState.CONNECTED:
                await asyncio.sleep(self.config.heartbeat_interval)
                await self.send(ProtocolMessage(
                    id="heartbeat",
                    type="heartbeat",
                    payload={"timestamp": time.time()}
                ))
        
        self.heartbeat_task = asyncio.create_task(heartbeat())
    
    async def stop_heartbeat(self):
        """停止心跳"""
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            try:
                await self.heartbeat_task
            except asyncio.CancelledError:
                pass


class WebSocketHandler(ProtocolHandler):
    """WebSocket协议处理器"""
    
    def __init__(self, config: ConnectionConfig, path: str = "/ws"):
        super().__init__(config)
        self.path = path
        self.ws = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
    
    async def connect(self) -> bool:
        self.state = ConnectionState.CONNECTING
        
        try:
            # 构建WebSocket URL
            scheme = "wss" if self.config.ssl else "ws"
            url = f"{scheme}://{self.config.host}:{self.config.port}{self.path}"
            
            # 使用asyncio创建WebSocket连接
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(
                    self.config.host,
                    self.config.port,
                    ssl=ssl.create_default_context() if self.config.ssl else None
                ),
                timeout=self.config.timeout
            )
            
            # 发送WebSocket握手
            await self._handshake(url)
            
            self.state = ConnectionState.CONNECTED
            await self.start_heartbeat()
            
            logger.info(f"WebSocket connected to {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    async def _handshake(self, url: str):
        """WebSocket握手"""
        import urllib.parse
        
        # 发送HTTP升级请求
        request = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.config.host}:{self.config.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: dGhlIHNhbXBsZSBub25jZQ==\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        
        self.writer.write(request.encode())
        await self.writer.drain()
        
        # 读取响应
        response = await self.reader.read(1024)
        logger.debug(f"WebSocket handshake response: {response[:200]}")
    
    async def disconnect(self):
        await self.stop_heartbeat()
        
        if self.writer:
            # 发送WebSocket关闭帧
            self.writer.write(b'\x88\x00')
            await self.writer.drain()
            self.writer.close()
            await self.writer.wait_closed()
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("WebSocket disconnected")
    
    async def send(self, message: ProtocolMessage) -> bool:
        if self.state != ConnectionState.CONNECTED:
            return False
        
        try:
            data = json.dumps({
                "id": message.id,
                "type": message.type,
                "payload": message.payload,
                "timestamp": message.timestamp
            })
            
            # 简单的文本帧
            frame = b'\x81' + bytes([len(data)]) + data.encode()
            self.writer.write(frame)
            await self.writer.drain()
            
            return True
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            return False
    
    async def receive(self) -> Optional[ProtocolMessage]:
        if self.state != ConnectionState.CONNECTED:
            return None
        
        try:
            # 读取帧头
            header = await self.reader.read(2)
            if not header:
                return None
            
            opcode = header[0] & 0x0f
            length = header[1] & 0x7f
            
            # 处理关闭帧
            if opcode == 0x8:
                await self.disconnect()
                return None
            
            # 读取数据
            if length > 0:
                data = await self.reader.read(length)
                if opcode == 0x1:  # 文本帧
                    msg_data = json.loads(data.decode())
                    return ProtocolMessage(
                        id=msg_data.get("id", ""),
                        type=msg_data.get("type", ""),
                        payload=msg_data.get("payload"),
                        timestamp=msg_data.get("timestamp", time.time())
                    )
            
            return None
        except Exception as e:
            logger.error(f"WebSocket receive failed: {e}")
            return None


class HTTPHandler(ProtocolHandler):
    """HTTP协议处理器"""
    
    def __init__(self, config: ConnectionConfig, api_prefix: str = "/api"):
        super().__init__(config)
        self.api_prefix = api_prefix
        self.session = None
    
    async def connect(self) -> bool:
        self.state = ConnectionState.CONNECTING
        
        try:
            import aiohttp
            self.session = aiohttp.ClientSession()
            self.state = ConnectionState.CONNECTED
            logger.info(f"HTTP handler initialized: {self.config.host}:{self.config.port}")
            return True
        except Exception as e:
            logger.error(f"HTTP connection failed: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    async def disconnect(self):
        await self.stop_heartbeat()
        
        if self.session:
            await self.session.close()
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("HTTP session closed")
    
    async def send(self, message: ProtocolMessage) -> bool:
        if not self.session or self.state != ConnectionState.CONNECTED:
            return False
        
        try:
            url = f"http://{self.config.host}:{self.config.port}{self.api_prefix}/{message.type}"
            
            async with self.session.post(url, json=message.payload) as resp:
                return resp.status < 400
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            return False
    
    async def receive(self) -> Optional[ProtocolMessage]:
        """HTTP轮询方式接收消息"""
        # 在实际应用中，这里可能是webhook回调
        return None
    
    async def get(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """GET请求"""
        if not self.session:
            return None
        
        try:
            url = f"http://{self.config.host}:{self.config.port}{self.api_prefix}{endpoint}"
            async with self.session.get(url, params=params) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"HTTP GET failed: {e}")
            return None
    
    async def post(self, endpoint: str, data: Dict) -> Optional[Dict]:
        """POST请求"""
        if not self.session:
            return None
        
        try:
            url = f"http://{self.config.host}:{self.config.port}{self.api_prefix}{endpoint}"
            async with self.session.post(url, json=data) as resp:
                return await resp.json()
        except Exception as e:
            logger.error(f"HTTP POST failed: {e}")
            return None


class MQTTHandler(ProtocolHandler):
    """MQTT协议处理器"""
    
    def __init__(self, config: ConnectionConfig, client_id: str = "ultron"):
        super().__init__(config)
        self.client_id = client_id
        self.client = None
        self.subscriptions: Dict[str, int] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._callbacks: Dict[str, List[Callable]] = {}
    
    async def connect(self) -> bool:
        self.state = ConnectionState.CONNECTING
        
        try:
            import paho.mqtt.client as mqtt
            
            self.client = mqtt.Client(client_id=self.client_id)
            self.client.on_connect = self._on_connect
            self.client.on_message = self._on_message
            self.client.on_disconnect = self._on_disconnect
            
            # 连接
            self.client.connect(
                self.config.host,
                self.config.port,
                keepalive=self.config.heartbeat_interval
            )
            
            # 启动循环
            self.client.loop_start()
            
            # 等待连接
            await asyncio.sleep(1)
            
            self.state = ConnectionState.CONNECTED
            await self.start_heartbeat()
            
            logger.info(f"MQTT connected to {self.config.host}:{self.config.port}")
            return True
            
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("MQTT connected successfully")
        else:
            logger.error(f"MQTT connection failed with code {rc}")
    
    def _on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            asyncio.create_task(self.message_queue.put({
                "topic": msg.topic,
                "payload": payload
            }))
        except Exception as e:
            logger.error(f"MQTT message parse error: {e}")
    
    def _on_disconnect(self, client, userdata, rc):
        logger.warning(f"MQTT disconnected: {rc}")
    
    async def disconnect(self):
        await self.stop_heartbeat()
        
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("MQTT disconnected")
    
    async def send(self, message: ProtocolMessage) -> bool:
        if not self.client or self.state != ConnectionState.CONNECTED:
            return False
        
        try:
            topic = f"ultron/{message.type}"
            payload = json.dumps({
                "id": message.id,
                "payload": message.payload,
                "timestamp": message.timestamp
            })
            
            result = self.client.publish(topic, payload)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            logger.error(f"MQTT publish failed: {e}")
            return False
    
    async def receive(self) -> Optional[ProtocolMessage]:
        try:
            msg = await asyncio.wait_for(
                self.message_queue.get(),
                timeout=1.0
            )
            
            payload = msg["payload"]
            return ProtocolMessage(
                id=payload.get("id", ""),
                type=msg["topic"].split("/")[-1],
                payload=payload.get("payload"),
                timestamp=payload.get("timestamp", time.time())
            )
        except asyncio.TimeoutError:
            return None
    
    def subscribe(self, topic: str, qos: int = 0):
        """订阅主题"""
        if self.client and self.state == ConnectionState.CONNECTED:
            self.client.subscribe(topic, qos)
            self.subscriptions[topic] = qos
    
    def add_callback(self, topic: str, callback: Callable):
        """添加消息回调"""
        if topic not in self._callbacks:
            self._callbacks[topic] = []
        self._callbacks[topic].append(callback)


class GRPCHandler(ProtocolHandler):
    """gRPC协议处理器"""
    
    def __init__(self, config: ConnectionConfig, proto_file: str = None):
        super().__init__(config)
        self.proto_file = proto_file
        self.channel = None
        self.stub = None
    
    async def connect(self) -> bool:
        self.state = ConnectionState.CONNECTING
        
        try:
            import grpc
            import aio.grpc
            
            # 创建channel
            target = f"{self.config.host}:{self.config.port}"
            self.channel = grpc.aio.insecure_channel(target)
            
            # 注意: 需要proto定义才能创建stub
            # 这里只是一个框架
            
            self.state = ConnectionState.CONNECTED
            await self.start_heartbeat()
            
            logger.info(f"gRPC channel created: {target}")
            return True
            
        except ImportError:
            logger.error("grpc library not installed")
            self.state = ConnectionState.ERROR
            return False
        except Exception as e:
            logger.error(f"gRPC connection failed: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    async def disconnect(self):
        await self.stop_heartbeat()
        
        if self.channel:
            await self.channel.close()
        
        self.state = ConnectionState.DISCONNECTED
        logger.info("gRPC channel closed")
    
    async def send(self, message: ProtocolMessage) -> bool:
        if not self.channel or self.state != ConnectionState.CONNECTED:
            return False
        
        # gRPC需要具体的service定义
        # 这里是一个通用框架
        try:
            # 示例调用
            # await self.stub.SendMessage(...)
            logger.debug(f"gRPC send: {message.type}")
            return True
        except Exception as e:
            logger.error(f"gRPC send failed: {e}")
            return False
    
    async def receive(self) -> Optional[ProtocolMessage]:
        # gRPC是双向流，这里是简化的实现
        return None


class ProtocolManager:
    """协议管理器 - 统一管理多协议"""
    
    def __init__(self):
        self.handlers: Dict[str, ProtocolHandler] = {}
        self.default_handler: Optional[ProtocolHandler] = None
    
    def register_handler(self, name: str, handler: ProtocolHandler):
        self.handlers[name] = handler
    
    def get_handler(self, name: str) -> Optional[ProtocolHandler]:
        return self.handlers.get(name)
    
    def set_default(self, name: str):
        self.default_handler = self.handlers.get(name)
    
    async def connect_all(self):
        """连接所有协议"""
        results = {}
        for name, handler in self.handlers.items():
            results[name] = await handler.connect()
        return results
    
    async def disconnect_all(self):
        """断开所有协议"""
        for handler in self.handlers.values():
            await handler.disconnect()
    
    def get_status(self) -> Dict[str, Any]:
        return {
            name: {
                "state": handler.state.value,
                "config": {
                    "host": handler.config.host,
                    "port": handler.config.port
                }
            }
            for name, handler in self.handlers.items()
        }


# 示例
if __name__ == "__main__":
    async def main():
        # 创建协议管理器
        pm = ProtocolManager()
        
        # 注册WebSocket
        ws_config = ConnectionConfig(
            host="localhost",
            port=8080,
            ssl=False,
            heartbeat_interval=30
        )
        pm.register_handler("websocket", WebSocketHandler(ws_config))
        
        # 注册HTTP
        http_config = ConnectionConfig(
            host="localhost",
            port=8081,
            heartbeat_interval=60
        )
        pm.register_handler("http", HTTPHandler(http_config))
        
        # 注册MQTT
        mqtt_config = ConnectionConfig(
            host="localhost",
            port=1883,
            heartbeat_interval=30
        )
        pm.register_handler("mqtt", MQTTHandler(mqtt_config))
        
        # 连接所有
        await pm.connect_all()
        
        # 发送消息
        ws = pm.get_handler("websocket")
        if ws:
            await ws.send(ProtocolMessage(
                id="test-1",
                type="chat",
                payload={"text": "Hello!"}
            ))
        
        # 断开所有
        await pm.disconnect_all()
    
    asyncio.run(main())