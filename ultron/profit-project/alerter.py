#!/usr/bin/env python3
"""
网站监控告警模块 - 钉钉通知
"""

import requests
import json
import os

DINGTALK_WEBHOOK = os.environ.get('DINGTALK_WEBHOOK', '')

def send_dingtalk(message, webhook=None):
    """发送钉钉消息"""
    webhook = webhook or DINGTALK_WEBHOOK
    if not webhook:
        print("⚠️ 未配置钉钉Webhook")
        return False
    
    msg_type = "text"
    data = {
        "msgtype": msg_type,
        "text": {
            "content": f"【网站监控告警】\n{message}"
        }
    }
    
    try:
        response = requests.post(webhook, json=data, timeout=10)
        result = response.json()
        if result.get('errcode') == 0:
            print("✅ 钉钉通知发送成功")
            return True
        else:
            print(f"❌ 钉钉通知失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 钉钉通知异常: {e}")
        return False

def send_alert(site, url, error):
    """发送告警消息"""
    message = f"站点: {site}\nURL: {url}\n错误: {error}"
    return send_dingtalk(message)

if __name__ == "__main__":
    # 测试发送
    import sys
    if len(sys.argv) > 1:
        send_alert("测试站点", "https://test.com", sys.argv[1])
    else:
        send_alert("测试站点", "https://test.com", "测试告警")