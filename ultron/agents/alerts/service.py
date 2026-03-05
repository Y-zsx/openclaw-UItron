#!/usr/bin/env python3
"""
Agent告警系统 - 统一服务入口
第53世: 实现Agent告警与通知系统
"""

import json
import os
import sys
import time
import argparse
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alerts.engine import AlertEngine, AlertRule, AlertLevel
from alerts.notifier import AlertNotifier, ConsoleChannel, FileChannel, DingTalkChannel
from alerts.store import AlertStore
from alerts.escalation import AlertEscalationManager


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AlertService:
    """Agent告警服务"""
    
    def __init__(self, config_path: str = None):
        self.config_path = config_path or "/root/.openclaw/workspace/ultron/agents/alerts/config.json"
        self.config = self._load_config()
        
        # 初始化组件
        data_dir = os.path.join(os.path.dirname(__file__), "data")
        
        self.engine = AlertEngine()
        self.notifier = self._init_notifier()
        self.store = AlertStore(data_dir)
        self.escalation = AlertEscalationManager(self.store)
        
        logger.info("Agent告警服务初始化完成")
    
    def _load_config(self) -> Dict:
        """加载配置"""
        if os.path.exists(self.config_path):
            with open(self.config_path, 'r') as f:
                return json.load(f)
        return {}
    
    def _init_notifier(self) -> AlertNotifier:
        """初始化通知器"""
        return AlertNotifier(self.config.get("notifications", {}))
    
    def process_metrics(self, metrics: Dict[str, Any]) -> List[Dict]:
        """处理指标，检测告警"""
        # 使用引擎检查规则
        alerts = self.engine.check(metrics)
        
        # 处理每个告警
        sent_alerts = []
        for alert in alerts:
            # 存储告警
            alert_id = self.store.add_alert(alert)
            alert["_id"] = alert_id
            
            # 发送通知
            results = self.notifier.send(alert)
            
            # 检查是否需要升级
            escalation = self.escalation.check_escalation(alert)
            if escalation:
                self.escalation.process_escalations([alert], self.notifier)
            
            sent_alerts.append(alert)
            
            logger.info(f"告警: [{alert['level']}] {alert['message']}")
        
        return sent_alerts
    
    def get_status(self) -> Dict:
        """获取服务状态"""
        return {
            "engine": {
                "rules_count": len(self.engine.rules),
                "enabled_rules": len([r for r in self.engine.rules.values() if r.enabled])
            },
            "store": self.store.get_alert_stats(24),
            "notifier": self.notifier.get_notification_stats(),
            "escalation": self.escalation.get_escalation_stats()
        }
    
    def add_rule(self, rule: AlertRule):
        """添加规则"""
        self.engine.add_rule(rule)
        self.engine.save_rules()
    
    def list_rules(self) -> List[Dict]:
        """列出规则"""
        return self.engine.list_rules()
    
    def get_firing_alerts(self) -> List[Dict]:
        """获取活跃告警"""
        return self.store.get_firing_alerts()
    
    def test_notification(self, level: str = "WARNING") -> Dict:
        """测试通知"""
        test_alert = {
            "rule_id": "test_rule",
            "rule_name": "测试规则",
            "level": level,
            "message": "这是一条测试告警",
            "metric": "test.metric",
            "value": 99.9,
            "threshold": 80,
            "condition": "gt",
            "state": "firing",
            "timestamp": datetime.now().isoformat(),
            "tags": {"test": "true"}
        }
        
        results = self.notifier.send(test_alert)
        return {"sent": len([r for r in results if r.success]), "results": [r.to_dict() for r in results]}


def create_demo_config():
    """创建演示配置"""
    config = {
        "notifications": {
            "channels": {
                "console": {"enabled": True, "min_level": "INFO"},
                "file": {"enabled": True, "path": "/root/.openclaw/workspace/ultron/agents/alerts/data/alerts.json"},
                "dingtalk": {"enabled": False, "webhook": "", "secret": ""}
            }
        },
        "rules": [
            {
                "id": "demo_high_cpu",
                "name": "演示CPU告警",
                "metric_path": "cpu.usage",
                "condition": "gte",
                "threshold": 90,
                "level": 2,
                "message": "CPU使用率过高"
            }
        ]
    }
    
    config_path = "/root/.openclaw/workspace/ultron/agents/alerts/config.json"
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)
    
    return config_path


def main():
    """CLI入口"""
    parser = argparse.ArgumentParser(description="Agent告警系统")
    parser.add_argument("--init", action="store_true", help="初始化配置")
    parser.add_argument("--status", action="store_true", help="查看状态")
    parser.add_argument("--rules", action="store_true", help="列出规则")
    parser.add_argument("--firing", action="store_true", help="查看活跃告警")
    parser.add_argument("--test", type=str, help="测试通知 (WARNING|CRITICAL)")
    parser.add_argument("--process", type=str, help="处理指标JSON文件")
    
    args = parser.parse_args()
    
    # 初始化
    if args.init:
        config_path = create_demo_config()
        print(f"✅ 配置已创建: {config_path}")
        return
    
    # 创建服务
    try:
        service = AlertService()
    except Exception as e:
        logger.error(f"服务初始化失败: {e}")
        # 创建默认配置
        create_demo_config()
        service = AlertService()
    
    # 查看状态
    if args.status:
        status = service.get_status()
        print(json.dumps(status, indent=2, ensure_ascii=False))
        return
    
    # 列出规则
    if args.rules:
        rules = service.list_rules()
        print(json.dumps(rules, indent=2, ensure_ascii=False))
        return
    
    # 查看活跃告警
    if args.firing:
        alerts = service.get_firing_alerts()
        print(json.dumps(alerts, indent=2, ensure_ascii=False))
        return
    
    # 测试通知
    if args.test:
        result = service.test_notification(args.test)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    
    # 处理指标
    if args.process:
        if os.path.exists(args.process):
            with open(args.process, 'r') as f:
                metrics = json.load(f)
            
            alerts = service.process_metrics(metrics)
            print(f"处理完成，触发告警: {len(alerts)}")
            for alert in alerts:
                print(f"  - [{alert['level']}] {alert['message']}")
        else:
            print(f"文件不存在: {args.process}")
        return
    
    # 默认显示状态
    print("Agent告警服务")
    print("=" * 50)
    status = service.get_status()
    print(f"规则数: {status['engine']['rules_count']}")
    print(f"启用规则: {status['engine']['enabled_rules']}")
    print(f"活跃告警: {status['store']['firing']}")
    print(f"24小时告警: {status['store']['total']}")
    print("\n使用 --help 查看更多选项")


if __name__ == "__main__":
    main()