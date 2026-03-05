#!/usr/bin/env python3
"""
Agent服务配置管理中心 (port 18163)
统一管理所有运维服务的配置，支持配置的CRUD、版本管理、热更新
"""

import json
import os
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse, parse_qs

CONFIG_FILE = "/root/.openclaw/workspace/ultron-data/configs.json"
HISTORY_FILE = "/root/.openclaw/workspace/ultron-data/config-history.json"
PORT = 18163

# 默认配置模板
DEFAULT_CONFIGS = {
    "global": {
        "log_level": "INFO",
        "health_check_interval": 30,
        "auto_recovery": True,
        "alert_threshold": 80
    },
    "load_balancer": {
        "strategy": "random",
        "max_retries": 3,
        "timeout": 60,
        "weight_algorithm": "dynamic"
    },
    "auto_scaler": {
        "min_agents": 1,
        "max_agents": 10,
        "scale_up_threshold": 70,
        "scale_down_threshold": 20,
        "cooldown_period": 120
    },
    "monitor": {
        "metrics_interval": 10,
        "retention_days": 7,
        "alert_channels": ["dingtalk"]
    },
    "task_queue": {
        "max_queue_size": 1000,
        "task_timeout": 300,
        "retry_policy": "exponential"
    }
}

def load_configs():
    """加载配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return DEFAULT_CONFIGS.copy()

def save_configs(configs):
    """保存配置"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(configs, f, indent=2)

def load_history():
    """加载配置历史"""
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            return json.load(f)
    return []

def save_history(history):
    """保存配置历史"""
    with open(HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def add_history(service, action, old_value, new_value):
    """添加配置变更历史"""
    history = load_history()
    history.append({
        "timestamp": datetime.now().isoformat(),
        "service": service,
        "action": action,
        "old_value": old_value,
        "new_value": new_value
    })
    # 只保留最近100条
    history = history[-100:]
    save_history(history)

class ConfigHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)

        if path == '/health':
            self.send_json({"status": "ok", "service": "config-manager", "port": PORT})
        elif path == '/api/configs':
            configs = load_configs()
            self.send_json({"configs": configs, "count": len(configs)})
        elif path == '/api/config':
            service = params.get('service', [None])[0]
            if not service:
                self.send_json({"error": "service required"}, 400)
                return
            configs = load_configs()
            if service not in configs:
                self.send_json({"error": f"service {service} not found"}, 404)
                return
            self.send_json({"service": service, "config": configs[service]})
        elif path == '/api/history':
            history = load_history()
            limit = int(params.get('limit', [20])[0])
            self.send_json({"history": history[-limit:], "count": len(history)})
        elif path == '/api/services':
            configs = load_configs()
            self.send_json({"services": list(configs.keys())})
        else:
            self.send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode() if content_length > 0 else '{}'

        try:
            data = json.loads(body)
        except:
            self.send_json({"error": "invalid json"}, 400)
            return

        if path == '/api/config':
            service = data.get('service')
            config = data.get('config')
            if not service or not config:
                self.send_json({"error": "service and config required"}, 400)
                return

            configs = load_configs()
            old_value = configs.get(service, {})
            configs[service] = config
            save_configs(configs)
            add_history(service, "update", old_value, config)
            self.send_json({
                "status": "success",
                "service": service,
                "message": f"config updated for {service}"
            })
        elif path == '/api/config/reset':
            service = data.get('service')
            configs = load_configs()
            if service:
                if service not in DEFAULT_CONFIGS:
                    self.send_json({"error": f"service {service} not found"}, 404)
                    return
                old_value = configs.get(service, {})
                configs[service] = DEFAULT_CONFIGS[service]
                save_configs(configs)
                add_history(service, "reset", old_value, DEFAULT_CONFIGS[service])
                self.send_json({
                    "status": "success",
                    "service": service,
                    "message": f"config reset to default for {service}"
                })
            else:
                configs = DEFAULT_CONFIGS.copy()
                save_configs(configs)
                add_history("all", "reset_all", {}, DEFAULT_CONFIGS)
                self.send_json({
                    "status": "success",
                    "message": "all configs reset to default"
                })
        elif path == '/api/config/validate':
            service = data.get('service')
            config = data.get('config')
            if not service or not config:
                self.send_json({"error": "service and config required"}, 400)
                return
            
            # 简单的配置验证
            errors = []
            # 添加验证逻辑
            self.send_json({
                "valid": len(errors) == 0,
                "errors": errors
            })
        else:
            self.send_json({"error": "not found"}, 404)

    def do_PUT(self):
        # PUT等同于POST的更新
        self.do_POST()

def run_server():
    # 初始化默认配置
    if not os.path.exists(CONFIG_FILE):
        save_configs(DEFAULT_CONFIGS.copy())
    
    server = HTTPServer(('0.0.0.0', PORT), ConfigHandler)
    print(f"Config Manager running on port {PORT}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()