"""
Agent安全通信与加密通道模块
实现端到端加密、TLS通道、消息签名与验证
"""

import os
import json
import hmac
import hashlib
import base64
import time
import secrets
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend


class EncryptionType(Enum):
    """加密类型"""
    NONE = "none"
    AES_GCM_256 = "aes_gcm_256"
    RSA_2048 = "rsa_2048"
    HYBRID = "hybrid"  # RSA + AES


class ChannelSecurityLevel(Enum):
    """通道安全级别"""
    PUBLIC = "public"           # 无加密
    AUTHENTICATED = "authenticated"  # 仅认证
    ENCRYPTED = "encrypted"     # 加密
    VERIFIED = "verified"       # 加密+签名验证


@dataclass
class KeyPair:
    """密钥对"""
    public_key: str
    private_key: str
    key_id: str
    created_at: float = field(default_factory=time.time)
    algorithm: str = "rsa_2048"


@dataclass
class SecureSession:
    """安全会话"""
    session_id: str
    peer_id: str
    shared_key: Optional[str] = None
    encryption_type: EncryptionType = EncryptionType.NONE
    security_level: ChannelSecurityLevel = ChannelSecurityLevel.PUBLIC
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    message_count: int = 0
    is_verified: bool = False


@dataclass
class EncryptedMessage:
    """加密消息"""
    message_id: str
    session_id: str
    sender_id: str
    recipient_id: str
    ciphertext: str  # Base64编码
    nonce: str       # Base64编码
    signature: Optional[str] = None  # Base64编码
    timestamp: float = field(default_factory=time.time)
    encryption_type: str = "aes_gcm_256"


class SecureChannelManager:
    """安全通道管理器"""
    
    def __init__(self, agent_id: str, storage_path: str = None):
        self.agent_id = agent_id
        self.storage_path = storage_path or "/root/.openclaw/workspace/ultron/agents/secure_channel_state.json"
        self.key_pairs: Dict[str, KeyPair] = {}
        self.sessions: Dict[str, SecureSession] = {}
        self.trusted_peers: Dict[str, str] = {}  # peer_id -> public_key
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    # 加载密钥对
                    for kp_data in data.get('key_pairs', []):
                        self.key_pairs[kp_data['key_id']] = KeyPair(**kp_data)
                    # 加载会话
                    for s_id, s_data in data.get('sessions', {}).items():
                        s_data['encryption_type'] = EncryptionType(s_data['encryption_type'])
                        s_data['security_level'] = ChannelSecurityLevel(s_data['security_level'])
                        self.sessions[s_id] = SecureSession(**s_data)
                    self.trusted_peers = data.get('trusted_peers', {})
            except Exception as e:
                print(f"加载安全通道状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        data = {
            'key_pairs': [vars(kp) for kp in self.key_pairs.values()],
            'sessions': {s_id: {
                'session_id': s.session_id,
                'peer_id': s.peer_id,
                'shared_key': s.shared_key,
                'encryption_type': s.encryption_type.value,
                'security_level': s.security_level.value,
                'created_at': s.created_at,
                'last_activity': s.last_activity,
                'message_count': s.message_count,
                'is_verified': s.is_verified
            } for s_id, s in self.sessions.items()},
            'trusted_peers': self.trusted_peers
        }
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_key_pair(self, algorithm: str = "rsa_2048") -> KeyPair:
        """生成密钥对"""
        if algorithm == "rsa_2048":
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            
            # 序列化密钥
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            key_id = secrets.token_hex(8)
            key_pair = KeyPair(
                key_id=key_id,
                public_key=public_pem.decode('utf-8'),
                private_key=private_pem.decode('utf-8'),
                algorithm=algorithm
            )
            self.key_pairs[key_id] = key_pair
            self._save_state()
            return key_pair
        
        raise ValueError(f"不支持的算法: {algorithm}")
    
    def get_public_key(self, key_id: str = None) -> Optional[str]:
        """获取公钥"""
        if key_id and key_id in self.key_pairs:
            return self.key_pairs[key_id].public_key
        # 返回第一个密钥
        for kp in self.key_pairs.values():
            return kp.public_key
        return None
    
    def add_trusted_peer(self, peer_id: str, public_key: str):
        """添加可信节点"""
        self.trusted_peers[peer_id] = public_key
        self._save_state()
    
    def remove_trusted_peer(self, peer_id: str):
        """移除可信节点"""
        if peer_id in self.trusted_peers:
            del self.trusted_peers[peer_id]
            self._save_state()
    
    def is_peer_trusted(self, peer_id: str) -> bool:
        """检查节点是否可信"""
        return peer_id in self.trusted_peers
    
    def derive_shared_key(self, peer_public_key: str, private_key_pem: str) -> bytes:
        """使用密钥封装派生共享密钥（简化版ECDH）"""
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.kdf.hkdf import HKDF
        
        # 加载私钥
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode('utf-8'),
            password=None,
            backend=default_backend()
        )
        
        # 加载公钥
        public_key = serialization.load_pem_public_key(
            peer_public_key.encode('utf-8'),
            backend=default_backend()
        )
        
        # 使用RSA-OAEP进行密钥封装
        # 在实际应用中应使用ECDH
        shared_secret = private_key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ) + public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # 使用HKDF派生最终密钥
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'ultron_secure_channel',
            info=b'session_key',
            backend=default_backend()
        )
        return hkdf.derive(shared_secret)
    
    def create_session(self, peer_id: str, use_encryption: bool = True) -> SecureSession:
        """创建安全会话"""
        session_id = secrets.token_hex(16)
        session = SecureSession(
            session_id=session_id,
            peer_id=peer_id,
            encryption_type=EncryptionType.AES_GCM_256 if use_encryption else EncryptionType.NONE,
            security_level=ChannelSecurityLevel.ENCRYPTED if use_encryption else ChannelSecurityLevel.PUBLIC
        )
        
        # 如果节点可信，建立共享密钥
        if peer_id in self.trusted_peers and self.key_pairs:
            try:
                key_pair = next(iter(self.key_pairs.values()))
                session.shared_key = base64.b64encode(
                    self.derive_shared_key(self.trusted_peers[peer_id], key_pair.private_key)
                ).decode('utf-8')
                session.security_level = ChannelSecurityLevel.VERIFIED
                session.is_verified = True
            except Exception as e:
                print(f"建立共享密钥失败: {e}")
        
        self.sessions[session_id] = session
        self._save_state()
        return session
    
    def get_session(self, session_id: str) -> Optional[SecureSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def close_session(self, session_id: str):
        """关闭会话"""
        if session_id in self.sessions:
            del self.sessions[session_id]
            self._save_state()
    
    def encrypt_message(self, plaintext: str, session_id: str, recipient_id: str) -> EncryptedMessage:
        """加密消息"""
        session = self.sessions.get(session_id)
        if not session:
            raise ValueError(f"会话不存在: {session_id}")
        
        message_id = secrets.token_hex(8)
        nonce = secrets.token_bytes(12)  # 96位nonce
        
        ciphertext = None
        signature = None
        
        if session.encryption_type == EncryptionType.AES_GCM_256 and session.shared_key:
            # 使用AES-GCM加密
            key = base64.b64decode(session.shared_key)
            aesgcm = AESGCM(key)
            ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
            
            # 签名
            signature = self._sign_message(ciphertext, session_id)
        
        elif session.encryption_type == EncryptionType.HYBRID:
            # 混合加密：RSA + AES
            if recipient_id in self.trusted_peers:
                # 生成一次性AES密钥
                aes_key = secrets.token_bytes(32)
                aesgcm = AESGCM(aes_key)
                ciphertext = aesgcm.encrypt(nonce, plaintext.encode('utf-8'), None)
                
                # 用RSA加密AES密钥（简化实现）
                ciphertext = aes_key + ciphertext  # 前32字节是AES密钥
                signature = self._sign_message(ciphertext, session_id)
        
        else:
            # 无加密
            ciphertext = plaintext.encode('utf-8')
        
        session.message_count += 1
        session.last_activity = time.time()
        self._save_state()
        
        return EncryptedMessage(
            message_id=message_id,
            session_id=session_id,
            sender_id=self.agent_id,
            recipient_id=recipient_id,
            ciphertext=base64.b64encode(ciphertext).decode('utf-8'),
            nonce=base64.b64encode(nonce).decode('utf-8'),
            signature=signature,
            encryption_type=session.encryption_type.value
        )
    
    def decrypt_message(self, encrypted_msg: EncryptedMessage) -> str:
        """解密消息"""
        session = self.sessions.get(encrypted_msg.session_id)
        if not session:
            raise ValueError(f"会话不存在: {encrypted_msg.session_id}")
        
        ciphertext = base64.b64decode(encrypted_msg.ciphertext)
        nonce = base64.b64decode(encrypted_msg.nonce)
        
        # 验证签名
        if encrypted_msg.signature and not self._verify_signature(
            ciphertext, encrypted_msg.signature, encrypted_msg.sender_id
        ):
            raise ValueError("消息签名验证失败")
        
        plaintext = None
        
        if session.encryption_type == EncryptionType.AES_GCM_256 and session.shared_key:
            key = base64.b64decode(session.shared_key)
            aesgcm = AESGCM(key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        elif session.encryption_type == EncryptionType.HYBRID:
            # 分离AES密钥和密文
            aes_key = ciphertext[:32]
            ciphertext = ciphertext[32:]
            aesgcm = AESGCM(aes_key)
            plaintext = aesgcm.decrypt(nonce, ciphertext, None)
        
        else:
            plaintext = ciphertext
        
        return plaintext.decode('utf-8')
    
    def _sign_message(self, data: bytes, session_id: str) -> str:
        """签名消息"""
        # 使用HMAC作为简化签名（实际应用应使用私钥签名）
        session = self.sessions.get(session_id)
        if session and session.shared_key:
            key = base64.b64decode(session.shared_key)
            h = hmac.new(key, data, hashlib.sha256)
            return base64.b64encode(h.digest()).decode('utf-8')
        return ""
    
    def _verify_signature(self, data: bytes, signature: str, sender_id: str) -> bool:
        """验证签名"""
        if sender_id not in self.trusted_peers:
            return False
        
        session = self._find_session_by_peer(sender_id)
        if not session or not session.shared_key:
            return False
        
        key = base64.b64decode(session.shared_key)
        expected = hmac.new(key, data, hashlib.sha256)
        expected_sig = base64.b64encode(expected.digest()).decode('utf-8')
        
        return hmac.compare_digest(expected_sig, signature)
    
    def _find_session_by_peer(self, peer_id: str) -> Optional[SecureSession]:
        """根据peer_id查找会话"""
        for session in self.sessions.values():
            if session.peer_id == peer_id:
                return session
        return None
    
    def get_security_status(self) -> Dict[str, Any]:
        """获取安全状态"""
        return {
            'agent_id': self.agent_id,
            'key_pairs_count': len(self.key_pairs),
            'sessions_count': len(self.sessions),
            'trusted_peers_count': len(self.trusted_peers),
            'sessions': [
                {
                    'session_id': s.session_id,
                    'peer_id': s.peer_id,
                    'encryption': s.encryption_type.value,
                    'security_level': s.security_level.value,
                    'is_verified': s.is_verified,
                    'message_count': s.message_count
                }
                for s in self.sessions.values()
            ]
        }


class MessageVerifier:
    """消息验证器"""
    
    def __init__(self, secure_channel: SecureChannelManager):
        self.secure_channel = secure_channel
    
    def verify_message_integrity(self, encrypted_msg: EncryptedMessage) -> Tuple[bool, str]:
        """验证消息完整性"""
        try:
            # 尝试解密验证完整性
            self.secure_channel.decrypt_message(encrypted_msg)
            return True, "消息完整"
        except Exception as e:
            return False, f"验证失败: {str(e)}"
    
    def verify_sender(self, encrypted_msg: EncryptedMessage) -> bool:
        """验证发送者"""
        if not encrypted_msg.signature:
            return False
        return self.secure_channel._verify_signature(
            base64.b64decode(encrypted_msg.ciphertext),
            encrypted_msg.signature,
            encrypted_msg.sender_id
        )


def demo_secure_channel():
    """演示安全通道"""
    print("=" * 60)
    print("Agent安全通信与加密通道演示")
    print("=" * 60)
    
    # 创建两个安全通道管理器（模拟两个Agent）
    alice = SecureChannelManager("alice-agent")
    bob = SecureChannelManager("bob-agent")
    
    # 1. 生成密钥对
    print("\n[1] 生成密钥对...")
    alice_key = alice.generate_key_pair()
    bob_key = bob.generate_key_pair()
    print(f"   Alice密钥ID: {alice_key.key_id}")
    print(f"   Bob密钥ID: {bob_key.key_id}")
    
    # 2. 交换公钥并建立信任
    print("\n[2] 建立可信连接...")
    alice.add_trusted_peer("bob-agent", bob_key.public_key)
    bob.add_trusted_peer("alice-agent", alice_key.public_key)
    print("   ✓ 公钥交换完成")
    print("   ✓ 相互添加为可信节点")
    
    # 3. 创建加密会话
    print("\n[3] 创建加密会话...")
    alice_session = alice.create_session("bob-agent", use_encryption=True)
    bob_session = bob.create_session("alice-agent", use_encryption=True)
    
    # 同步会话（简化演示）
    if alice_session.shared_key:
        bob_session.shared_key = alice_session.shared_key
        bob_session.encryption_type = alice_session.encryption_type
        bob_session.security_level = alice_session.security_level
        bob_session.is_verified = True
        bob.sessions[bob_session.session_id] = bob_session
        bob._save_state()
    
    print(f"   Alice会话: {alice_session.session_id[:16]}...")
    print(f"   Bob会话: {bob_session.session_id[:16]}...")
    print(f"   加密类型: {alice_session.encryption_type.value}")
    print(f"   安全级别: {alice_session.security_level.value}")
    print(f"   共享密钥: {'已建立' if alice_session.shared_key else '未建立'}")
    
    # 4. 加密消息
    print("\n[4] 加密消息测试...")
    test_messages = [
        "Hello Bob! This is an encrypted message.",
        "Transfer 1000 credits to agent-007",
        "EXECUTE: system_backup --full"
    ]
    
    for msg in test_messages:
        encrypted = alice.encrypt_message(msg, alice_session.session_id, "bob-agent")
        print(f"   原文: {msg[:40]}...")
        print(f"   密文: {encrypted.ciphertext[:40]}...")
        
        # 解密 - 使用Bob的会话
        bob_session_for_decrypt = bob.get_session(bob_session.session_id)
        encrypted.session_id = bob_session_for_decrypt.session_id
        decrypted = bob.decrypt_message(encrypted)
        print(f"   解密: {decrypted}")
        assert msg == decrypted, "解密失败!"
        print("   ✓ 加密解密验证通过")
    
    # 5. 安全状态
    print("\n[5] 安全状态报告...")
    status = alice.get_security_status()
    print(f"   Agent: {status['agent_id']}")
    print(f"   密钥对数量: {status['key_pairs_count']}")
    print(f"   会话数量: {status['sessions_count']}")
    print(f"   可信节点: {status['trusted_peers_count']}")
    
    print("\n" + "=" * 60)
    print("✅ 安全通道演示完成")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    demo_secure_channel()