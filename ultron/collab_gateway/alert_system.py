"""
告警通知系统 - 多智能体协作网络的告警通知渠道
"""
import json
import time
import asyncio
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from threading import Thread
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertSource(Enum):
    AGENT_STATUS = "agent_status"
    TASK_STATUS = "task_status"
    SYSTEM_HEALTH = "system_health"
    METRICS = "metrics"
    CUSTOM = "custom"


class NotificationChannel(Enum):
    DINGTALK = "dingtalk"
    EMAIL = "email"
    WEBHOOK = "webhook"
    CONSOLE = "console"
    SMS = "sms"


@dataclass
class AlertRule:
    """告警规则"""
    name: str
    source: AlertSource
    condition: str  # gt, lt, eq, ne, contains
    threshold: any
    level: AlertLevel
    enabled: bool = True
    cooldown_seconds: int = 300  # 冷却时间，避免重复告警
    last_triggered: Optional[datetime] = None


@dataclass
class Alert:
    """告警实例"""
    id: str
    source: AlertSource
    level: AlertLevel
    title: str
    message: str
    data: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    resolved: bool = False
    resolved_at: Optional[datetime] = None


class NotificationChannelBase:
    """通知渠道基类"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.enabled = config.get("enabled", True)
    
    async def send(self, alert: Alert) -> bool:
        """发送通知"""
        raise NotImplementedError
    
    def format_message(self, alert: Alert) -> str:
        """格式化消息"""
        level_emoji = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.ERROR: "❌",
            AlertLevel.CRITICAL: "🔥"
        }
        emoji = level_emoji.get(alert.level, "📢")
        return f"""{emoji} **{alert.level.value.upper()}** - {alert.title}

{alert.message}

> 来源: {alert.source.value}
> 时间: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
"""


class DingTalkChannel(NotificationChannelBase):
    """钉钉通知渠道"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.webhook = config.get("webhook", "")
        self.secret = config.get("secret", "")
    
    async def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.webhook:
            logger.info(f"钉钉通知已禁用或未配置: {alert.title}")
            return False
        
        import urllib.request
        import hmac
        import hashlib
        import base64
        import json
        
        timestamp = str(round(time.time() * 1000))
        secret_enc = self.secret.encode('utf-8')
        string_to_sign = '{}\n{}'.format(timestamp, self.secret)
        string_to_sign_enc = string_to_sign.encode('utf-8')
        hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
        sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))
        
        url = f"{self.webhook}&timestamp={timestamp}&sign={sign}"
        
        msg = self.format_message(alert)
        data = {
            "msgtype": "markdown",
            "markdown": {
                "title": f"{alert.level.value.upper()}: {alert.title}",
                "text": msg
            }
        }
        
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(data).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                result = json.loads(response.read().decode('utf-8'))
                logger.info(f"钉钉通知发送成功: {alert.title}, result: {result.get('errcode')}")
                return result.get('errcode') == 0
        except Exception as e:
            logger.error(f"钉钉通知发送失败: {e}")
            return False


class EmailChannel(NotificationChannelBase):
    """邮件通知渠道"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.smtp_host = config.get("smtp_host", "")
        self.smtp_port = config.get("smtp_port", 587)
        self.smtp_user = config.get("smtp_user", "")
        self.smtp_password = config.get("smtp_password", "")
        self.from_addr = config.get("from_addr", "")
        self.to_addrs = config.get("to_addrs", [])
    
    async def send(self, alert: Alert) -> bool:
        if not self.enabled:
            return False
        
        # 简化实现，实际需要smtplib
        logger.info(f"[Email] 告警: {alert.title} -> {self.to_addrs}")
        return True


class WebhookChannel(NotificationChannelBase):
    """WebHook通知渠道"""
    
    def __init__(self, config: Dict):
        super().__init__(config)
        self.url = config.get("url", "")
        self.headers = config.get("headers", {})
    
    async def send(self, alert: Alert) -> bool:
        if not self.enabled or not self.url:
            return False
        
        import urllib.request
        import json
        
        data = {
            "alert_id": alert.id,
            "source": alert.source.value,
            "level": alert.level.value,
            "title": alert.title,
            "message": alert.message,
            "data": alert.data,
            "timestamp": alert.timestamp.isoformat()
        }
        
        try:
            req = urllib.request.Request(
                self.url,
                data=json.dumps(data).encode('utf-8'),
                headers={**self.headers, 'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"Webhook通知发送成功: {alert.title}")
                return True
        except Exception as e:
            logger.error(f"Webhook通知发送失败: {e}")
            return False


class ConsoleChannel(NotificationChannelBase):
    """控制台通知渠道"""
    
    async def send(self, alert: Alert) -> bool:
        msg = self.format_message(alert)
        if alert.level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            print(f"\n{'='*50}")
            print(msg)
            print(f"{'='*50}\n")
        else:
            print(msg)
        return True


class AlertManager:
    """告警管理器"""
    
    def __init__(self):
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: List[Alert] = []
        self.channels: Dict[NotificationChannel, NotificationChannelBase] = {}
        self.handlers: List[Callable] = []  # 告警处理器
        self._alert_id_counter = 0
        
        # 默认告警规则
        self._init_default_rules()
    
    def _init_default_rules(self):
        """初始化默认告警规则"""
        default_rules = [
            AlertRule(
                name="agent_offline",
                source=AlertSource.AGENT_STATUS,
                condition="eq",
                threshold="offline",
                level=AlertLevel.ERROR,
                cooldown_seconds=300
            ),
            AlertRule(
                name="task_failed",
                source=AlertSource.TASK_STATUS,
                condition="eq",
                threshold="failed",
                level=AlertLevel.WARNING,
                cooldown_seconds=600
            ),
            AlertRule(
                name="high_failure_rate",
                source=AlertSource.METRICS,
                condition="gt",
                threshold=0.5,
                level=AlertLevel.CRITICAL,
                cooldown_seconds=300
            ),
            AlertRule(
                name="agent_unresponsive",
                source=AlertSource.AGENT_STATUS,
                condition="contains",
                threshold="unresponsive",
                level=AlertLevel.WARNING,
                cooldown_seconds=180
            ),
        ]
        
        for rule in default_rules:
            self.rules[rule.name] = rule
    
    def register_channel(self, channel_type: NotificationChannel, config: Dict):
        """注册通知渠道"""
        channel_map = {
            NotificationChannel.DINGTALK: DingTalkChannel,
            NotificationChannel.EMAIL: EmailChannel,
            NotificationChannel.WEBHOOK: WebhookChannel,
            NotificationChannel.CONSOLE: ConsoleChannel,
        }
        
        channel_class = channel_map.get(channel_type)
        if channel_class:
            self.channels[channel_type] = channel_class(config)
            logger.info(f"已注册通知渠道: {channel_type.value}")
    
    def add_rule(self, rule: AlertRule):
        """添加告警规则"""
        self.rules[rule.name] = rule
        logger.info(f"已添加告警规则: {rule.name}")
    
    def enable_rule(self, name: str):
        """启用告警规则"""
        if name in self.rules:
            self.rules[name].enabled = True
    
    def disable_rule(self, name: str):
        """禁用告警规则"""
        if name in self.rules:
            self.rules[name].enabled = False
    
    def _check_rule(self, rule: AlertRule, data: Dict) -> bool:
        """检查规则是否触发"""
        value = data.get(rule.source.value, data.get("status"))
        
        if rule.condition == "eq":
            return value == rule.threshold
        elif rule.condition == "ne":
            return value != rule.threshold
        elif rule.condition == "gt":
            try:
                return float(value) > float(rule.threshold)
            except:
                return False
        elif rule.condition == "lt":
            try:
                return float(value) < float(rule.threshold)
            except:
                return False
        elif rule.condition == "contains":
            return str(rule.threshold) in str(value)
        return False
    
    def _should_alert(self, rule: AlertRule) -> bool:
        """检查是否应该告警（冷却时间内不重复告警）"""
        if not rule.enabled:
            return False
        
        if rule.last_triggered is None:
            return True
        
        elapsed = (datetime.now() - rule.last_triggered).total_seconds()
        return elapsed >= rule.cooldown_seconds
    
    async def trigger_alert(
        self,
        source: AlertSource,
        level: AlertLevel,
        title: str,
        message: str,
        data: Dict = None
    ):
        """触发告警"""
        self._alert_id_counter += 1
        alert = Alert(
            id=f"alert_{self._alert_id_counter}_{int(time.time())}",
            source=source,
            level=level,
            title=title,
            message=message,
            data=data or {}
        )
        
        # 检查规则
        triggered_rules = []
        for rule_name, rule in self.rules.items():
            if rule.source == source and self._should_alert(rule):
                if self._check_rule(rule, data or {}):
                    triggered_rules.append(rule_name)
                    rule.last_triggered = datetime.now()
        
        # 如果没有匹配规则但级别较高，也发送告警
        if not triggered_rules and level in [AlertLevel.ERROR, AlertLevel.CRITICAL]:
            triggered_rules = ["custom"]
        
        # 发送通知
        for channel_type, channel in self.channels.items():
            try:
                await channel.send(alert)
            except Exception as e:
                logger.error(f"渠道 {channel_type.value} 发送失败: {e}")
        
        # 调用处理器
        for handler in self.handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"告警处理器失败: {e}")
        
        self.alerts.append(alert)
        logger.info(f"告警已触发: {alert.id} - {title}")
        
        return alert
    
    def get_alerts(self, 
                   level: AlertLevel = None, 
                   source: AlertSource = None,
                   unresolved_only: bool = False,
                   limit: int = 100) -> List[Alert]:
        """获取告警列表"""
        alerts = self.alerts
        
        if level:
            alerts = [a for a in alerts if a.level == level]
        if source:
            alerts = [a for a in alerts if a.source == source]
        if unresolved_only:
            alerts = [a for a in alerts if not a.resolved]
        
        return alerts[-limit:]
    
    def resolve_alert(self, alert_id: str) -> bool:
        """解决告警"""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                alert.resolved_at = datetime.now()
                logger.info(f"告警已解决: {alert_id}")
                return True
        return False
    
    def get_stats(self) -> Dict:
        """获取告警统计"""
        total = len(self.alerts)
        resolved = len([a for a in self.alerts if a.resolved])
        by_level = {}
        by_source = {}
        
        for alert in self.alerts:
            level_key = alert.level.value
            source_key = alert.source.value
            by_level[level_key] = by_level.get(level_key, 0) + 1
            by_source[source_key] = by_source.get(source_key, 0) + 1
        
        return {
            "total": total,
            "active": total - resolved,
            "resolved": resolved,
            "by_level": by_level,
            "by_source": by_source,
            "rules_count": len(self.rules),
            "enabled_rules": len([r for r in self.rules.values() if r.enabled]),
            "channels": list(self.channels.keys())
        }


# 全局告警管理器
_alert_manager = None

def get_alert_manager() -> AlertManager:
    """获取告警管理器单例"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# 便捷函数
async def alert(source: AlertSource, level: AlertLevel, title: str, message: str, data: Dict = None):
    """触发告警的便捷函数"""
    manager = get_alert_manager()
    return await manager.trigger_alert(source, level, title, message, data)


# 集成到协作网关的钩子
def setup_gateway_alerts(gateway, config: Dict = None):
    """为协作网关设置告警"""
    manager = get_alert_manager()
    
    # 配置通知渠道
    if config:
        if config.get("dingtalk"):
            manager.register_channel(NotificationChannel.DINGTALK, config["dingtalk"])
        if config.get("webhook"):
            manager.register_channel(NotificationChannel.WEBHOOK, config["webhook"])
        if config.get("console", True):
            manager.register_channel(NotificationChannel.CONSOLE, {"enabled": True})
    
    # 钩子：Agent状态变化时检查告警
    original_update_status = gateway.update_agent_status
    
    def hooked_update_status(agent_id: str, status: str) -> Dict:
        result = original_update_status(agent_id, status)
        
        # 检查是否需要告警
        if status in ["offline", "unresponsive", "error"]:
            asyncio.create_task(alert(
                source=AlertSource.AGENT_STATUS,
                level=AlertLevel.ERROR if status == "offline" else AlertLevel.WARNING,
                title=f"Agent状态异常: {agent_id}",
                message=f"Agent {agent_id} 状态变为 {status}",
                data={"agent_id": agent_id, "status": status}
            ))
        
        return result
    
    gateway.update_agent_status = hooked_update_status
    
    # 钩子：任务状态变化时检查告警
    original_update_task = gateway.update_task_status
    
    def hooked_update_task(task_id: str, status: str, result: Dict = None) -> Dict:
        result = original_update_task(task_id, status, result)
        
        if status == "failed":
            asyncio.create_task(alert(
                source=AlertSource.TASK_STATUS,
                level=AlertLevel.WARNING,
                title=f"任务失败: {task_id}",
                message=f"任务 {task_id} 执行失败",
                data={"task_id": task_id, "result": result}
            ))
        
        return result
    
    gateway.update_task_status = hooked_update_task
    
    logger.info("协作网关告警系统已集成")
    return manager