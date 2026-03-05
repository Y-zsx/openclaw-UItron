#!/usr/bin/env python3
"""
安全通道REST API服务
端口: 8090
"""
import os
import sys
import json
import time
import hashlib
import hmac
import base64
import secrets
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import ssl

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from collab_gateway.secure_channel import CryptoManager, SecureSession, EncryptedMessage

PORT = 8090
CONFIG_DIR = "/root/.openclaw/workspace/ultron/config"


class SecureChannelHandler(BaseHTTPRequestHandler):
    """HTTP请求处理器"""
    
    crypto = CryptoManager()
    
    def _set_headers(self, status=200, content_type='application/json'):
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('X-Frame-Options', 'DENY')
        self.end_headers()
    
    def _read_json(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length > 0:
            return json.loads(self.rfile.read(content_length).decode())
        return {}
    
    def _json_response(self, data, status=200):
        self._set_headers(status)
        self.wfile.write(json.dumps(data, indent=2, ensure_ascii=False).encode())
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/health':
            self._json_response({'status': 'ok', 'service': 'secure-channel'})
        
        elif path == '/keys':
            # 列出所有密钥
            keys = []
            for agent_id, kp in self.crypto.key_pairs.items():
                keys.append({
                    'agent_id': agent_id,
                    'created_at': kp.created_at,
                    'expires_at': kp.expires_at
                })
            self._json_response({'keys': keys, 'count': len(keys)})
        
        elif path == '/sessions':
            # 列出会话
            agent_id = params.get('agent_id', [None])[0]
            sessions = self.crypto.list_sessions(agent_id)
            self._json_response({
                'sessions': [{
                    'session_id': s.session_id,
                    'agent_id': s.agent_id,
                    'peer_id': s.peer_id,
                    'created_at': s.created_at,
                    'last_activity': s.last_activity,
                    'message_count': s.message_count,
                    'verified': s.verified
                } for s in sessions],
                'count': len(sessions)
            })
        
        elif path == '/session':
            # 获取特定会话
            session_id = params.get('session_id', [None])[0]
            if session_id:
                session = self.crypto.get_session(session_id)
                if session:
                    self._json_response({
                        'session_id': session.session_id,
                        'agent_id': session.agent_id,
                        'peer_id': session.peer_id,
                        'created_at': session.created_at,
                        'last_activity': session.last_activity,
                        'message_count': session.message_count,
                        'verified': session.verified
                    })
                else:
                    self._json_response({'error': 'Session not found'}, 404)
            else:
                self._json_response({'error': 'session_id required'}, 400)
        
        else:
            self._json_response({'error': 'Not found'}, 404)
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        data = self._read_json()
        
        if path == '/keys/generate':
            # 生成密钥对
            agent_id = data.get('agent_id')
            key_size = data.get('key_size', 2048)
            
            if not agent_id:
                self._json_response({'error': 'agent_id required'}, 400)
                return
            
            kp = self.crypto.generate_keypair(agent_id, key_size)
            self._json_response({
                'agent_id': agent_id,
                'public_key': kp.public_key,
                'created_at': kp.created_at,
                'expires_at': kp.expires_at
            })
        
        elif path == '/keys/public':
            # 获取公钥
            agent_id = data.get('agent_id')
            if not agent_id:
                self._json_response({'error': 'agent_id required'}, 400)
                return
            
            key_pair = self.crypto.key_pairs.get(agent_id)
            if key_pair:
                self._json_response({
                    'agent_id': agent_id,
                    'public_key': key_pair.public_key
                })
            else:
                self._json_response({'error': 'Key pair not found'}, 404)
        
        elif path == '/sessions/establish':
            # 建立会话
            agent_id = data.get('agent_id')
            peer_id = data.get('peer_id')
            
            if not agent_id or not peer_id:
                self._json_response({'error': 'agent_id and peer_id required'}, 400)
                return
            
            session = self.crypto.establish_session(agent_id, peer_id)
            self._json_response({
                'session_id': session.session_id,
                'agent_id': session.agent_id,
                'peer_id': session.peer_id,
                'created_at': session.created_at,
                'expires_at': session.expires_at
            })
        
        elif path == '/message/encrypt':
            # 加密消息
            session_id = data.get('session_id')
            sender_id = data.get('sender_id')
            recipient_id = data.get('recipient_id')
            plaintext = data.get('message')
            
            if not all([session_id, sender_id, recipient_id, plaintext]):
                self._json_response({'error': 'session_id, sender_id, recipient_id, message required'}, 400)
                return
            
            msg = self.crypto.create_encrypted_message(
                session_id, sender_id, recipient_id, plaintext
            )
            
            if msg:
                self._json_response({
                    'session_id': msg.session_id,
                    'sender_id': msg.sender_id,
                    'recipient_id': msg.recipient_id,
                    'ciphertext': msg.ciphertext,
                    'nonce': msg.nonce,
                    'signature': msg.signature,
                    'timestamp': msg.timestamp,
                    'sequence': msg.sequence
                })
            else:
                self._json_response({'error': 'Failed to create message'}, 400)
        
        elif path == '/message/decrypt':
            # 解密消息
            msg_data = data.get('message')
            if not msg_data:
                self._json_response({'error': 'message required'}, 400)
                return
            
            try:
                msg = EncryptedMessage(
                    session_id=msg_data.get('session_id'),
                    sender_id=msg_data.get('sender_id'),
                    recipient_id=msg_data.get('recipient_id'),
                    ciphertext=msg_data.get('ciphertext'),
                    nonce=msg_data.get('nonce'),
                    signature=msg_data.get('signature'),
                    timestamp=msg_data.get('timestamp'),
                    sequence=msg_data.get('sequence')
                )
                
                plaintext = self.crypto.decrypt_message(msg)
                if plaintext:
                    self._json_response({
                        'plaintext': plaintext,
                        'sender_id': msg.sender_id,
                        'timestamp': msg.timestamp,
                        'sequence': msg.sequence
                    })
                else:
                    self._json_response({'error': 'Decryption failed'}, 400)
            except Exception as e:
                self._json_response({'error': str(e)}, 400)
        
        else:
            self._json_response({'error': 'Not found'}, 404)
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {args[0]}")


class SecureChannelAPI:
    """安全通道API服务"""
    
    def __init__(self, host='0.0.0.0', port=PORT):
        self.host = host
        self.port = port
        self.server = None
        self.thread = None
    
    def start(self):
        """启动服务"""
        self.server = HTTPServer((self.host, self.port), SecureChannelHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        print(f"Secure Channel API started on http://{self.host}:{self.port}")
        print(f"Endpoints:")
        print(f"  GET  /health - Health check")
        print(f"  GET  /keys - List keys")
        print(f"  GET  /sessions - List sessions")
        print(f"  POST /keys/generate - Generate key pair")
        print(f"  POST /sessions/establish - Establish session")
        print(f"  POST /message/encrypt - Encrypt message")
        print(f"  POST /message/decrypt - Decrypt message")
    
    def stop(self):
        """停止服务"""
        if self.server:
            self.server.shutdown()
            print("Secure Channel API stopped")


def main():
    api = SecureChannelAPI()
    api.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        api.stop()


if __name__ == "__main__":
    main()