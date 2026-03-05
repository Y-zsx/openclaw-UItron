#!/usr/bin/env python3
"""
奥创安全加固层 v1.0
- API密钥认证
- 请求速率限制
- 输入验证
- 安全头
- 审计日志
"""
import hashlib
import hmac
import time
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from functools import wraps

CONFIG_DIR = "/root/.openclaw/workspace/ultron/config"
AUDIT_LOG = "/root/.openclaw/workspace/ultron/logs/audit.log"

class SecurityConfig:
    def __init__(self):
        self.api_keys = {}
        self.rate_limits = {}  # {endpoint: (requests, seconds)}
        self.allowed_ips = []
        self.blocked_ips = []
        self._load_config()
    
    def _load_config(self):
        config_file = f"{CONFIG_DIR}/security.json"
        if os.path.exists(config_file):
            with open(config_file, 'r') as f:
                data = json.load(f)
                self.api_keys = data.get('api_keys', {})
                self.rate_limits = data.get('rate_limits', {
                    '/api/status': (60, 60),
                    '/api/exec': (10, 60),
                    '/api/agent': (30, 60)
                })
                self.allowed_ips = data.get('allowed_ips', [])
                self.blocked_ips = data.get('blocked_ips', [])
        else:
            # 默认配置
            self._create_default_config()
    
    def _create_default_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        # 生成默认API密钥
        default_key = hashlib.sha256(f"ultron-{time.time()}".encode()).hexdigest()[:32]
        self.api_keys = {
            "default": {
                "key": default_key,
                "name": "default",
                "created": datetime.now().isoformat(),
                "rate_limit": (100, 60)
            }
        }
        self.rate_limits = {
            '/api/status': (60, 60),
            '/api/full': (30, 60),
            '/api/exec': (10, 60),
            '/api/agent': (30, 60)
        }
        self._save_config()
    
    def _save_config(self):
        config_file = f"{CONFIG_DIR}/security.json"
        with open(config_file, 'w') as f:
            json.dump({
                'api_keys': self.api_keys,
                'rate_limits': self.rate_limits,
                'allowed_ips': self.allowed_ips,
                'blocked_ips': self.blocked_ips
            }, f, indent=2)
    
    def add_api_key(self, name, rate_limit=(100, 60)):
        key = hashlib.sha256(f"{name}-{time.time()}".encode()).hexdigest()[:32]
        self.api_keys[name] = {
            "key": key,
            "name": name,
            "created": datetime.now().isoformat(),
            "rate_limit": rate_limit
        }
        self._save_config()
        return key
    
    def verify_api_key(self, key):
        for name, data in self.api_keys.items():
            if data['key'] == key:
                return data
        return None
    
    def check_rate_limit(self, client_id, endpoint, limit=None, window=60):
        if limit is None:
            limits = self.rate_limits.get(endpoint, (100, 60))
            limit, window = limits
        
        key = f"{client_id}:{endpoint}"
        now = time.time()
        
        if not hasattr(self, '_rate_store'):
            self._rate_store = defaultdict(list)
        
        # 清理过期记录
        self._rate_store[key] = [t for t in self._rate_store[key] if now - t < window]
        
        if len(self._rate_store[key]) >= limit:
            return False
        
        self._rate_store[key].append(now)
        return True

class SecurityAuditor:
    def __init__(self):
        os.makedirs(os.path.dirname(AUDIT_LOG), exist_ok=True)
    
    def log(self, event_type, client_ip, endpoint, details=None, severity="INFO"):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event_type,
            "client_ip": client_ip,
            "endpoint": endpoint,
            "details": details or {},
            "severity": severity
        }
        with open(AUDIT_LOG, 'a') as f:
            f.write(json.dumps(log_entry) + "\n")
    
    def get_recent_logs(self, hours=24, event_type=None):
        logs = []
        if not os.path.exists(AUDIT_LOG):
            return logs
        
        cutoff = datetime.now() - timedelta(hours=hours)
        with open(AUDIT_LOG, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    log_time = datetime.fromisoformat(entry['timestamp'])
                    if log_time >= cutoff:
                        if event_type is None or entry['event'] == event_type:
                            logs.append(entry)
                except:
                    continue
        return logs

# 安全头生成器
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
}

# 输入验证规则
class InputValidator:
    @staticmethod
    def validate_command(cmd):
        # 危险命令黑名单
        dangerous = ['rm -rf', 'mkfs', 'dd if=', '> /dev/', 'chmod 777', 'chown -R']
        for d in dangerous:
            if d in cmd.lower():
                return False, f"Dangerous command detected: {d}"
        return True, None
    
    @staticmethod
    def sanitize_path(path):
        # 防止路径遍历
        path = path.replace('..', '').replace('//', '/')
        if path.startswith('/etc') or path.startswith('/sys') or path.startswith('/proc'):
            return None
        return path
    
    @staticmethod
    def validate_filename(filename):
        # 防止文件名注入
        dangerous = [';', '|', '&', '`', '$', '(', ')']
        for d in dangerous:
            if d in filename:
                return False
        return True

# 单例
_security_config = None
_auditor = None

def get_security_config():
    global _security_config
    if _security_config is None:
        _security_config = SecurityConfig()
    return _security_config

def get_auditor():
    global _auditor
    if _auditor is None:
        _auditor = SecurityAuditor()
    return _auditor

if __name__ == "__main__":
    print("=== 奥创安全加固层 v1.0 ===")
    cfg = get_security_config()
    print(f"API密钥数量: {len(cfg.api_keys)}")
    print(f"速率限制规则: {len(cfg.rate_limits)}")
    
    auditor = get_auditor()
    logs = auditor.get_recent_logs(hours=1)
    print(f"最近1小时审计日志: {len(logs)}条")