#!/usr/bin/env python3
"""
跨维度智能交互网络 - 跨平台认证系统
Cross-Platform Authentication System

功能：
- 多平台统一认证
- OAuth 2.0 / API Key / JWT 支持
- 访问控制与权限管理
- 令牌刷新与撤销
"""

import json
import time
import hashlib
import hmac
import secrets
import asyncio
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod
import base64
import jwt

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CrossPlatformAuth")


class AuthMethod(Enum):
    """认证方法"""
    API_KEY = "api_key"
    OAUTH2 = "oauth2"
    JWT = "jwt"
    BASIC = "basic"
    CUSTOM = "custom"


class Permission(Enum):
    """权限类型"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    EXECUTE = "execute"
    WEBHOOK = "webhook"


@dataclass
class User:
    """用户"""
    user_id: str
    platform: str
    username: str
    permissions: List[Permission] = field(default_factory=list)
    metadata: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_login: float = field(default_factory=time.time)


@dataclass
class AuthCredential:
    """认证凭据"""
    method: AuthMethod
    key: str
    secret: str = ""
    refresh_token: str = ""
    expires_at: float = 0


@dataclass
class AuthSession:
    """认证会话"""
    session_id: str
    user_id: str
    platform: str
    permissions: List[Permission]
    created_at: float
    expires_at: float
    refresh_count: int = 0
    metadata: Dict = field(default_factory=dict)


class AuthProvider(ABC):
    """认证提供者基类"""
    
    @abstractmethod
    async def authenticate(self, credential: AuthCredential) -> Optional[User]:
        """验证凭据"""
        pass
    
    @abstractmethod
    async def refresh(self, session: AuthSession) -> Optional[AuthSession]:
        """刷新会话"""
        pass
    
    @abstractmethod
    async def revoke(self, session: AuthSession):
        """撤销会话"""
        pass


class APIKeyProvider(AuthProvider):
    """API Key 认证提供者"""
    
    def __init__(self, secret_key: str = None):
        self.secret_key = secret_key or secrets.token_hex(32)
        self.api_keys: Dict[str, Dict] = {}
    
    def generate_api_key(self, user_id: str, permissions: List[Permission] = None,
                        expires_in: int = 86400) -> str:
        """生成API Key"""
        api_key = f"sk_{secrets.token_urlsafe(32)}"
        
        self.api_keys[api_key] = {
            "user_id": user_id,
            "permissions": [p.value for p in (permissions or [Permission.READ])],
            "created_at": time.time(),
            "expires_at": time.time() + expires_in,
            "secret": secrets.token_urlsafe(32)
        }
        
        return api_key
    
    def verify_api_key(self, api_key: str) -> Optional[Dict]:
        """验证API Key"""
        if api_key not in self.api_keys:
            return None
        
        key_data = self.api_keys[api_key]
        
        # 检查过期
        if time.time() > key_data["expires_at"]:
            del self.api_keys[api_key]
            return None
        
        return key_data
    
    async def authenticate(self, credential: AuthCredential) -> Optional[User]:
        """API Key 认证"""
        if credential.method != AuthMethod.API_KEY:
            return None
        
        key_data = self.verify_api_key(credential.key)
        if not key_data:
            return None
        
        permissions = [Permission(p) for p in key_data["permissions"]]
        
        return User(
            user_id=key_data["user_id"],
            platform="api",
            username=f"user_{key_data['user_id']}",
            permissions=permissions
        )
    
    async def refresh(self, session: AuthSession) -> Optional[AuthSession]:
        """刷新会话"""
        # API Key 模式下通常不需要刷新
        if time.time() < session.expires_at:
            return session
        return None
    
    async def revoke(self, session: AuthSession):
        """撤销会话 - API Key模式下移除key"""
        for key, data in list(self.api_keys.items()):
            if data["user_id"] == session.user_id:
                del self.api_keys[key]


class OAuth2Provider(AuthProvider):
    """OAuth 2.0 认证提供者"""
    
    def __init__(self, client_id: str, client_secret: str, 
                 token_url: str, refresh_url: str = None):
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.refresh_url = refresh_url or token_url
        self.authorization_codes: Dict[str, Dict] = {}
        self.access_tokens: Dict[str, Dict] = {}
        self.refresh_tokens: Dict[str, Dict] = {}
    
    def generate_auth_url(self, redirect_uri: str, state: str = None) -> str:
        """生成授权URL"""
        code = secrets.token_urlsafe(32)
        self.authorization_codes[code] = {
            "redirect_uri": redirect_uri,
            "created_at": time.time(),
            "state": state
        }
        
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state or code
        }
        
        return f"{self.token_url}?{urllib.parse.urlencode(params)}"
    
    async def exchange_code(self, code: str, redirect_uri: str) -> Optional[Dict]:
        """交换授权码"""
        if code not in self.authorization_codes:
            return None
        
        code_data = self.authorization_codes[code]
        
        # 验证redirect_uri
        if code_data["redirect_uri"] != redirect_uri:
            return None
        
        # 检查过期 (5分钟)
        if time.time() - code_data["created_at"] > 300:
            del self.authorization_codes[code]
            return None
        
        # 实际应用中这里会调用token_url
        # 模拟返回token
        access_token = secrets.token_urlsafe(32)
        refresh_token = secrets.token_urlsafe(32)
        
        self.access_tokens[access_token] = {
            "user_id": f"user_{secrets.randbelow(10000)}",
            "scope": "read write",
            "created_at": time.time(),
            "expires_at": time.time() + 3600
        }
        
        self.refresh_tokens[refresh_token] = {
            "access_token": access_token,
            "created_at": time.time()
        }
        
        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": 3600
        }
    
    async def authenticate(self, credential: AuthCredential) -> Optional[User]:
        """OAuth2 认证"""
        if credential.method != AuthMethod.OAUTH2:
            return None
        
        if credential.key not in self.access_tokens:
            return None
        
        token_data = self.access_tokens[credential.key]
        
        if time.time() > token_data["expires_at"]:
            del self.access_tokens[credential.key]
            return None
        
        return User(
            user_id=token_data["user_id"],
            platform="oauth2",
            username=f"oauth_user_{token_data['user_id']}",
            permissions=[Permission.READ, Permission.WRITE]
        )
    
    async def refresh(self, session: AuthSession) -> Optional[AuthSession]:
        """刷新OAuth token"""
        # 查找refresh token
        for rt, data in self.refresh_tokens.items():
            if data["access_token"] in self.access_tokens:
                # 模拟刷新
                old_token = data["access_token"]
                new_token = secrets.token_urlsafe(32)
                
                self.access_tokens[new_token] = self.access_tokens.pop(old_token)
                self.access_tokens[new_token]["expires_at"] = time.time() + 3600
                
                session.session_id = new_token
                session.expires_at = time.time() + 3600
                session.refresh_count += 1
                
                return session
        
        return None
    
    async def revoke(self, session: AuthSession):
        """撤销OAuth token"""
        if session.session_id in self.access_tokens:
            del self.access_tokens[session.session_id]


class JWTProvider(AuthProvider):
    """JWT 认证提供者"""
    
    def __init__(self, secret_key: str, algorithm: str = "HS256"):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.revoked_tokens: set = set()
    
    def create_token(self, user_id: str, permissions: List[Permission] = None,
                    expires_in: int = 3600, **extra_claims) -> str:
        """创建JWT"""
        now = time.time()
        
        payload = {
            "sub": user_id,
            "iat": now,
            "exp": now + expires_in,
            "permissions": [p.value for p in (permissions or [Permission.READ])],
            **extra_claims
        }
        
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    def verify_token(self, token: str) -> Optional[Dict]:
        """验证JWT"""
        if token in self.revoked_tokens:
            return None
        
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
    
    def revoke_token(self, token: str):
        """撤销JWT"""
        self.revoked_tokens.add(token)
    
    async def authenticate(self, credential: AuthCredential) -> Optional[User]:
        """JWT 认证"""
        if credential.method != AuthMethod.JWT:
            return None
        
        payload = self.verify_token(credential.key)
        if not payload:
            return None
        
        permissions = [Permission(p) for p in payload.get("permissions", [])]
        
        return User(
            user_id=payload["sub"],
            platform=payload.get("platform", "jwt"),
            username=payload.get("username", f"user_{payload['sub']}"),
            permissions=permissions
        )
    
    async def refresh(self, session: AuthSession) -> Optional[AuthSession]:
        """刷新JWT - 创建新token"""
        payload = self.verify_token(session.session_id)
        if not payload:
            return None
        
        new_token = self.create_token(
            user_id=payload["sub"],
            permissions=[Permission(p) for p in payload.get("permissions", [])]
        )
        
        session.session_id = new_token
        session.expires_at = time.time() + 3600
        
        return session
    
    async def revoke(self, session: AuthSession):
        """撤销JWT"""
        self.revoke_token(session.session_id)


class CrossPlatformAuthManager:
    """跨平台认证管理器"""
    
    def __init__(self, jwt_secret: str = None):
        self.jwt_secret = jwt_secret or secrets.token_hex(32)
        self.providers: Dict[AuthMethod, AuthProvider] = {}
        self.sessions: Dict[str, AuthSession] = {}
        self.users: Dict[str, User] = {}
        
        # 初始化默认提供者
        self.providers[AuthMethod.API_KEY] = APIKeyProvider()
        self.providers[AuthMethod.JWT] = JWTProvider(self.jwt_secret)
    
    def register_provider(self, method: AuthMethod, provider: AuthProvider):
        """注册认证提供者"""
        self.providers[method] = provider
    
    async def login(self, platform: str, credential: AuthCredential) -> Optional[AuthSession]:
        """登录"""
        provider = self.providers.get(credential.method)
        if not provider:
            return None
        
        user = await provider.authenticate(credential)
        if not user:
            return None
        
        # 保存用户
        self.users[user.user_id] = user
        
        # 创建会话
        session_id = secrets.token_urlsafe(32)
        session = AuthSession(
            session_id=session_id,
            user_id=user.user_id,
            platform=platform,
            permissions=user.permissions,
            created_at=time.time(),
            expires_at=time.time() + 86400  # 24小时
        )
        
        self.sessions[session_id] = session
        
        logger.info(f"User {user.user_id} logged in from {platform}")
        return session
    
    async def verify_session(self, session_id: str) -> Optional[AuthSession]:
        """验证会话"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        if time.time() > session.expires_at:
            await self.logout(session_id)
            return None
        
        return session
    
    async def logout(self, session_id: str):
        """登出"""
        if session_id in self.sessions:
            session = self.sessions[session_id]
            
            # 通知提供者
            for provider in self.providers.values():
                await provider.revoke(session)
            
            del self.sessions[session_id]
            logger.info(f"Session {session_id} logged out")
    
    async def check_permission(self, session_id: str, permission: Permission) -> bool:
        """检查权限"""
        session = await self.verify_session(session_id)
        if not session:
            return False
        
        return permission in session.permissions
    
    async def refresh_session(self, session_id: str) -> Optional[AuthSession]:
        """刷新会话"""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        
        # 查找认证方法
        for provider in self.providers.values():
            new_session = await provider.refresh(session)
            if new_session:
                self.sessions[new_session.session_id] = new_session
                if new_session.session_id != session_id:
                    del self.sessions[session_id]
                return new_session
        
        return None
    
    def create_jwt_token(self, user_id: str, permissions: List[Permission] = None,
                        platform: str = "default", **extra) -> str:
        """直接创建JWT token"""
        provider = self.providers.get(AuthMethod.JWT)
        if not provider:
            return ""
        
        return provider.create_token(user_id, permissions, platform=platform, **extra)
    
    def verify_jwt(self, token: str) -> Optional[Dict]:
        """验证JWT"""
        provider = self.providers.get(AuthMethod.JWT)
        if not provider:
            return None
        
        return provider.verify_token(token)
    
    def get_status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "active_sessions": len(self.sessions),
            "registered_users": len(self.users),
            "providers": [p.value for p in self.providers.keys()],
            "jwt_secret_set": bool(self.jwt_secret)
        }


# 辅助函数
def generate_secure_token(length: int = 32) -> str:
    """生成安全随机token"""
    return secrets.token_urlsafe(length)


def hash_password(password: str, salt: str = None) -> tuple:
    """密码哈希"""
    salt = salt or secrets.token_hex(16)
    hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
    return hashed.hex(), salt


def verify_password(password: str, hashed: str, salt: str) -> bool:
    """验证密码"""
    new_hash, _ = hash_password(password, salt)
    return hmac.compare_digest(new_hash, hashed)


# 示例
if __name__ == "__main__":
    import urllib.parse
    
    async def main():
        # 创建认证管理器
        auth = CrossPlatformAuthManager()
        
        # 使用API Key登录
        api_provider = auth.providers[AuthMethod.API_KEY]
        api_key = api_provider.generate_api_key(
            "user123",
            [Permission.READ, Permission.WRITE],
            expires_in=3600
        )
        
        session = await auth.login("telegram", AuthCredential(
            method=AuthMethod.API_KEY,
            key=api_key
        ))
        
        if session:
            print(f"Login successful: {session.session_id}")
            
            # 检查权限
            has_perm = await auth.check_permission(session.session_id, Permission.WRITE)
            print(f"Has write permission: {has_perm}")
            
            # 登出
            await auth.logout(session.session_id)
        
        # 使用JWT
        jwt_token = auth.create_jwt_token(
            "user456",
            [Permission.READ, Permission.WRITE, Permission.ADMIN]
        )
        
        jwt_payload = auth.verify_jwt(jwt_token)
        print(f"JWT payload: {jwt_payload}")
        
        # 状态
        print(f"Auth status: {auth.get_status()}")
    
    asyncio.run(main())