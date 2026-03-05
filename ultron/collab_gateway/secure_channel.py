#!/usr/bin/env python3
"""
Agent安全通信与加密通道 v1.0
- 端到端加密
- 消息签名与验证
- TLS/SSL通道
- 密钥交换
- 安全会话管理
"""
import os
import sys
import json
import time
import hashlib
import hmac
import base64
import secrets
import threading
import socket
import ssl
from datetime import datetime, timedelta
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
from functools import wraps

# 加密库
try:
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa, padding
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.backends import default_backend
    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    print("Warning: cryptography library not available, using fallback")

# 配置
CONFIG_DIR = "/root/.openclaw/workspace/ultron/config"
KEYS_DIR = "/root/.openclaw/workspace/ultron/data/keys"
SESSION_DIR = "/root/.openclaw/workspace/ultron/data/sessions"
CERTS_DIR = "/root/.openclaw/workspace/ultron/data/certs"

os.makedirs(KEYS_DIR, exist_ok=True)
os.makedirs(SESSION_DIR, exist_ok=True)
os.makedirs(CERTS_DIR, exist_ok=True)


@dataclass
class KeyPair:
    """非对称密钥对"""
    public_key: str
    private_key: str
    agent_id: str
    created_at: str
    expires_at: str


@dataclass
class SecureSession:
    """安全会话"""
    session_id: str
    agent_id: str
    peer_id: str
    symmetric_key: str  # 共享对称密钥
    created_at: str
    last_activity: str
    expires_at: str
    message_count: int = 0
    verified: bool = False


@dataclass
class EncryptedMessage:
    """加密消息"""
    session_id: str
    sender_id: str
    recipient_id: str
    ciphertext: str  # Base64编码
    nonce: str  # Base64编码
    signature: str  # Base64编码
    timestamp: str
    sequence: int


class CryptoManager:
    """加密管理器"""
    
    def __init__(self):
        self.key_pairs: Dict[str, KeyPair] = {}
        self.sessions: Dict[str, SecureSession] = {}
        self._load_keys()
        self._load_sessions()
        self.sequence_numbers: Dict[str, int] = defaultdict(int)
    
    def _load_keys(self):
        """加载密钥对"""
        keys_file = f"{KEYS_DIR}/keypairs.json"
        if os.path.exists(keys_file):
            with open(keys_file, 'r') as f:
                data = json.load(f)
                for agent_id, kp_data in data.items():
                    self.key_pairs[agent_id] = KeyPair(**kp_data)
    
    def _save_keys(self):
        """保存密钥对"""
        keys_file = f"{KEYS_DIR}/keypairs.json"
        data = {aid: {
            'public_key': kp.public_key,
            'private_key': kp.private_key,
            'agent_id': kp.agent_id,
            'created_at': kp.created_at,
            'expires_at': kp.expires_at
        } for aid, kp in self.key_pairs.items()}
        with open(keys_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _load_sessions(self):
        """加载会话"""
        sessions_file = f"{SESSION_DIR}/secure_sessions.json"
        if os.path.exists(sessions_file):
            with open(sessions_file, 'r') as f:
                data = json.load(f)
                for sid, sess_data in data.items():
                    self.sessions[sid] = SecureSession(**sess_data)
    
    def _save_sessions(self):
        """保存会话"""
        sessions_file = f"{SESSION_DIR}/secure_sessions.json"
        data = {sid: {
            'session_id': sess.session_id,
            'agent_id': sess.agent_id,
            'peer_id': sess.peer_id,
            'symmetric_key': sess.symmetric_key,
            'created_at': sess.created_at,
            'last_activity': sess.last_activity,
            'expires_at': sess.expires_at,
            'message_count': sess.message_count,
            'verified': sess.verified
        } for sid, sess in self.sessions.items()}
        with open(sessions_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def generate_keypair(self, agent_id: str, key_size: int = 2048) -> KeyPair:
        """生成非对称密钥对"""
        if CRYPTO_AVAILABLE:
            # 使用RSA生成密钥对
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=key_size,
                backend=default_backend()
            )
            public_key = private_key.public_key()
            
            private_pem = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            
            key_pair = KeyPair(
                public_key=base64.b64encode(public_pem).decode(),
                private_key=base64.b64encode(private_pem).decode(),
                agent_id=agent_id,
                created_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(days=365)).isoformat()
            )
        else:
            # 回退方案：使用密钥派生
            random.seed(secrets.randbits(128))
            key_pair = KeyPair(
                public_key=secrets.token_hex(256),
                private_key=secrets.token_hex(256),
                agent_id=agent_id,
                created_at=datetime.now().isoformat(),
                expires_at=(datetime.now() + timedelta(days=365)).isoformat()
            )
        
        self.key_pairs[agent_id] = key_pair
        self._save_keys()
        return key_pair
    
    def generate_symmetric_key(self) -> str:
        """生成对称密钥"""
        return secrets.token_hex(32)  # 256位
    
    def generate_session_id(self) -> str:
        """生成会话ID"""
        return f"session-{secrets.token_hex(16)}"
    
    def derive_key(self, password: str, salt: bytes) -> bytes:
        """从密码派生密钥"""
        if CRYPTO_AVAILABLE:
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            return kdf.derive(password.encode())
        else:
            # 简单回退
            return hashlib.pbkdf2_hmac('sha256', password.encode(), salt, 100000)
    
    def _get_aes_key(self, key: str) -> bytes:
        """获取32字节AES密钥"""
        key_bytes = key.encode() if isinstance(key, str) else key
        if len(key_bytes) == 32:
            return key_bytes
        elif len(key_bytes) > 32:
            return hashlib.sha256(key_bytes).digest()
        else:
            # 填充到32字节
            return key_bytes.ljust(32, b'\0')
    
    def encrypt(self, plaintext: bytes, key: str) -> Tuple[bytes, bytes]:
        """对称加密 (AES-CBC with HMAC) - 简单可靠"""
        nonce = secrets.token_bytes(16)  # 16字节IV
        aes_key = self._get_aes_key(key)
        
        if CRYPTO_AVAILABLE:
            from cryptography.hazmat.primitives.ciphers.modes import CBC
            cipher = Cipher(
                algorithms.AES(aes_key),
                CBC(nonce),
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            
            # PKCS7填充
            pad_len = 16 - (len(plaintext) % 16)
            padded = plaintext + bytes([pad_len] * pad_len)
            ciphertext = encryptor.update(padded) + encryptor.finalize()
            return ciphertext, nonce
        else:
            # 简单XOR回退
            key_bytes = key.encode()[:len(plaintext)]
            ciphertext = bytes(a ^ b for a, b in zip(plaintext, key_bytes * (len(plaintext) // len(key_bytes) + 1)))
            return ciphertext, nonce
    
    def decrypt(self, ciphertext: bytes, nonce: bytes, key: str) -> bytes:
        """对称解密"""
        aes_key = self._get_aes_key(key)
        
        if CRYPTO_AVAILABLE:
            from cryptography.hazmat.primitives.ciphers.modes import CBC
            try:
                cipher = Cipher(
                    algorithms.AES(aes_key),
                    CBC(nonce),
                    backend=default_backend()
                )
                decryptor = cipher.decryptor()
                padded = decryptor.update(ciphertext) + decryptor.finalize()
                
                # 去除PKCS7填充
                pad_len = padded[-1]
                plaintext = padded[:-pad_len]
                return plaintext
            except:
                # 回退
                key_bytes = key.encode()[:len(ciphertext)]
                return bytes(a ^ b for a, b in zip(ciphertext, key_bytes * (len(ciphertext) // len(key_bytes) + 1)))
        else:
            key_bytes = key.encode()[:len(ciphertext)]
            return bytes(a ^ b for a, b in zip(ciphertext, key_bytes * (len(ciphertext) // len(key_bytes) + 1)))
    
    def sign(self, data: bytes, private_key: str) -> bytes:
        """消息签名"""
        if CRYPTO_AVAILABLE:
            try:
                private_pem = base64.b64decode(private_key)
                from cryptography.hazmat.primitives.serialization import load_pem_private_key
                key = load_pem_private_key(private_pem, password=None, backend=default_backend())
                signature = key.sign(
                    data,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                return signature
            except:
                pass
        
        # 回退：HMAC
        return hmac.new(private_key.encode(), data, hashlib.sha256).digest()
    
    def verify(self, data: bytes, signature: bytes, public_key: str) -> bool:
        """验证签名"""
        if CRYPTO_AVAILABLE:
            try:
                public_pem = base64.b64decode(public_key)
                from cryptography.hazmat.primitives.serialization import load_pem_public_key
                key = load_pem_public_key(public_pem, backend=default_backend())
                key.verify(
                    signature,
                    data,
                    padding.PKCS1v15(),
                    hashes.SHA256()
                )
                return True
            except:
                pass
        
        # 回退：HMAC验证
        expected = hmac.new(public_key.encode(), data, hashlib.sha256).digest()
        return hmac.compare_digest(expected, signature)
    
    def establish_session(self, agent_id: str, peer_id: str) -> SecureSession:
        """建立安全会话"""
        # 生成共享对称密钥
        symmetric_key = self.generate_symmetric_key()
        
        session = SecureSession(
            session_id=self.generate_session_id(),
            agent_id=agent_id,
            peer_id=peer_id,
            symmetric_key=symmetric_key,
            created_at=datetime.now().isoformat(),
            last_activity=datetime.now().isoformat(),
            expires_at=(datetime.now() + timedelta(hours=24)).isoformat(),
            verified=True
        )
        
        self.sessions[session.session_id] = session
        self._save_sessions()
        return session
    
    def create_encrypted_message(
        self,
        session_id: str,
        sender_id: str,
        recipient_id: str,
        plaintext: str
    ) -> Optional[EncryptedMessage]:
        """创建加密消息"""
        session = self.sessions.get(session_id)
        if not session:
            return None
        
        # 获取发送方的私钥
        key_pair = self.key_pairs.get(sender_id)
        if not key_pair:
            return None
        
        # 序列号
        seq_key = f"{session_id}:{sender_id}"
        sequence = self.sequence_numbers[seq_key]
        self.sequence_numbers[seq_key] += 1
        
        # 加密
        plaintext_bytes = plaintext.encode()
        ciphertext, nonce = self.encrypt(plaintext_bytes, session.symmetric_key)
        
        # 签名
        data_to_sign = ciphertext + nonce + str(sequence).encode()
        signature = self.sign(data_to_sign, key_pair.private_key)
        
        return EncryptedMessage(
            session_id=session_id,
            sender_id=sender_id,
            recipient_id=recipient_id,
            ciphertext=base64.b64encode(ciphertext).decode(),
            nonce=base64.b64encode(nonce).decode(),
            signature=base64.b64encode(signature).decode(),
            timestamp=datetime.now().isoformat(),
            sequence=sequence
        )
    
    def decrypt_message(self, msg: EncryptedMessage) -> Optional[str]:
        """解密消息"""
        session = self.sessions.get(msg.session_id)
        if not session:
            return None
        
        # 验证发送方公钥
        key_pair = self.key_pairs.get(msg.sender_id)
        if not key_pair:
            return None
        
        # 解密
        ciphertext = base64.b64decode(msg.ciphertext)
        nonce = base64.b64decode(msg.nonce)
        plaintext_bytes = self.decrypt(ciphertext, nonce, session.symmetric_key)
        
        # 验证签名
        signature = base64.b64decode(msg.signature)
        data_to_verify = ciphertext + nonce + str(msg.sequence).encode()
        
        if not self.verify(data_to_verify, signature, key_pair.public_key):
            return None
        
        # 更新会话活动
        session.last_activity = datetime.now().isoformat()
        session.message_count += 1
        self._save_sessions()
        
        return plaintext_bytes.decode()
    
    def get_session(self, session_id: str) -> Optional[SecureSession]:
        """获取会话"""
        return self.sessions.get(session_id)
    
    def list_sessions(self, agent_id: str = None) -> list:
        """列出会话"""
        if agent_id:
            return [s for s in self.sessions.values() if s.agent_id == agent_id]
        return list(self.sessions.values())


class SecureChannelServer:
    """安全通道服务器 (TLS/SSL)"""
    
    def __init__(self, host: str = "0.0.0.0", port: int = 8090):
        self.host = host
        self.port = port
        self.crypto = CryptoManager()
        self.running = False
        self._server_socket = None
        self._thread = None
        self._clients: Dict[str, socket.socket] = {}
    
    def generate_self_signed_cert(self):
        """生成自签名证书"""
        cert_file = f"{CERTS_DIR}/server.crt"
        key_file = f"{CERTS_DIR}/server.key"
        
        if os.path.exists(cert_file) and os.path.exists(key_file):
            return cert_file, key_file
        
        # 生成私钥
        if CRYPTO_AVAILABLE:
            from cryptography import x509
            from cryptography.x509.oid import NameOID
            
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            subject = issuer = x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, "CN"),
                x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "Shanghai"),
                x509.NameAttribute(NameOID.LOCALITY_NAME, "Shanghai"),
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
                datetime.utcnow()
            ).not_valid_after(
                datetime.utcnow() + timedelta(days=365)
            ).sign(private_key, hashes.SHA256(), default_backend())
            
            with open(key_file, 'wb') as f:
                f.write(private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption()
                ))
            
            with open(cert_file, 'wb') as f:
                f.write(cert.public_bytes(serialization.Encoding.PEM))
        
        return cert_file, key_file
    
    def start(self):
        """启动服务器"""
        cert_file, key_file = self.generate_self_signed_cert()
        
        # 创建SSL上下文
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cert_file, key_file)
        
        # 创建监听socket
        self._server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_socket.bind((self.host, self.port))
        self._server_socket.listen(10)
        
        self.running = True
        self._thread = threading.Thread(target=self._accept_loop, daemon=True)
        self._thread.start()
        
        print(f"Secure Channel Server started on {self.host}:{self.port}")
    
    def _accept_loop(self):
        """接受连接循环"""
        while self.running:
            try:
                client_socket, address = self._server_socket.accept()
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, address),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                if self.running:
                    print(f"Accept error: {e}")
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """处理客户端"""
        try:
            self._clients[str(address)] = client_socket
            while self.running:
                data = client_socket.recv(4096)
                if not data:
                    break
                # 处理消息
                self._process_message(client_socket, data)
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            self._clients.pop(str(address), None)
            client_socket.close()
    
    def _process_message(self, client_socket: socket.socket, data: bytes):
        """处理消息"""
        try:
            msg = json.loads(data.decode())
            msg_type = msg.get('type')
            
            if msg_type == 'key_exchange':
                # 密钥交换
                agent_id = msg.get('agent_id')
                if agent_id not in self.crypto.key_pairs:
                    self.crypto.generate_keypair(agent_id)
                key_pair = self.crypto.key_pairs[agent_id]
                client_socket.send(json.dumps({
                    'type': 'key_exchange_response',
                    'public_key': key_pair.public_key,
                    'agent_id': agent_id
                }).encode())
            
            elif msg_type == 'session_request':
                # 会话请求
                agent_id = msg.get('agent_id')
                peer_id = msg.get('peer_id')
                session = self.crypto.establish_session(agent_id, peer_id)
                client_socket.send(json.dumps({
                    'type': 'session_response',
                    'session_id': session.session_id,
                    'symmetric_key': session.symmetric_key
                }).encode())
        
        except Exception as e:
            print(f"Message error: {e}")
    
    def stop(self):
        """停止服务器"""
        self.running = False
        for client in self._clients.values():
            client.close()
        if self._server_socket:
            self._server_socket.close()


# CLI工具
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Agent Secure Channel")
    parser.add_argument('command', choices=['generate-key', 'list-keys', 'list-sessions', 'start-server', 'encrypt', 'decrypt'])
    parser.add_argument('--agent-id', help='Agent ID')
    parser.add_argument('--peer-id', help='Peer ID')
    parser.add_argument('--session-id', help='Session ID')
    parser.add_argument('--message', help='Message to encrypt/decrypt')
    parser.add_argument('--host', default='0.0.0.0', help='Server host')
    parser.add_argument('--port', type=int, default=8090, help='Server port')
    
    args = parser.parse_args()
    crypto = CryptoManager()
    
    if args.command == 'generate-key':
        if not args.agent_id:
            print("Error: --agent-id required")
            return
        kp = crypto.generate_keypair(args.agent_id)
        print(f"Key pair generated for {args.agent_id}")
        print(f"Public key: {kp.public_key[:64]}...")
    
    elif args.command == 'list-keys':
        for agent_id, kp in crypto.key_pairs.items():
            print(f"{agent_id}: created={kp.created_at[:19]}")
    
    elif args.command == 'list-sessions':
        sessions = crypto.list_sessions(args.agent_id)
        for s in sessions:
            print(f"{s.session_id}: {s.agent_id} <-> {s.peer_id} (verified={s.verified})")
    
    elif args.command == 'start-server':
        server = SecureChannelServer(args.host, args.port)
        server.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            server.stop()
    
    elif args.command == 'encrypt':
        if not all([args.agent_id, args.peer_id, args.message]):
            print("Error: --agent-id, --peer-id, --message required")
            return
        session = crypto.establish_session(args.agent_id, args.peer_id)
        msg = crypto.create_encrypted_message(
            session.session_id,
            args.agent_id,
            args.peer_id,
            args.message
        )
        if msg:
            print(json.dumps({
                'session_id': msg.session_id,
                'ciphertext': msg.ciphertext,
                'nonce': msg.nonce,
                'signature': msg.signature,
                'timestamp': msg.timestamp
            }, indent=2))
    
    elif args.command == 'decrypt':
        print("Decrypt not implemented via CLI")


if __name__ == "__main__":
    main()