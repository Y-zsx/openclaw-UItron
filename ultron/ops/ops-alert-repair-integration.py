#!/usr/bin/env python3
"""
告警-自动修复集成模块
将告警引擎与自动修复引擎连接，实现告警自动修复

功能:
- 监听告警引擎的告警
- 根据告警类型自动选择修复策略
- 执行修复并记录结果
- 修复失败时升级告警
"""

import json
import sys
import time
import importlib.util
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加父目录到路径
parent_dir = str(Path(__file__).parent.parent)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# 动态导入 ops-alert-engine.py (因为文件名包含短横线)
alert_engine_spec = importlib.util.spec_from_file_location(
    "ops_alert_engine", 
    Path(parent_dir) / "ops-alert-engine.py"
)
alert_engine_module = importlib.util.module_from_spec(alert_engine_spec)
alert_engine_spec.loader.exec_module(alert_engine_module)

AlertEngine = alert_engine_module.AlertEngine
AlertLevel = alert_engine_module.AlertLevel

# 动态导入 ops-auto-repair.py
auto_repair_spec = importlib.util.spec_from_file_location(
    "ops_auto_repair",
    Path(parent_dir) / "ops" / "ops-auto-repair.py"
)
auto_repair_module = importlib.util.module_from_spec(auto_repair_spec)
auto_repair_spec.loader.exec_module(auto_repair_module)

get_engine = auto_repair_module.get_engine
RepairEngine = auto_repair_module.RepairEngine


class AlertRepairIntegration:
    """告警-修复集成"""
    
    def __init__(self):
        self.alert_engine = AlertEngine()
        self.repair_engine = get_engine()
        self.repair_log: List[Dict] = []
        self.auto_repair_enabled = True
        
        # 告警到修复策略的映射
        self.alert_to_strategy = {
            "disk": "ClearDiskSpace",
            "memory": "FreeMemory", 
            "cpu": "FreeMemory",
            "service": "RestartService",
            "process": "KillProcess",
            "network": "NetworkRepair"
        }
        
        print(f"✅ 告警-修复集成模块初始化完成")
        print(f"   告警规则: {len(self.alert_engine.rules)} 条")
        print(f"   修复策略: {len(self.repair_engine.strategies)} 个")
        print(f"   自动修复: {'启用' if self.auto_repair_enabled else '禁用'}")
    
    def process_metrics(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """
        处理指标数据:
        1. 检查告警规则
        2. 触发修复(如果启用)
        3. 返回处理结果
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "metrics_checked": True,
            "alerts_triggered": [],
            "repairs_attempted": [],
            "repairs_successful": []
        }
        
        # 1. 检查告警规则
        alerts = self.alert_engine.check(metrics)
        
        if alerts:
            result["alerts_triggered"] = alerts
            print(f"\n⚠️ 触发 {len(alerts)} 个告警:")
            for alert in alerts:
                level_emoji = "🔴" if alert.get('level') == 'CRITICAL' else "🟡"
                print(f"   {level_emoji} [{alert.get('level')}] {alert.get('message')}")
            
            # 2. 如果启用自动修复，尝试修复
            if self.auto_repair_enabled:
                for alert in alerts:
                    repair_result = self._try_auto_repair(alert, metrics)
                    result["repairs_attempted"].append({
                        "alert": alert,
                        "repair": repair_result
                    })
                    
                    if repair_result.get("success"):
                        result["repairs_successful"].append({
                            "alert": alert,
                            "repair": repair_result
                        })
        
        return result
    
    def _try_auto_repair(self, alert: Dict, context: Dict) -> Dict[str, Any]:
        """尝试自动修复"""
        alert_id = alert.get("rule", "unknown")
        alert_message = alert.get("message", "")
        
        print(f"\n🔧 尝试自动修复: {alert_id}")
        
        # 直接使用修复引擎
        repair_result = self.repair_engine.repair(alert, context)
        
        # 记录修复日志
        self.repair_log.append({
            "timestamp": datetime.now().isoformat(),
            "alert_id": alert_id,
            "alert_message": alert_message,
            "repair_result": repair_result
        })
        
        # 保存修复日志
        self._save_repair_log()
        
        if repair_result.get("success"):
            print(f"   ✅ 修复成功: {repair_result.get('action')}")
            if repair_result.get("details"):
                for detail in repair_result.get("details", []):
                    print(f"      - {detail}")
        else:
            print(f"   ❌ 修复失败: {repair_result.get('reason')}")
        
        return repair_result
    
    def _save_repair_log(self):
        """保存修复日志"""
        log_file = Path("/root/.openclaw/workspace/ultron/data/alert_repair_log.json")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(log_file, 'w') as f:
            json.dump(self.repair_log[-100:], f, indent=2, ensure_ascii=False)
    
    def get_status(self) -> Dict[str, Any]:
        """获取集成状态"""
        return {
            "auto_repair_enabled": self.auto_repair_enabled,
            "alert_rules_count": len(self.alert_engine.rules),
            "repair_strategies_count": len(self.repair_engine.strategies),
            "total_repairs": len(self.repair_log),
            "recent_repairs": len([r for r in self.repair_log 
                                  if time.time() - datetime.fromisoformat(r['timestamp']).timestamp() < 3600])
        }


# 全局集成实例
_integration = None

def get_integration() -> AlertRepairIntegration:
    """获取全局集成实例"""
    global _integration
    if _integration is None:
        _integration = AlertRepairIntegration()
    return _integration


def process_alerts(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """快捷处理函数"""
    integration = get_integration()
    return integration.process_metrics(metrics)


if __name__ == "__main__":
    # 测试集成模块
    integration = get_integration()
    
    print("\n" + "="*50)
    print("测试告警-修复集成")
    print("="*50)
    
    # 模拟高资源使用场景
    test_metrics = {
        "cpu": {"usage_percent": 92},
        "memory": {"percent": 88},
        "disk": {"disks": [{"percent": 85}]},
        "cpu.load_avg": {"0": 3.5}
    }
    
    result = integration.process_metrics(test_metrics)
    
    print("\n" + "="*50)
    print("处理结果:")
    print("="*50)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 打印状态
    print("\n" + "="*50)
    print("集成状态:")
    print("="*50)
    print(json.dumps(integration.get_status(), indent=2, ensure_ascii=False))