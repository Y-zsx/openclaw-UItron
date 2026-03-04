#!/usr/bin/env python3
"""
跨维度智能交互网络 - 统一接口层
Multi-Platform Unified Interface Layer

功能：
- 统一API抽象
- 多协议适配器管理
- 跨平台认证
- 消息路由
"""

import json
import asyncio
import hashlib
import hmac
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
from dataclasses import dataclass, field
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("MultiPlatformInterface")


class Protocol(Enum):
    """支持的协议类型"""
    WEBSOCKET = "websocket"
    HTTP = "http"
    MQTT = "mqtt"
    GRPC = "grpc"
    WEBSOCKET_STREAM = "websocket_stream"


class Platform(Enum):
    """支持的平台"""
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    WHATSAPP = "whatsapp"
    DINGTALK = "dingtalk"
    SIGNAL = "signal"
    CUSTOM = "custom"


class MessageType(Enum):
    """消息类型"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    FILE = "file"
    BUTTON = "button"
    POLL = "poll"
    LOCATION = "location"
    COMMAND = "command"


@dataclass
class PlatformMessage:
    """统一消息格式"""
    message_id: str
    platform: Platform
    chat_id: str
    user_id: str
    message_type: MessageType
    content: Any
    raw_data: Dict = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


@dataclass
class PlatformConfig:
    """平台配置"""
    platform: Platform
    enabled: bool = True
    api_key: str = ""
    api_secret: str = ""
    webhook_url: str = ""
    bot_token: str = ""
    rate_limit: int = 30  # 每秒请求数
    timeout: int = 30


@dataclass 
class AuthToken:
    """认证令牌"""
    token: str
    platform: Platform
    user_id: str
    expires_at: float
    scopes: List[str] = field(default_factory=list)


class PlatformAdapter(ABC):
    """平台适配器基类"""
    
    def __init__(self, config: PlatformConfig):
        self.config = config
        self.connected = False
        self.message_handlers: List[Callable] = []
    
    @abstractmethod
    async def connect(self) -> bool:
        """建立连接"""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """断开连接"""
        pass
    
    @abstractmethod
    async def send_message(self, chat_id: str, content: Any, 
                          message_type: MessageType = MessageType.TEXT) -> bool:
        """发送消息"""
        pass
    
    @abstractmethod
    async def handle_incoming(self, data: Dict) -> Optional[PlatformMessage]:
        """处理接收的消息"""
        pass
    
    def register_handler(self, handler: Callable):
        """注册消息处理器"""
        self.message_handlers.append(handler)
    
    async def notify_handlers(self, message: PlatformMessage):
        """通知所有处理器"""
        for handler in self.message_handlers:
            try:
                await handler(message)
            except Exception as e:
                logger.error(f"Handler error: {e}")


class WebSocketAdapter(PlatformAdapter):
    """WebSocket协议适配器"""
    
    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.ws = None
        self.reconnect_interval = 5
        self.max_reconnect = 10
    
    async def connect(self) -> bool:
        """建立WebSocket连接"""
        try:
            import websockets
            self.ws = await websockets.connect(self.config.webhook_url)
            self.connected = True
            logger.info(f"WebSocket connected to {self.config.webhook_url}")
            asyncio.create_task(self._listen())
            return True
        except Exception as e:
            logger.error(f"WebSocket connection failed: {e}")
            return False
    
    async def disconnect(self):
        """断开WebSocket连接"""
        if self.ws:
            await self.ws.close()
        self.connected = False
    
    async def send_message(self, chat_id: str, content: Any,
                          message_type: MessageType = MessageType.TEXT) -> bool:
        """发送WebSocket消息"""
        if not self.connected:
            return False
        
        payload = {
            "action": "send",
            "chat_id": chat_id,
            "type": message_type.value,
            "content": content,
            "timestamp": time.time()
        }
        
        try:
            await self.ws.send(json.dumps(payload))
            return True
        except Exception as e:
            logger.error(f"WebSocket send failed: {e}")
            return False
    
    async def handle_incoming(self, data: Dict) -> Optional[PlatformMessage]:
        """处理WebSocket消息"""
        return PlatformMessage(
            message_id=data.get("id", ""),
            platform=Platform.CUSTOM,
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", ""),
            message_type=MessageType(data.get("type", "text")),
            content=data.get("content", ""),
            raw_data=data
        )
    
    async def _listen(self):
        """监听消息"""
        while self.connected and self.ws:
            try:
                async for message in self.ws:
                    data = json.loads(message)
                    msg = await self.handle_incoming(data)
                    if msg:
                        await self.notify_handlers(msg)
            except Exception as e:
                logger.error(f"WebSocket listen error: {e}")
                await asyncio.sleep(self.reconnect_interval)


class HTTPAdapter(PlatformAdapter):
    """HTTP协议适配器"""
    
    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.session = None
    
    async def connect(self) -> bool:
        """HTTP不需要主动连接"""
        import aiohttp
        self.session = aiohttp.ClientSession()
        self.connected = True
        logger.info("HTTP adapter initialized")
        return True
    
    async def disconnect(self):
        """断开HTTP会话"""
        if self.session:
            await self.session.close()
        self.connected = False
    
    async def send_message(self, chat_id: str, content: Any,
                          message_type: MessageType = MessageType.TEXT) -> bool:
        """发送HTTP请求"""
        if not self.session:
            return False
        
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "chat_id": chat_id,
            "type": message_type.value,
            "content": content
        }
        
        try:
            async with self.session.post(
                self.config.webhook_url,
                json=payload,
                headers=headers
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"HTTP send failed: {e}")
            return False
    
    async def handle_incoming(self, data: Dict) -> Optional[PlatformMessage]:
        """处理HTTP webhook"""
        return PlatformMessage(
            message_id=data.get("message_id", ""),
            platform=Platform.CUSTOM,
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", ""),
            message_type=MessageType(data.get("type", "text")),
            content=data.get("content", ""),
            raw_data=data
        )


class MQTTAdapter(PlatformAdapter):
    """MQTT协议适配器"""
    
    def __init__(self, config: PlatformConfig):
        super().__init__(config)
        self.client = None
        self.subscriptions = []
    
    async def connect(self) -> bool:
        """建立MQTT连接"""
        try:
            import paho.mqtt.client as mqtt
            self.client = mqtt.Client()
            
            # 设置认证
            if self.config.api_key:
                self.client.username_pw_set(
                    self.config.api_key, 
                    self.config.api_secret
                )
            
            # 连接 broker
            broker = self.config.webhook_url.replace("mqtt://", "").split(":")
            host = broker[0]
            port = int(broker[1]) if len(broker) > 1 else 1883
            
            self.client.connect(host, port, 60)
            self.client.loop_start()
            
            self.connected = True
            logger.info(f"MQTT connected to {host}:{port}")
            return True
        except Exception as e:
            logger.error(f"MQTT connection failed: {e}")
            return False
    
    async def disconnect(self):
        """断开MQTT连接"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
        self.connected = False
    
    async def send_message(self, chat_id: str, content: Any,
                          message_type: MessageType = MessageType.TEXT) -> bool:
        """发布MQTT消息"""
        if not self.client or not self.connected:
            return False
        
        topic = f"ultron/{chat_id}"
        payload = json.dumps({
            "type": message_type.value,
            "content": content,
            "timestamp": time.time()
        })
        
        try:
            self.client.publish(topic, payload)
            return True
        except Exception as e:
            logger.error(f"MQTT publish failed: {e}")
            return False
    
    def subscribe(self, topic: str):
        """订阅主题"""
        if self.client and self.connected:
            self.client.subscribe(topic)
            self.subscriptions.append(topic)
    
    async def handle_incoming(self, data: Dict) -> Optional[PlatformMessage]:
        """处理MQTT消息"""
        return PlatformMessage(
            message_id=data.get("id", ""),
            platform=Platform.CUSTOM,
            chat_id=data.get("chat_id", ""),
            user_id=data.get("user_id", ""),
            message_type=MessageType(data.get("type", "text")),
            content=data.get("content", ""),
            raw_data=data
        )


class CrossPlatformAuth:
    """跨平台认证系统"""
    
    def __init__(self, secret_key: str):
        self.secret_key = secret_key
        self.tokens: Dict[str, AuthToken] = {}
    
    def generate_token(self, platform: Platform, user_id: str, 
                      scopes: List[str] = None, ttl: int = 3600) -> str:
        """生成认证令牌"""
        payload = f"{platform.value}:{user_id}:{time.time()}:{json.dumps(scopes or [])}"
        signature = hmac.new(
            self.secret_key.encode(),
            payload.encode(),
            hashlib.sha256
        ).hexdigest()
        
        token = f"{payload}:{signature}"
        self.tokens[token] = AuthToken(
            token=token,
            platform=platform,
            user_id=user_id,
            expires_at=time.time() + ttl,
            scopes=scopes or []
        )
        
        return token
    
    def verify_token(self, token: str) -> Optional[AuthToken]:
        """验证令牌"""
        if token not in self.tokens:
            return None
        
        auth_token = self.tokens[token]
        if time.time() > auth_token.expires_at:
            del self.tokens[token]
            return None
        
        return auth_token
    
    def revoke_token(self, token: str):
        """撤销令牌"""
        if token in self.tokens:
            del self.tokens[token]
    
    def cleanup_expired(self):
        """清理过期令牌"""
        now = time.time()
        expired = [t for t, at in self.tokens.items() if now > at.expires_at]
        for t in expired:
            del self.tokens[t]


class MessageRouter:
    """消息路由器"""
    
    def __init__(self):
        self.routes: Dict[str, List[Callable]] = {}
        self.platform_handlers: Dict[Platform, Callable] = {}
        self.default_handler: Optional[Callable] = None
    
    def add_route(self, pattern: str, handler: Callable):
        """添加路由规则"""
        if pattern not in self.routes:
            self.routes[pattern] = []
        self.routes[pattern].append(handler)
    
    def set_platform_handler(self, platform: Platform, handler: Callable):
        """设置平台特定处理器"""
        self.platform_handlers[platform] = handler
    
    def set_default(self, handler: Callable):
        """设置默认处理器"""
        self.default_handler = handler
    
    async def route(self, message: PlatformMessage):
        """路由消息"""
        # 平台特定处理器
        if message.platform in self.platform_handlers:
            await self.platform_handlers[message.platform](message)
            return
        
        # 模式匹配
        content_str = str(message.content)
        for pattern, handlers in self.routes.items():
            if pattern in content_str:
                for handler in handlers:
                    await handler(message)
                return
        
        # 默认处理器
        if self.default_handler:
            await self.default_handler(message)


class MultiPlatformInterface:
    """统一接口管理器"""
    
    def __init__(self, secret_key: str):
        self.adapters: Dict[Platform, PlatformAdapter] = {}
        self.configs: Dict[Platform, PlatformConfig] = {}
        self.auth = CrossPlatformAuth(secret_key)
        self.router = MessageRouter()
        self.running = False
    
    def register_platform(self, config: PlatformConfig):
        """注册平台"""
        self.configs[config.platform] = config
        
        # 根据协议创建适配器
        if config.platform == Platform.CUSTOM:
            # 自定义平台，默认用HTTP
            adapter = HTTPAdapter(config)
        else:
            # 其他平台使用HTTP作为默认
            adapter = HTTPAdapter(config)
        
        self.adapters[config.platform] = adapter
    
    async def start(self):
        """启动所有平台连接"""
        self.running = True
        
        for platform, adapter in self.adapters.items():
            config = self.configs.get(platform)
            if config and config.enabled:
                await adapter.connect()
        
        logger.info(f"Started {len(self.adapters)} platform adapters")
    
    async def stop(self):
        """停止所有平台连接"""
        self.running = False
        
        for adapter in self.adapters.values():
            await adapter.disconnect()
        
        logger.info("All platform adapters stopped")
    
    async def send_to_platform(self, platform: Platform, chat_id: str,
                               content: Any, message_type: MessageType = MessageType.TEXT) -> bool:
        """向指定平台发送消息"""
        adapter = self.adapters.get(platform)
        if not adapter or not adapter.connected:
            logger.warning(f"Platform {platform} not available")
            return False
        
        return await adapter.send_message(chat_id, content, message_type)
    
    async def broadcast(self, platforms: List[Platform], chat_ids: List[str],
                       content: Any, message_type: MessageType = MessageType.TEXT) -> Dict[Platform, bool]:
        """广播到多个平台"""
        results = {}
        
        tasks = []
        for platform in platforms:
            task = self.send_to_platform(platform, chat_ids[platforms.index(platform)] if platforms.index(platform) < len(chat_ids) else "", content, message_type)
            tasks.append((platform, task))
        
        for platform, task in tasks:
            results[platform] = await task
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "running": self.running,
            "platforms": {
                platform.value: {
                    "enabled": config.enabled,
                    "connected": adapter.connected
                }
                for platform, (config, adapter) in enumerate(zip(self.configs.values(), self.adapters.values()))
            },
            "active_tokens": len(self.auth.tokens)
        }


# 示例用法
if __name__ == "__main__":
    async def main():
        # 创建接口管理器
        interface = MultiPlatformInterface(secret_key="ultron-secret-key")
        
        # 注册平台配置
        interface.register_platform(PlatformConfig(
            platform=Platform.TELEGRAM,
            enabled=True,
            api_key="telegram-bot-token",
            webhook_url="https://api.telegram.org/bot<token>/sendMessage"
        ))
        
        interface.register_platform(PlatformConfig(
            platform=Platform.DISCORD,
            enabled=True,
            api_key="discord-bot-token",
            webhook_url="https://discord.com/api/webhooks/xxx"
        ))
        
        # 启动
        await interface.start()
        
        # 发送消息
        await interface.send_to_platform(
            Platform.TELEGRAM,
            "chat123",
            "Hello from multi-platform interface!"
        )
        
        # 停止
        await interface.stop()
    
    asyncio.run(main())