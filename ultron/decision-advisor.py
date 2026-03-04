#!/usr/bin/env python3
"""
智能决策建议系统
基于数据分析生成决策建议，支持自动化执行与效果评估

功能：
- 基于数据的建议生成
- 自动化决策执行
- 决策效果评估
"""

import json
import time
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DecisionType(Enum):
    """决策类型"""
    RESOURCE_ALLOCATION = "resource_allocation"
    SCALING = "scaling"
    MAINTENANCE = "maintenance"
    OPTIMIZATION = "optimization"
    ALERT_RESPONSE = "alert_response"
    WORKFLOW_SCHEDULING = "workflow_scheduling"

class Priority(Enum):
    """优先级"""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class DecisionStatus(Enum):
    """决策状态"""
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"

@dataclass
class DecisionContext:
    """决策上下文"""
    timestamp: str
    source: str
    data: Dict[str, Any]
    constraints: Dict[str, Any] = field(default_factory=dict)
    history: List[Dict] = field(default_factory=list)

@dataclass
class Decision:
    """决策"""
    id: str
    type: DecisionType
    title: str
    description: str
    priority: Priority
    context: DecisionContext
    options: List[Dict[str, Any]]
    recommended_option: int
    confidence: float
    status: DecisionStatus = DecisionStatus.PENDING
    executed_result: Optional[Dict] = None
    created_at: str = ""
    executed_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

@dataclass
class DecisionEffect:
    """决策效果评估"""
    decision_id: str
    metrics_before: Dict[str, float]
    metrics_after: Dict[str, float]
    improvement: Dict[str, float]
    score: float
    evaluated_at: str
    notes: str = ""

class DecisionAdvisor:
    """智能决策建议系统"""
    
    def __init__(self, data_dir: str = "/root/.openclaw/workspace/ultron-self"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        self.decisions_file = self.data_dir / "decisions.json"
        self.effects_file = self.data_dir / "decision_effects.jsonl"
        self.context_file = self.data_dir / "decision_context.json"
        
        self.decisions: List[Decision] = []
        self.effects: List[DecisionEffect] = []
        
        self.load_decisions()
        self.load_effects()
        
    def load_decisions(self):
        """加载历史决策"""
        if self.decisions_file.exists():
            with open(self.decisions_file, 'r') as f:
                data = json.load(f)
                for d in data:
                    d['type'] = DecisionType(d['type'])
                    d['priority'] = Priority(d['priority'])
                    d['status'] = DecisionStatus(d['status'])
                    self.decisions.append(Decision(**d))
        logger.info(f"加载了 {len(self.decisions)} 条历史决策")
    
    def save_decisions(self):
        """保存决策"""
        data = []
        for d in self.decisions:
            data.append({
                'id': d.id,
                'type': d.type.value,
                'title': d.title,
                'description': d.description,
                'priority': d.priority.value,
                'status': d.status.value,
                'created_at': d.created_at,
                'executed_at': d.executed_at,
                'completed_at': d.completed_at,
                'context': {
                    'timestamp': d.context.timestamp,
                    'source': d.context.source,
                    'data': d.context.data,
                    'constraints': d.context.constraints,
                    'history': d.context.history
                },
                'options': d.options,
                'recommended_option': d.recommended_option,
                'confidence': d.confidence,
                'executed_result': d.executed_result
            })
        with open(self.decisions_file, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_effects(self):
        """加载效果评估"""
        if self.effects_file.exists():
            with open(self.effects_file, 'r') as f:
                for line in f:
                    self.effects.append(DecisionEffect(**json.loads(line)))
        logger.info(f"加载了 {len(self.effects)} 条效果评估")
    
    def analyze_context(self, context_data: Dict[str, Any]) -> Dict[str, Any]:
        """分析上下文，生成决策建议"""
        analysis = {
            'trends': [],
            'anomalies': [],
            'patterns': [],
            'recommendations': []
        }
        
        # 分析趋势
        if 'metrics' in context_data:
            metrics = context_data['metrics']
            
            # CPU趋势分析
            if 'cpu' in metrics:
                cpu = metrics['cpu']
                if cpu > 80:
                    analysis['trends'].append({
                        'metric': 'cpu',
                        'direction': 'increasing',
                        'severity': 'high',
                        'value': cpu
                    })
                    analysis['recommendations'].append({
                        'type': DecisionType.SCALING,
                        'action': '增加计算资源',
                        'reason': f'CPU使用率{cpu}%过高'
                    })
                elif cpu < 20:
                    analysis['trends'].append({
                        'metric': 'cpu',
                        'direction': 'decreasing',
                        'severity': 'low',
                        'value': cpu
                    })
                    analysis['recommendations'].append({
                        'type': DecisionType.OPTIMIZATION,
                        'action': '降低资源配置',
                        'reason': f'CPU使用率{cpu}%过低，可节约成本'
                    })
            
            # 内存趋势分析
            if 'memory' in metrics:
                mem = metrics['memory']
                if mem > 85:
                    analysis['anomalies'].append({
                        'metric': 'memory',
                        'value': mem,
                        'severity': 'critical'
                    })
                    analysis['recommendations'].append({
                        'type': DecisionType.RESOURCE_ALLOCATION,
                        'action': '增加内存资源',
                        'reason': f'内存使用率{mem}%过高'
                    })
            
            # 磁盘趋势分析
            if 'disk' in metrics:
                disk = metrics['disk']
                if disk > 90:
                    analysis['anomalies'].append({
                        'metric': 'disk',
                        'value': disk,
                        'severity': 'critical'
                    })
                    analysis['recommendations'].append({
                        'type': DecisionType.MAINTENANCE,
                        'action': '清理磁盘空间',
                        'reason': f'磁盘使用率{disk}%过高'
                    })
        
        # 分析工作流
        if 'workflows' in context_data:
            wf_data = context_data['workflows']
            failed = wf_data.get('failed_count', 0)
            total = wf_data.get('total_count', 1)
            if total > 0:
                failure_rate = failed / total
                if failure_rate > 0.1:
                    analysis['patterns'].append({
                        'pattern': 'high_failure_rate',
                        'value': failure_rate,
                        'severity': 'medium'
                    })
                    analysis['recommendations'].append({
                        'type': DecisionType.OPTIMIZATION,
                        'action': '优化工作流',
                        'reason': f'工作流失败率{failure_rate:.1%}过高'
                    })
        
        # 分析告警
        if 'alerts' in context_data:
            alerts = context_data['alerts']
            critical_count = alerts.get('critical', 0)
            if critical_count > 0:
                analysis['anomalies'].append({
                    'pattern': 'critical_alerts',
                    'count': critical_count,
                    'severity': 'critical'
                })
                analysis['recommendations'].append({
                    'type': DecisionType.ALERT_RESPONSE,
                    'action': '处理关键告警',
                    'reason': f'{critical_count}个关键告警待处理'
                })
        
        return analysis
    
    def generate_decision(
        self,
        decision_type: DecisionType,
        title: str,
        description: str,
        context_data: Dict[str, Any],
        options: List[Dict[str, Any]]
    ) -> Decision:
        """生成决策"""
        # 分析上下文
        analysis = self.analyze_context(context_data)
        
        # 确定优先级
        priority = Priority.MEDIUM
        severity = 0
        for rec in analysis.get('recommendations', []):
            if rec['type'] == DecisionType.ALERT_RESPONSE:
                severity = max(severity, 1)
            elif rec['type'] == DecisionType.SCALING:
                severity = max(severity, 2)
        
        if severity == 1:
            priority = Priority.CRITICAL
        elif severity == 2:
            priority = Priority.HIGH
        
        # 计算置信度
        confidence = 0.7
        if len(options) > 0:
            confidence = min(0.95, 0.7 + len(options) * 0.05)
        if analysis.get('anomalies'):
            confidence = min(0.95, confidence + 0.1)
        
        # 选择推荐选项
        recommended = 0
        if analysis.get('recommendations'):
            # 根据分析结果选择最佳选项
            for i, opt in enumerate(options):
                for rec in analysis['recommendations']:
                    if rec.get('action') in str(opt.get('action', '')):
                        recommended = i
                        break
        
        # 创建上下文
        context = DecisionContext(
            timestamp=datetime.now().isoformat(),
            source="decision_advisor",
            data=context_data,
            history=[]
        )
        
        decision = Decision(
            id=f"decision_{int(time.time()*1000)}",
            type=decision_type,
            title=title,
            description=description,
            priority=priority,
            context=context,
            options=options,
            recommended_option=recommended,
            confidence=confidence
        )
        
        self.decisions.append(decision)
        self.save_decisions()
        
        logger.info(f"生成决策: {decision.id} - {title}, 置信度: {confidence:.2f}")
        return decision
    
    def approve_decision(self, decision_id: str) -> bool:
        """批准决策"""
        for d in self.decisions:
            if d.id == decision_id:
                d.status = DecisionStatus.APPROVED
                self.save_decisions()
                logger.info(f"批准决策: {decision_id}")
                return True
        return False
    
    def reject_decision(self, decision_id: str, reason: str = "") -> bool:
        """拒绝决策"""
        for d in self.decisions:
            if d.id == decision_id:
                d.status = DecisionStatus.REJECTED
                self.save_decisions()
                logger.info(f"拒绝决策: {decision_id}, 原因: {reason}")
                return True
        return False
    
    def execute_decision(self, decision_id: str) -> Dict[str, Any]:
        """执行决策"""
        for d in self.decisions:
            if d.id == decision_id:
                d.status = DecisionStatus.EXECUTING
                d.executed_at = datetime.now().isoformat()
                self.save_decisions()
                
                # 执行推荐选项
                option = d.options[d.recommended_option]
                result = {
                    'decision_id': decision_id,
                    'executed_option': option,
                    'success': True,
                    'timestamp': datetime.now().isoformat(),
                    'actions_taken': []
                }
                
                # 模拟执行（实际可根据option类型执行不同操作）
                action = option.get('action', '')
                if '增加' in action or '扩展' in action:
                    result['actions_taken'].append(f"执行资源扩展: {action}")
                elif '减少' in action or '缩减' in action:
                    result['actions_taken'].append(f"执行资源缩减: {action}")
                elif '清理' in action:
                    result['actions_taken'].append(f"执行清理操作: {action}")
                elif '优化' in action:
                    result['actions_taken'].append(f"执行优化: {action}")
                else:
                    result['actions_taken'].append(f"执行操作: {action}")
                
                # 模拟结果
                result['success'] = random.random() > 0.1  # 90%成功率
                
                d.executed_result = result
                d.status = DecisionStatus.COMPLETED if result['success'] else DecisionStatus.FAILED
                d.completed_at = datetime.now().isoformat()
                self.save_decisions()
                
                logger.info(f"执行决策: {decision_id}, 状态: {d.status.value}")
                return result
        
        return {'success': False, 'error': '决策不存在'}
    
    def evaluate_effect(
        self,
        decision_id: str,
        metrics_before: Dict[str, float],
        metrics_after: Dict[str, float]
    ) -> DecisionEffect:
        """评估决策效果"""
        improvement = {}
        for key in metrics_before:
            if key in metrics_after:
                before = metrics_before[key]
                after = metrics_after[key]
                if before > 0:
                    imp = (after - before) / before
                    improvement[key] = imp
        
        # 计算综合评分
        score = 0.5  # 基础分
        for key, imp in improvement.items():
            # 对于资源使用，越低越好
            if key in ['cpu', 'memory', 'disk']:
                if imp < 0:
                    score += abs(imp) * 0.3  # 降低资源使用，加分
                else:
                    score -= imp * 0.2  # 增加资源使用，减分
            # 对于性能指标，越高越好
            elif key in ['throughput', 'performance']:
                if imp > 0:
                    score += imp * 0.3
                else:
                    score -= abs(imp) * 0.2
        
        score = max(0, min(1, score))  # 限制在0-1之间
        
        effect = DecisionEffect(
            decision_id=decision_id,
            metrics_before=metrics_before,
            metrics_after=metrics_after,
            improvement=improvement,
            score=score,
            evaluated_at=datetime.now().isoformat(),
            notes=f"决策效果评分: {score:.2f}"
        )
        
        self.effects.append(effect)
        
        # 追加到效果文件
        with open(self.effects_file, 'a') as f:
            f.write(json.dumps({
                'decision_id': effect.decision_id,
                'metrics_before': effect.metrics_before,
                'metrics_after': effect.metrics_after,
                'improvement': effect.improvement,
                'score': effect.score,
                'evaluated_at': effect.evaluated_at,
                'notes': effect.notes
            }, ensure_ascii=False) + '\n')
        
        logger.info(f"评估决策效果: {decision_id}, 评分: {score:.2f}")
        return effect
    
    def get_recent_decisions(self, limit: int = 10) -> List[Dict]:
        """获取最近决策"""
        sorted_decisions = sorted(self.decisions, 
                                  key=lambda x: x.created_at, 
                                  reverse=True)
        result = []
        for d in sorted_decisions[:limit]:
            result.append({
                'id': d.id,
                'type': d.type.value,
                'title': d.title,
                'priority': d.priority.value,
                'status': d.status.value,
                'confidence': d.confidence,
                'created_at': d.created_at
            })
        return result
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取决策统计"""
        total = len(self.decisions)
        if total == 0:
            return {
                'total': 0,
                'by_status': {},
                'by_type': {},
                'by_priority': {},
                'average_confidence': 0,
                'average_effect_score': 0
            }
        
        by_status = {}
        by_type = {}
        by_priority = {}
        
        for d in self.decisions:
            status = d.status.value
            by_status[status] = by_status.get(status, 0) + 1
            
            dtype = d.type.value
            by_type[dtype] = by_type.get(dtype, 0) + 1
            
            priority = d.priority.name
            by_priority[priority] = by_priority.get(priority, 0) + 1
        
        avg_confidence = sum(d.confidence for d in self.decisions) / total
        avg_effect = sum(e.score for e in self.effects) / len(self.effects) if self.effects else 0
        
        return {
            'total': total,
            'by_status': by_status,
            'by_type': by_type,
            'by_priority': by_priority,
            'average_confidence': avg_confidence,
            'average_effect_score': avg_effect
        }

def main():
    """主函数 - 测试决策建议系统"""
    advisor = DecisionAdvisor()
    
    # 模拟上下文数据
    context_data = {
        'metrics': {
            'cpu': 85,
            'memory': 75,
            'disk': 45
        },
        'workflows': {
            'total_count': 100,
            'failed_count': 5
        },
        'alerts': {
            'critical': 2,
            'warning': 5
        }
    }
    
    # 生成决策
    decision = advisor.generate_decision(
        decision_type=DecisionType.SCALING,
        title="CPU使用率过高建议",
        description="检测到CPU使用率达到85%，建议扩展计算资源",
        context_data=context_data,
        options=[
            {'action': '增加CPU核心数', 'cost': 'high', 'impact': 'immediate'},
            {'action': '启用负载均衡', 'cost': 'medium', 'impact': 'gradual'},
            {'action': '优化现有资源', 'cost': 'low', 'impact': 'gradual'}
        ]
    )
    
    print(f"\n生成决策: {decision.title}")
    print(f"推荐选项: {decision.options[decision.recommended_option]}")
    print(f"置信度: {decision.confidence:.2f}")
    print(f"优先级: {decision.priority.name}")
    
    # 批准并执行
    advisor.approve_decision(decision.id)
    result = advisor.execute_decision(decision.id)
    print(f"\n执行结果: {result}")
    
    # 评估效果
    metrics_before = {'cpu': 85, 'memory': 75}
    metrics_after = {'cpu': 45, 'memory': 60}
    effect = advisor.evaluate_effect(decision.id, metrics_before, metrics_after)
    print(f"\n效果评分: {effect.score:.2f}")
    print(f"改进: {effect.improvement}")
    
    # 统计
    stats = advisor.get_statistics()
    print(f"\n统计: {json.dumps(stats, indent=2)}")

if __name__ == "__main__":
    main()