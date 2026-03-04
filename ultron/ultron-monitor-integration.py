#!/usr/bin/env python3
"""
奥创监控系统与决策引擎集成
功能：将决策引擎嵌入监控系统，实现自动化决策
"""

import json
import os
import sys
import subprocess
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

# ===== 决策引擎核心 (简化版) =====

class DecisionType(Enum):
    RULE_BASED = "rule_based"
    DATA_DRIVEN = "data_driven"
    HYBRID = "hybrid"

class DecisionLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"

class DecisionResult(Enum):
    EXECUTE = "execute"
    DEFER = "defer"
    REJECT = "reject"
    ESCALATE = "escalate"

@dataclass
class Decision:
    id: str
    timestamp: str
    context: Dict[str, Any]
    decision_type: str
    level: str
    rule_applied: Optional[str]
    result: str
    reason: str
    confidence: float
    action_taken: Optional[str]

class SimpleDecisionEngine:
    """简化决策引擎"""
    
    def __init__(self):
        self.decisions = []
        self.log_path = "/root/.openclaw/workspace/ultron/logs/decisions.json"
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        
    def decide(self, context: Dict[str, Any]) -> Decision:
        """做出决策"""
        decision_id = str(uuid.uuid4())[:8]
        timestamp = datetime.now().isoformat()
        
        # 规则检查
        rule_applied = None
        action = None
        level = DecisionLevel.LOW
        
        # 磁盘检查
        if context.get('disk_usage', 0) > 90:
            rule_applied = "disk_space_check"
            action = f"磁盘使用率 {context.get('disk_usage')}%，建议清理"
            level = DecisionLevel.MEDIUM
        # 内存检查
        elif context.get('memory_usage', 0) > 85:
            rule_applied = "memory_check"
            action = f"内存使用率 {context.get('memory_usage')}%，考虑释放"
            level = DecisionLevel.LOW
        # 服务检查
        elif context.get('service_status') == 'down':
            rule_applied = "service_down"
            action = f"服务 {context.get('service_name', 'unknown')} 宕机，尝试重启"
            level = DecisionLevel.HIGH
        else:
            action = "系统运行正常"
        
        # 确定结果
        if level == DecisionLevel.HIGH:
            result = DecisionResult.ESCALATE
            reason = "高风险决策，需要升级"
        elif level == DecisionLevel.MEDIUM:
            result = DecisionResult.DEFER
            reason = "中风险决策，建议延迟执行"
        else:
            result = DecisionResult.EXECUTE
            reason = "低风险决策，可以执行"
        
        decision = Decision(
            id=decision_id,
            timestamp=timestamp,
            context=context,
            decision_type=DecisionType.HYBRID.value,
            level=level.value,
            rule_applied=rule_applied,
            result=result.value,
            reason=reason,
            confidence=0.85,
            action_taken=action
        )
        
        self.decisions.append(decision)
        return decision


class MonitorDecision集成:
    """监控决策集成系统"""
    
    def __init__(self):
        self.engine = SimpleDecisionEngine()
        self.log_path = "/root/.openclaw/workspace/ultron/logs/monitor_decisions.json"
        Path(self.log_path).parent.mkdir(parents=True, exist_ok=True)
        
    def collect_metrics(self) -> dict:
        """收集系统指标"""
        metrics = {}
        
        # CPU/内存
        try:
            result = subprocess.run(
                ["free", "-m"], capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                mem = lines[1].split()
                metrics['memory_total'] = int(mem[1])
                metrics['memory_used'] = int(mem[2])
                metrics['memory_usage'] = round(metrics['memory_used'] / metrics['memory_total'] * 100, 1)
        except:
            metrics['memory_usage'] = 0
        
        # 磁盘
        try:
            result = subprocess.run(
                ["df", "-h", "/"], capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                metrics['disk_usage'] = int(parts[4].replace('%', ''))
        except:
            metrics['disk_usage'] = 0
        
        # 负载
        try:
            result = subprocess.run(
                ["cat", "/proc/loadavg"], capture_output=True, text=True, timeout=5
            )
            load = result.stdout.strip().split()[:3]
            metrics['load_avg'] = [float(x) for x in load]
        except:
            metrics['load_avg'] = [0, 0, 0]
            
        # 服务状态
        metrics['service_status'] = 'up'
        
        return metrics
    
    def monitor_and_decide(self) -> dict:
        """监控并决策"""
        # 收集指标
        metrics = self.collect_metrics()
        
        # 决策
        decision = self.engine.decide(metrics)
        
        # 返回结果
        result = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "decision": {
                "id": decision.id,
                "result": decision.result,
                "action": decision.action_taken,
                "reason": decision.reason,
                "level": decision.level,
                "confidence": decision.confidence
            }
        }
        
        # 记录到日志
        self._log_result(result)
        
        return result
    
    def _log_result(self, result: dict):
        """记录监控决策结果"""
        log_file = self.log_path
        
        # 读取现有日志
        logs = []
        if os.path.exists(log_file):
            try:
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        logs.append(result)
        
        # 保留最近100条
        logs = logs[-100:]
        
        with open(log_file, 'w') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    
    def run_auto_monitoring(self, interval: int = 60):
        """自动监控循环"""
        print(f"启动自动监控决策系统 (间隔{interval}秒)...")
        
        import time
        while True:
            try:
                result = self.monitor_and_decide()
                print(f"[{result['timestamp']}] 决策: {result['decision']['result']} - {result['decision']['action']}")
                
                # 高风险决策立即通知
                if result['decision']['level'] == 'high':
                    print(f"⚠️ 高风险告警: {result['decision']['action']}")
                    
            except Exception as e:
                print(f"监控错误: {e}")
            
            time.sleep(interval)


if __name__ == "__main__":
    integration = MonitorDecision集成()
    
    if len(sys.argv) > 1 and sys.argv[1] == "auto":
        # 自动监控模式
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 60
        integration.run_auto_monitoring(interval)
    else:
        # 单次决策
        result = integration.monitor_and_decide()
        print(json.dumps(result, indent=2, ensure_ascii=False))