#!/usr/bin/env python3
"""
Agent Identity & Access Control API
Agent身份认证与访问控制REST API
"""

import json
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import hashlib
import hmac
import secrets
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

class Permission(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"

class AuthLevel(Enum):
    ANONYMOUS = 0
    BASIC = 1
    VERIFIED = 2
    TRUSTED = 3
    ADMIN = 4

@dataclass
class AgentIdentity:
    agent_id: str
    name: str
    auth_level: int
    permissions: List[str]
    public_key: str
    created_at: str
    last_auth: str
    trusted_agents: List[str]

@dataclass
class AccessPolicy:
    policy_id: str
    resource: str
    required_permissions: List[str]
    required_auth_level: int
    allowed_agents: List[str]

class IdentityProvider:
    """身份提供者"""
    
    def __init__(self, storage_path: str = "/root/.openclaw/workspace/ultron/identity_provider.json"):
        self.storage_path = storage_path
        self.identities: Dict[str, AgentIdentity] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self._load_or_initialize()
    
    def _load_or_initialize(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    for k, v in data.get('identities', {}).items():
                        self.identities[k] = AgentIdentity(**v)
                    for k, v in data.get('policies', {}).items():
                        self.policies[k] = AccessPolicy(**v)
            except:
                self._initialize_default()
        else:
            self._initialize_default()
    
    def _initialize_default(self):
        # 注册系统Agent
        self.register_agent("ultron-main", "Ultron Main", "main-key-001", 4, ["read", "write", "execute", "admin"])
        self.register_agent("agent-gateway", "API Gateway", "gateway-key-001", 3, ["read", "write", "execute"])
        self.register_agent("agent-monitor", "Monitor Agent", "monitor-key-001", 2, ["read"])
        self.register_agent("agent-worker-1", "Worker Agent 1", "worker-key-001", 1, ["execute"])
        
        # 添加访问策略
        self.add_policy(AccessPolicy(
            policy_id="admin-resources",
            resource="system/*",
            required_permissions=["admin"],
            required_auth_level=4,
            allowed_agents=["ultron-main"]
        ))
        
        self.add_policy(AccessPolicy(
            policy_id="api-gateway",
            resource="api/*",
            required_permissions=["execute"],
            required_auth_level=2,
            allowed_agents=["agent-gateway", "ultron-main"]
        ))
        
        self.add_policy(AccessPolicy(
            policy_id="monitor-read",
            resource="metrics/*",
            required_permissions=["read"],
            required_auth_level=1,
            allowed_agents=[]
        ))
        
        # 建立信任关系
        self.trust_agent("ultron-main", "agent-gateway")
        self.trust_agent("ultron-main", "agent-monitor")
    
    def _save(self):
        data = {
            'identities': {k: asdict(v) for k, v in self.identities.items()},
            'policies': {k: asdict(v) for k, v in self.policies.items()}
        }
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def register_agent(self, agent_id: str, name: str, public_key: str, 
                       auth_level: int = 1, permissions: List[str] = None) -> AgentIdentity:
        """注册新Agent"""
        identity = AgentIdentity(
            agent_id=agent_id,
            name=name,
            auth_level=auth_level,
            permissions=permissions or ["read"],
            public_key=public_key,
            created_at=datetime.utcnow().isoformat(),
            last_auth=datetime.utcnow().isoformat(),
            trusted_agents=[]
        )
        self.identities[agent_id] = identity
        self._save()
        return identity
    
    def authenticate(self, agent_id: str, signature: str, challenge: str) -> bool:
        """验证Agent身份"""
        if agent_id not in self.identities:
            return False
        
        identity = self.identities[agent_id]
        expected = self._sign(challenge, identity.public_key)
        if hmac.compare_digest(signature, expected):
            identity.last_auth = datetime.utcnow().isoformat()
            self._save()
            return True
        return False
    
    def _sign(self, message: str, private_key: str) -> str:
        return hashlib.sha256(f"{message}:{private_key}".encode()).hexdigest()[:32]
    
    def authorize(self, agent_id: str, resource: str, action: str) -> bool:
        """检查Agent是否有权访问资源"""
        if agent_id not in self.identities:
            return False
        
        identity = self.identities[agent_id]
        
        for policy in self.policies.values():
            if policy.resource == resource or policy.resource.endswith("/*"):
                if action in policy.required_permissions or "*" in policy.required_permissions:
                    if identity.auth_level >= policy.required_auth_level:
                        if not policy.allowed_agents or agent_id in policy.allowed_agents:
                            return True
        return False
    
    def add_policy(self, policy: AccessPolicy):
        self.policies[policy.policy_id] = policy
        self._save()
    
    def trust_agent(self, agent_id: str, trusted_agent_id: str):
        if agent_id in self.identities:
            if trusted_agent_id not in self.identities[agent_id].trusted_agents:
                self.identities[agent_id].trusted_agents.append(trusted_agent_id)
                self._save()
    
    def list_agents(self) -> List[dict]:
        return [asdict(v) for v in self.identities.values()]
    
    def list_policies(self) -> List[dict]:
        return [asdict(v) for v in self.policies.values()]

class AccessControl:
    """访问控制器"""
    
    def __init__(self, identity_provider: IdentityProvider):
        self.idp = identity_provider
        self.sessions: Dict[str, dict] = {}
    
    def create_session(self, agent_id: str, ttl: int = 3600) -> str:
        session_token = secrets.token_urlsafe(32)
        self.sessions[session_token] = {
            'agent_id': agent_id,
            'created': time.time(),
            'ttl': ttl,
            'last_access': time.time()
        }
        return session_token
    
    def validate_session(self, session_token: str) -> Optional[str]:
        if session_token not in self.sessions:
            return None
        
        session = self.sessions[session_token]
        if time.time() - session['created'] > session['ttl']:
            del self.sessions[session_token]
            return None
        
        session['last_access'] = time.time()
        return session['agent_id']
    
    def revoke_session(self, session_token: str):
        if session_token in self.sessions:
            del self.sessions[session_token]

# 全局实例
idp = IdentityProvider()
ac = AccessControl(idp)

class APIHandler(BaseHTTPRequestHandler):
    def _send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def do_GET(self):
        path = urlparse(self.path).path
        
        if path == '/health':
            self._send_json({"status": "ok", "service": "identity-auth"})
        elif path == '/agents':
            self._send_json({"agents": idp.list_agents()})
        elif path == '/policies':
            self._send_json({"policies": idp.list_policies()})
        elif path == '/session/validate':
            params = parse_qs(urlparse(self.path).query)
            token = params.get('token', [None])[0]
            if token:
                agent_id = ac.validate_session(token)
                self._send_json({"valid": agent_id is not None, "agent_id": agent_id})
            else:
                self._send_json({"error": "missing token"}, 400)
        else:
            self._send_json({"error": "not found"}, 404)
    
    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == '/session/create':
            agent_id = data.get('agent_id')
            if agent_id and agent_id in idp.identities:
                token = ac.create_session(agent_id)
                self._send_json({"token": token, "agent_id": agent_id})
            else:
                self._send_json({"error": "invalid agent_id"}, 400)
        
        elif path == '/authenticate':
            agent_id = data.get('agent_id')
            signature = data.get('signature', '')
            challenge = data.get('challenge', '')
            if idp.authenticate(agent_id, signature, challenge):
                self._send_json({"authenticated": True})
            else:
                self._send_json({"authenticated": False}, 401)
        
        elif path == '/authorize':
            agent_id = data.get('agent_id')
            resource = data.get('resource')
            action = data.get('action', 'read')
            if idp.authorize(agent_id, resource, action):
                self._send_json({"authorized": True})
            else:
                self._send_json({"authorized": False}, 403)
        
        else:
            self._send_json({"error": "not found"}, 404)
    
    def log_message(self, format, *args):
        pass

def run_server(port=8091):
    server = HTTPServer(('0.0.0.0', port), APIHandler)
    print(f"🔐 Identity Auth API running on port {port}")
    server.serve_forever()

if __name__ == "__main__":
    run_server()
