#!/usr/bin/env python3
"""
决策自动化触发与编排引擎
Decision Automation Trigger and Orchestration Engine
事件驱动决策触发 + 任务编排
"""
import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from enum import Enum
import requests

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TriggerType(Enum):
    """触发器类型"""
    SCHEDULE = "schedule"           # 定时触发
    EVENT = "event"                 # 事件触发
    WEBHOOK = "webhook"             # Webhook触发
    METRIC = "metric"               # 指标阈值触发
    MANUAL = "manual"               # 手动触发


class EventSource(Enum):
    """事件源"""
    SYSTEM = "system"               # 系统事件
    SCHEDULER = "scheduler"         # 调度器
    WEBHOOK = "webhook"             # Webhook
    API = "api"                     # API调用
    MONITOR = "monitor"             # 监控系统
    WORKFLOW = "workflow"           # 工作流


@dataclass
class Trigger:
    """触发器定义"""
    id: str
    name: str
    type: TriggerType
    source: EventSource
    condition: Dict[str, Any]       # 触发条件
    action: str                     # 触发动作: decision, workflow, notify
    config: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_triggered: Optional[str] = None
    trigger_count: int = 0
    

@dataclass
class AutomationRule:
    """自动化规则"""
    id: str
    name: str
    trigger: Trigger
    decision_config: Dict[str, Any] = field(default_factory=dict)
    workflow_id: Optional[str] = None
    notification: Optional[Dict] = None
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class AutomationOrchestrator:
    """
    决策自动化触发与编排器
    - 支持多种触发器类型
    - 事件驱动决策
    - 任务编排与工作流联动
    """
    
    def __init__(self, 
                 decision_engine_url: str = "http://localhost:18120",
                 workflow_api_url: str = "http://localhost:18135"):
        self.decision_engine_url = decision_engine_url
        self.workflow_api_url = workflow_api_url
        
        # 触发器存储
        self.triggers: Dict[str, Trigger] = {}
        self.rules: Dict[str, AutomationRule] = {}
        
        # 执行器
        self.running = False
        self._thread = None
        self._schedule_thread = None
        
        # 统计
        self.stats = {
            "total_triggers": 0,
            "total_executions": 0,
            "decisions_made": 0,
            "workflows_triggered": 0,
            "errors": 0,
            "last_execution": None
        }
        
        # 回调
        self.on_decision: Optional[Callable] = None
        self.on_workflow: Optional[Callable] = None
        self.on_notification: Optional[Callable] = None
        
        # 内置触发器
        self._init_builtin_triggers()
        
    def _init_builtin_triggers(self):
        """初始化内置触发器"""
        
        # 1. 定期健康检查触发器
        health_trigger = Trigger(
            id="trigger-health-check",
            name="定期健康检查",
            type=TriggerType.SCHEDULE,
            source=EventSource.SCHEDULER,
            condition={"interval": 60},  # 60秒
            action="decision",
            config={"decision_type": "health_check"}
        )
        self.triggers[health_trigger.id] = health_trigger
        
        # 2. 高CPU触发器
        cpu_trigger = Trigger(
            id="trigger-high-cpu",
            name="高CPU告警",
            type=TriggerType.METRIC,
            source=EventSource.MONITOR,
            condition={"metric": "cpu", "threshold": 80, "operator": ">"},
            action="decision",
            config={"decision_type": "high_cpu_response"}
        )
        self.triggers[cpu_trigger.id] = cpu_trigger
        
        # 3. 高内存触发器
        memory_trigger = Trigger(
            id="trigger-high-memory",
            name="高内存告警",
            type=TriggerType.METRIC,
            source=EventSource.MONITOR,
            condition={"metric": "memory", "threshold": 85, "operator": ">"},
            action="decision",
            config={"decision_type": "high_memory_response"}
        )
        self.triggers[memory_trigger.id] = memory_trigger
        
        # 4. 磁盘空间不足触发器
        disk_trigger = Trigger(
            id="trigger-low-disk",
            name="磁盘空间不足",
            type=TriggerType.METRIC,
            source=EventSource.MONITOR,
            condition={"metric": "disk", "threshold": 90, "operator": ">"},
            action="workflow",
            config={"workflow_id": "cleanup-old-files"}
        )
        self.triggers[disk_trigger.id] = disk_trigger
        
        logger.info(f"初始化了 {len(self.triggers)} 个内置触发器")
    
    def add_trigger(self, trigger: Trigger) -> bool:
        """添加触发器"""
        self.triggers[trigger.id] = trigger
        logger.info(f"添加触发器: {trigger.id} - {trigger.name}")
        return True
    
    def remove_trigger(self, trigger_id: str) -> bool:
        """移除触发器"""
        if trigger_id in self.triggers:
            del self.triggers[trigger_id]
            logger.info(f"移除触发器: {trigger_id}")
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
    
    def create_rule(self, rule: AutomationRule) -> bool:
        """创建自动化规则"""
        self.rules[rule.id] = rule
        logger.info(f"创建自动化规则: {rule.id} - {rule.name}")
        return True
    
    def delete_rule(self, rule_id: str) -> bool:
        """删除自动化规则"""
        if rule_id in self.rules:
            del self.rules[rule_id]
            return True
        return False
    
    def evaluate_trigger(self, trigger: Trigger, context: Dict) -> bool:
        """评估触发条件"""
        if not trigger.enabled:
            return False
            
        trigger_type = trigger.type
        
        if trigger_type == TriggerType.SCHEDULE:
            # 定时触发：检查时间间隔
            interval = trigger.condition.get("interval", 60)
            if trigger.last_triggered:
                last = datetime.fromisoformat(trigger.last_triggered)
                elapsed = (datetime.now() - last).total_seconds()
                return elapsed >= interval
            return True
            
        elif trigger_type == TriggerType.METRIC:
            # 指标阈值触发
            metric = trigger.condition.get("metric")
            threshold = trigger.condition.get("threshold")
            operator = trigger.condition.get("operator", ">")
            
            value = context.get(metric)
            if value is None:
                return False
                
            if operator == ">":
                return value > threshold
            elif operator == ">=":
                return value >= threshold
            elif operator == "<":
                return value < threshold
            elif operator == "<=":
                return value <= threshold
            elif operator == "==":
                return value == threshold
            return False
            
        elif trigger_type == TriggerType.EVENT:
            # 事件触发：检查事件类型
            event_type = trigger.condition.get("event_type")
            return context.get("event_type") == event_type
            
        return False
    
    def execute_trigger(self, trigger: Trigger, context: Dict) -> Dict:
        """执行触发器动作"""
        self.stats["total_executions"] += 1
        self.stats["last_execution"] = datetime.now().isoformat()
        
        # 更新触发器状态
        trigger.last_triggered = datetime.now().isoformat()
        trigger.trigger_count += 1
        
        result = {
            "trigger_id": trigger.id,
            "trigger_name": trigger.name,
            "action": trigger.action,
            "timestamp": trigger.last_triggered,
            "success": False
        }
        
        try:
            if trigger.action == "decision":
                # 触发决策
                decision_result = self._execute_decision(trigger, context)
                result["decision"] = decision_result
                result["success"] = decision_result.get("success", False)
                self.stats["decisions_made"] += 1
                
                # 回调
                if self.on_decision:
                    self.on_decision(trigger, decision_result)
                    
            elif trigger.action == "workflow":
                # 触发工作流
                workflow_result = self._execute_workflow(trigger, context)
                result["workflow"] = workflow_result
                result["success"] = workflow_result is not None
                self.stats["workflows_triggered"] += 1
                
                # 回调
                if self.on_workflow:
                    self.on_workflow(trigger, workflow_result)
                    
            elif trigger.action == "notify":
                # 发送通知
                notification_result = self._send_notification(trigger, context)
                result["notification"] = notification_result
                result["success"] = True
                
                if self.on_notification:
                    self.on_notification(trigger, notification_result)
                    
        except Exception as e:
            logger.error(f"执行触发器 {trigger.id} 失败: {e}")
            self.stats["errors"] += 1
            result["error"] = str(e)
        
        return result
    
    def _execute_decision(self, trigger: Trigger, context: Dict) -> Dict:
        """执行决策"""
        decision_type = trigger.config.get("decision_type", "general")
        
        # 构建决策请求
        decision_request = {
            "trigger": trigger.id,
            "source": f"automation-{trigger.source.value}",
            "context": {
                **context,
                "automation_trigger": trigger.id,
                "decision_type": decision_type
            }
        }
        
        try:
            response = requests.post(
                f"{self.decision_engine_url}/decide",
                json=decision_request,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"决策请求失败: {response.status_code}")
                return {"success": False, "error": f"HTTP {response.status_code}"}
                
        except Exception as e:
            logger.error(f"决策执行异常: {e}")
            return {"success": False, "error": str(e)}
    
    def _execute_workflow(self, trigger: Trigger, context: Dict) -> Optional[Dict]:
        """执行工作流"""
        workflow_id = trigger.config.get("workflow_id")
        
        if not workflow_id:
            logger.warning(f"触发器 {trigger.id} 未配置workflow_id")
            return None
        
        workflow_context = {
            **context,
            "_triggered_by": trigger.id,
            "_trigger_name": trigger.name,
            "_source": "automation"
        }
        
        try:
            response = requests.post(
                f"{self.workflow_api_url}/workflows/run",
                json={"workflow_id": workflow_id, "params": workflow_context},
                timeout=60
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"工作流触发失败: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"工作流执行异常: {e}")
            return None
    
    def _send_notification(self, trigger: Trigger, context: Dict) -> Dict:
        """发送通知"""
        # 实现简化的通知逻辑
        notification_config = trigger.config.get("notification", {})
        
        logger.info(f"发送通知: {trigger.name}, 内容: {context}")
        
        return {
            "sent": True,
            "type": notification_config.get("type", "log"),
            "timestamp": datetime.now().isoformat()
        }
    
    def check_and_trigger(self, context: Dict) -> List[Dict]:
        """检查所有触发器并执行符合条件的"""
        results = []
        
        for trigger_id, trigger in self.triggers.items():
            if self.evaluate_trigger(trigger, context):
                logger.info(f"触发器 {trigger_id} 条件满足，执行动作: {trigger.action}")
                result = self.execute_trigger(trigger, context)
                results.append(result)
                self.stats["total_triggers"] += 1
        
        return results
    
    def collect_metrics(self) -> Dict:
        """收集系统指标"""
        metrics = {}
        
        try:
            # CPU
            with open('/proc/loadavg', 'r') as f:
                load = f.read().split()[0]
                metrics['cpu'] = min(100, float(load) * 25)
        except:
            metrics['cpu'] = 0
            
        try:
            # 内存
            with open('/proc/meminfo', 'r') as f:
                meminfo = f.read()
                total = int([x for x in meminfo.split('\n') if x.startswith('MemTotal:')][0].split()[1])
                available = int([x for x in meminfo.split('\n') if x.startswith('MemAvailable:')][0].split()[1])
                if total > 0:
                    metrics['memory'] = round((1 - available/total) * 100, 1)
        except:
            metrics['memory'] = 0
            
        try:
            # 磁盘
            import shutil
            usage = shutil.disk_usage('/')
            metrics['disk'] = round((usage.used / usage.total) * 100, 1)
        except:
            metrics['disk'] = 0
        
        metrics['_timestamp'] = datetime.now().isoformat()
        
        return metrics
    
    def run_cycle(self):
        """运行一个检查周期"""
        # 收集指标
        context = self.collect_metrics()
        
        # 检查触发器
        results = self.check_and_trigger(context)
        
        if results:
            logger.info(f"本周期触发 {len(results)} 个动作")
        
        return results
    
    def run(self):
        """运行自动化引擎"""
        logger.info("启动决策自动化引擎...")
        
        while self.running:
            try:
                self.run_cycle()
            except Exception as e:
                logger.error(f"自动化引擎循环错误: {e}")
                self.stats["errors"] += 1
            
            # 默认60秒周期
            time.sleep(60)
    
    def start(self):
        """启动自动化引擎"""
        if self.running:
            return
            
        self.running = True
        self._thread = threading.Thread(target=self.run, daemon=True)
        self._thread.start()
        logger.info("决策自动化引擎已启动")
    
    def stop(self):
        """停止自动化引擎"""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("决策自动化引擎已停止")
    
    def get_status(self) -> Dict:
        """获取状态"""
        return {
            "running": self.running,
            "triggers": len(self.triggers),
            "rules": len(self.rules),
            "stats": self.stats.copy(),
            "trigger_details": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.type.value,
                    "enabled": t.enabled,
                    "trigger_count": t.trigger_count,
                    "last_triggered": t.last_triggered
                }
                for t in self.triggers.values()
            ]
        }
    
    def manual_trigger(self, trigger_id: str, context: Dict = None) -> Optional[Dict]:
        """手动触发器"""
        if trigger_id not in self.triggers:
            return None
            
        trigger = self.triggers[trigger_id]
        context = context or {}
        
        logger.info(f"手动触发: {trigger_id}")
        return self.execute_trigger(trigger, context)


# Flask API Server
def create_api_server(orchestrator: AutomationOrchestrator):
    """创建API服务器"""
    from flask import Flask, request, jsonify
    
    app = Flask(__name__)
    
    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "ok",
            "service": "automation-orchestrator",
            "version": "1.0.0"
        })
    
    @app.route('/status', methods=['GET'])
    def status():
        return jsonify(orchestrator.get_status())
    
    @app.route('/triggers', methods=['GET'])
    def list_triggers():
        return jsonify({
            "triggers": [
                {
                    "id": t.id,
                    "name": t.name,
                    "type": t.type.value,
                    "source": t.source.value,
                    "condition": t.condition,
                    "action": t.action,
                    "enabled": t.enabled,
                    "trigger_count": t.trigger_count,
                    "last_triggered": t.last_triggered
                }
                for t in orchestrator.triggers.values()
            ]
        })
    
    @app.route('/triggers/<trigger_id>/enable', methods=['POST'])
    def enable_trigger(trigger_id):
        success = orchestrator.enable_trigger(trigger_id)
        return jsonify({"success": success})
    
    @app.route('/triggers/<trigger_id>/disable', methods=['POST'])
    def disable_trigger(trigger_id):
        success = orchestrator.disable_trigger(trigger_id)
        return jsonify({"success": success})
    
    @app.route('/triggers/<trigger_id>/trigger', methods=['POST'])
    def trigger_now(trigger_id):
        context = request.json or {}
        result = orchestrator.manual_trigger(trigger_id, context)
        if result:
            return jsonify({"success": True, "result": result})
        return jsonify({"success": False, "error": "Trigger not found"}), 404
    
    @app.route('/trigger', methods=['POST'])
    def trigger_all():
        """触发所有符合条件的触发器"""
        context = request.json or {}
        results = orchestrator.check_and_trigger(context)
        return jsonify({
            "success": True,
            "results": results,
            "count": len(results)
        })
    
    @app.route('/evaluate', methods=['POST'])
    def evaluate():
        """评估触发条件"""
        context = request.json or {}
        triggered = []
        
        for trigger in orchestrator.triggers.values():
            if orchestrator.evaluate_trigger(trigger, context):
                triggered.append({
                    "id": trigger.id,
                    "name": trigger.name,
                    "type": trigger.type.value
                })
        
        return jsonify({
            "context": context,
            "triggered": triggered,
            "count": len(triggered)
        })
    
    @app.route('/run-cycle', methods=['POST'])
    def run_cycle():
        """立即运行一个检查周期"""
        results = orchestrator.run_cycle()
        return jsonify({
            "success": True,
            "results": results,
            "count": len(results)
        })
    
    return app


def main():
    """主入口"""
    import sys
    
    # 创建编排器
    orchestrator = AutomationOrchestrator(
        decision_engine_url="http://localhost:18120",
        workflow_api_url="http://localhost:18135"
    )
    
    # 创建API服务器
    app = create_api_server(orchestrator)
    
    # 启动自动化引擎
    orchestrator.start()
    
    # 立即执行一次
    results = orchestrator.run_cycle()
    print(f"初始执行: {len(results)} 个触发")
    
    # 启动API服务器
    port = 18128
    print(f"启动自动化编排API服务器: 端口 {port}")
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()