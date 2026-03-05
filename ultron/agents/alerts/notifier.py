#!/usr/bin/env python3
"""
Agent告警通知器 - 多渠道通知
"""

import json
import os
import time
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Any, Optional
from enum import Enum


logger = logging.getLogger(__name__)


class NotificationResult:
    """通知结果"""
    def __init__(self, success: bool, channel: str, message: str = "", error: str = ""):
        self.success = success
        self.channel = channel
        self.message = message
        self.error = error
        self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "channel": self.channel,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp
        }


class NotificationChannel(ABC):
    """通知渠道基类"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
    
    @abstractmethod
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        """发送通知"""
        pass
    
    @abstractmethod
    def get_name(self) -> str:
        """渠道名称"""
        pass
    
    def should_send(self, alert: Dict[str, Any]) -> bool:
        """检查是否应该发送"""
        if not self.enabled:
            return False
        
        # 按级别过滤
        level = alert.get("level", "INFO")
        min_level = self.config.get("min_level", "INFO")
        
        level_order = {"INFO": 0, "WARNING": 1, "CRITICAL": 2}
        if level_order.get(level, 0) < level_order.get(min_level, 0):
            return False
        
        return True


class ConsoleChannel(NotificationChannel):
    """控制台输出渠道"""
    
    def get_name(self) -> str:
        return "console"
    
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        try:
            level = alert.get('level', 'INFO')
            state = alert.get('state', 'firing')
            
            level_emoji = {
                "CRITICAL": "🔴",
                "WARNING": "🟡",
                "INFO": "🔵"
            }.get(level, "⚪")
            
            state_prefix = "🚨" if state == "firing" else "✅"
            
            message = f"""
{'='*60}
{state_prefix} [{level}] {alert.get('message', '告警')}
   规则: {alert.get('rule_name', alert.get('rule_id', 'N/A'))}
   指标: {alert.get('metric', 'N/A')} = {alert.get('value', 'N/A')}
   阈值: {alert.get('condition', 'N/A')} {alert.get('threshold', 'N/A')}
   时间: {alert.get('timestamp', 'N/A')}
{'='*60}
"""
            
            print(message)
            return NotificationResult(True, self.get_name(), "已发送")
        except Exception as e:
            return NotificationResult(False, self.get_name(), "", str(e))


class FileChannel(NotificationChannel):
    """文件存储渠道"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.file_path = self.config.get("path", "/root/.openclaw/workspace/ultron/agents/alerts/data/alerts.json")
        self._ensure_file()
    
    def _ensure_file(self):
        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"alerts": [], "version": "1.0"}, f)
    
    def get_name(self) -> str:
        return "file"
    
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        try:
            with open(self.file_path, 'r') as f:
                data = json.load(f)
            
            alert['_id'] = f"alert_{int(time.time() * 1000)}"
            alert['_created_at'] = time.time()
            
            data.setdefault("alerts", []).append(alert)
            
            # 只保留最近1000条
            data["alerts"] = data["alerts"][-1000:]
            
            with open(self.file_path, 'w') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            return NotificationResult(True, self.get_name(), "已保存")
        except Exception as e:
            return NotificationResult(False, self.get_name(), "", str(e))


class DingTalkChannel(NotificationChannel):
    """钉钉通知渠道"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.webhook = self.config.get("webhook", "")
        self.secret = self.config.get("secret", "")
    
    def get_name(self) -> str:
        return "dingtalk"
    
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        if not self.webhook:
            return NotificationResult(False, self.get_name(), "", "未配置webhook")
        
        try:
            level = alert.get('level', 'INFO')
            state = alert.get('state', 'firing')
            
            # 构建消息
            if level == "CRITICAL":
                title = "🔴 严重告警"
                color = "FF0000"
            elif level == "WARNING":
                title = "🟡 警告告警"
                color = "FFA500"
            else:
                title = "🔵 信息通知"
                color = "1890FF"
            
            if state == "resolved":
                title = "✅ 告警恢复"
            
            message = {
                "msgtype": "markdown",
                "markdown": {
                    "title": title,
                    "text": f"""## {title}

**{alert.get('message', '告警通知')}**

- **规则**: {alert.get('rule_name', 'N/A')}
- **指标**: {alert.get('metric', 'N/A')} = {alert.get('value', 'N/A')}
- **阈值**: {alert.get('condition', 'N/A')} {alert.get('threshold', 'N/A')}
- **时间**: {alert.get('timestamp', 'N/A')}

> 来自 Agent 监控系统
"""
                }
            }
            
            import requests
            response = requests.post(
                self.webhook,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.json().get("errcode") == 0:
                return NotificationResult(True, self.get_name(), "已发送")
            else:
                return NotificationResult(False, self.get_name(), "", response.text)
                
        except Exception as e:
            return NotificationResult(False, self.get_name(), "", str(e))


class SlackChannel(NotificationChannel):
    """Slack通知渠道"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.webhook = self.config.get("webhook", "")
    
    def get_name(self) -> str:
        return "slack"
    
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        if not self.webhook:
            return NotificationResult(False, self.get_name(), "", "未配置webhook")
        
        try:
            level = alert.get('level', 'INFO')
            
            color = {
                "CRITICAL": "danger",
                "WARNING": "warning",
                "INFO": "info"
            }.get(level, "#cccccc")
            
            message = {
                "attachments": [{
                    "color": color,
                    "title": f"[{level}] {alert.get('message', '告警')}",
                    "fields": [
                        {"title": "规则", "value": alert.get('rule_name', 'N/A'), "short": True},
                        {"title": "指标", "value": f"{alert.get('metric', 'N/A')} = {alert.get('value', 'N/A')}", "short": True},
                        {"title": "阈值", "value": f"{alert.get('condition', 'N/A')} {alert.get('threshold', 'N/A')}", "short": True},
                        {"title": "时间", "value": alert.get('timestamp', 'N/A'), "short": True}
                    ],
                    "footer": "Agent Alert System",
                    "ts": int(time.time())
                }]
            }
            
            import requests
            response = requests.post(
                self.webhook,
                json=message,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            if response.status_code == 200:
                return NotificationResult(True, self.get_name(), "已发送")
            else:
                return NotificationResult(False, self.get_name(), "", response.text)
                
        except Exception as e:
            return NotificationResult(False, self.get_name(), "", str(e))


class EmailChannel(NotificationChannel):
    """邮件通知渠道"""
    
    def __init__(self, config: Dict[str, Any] = None):
        super().__init__(config)
        self.smtp_host = self.config.get("smtp_host", "")
        self.smtp_port = self.config.get("smtp_port", 587)
        self.smtp_user = self.config.get("smtp_user", "")
        self.smtp_password = self.config.get("smtp_password", "")
        self.from_addr = self.config.get("from", self.smtp_user)
        self.to_addrs = self.config.get("to", [])
    
    def get_name(self) -> str:
        return "email"
    
    def send(self, alert: Dict[str, Any]) -> NotificationResult:
        if not self.smtp_host or not self.to_addrs:
            return NotificationResult(False, self.get_name(), "", "未配置邮件")
        
        try:
            import smtplib
            from email.mime.text import MIMEText
            from email.mime.multipart import MIMEMultipart
            
            level = alert.get('level', 'INFO')
            subject_prefix = {"CRITICAL": "🔴", "WARNING": "🟡", "INFO": "🔵"}.get(level, "")
            
            msg = MIMEMultipart()
            msg['From'] = self.from_addr
            msg['To'] = ', '.join(self.to_addrs)
            msg['Subject'] = f"{subject_prefix} Agent告警: {alert.get('message', '告警通知')}"
            
            body = f"""
<html>
<body>
<h2>Agent 告警通知</h2>
<p><strong>级别:</strong> {alert.get('level', 'N/A')}</p>
<p><strong>消息:</strong> {alert.get('message', 'N/A')}</p>
<p><strong>规则:</strong> {alert.get('rule_name', 'N/A')}</p>
<p><strong>指标:</strong> {alert.get('metric', 'N/A')} = {alert.get('value', 'N/A')}</p>
<p><strong>阈值:</strong> {alert.get('condition', 'N/A')} {alert.get('threshold', 'N/A')}</p>
<p><strong>时间:</strong> {alert.get('timestamp', 'N/A')}</p>
</body>
</html>
"""
            
            msg.attach(MIMEText(body, 'html'))
            
            import smtplib
            server = smtplib.SMTP(self.smtp_host, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return NotificationResult(True, self.get_name(), "已发送")
                
        except Exception as e:
            return NotificationResult(False, self.get_name(), "", str(e))


class AlertNotifier:
    """告警通知管理器"""
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.channels: Dict[str, NotificationChannel] = {}
        self.notification_history: List[Dict] = []
        self._init_channels()
    
    def _init_channels(self):
        """初始化渠道"""
        channel_configs = self.config.get("channels", {})
        
        # 控制台
        if channel_configs.get("console", {}).get("enabled", True):
            self.channels["console"] = ConsoleChannel(channel_configs.get("console"))
        
        # 文件
        if channel_configs.get("file", {}).get("enabled", True):
            self.channels["file"] = FileChannel(channel_configs.get("file"))
        
        # 钉钉
        if channel_configs.get("dingtalk", {}).get("enabled"):
            self.channels["dingtalk"] = DingTalkChannel(channel_configs.get("dingtalk"))
        
        # Slack
        if channel_configs.get("slack", {}).get("enabled"):
            self.channels["slack"] = SlackChannel(channel_configs.get("slack"))
        
        # 邮件
        if channel_configs.get("email", {}).get("enabled"):
            self.channels["email"] = EmailChannel(channel_configs.get("email"))
    
    def add_channel(self, name: str, channel: NotificationChannel):
        """添加渠道"""
        self.channels[name] = channel
    
    def remove_channel(self, name: str) -> bool:
        """移除渠道"""
        if name in self.channels:
            del self.channels[name]
            return True
        return False
    
    def send(self, alert: Dict[str, Any]) -> List[NotificationResult]:
        """发送告警到所有启用的渠道"""
        results = []
        
        for name, channel in self.channels.items():
            if channel.should_send(alert):
                result = channel.send(alert)
                results.append(result)
                self.notification_history.append(result.to_dict())
        
        # 只保留最近500条记录
        self.notification_history = self.notification_history[-500:]
        
        return results
    
    def send_to(self, alert: Dict[str, Any], channels: List[str]) -> List[NotificationResult]:
        """发送到指定渠道"""
        results = []
        
        for name in channels:
            if name in self.channels and self.channels[name].should_send(alert):
                result = self.channels[name].send(alert)
                results.append(result)
        
        return results
    
    def get_notification_stats(self) -> Dict[str, Any]:
        """获取通知统计"""
        total = len(self.notification_history)
        success = len([n for n in self.notification_history if n.get("success")])
        
        by_channel = {}
        for n in self.notification_history:
            ch = n.get("channel", "unknown")
            by_channel[ch] = by_channel.get(ch, 0) + 1
        
        return {
            "total": total,
            "success": success,
            "failed": total - success,
            "success_rate": success / total if total > 0 else 0,
            "by_channel": by_channel,
            "channels": list(self.channels.keys())
        }


def create_notifier_from_config(config_path: str = None) -> AlertNotifier:
    """从配置文件创建通知器"""
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            config = json.load(f)
        return AlertNotifier(config)
    return AlertNotifier()


# 导出
__all__ = ['AlertNotifier', 'NotificationChannel', 'NotificationResult', 
           'ConsoleChannel', 'FileChannel', 'DingTalkChannel', 'SlackChannel', 'EmailChannel']