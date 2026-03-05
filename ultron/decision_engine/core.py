"""
决策引擎核心模块
Decision Engine Core - 智能决策与自主行动系统基础
"""
import json
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)


class DecisionPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class DecisionStatus(Enum):
    PENDING = "pending"
    EVALUATING = "evaluating"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"


class DecisionContext:
    """决策上下文 - 包含决策所需的所有信息"""
    
    def __init__(self, trigger: str, data: Dict[str, Any], source: str = "system"):
        self.id = f"ctx_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.trigger = trigger  # 触发器类型
        self.data = data        # 决策数据
        self.source = source    # 触发来源
        self.timestamp = datetime.now()
        self.metadata = {}
        
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "trigger": self.trigger,
            "data": self.data,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata
        }


class Decision:
    """决策对象"""
    
    def __init__(self, context: DecisionContext, action: str, params: Dict = None):
        self.id = f"dec_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.context = context
        self.action = action          # 执行动作
        self.params = params or {}    # 动作参数
        self.priority = DecisionPriority.NORMAL
        self.status = DecisionStatus.PENDING
        self.risk_level = 0           # 风险等级 0-10
        self.conditions = []          # 执行条件
        self.created_at = datetime.now()
        self.evaluated_at = None
        self.executed_at = None
        self.result = None
        self.error = None
        
    def approve(self) -> bool:
        """审批决策"""
        # 自动批准低风险决策
        if self.risk_level <= 3:
            self.status = DecisionStatus.APPROVED
            return True
        # 高风险需要额外验证
        return False
    
    def reject(self, reason: str):
        """拒绝决策"""
        self.status = DecisionStatus.REJECTED
        self.error = reason
        
    def execute(self):
        """标记为执行中"""
        self.status = DecisionStatus.EXECUTING
        self.executed_at = datetime.now()
        
    def complete(self, result: Any = None):
        """完成决策"""
        self.status = DecisionStatus.COMPLETED
        self.result = result
        
    def fail(self, error: str):
        """决策失败"""
        self.status = DecisionStatus.FAILED
        self.error = error
        
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "action": self.action,
            "params": self.params,
            "priority": self.priority.name,
            "status": self.status.value,
            "risk_level": self.risk_level,
            "created_at": self.created_at.isoformat(),
            "result": self.result,
            "error": self.error
        }


class DecisionEngine:
    """
    智能决策引擎
    核心功能:
    - 接收决策请求
    - 评估风险
    - 应用规则
    - 生成决策
    - 执行行动
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.rules = []
        self.action_handlers: Dict[str, Callable] = {}
        self.decisions: List[Decision] = []
        self.history: List[Decision] = []
        self.max_history = self.config.get("max_history", 1000)
        
        # 决策统计
        self.stats = {
            "total": 0,
            "approved": 0,
            "rejected": 0,
            "completed": 0,
            "failed": 0
        }
        
        # 注册默认动作处理器
        self._register_default_handlers()
        
        logger.info("决策引擎初始化完成")
        
    def _register_default_handlers(self):
        """注册默认动作处理器"""
        self.action_handlers = {
            "notify": self._handle_notify,
            "execute": self._handle_execute,
            "alert": self._handle_alert,
            "log": self._handle_log,
            "escalate": self._handle_escalate
        }
        
    def register_rule(self, rule: 'Rule'):
        """注册决策规则"""
        self.rules.append(rule)
        logger.info(f"注册规则: {rule.name}")
        
    def register_action(self, action_name: str, handler: Callable):
        """注册动作处理器"""
        self.action_handlers[action_name] = handler
        logger.info(f"注册动作处理器: {action_name}")
        
    def evaluate(self, context: DecisionContext) -> List[Decision]:
        """评估决策上下文，生成候选决策"""
        decisions = []
        self.stats["total"] += 1
        
        # 应用所有规则
        for rule in self.rules:
            if rule.matches(context):
                decision = rule.create_decision(context)
                if decision:
                    # 风险评估
                    decision.risk_level = self._assess_risk(decision)
                    decisions.append(decision)
                    
        # 如果没有匹配的规则，创建默认决策
        if not decisions:
            default = self._create_default_decision(context)
            if default:
                decisions.append(default)
                
        logger.info(f"评估完成: {len(decisions)} 个候选决策")
        return decisions
    
    def _assess_risk(self, decision: Decision) -> int:
        """评估决策风险等级 (0-10)"""
        risk = 0
        
        # 基于优先级
        priority_risk = {
            DecisionPriority.LOW: 1,
            DecisionPriority.NORMAL: 3,
            DecisionPriority.HIGH: 6,
            DecisionPriority.CRITICAL: 9
        }
        risk += priority_risk.get(decision.priority, 3)
        
        # 基于动作类型
        dangerous_actions = ["execute", "delete", "stop", "kill"]
        if decision.action in dangerous_actions:
            risk += 3
            
        return min(risk, 10)
    
    def _create_default_decision(self, context: DecisionContext) -> Optional[Decision]:
        """创建默认决策"""
        # 根据触发器类型决定默认动作
        default_actions = {
            "health_check": "log",
            "error": "alert",
            "timeout": "notify",
            "metric_threshold": "escalate"
        }
        
        action = default_actions.get(context.trigger, "log")
        return Decision(context, action, {"auto": True})
    
    def approve(self, decision: Decision) -> bool:
        """审批决策"""
        if decision.approve():
            self.stats["approved"] += 1
            logger.info(f"决策已批准: {decision.id}")
            return True
        self.stats["rejected"] += 1
        logger.warning(f"决策被拒绝: {decision.id}")
        return False
    
    def execute(self, decision: Decision) -> Any:
        """执行决策"""
        decision.execute()
        
        handler = self.action_handlers.get(decision.action)
        if not handler:
            decision.fail(f"未知动作: {decision.action}")
            self.stats["failed"] += 1
            return None
            
        try:
            result = handler(decision)
            decision.complete(result)
            self.stats["completed"] += 1
            logger.info(f"决策执行完成: {decision.id}")
            return result
        except Exception as e:
            decision.fail(str(e))
            self.stats["failed"] += 1
            logger.error(f"决策执行失败: {decision.id} - {e}")
            return None
    
    def process(self, context: DecisionContext, auto_approve: bool = True) -> Decision:
        """完整处理流程: 评估 -> 审批 -> 执行"""
        # 评估
        decisions = self.evaluate(context)
        if not decisions:
            return None
            
        decision = decisions[0]
        
        # 审批
        if auto_approve or self.approve(decision):
            result = self.execute(decision)
            decision.result = result
            
        # 记录
        self.decisions.append(decision)
        self.history.append(decision)
        
        # 清理历史
        if len(self.history) > self.max_history:
            self.history = self.history[-self.max_history:]
            
        return decision
    
    def get_stats(self) -> Dict:
        """获取决策统计"""
        total = self.stats.get("total", 0)
        completed = self.stats.get("completed", 0)
        return {
            **self.stats,
            "total_decisions": total,
            "success_rate": completed / total if total > 0 else 0,
            "pending": len([d for d in self.decisions if d.status == DecisionStatus.PENDING]),
            "rules_count": len(self.rules),
            "handlers_count": len(self.action_handlers)
        }
    
    def get_decisions(self, status: DecisionStatus = None, limit: int = 100) -> List[Dict]:
        """获取决策列表"""
        decisions = self.decisions
        if status:
            decisions = [d for d in decisions if d.status == status]
        return [d.to_dict() for d in decisions[-limit:]]
    
    def get_recent_decisions(self, limit: int = 10) -> List[Decision]:
        """获取最近的决策"""
        return self.decisions[-limit:] if self.decisions else []
    
    # 默认动作处理器
    def _handle_notify(self, decision: Decision) -> Any:
        logger.info(f"通知动作: {decision.action} - {decision.params}")
        return {"status": "notified", "action": decision.action}
    
    def _handle_execute(self, decision: Decision) -> Any:
        logger.info(f"执行动作: {decision.action} - {decision.params}")
        return {"status": "executed", "action": decision.action}
    
    def _handle_alert(self, decision: Decision) -> Any:
        logger.info(f"告警动作: {decision.action} - {decision.params}")
        return {"status": "alerted", "action": decision.action}
    
    def _handle_log(self, decision: Decision) -> Any:
        logger.info(f"日志动作: {decision.action} - {decision.params}")
        return {"status": "logged", "action": decision.action}
    
    def _handle_escalate(self, decision: Decision) -> Any:
        logger.info(f"升级动作: {decision.action} - {decision.params}")
        return {"status": "escalated", "action": decision.action}