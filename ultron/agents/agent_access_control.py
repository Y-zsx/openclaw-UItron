"""
Agent身份认证与访问控制集成模块
实现：身份认证与安全通道集成、访问控制列表(ACL)、安全策略执行
"""

import os
import json
import time
import hashlib
import secrets
from typing import Dict, List, Optional, Set, Any, Callable
from dataclasses import dataclass, field, asdict
from enum import Enum
from functools import wraps

# 导入已有模块
try:
    from agent_auth import AuthType, Permission, Role, ROLE_PERMISSIONS, AuthManager
    from agent_secure_channel import SecureChannelManager, ChannelSecurityLevel, EncryptionType
except ImportError:
    # 如果导入失败，定义基础类
    class AuthType(Enum):
        API_KEY = "api_key"
        JWT = "jwt"
        NONE = "none"

    class Permission(Enum):
        AGENT_REGISTER = "agent:register"
        AGENT_VIEW = "agent:view"
        TASK_CREATE = "task:create"
        TASK_EXECUTE = "task:execute"
        MESSAGE_SEND = "message:send"
        ADMIN = "admin"

    class Role(Enum):
        ADMIN = "admin"
        OPERATOR = "operator"
        AGENT = "agent"
        VIEWER = "viewer"
        GUEST = "guest"

    ROLE_PERMISSIONS = {
        Role.ADMIN: [p.value for p in Permission],
        Role.OPERATOR: [Permission.AGENT_VIEW.value, Permission.TASK_CREATE.value],
        Role.AGENT: [Permission.AGENT_VIEW.value, Permission.TASK_CREATE.value],
        Role.VIEWER: [Permission.AGENT_VIEW.value],
        Role.GUEST: [],
    }


class AccessControlPolicy(Enum):
    """访问控制策略"""
    ALLOW_ALL = "allow_all"
    DENY_ALL = "deny_all"
    WHITELIST = "whitelist"
    BLACKLIST = "blacklist"
    RBAC = "rbac"  # Role-Based Access Control
    ABAC = "abac"  # Attribute-Based Access Control


class ResourceType(Enum):
    """资源类型"""
    AGENT = "agent"
    TASK = "task"
    MESSAGE = "message"
    API = "api"
    DATA = "data"
    SYSTEM = "system"


class Action(Enum):
    """操作类型"""
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    SEND = "send"
    RECEIVE = "receive"
    ADMIN = "admin"


@dataclass
class AgentIdentity:
    """Agent身份信息"""
    agent_id: str
    name: str
    role: str
    permissions: List[str] = field(default_factory=list)
    security_level: str = "PUBLIC"
    trusted: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    last_auth: float = 0.0


@dataclass
class AccessRule:
    """访问规则"""
    rule_id: str
    name: str
    resource_type: str
    resource_id: Optional[str] = None
    actions: List[str] = field(default_factory=list)
    subjects: List[str] = field(default_factory=list)  # Agent IDs或roles
    effect: str = "allow"  # allow/deny
    conditions: Dict[str, Any] = field(default_factory=dict)
    priority: int = 0
    enabled: bool = True


@dataclass
class SecurityPolicy:
    """安全策略"""
    policy_id: str
    name: str
    description: str
    rules: List[AccessRule] = field(default_factory=list)
    default_action: str = "deny"
    enforcement_level: str = "strict"  # strict/permissive
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)


@dataclass
class AuthResult:
    """认证结果"""
    success: bool
    agent_id: str
    identity: Optional[AgentIdentity] = None
    security_level: str = "PUBLIC"
    token: Optional[str] = None
    message: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class AccessDecision:
    """访问决策"""
    granted: bool
    reason: str
    matched_rule: Optional[str] = None
    security_level: str = "PUBLIC"
    timestamp: float = field(default_factory=time.time)


class AgentAccessControlManager:
    """Agent访问控制管理器 - 集成身份认证与安全通道"""
    
    def __init__(self, agent_id: str, storage_path: str = None):
        self.agent_id = agent_id
        self.storage_path = storage_path or "/root/.openclaw/workspace/ultron/agents/access_control_state.json"
        
        # 核心组件
        self.auth_manager = AuthManager() if 'AuthManager' in dir() else None
        self.secure_channel = SecureChannelManager(agent_id, storage_path)
        
        # 身份管理
        self.identities: Dict[str, AgentIdentity] = {}  # agent_id -> AgentIdentity
        self.auth_tokens: Dict[str, AgentIdentity] = {}  # token -> AgentIdentity
        
        # 访问控制
        self.policies: Dict[str, SecurityPolicy] = {}
        self.acl: Dict[str, List[AccessRule]] = {}  # resource_type -> rules
        self.default_policy = "deny"
        
        # 统计
        self.auth_attempts = 0
        self.auth_failures = 0
        self.access_checks = 0
        self.access_denials = 0
        
        self._load_state()
    
    def _load_state(self):
        """加载状态"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    
                    # 加载身份
                    for aid, idata in data.get('identities', {}).items():
                        self.identities[aid] = AgentIdentity(**idata)
                    
                    # 加载策略
                    for pid, pdata in data.get('policies', {}).items():
                        rules = [AccessRule(**r) for r in pdata.get('rules', [])]
                        pdata['rules'] = rules
                        self.policies[pid] = SecurityPolicy(**pdata)
                    
                    # 加载ACL
                    self.acl = data.get('acl', {})
                    
                    # 统计
                    self.auth_attempts = data.get('auth_attempts', 0)
                    self.auth_failures = data.get('auth_failures', 0)
                    self.access_checks = data.get('access_checks', 0)
                    self.access_denials = data.get('access_denials', 0)
                    
            except Exception as e:
                print(f"加载状态失败: {e}")
    
    def _save_state(self):
        """保存状态"""
        # 将ACL规则转换为字典
        acl_dict = {}
        for resource_type, rules in self.acl.items():
            acl_dict[resource_type] = [asdict(r) if isinstance(r, AccessRule) else r for r in rules]
        
        data = {
            'identities': {aid: asdict(id) for aid, id in self.identities.items()},
            'policies': {pid: {
                'policy_id': p.policy_id,
                'name': p.name,
                'description': p.description,
                'rules': [asdict(r) for r in p.rules],
                'default_action': p.default_action,
                'enforcement_level': p.enforcement_level,
                'created_at': p.created_at,
                'updated_at': p.updated_at,
            } for pid, p in self.policies.items()},
            'acl': acl_dict,
            'auth_attempts': self.auth_attempts,
            'auth_failures': self.auth_failures,
            'access_checks': self.access_checks,
            'access_denials': self.access_denials,
        }
        
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    # ============ 身份认证 ============
    
    def register_agent_identity(self, agent_id: str, name: str, role: str = "agent",
                                metadata: Dict[str, Any] = None) -> AgentIdentity:
        """注册Agent身份"""
        identity = AgentIdentity(
            agent_id=agent_id,
            name=name,
            role=role,
            permissions=ROLE_PERMISSIONS.get(Role(role), []),
            trusted=False,
            metadata=metadata or {}
        )
        
        self.identities[agent_id] = identity
        self._save_state()
        
        return identity
    
    def authenticate_agent(self, agent_id: str, credentials: Dict[str, str] = None,
                          security_level: str = "ENCRYPTED") -> AuthResult:
        """认证Agent身份并建立安全通道"""
        self.auth_attempts += 1
        
        # 检查身份是否存在
        identity = self.identities.get(agent_id)
        
        if not identity:
            self.auth_failures += 1
            self._save_state()
            return AuthResult(
                success=False,
                agent_id=agent_id,
                message="Agent identity not found"
            )
        
        # 验证凭证
        if credentials:
            # 这里可以添加更复杂的凭证验证逻辑
            # 例如：API Key验证、密码验证等
            pass
        
        # 生成认证令牌
        token = self._generate_token(agent_id)
        
        # 更新身份状态
        identity.last_auth = time.time()
        identity.security_level = security_level
        
        # 建立安全通道
        if security_level in ["ENCRYPTED", "VERIFIED"]:
            use_enc = security_level in ["ENCRYPTED", "VERIFIED"]
            self.secure_channel.create_session(
                peer_id=agent_id,
                use_encryption=use_enc
            )
        
        # 存储令牌
        self.auth_tokens[token] = identity
        
        self._save_state()
        
        return AuthResult(
            success=True,
            agent_id=agent_id,
            identity=identity,
            security_level=security_level,
            token=token,
            message="Authentication successful"
        )
    
    def verify_token(self, token: str) -> Optional[AgentIdentity]:
        """验证认证令牌"""
        return self.auth_tokens.get(token)
    
    def revoke_token(self, token: str) -> bool:
        """撤销令牌"""
        if token in self.auth_tokens:
            del self.auth_tokens[token]
            self._save_state()
            return True
        return False
    
    def _generate_token(self, agent_id: str) -> str:
        """生成认证令牌"""
        data = f"{agent_id}:{time.time()}:{secrets.token_hex(16)}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    # ============ 访问控制 ============
    
    def add_access_rule(self, rule: AccessRule) -> bool:
        """添加访问规则"""
        resource_type = rule.resource_type
        
        if resource_type not in self.acl:
            self.acl[resource_type] = []
        
        self.acl[resource_type].append(rule)
        self._save_state()
        
        return True
    
    def remove_access_rule(self, rule_id: str) -> bool:
        """移除访问规则"""
        for rules in self.acl.values():
            for i, rule in enumerate(rules):
                if rule.rule_id == rule_id:
                    rules.pop(i)
                    self._save_state()
                    return True
        return False
    
    def check_access(self, agent_id: str, resource_type: str, action: str,
                    resource_id: str = None) -> AccessDecision:
        """检查访问权限"""
        self.access_checks += 1
        
        # 获取Agent身份
        identity = self.identities.get(agent_id)
        
        if not identity:
            self.access_denials += 1
            self._save_state()
            return AccessDecision(
                granted=False,
                reason="Unknown agent identity"
            )
        
        # 获取相关规则
        rules = self.acl.get(resource_type, [])
        
        # 按优先级排序
        rules = sorted(rules, key=lambda r: r.priority, reverse=True)
        
        # 匹配规则
        for rule in rules:
            if not rule.enabled:
                continue
            
            # 检查是否适用于此Agent
            if agent_id not in rule.subjects and identity.role not in rule.subjects:
                continue
            
            # 检查操作
            if action not in rule.actions and "*" not in rule.actions:
                continue
            
            # 检查资源ID（如果指定）
            if rule.resource_id and resource_id and rule.resource_id != resource_id:
                continue
            
            # 规则匹配
            self._save_state()
            
            if rule.effect == "allow":
                return AccessDecision(
                    granted=True,
                    reason=f"Matched rule: {rule.name}",
                    matched_rule=rule.rule_id,
                    security_level=identity.security_level
                )
            else:
                self.access_denials += 1
                return AccessDecision(
                    granted=False,
                    reason=f"Denied by rule: {rule.name}",
                    matched_rule=rule.rule_id,
                    security_level=identity.security_level
                )
        
        # 默认策略
        if self.default_policy == "allow":
            return AccessDecision(
                granted=True,
                reason="Default allow policy"
            )
        
        self.access_denials += 1
        self._save_state()
        
        return AccessDecision(
            granted=False,
            reason="No matching rule, default deny"
        )
    
    # ============ 安全策略管理 ============
    
    def create_policy(self, policy: SecurityPolicy) -> bool:
        """创建安全策略"""
        self.policies[policy.policy_id] = policy
        self._save_state()
        return True
    
    def apply_policy(self, policy_id: str) -> bool:
        """应用安全策略"""
        policy = self.policies.get(policy_id)
        
        if not policy:
            return False
        
        # 将策略规则应用到ACL
        for rule in policy.rules:
            self.add_access_rule(rule)
        
        self.default_policy = policy.default_action
        self._save_state()
        
        return True
    
    def get_policy_stats(self) -> Dict[str, Any]:
        """获取策略统计"""
        return {
            'total_policies': len(self.policies),
            'total_rules': sum(len(p.rules) for p in self.policies.values()),
            'identities': len(self.identities),
            'active_tokens': len(self.auth_tokens),
            'auth_attempts': self.auth_attempts,
            'auth_failures': self.auth_failures,
            'access_checks': self.access_checks,
            'access_denials': self.access_denials,
            'default_policy': self.default_policy
        }
    
    # ============ 便捷装饰器 ============
    
    def require_permission(self, permission: str):
        """权限要求装饰器"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(agent_id: str, *args, **kwargs):
                identity = self.identities.get(agent_id)
                
                if not identity or permission not in identity.permissions:
                    raise PermissionError(f"Agent {agent_id} lacks permission: {permission}")
                
                return func(agent_id, *args, **kwargs)
            return wrapper
        return decorator
    
    def require_role(self, role: str):
        """角色要求装饰器"""
        def decorator(func: Callable):
            @wraps(func)
            def wrapper(agent_id: str, *args, **kwargs):
                identity = self.identities.get(agent_id)
                
                if not identity or identity.role != role:
                    raise PermissionError(f"Agent {agent_id} lacks role: {role}")
                
                return func(agent_id, *args, **kwargs)
            return wrapper
        return decorator


def demo():
    """演示"""
    print("=" * 60)
    print("Agent访问控制集成演示")
    print("=" * 60)
    
    # 创建访问控制管理器
    acm = AgentAccessControlManager("main-brain")
    
    # 1. 注册Agent身份
    print("\n1. 注册Agent身份:")
    acm.register_agent_identity("monitor-01", "Monitor Agent", "agent")
    acm.register_agent_identity("executor-01", "Executor Agent", "operator")
    acm.register_agent_identity("admin-01", "Admin Agent", "admin")
    
    for agent_id, identity in acm.identities.items():
        print(f"   - {agent_id}: role={identity.role}, permissions={len(identity.permissions)}")
    
    # 2. 认证Agent
    print("\n2. Agent身份认证:")
    result = acm.authenticate_agent("monitor-01", security_level="ENCRYPTED")
    print(f"   - {result.agent_id}: {result.message}, token={result.token[:16]}...")
    
    result = acm.authenticate_agent("admin-01", security_level="VERIFIED")
    print(f"   - {result.agent_id}: {result.message}, security_level={result.security_level}")
    
    # 3. 添加访问规则
    print("\n3. 配置访问控制规则:")
    
    # 允许所有Agent查看任务
    rule1 = AccessRule(
        rule_id="rule-001",
        name="View Tasks",
        resource_type="task",
        actions=["read"],
        subjects=["agent", "operator", "admin"],
        effect="allow",
        priority=10
    )
    acm.add_access_rule(rule1)
    print(f"   - 添加规则: {rule1.name}")
    
    # 只允许Operator和Admin执行任务
    rule2 = AccessRule(
        rule_id="rule-002",
        name="Execute Tasks",
        resource_type="task",
        actions=["execute"],
        subjects=["operator", "admin"],
        effect="allow",
        priority=20
    )
    acm.add_access_rule(rule2)
    print(f"   - 添加规则: {rule2.name}")
    
    # 禁止Guest访问系统
    rule3 = AccessRule(
        rule_id="rule-003",
        name="Deny Guest System",
        resource_type="system",
        actions=["*"],
        subjects=["guest"],
        effect="deny",
        priority=30
    )
    acm.add_access_rule(rule3)
    print(f"   - 添加规则: {rule3.name}")
    
    # 4. 测试访问控制
    print("\n4. 访问控制测试:")
    
    tests = [
        ("monitor-01", "task", "read"),
        ("monitor-01", "task", "execute"),
        ("executor-01", "task", "execute"),
        ("admin-01", "system", "admin"),
        ("guest-01", "system", "read"),
    ]
    
    for agent_id, resource, action in tests:
        decision = acm.check_access(agent_id, resource, action)
        status = "✅" if decision.granted else "❌"
        print(f"   {status} {agent_id} -> {resource}:{action} ({decision.reason})")
    
    # 5. 策略统计
    print("\n5. 策略统计:")
    stats = acm.get_policy_stats()
    for key, value in stats.items():
        print(f"   - {key}: {value}")
    
    print("\n" + "=" * 60)
    print("演示完成!")
    print("=" * 60)


if __name__ == "__main__":
    demo()