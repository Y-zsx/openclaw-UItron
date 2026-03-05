#!/usr/bin/env python3
"""
智能运维助手 - 告警通知渠道
第29世: 实现告警通知渠道
"""

import json
import os
import time
import requests
from datetime import datetime
from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum


class AlertLevel(Enum):
    """告警级别"""
    CRITICAL = 1
    WARNING = 2
    INFO = 3


class AlertChannel(ABC):
    """告警渠道基类"""
    
    @abstractmethod
    def send(self, alert: Dict[str, Any]) -> bool:
        """发送告警"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """渠道名称"""
        pass


class ConsoleChannel(AlertChannel):
    """控制台输出渠道"""
    
    def get_name(self) -> str:
        return "console"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        level = alert.get('level', 'INFO')
        level_emoji = {
            "CRITICAL": "🔴",
            "WARNING": "🟡",
            "INFO": "🔵"
        }.get(level, "⚪")
        
        print(f"\n{'='*60}")
        print(f"{level_emoji} [{level}] {alert.get('message', '告警')}")
        print(f"   规则: {alert.get('rule', 'N/A')}")
        print(f"   指标: {alert.get('metric', 'N/A')} = {alert.get('value', 'N/A')}")
        print(f"   阈值: {alert.get('condition', 'N/A')} {alert.get('threshold', 'N/A')}")
        print(f"   时间: {alert.get('timestamp', 'N/A')}")
        print(f"{'='*60}\n")
        
        return True


class FileChannel(AlertChannel):
    """文件存储渠道"""
    
    def __init__(self, file_path: str = "/root/.openclaw/workspace/ultron/alerts/alerts.json"):
        self.file_path = file_path
        self._ensure_file()
    
    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump([], f)
    
    def get_name(self) -> str:
        return "file"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        try:
            # 读取现有告警
            with open(self.file_path, 'r') as f:
                alerts = json.load(f)
            
            # 添加新告警
            alert['_id'] = f"alert_{int(time.time() * 1000)}"
            alert['_created_at'] = time.time()
            alerts.append(alert)
            
            # 只保留最近1000条
            alerts = alerts[-1000:]
            
            # 写入
            with open(self.file_path, 'w') as f:
                json.dump(alerts, f, indent=2, ensure_ascii=False)
            
            return True
        except Exception as e:
            print(f"❌ 文件渠道发送失败: {e}")
            return False


class DingTalkChannel(AlertChannel):
    """钉钉 webhook 渠道"""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or os.environ.get("DINGTALK_WEBHOOK", "")
        self.secret = os.environ.get("DINGTALK_SECRET", "")
    
    def get_name(self) -> str:
        return "dingtalk"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            print("⚠️ 钉钉 webhook 未配置")
            return False
        
        try:
            level = alert.get('level', 'INFO')
            level_emoji = {
                "CRITICAL": "🔴",
                "WARNING": "🟡",
                "INFO": "🔵"
            }.get(level, "⚪")
            
            # 构造消息
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"服务器告警 - {level}",
                    "text": f"### {level_emoji} {alert.get('message', '告警通知')}\n\n"
                            f"- **规则**: {alert.get('rule', 'N/A')}\n"
                            f"- **指标**: {alert.get('metric', 'N/A')} = `{alert.get('value', 'N/A')}`\n"
                            f"- **阈值**: {alert.get('condition', '')} {alert.get('threshold', '')}\n"
                            f"- **级别**: {level}\n"
                            f"- **时间**: {alert.get('timestamp', 'N/A')}\n\n"
                            f"> 来自奥创智能运维系统"
                }
            }
            
            response = requests.post(
                self.webhook_url, 
                json=message, 
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('errcode') == 0:
                    print(f"✅ 钉钉通知发送成功")
                    return True
            
            print(f"❌ 钉钉发送失败: {response.text}")
            return False
            
        except Exception as e:
            print(f"❌ 钉钉渠道异常: {e}")
            return False


class AlertNotifier:
    """告警通知器"""
    
    def __init__(self):
        self.channels: List[AlertChannel] = []
        self._init_default_channels()
    
    def _init_default_channels(self):
        """初始化默认渠道"""
        # 控制台输出
        self.channels.append(ConsoleChannel())
        
        # 文件存储
        self.channels.append(FileChannel())
        
        # 钉钉 (如果配置了)
        self.channels.append(DingTalkChannel())
    
    def add_channel(self, channel: AlertChannel):
        """添加渠道"""
        self.channels.append(channel)
    
    def remove_channel(self, name: str):
        """移除渠道"""
        self.channels = [c for c in self.channels if c.get_name() != name]
    
    def notify(self, alerts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """发送告警到所有渠道"""
        results = {
            "total": len(alerts),
            "channels": {},
            "failed": []
        }
        
        for alert in alerts:
            for channel in self.channels:
                try:
                    success = channel.send(alert)
                    channel_name = channel.get_name()
                    if channel_name not in results["channels"]:
                        results["channels"][channel_name] = {"sent": 0, "failed": 0}
                    
                    if success:
                        results["channels"][channel_name]["sent"] += 1
                    else:
                        results["channels"][channel_name]["failed"] += 1
                        results["failed"].append(channel_name)
                except Exception as e:
                    print(f"❌ 渠道 {channel.get_name()} 异常: {e}")
        
        return results


def main():
    """测试告警通知"""
    # 模拟告警数据
    test_alerts = [
        {
            "rule": "CPU使用率过高",
            "metric": "cpu.usage_percent",
            "value": 92.5,
            "threshold": 90,
            "condition": "gte",
            "level": "WARNING",
            "message": "CPU使用率超过90%",
            "timestamp": datetime.now().isoformat()
        },
        {
            "rule": "内存使用率过高",
            "metric": "memory.percent",
            "value": 88.0,
            "threshold": 85,
            "condition": "gte",
            "level": "WARNING",
            "message": "内存使用率超过85%",
            "timestamp": datetime.now().isoformat()
        },
        {
            "rule": "CPU使用率严重",
            "metric": "cpu.usage_percent",
            "value": 97.0,
            "threshold": 95,
            "condition": "gte",
            "level": "CRITICAL",
            "message": "CPU使用率超过95%",
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    notifier = AlertNotifier()
    
    print("=" * 60)
    print("智能运维助手 - 告警通知渠道")
    print("=" * 60)
    print(f"\n📢 初始化渠道数: {len(notifier.channels)}")
    
    for i, ch in enumerate(notifier.channels, 1):
        print(f"   {i}. {ch.get_name()}")
    
    # 发送测试告警
    print(f"\n📤 发送 {len(test_alerts)} 条告警...")
    results = notifier.notify(test_alerts)
    
    print(f"\n📊 发送结果:")
    print(f"   总计: {results['total']} 条")
    for ch_name, stats in results['channels'].items():
        print(f"   {ch_name}: 成功 {stats['sent']}, 失败 {stats['failed']}")
    
    if results['failed']:
        print(f"\n⚠️ 失败渠道: {results['failed']}")
    else:
        print("\n✅ 所有渠道发送成功")


if __name__ == "__main__":
    main()