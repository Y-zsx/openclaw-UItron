#!/usr/bin/env python3
"""
智能告警通知API服务
集成钉钉/邮件通知到决策系统
端口: 18124
"""
import json
import os
import sys
from pathlib import Path
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import urllib.parse

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))
from notifier import AlertNotifier

NOTIFIER_DIR = Path("/root/.openclaw/workspace/ultron-workflow/monitoring")
CONFIG_FILE = NOTIFIER_DIR / "config.json"
PORT = 18124

# 全局通知器
notifier = AlertNotifier()


class NotificationAPIHandler(BaseHTTPRequestHandler):
    """通知API处理器"""
    
    def log_message(self, format, *args):
        """自定义日志"""
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {format % args}")
    
    def send_json(self, status_code, data):
        """发送JSON响应"""
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
    
    def do_GET(self):
        """处理GET请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == '/health' or path == '/':
            # 健康检查
            self.send_json(200, {
                "status": "ok",
                "service": "notification-api",
                "port": PORT,
                "timestamp": datetime.now().isoformat()
            })
        
        elif path == '/config':
            # 获取配置
            self.send_json(200, notifier.config)
        
        elif path == '/channels':
            # 获取可用渠道
            self.send_json(200, {
                "available": ["console", "dingtalk", "email"],
                "enabled": notifier.config.get("channels", [])
            })
        
        else:
            self.send_json(404, {"error": "not found"})
    
    def do_POST(self):
        """处理POST请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except json.JSONDecodeError:
            self.send_json(400, {"error": "invalid json"})
            return
        
        if path == '/notify' or path == '/alert':
            # 发送告警通知
            alert = data
            
            # 添加时间戳
            if 'timestamp' not in alert:
                alert['timestamp'] = datetime.now().isoformat()
            
            result = notifier.notify(alert)
            self.send_json(200, result)
        
        elif path == '/notify/batch':
            # 批量通知
            alerts = data.get("alerts", [])
            results = notifier.notify_batch(alerts)
            self.send_json(200, {"results": results})
        
        elif path == '/config/set':
            # 设置配置
            key = data.get("key")
            value = data.get("value")
            
            if not key:
                self.send_json(400, {"error": "key required"})
                return
            
            result = notifier.set_config(key, value)
            self.send_json(200, result)
        
        elif path == '/config/channels':
            # 设置通知渠道
            channels = data.get("channels", [])
            notifier.set_config("channels", channels)
            self.send_json(200, {"status": "ok", "channels": channels})
        
        elif path == '/test':
            # 发送测试告警
            test_alert = {
                "level": data.get("level", "info"),
                "message": data.get("message", "测试告警 - 系统运行正常"),
                "timestamp": datetime.now().isoformat(),
                "context": data.get("context", {"test": True})
            }
            result = notifier.notify(test_alert)
            self.send_json(200, result)
        
        else:
            self.send_json(404, {"error": "not found"})


def start_server(port=PORT):
    """启动API服务器"""
    server = HTTPServer(('0.0.0.0', port), NotificationAPIHandler)
    print(f"🤖 智能告警通知API服务启动成功")
    print(f"   端口: {port}")
    print(f"   端点:")
    print(f"   - GET  /health        健康检查")
    print(f"   - GET  /config        获取配置")
    print(f"   - GET  /channels      获取可用渠道")
    print(f"   - POST /notify        发送告警")
    print(f"   - POST /notify/batch  批量通知")
    print(f"   - POST /config/set    设置配置")
    print(f"   - POST /config/channels 设置通知渠道")
    print(f"   - POST /test          测试通知")
    print(f"\n监听中...")
    server.serve_forever()


def run_background(port=PORT):
    """后台运行"""
    import daemon
    with daemon.DaemonContext():
        start_server(port)


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "start":
            # 前台启动
            start_server(int(sys.argv[2]) if len(sys.argv) > 2 else PORT)
        elif sys.argv[1] == "daemon":
            # 后台运行
            run_background()
        elif sys.argv[1] == "test":
            # 测试通知
            test_alert = {
                "level": "warning",
                "message": "测试告警 - 通知系统正常",
                "timestamp": datetime.now().isoformat(),
                "context": {"test": True}
            }
            result = notifier.notify(test_alert)
            print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        start_server()