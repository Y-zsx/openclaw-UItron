#!/usr/bin/env python3
"""
告警通知集成API服务
提供统一的告警发送、聚合、升级和统计接口
端口: 18170
"""

import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
from threading import Lock
import uuid

from flask import Flask, request, jsonify
from flask_cors import CORS

# 导入通知渠道模块
import sys
sys.path.insert(0, '/root/.openclaw/workspace/ultron/tools')
from alert_notification_channels import AlertNotificationManager, AlertNotification

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)


class AlertStatus(Enum):
    """告警状态"""
    FIRING = "firing"      # 触发中
    RESOLVED = "resolved"  # 已解决
    EXPIRED = "expired"    # 已过期
    SUPPRESSED = "suppressed"  # 已抑制


class AlertLevel(Enum):
    """告警级别"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class Alert:
    """告警数据模型"""
    id: str
    rule_id: str
    rule_name: str
    service_name: str
    level: str
    message: str
    value: float
    threshold: float
    status: str = "firing"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None
    annotations: Dict[str, str] = field(default_factory=dict)
    labels: Dict[str, str] = field(default_factory=dict)
    source: str = "api"
    notified_channels: List[str] = field(default_factory=list)
    notification_count: int = 0
    escalate_level: int = 0
    group_key: Optional[str] = None  # 用于告警聚合


@dataclass
class AlertGroup:
    """告警组（用于聚合）"""
    key: str
    rule_id: str
    rule_name: str
    service_name: str
    level: str
    count: int = 1
    first_alert_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_alert_at: str = field(default_factory=lambda: datetime.now().isoformat())
    alerts: List[str] = field(default_factory=list)


class AlertAggregation:
    """告警聚合器"""
    
    def __init__(self, group_window_seconds: int = 300):
        self.groups: Dict[str, AlertGroup] = {}
        self.group_window_seconds = group_window_seconds
        self.lock = Lock()
    
    def get_group_key(self, alert: Dict) -> str:
        """计算告警分组key"""
        # 基于 rule_id + service_name + level 分组
        return f"{alert.get('rule_id', '')}:{alert.get('service_name', '')}:{alert.get('level', '')}"
    
    def process(self, alert: Dict) -> Optional[AlertGroup]:
        """处理告警，返回是否需要发送新通知"""
        group_key = self.get_group_key(alert)
        
        with self.lock:
            if group_key in self.groups:
                group = self.groups[group_key]
                
                # 检查时间窗口
                last_time = datetime.fromisoformat(group.last_alert_at)
                now = datetime.now()
                
                if (now - last_time).total_seconds() < self.group_window_seconds:
                    # 在窗口期内，只更新计数
                    group.count += 1
                    group.last_alert_at = now.isoformat()
                    group.alerts.append(alert.get("id", ""))
                    # 不触发新通知
                    return None
                else:
                    # 窗口期外，创建新组
                    group.count = 1
                    group.first_alert_at = now.isoformat()
                    group.last_alert_at = now.isoformat()
                    group.alerts = [alert.get("id", "")]
                    return group
            else:
                # 新组
                group = AlertGroup(
                    key=group_key,
                    rule_id=alert.get("rule_id", ""),
                    rule_name=alert.get("rule_name", ""),
                    service_name=alert.get("service_name", ""),
                    level=alert.get("level", "info"),
                    alerts=[alert.get("id", "")]
                )
                self.groups[group_key] = group
                return group
    
    def cleanup(self, max_age_hours: int = 24):
        """清理过期的分组"""
        with self.lock:
            now = datetime.now()
            expired_keys = []
            for key, group in self.groups.items():
                last_time = datetime.fromisoformat(group.last_alert_at)
                if (now - last_time).total_seconds() > max_age_hours * 3600:
                    expired_keys.append(key)
            
            for key in expired_keys:
                del self.groups[key]
            
            if expired_keys:
                logger.info(f"清理了 {len(expired_keys)} 个过期告警组")


class AlertEscalation:
    """告警升级器"""
    
    def __init__(self):
        self.escalation_rules = {
            "critical": 0,      # 立即升级
            "error": 300,       # 5分钟后升级
            "warning": 600,     # 10分钟后升级
            "info": 1800        # 30分钟后升级
        }
        self.escalation_actions = {}
        self.lock = Lock()
    
    def should_escalate(self, alert: Alert) -> bool:
        """检查是否需要升级"""
        if alert.status != "firing":
            return False
        
        # 检查是否已经升级过
        if alert.escalate_level >= 3:
            return False
        
        # 检查时间
        created = datetime.fromisoformat(alert.created_at)
        now = datetime.now()
        age_seconds = (now - created).total_seconds()
        
        threshold = self.escalation_rules.get(alert.level, 1800)
        return age_seconds > threshold * (alert.escalate_level + 1)
    
    def escalate(self, alert: Alert) -> Dict:
        """执行升级"""
        with self.lock:
            alert.escalate_level += 1
            
            # 升级动作
            actions = []
            if alert.escalate_level == 1:
                actions.append("notify_supervisor")
            elif alert.escalate_level == 2:
                actions.append("notify_manager")
            elif alert.escalate_level >= 3:
                actions.append("notify_on_call")
            
            return {
                "alert_id": alert.id,
                "escalate_level": alert.escalate_level,
                "actions": actions,
                "timestamp": datetime.now().isoformat()
            }


class AlertIntegrationAPI:
    """告警通知集成API"""
    
    def __init__(self):
        self.alerts: Dict[str, Alert] = {}
        self.notification_manager = AlertNotificationManager()
        self.aggregation = AlertAggregation(group_window_seconds=300)
        self.escalation = AlertEscalation()
        self.lock = Lock()
        
        # 统计
        self.stats = {
            "total_alerts": 0,
            "firing_count": 0,
            "resolved_count": 0,
            "by_level": {"info": 0, "warning": 0, "error": 0, "critical": 0},
            "by_service": defaultdict(int),
            "notification_sent": 0,
            "notification_failed": 0
        }
        
        # 加载历史告警
        self._load_history()
    
    def _load_history(self):
        """加载历史告警"""
        try:
            import os
            history_path = "/root/.openclaw/workspace/ultron/data/alert_history.json"
            if os.path.exists(history_path):
                with open(history_path, 'r') as f:
                    data = json.load(f)
                    for alert_data in data.get("alerts", []):
                        alert = Alert(**alert_data)
                        self.alerts[alert.id] = alert
                    logger.info(f"加载了 {len(self.alerts)} 条历史告警")
        except Exception as e:
            logger.warning(f"加载历史告警失败: {e}")
    
    def _save_history(self):
        """保存历史告警"""
        try:
            import os
            history_path = "/root/.openclaw/workspace/ultron/data/alert_history.json"
            os.makedirs(os.path.dirname(history_path), exist_ok=True)
            
            # 只保留最近1000条
            recent_alerts = list(self.alerts.values())[-1000:]
            
            with open(history_path, 'w') as f:
                json.dump({
                    "alerts": [asdict(a) for a in recent_alerts],
                    "saved_at": datetime.now().isoformat()
                }, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"保存历史告警失败: {e}")
    
    def create_alert(self, alert_data: Dict) -> Dict:
        """创建告警"""
        with self.lock:
            # 生成ID
            alert_id = alert_data.get("id") or f"alert-{uuid.uuid4().hex[:12]}"
            
            # 检查是否已存在（避免重复）
            if alert_id in self.alerts:
                existing = self.alerts[alert_id]
                if existing.status == "firing":
                    # 更新现有告警
                    existing.value = alert_data.get("value", existing.value)
                    existing.message = alert_data.get("message", existing.message)
                    existing.updated_at = datetime.now().isoformat()
                    return {"alert": asdict(existing), "is_new": False, "notification_sent": False}
            
            # 创建新告警
            alert = Alert(
                id=alert_id,
                rule_id=alert_data.get("rule_id", ""),
                rule_name=alert_data.get("rule_name", "Unknown"),
                service_name=alert_data.get("service_name", "unknown"),
                level=alert_data.get("level", "info"),
                message=alert_data.get("message", ""),
                value=alert_data.get("value", 0),
                threshold=alert_data.get("threshold", 0),
                status=alert_data.get("status", "firing"),
                annotations=alert_data.get("annotations", {}),
                labels=alert_data.get("labels", {}),
                source=alert_data.get("source", "api")
            )
            
            self.alerts[alert_id] = alert
            
            # 更新统计
            self.stats["total_alerts"] += 1
            self.stats["firing_count"] += 1
            self.stats["by_level"][alert.level] = self.stats["by_level"].get(alert.level, 0) + 1
            self.stats["by_service"][alert.service_name] += 1
            
            # 处理聚合
            alert_dict = asdict(alert)
            group = self.aggregation.process(alert_dict)
            
            # 决定是否发送通知
            should_notify = group is not None
            
            if should_notify:
                # 发送通知
                notification_sent = self._send_notification(alert)
                alert.notified_channels = list(notification_sent.keys())
                alert.notification_count = 1
            
            self._save_history()
            
            return {
                "alert": asdict(alert),
                "is_new": True,
                "notification_sent": should_notify,
                "group_info": asdict(group) if group else None
            }
    
    def _send_notification(self, alert: Alert) -> Dict[str, bool]:
        """发送通知"""
        alert_dict = asdict(alert)
        results = self.notification_manager.send_alert(alert_dict)
        
        # 更新统计
        for channel_id, success in results.items():
            if success:
                self.stats["notification_sent"] += 1
            else:
                self.stats["notification_failed"] += 1
        
        return results
    
    def resolve_alert(self, alert_id: str, message: str = None) -> Optional[Dict]:
        """解决告警"""
        with self.lock:
            if alert_id not in self.alerts:
                return None
            
            alert = self.alerts[alert_id]
            alert.status = "resolved"
            alert.resolved_at = datetime.now().isoformat()
            alert.updated_at = datetime.now().isoformat()
            
            if message:
                alert.annotations["resolve_message"] = message
            
            self.stats["firing_count"] -= 1
            self.stats["resolved_count"] += 1
            
            self._save_history()
            
            return asdict(alert)
    
    def get_alert(self, alert_id: str) -> Optional[Dict]:
        """获取告警详情"""
        alert = self.alerts.get(alert_id)
        return asdict(alert) if alert else None
    
    def get_alerts(self, status: str = None, level: str = None, 
                   service: str = None, limit: int = 100,
                   start_time: str = None, end_time: str = None,
                   search: str = None, offset: int = 0) -> List[Dict]:
        """查询告警列表"""
        results = []
        
        # 解析时间范围
        start_dt = None
        end_dt = None
        if start_time:
            try:
                start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            except:
                pass
        if end_time:
            try:
                end_dt = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            except:
                pass
        
        for alert in self.alerts.values():
            # 状态过滤
            if status and alert.status != status:
                continue
            # 级别过滤
            if level and alert.level != level:
                continue
            # 服务过滤
            if service and alert.service_name != service:
                continue
            
            # 时间范围过滤
            if start_dt or end_dt:
                alert_dt = datetime.fromisoformat(alert.created_at.replace('Z', '+00:00'))
                if start_dt and alert_dt < start_dt:
                    continue
                if end_dt and alert_dt > end_dt:
                    continue
            
            # 关键字搜索
            if search:
                search_lower = search.lower()
                if (search_lower not in alert.message.lower() and 
                    search_lower not in alert.rule_name.lower() and
                    search_lower not in alert.service_name.lower()):
                    continue
            
            results.append(asdict(alert))
        
        # 按时间倒序
        results.sort(key=lambda x: x["created_at"], reverse=True)
        return results[offset:offset+limit]
    
    def get_alert_history_stats(self, hours: int = 24) -> Dict:
        """获取告警历史趋势统计"""
        now = datetime.now()
        start_dt = now - timedelta(hours=hours)
        
        # 按小时统计
        hourly_stats = defaultdict(lambda: {"total": 0, "firing": 0, "resolved": 0, 
                                            "info": 0, "warning": 0, "error": 0, "critical": 0})
        
        for alert in self.alerts.values():
            alert_dt = datetime.fromisoformat(alert.created_at.replace('Z', '+00:00'))
            if alert_dt < start_dt:
                continue
            
            hour_key = alert_dt.strftime("%Y-%m-%d %H:00")
            hourly_stats[hour_key]["total"] += 1
            hourly_stats[hour_key][alert.level] += 1
            if alert.status == "firing":
                hourly_stats[hour_key]["firing"] += 1
            else:
                hourly_stats[hour_key]["resolved"] += 1
        
        # 转换为列表
        timeline = []
        for hour in sorted(hourly_stats.keys()):
            timeline.append({
                "hour": hour,
                **hourly_stats[hour]
            })
        
        return {
            "period_hours": hours,
            "timeline": timeline,
            "summary": {
                "total": sum(h["total"] for h in timeline),
                "by_level": {
                    "info": sum(h["info"] for h in timeline),
                    "warning": sum(h["warning"] for h in timeline),
                    "error": sum(h["error"] for h in timeline),
                    "critical": sum(h["critical"] for h in timeline)
                }
            }
        }
    
    def get_firing_alerts(self) -> List[Dict]:
        """获取所有触发中的告警"""
        return [asdict(a) for a in self.alerts.values() if a.status == "firing"]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self.stats,
            "firing_alerts": len([a for a in self.alerts.values() if a.status == "firing"]),
            "active_channels": len([ch for ch in self.notification_manager.channels.values() if ch.enabled])
        }
    
    def check_escalation(self) -> List[Dict]:
        """检查需要升级的告警"""
        escalations = []
        
        for alert in self.alerts.values():
            if self.escalation.should_escalate(alert):
                result = self.escalation.escalate(alert)
                # 发送升级通知
                self._send_notification(alert)
                escalations.append(result)
        
        return escalations
    
    def add_channel(self, channel_data: Dict) -> Dict:
        """添加通知渠道"""
        from alert_notification_channels import NotificationChannel
        
        channel = NotificationChannel(
            id=channel_data.get("id", f"channel-{uuid.uuid4().hex[:8]}"),
            name=channel_data.get("name", "Unnamed"),
            channel_type=channel_data.get("type", "webhook"),
            enabled=channel_data.get("enabled", True),
            config=channel_data.get("config", {}),
            min_level=channel_data.get("min_level", "info"),
            services=channel_data.get("services", [])
        )
        
        success = self.notification_manager.add_channel(channel)
        return {"success": success, "channel": asdict(channel)}
    
    def get_channels(self) -> List[Dict]:
        """获取所有通知渠道"""
        return self.notification_manager.get_channels()
    
    def test_notification(self, channel_id: str = None) -> Dict:
        """测试通知"""
        test_alert = {
            "id": f"test-{uuid.uuid4().hex[:8]}",
            "rule_id": "test-rule",
            "rule_name": "测试告警",
            "service_name": "alert-integration",
            "level": "warning",
            "message": "这是一条测试告警",
            "value": 50.0,
            "threshold": 80.0,
            "status": "firing",
            "source": "test"
        }
        
        if channel_id:
            # 只测试指定渠道
            channel = self.notification_manager.channels.get(channel_id)
            if not channel:
                return {"success": False, "error": "Channel not found"}
            
            notifier = self.notification_manager.notifiers.get(channel_id)
            if not notifier:
                return {"success": False, "error": "Notifier not initialized"}
            
            notification = AlertNotification(
                alert_id=test_alert["id"],
                rule_id=test_alert["rule_id"],
                rule_name=test_alert["rule_name"],
                service_name=test_alert["service_name"],
                level=test_alert["level"],
                message=test_alert["message"],
                value=test_alert["value"],
                threshold=test_alert["threshold"],
                status=test_alert["status"],
                created_at=test_alert.get("created_at", datetime.now().isoformat()),
                channel=channel_id
            )
            
            success = notifier.send(notification)
            return {"success": success, "channel_id": channel_id}
        else:
            # 测试所有渠道
            results = self.notification_manager.send_alert(test_alert)
            return {"success": any(results.values()), "results": results}


# 全局实例
alert_api = AlertIntegrationAPI()


# ========== API 路由 ==========

@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    return jsonify({"status": "ok", "service": "alert-integration-api"})


@app.route("/alerts", methods=["POST"])
def create_alert():
    """创建告警"""
    try:
        data = request.get_json()
        result = alert_api.create_alert(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"创建告警失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/alerts", methods=["GET"])
def get_alerts():
    """查询告警列表
    
    支持的参数:
    - status: 告警状态 (firing/resolved)
    - level: 告警级别 (info/warning/error/critical)
    - service: 服务名称
    - start_time: 开始时间 (ISO格式)
    - end_time: 结束时间 (ISO格式)
    - search: 关键字搜索
    - offset: 分页偏移
    - limit: 返回数量 (默认100)
    """
    status = request.args.get("status")
    level = request.args.get("level")
    service = request.args.get("service")
    start_time = request.args.get("start_time")
    end_time = request.args.get("end_time")
    search = request.args.get("search")
    offset = int(request.args.get("offset", 0))
    limit = int(request.args.get("limit", 100))
    
    alerts = alert_api.get_alerts(status, level, service, limit, 
                                   start_time, end_time, search, offset)
    return jsonify({"alerts": alerts, "count": len(alerts), "offset": offset})


@app.route("/alerts/history", methods=["GET"])
def get_alert_history():
    """获取告警历史趋势统计
    
    支持的参数:
    - hours: 统计小时数 (默认24, 最大168)
    """
    hours = min(int(request.args.get("hours", 24)), 168)
    stats = alert_api.get_alert_history_stats(hours)
    return jsonify(stats)


@app.route("/alerts/firing", methods=["GET"])
def get_firing_alerts():
    """获取触发中的告警"""
    alerts = alert_api.get_firing_alerts()
    return jsonify({"alerts": alerts, "count": len(alerts)})


@app.route("/alerts/<alert_id>", methods=["GET"])
def get_alert(alert_id):
    """获取告警详情"""
    alert = alert_api.get_alert(alert_id)
    if alert:
        return jsonify(alert)
    return jsonify({"error": "Alert not found"}), 404


@app.route("/alerts/<alert_id>/resolve", methods=["POST"])
def resolve_alert(alert_id):
    """解决告警"""
    data = request.get_json() or {}
    message = data.get("message", "")
    
    result = alert_api.resolve_alert(alert_id, message)
    if result:
        return jsonify({"success": True, "alert": result})
    return jsonify({"error": "Alert not found"}), 404


@app.route("/stats", methods=["GET"])
def get_stats():
    """获取统计信息"""
    return jsonify(alert_api.get_stats())


@app.route("/channels", methods=["GET"])
def get_channels():
    """获取通知渠道"""
    return jsonify({"channels": alert_api.get_channels()})


@app.route("/channels", methods=["POST"])
def add_channel():
    """添加通知渠道"""
    try:
        data = request.get_json()
        result = alert_api.add_channel(data)
        return jsonify(result)
    except Exception as e:
        logger.error(f"添加渠道失败: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/channels/<channel_id>", methods=["DELETE"])
def remove_channel(channel_id):
    """移除通知渠道"""
    success = alert_api.notification_manager.remove_channel(channel_id)
    return jsonify({"success": success})


@app.route("/test", methods=["POST"])
def test_notification():
    """测试通知"""
    data = request.get_json() or {}
    channel_id = data.get("channel_id")
    
    result = alert_api.test_notification(channel_id)
    return jsonify(result)


@app.route("/escalation/check", methods=["POST"])
def check_escalation():
    """检查并执行告警升级"""
    escalations = alert_api.check_escalation()
    return jsonify({"escalations": escalations, "count": len(escalations)})


@app.route("/", methods=["GET"])
def index():
    """API信息"""
    return jsonify({
        "service": "Alert Integration API",
        "version": "1.1.0",
        "port": 18170,
        "endpoints": [
            "POST /alerts - 创建告警",
            "GET /alerts - 查询告警列表 (支持status/level/service/start_time/end_time/search/offset/limit)",
            "GET /alerts/history - 获取告警历史趋势统计 (支持hours参数)",
            "GET /alerts/firing - 获取触发中的告警",
            "GET /alerts/<id> - 获取告警详情",
            "POST /alerts/<id>/resolve - 解决告警",
            "GET /stats - 获取统计信息",
            "GET /channels - 获取通知渠道",
            "POST /channels - 添加通知渠道",
            "DELETE /channels/<id> - 移除通知渠道",
            "POST /test - 测试通知",
            "POST /escalation/check - 检查告警升级"
        ]
    })


if __name__ == "__main__":
    logger.info("启动告警通知集成API服务，端口: 18170")
    app.run(host="0.0.0.0", port=18170, debug=False)