#!/usr/bin/env python3
"""
告警通知渠道集成模块
支持多种通知渠道：钉钉、邮件、Webhook、Telegram、飞书
"""

import json
import logging
import requests
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, asdict
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)


class ChannelType(Enum):
    DINGTALK = "dingtalk"
    EMAIL = "email"
    WEBHOOK = "webhook"
    TELEGRAM = "telegram"
    FEISHU = "feishu"


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class NotificationChannel:
    """通知渠道配置"""
    id: str
    name: str
    channel_type: str
    enabled: bool = True
    config: Dict[str, Any] = None
    # 告警级别过滤
    min_level: str = "info"  # 只发送 >= min_level 的告警
    # 告警服务过滤
    services: List[str] = None  # 空表示所有服务
    
    def __post_init__(self):
        if self.config is None:
            self.config = {}
        if self.services is None:
            self.services = []


@dataclass
class AlertNotification:
    """告警通知"""
    alert_id: str
    rule_id: str
    rule_name: str
    service_name: str
    level: str
    message: str
    value: float
    threshold: float
    status: str
    created_at: str
    channel: str


class DingTalkNotifier:
    """钉钉通知器"""
    
    def __init__(self, webhook_url: str, secret: str = None):
        self.webhook_url = webhook_url
        self.secret = secret
    
    def send(self, notification: AlertNotification) -> bool:
        """发送钉钉通知"""
        try:
            # 根据告警级别选择颜色
            level_colors = {
                "info": "grey",
                "warning": "orange", 
                "error": "red",
                "critical": "red"
            }
            color = level_colors.get(notification.level, "grey")
            
            # 构建消息
            msg = {
                "msgtype": "markdown",
                "markdown": {
                    "title": f"🚨 {notification.rule_name}",
                    "text": f"""## 🚨 告警通知

**级别**: {notification.level.upper()}
**服务**: {notification.service_name}
**规则**: {notification.rule_name}
**消息**: {notification.message}
**当前值**: {notification.value}
**阈值**: {notification.threshold}
**状态**: {notification.status}
**时间**: {notification.created_at}

> 告警ID: {notification.alert_id}
"""
                }
            }
            
            # 添加AT功能（严重告警时）
            if notification.level in ["error", "critical"]:
                msg["at"] = {"isAtAll": True}
            
            response = requests.post(self.webhook_url, json=msg, timeout=10)
            result = response.json()
            
            if result.get("errcode") == 0:
                logger.info(f"钉钉通知发送成功: {notification.alert_id}")
                return True
            else:
                logger.error(f"钉钉通知失败: {result}")
                return False
        except Exception as e:
            logger.error(f"钉钉通知异常: {e}")
            return False


class EmailNotifier:
    """邮件通知器"""
    
    def __init__(self, smtp_host: str, smtp_port: int, username: str, password: str,
                 from_addr: str, to_addrs: List[str], use_tls: bool = True):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password
        self.from_addr = from_addr
        self.to_addrs = to_addrs
        self.use_tls = use_tls
    
    def send(self, notification: AlertNotification) -> bool:
        """发送邮件通知"""
        try:
            subject = f"[{notification.level.upper()}] {notification.rule_name} - {notification.service_name}"
            
            body = f"""
告警通知

级别: {notification.level.upper()}
服务: {notification.service_name}
规则: {notification.rule_name}
消息: {notification.message}
当前值: {notification.value}
阈值: {notification.threshold}
状态: {notification.status}
时间: {notification.created_at}

告警ID: {notification.alert_id}
规则ID: {notification.rule_id}
"""
            
            msg = MIMEMultipart()
            msg["From"] = self.from_addr
            msg["To"] = ", ".join(self.to_addrs)
            msg["Subject"] = subject
            msg.attach(MIMEText(body, "plain", "utf-8"))
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                if self.use_tls:
                    server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, self.to_addrs, msg.as_string())
            
            logger.info(f"邮件通知发送成功: {notification.alert_id}")
            return True
        except Exception as e:
            logger.error(f"邮件通知异常: {e}")
            return False


class WebhookNotifier:
    """Webhook通知器"""
    
    def __init__(self, url: str, method: str = "POST", headers: Dict = None):
        self.url = url
        self.method = method.upper()
        self.headers = headers or {"Content-Type": "application/json"}
    
    def send(self, notification: AlertNotification) -> bool:
        """发送Webhook通知"""
        try:
            payload = {
                "alert_id": notification.alert_id,
                "rule_id": notification.rule_id,
                "rule_name": notification.rule_name,
                "service_name": notification.service_name,
                "level": notification.level,
                "message": notification.message,
                "value": notification.value,
                "threshold": notification.threshold,
                "status": notification.status,
                "created_at": notification.created_at,
                "timestamp": datetime.now().isoformat()
            }
            
            if self.method == "POST":
                response = requests.post(self.url, json=payload, headers=self.headers, timeout=10)
            else:
                response = requests.get(self.url, params=payload, headers=self.headers, timeout=10)
            
            if response.status_code < 400:
                logger.info(f"Webhook通知发送成功: {notification.alert_id}")
                return True
            else:
                logger.error(f"Webhook通知失败: {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"Webhook通知异常: {e}")
            return False


class TelegramNotifier:
    """Telegram通知器"""
    
    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}"
    
    def send(self, notification: AlertNotification) -> bool:
        """发送Telegram通知"""
        try:
            emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "critical": "🔴"}
            icon = emoji.get(notification.level, "ℹ️")
            
            text = f"""{icon} *告警通知*

*{notification.rule_name}*

级别: {notification.level.upper()}
服务: {notification.service_name}
消息: {notification.message}
当前值: {notification.value}
阈值: {notification.threshold}
状态: {notification.status}
时间: {notification.created_at}
"""
            
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "Markdown"
            }
            
            response = requests.post(f"{self.api_url}/sendMessage", json=payload, timeout=10)
            result = response.json()
            
            if result.get("ok"):
                logger.info(f"Telegram通知发送成功: {notification.alert_id}")
                return True
            else:
                logger.error(f"Telegram通知失败: {result}")
                return False
        except Exception as e:
            logger.error(f"Telegram通知异常: {e}")
            return False


class FeishuNotifier:
    """飞书通知器"""
    
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
    
    def send(self, notification: AlertNotification) -> bool:
        """发送飞书通知"""
        try:
            level_colors = {
                "info": "grey",
                "warning": "orange",
                "error": "red", 
                "critical": "red"
            }
            
            msg = {
                "msg_type": "interactive",
                "card": {
                    "header": {
                        "title": {"tag": "plain_text", "content": f"🚨 告警通知 - {notification.rule_name}"},
                        "template": level_colors.get(notification.level, "grey")
                    },
                    "elements": [
                        {
                            "tag": "div",
                            "fields": [
                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**级别**: {notification.level.upper()}"}},
                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**服务**: {notification.service_name}"}}
                            ]
                        },
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": f"**消息**: {notification.message}"}
                        },
                        {
                            "tag": "div",
                            "fields": [
                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**当前值**: {notification.value}"}},
                                {"is_short": True, "text": {"tag": "lark_md", "content": f"**阈值**: {notification.threshold}"}}
                            ]
                        },
                        {
                            "tag": "div",
                            "text": {"tag": "lark_md", "content": f"**状态**: {notification.status} | **时间**: {notification.created_at}"}
                        }
                    ]
                }
            }
            
            response = requests.post(self.webhook_url, json=msg, timeout=10)
            result = response.json()
            
            if result.get("code") == 0:
                logger.info(f"飞书通知发送成功: {notification.alert_id}")
                return True
            else:
                logger.error(f"飞书通知失败: {result}")
                return False
        except Exception as e:
            logger.error(f"飞书通知异常: {e}")
            return False


class AlertNotificationManager:
    """告警通知管理器"""
    
    def __init__(self):
        self.channels: Dict[str, NotificationChannel] = {}
        self.notifiers: Dict[str, Any] = {}
        self.notification_history: List[Dict] = []
        
        # 加载配置
        self._load_config()
    
    def _load_config(self):
        """加载渠道配置"""
        config_path = "/root/.openclaw/workspace/ultron/config/notification_channels.json"
        try:
            import os
            if os.path.exists(config_path):
                with open(config_path, 'r') as f:
                    config = json.load(f)
                    for ch in config.get("channels", []):
                        self.add_channel(NotificationChannel(**ch))
                logger.info(f"加载了 {len(self.channels)} 个通知渠道")
        except Exception as e:
            logger.warning(f"加载通知渠道配置失败: {e}")
    
    def _save_config(self):
        """保存渠道配置"""
        config_path = "/root/.openclaw/workspace/ultron/config/notification_channels.json"
        try:
            import os
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            config = {
                "channels": [asdict(ch) for ch in self.channels.values()]
            }
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存通知渠道配置失败: {e}")
    
    def add_channel(self, channel: NotificationChannel) -> bool:
        """添加通知渠道"""
        try:
            self.channels[channel.id] = channel
            
            # 创建对应的notifier
            if channel.channel_type == ChannelType.DINGTALK.value:
                self.notifiers[channel.id] = DingTalkNotifier(
                    channel.config.get("webhook_url"),
                    channel.config.get("secret")
                )
            elif channel.channel_type == ChannelType.EMAIL.value:
                self.notifiers[channel.id] = EmailNotifier(
                    channel.config.get("smtp_host"),
                    channel.config.get("smtp_port", 465),
                    channel.config.get("username"),
                    channel.config.get("password"),
                    channel.config.get("from_addr"),
                    channel.config.get("to_addrs", []),
                    channel.config.get("use_tls", True)
                )
            elif channel.channel_type == ChannelType.WEBHOOK.value:
                self.notifiers[channel.id] = WebhookNotifier(
                    channel.config.get("url"),
                    channel.config.get("method", "POST"),
                    channel.config.get("headers")
                )
            elif channel.channel_type == ChannelType.TELEGRAM.value:
                self.notifiers[channel.id] = TelegramNotifier(
                    channel.config.get("bot_token"),
                    channel.config.get("chat_id")
                )
            elif channel.channel_type == ChannelType.FEISHU.value:
                self.notifiers[channel.id] = FeishuNotifier(
                    channel.config.get("webhook_url")
                )
            
            logger.info(f"添加通知渠道: {channel.name} ({channel.channel_type})")
            self._save_config()
            return True
        except Exception as e:
            logger.error(f"添加通知渠道失败: {e}")
            return False
    
    def remove_channel(self, channel_id: str) -> bool:
        """移除通知渠道"""
        if channel_id in self.channels:
            del self.channels[channel_id]
            if channel_id in self.notifiers:
                del self.notifiers[channel_id]
            self._save_config()
            logger.info(f"移除通知渠道: {channel_id}")
            return True
        return False
    
    def send_alert(self, alert: Dict) -> Dict[str, bool]:
        """发送告警通知到所有启用的渠道"""
        results = {}
        
        # 构建通知对象
        notification = AlertNotification(
            alert_id=alert.get("id", ""),
            rule_id=alert.get("rule_id", ""),
            rule_name=alert.get("rule_name", ""),
            service_name=alert.get("service_name", ""),
            level=alert.get("level", "info"),
            message=alert.get("message", ""),
            value=alert.get("value", 0),
            threshold=alert.get("threshold", 0),
            status=alert.get("status", "firing"),
            created_at=alert.get("created_at", datetime.now().isoformat()),
            channel=""
        )
        
        # 级别优先级
        level_priority = {"info": 0, "warning": 1, "error": 2, "critical": 3}
        
        for channel_id, channel in self.channels.items():
            if not channel.enabled:
                continue
            
            # 检查告警级别过滤
            min_level_pri = level_priority.get(channel.min_level, 0)
            alert_level_pri = level_priority.get(notification.level, 0)
            if alert_level_pri < min_level_pri:
                logger.debug(f"告警级别低于渠道最小级别，跳过: {channel_id}")
                continue
            
            # 检查服务过滤
            if channel.services and notification.service_name not in channel.services:
                logger.debug(f"服务不在过滤列表，跳过: {channel_id}")
                continue
            
            # 发送通知
            notification.channel = channel_id
            notifier = self.notifiers.get(channel_id)
            if notifier:
                try:
                    success = notifier.send(notification)
                    results[channel_id] = success
                    
                    # 记录历史
                    self.notification_history.append({
                        "alert_id": notification.alert_id,
                        "channel_id": channel_id,
                        "success": success,
                        "timestamp": datetime.now().isoformat()
                    })
                except Exception as e:
                    logger.error(f"通知发送失败: {channel_id}, {e}")
                    results[channel_id] = False
        
        return results
    
    def get_channels(self) -> List[Dict]:
        """获取所有渠道"""
        return [asdict(ch) for ch in self.channels.values()]
    
    def get_notification_history(self, limit: int = 100) -> List[Dict]:
        """获取通知历史"""
        return self.notification_history[-limit:]


# 全局实例
_notification_manager = None

def get_notification_manager() -> AlertNotificationManager:
    """获取全局通知管理器"""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = AlertNotificationManager()
    return _notification_manager


def create_demo_channels():
    """创建演示渠道配置"""
    manager = get_notification_manager()
    
    # 钉钉渠道（如果配置了webhook）
    import os
    dingtalk_webhook = os.environ.get("DINGTALK_WEBHOOK")
    if dingtalk_webhook:
        manager.add_channel(NotificationChannel(
            id="dingtalk-main",
            name="主钉钉群",
            channel_type="dingtalk",
            enabled=True,
            config={"webhook_url": dingtalk_webhook},
            min_level="warning",
            services=[]
        ))
    
    # Webhook渠道
    webhook_url = os.environ.get("ALERT_WEBHOOK_URL")
    if webhook_url:
        manager.add_channel(NotificationChannel(
            id="webhook-main",
            name="主Webhook",
            channel_type="webhook",
            enabled=True,
            config={"url": webhook_url, "method": "POST"},
            min_level="info",
            services=[]
        ))


if __name__ == "__main__":
    # 测试
    manager = get_notification_manager()
    
    # 添加测试渠道
    manager.add_channel(NotificationChannel(
        id="test-dingtalk",
        name="测试钉钉",
        channel_type="dingtalk",
        enabled=False,  # 默认禁用
        config={"webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=xxx"},
        min_level="warning",
        services=["gateway", "browser"]
    ))
    
    # 测试发送
    test_alert = {
        "id": "test-001",
        "rule_id": "rule-001",
        "rule_name": "CPU使用率过高",
        "service_name": "gateway",
        "level": "warning",
        "message": "CPU使用率达到85%",
        "value": 85.0,
        "threshold": 80.0,
        "status": "firing",
        "created_at": datetime.now().isoformat()
    }
    
    print("可用渠道:", manager.get_channels())
    print("\n测试告警通知发送...")
    results = manager.send_alert(test_alert)
    print("发送结果:", results)