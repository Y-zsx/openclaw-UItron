#!/usr/bin/env python3
"""
智能运维助手 - 告警通知渠道
第30世: 实现告警通知渠道集成 (扩展多渠道)
"""

import json
import os
import time
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
            # 静默跳过未配置的渠道
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
                    return True
            
            return False
            
        except Exception as e:
            print(f"❌ 钉钉渠道异常: {e}")
            return False


class LarkChannel(AlertChannel):
    """飞书 webhook 渠道"""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or os.environ.get("LARK_WEBHOOK", "")
    
    def get_name(self) -> str:
        return "lark"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            return False
        
        try:
            level = alert.get('level', 'INFO')
            level_emoji = {
                "CRITICAL": "🔴",
                "WARNING": "🟡",
                "INFO": "🔵"
            }.get(level, "⚪")
            
            message = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {
                            "tag": "plain_text",
                            "content": f"服务器告警 - {level}"
                        },
                        "template": "red" if level == "CRITICAL" else "orange"
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"### {level_emoji} {alert.get('message', '告警通知')}"
                            }
                        },
                        {
                            "tag": "div",
                            "fields": [
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**规则**\n{alert.get('rule', 'N/A')}"
                                    }
                                },
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**指标**\n{alert.get('metric', 'N/A')}"
                                    }
                                },
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**当前值**\n{alert.get('value', 'N/A')}"
                                    }
                                },
                                {
                                    "is_short": True,
                                    "text": {
                                        "tag": "lark_md",
                                        "content": f"**阈值**\n{alert.get('threshold', 'N/A')}"
                                    }
                                }
                            ]
                        },
                        {
                            "tag": "div",
                            "text": {
                                "tag": "lark_md",
                                "content": f"**时间**: {alert.get('timestamp', 'N/A')}\n\n> 来自奥创智能运维系统"
                            }
                        }
                    ]
                }
            }
            
            response = requests.post(
                self.webhook_url,
                json=message,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            return response.status_code == 200
            
        except Exception as e:
            print(f"❌ 飞书渠道异常: {e}")
            return False


class TelegramChannel(AlertChannel):
    """Telegram Bot 渠道"""
    
    def __init__(self, bot_token: str = "", chat_id: str = ""):
        self.bot_token = bot_token or os.environ.get("TELEGRAM_BOT_TOKEN", "")
        self.chat_id = chat_id or os.environ.get("TELEGRAM_CHAT_ID", "")
    
    def get_name(self) -> str:
        return "telegram"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.bot_token or not self.chat_id:
            return False
        
        try:
            level = alert.get('level', 'INFO')
            level_emoji = {
                "CRITICAL": "🔴",
                "WARNING": "🟡",
                "INFO": "🔵"
            }.get(level, "⚪")
            
            text = f"{level_emoji} *{alert.get('message', '告警通知')}*\n\n" \
                   f"📋 *规则*: {alert.get('rule', 'N/A')}\n" \
                   f"📊 *指标*: {alert.get('metric', 'N/A')} = `{alert.get('value', 'N/A')}`\n" \
                   f"⚡ *阈值*: {alert.get('condition', '')} {alert.get('threshold', '')}\n" \
                   f"🕐 *时间*: {alert.get('timestamp', 'N/A')}\n\n" \
                   f"_来自奥创智能运维系统_"
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            data = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200 and response.json().get("ok", False)
            
        except Exception as e:
            print(f"❌ Telegram渠道异常: {e}")
            return False


class DiscordChannel(AlertChannel):
    """Discord Webhook 渠道"""
    
    def __init__(self, webhook_url: str = ""):
        self.webhook_url = webhook_url or os.environ.get("DISCORD_WEBHOOK", "")
    
    def get_name(self) -> str:
        return "discord"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            return False
        
        try:
            level = alert.get('level', 'INFO')
            color = {
                "CRITICAL": 16711680,  # Red
                "WARNING": 16776960,   # Yellow
                "INFO": 3447003        # Blue
            }.get(level, 8421504)
            
            embed = {
                "title": f"⚠️ {alert.get('message', '告警通知')}",
                "color": color,
                "fields": [
                    {"name": "规则", "value": alert.get('rule', 'N/A'), "inline": True},
                    {"name": "指标", "value": alert.get('metric', 'N/A'), "inline": True},
                    {"name": "当前值", "value": str(alert.get('value', 'N/A')), "inline": True},
                    {"name": "阈值", "value": f"{alert.get('condition', '')} {alert.get('threshold', '')}", "inline": True},
                    {"name": "级别", "value": level, "inline": True},
                    {"name": "时间", "value": alert.get('timestamp', 'N/A'), "inline": True}
                ],
                "footer": {"text": "奥创智能运维系统"}
            }
            
            data = {"embeds": [embed]}
            response = requests.post(
                self.webhook_url,
                json=data,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            return response.status_code == 204
            
        except Exception as e:
            print(f"❌ Discord渠道异常: {e}")
            return False


class EmailChannel(AlertChannel):
    """邮件渠道"""
    
    def __init__(self, smtp_host: str = "", smtp_port: int = 587,
                 username: str = "", password: str = "",
                 from_addr: str = "", to_addrs: List[str] = None):
        self.smtp_host = smtp_host or os.environ.get("SMTP_HOST", "")
        self.smtp_port = smtp_port or int(os.environ.get("SMTP_PORT", "587"))
        self.username = username or os.environ.get("SMTP_USERNAME", "")
        self.password = password or os.environ.get("SMTP_PASSWORD", "")
        self.from_addr = from_addr or os.environ.get("SMTP_FROM", self.username)
        self.to_addrs = to_addrs or os.environ.get("SMTP_TO", "").split(",")
    
    def get_name(self) -> str:
        return "email"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.smtp_host or not self.to_addrs:
            return False
        
        try:
            level = alert.get('level', 'INFO')
            
            subject = f"[{level}] {alert.get('message', '告警通知')} - 奥创运维"
            
            body = f"""
<html>
<body>
<h2>{alert.get('message', '告警通知')}</h2>
<table style="border-collapse: collapse;">
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>规则</b></td><td style="padding: 5px; border: 1px solid #ddd;">{alert.get('rule', 'N/A')}</td></tr>
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>指标</b></td><td style="padding: 5px; border: 1px solid #ddd;">{alert.get('metric', 'N/A')}</td></tr>
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>当前值</b></td><td style="padding: 5px; border: 1px solid #ddd;">{alert.get('value', 'N/A')}</td></tr>
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>阈值</b></td><td style="padding: 5px; border: 1px solid #ddd;">{alert.get('condition', '')} {alert.get('threshold', '')}</td></tr>
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>级别</b></td><td style="padding: 5px; border: 1px solid #ddd;">{level}</td></tr>
<tr><td style="padding: 5px; border: 1px solid #ddd;"><b>时间</b></td><td style="padding: 5px; border: 1px solid #ddd;">{alert.get('timestamp', 'N/A')}</td></tr>
</table>
<p><i>来自奥创智能运维系统</i></p>
</body>
</html>
"""
            
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.from_addr
            msg['To'] = ','.join(self.to_addrs)
            msg.attach(MIMEText(body, 'html', 'utf-8'))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            
            return True
            
        except Exception as e:
            print(f"❌ 邮件渠道异常: {e}")
            return False


class WebhookChannel(AlertChannel):
    """通用 Webhook 渠道"""
    
    def __init__(self, webhook_url: str = "", method: str = "POST"):
        self.webhook_url = webhook_url or os.environ.get("WEBHOOK_URL", "")
        self.method = method.upper()
    
    def get_name(self) -> str:
        return "webhook"
    
    def send(self, alert: Dict[str, Any]) -> bool:
        if not self.webhook_url:
            return False
        
        try:
            response = requests.request(
                self.method,
                self.webhook_url,
                json=alert,
                timeout=10,
                headers={"Content-Type": "application/json"}
            )
            
            return response.status_code < 400
            
        except Exception as e:
            print(f"❌ Webhook渠道异常: {e}")
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
        
        # 飞书 (如果配置了)
        self.channels.append(LarkChannel())
        
        # Telegram (如果配置了)
        self.channels.append(TelegramChannel())
        
        # Discord (如果配置了)
        self.channels.append(DiscordChannel())
        
        # 邮件 (如果配置了)
        self.channels.append(EmailChannel())
        
        # 通用 Webhook (如果配置了)
        self.channels.append(WebhookChannel())
    
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
                except Exception as e:
                    print(f"❌ 渠道 {channel.get_name()} 异常: {e}")
        
        # 统计失败的渠道
        for ch_name, stats in results["channels"].items():
            if stats["failed"] > 0 and stats["sent"] == 0:
                results["failed"].append(ch_name)
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """获取渠道状态"""
        return {
            "total_channels": len(self.channels),
            "channels": [
                {
                    "name": c.get_name(),
                    "type": c.__class__.__name__
                }
                for c in self.channels
            ]
        }


def main():
    """测试告警通知"""
    # 模拟告警数据
    test_alerts = [
        {
            "rule": "CPU使用率过高",
            "metric": "cpu.usage_percent",
            "value": 92.5,
            "threshold": 90,
            "condition": ">=",
            "level": "WARNING",
            "message": "CPU使用率超过90%",
            "timestamp": datetime.now().isoformat()
        },
        {
            "rule": "内存使用率过高",
            "metric": "memory.percent",
            "value": 88.0,
            "threshold": 85,
            "condition": ">=",
            "level": "WARNING",
            "message": "内存使用率超过85%",
            "timestamp": datetime.now().isoformat()
        },
        {
            "rule": "CPU使用率严重",
            "metric": "cpu.usage_percent",
            "value": 97.0,
            "threshold": 95,
            "condition": ">=",
            "level": "CRITICAL",
            "message": "CPU使用率超过95%",
            "timestamp": datetime.now().isoformat()
        }
    ]
    
    notifier = AlertNotifier()
    
    print("=" * 60)
    print("智能运维助手 - 告警通知渠道 (多渠道集成)")
    print("=" * 60)
    
    # 显示渠道状态
    status = notifier.get_status()
    print(f"\n📢 已初始化 {status['total_channels']} 个渠道:")
    for ch in status['channels']:
        print(f"   • {ch['name']} ({ch['type']})")
    
    # 发送测试告警
    print(f"\n📤 发送 {len(test_alerts)} 条告警到所有可用渠道...")
    results = notifier.notify(test_alerts)
    
    print(f"\n📊 发送结果:")
    print(f"   总计: {results['total']} 条告警")
    print(f"\n   渠道详情:")
    for ch_name, stats in results['channels'].items():
        status_icon = "✅" if stats['sent'] > 0 else "⚪"
        print(f"   {status_icon} {ch_name}: 成功 {stats['sent']}, 失败 {stats['failed']}")
    
    if results['failed']:
        print(f"\n⚠️ 未配置/失败渠道: {results['failed']}")
    else:
        print("\n✅ 所有已配置渠道发送成功!")


if __name__ == "__main__":
    main()