#!/usr/bin/env python3
"""
网站监控告警模块 - 钉钉通知 + 自动记录
"""

import requests
import json
import os
import sys

# 添加告警模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'alerts'))
try:
    from alert_store import AlertStore
    alert_store = AlertStore()
except Exception as e:
    print(f"⚠️ 告警存储模块加载失败: {e}")
    alert_store = None

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

def send_alert(site, url, error, alert_type="site_down"):
    """发送告警消息并自动记录"""
    message = f"站点: {site}\nURL: {url}\n错误: {error}"
    
    # 自动记录告警
    if alert_store:
        try:
            alert_store.add(alert_type, site, url, error, "error")
            print(f"📝 告警已自动记录")
        except Exception as e:
            print(f"⚠️ 告警记录失败: {e}")
    
    return send_dingtalk(message)

if __name__ == "__main__":
    # 测试发送
    import sys
    if len(sys.argv) > 1:
        send_alert("测试站点", "https://test.com", sys.argv[1])
    else:
        send_alert("测试站点", "https://test.com", "测试告警")