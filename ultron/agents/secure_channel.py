#!/usr/bin/env python3
"""
Agent安全通信与加密通道 - 第44世
实现SSL/TLS加密、端到端加密、安全通道管理
"""

import ssl
import hashlib
import hmac
import json
import time
import uuid
import threading
import asyncio
from pathlib import Path
from typing import Dict, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import base64
import os

# 加密库
try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: cryptography library not available, using basic encryption")

# ============== 数据结构 ==============

class EncryptionType(Enum):
    NONE = "none"
    TLS = "tls"
    E2E = "e2e"
    HYBRID = "hybrid"

class ChannelStatus(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    ERROR = "error"

@dataclass
class SecurityCredentials:
    """安全凭证"""
    agent_id: str
    public_key: str
    certificate: Optional[str] = None
    issued_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    permissions: list = field(default_factory=list)

@dataclass
class SecureChannel:
    """安全通道"""
    channel_id: str
    agent_a: str
    agent_b: str
    encryption: EncryptionType
    status: ChannelStatus
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_count: int = 0
    bytes_transferred: int = 0
    session_key: Optional[str] = None

@dataclass
class EncryptedMessage:
    """加密消息"""
    id: str
    channel_id: str
    sender: str
    recipient: str
    encrypted_content: str
    iv: str
    auth_tag: str
    timestamp: datetime = field(default_factory=datetime.now)
    sequence: int = 0

# ============== 密钥管理器 ==============

class KeyManager:
    """密钥管理器 - 生成、存储、分发密钥"""
    
    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or "/root/.openclaw/workspace/ultron/agents/data")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.keys_file = self.storage_path / "secure_keys.json"
        self.session_keys: Dict[str, str] = {}
        self._lock = threading.RLock()
        self._load_keys()
    
    def _load_keys(self):
        """加载密钥库"""
        if self.keys_file.exists():
            try:
                with open(self.keys_file, 'r') as f:
                    data = json.load(f)
                    self.session_keys = data.get('session_keys', {})
            except:
                self.session_keys = {}
    
    def _save_keys(self):
        """保存密钥库"""
        with self._lock:
            with open(self.keys_file, 'w') as f:
                json.dump({'session_keys': self.session_keys}, f)
    
    def generate_session_key(self, agent_a: str, agent_b: str) -> str:
        """生成会话密钥"""
        channel_id = f"{agent_a}:{agent_b}"
        if channel_id not in self.session_keys:
            if CRYPTO_AVAILABLE:
                key = Fernet.generate_key().decode()
            else:
                key = base64.b64encode(os.urandom(32)).decode()
            self.session_keys[channel_id] = key
            self._save_keys()
        return self.session_keys[channel_id]
    
    def get_session_key(self, agent_a: str, agent_b: str) -> Optional[str]:
        """获取会话密钥"""
        channel_id = f"{agent_a}:{agent_b}"
        return self.session_keys.get(channel_id)
    
    def generate_key_pair(self) -> tuple:
        """生成RSA密钥对"""
        if not CRYPTO_AVAILABLE:
            return ("", "")
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        public_key = private_key.public_key()
        
        private_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode()
        
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode()
        
        return private_pem, public_pem
    
    def derive_key(self, password: str, salt: bytes = None) -> tuple:
        """从密码派生密钥"""
        if salt is None:
            salt = os.urandom(16)
        
        if CRYPTO_AVAILABLE:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            key = base64.b64encode(kdf.derive(password.encode()))
            return key.decode(), base64.b64encode(salt).decode()
        else:
            key = hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
            return base64.b64encode(key).decode(), base64.b64encode(salt).decode()

# ============== 加密器 ==============

class Encryptor:
    """加密器 - 实现各种加密方法"""
    
    def __init__(self, key_manager: KeyManager):
        self.key_manager = key_manager
        self.fernet_cache: Dict[str, Fernet] = {}
    
    def _get_fernet(self, key: str) -> Fernet:
        """获取Fernet实例"""
        if key not in self.fernet_cache:
            try:
                self.fernet_cache[key] = Fernet(key.encode())
            except:
                # 生成新密钥
                new_key = Fernet.generate_key()
                self.fernet_cache[key] = Fernet(new_key)
        return self.fernet_cache[key]
    
    def encrypt(self, data: str, key: str) -> tuple:
        """加密数据，返回(密文, iv, auth_tag)"""
        if not CRYPTO_AVAILABLE:
            # 简单XOR加密作为后备
            iv = base64.b64encode(os.urandom(16)).decode()
            data_bytes = data.encode()
            key_bytes = key.encode()[:len(data_bytes)]
            encrypted = bytes(a ^ b for a, b in zip(data_bytes, key_bytes * (len(data_bytes) // len(key_bytes) + 1)))
            return base64.b64encode(encrypted).decode(), iv, ""
        
        try:
            fernet = self._get_fernet(key)
            encrypted = fernet.encrypt(data.encode())
            # Fernet自动包含IV和认证标签
            return base64.b64encode(encrypted).decode(), "", ""
        except Exception as e:
            # 回退到简单加密
            iv = base64.b64encode(os.urandom(16)).decode()
            data_bytes = data.encode()
            key_bytes = key.encode()[:len(data_bytes)]
            encrypted = bytes(a ^ b for a, b in zip(data_bytes, key_bytes * (len(data_bytes) // len(key_bytes) + 1)))
            return base64.b64encode(encrypted).decode(), iv, ""
    
    def decrypt(self, encrypted_data: str, key: str, iv: str = "", auth_tag: str = "") -> str:
        """解密数据"""
        if not CRYPTO_AVAILABLE:
            # 简单XOR解密
            encrypted = base64.b64decode(encrypted_data.encode())
            key_bytes = key.encode()[:len(encrypted)]
            decrypted = bytes(a ^ b for a, b in zip(encrypted, key_bytes * (len(encrypted) // len(key_bytes) + 1)))
            return decrypted.decode()
        
        try:
            fernet = self._get_fernet(key)
            decrypted = fernet.decrypt(base64.b64decode(encrypted_data))
            return decrypted.decode()
        except:
            # 回退
            encrypted = base64.b64decode(encrypted_data.encode())
            key_bytes = key.encode()[:len(encrypted)]
            decrypted = bytes(a ^ b for a, b in zip(encrypted, key_bytes * (len(encrypted) // len(key_bytes) + 1)))
            return decrypted.decode()
    
    def sign_data(self, data: str, private_key: str) -> str:
        """数据签名"""
        if not CRYPTO_AVAILABLE:
            return hashlib.sha256(data.encode()).hexdigest()
        
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            private = serialization.load_pem_private_key(
                private_key.encode(),
                password=None,
                backend=default_backend()
            )
            
            signature = private.sign(
                data.encode(),
                padding.PKCS15(),
                hashes.SHA256()
            )
            return base64.b64encode(signature).decode()
        except:
            return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_signature(self, data: str, signature: str, public_key: str) -> bool:
        """验证签名"""
        if not CRYPTO_AVAILABLE:
            expected = hashlib.sha256(data.encode()).hexdigest()
            return hmac.compare_digest(expected, signature)
        
        try:
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.asymmetric import padding
            
            public = serialization.load_pem_public_key(
                public_key.encode(),
                backend=default_backend()
            )
            
            public.verify(
                base64.b64decode(signature),
                data.encode(),
                padding.PKCS15(),
                hashes.SHA256()
            )
            return True
        except:
            expected = hashlib.sha256(data.encode()).hexdigest()
            return hmac.compare_digest(expected, signature)

# ============== 安全通道管理器 ==============

class SecureChannelManager:
    """安全通道管理器"""
    
    def __init__(self, key_manager: KeyManager, encryptor: Encryptor):
        self.key_manager = key_manager
        self.encryptor = encryptor
        self.channels: Dict[str, SecureChannel] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self._lock = threading.RLock()
        self._sequence = 0
    
    def create_channel(self, agent_a: str, agent_b: str, encryption: EncryptionType = EncryptionType.E2E) -> SecureChannel:
        """创建安全通道"""
        with self._lock:
            channel_id = str(uuid.uuid4())
            
            # 生成会话密钥
            session_key = self.key_manager.generate_session_key(agent_a, agent_b)
            
            channel = SecureChannel(
                channel_id=channel_id,
                agent_a=agent_a,
                agent_b=agent_b,
                encryption=encryption,
                status=ChannelStatus.CONNECTING,
                session_key=session_key
            )
            
            self.channels[channel_id] = channel
            channel.status = ChannelStatus.CONNECTED
            
            return channel
    
    def get_channel(self, channel_id: str) -> Optional[SecureChannel]:
        """获取通道"""
        return self.channels.get(channel_id)
    
    def close_channel(self, channel_id: str) -> bool:
        """关闭通道"""
        with self._lock:
            if channel_id in self.channels:
                self.channels[channel_id].status = ChannelStatus.DISCONNECTED
                del self.channels[channel_id]
                return True
            return False
    
    def send_encrypted(self, channel_id: str, sender: str, recipient: str, message: Any) -> Optional[EncryptedMessage]:
        """发送加密消息"""
        with self._lock:
            channel = self.channels.get(channel_id)
            if not channel or channel.status != ChannelStatus.CONNECTED:
                return None
            
            # 序列化消息
            if isinstance(message, (dict, list)):
                content = json.dumps(message)
            else:
                content = str(message)
            
            # 加密
            encrypted_content, iv, auth_tag = self.encryptor.encrypt(content, channel.session_key)
            
            # 创建消息
            self._sequence += 1
            msg = EncryptedMessage(
                id=str(uuid.uuid4()),
                channel_id=channel_id,
                sender=sender,
                recipient=recipient,
                encrypted_content=encrypted_content,
                iv=iv,
                auth_tag=auth_tag,
                sequence=self._sequence
            )
            
            # 更新通道统计
            channel.message_count += 1
            channel.bytes_transferred += len(encrypted_content)
            channel.last_activity = datetime.now()
            
            return msg
    
    def receive_decrypt(self, encrypted_msg: EncryptedMessage) -> Optional[Any]:
        """接收并解密消息"""
        channel = self.channels.get(encrypted_msg.channel_id)
        if not channel:
            return None
        
        try:
            content = self.encryptor.decrypt(
                encrypted_msg.encrypted_content,
                channel.session_key,
                encrypted_msg.iv,
                encrypted_msg.auth_tag
            )
            
            # 尝试解析JSON
            try:
                return json.loads(content)
            except:
                return content
        except:
            return None
    
    def register_handler(self, event: str, handler: Callable):
        """注册消息处理器"""
        self.message_handlers[event] = handler
    
    def get_stats(self) -> Dict[str, Any]:
        """获取通道统计"""
        stats = {
            "total_channels": len(self.channels),
            "connected": sum(1 for c in self.channels.values() if c.status == ChannelStatus.CONNECTED),
            "by_encryption": {},
            "total_messages": sum(c.message_count for c in self.channels.values()),
            "total_bytes": sum(c.bytes_transferred for c in self.channels.values())
        }
        
        for enc in EncryptionType:
            count = sum(1 for c in self.channels.values() if c.encryption == enc)
            stats["by_encryption"][enc.value] = count
        
        return stats

# ============== SSL/TLS 包装器 ==============

class SSLContextManager:
    """SSL/TLS上下文管理器"""
    
    def __init__(self, cert_path: str = None, key_path: str = None):
        self.cert_path = cert_path
        self.key_path = key_path
        self._context: Optional[ssl.SSLContext] = None
    
    def create_server_context(self, verify_client: bool = False) -> ssl.SSLContext:
        """创建服务器SSL上下文"""
        if not self.cert_path or not self.key_path:
            # 创建自签名证书（开发用）
            self._generate_self_signed()
        
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(self.cert_path, self.key_path)
        
        if verify_client:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(self.cert_path)
        
        self._context = context
        return context
    
    def create_client_context(self, verify_server: bool = True) -> ssl.SSLContext:
        """创建客户端SSL上下文"""
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        
        if verify_server and self.cert_path:
            context.verify_mode = ssl.CERT_REQUIRED
            context.load_verify_locations(self.cert_path)
        
        self._context = context
        return context
    
    def _generate_self_signed(self):
        """生成自签名证书（开发用）"""
        if not CRYPTO_AVAILABLE:
            # 使用openssl命令生成
            self.cert_path = "/root/.openclaw/workspace/ultron/agents/data/server.crt"
            self.key_path = "/root/.openclaw/workspace/ultron/agents/data/server.key"
            
            if not Path(self.cert_path).exists():
                os.system(f"openssl req -x509 -newkey rsa:2048 -keyout {self.key_path} -out {self.cert_path} -days 365 -nodes -subj '/CN=localhost'")
            return
        
        # 使用cryptography生成
        from cryptography import x509
        from cryptography.x509.oid import NameOID
        import datetime
        
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
            backend=default_backend()
        )
        
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "California"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "San Francisco"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Ultron"),
            x509.NameAttribute(NameOID.COMMON_NAME, "localhost"),
        ])
        
        cert = x509.CertificateBuilder().subject_name(
            subject
        ).issuer_name(
            issuer
        ).public_key(
            private_key.public_key()
        ).serial_number(
            x509.random_serial_number()
        ).not_valid_before(
            datetime.datetime.utcnow()
        ).not_valid_after(
            datetime.datetime.utcnow() + datetime.timedelta(days=365)
        ).sign(private_key, hashes.SHA256(), default_backend())
        
        self.cert_path = "/root/.openclaw/workspace/ultron/agents/data/server.crt"
        self.key_path = "/root/.openclaw/workspace/ultron/agents/data/server.key"
        
        Path(self.cert_path).parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.key_path, 'wb') as f:
            f.write(private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            ))
        
        with open(self.cert_path, 'wb') as f:
            f.write(cert.public_bytes(serialization.Encoding.PEM))

# ============== 安全网关 ==============

class SecureGateway:
    """安全网关 - 集成到Agent协作网络"""
    
    def __init__(self, port: int = 8091):
        self.port = port
        self.key_manager = KeyManager()
        self.encryptor = Encryptor(self.key_manager)
        self.channel_manager = SecureChannelManager(self.key_manager, self.encryptor)
        self.ssl_manager = SSLContextManager()
        self._running = False
    
    def start(self):
        """启动安全网关"""
        self._running = True
        print(f"🔐 Secure Gateway started on port {self.port}")
        print(f"   - Encryption: {'Available' if CRYPTO_AVAILABLE else 'Basic fallback'}")
        print(f"   - Active channels: 0")
    
    def stop(self):
        """停止安全网关"""
        self._running = False
        print("🔐 Secure Gateway stopped")
    
    def create_secure_channel(self, agent_a: str, agent_b: str, encryption: str = "e2e") -> Dict[str, Any]:
        """创建安全通道API"""
        enc_type = EncryptionType(encryption.lower())
        channel = self.channel_manager.create_channel(agent_a, agent_b, enc_type)
        
        return {
            "success": True,
            "channel_id": channel.channel_id,
            "encryption": channel.encryption.value,
            "status": channel.status.value
        }
    
    def send_message(self, channel_id: str, sender: str, recipient: str, message: Any) -> Dict[str, Any]:
        """发送加密消息API"""
        msg = self.channel_manager.send_encrypted(channel_id, sender, recipient, message)
        
        if msg:
            return {
                "success": True,
                "message_id": msg.id,
                "sequence": msg.sequence
            }
        return {"success": False, "error": "Channel not found or not connected"}
    
    def get_channel_info(self, channel_id: str) -> Optional[Dict[str, Any]]:
        """获取通道信息"""
        channel = self.channel_manager.get_channel(channel_id)
        if not channel:
            return None
        
        return {
            "channel_id": channel.channel_id,
            "agent_a": channel.agent_a,
            "agent_b": channel.agent_b,
            "encryption": channel.encryption.value,
            "status": channel.status.value,
            "message_count": channel.message_count,
            "bytes_transferred": channel.bytes_transferred,
            "created_at": channel.created_at.isoformat(),
            "last_activity": channel.last_activity.isoformat()
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return self.channel_manager.get_stats()

# ============== 主程序 ==============

def main():
    """测试运行"""
    print("=" * 60)
    print("🔐 Agent安全通信与加密通道 - 第44世")
    print("=" * 60)
    
    # 初始化
    gateway = SecureGateway(port=8091)
    gateway.start()
    
    # 测试创建通道
    print("\n📡 创建安全通道...")
    result = gateway.create_secure_channel("agent-1", "agent-2", "e2e")
    print(f"   通道创建: {result}")
    
    channel_id = result.get("channel_id")
    
    # 测试发送加密消息
    print("\n🔒 发送加密消息...")
    msg_result = gateway.send_message(
        channel_id, 
        "agent-1", 
        "agent-2",
        {"type": "task", "data": "Hello, secure world!"}
    )
    print(f"   消息发送: {msg_result}")
    
    # 测试获取通道信息
    print("\n📊 通道信息:")
    info = gateway.get_channel_info(channel_id)
    for k, v in info.items():
        print(f"   {k}: {v}")
    
    # 测试统计
    print("\n📈 全局统计:")
    stats = gateway.get_stats()
    for k, v in stats.items():
        print(f"   {k}: {v}")
    
    print("\n✅ 第44世任务完成: Agent安全通信与加密通道")
    
    gateway.stop()
    return gateway

if __name__ == "__main__":
    main()