#!/usr/bin/env python3
"""
Agent Identity and Access Control System
Agent身份认证与访问控制系统
"""

import hashlib
import hmac
import json
import time
import os
import secrets
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

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
    """身份提供者 - 管理Agent身份"""
    
    def __init__(self, storage_path: str = "/root/.openclaw/workspace/ultron/identity_provider.json"):
        self.storage_path = storage_path
        self.identities: Dict[str, AgentIdentity] = {}
        self.policies: Dict[str, AccessPolicy] = {}
        self._load()
    
    def _load(self):
        if os.path.exists(self.storage_path):
            with open(self.storage_path, 'r') as f:
                data = json.load(f)
                for k, v in data.get('identities', {}).items():
                    self.identities[k] = AgentIdentity(**v)
                for k, v in data.get('policies', {}).items():
                    self.policies[k] = AccessPolicy(**v)
    
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
        # 验证签名
        expected = self._sign(challenge, identity.public_key)
        if hmac.compare_digest(signature, expected):
            identity.last_auth = datetime.utcnow().isoformat()
            self._save()
            return True
        return False
    
    def _sign(self, message: str, private_key: str) -> str:
        """签名消息"""
        return hashlib.sha256(f"{message}:{private_key}".encode()).hexdigest()[:32]
    
    def authorize(self, agent_id: str, resource: str, action: str) -> bool:
        """检查Agent是否有权访问资源"""
        if agent_id not in self.identities:
            return False
        
        identity = self.identities[agent_id]
        
        # 查找相关策略
        for policy in self.policies.values():
            if policy.resource == resource or policy.resource == "*":
                # 检查权限
                if action in policy.required_permissions or "*" in policy.required_permissions:
                    # 检查认证级别
                    if identity.auth_level >= policy.required_auth_level:
                        # 检查Agent是否在白名单
                        if not policy.allowed_agents or agent_id in policy.allowed_agents:
                            return True
        return False
    
    def add_policy(self, policy: AccessPolicy):
        """添加访问策略"""
        self.policies[policy.policy_id] = policy
        self._save()
    
    def trust_agent(self, agent_id: str, trusted_agent_id: str):
        """设置Agent信任关系"""
        if agent_id in self.identities:
            if trusted_agent_id not in self.identities[agent_id].trusted_agents:
                self.identities[agent_id].trusted_agents.append(trusted_agent_id)
                self._save()

class AccessControl:
    """访问控制器"""
    
    def __init__(self, identity_provider: IdentityProvider):
        self.idp = identity_provider
        self.sessions: Dict[str, dict] = {}
    
    def create_session(self, agent_id: str, ttl: int = 3600) -> str:
        """创建会话"""
        session_token = secrets.token_urlsafe(32)
        self.sessions[session_token] = {
            'agent_id': agent_id,
            'created': time.time(),
            'ttl': ttl,
            'last_access': time.time()
        }
        return session_token
    
    def validate_session(self, session_token: str) -> Optional[str]:
        """验证会话并返回agent_id"""
        if session_token not in self.sessions:
            return None
        
        session = self.sessions[session_token]
        if time.time() - session['created'] > session['ttl']:
            del self.sessions[session_token]
            return None
        
        session['last_access'] = time.time()
        return session['agent_id']
    
    def revoke_session(self, session_token: str):
        """撤销会话"""
        if session_token in self.sessions:
            del self.sessions[session_token]

# 主程序
if __name__ == "__main__":
    idp = IdentityProvider()
    
    # 注册系统Agent
    idp.register_agent("ultron-main", "Ultron Main", "main-key-001", 4, ["read", "write", "execute", "admin"])
    idp.register_agent("agent-gateway", "API Gateway", "gateway-key-001", 3, ["read", "write", "execute"])
    idp.register_agent("agent-monitor", "Monitor Agent", "monitor-key-001", 2, ["read"])
    idp.register_agent("agent-worker-1", "Worker Agent 1", "worker-key-001", 1, ["execute"])
    
    # 添加访问策略
    idp.add_policy(AccessPolicy(
        policy_id="admin-resources",
        resource="system/*",
        required_permissions=["admin"],
        required_auth_level=4,
        allowed_agents=["ultron-main"]
    ))
    
    idp.add_policy(AccessPolicy(
        policy_id="api-gateway",
        resource="api/*",
        required_permissions=["execute"],
        required_auth_level=2,
        allowed_agents=["agent-gateway", "ultron-main"]
    ))
    
    idp.add_policy(AccessPolicy(
        policy_id="monitor-read",
        resource="metrics/*",
        required_permissions=["read"],
        required_auth_level=1,
        allowed_agents=[]
    ))
    
    # 建立信任关系
    idp.trust_agent("ultron-main", "agent-gateway")
    idp.trust_agent("ultron-main", "agent-monitor")
    
    print("✅ 身份认证与访问控制系统初始化完成")
    print(f"   注册Agent: {len(idp.identities)}")
    print(f"   访问策略: {len(idp.policies)}")
    
    # 测试
    ac = AccessControl(idp)
    session = ac.create_session("ultron-main")
    print(f"   测试会话创建: {session[:16]}...")
    valid_agent = ac.validate_session(session)
    print(f"   会话验证: {valid_agent}")
    print(f"   权限检查(ultron-main, system/*, admin): {idp.authorize('ultron-main', 'system/config', 'admin')}")
