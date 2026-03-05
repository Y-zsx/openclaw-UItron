#!/usr/bin/env python3
"""
安全中间件 - Flask/Werkzeug集成
用法: 在Flask app中注册此中间件
"""
from flask import request, jsonify, g
from functools import wraps
from security_layer import get_security_config, get_auditor, SECURITY_HEADERS, InputValidator
import os

class SecurityMiddleware:
    def __init__(self, app=None):
        self.app = app
        self.cfg = get_security_config()
        self.auditor = get_auditor()
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        @app.before_request
        def before_request():
            client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
            endpoint = request.path
            
            # 检查IP黑名单
            if client_ip in self.cfg.blocked_ips:
                self.auditor.log("BLOCKED_IP", client_ip, endpoint, severity="WARNING")
                return jsonify({"error": "Access denied"}), 403
            
            # API密钥验证 (除健康检查外)
            if endpoint not in ['/health', '/api/health']:
                auth_header = request.headers.get('Authorization', '')
                if auth_header.startswith('Bearer '):
                    key = auth_header[7:]
                    key_data = self.cfg.verify_api_key(key)
                    if not key_data:
                        self.auditor.log("INVALID_KEY", client_ip, endpoint, severity="WARNING")
                        return jsonify({"error": "Invalid API key"}), 401
                    g.api_key_name = key_data['name']
                    g.client_id = key_data['name']
                else:
                    # 允许无密钥访问状态端点
                    if not endpoint.startswith('/status') and not endpoint.startswith('/api/status'):
                        self.auditor.log("NO_AUTH", client_ip, endpoint, severity="INFO")
            
            # 速率限制检查
            client_id = getattr(g, 'client_id', client_ip)
            if not self.cfg.check_rate_limit(client_id, endpoint):
                self.auditor.log("RATE_LIMIT", client_id, endpoint, severity="WARNING")
                return jsonify({"error": "Rate limit exceeded"}), 429
            
            # 输入验证
            if request.method == 'POST':
                if request.is_json:
                    data = request.get_json()
                    if 'cmd' in data:
                        valid, err = InputValidator.validate_command(data['cmd'])
                        if not valid:
                            self.auditor.log("DANGEROUS_CMD", client_id, endpoint, {"cmd": data['cmd']}, severity="CRITICAL")
                            return jsonify({"error": str(err)}), 400
            
            # 记录请求
            self.auditor.log("REQUEST", client_id, endpoint)
        
        @app.after_request
        def after_request(response):
            # 添加安全头
            for header, value in SECURITY_HEADERS.items():
                response.headers[header] = value
            return response

def require_api_key(f):
    """装饰器: 要求API密钥"""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "API key required"}), 401
        
        key = auth_header[7:]
        cfg = get_security_config()
        key_data = cfg.verify_api_key(key)
        
        if not key_data:
            return jsonify({"error": "Invalid API key"}), 401
        
        g.client_id = key_data['name']
        return f(*args, **kwargs)
    return decorated

# 独立安全API服务
SECURITY_API_PORT = 18097

def create_security_api():
    from flask import Flask
    app = Flask(__name__)
    SecurityMiddleware(app)
    
    @app.route('/health')
    def health():
        return jsonify({"status": "ok", "security": "enabled"})
    
    @app.route('/api/security/status')
    def security_status():
        cfg = get_security_config()
        auditor = get_auditor()
        return jsonify({
            "api_keys": len(cfg.api_keys),
            "rate_limits": len(cfg.rate_limits),
            "blocked_ips": len(cfg.blocked_ips),
            "audit_logs_24h": len(auditor.get_recent_logs(hours=24))
        })
    
    return app

if __name__ == "__main__":
    app = create_security_api()
    print(f"启动安全中间件服务: 0.0.0.0:{SECURITY_API_PORT}")
    app.run(host='0.0.0.0', port=SECURITY_API_PORT)