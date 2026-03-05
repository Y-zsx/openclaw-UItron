"""
Agent认证与授权机制
提供API Key认证、JWT Token认证、RBAC权限控制
支持：用户认证/Agent认证/权限管理/访问控制
"""

import asyncio
import json
import time
import uuid
import hashlib
import hmac
import secrets
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from functools import wraps
import jwt


class AuthType(Enum):
    """认证类型"""
    API_KEY = "api_key"
    JWT = "jwt"
    OAUTH2 = "oauth2"
    NONE = "none"


class Permission(Enum):
    """权限枚举"""
    # Agent权限
    AGENT_REGISTER = "agent:register"
    AGENT_UNREGISTER = "agent:unregister"
    AGENT_VIEW = "agent:view"
    AGENT_CONTROL = "agent:control"
    
    # 任务权限
    TASK_CREATE = "task:create"
    TASK_VIEW = "task:view"
    TASK_CANCEL = "task:cancel"
    TASK_EXECUTE = "task:execute"
    
    # 消息权限
    MESSAGE_SEND = "message:send"
    MESSAGE_RECEIVE = "message:receive"
    MESSAGE_BROADCAST = "message:broadcast"
    
    # 管理权限
    ADMIN = "admin"
    SYSTEM_CONFIG = "system:config"
    USER_MANAGE = "user:manage"


class Role(Enum):
    """角色枚举"""
    ADMIN = "admin"
    OPERATOR = "operator"
    AGENT = "agent"
    VIEWER = "viewer"
    GUEST = "guest"


# 角色默认权限映射
ROLE_PERMISSIONS = {
    Role.ADMIN: [p.value for p in Permission],
    Role.OPERATOR: [
        Permission.AGENT_VIEW.value,
        Permission.AGENT_CONTROL.value,
        Permission.TASK_CREATE.value,
        Permission.TASK_VIEW.value,
        Permission.TASK_CANCEL.value,
        Permission.TASK_EXECUTE.value,
        Permission.MESSAGE_SEND.value,
        Permission.MESSAGE_RECEIVE.value,
    ],
    Role.AGENT: [
        Permission.AGENT_VIEW.value,
        Permission.TASK_CREATE.value,
        Permission.TASK_VIEW.value,
        Permission.MESSAGE_SEND.value,
        Permission.MESSAGE_RECEIVE.value,
    ],
    Role.VIEWER: [
        Permission.AGENT_VIEW.value,
        Permission.TASK_VIEW.value,
    ],
    Role.GUEST: [],
}


@dataclass
class User:
    """用户信息"""
    user_id: str
    username: str
    role: str
    permissions: List[str] = field(default_factory=list)
    api_keys: List[str] = field(default_factory=list)
    created_at: float = 0.0
    last_login: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        # 如果没有指定权限，从角色继承
        if not self.permissions and self.role:
            role_enum = Role(self.role) if self.role in [r.value for r in Role] else Role.VIEWER
            self.permissions = ROLE_PERMISSIONS.get(role_enum, [])
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'User':
        return cls(**data)


@dataclass
class AuthToken:
    """认证令牌"""
    token_id: str
    user_id: str
    token_type: str  # access, refresh
    permissions: List[str]
    issued_at: float
    expires_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_valid(self) -> bool:
        return time.time() < self.expires_at
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    user: Optional[User] = None
    token: Optional[str] = None
    error: Optional[str] = None
    permissions: List[str] = field(default_factory=list)


class AuthManager:
    """认证授权管理器"""
    
    def __init__(self, secret_key: Optional[str] = None, jwt_algorithm: str = "HS256"):
        self.secret_key = secret_key or secrets.token_urlsafe(32)
        self.jwt_algorithm = jwt_algorithm
        self.users: Dict[str, User] = {}  # user_id -> User
        self.api_keys: Dict[str, str] = {}  # api_key -> user_id
        self.tokens: Dict[str, AuthToken] = {}  # token_id -> AuthToken
        self.jwt_tokens: Dict[str, dict] = {}  # jwt_token -> claims
        
        # 初始化默认管理员
        self._init_default_admin()
    
    def _init_default_admin(self):
        """初始化默认管理员"""
        admin = User(
            user_id="admin",
            username="admin",
            role=Role.ADMIN.value,
            api_keys=["ultron-admin-key-2026"]
        )
        self.users["admin"] = admin
        self.api_keys["ultron-admin-key-2026"] = "admin"
    
    def register_user(self, username: str, role: str = "viewer", 
                     metadata: Optional[Dict] = None) -> User:
        """注册用户"""
        user_id = str(uuid.uuid4())
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            metadata=metadata or {}
        )
        self.users[user_id] = user
        return user
    
    def generate_api_key(self, user_id: str, name: str = "default") -> str:
        """生成API Key"""
        if user_id not in self.users:
            raise ValueError(f"User {user_id} not found")
        
        api_key = f"ultron-{name}-{secrets.token_urlsafe(16)}"
        self.api_keys[api_key] = user_id
        self.users[user_id].api_keys.append(api_key)
        return api_key
    
    def authenticate_api_key(self, api_key: str) -> AuthResult:
        """API Key认证"""
        user_id = self.api_keys.get(api_key)
        if not user_id:
            return AuthResult(success=False, error="Invalid API key")
        
        user = self.users.get(user_id)
        if not user:
            return AuthResult(success=False, error="User not found")
        
        user.last_login = time.time()
        return AuthResult(
            success=True,
            user=user,
            permissions=user.permissions
        )
    
    def authenticate_jwt(self, token: str) -> AuthResult:
        """JWT Token认证"""
        try:
            claims = jwt.decode(token, self.secret_key, algorithms=[self.jwt_algorithm])
            user_id = claims.get("user_id")
            
            if not user_id:
                return AuthResult(success=False, error="Invalid token claims")
            
            user = self.users.get(user_id)
            if not user:
                return AuthResult(success=False, error="User not found")
            
            user.last_login = time.time()
            return AuthResult(
                success=True,
                user=user,
                token=token,
                permissions=claims.get("permissions", user.permissions)
            )
        except jwt.ExpiredSignatureError:
            return AuthResult(success=False, error="Token expired")
        except jwt.InvalidTokenError as e:
            return AuthResult(success=False, error=f"Invalid token: {str(e)}")
    
    def create_access_token(self, user_id: str, expires_in: int = 3600) -> str:
        """创建访问令牌"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        now = time.time()
        token_id = str(uuid.uuid4())
        
        # 创建内部token记录
        token = AuthToken(
            token_id=token_id,
            user_id=user_id,
            token_type="access",
            permissions=user.permissions,
            issued_at=now,
            expires_at=now + expires_in
        )
        self.tokens[token_id] = token
        
        # 创建JWT
        claims = {
            "user_id": user_id,
            "username": user.username,
            "role": user.role,
            "permissions": user.permissions,
            "iat": int(now),
            "exp": int(now + expires_in),
            "token_id": token_id
        }
        jwt_token = jwt.encode(claims, self.secret_key, algorithm=self.jwt_algorithm)
        self.jwt_tokens[jwt_token] = claims
        
        return jwt_token
    
    def create_refresh_token(self, user_id: str, expires_in: int = 604800) -> str:
        """创建刷新令牌"""
        user = self.users.get(user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        now = time.time()
        claims = {
            "user_id": user_id,
            "type": "refresh",
            "iat": int(now),
            "exp": int(now + expires_in)
        }
        return jwt.encode(claims, self.secret_key, algorithm=self.jwt_algorithm)
    
    def refresh_access_token(self, refresh_token: str) -> AuthResult:
        """刷新访问令牌"""
        try:
            claims = jwt.decode(refresh_token, self.secret_key, algorithms=[self.jwt_algorithm])
            if claims.get("type") != "refresh":
                return AuthResult(success=False, error="Invalid refresh token")
            
            user_id = claims.get("user_id")
            new_token = self.create_access_token(user_id)
            
            user = self.users.get(user_id)
            return AuthResult(
                success=True,
                user=user,
                token=new_token,
                permissions=user.permissions
            )
        except jwt.InvalidTokenError as e:
            return AuthResult(success=False, error=str(e))
    
    def check_permission(self, user: User, permission: str) -> bool:
        """检查权限"""
        if user.role == Role.ADMIN.value:
            return True
        return permission in user.permissions
    
    def check_permissions(self, user: User, permissions: List[str], require_all: bool = False) -> bool:
        """批量检查权限"""
        if user.role == Role.ADMIN.value:
            return True
        
        if require_all:
            return all(p in user.permissions for p in permissions)
        return any(p in user.permissions for p in permissions)
    
    def grant_permission(self, user_id: str, permission: str) -> bool:
        """授予权限"""
        if user_id not in self.users:
            return False
        user = self.users[user_id]
        if permission not in user.permissions:
            user.permissions.append(permission)
        return True
    
    def revoke_permission(self, user_id: str, permission: str) -> bool:
        """撤销权限"""
        if user_id not in self.users:
            return False
        user = self.users[user_id]
        if permission in user.permissions:
            user.permissions.remove(permission)
        return True
    
    def revoke_api_key(self, api_key: str) -> bool:
        """撤销API Key"""
        user_id = self.api_keys.pop(api_key, None)
        if user_id and user_id in self.users:
            user = self.users[user_id]
            if api_key in user.api_keys:
                user.api_keys.remove(api_key)
            return True
        return False
    
    def revoke_token(self, token_id: str) -> bool:
        """撤销令牌"""
        token = self.tokens.pop(token_id, None)
        if token:
            # 尝试从JWT tokens中移除
            for jwt_t, claims in list(self.jwt_tokens.items()):
                if claims.get("token_id") == token_id:
                    del self.jwt_tokens[jwt_t]
                    break
            return True
        return False
    
    def get_user(self, user_id: str) -> Optional[User]:
        """获取用户"""
        return self.users.get(user_id)
    
    def list_users(self) -> List[User]:
        """列出所有用户"""
        return list(self.users.values())
    
    def get_stats(self) -> dict:
        """获取认证统计"""
        return {
            "total_users": len(self.users),
            "total_api_keys": len(self.api_keys),
            "active_tokens": sum(1 for t in self.tokens.values() if t.is_valid()),
            "roles": {role.value: sum(1 for u in self.users.values() if u.role == role.value) 
                     for role in Role}
        }


def require_permission(permission: str):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, auth_result: AuthResult, *args, **kwargs):
            if not auth_result.success:
                return {"error": "Authentication failed", "code": 401}
            
            if not self.auth_manager.check_permission(auth_result.user, permission):
                return {"error": f"Permission denied: {permission}", "code": 403}
            
            return await func(self, auth_result, *args, **kwargs)
        return wrapper
    return decorator


def require_any_permission(*permissions: str):
    """任一权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, auth_result: AuthResult, *args, **kwargs):
            if not auth_result.success:
                return {"error": "Authentication failed", "code": 401}
            
            if not self.auth_manager.check_permissions(auth_result.user, list(permissions), require_all=False):
                return {"error": f"Permission denied. Required one of: {permissions}", "code": 403}
            
            return await func(self, auth_result, *args, **kwargs)
        return wrapper
    return decorator


class AgentAuthMiddleware:
    """Agent认证中间件"""
    
    def __init__(self, auth_manager: AuthManager):
        self.auth_manager = auth_manager
    
    async def authenticate_request(self, request) -> AuthResult:
        """认证请求"""
        # 检查API Key
        api_key = request.headers.get("X-API-Key") or request.query.get("api_key")
        if api_key:
            return self.auth_manager.authenticate_api_key(api_key)
        
        # 检查JWT Token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return self.auth_manager.authenticate_jwt(token)
        
        # 检查Basic Auth
        auth_basic = request.headers.get("Authorization", "")
        if auth_basic.startswith("Basic "):
            import base64
            try:
                credentials = base64.b64decode(auth_basic[6:]).decode()
                username, password = credentials.split(":", 1)
                # 简单密码验证（生产环境应使用哈希）
                user = next((u for u in self.auth_manager.users.values() if u.username == username), None)
                if user and password == "password":  # 简化示例
                    return AuthResult(success=True, user=user, permissions=user.permissions)
            except:
                pass
        
        return AuthResult(success=False, error="No authentication provided")
    
    def require_auth(self, permission: Optional[str] = None):
        """请求认证装饰器"""
        def decorator(func):
            @wraps(func)
            async def wrapper(self, request, *args, **kwargs):
                auth_result = await self.authenticate_request(request)
                
                if not auth_result.success:
                    return web.json_response(
                        {"error": auth_result.error or "Unauthorized"},
                        status=401
                    )
                
                if permission and not self.auth_manager.check_permission(auth_result.user, permission):
                    return web.json_response(
                        {"error": f"Permission denied: {permission}"},
                        status=403
                    )
                
                request.auth_user = auth_result.user
                request.auth_permissions = auth_result.permissions
                return await func(self, request, *args, **kwargs)
            return wrapper
        return decorator


# 测试演示
async def demo():
    """演示认证授权功能"""
    print("=" * 60)
    print("Agent认证与授权系统演示")
    print("=" * 60)
    
    # 创建认证管理器
    auth = AuthManager()
    
    # 1. 注册用户
    print("\n[1] 注册用户")
    operator = auth.register_user("operator_user", "operator")
    agent = auth.register_user("agent_service", "agent")
    viewer = auth.register_user("viewer_user", "viewer")
    print(f"  ✅ 创建用户: {operator.username} (role: {operator.role})")
    print(f"  ✅ 创建用户: {agent.username} (role: {agent.role})")
    print(f"  ✅ 创建用户: {viewer.username} (role: {viewer.role})")
    
    # 2. 生成API Key
    print("\n[2] 生成API Key")
    op_key = auth.generate_api_key(operator.user_id, "operator-key")
    print(f"  ✅ Operator API Key: {op_key[:30]}...")
    
    # 3. API Key认证
    print("\n[3] API Key认证")
    result = auth.authenticate_api_key(op_key)
    print(f"  ✅ 认证结果: {result.success}")
    print(f"  ✅ 用户: {result.user.username}, 权限数: {len(result.permissions)}")
    
    # 4. JWT Token认证
    print("\n[4] JWT Token认证")
    token = auth.create_access_token(operator.user_id, expires_in=3600)
    print(f"  ✅ 生成Token: {token[:30]}...")
    
    result = auth.authenticate_jwt(token)
    print(f"  ✅ Token认证: {result.success}")
    print(f"  ✅ 用户: {result.user.username}")
    
    # 5. 权限检查
    print("\n[5] 权限检查")
    print(f"  • Admin权限检查 (agent:register): {auth.check_permission(auth.users['admin'], 'agent:register')}")
    print(f"  • Viewer权限检查 (agent:register): {auth.check_permission(viewer, 'agent:register')}")
    print(f"  • Operator权限检查 (task:create): {auth.check_permission(operator, 'task:create')}")
    
    # 6. 权限授予与撤销
    print("\n[6] 权限授予与撤销")
    auth.grant_permission(viewer.user_id, "task:create")
    print(f"  ✅ 授予Viewer task:create权限")
    print(f"  • Viewer权限检查 (task:create): {auth.check_permission(viewer, 'task:create')}")
    
    auth.revoke_permission(viewer.user_id, "task:create")
    print(f"  ✅ 撤销Viewer task:create权限")
    print(f"  • Viewer权限检查 (task:create): {auth.check_permission(viewer, 'task:create')}")
    
    # 7. 统计信息
    print("\n[7] 统计信息")
    stats = auth.get_stats()
    print(f"  ✅ 总用户数: {stats['total_users']}")
    print(f"  ✅ 总API Keys: {stats['total_api_keys']}")
    print(f"  ✅ 活跃Tokens: {stats['active_tokens']}")
    print(f"  ✅ 角色分布: {stats['roles']}")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(demo())