#!/usr/bin/env python3
"""
跨平台消息路由优化模块 v2.0
功能：
- 智能路由：根据消息类型、优先级、目标渠道自动分发
- 负载均衡：多渠道时自动选择最优渠道
- 故障转移：主渠道失败时自动切换到备用渠道
- 消息缓冲：高频消息批量发送，减少API调用
"""

import json
import asyncio
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4


class ChannelStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


@dataclass
class ChannelMetrics:
    """渠道性能指标"""
    channel: str
    success_count: int = 0
    fail_count: int = 0
    avg_latency: float = 0.0
    last_success: float = 0
    last_fail: float = 0
    status: str = "healthy"
    
    @property
    def success_rate(self) -> float:
        total = self.success_count + self.fail_count
        return self.success_count / total if total > 0 else 1.0


@dataclass
class RoutingRule:
    """路由规则"""
    name: str
    priority: int
    conditions: Dict[str, Any]  # 匹配条件
    targets: List[str]  # 目标渠道列表
    fallback: List[str] = field(default_factory=list)  # 备用渠道
    enabled: bool = True


class MessageRouter:
    """跨平台消息路由器"""
    
    def __init__(self):
        self.channels: Dict[str, ChannelMetrics] = {}
        self.rules: List[RoutingRule] = []
        self.message_buffer: Dict[str, List[Dict]] = defaultdict(list)
        self.buffer_ttl = 5  # 缓冲时间(秒)
        
        # 初始化默认渠道
        self._init_default_channels()
        self._init_default_rules()
    
    def _init_default_channels(self):
        """初始化默认渠道"""
        default_channels = ["dingtalk", "telegram", "email", "webhook"]
        for ch in default_channels:
            self.channels[ch] = ChannelMetrics(channel=ch)
    
    def _init_default_rules(self):
        """初始化默认路由规则"""
        self.rules = [
            RoutingRule(
                name="critical_alert",
                priority=1,
                conditions={"level": "critical", "type": "alert"},
                targets=["dingtalk", "telegram"],
                fallback=["email"]
            ),
            RoutingRule(
                name="error_alert",
                priority=2,
                conditions={"level": "error", "type": "alert"},
                targets=["dingtalk"],
                fallback=["email"]
            ),
            RoutingRule(
                name="system_notification",
                priority=3,
                conditions={"type": "system"},
                targets=["dingtalk"]
            ),
            RoutingRule(
                name="heartbeat",
                priority=4,
                conditions={"type": "heartbeat"},
                targets=[]
            ),
        ]
    
    def select_channel(self, message: Dict) -> List[str]:
        """智能选择最佳渠道"""
        # 按优先级匹配规则
        for rule in sorted(self.rules, key=lambda r: r.priority):
            if not rule.enabled:
                continue
            if self._match_conditions(message, rule.conditions):
                targets = rule.targets.copy()
                # 检查渠道可用性
                available = [ch for ch in targets if self.channels[ch].status != "failed"]
                if available:
                    return available
                # 尝试备用渠道
                if rule.fallback:
                    return [ch for ch in rule.fallback if self.channels[ch].status != "failed"]
                return []
        return []
    
    def _match_conditions(self, message: Dict, conditions: Dict) -> bool:
        """检查消息是否匹配条件"""
        for key, value in conditions.items():
            if key not in message:
                return False
            if isinstance(value, list):
                if message[key] not in value:
                    return False
            elif message[key] != value:
                return False
        return True
    
    def update_channel_status(self, channel: str, success: bool, latency: float = 0):
        """更新渠道状态"""
        if channel not in self.channels:
            self.channels[channel] = ChannelMetrics(channel=channel)
        
        metrics = self.channels[channel]
        now = time.time()
        
        if success:
            metrics.success_count += 1
            metrics.last_success = now
            # 滑动平均计算延迟
            metrics.avg_latency = (metrics.avg_latency * 0.9 + latency * 0.1)
            if metrics.status == "degraded":
                metrics.status = "healthy"
        else:
            metrics.fail_count += 1
            metrics.last_fail = now
            if metrics.fail_count >= 3:
                metrics.status = "failed"
            elif metrics.fail_count >= 1:
                metrics.status = "degraded"
    
    def get_optimal_channel(self, channels: List[str]) -> str:
        """获取最优渠道（基于延迟和成功率）"""
        candidates = [self.channels[ch] for ch in channels if ch in self.channels]
        if not candidates:
            return ""
        
        # 评分算法：成功率 * 0.7 + (1/延迟) * 0.3
        def score(m: ChannelMetrics) -> float:
            latency_factor = 1.0 / (m.avg_latency + 0.1)
            return m.success_rate * 0.7 + min(latency_factor, 10) * 0.3
        
        best = max(candidates, key=score)
        return best.channel
    
    def get_status(self) -> Dict:
        """获取路由状态"""
        return {
            "channels": {k: {
                "status": v.status,
                "success_rate": f"{v.success_rate*100:.1f}%",
                "avg_latency": f"{v.avg_latency:.2f}s"
            } for k, v in self.channels.items()},
            "rules_count": len(self.rules),
            "buffer_size": sum(len(v) for v in self.message_buffer.values())
        }


# 全局路由器实例
_router = MessageRouter()


def get_router() -> MessageRouter:
    return _router


if __name__ == "__main__":
    router = get_router()
    print("=== 消息路由优化模块 v2.0 ===")
    print(json.dumps(router.get_status(), indent=2, ensure_ascii=False))
    
    # 测试路由选择
    test_msg = {"level": "critical", "type": "alert", "content": "测试告警"}
    channels = router.select_channel(test_msg)
    print(f"\n测试消息路由: {test_msg}")
    print(f"选择渠道: {channels}")