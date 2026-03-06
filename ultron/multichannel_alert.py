#!/usr/bin/env python3
"""
多渠道告警通知服务
支持多种通知渠道: 钉钉/邮件/短信/WebHook
端口: 18221
"""

import json
import os
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
from flask import Flask, jsonify, request

app = Flask(__name__)

CONFIG_FILE = "/root/.openclaw/workspace/ultron/data/alert_channels.json"

# 默认配置
DEFAULT_CONFIG = {
    "dingtalk": {
        "enabled": False,
        "webhook": "",
        "secret": "",
        "at_mobiles": [],
        "is_at_all": False
    },
    "email": {
        "enabled": False,
        "smtp_host": "",
        "smtp_port": 587,
        "username": "",
        "password": "",
        "from_addr": "",
        "to_addrs": [],
        "use_tls": True
    },
    "webhook": {
        "enabled": False,
        "url": "",
        "method": "POST",
        "headers": {}
    },
    "console": {
        "enabled": True
    }
}

def load_config():
    """加载渠道配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(config):
    """保存渠道配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def send_dingtalk(webhook, secret, message, at_mobiles=None, is_at_all=False):
    """发送钉钉消息"""
    try:
        import hmac
        import hashlib
        import base64
        import urllib.parse
        import time
        import requests
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = secret.encode('utf-8')
        string_to_sign = f'{timestamp}\n{secret}'
        string_to_sign_enc = string_to_sign.encode('utf-8')
        sign = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = base64.b64encode(sign).decode('utf-8')
        
        url = f"{webhook}&timestamp={timestamp}&sign={urllib.parse.quote(sign)}"
        
        data = {
            "msgtype": "text",
            "text": {
                "content": f"告警通知: {message}"
            }
        }
        
        if at_mobiles:
            data["at"] = {"atMobiles": at_mobiles, "isAtAll": is_at_all}
        
        response = requests.post(url, json=data, timeout=10)
        return response.json()
    except Exception as e:
        return {"error": str(e)}

def send_email(config, subject, message):
    """发送邮件"""
    try:
        smtp_host = config.get('smtp_host')
        smtp_port = config.get('smtp_port', 587)
        username = config.get('username')
        password = config.get('password')
        from_addr = config.get('from_addr')
        to_addrs = config.get('to_addrs', [])
        
        if not all([smtp_host, username, password, from_addr, to_addrs]):
            return {"error": "Email config incomplete"}
        
        msg = MIMEText(message, 'plain', 'utf-8')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = ', '.join(to_addrs)
        
        server = smtplib.SMTP(smtp_host, smtp_port)
        if config.get('use_tls', True):
            server.starttls()
        server.login(username, password)
        server.sendmail(from_addr, to_addrs, msg.as_string())
        server.quit()
        
        return {"status": "sent"}
    except Exception as e:
        return {"error": str(e)}

def send_webhook(config, message):
    """发送WebHook"""
    try:
        import requests
        
        url = config.get('url')
        method = config.get('method', 'POST')
        headers = config.get('headers', {})
        
        if not url:
            return {"error": "Webhook URL not configured"}
        
        data = {
            "message": message,
            "timestamp": datetime.now().isoformat(),
            "source": "ultron-alert"
        }
        
        if method == "POST":
            response = requests.post(url, json=data, headers=headers, timeout=10)
        else:
            response = requests.get(url, params=data, headers=headers, timeout=10)
        
        return {"status": response.status_code, "response": response.text[:100]}
    except Exception as e:
        return {"error": str(e)}

@app.route('/api/notify', methods=['POST'])
def notify():
    """发送告警通知"""
    data = request.get_json()
    message = data.get('message', '')
    level = data.get('level', 'info')
    title = data.get('title', '告警通知')
    
    config = load_config()
    results = {}
    
    # 钉钉
    if config.get('dingtalk', {}).get('enabled') and config.get('dingtalk', {}).get('webhook'):
        dt = config['dingtalk']
        result = send_dingtalk(
            dt['webhook'], 
            dt.get('secret', ''),
            f"[{level.upper()}] {title}\n{message}",
            dt.get('at_mobiles', []),
            dt.get('is_at_all', False)
        )
        results['dingtalk'] = result
    
    # 邮件
    if config.get('email', {}).get('enabled'):
        result = send_email(
            config['email'],
            f"[{level.upper()}] {title}",
            message
        )
        results['email'] = result
    
    # WebHook
    if config.get('webhook', {}).get('enabled') and config.get('webhook', {}).get('url'):
        result = send_webhook(config['webhook'], f"[{level.upper()}] {title}\n{message}")
        results['webhook'] = result
    
    # 控制台
    if config.get('console', {}).get('enabled'):
        print(f"[{datetime.now().isoformat()}] [{level.upper()}] {title}: {message}")
        results['console'] = {"status": "sent"}
    
    return jsonify({
        "status": "ok",
        "message": message,
        "level": level,
        "results": results,
        "sent_at": datetime.now().isoformat()
    })

@app.route('/api/channels', methods=['GET'])
def list_channels():
    """列出所有渠道配置"""
    config = load_config()
    
    channels = []
    for name, info in config.items():
        channels.append({
            "name": name,
            "enabled": info.get('enabled', False),
            "description": get_channel_description(name)
        })
    
    return jsonify({
        "status": "ok",
        "channels": channels
    })

def get_channel_description(name):
    """获取渠道描述"""
    descriptions = {
        "dingtalk": "钉钉群机器人通知",
        "email": "电子邮件通知",
        "webhook": "自定义WebHook回调",
        "console": "控制台输出"
    }
    return descriptions.get(name, name)

@app.route('/api/channels/<name>', methods=['GET'])
def get_channel(name):
    """获取指定渠道配置"""
    config = load_config()
    
    if name not in config:
        return jsonify({"status": "error", "message": f"Channel '{name}' not found"}), 404
    
    channel = config[name].copy()
    # 隐藏敏感信息
    if 'password' in channel:
        channel['password'] = '***' if channel['password'] else ''
    if 'secret' in channel:
        channel['secret'] = '***' if channel['secret'] else ''
    
    return jsonify({
        "status": "ok",
        "name": name,
        "config": channel
    })

@app.route('/api/channels/<name>', methods=['PUT', 'POST'])
def update_channel(name):
    """更新渠道配置"""
    config = load_config()
    data = request.get_json()
    
    if name not in config:
        return jsonify({"status": "error", "message": f"Channel '{name}' not found"}), 404
    
    # 更新配置
    config[name].update(data)
    save_config(config)
    
    return jsonify({
        "status": "ok",
        "name": name,
        "config": config[name]
    })

@app.route('/api/channels/<name>/test', methods=['POST'])
def test_channel(name):
    """测试渠道通知"""
    config = load_config()
    
    if name not in config:
        return jsonify({"status": "error", "message": f"Channel '{name}' not found"}), 404
    
    test_message = "这是一条测试消息"
    
    if name == 'dingtalk':
        if not config[name].get('webhook'):
            return jsonify({"status": "error", "message": "Webhook not configured"}), 400
        result = send_dingtalk(
            config[name]['webhook'],
            config[name].get('secret', ''),
            test_message
        )
    elif name == 'email':
        if not config[name].get('enabled'):
            return jsonify({"status": "error", "message": "Email not enabled"}), 400
        result = send_email(config[name], "测试邮件", test_message)
    elif name == 'webhook':
        if not config[name].get('url'):
            return jsonify({"status": "error", "message": "Webhook URL not configured"}), 400
        result = send_webhook(config[name], test_message)
    elif name == 'console':
        print(f"[TEST] {test_message}")
        result = {"status": "sent"}
    else:
        return jsonify({"status": "error", "message": "Unknown channel"}), 400
    
    return jsonify({
        "status": "ok",
        "channel": name,
        "result": result
    })

@app.route('/health', methods=['GET'])
def health():
    config = load_config()
    enabled_channels = [k for k, v in config.items() if v.get('enabled')]
    
    return jsonify({
        "status": "healthy",
        "service": "multichannel-alert",
        "port": 18221,
        "enabled_channels": enabled_channels
    })

if __name__ == '__main__':
    print("启动多渠道告警通知服务...")
    print(f"端口: 18221")
    print(f"配置文件: {CONFIG_FILE}")
    app.run(host='0.0.0.0', port=18221, debug=False)