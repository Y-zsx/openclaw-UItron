#!/usr/bin/env python3
"""
告警通知集成中心
统一管理所有告警通知渠道和集成
端口: 18280
"""
import json
import os
import sys
import subprocess
import hmac
import hashlib
import base64
import urllib.parse
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse
import sqlite3

NOTIFIER_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
CONFIG_FILE = NOTIFIER_DIR / "alert_integration_config.json"
DB_FILE = NOTIFIER_DIR / "alert_integration.db"


class AlertIntegrationDB:
    """告警集成数据库"""
    
    def __init__(self):
        self.init_db()
    
    def init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        
        # 创建告警历史表
        c.execute('''CREATE TABLE IF NOT EXISTS alert_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id TEXT,
            level TEXT,
            message TEXT,
            channel TEXT,
            status TEXT,
            timestamp TEXT,
            response TEXT
        )''')
        
        # 创建集成配置表
        c.execute('''CREATE TABLE IF NOT EXISTS integrations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE,
            type TEXT,
            config TEXT,
            enabled INTEGER DEFAULT 1,
            created_at TEXT,
            updated_at TEXT
        )''')
        
        conn.commit()
        conn.close()
    
    def save_alert(self, alert_id, level, message, channel, status, response):
        """保存告警记录"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''INSERT INTO alert_history 
            (alert_id, level, message, channel, status, timestamp, response)
            VALUES (?, ?, ?, ?, ?, ?, ?)''',
            (alert_id, level, message, channel, status, datetime.now().isoformat(), json.dumps(response)))
        conn.commit()
        conn.close()
    
    def get_history(self, limit=100):
        """获取告警历史"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT * FROM alert_history ORDER BY timestamp DESC LIMIT ?', (limit,))
        rows = c.fetchall()
        conn.close()
        return rows
    
    def save_integration(self, name, itype, config):
        """保存集成配置"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        now = datetime.now().isoformat()
        c.execute('''INSERT OR REPLACE INTO integrations (name, type, config, updated_at)
            VALUES (?, ?, ?, ?)''', (name, itype, json.dumps(config), now))
        conn.commit()
        conn.close()
    
    def get_integration(self, name):
        """获取集成配置"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT * FROM integrations WHERE name = ?', (name,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"name": row[1], "type": row[2], "config": json.loads(row[3]), "enabled": bool(row[4])}
        return None
    
    def list_integrations(self):
        """列出所有集成"""
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('SELECT name, type, enabled FROM integrations')
        rows = c.fetchall()
        conn.close()
        return [{"name": r[0], "type": r[1], "enabled": bool(r[2])} for r in rows]


class AlertIntegration:
    """告警通知集成中心"""
    
    def __init__(self):
        self.config = self.load_config()
        self.db = AlertIntegrationDB()
        self.default_channels = self.config.get("channels", ["console"])
    
    def load_config(self):
        """加载配置"""
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                return json.load(f)
        
        default_config = {
            "enabled": True,
            "channels": ["console", "dingtalk"],
            "rate_limit": {
                "enabled": True,
                "max_per_minute": 10
            },
            "integrations": {}
        }
        
        with open(CONFIG_FILE, 'w') as f:
            json.dump(default_config, f, indent=2, ensure_ascii=False)
        
        return default_config
    
    def save_config(self):
        """保存配置"""
        with open(CONFIG_FILE, 'w') as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
    
    def generate_alert_id(self):
        """生成唯一告警ID"""
        return f"alert_{datetime.now().strftime('%Y%m%d%H%M%S')}_{int(datetime.now().timestamp() * 1000) % 1000}"
    
    def send_dingtalk(self, webhook, secret, alert):
        """发送钉钉通知"""
        if not webhook:
            return {"status": "error", "reason": "no_webhook"}
        
        level = alert.get("level", "info")
        message = alert.get("message", "")
        
        # 构建消息
        msg_type = "markdown" if level in ["error", "critical"] else "text"
        
        if msg_type == "markdown":
            content = f"### 🦞 奥创告警\n\n" \
                     f"**级别**: {level.upper()}\n\n" \
                     f"**消息**: {message}\n\n" \
                     f"**时间**: {alert.get('timestamp', '')}\n\n" \
                     f"**来源**: {alert.get('source', 'system')}"
            if alert.get('context'):
                content += f"\n\n**详情**: {json.dumps(alert.get('context'), ensure_ascii=False, indent=2)}"
        else:
            content = f"🦞 奥创告警\n级别: {level.upper()}\n消息: {message}\n来源: {alert.get('source', 'system')}"
        
        payload = {
            "msgtype": msg_type,
            msg_type: {
                "content": content
            }
        }
        
        # 如果有密钥，使用签名
        webhook_url = webhook
        if secret:
            timestamp = str(int(datetime.now().timestamp() * 1000))
            sign_str = f"{timestamp}\n{secret}"
            sign = base64.b64encode(hmac.new(secret.encode(), sign_str.encode(), hashlib.sha256).digest()).decode()
            sign = urllib.parse.quote_plus(sign)
            webhook_url = f"{webhook}&timestamp={timestamp}&sign={sign}"
        
        try:
            cmd = [
                "curl", "-s", "-X", "POST",
                "-H", "Content-Type: application/json",
                "-d", json.dumps(payload, ensure_ascii=False),
                webhook_url
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                return {"status": "ok", "response": json.loads(result.stdout) if result.stdout else {}}
            else:
                return {"status": "error", "reason": result.stderr}
        
        except Exception as e:
            return {"status": "error", "reason": str(e)}
    
    def send_console(self, alert):
        """控制台通知"""
        level = alert.get("level", "info")
        message = alert.get("message", "")
        source = alert.get("source", "system")
        
        emojis = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🚨"}
        emoji = emojis.get(level, "ℹ️")
        
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {emoji} [{level.upper()}] [{source}] {message}")
        return {"status": "ok"}
    
    def notify(self, alert):
        """发送告警通知"""
        alert_id = self.generate_alert_id()
        alert["alert_id"] = alert_id
        alert["timestamp"] = alert.get("timestamp", datetime.now().isoformat())
        
        channels = self.config.get("channels", ["console"])
        results = []
        
        for channel in channels:
            if channel == "dingtalk":
                webhook = self.config.get("dingtalk_webhook")
                secret = self.config.get("dingtalk_secret")
                result = self.send_dingtalk(webhook, secret, alert)
                results.append({"channel": "dingtalk", "result": result})
                self.db.save_alert(alert_id, alert.get("level"), alert.get("message"), "dingtalk", result.get("status"), result)
            
            elif channel == "console":
                result = self.send_console(alert)
                results.append({"channel": "console", "result": result})
                self.db.save_alert(alert_id, alert.get("level"), alert.get("message"), "console", "ok", {})
        
        return {
            "alert_id": alert_id,
            "status": "sent",
            "results": results,
            "timestamp": alert["timestamp"]
        }
    
    def configure_dingtalk(self, webhook, secret=None):
        """配置钉钉"""
        self.config["dingtalk_webhook"] = webhook
        if secret:
            self.config["dingtalk_secret"] = secret
        self.save_config()
        return {"status": "configured", "webhook_set": bool(webhook)}
    
    def test_channel(self, channel):
        """测试通知渠道"""
        test_alert = {
            "level": "info",
            "message": "测试告警 - 通知系统正常运行",
            "source": "alert-integration-test",
            "timestamp": datetime.now().isoformat(),
            "context": {"test": True}
        }
        
        if channel == "dingtalk":
            webhook = self.config.get("dingtalk_webhook")
            secret = self.config.get("dingtalk_secret")
            return self.send_dingtalk(webhook, secret, test_alert)
        elif channel == "console":
            return self.send_console(test_alert)
        
        return {"status": "unknown_channel"}
    
    def get_status(self):
        """获取集成状态"""
        return {
            "enabled": self.config.get("enabled", True),
            "channels": self.config.get("channels", []),
            "dingtalk_configured": bool(self.config.get("dingtalk_webhook")),
            "integrations": self.db.list_integrations(),
            "db_file": str(DB_FILE)
        }


# 全局实例
integration = AlertIntegration()


class AlertIntegrationHandler(BaseHTTPRequestHandler):
    """API处理器"""
    
    def log_message(self, format, *args):
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
    
    def send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/health' or path == '/':
            self.send_json(200, {
                "status": "ok",
                "service": "alert-integration",
                "port": 18280,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/status':
            self.send_json(200, integration.get_status())
        
        elif path == '/history':
            limit = int(urllib.parse.parse_qs(parsed.query).get('limit', [100])[0])
            history = integration.db.get_history(limit)
            self.send_json(200, {"history": history})
        
        elif path == '/integrations':
            self.send_json(200, {"integrations": integration.db.list_integrations()})
        
        else:
            self.send_json(404, {"error": "not found"})
    
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid json"})
            return
        
        if path == '/notify' or path == '/alert':
            result = integration.notify(data)
            self.send_json(200, result)
        
        elif path == '/config/dingtalk':
            webhook = data.get("webhook")
            secret = data.get("secret")
            result = integration.configure_dingtalk(webhook, secret)
            self.send_json(200, result)
        
        elif path == '/test':
            channel = data.get("channel", "console")
            result = integration.test_channel(channel)
            self.send_json(200, result)
        
        elif path == '/integration/add':
            name = data.get("name")
            itype = data.get("type")
            config = data.get("config", {})
            integration.db.save_integration(name, itype, config)
            self.send_json(200, {"status": "saved", "name": name})
        
        else:
            self.send_json(404, {"error": "not found"})


def start_server(port=18280):
    server = HTTPServer(('0.0.0.0', port), AlertIntegrationHandler)
    print(f"🦞 告警通知集成中心启动成功")
    print(f"   端口: {port}")
    print(f"   端点:")
    print(f"   - GET  /health        健康检查")
    print(f"   - GET  /status        集成状态")
    print(f"   - GET  /history       告警历史")
    print(f"   - GET  /integrations  集成列表")
    print(f"   - POST /notify        发送告警")
    print(f"   - POST /config/dingtalk 配置钉钉")
    print(f"   - POST /test          测试渠道")
    print(f"   - POST /integration/add 添加集成")
    print(f"\n监听中...")
    server.serve_forever()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "start":
        start_server()
    else:
        start_server()