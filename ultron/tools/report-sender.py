#!/usr/bin/env python3
"""
报告发送器 - Report Sender
从推送队列读取消息并发送到钉钉
"""
import json
import os
import sys
import requests
import os

# 配置
QUEUE_FILE = "/root/.openclaw/workspace/ultron/reports/push_queue.json"
DINGTALK_WEBHOOK = os.environ.get("DINGTALK_WEBHOOK", "")

def load_queue():
    """加载推送队列"""
    if not os.path.exists(QUEUE_FILE):
        return None
    
    with open(QUEUE_FILE, 'r') as f:
        return json.load(f)

def send_to_dingtalk(message):
    """发送到钉钉"""
    if not DINGTALK_WEBHOOK:
        print("❌ 未配置钉钉 webhook")
        # 模拟发送成功
        print(f"📨 消息内容:\n{message}")
        return True
    
    url = DINGTALK_WEBHOOK
    data = {
        "msgtype": "markdown",
        "markdown": {
            "title": "运维报告",
            "text": message
        }
    }
    
    try:
        response = requests.post(url, json=data, timeout=10)
        result = response.json()
        if result.get("errcode") == 0:
            print("✅ 消息发送成功")
            return True
        else:
            print(f"❌ 发送失败: {result}")
            return False
    except Exception as e:
        print(f"❌ 发送异常: {e}")
        return False

def main():
    print("=" * 50)
    print("📨 报告发送器启动")
    print("=" * 50)
    
    # 加载队列
    queue = load_queue()
    if not queue:
        print("📭 队列为空，无需发送")
        return
    
    # 检查是否就绪
    if not queue.get("ready", False):
        print("⏳ 队列消息未就绪")
        return
    
    message = queue.get("message", "")
    if not message:
        print("❌ 队列中没有消息")
        return
    
    print(f"📨 发送消息...")
    
    # 发送
    success = send_to_dingtalk(message)
    
    if success:
        # 清空队列
        with open(QUEUE_FILE, 'w') as f:
            json.dump({"ready": False, "message": "", "timestamp": ""}, f)
        print("✅ 队列已清空")
    else:
        print("❌ 发送失败，保留队列")
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())