#!/usr/bin/env python3
"""
决策引擎触发器管理器
管理自动化触发器和规则
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class TriggerType(Enum):
    SCHEDULE = "schedule"
    METRIC = "metric"
    EVENT = "event"
    MANUAL = "manual"
    WEBHOOK = "webhook"


class TriggerSource(Enum):
    SYSTEM = "system"
    USER = "user"
    EXTERNAL = "external"


class TriggerCondition:
    """触发条件"""
    
    def __init__(self, condition_type: str, config: Dict):
        self.type = condition_type
        self.config = config
    
    def evaluate(self, context: Dict) -> bool:
        """评估条件是否满足"""
        if self.type == "metric_threshold":
            return self._eval_metric_threshold(context)
        elif self.type == "schedule":
            return self._eval_schedule(context)
        elif self.type == "custom":
            return self._eval_custom(context)
        return False
    
    def _eval_metric_threshold(self, context: Dict) -> bool:
        metric = self.config.get("metric")
        operator = self.config.get("operator", ">")
        threshold = self.config.get("threshold")
        
        value = context.get(metric)
        if value is None:
            return False
        
        if operator == ">":
            return value > threshold
        elif operator == "<":
            return value < threshold
        elif operator == ">=":
            return value >= threshold
        elif operator == "<=":
            return value <= threshold
        elif operator == "==":
            return value == threshold
        return False
    
    def _eval_schedule(self, context: Dict) -> bool:
        # 定时触发总是返回True，由调度器控制
        return True
    
    def _eval_custom(self, context: Dict) -> bool:
        # 自定义条件评估
        return True


class TriggerAction:
    """触发动作"""
    
    def __init__(self, action_type: str, config: Dict):
        self.type = action_type
        self.config = config
    
    def execute(self, context: Dict) -> Dict:
        """执行动作"""
        if self.type == "notify":
            return self._execute_notify(context)
        elif self.type == "api_call":
            return self._execute_api_call(context)
        elif self.type == "shell":
            return self._execute_shell(context)
        elif self.type == "webhook":
            return self._execute_webhook(context)
        elif self.type == "auto_scale":
            return self._execute_auto_scale(context)
        return {"success": False, "error": f"Unknown action type: {self.type}"}
    
    def _execute_notify(self, context: Dict) -> Dict:
        # 通知动作
        message = self.config.get("message", "").format(**context)
        logger.info(f"Notification: {message}")
        return {"success": True, "action": "notify", "message": message}
    
    def _execute_api_call(self, context: Dict) -> Dict:
        # API调用动作
        import requests
        url = self.config.get("url")
        method = self.config.get("method", "POST")
        try:
            response = requests.request(method, url, json=context, timeout=10)
            return {"success": True, "action": "api_call", "status": response.status_code}
        except Exception as e:
            return {"success": False, "action": "api_call", "error": str(e)}
    
    def _execute_shell(self, context: Dict) -> Dict:
        # Shell命令动作
        import subprocess
        command = self.config.get("command", "").format(**context)
        try:
            result = subprocess.run(command, shell=True, capture_output=True, timeout=30)
            return {
                "success": result.returncode == 0,
                "action": "shell",
                "output": result.stdout.decode()[:500],
                "returncode": result.returncode
            }
        except Exception as e:
            return {"success": False, "action": "shell", "error": str(e)}
    
    def _execute_webhook(self, context: Dict) -> Dict:
        # Webhook动作
        return self._execute_api_call(context)
    
    def _execute_auto_scale(self, context: Dict) -> Dict:
        # 自动扩缩容动作
        logger.info(f"Auto-scale action triggered: {context}")
        return {"success": True, "action": "auto_scale"}


@dataclass
class Trigger:
    """触发器定义"""
    id: str
    name: str
    type: TriggerType
    source: TriggerSource
    condition: TriggerCondition
    action: TriggerAction
    enabled: bool = True
    trigger_count: int = 0
    last_triggered: str = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type.value,
            "source": self.source.value,
            "condition_type": self.condition.type,
            "action_type": self.action.type,
            "enabled": self.enabled,
            "trigger_count": self.trigger_count,
            "last_triggered": self.last_triggered,
            "created_at": self.created_at
        }


class TriggerManager:
    """触发器管理器"""
    
    def __init__(self):
        self.triggers: Dict[str, Trigger] = {}
        self.execution_history: List[Dict] = []
        self._load_default_triggers()
    
    def _load_default_triggers(self):
        """加载默认触发器"""
        # CPU高负载告警
        self.add_trigger(Trigger(
            id="trigger-high-cpu",
            name="高CPU告警",
            type=TriggerType.METRIC,
            source=TriggerSource.SYSTEM,
            condition=TriggerCondition("metric_threshold", {
                "metric": "cpu_usage",
                "operator": ">",
                "threshold": 80
            }),
            action=TriggerAction("notify", {
                "message": "CPU使用率过高: {cpu_usage}%"
            })
        ))
        
        # 内存高负载告警
        self.add_trigger(Trigger(
            id="trigger-high-memory",
            name="高内存告警",
            type=TriggerType.METRIC,
            source=TriggerSource.SYSTEM,
            condition=TriggerCondition("metric_threshold", {
                "metric": "memory_percent",
                "operator": ">",
                "threshold": 85
            }),
            action=TriggerAction("notify", {
                "message": "内存使用率过高: {memory_percent}%"
            })
        ))
        
        # 磁盘空间告警
        self.add_trigger(Trigger(
            id="trigger-low-disk",
            name="磁盘空间不足告警",
            type=TriggerType.METRIC,
            source=TriggerSource.SYSTEM,
            condition=TriggerCondition("metric_threshold", {
                "metric": "disk_percent",
                "operator": ">",
                "threshold": 90
            }),
            action=TriggerAction("notify", {
                "message": "磁盘空间不足: {disk_percent}%"
            })
        ))
        
        # 定期健康检查
        self.add_trigger(Trigger(
            id="trigger-health-check",
            name="定期健康检查",
            type=TriggerType.SCHEDULE,
            source=TriggerSource.SYSTEM,
            condition=TriggerCondition("schedule", {}),
            action=TriggerAction("api_call", {
                "url": "http://localhost:8888/health",
                "method": "GET"
            })
        ))
        
        logger.info(f"Loaded {len(self.triggers)} default triggers")
    
    def add_trigger(self, trigger: Trigger):
        """添加触发器"""
        self.triggers[trigger.id] = trigger
        logger.info(f"Added trigger: {trigger.id}")
    
    def remove_trigger(self, trigger_id: str) -> bool:
        """移除触发器"""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            return True
        return False
    
    def enable_trigger(self, trigger_id: str) -> bool:
        """启用触发器"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = True
            return True
        return False
    
    def disable_trigger(self, trigger_id: str) -> bool:
        """禁用触发器"""
        if trigger_id in self.triggers:
            self.triggers[trigger_id].enabled = False
            return True
        return False
    
    def check_and_trigger(self, context: Dict) -> List[Dict]:
        """检查并触发符合条件的触发器"""
        results = []
        for trigger in self.triggers.values():
            if not trigger.enabled:
                continue
            
            try:
                if trigger.condition.evaluate(context):
                    result = trigger.action.execute(context)
                    trigger.trigger_count += 1
                    trigger.last_triggered = datetime.now().isoformat()
                    
                    execution_record = {
                        "trigger_id": trigger.id,
                        "trigger_name": trigger.name,
                        "timestamp": trigger.last_triggered,
                        "context": context,
                        "result": result
                    }
                    self.execution_history.append(execution_record)
                    results.append(execution_record)
                    
                    logger.info(f"Triggered: {trigger.name}")
            except Exception as e:
                logger.error(f"Error evaluating trigger {trigger.id}: {e}")
        
        return results
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "total_triggers": len(self.triggers),
            "enabled_triggers": sum(1 for t in self.triggers.values() if t.enabled),
            "total_executions": sum(t.trigger_count for t in self.triggers.values()),
            "triggers": [t.to_dict() for t in self.triggers.values()]
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    manager = TriggerManager()
    print(json.dumps(manager.get_status(), indent=2, ensure_ascii=False))