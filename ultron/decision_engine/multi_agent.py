"""
决策引擎多智能体协作模块
Multi-Agent Collaboration for Decision Engine
"""
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Any, Optional, Set
from enum import Enum
from dataclasses import dataclass, field
import threading

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """智能体角色"""
    COORDINATOR = "coordinator"       # 协调者 - 统筹全局
    ANALYZER = "analyzer"             # 分析者 - 分析数据
    EXECUTOR = "executor"             # 执行者 - 执行决策
    MONITOR = "monitor"               # 监督者 - 监控风险
    VALIDATOR = "validator"           # 验证者 - 验证决策


class AgentStatus(Enum):
    """智能体状态"""
    IDLE = "idle"
    THINKING = "thinking"
    EXECUTING = "executing"
    WAITING = "waiting"
    BLOCKED = "blocked"
    ERROR = "error"


@dataclass
class Agent:
    """智能体"""
    id: str
    name: str
    role: AgentRole
    capabilities: List[str] = field(default_factory=list)
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    last_active: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "status": self.status.value,
            "current_task": self.current_task,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_active": self.last_active.isoformat()
        }


@dataclass
class Task:
    """协作任务"""
    id: str
    type: str
    description: str
    priority: int = 2
    status: str = "pending"
    assignees: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    context: Dict = field(default_factory=dict)
    results: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type,
            "description": self.description,
            "priority": self.priority,
            "status": self.status,
            "assignees": self.assignees,
            "dependencies": self.dependencies,
            "context": self.context,
            "results": self.results,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }


@dataclass
class Message:
    """智能体消息"""
    id: str
    sender: str
    receiver: str
    type: str
    content: Dict
    timestamp: datetime = field(default_factory=datetime.now)
    read: bool = False


class AgentRegistry:
    """智能体注册表"""
    
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self._lock = threading.Lock()
        
    def register(self, agent: Agent) -> bool:
        with self._lock:
            if agent.id in self.agents:
                logger.warning(f"智能体已存在: {agent.id}")
                return False
            self.agents[agent.id] = agent
            logger.info(f"智能体注册: {agent.name} ({agent.role.value})")
            return True
            
    def unregister(self, agent_id: str) -> bool:
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                logger.info(f"智能体注销: {agent_id}")
                return True
            return False
            
    def get(self, agent_id: str) -> Optional[Agent]:
        return self.agents.get(agent_id)
    
    def get_by_role(self, role: AgentRole) -> List[Agent]:
        return [a for a in self.agents.values() if a.role == role]
    
    def get_all(self) -> List[Agent]:
        return list(self.agents.values())
    
    def get_available(self, capability: str = None) -> List[Agent]:
        """获取可用的智能体"""
        available = [a for a in self.agents.values() 
                     if a.status in [AgentStatus.IDLE, AgentStatus.WAITING]]
        if capability:
            available = [a for a in available if capability in a.capabilities]
        return available


class MessageBus:
    """智能体消息总线"""
    
    def __init__(self):
        self.messages: List[Message] = []
        self.subscribers: Dict[str, List[str]] = {}  # event_type -> [agent_ids]
        self._lock = threading.Lock()
        
    def send(self, message: Message):
        with self._lock:
            self.messages.append(message)
            logger.debug(f"消息发送: {message.sender} -> {message.receiver}")
            
    def receive(self, agent_id: str) -> List[Message]:
        with self._lock:
            messages = [m for m in self.messages 
                       if m.receiver == agent_id and not m.read]
            for m in messages:
                m.read = True
            return messages
            
    def subscribe(self, agent_id: str, event_type: str):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        if agent_id not in self.subscribers[event_type]:
            self.subscribers[event_type].append(agent_id)
            
    def broadcast(self, sender: str, event_type: str, content: Dict):
        message = Message(
            id=f"msg_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            sender=sender,
            receiver="*",
            type=event_type,
            content=content
        )
        self.send(message)


class CollaborationEngine:
    """
    多智能体协作引擎
    核心功能:
    - 智能体管理
    - 任务分配
    - 协作决策
    - 冲突解决
    """
    
    def __init__(self, config: Dict = None):
        self.config = config or {}
        self.registry = AgentRegistry()
        self.message_bus = MessageBus()
        self.tasks: Dict[str, Task] = {}
        self.decision_collaborations: Dict[str, Dict] = {}
        self._lock = threading.Lock()
        
        # 协作策略
        self.strategy = {
            "consensus_threshold": self.config.get("consensus_threshold", 0.7),
            "max_round": self.config.get("max_round", 3),
            "timeout": self.config.get("timeout", 30)
        }
        
        # 注册默认智能体
        self._register_default_agents()
        
        logger.info("多智能体协作引擎初始化完成")
        
    def _register_default_agents(self):
        """注册默认智能体"""
        default_agents = [
            Agent(
                id="coordinator_01",
                name="协调者小队长",
                role=AgentRole.COORDINATOR,
                capabilities=["coordinate", "delegate", "resolve_conflict", "final_decision"]
            ),
            Agent(
                id="analyzer_01", 
                name="分析者大卫",
                role=AgentRole.ANALYZER,
                capabilities=["analyze", "predict", "evaluate_risk", "suggest"]
            ),
            Agent(
                id="executor_01",
                name="执行者闪电",
                role=AgentRole.EXECUTOR,
                capabilities=["execute", "schedule", "retry", "rollback"]
            ),
            Agent(
                id="monitor_01",
                name="监督者守卫",
                role=AgentRole.MONITOR,
                capabilities=["monitor", "alert", "checkpoint", "validate"]
            ),
            Agent(
                id="validator_01",
                name="验证者严谨",
                role=AgentRole.VALIDATOR,
                capabilities=["validate", "verify", "audit", "approve"]
            )
        ]
        
        for agent in default_agents:
            self.registry.register(agent)
            
    def create_task(self, task_type: str, description: str, 
                    context: Dict = None, priority: int = 2) -> Task:
        """创建协作任务"""
        task = Task(
            id=f"task_{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
            type=task_type,
            description=description,
            priority=priority,
            context=context or {}
        )
        
        with self._lock:
            self.tasks[task.id] = task
            
        logger.info(f"创建任务: {task.id} ({task_type})")
        return task
    
    def assign_task(self, task_id: str, agent_ids: List[str]) -> bool:
        """分配任务给智能体"""
        with self._lock:
            if task_id not in self.tasks:
                return False
            task = self.tasks[task_id]
            task.assignees = agent_ids
            
            for agent_id in agent_ids:
                agent = self.registry.get(agent_id)
                if agent:
                    agent.current_task = task_id
                    agent.status = AgentStatus.THINKING
                    
        logger.info(f"任务分配: {task_id} -> {agent_ids}")
        return True
    
    def collaborative_decide(self, context: Dict) -> Dict:
        """
        协作决策 - 多智能体共同决策
        流程: 分析 -> 评估 -> 验证 -> 协调 -> 执行
        """
        decision_id = f"collab_{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        
        # 1. 分析阶段
        analyzer = self.registry.get_by_role(AgentRole.ANALYZER)[0]
        if analyzer:
            analyzer.status = AgentStatus.THINKING
            analysis_result = self._agent_analyze(analyzer, context)
            
        # 2. 评估阶段
        monitor = self.registry.get_by_role(AgentRole.MONITOR)[0]
        if monitor:
            monitor.status = AgentStatus.THINKING
            risk_result = self._agent_evaluate(monitor, context, analysis_result)
            
        # 3. 验证阶段
        validator = self.registry.get_by_role(AgentRole.VALIDATOR)[0]
        if validator:
            validator.status = AgentStatus.THINKING
            validation_result = self._agent_validate(validator, context, analysis_result, risk_result)
            
        # 4. 协调阶段
        coordinator = self.registry.get_by_role(AgentRole.COORDINATOR)[0]
        if coordinator:
            coordinator.status = AgentStatus.THINKING
            final_decision = self._agent_coordinate(coordinator, {
                "analysis": analysis_result,
                "risk": risk_result,
                "validation": validation_result
            })
            
        # 5. 执行阶段
        executor = self.registry.get_by_role(AgentRole.EXECUTOR)[0]
        if executor:
            executor.status = AgentStatus.EXECUTING
            execution_result = self._agent_execute(executor, final_decision)
            
        # 保存协作结果
        collaboration_result = {
            "decision_id": decision_id,
            "analysis": analysis_result,
            "risk_assessment": risk_result,
            "validation": validation_result,
            "final_decision": final_decision,
            "execution": execution_result,
            "timestamp": datetime.now().isoformat()
        }
        
        with self._lock:
            self.decision_collaborations[decision_id] = collaboration_result
            
        # 重置智能体状态
        self._reset_agent_status()
        
        logger.info(f"协作决策完成: {decision_id}")
        return collaboration_result
    
    def _agent_analyze(self, agent: Agent, context: Dict) -> Dict:
        """分析智能体处理"""
        logger.info(f"分析者 {agent.name} 处理中...")
        agent.last_active = datetime.now()
        
        # 分析决策上下文
        trigger = context.get("trigger", "unknown")
        data = context.get("data", {})
        
        analysis = {
            "trigger": trigger,
            "data_summary": str(data)[:200],
            "patterns_identified": self._identify_patterns(context),
            "recommendations": self._generate_recommendations(context),
            "confidence": 0.85
        }
        
        agent.status = AgentStatus.IDLE
        return analysis
    
    def _agent_evaluate(self, agent: Agent, context: Dict, analysis: Dict) -> Dict:
        """监控智能体风险评估"""
        logger.info(f"监督者 {agent.name} 评估风险...")
        agent.last_active = datetime.now()
        
        # 风险评估
        risk_factors = []
        risk_score = 0
        
        # 基于触发器类型
        trigger_risk = {
            "error": 7,
            "timeout": 5,
            "health_check": 1,
            "metric_threshold": 4
        }
        trigger = context.get("trigger", "unknown")
        risk_score += trigger_risk.get(trigger, 3)
        
        if risk_score >= 6:
            risk_factors.append("高风险操作")
        if risk_score >= 4:
            risk_factors.append("需要人工确认")
            
        risk_assessment = {
            "risk_score": risk_score,
            "risk_level": "high" if risk_score >= 6 else "medium" if risk_score >= 4 else "low",
            "risk_factors": risk_factors,
            "mitigation_suggestions": self._suggest_mitigations(risk_score)
        }
        
        agent.status = AgentStatus.IDLE
        return risk_assessment
    
    def _agent_validate(self, agent: Agent, context: Dict, 
                        analysis: Dict, risk: Dict) -> Dict:
        """验证智能体验证决策"""
        logger.info(f"验证者 {agent.name} 验证中...")
        agent.last_active = datetime.now()
        
        # 验证决策可行性
        is_valid = True
        validation_issues = []
        
        # 检查风险等级
        if risk.get("risk_score", 0) >= 8:
            is_valid = False
            validation_issues.append("风险等级过高")
            
        # 检查分析置信度
        if analysis.get("confidence", 0) < 0.5:
            is_valid = False
            validation_issues.append("分析置信度不足")
            
        validation = {
            "is_valid": is_valid,
            "issues": validation_issues,
            "approved": is_valid and risk.get("risk_score", 0) < 7,
            "notes": "自动验证通过" if is_valid else "需要人工审核"
        }
        
        agent.status = AgentStatus.IDLE
        return validation
    
    def _agent_coordinate(self, agent: Agent, inputs: Dict) -> Dict:
        """协调智能体做出最终决策"""
        logger.info(f"协调者 {agent.name} 做出最终决策...")
        agent.last_active = datetime.now()
        
        analysis = inputs.get("analysis", {})
        risk = inputs.get("risk", {})
        validation = inputs.get("validation", {})
        
        # 综合决策
        if validation.get("is_valid", False):
            decision = {
                "action": "approve",
                "summary": "协作决策通过",
                "details": {
                    "analysis_confidence": analysis.get("confidence", 0),
                    "risk_level": risk.get("risk_level", "unknown"),
                    "validated": validation.get("approved", False)
                }
            }
        else:
            decision = {
                "action": "reject",
                "summary": "协作决策驳回",
                "details": {
                    "reason": validation.get("issues", ["未知原因"]),
                    "risk_level": risk.get("risk_level", "unknown")
                }
            }
            
        agent.status = AgentStatus.IDLE
        return decision
    
    def _agent_execute(self, agent: Agent, decision: Dict) -> Dict:
        """执行智能体执行决策"""
        logger.info(f"执行者 {agent.name} 执行决策...")
        agent.last_active = datetime.now()
        
        action = decision.get("action", "none")
        
        execution = {
            "status": "executed",
            "action_taken": action,
            "timestamp": datetime.now().isoformat(),
            "success": True
        }
        
        agent.status = AgentStatus.IDLE
        return execution
    
    def _identify_patterns(self, context: Dict) -> List[str]:
        """识别模式"""
        patterns = []
        trigger = context.get("trigger", "")
        
        if "error" in trigger:
            patterns.append("错误模式")
        if "timeout" in trigger:
            patterns.append("超时模式")
        if "health" in trigger:
            patterns.append("健康检查模式")
            
        return patterns
    
    def _generate_recommendations(self, context: Dict) -> List[str]:
        """生成建议"""
        trigger = context.get("trigger", "unknown")
        
        recommendations = {
            "error": ["检查服务状态", "查看日志详情", "考虑重启服务"],
            "timeout": ["增加超时时间", "检查网络状况", "优化查询性能"],
            "health_check": ["继续监控", "记录基准指标"],
            "metric_threshold": ["调整阈值", "分析趋势"]
        }
        
        return recommendations.get(trigger, ["常规处理"])
    
    def _suggest_mitigations(self, risk_score: int) -> List[str]:
        """建议缓解措施"""
        if risk_score >= 7:
            return ["需要人工审批", "降低风险后重试", "分步执行"]
        elif risk_score >= 4:
            return ["增加监控频率", "记录执行日志"]
        return []
    
    def _reset_agent_status(self):
        """重置所有智能体状态"""
        for agent in self.registry.get_all():
            if agent.status != AgentStatus.IDLE:
                agent.status = AgentStatus.IDLE
                
    def get_collaboration_history(self, limit: int = 10) -> List[Dict]:
        """获取协作历史"""
        histories = list(self.decision_collaborations.values())
        return histories[-limit:]
    
    def get_agent_status(self) -> List[Dict]:
        """获取所有智能体状态"""
        return [agent.to_dict() for agent in self.registry.get_all()]
    
    def get_task_status(self, task_id: str = None) -> Dict:
        """获取任务状态"""
        with self._lock:
            if task_id:
                task = self.tasks.get(task_id)
                return task.to_dict() if task else {}
            return {tid: t.to_dict() for tid, t in self.tasks.items()}


# 全局协作引擎实例
_collab_engine = None

def get_collaboration_engine(config: Dict = None) -> CollaborationEngine:
    """获取协作引擎单例"""
    global _collab_engine
    if _collab_engine is None:
        _collab_engine = CollaborationEngine(config)
    return _collab_engine