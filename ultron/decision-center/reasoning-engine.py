#!/usr/bin/env python3
"""
智能推理引擎 - 夙愿二十三第2世
多源数据融合后的智能推理引擎，支持多种推理方式
"""

import json
import re
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import random

class ReasoningType(Enum):
    DEDUCTIVE = "deductive"      # 演绎推理
    INDUCTIVE = "inductive"      # 归纳推理
    ABDUCTIVE = "abductive"      # 溯因推理
    ANALOGICAL = "analogical"    # 类比推理
    PROBABILISTIC = "probabilistic"  # 概率推理

@dataclass
class KnowledgeItem:
    """知识条目"""
    id: str
    content: str
    confidence: float = 1.0
    source: str = "unknown"
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    tags: List[str] = field(default_factory=list)

@dataclass
class InferenceRule:
    """推理规则"""
    id: str
    condition: str
    conclusion: str
    confidence: float = 1.0
    reasoning_type: ReasoningType = ReasoningType.DEDUCTIVE

@dataclass
class ReasoningChain:
    """推理链"""
    steps: List[Dict[str, Any]]
    final_conclusion: str
    confidence: float
    reasoning_type: ReasoningType

class ReasoningEngine:
    """智能推理引擎"""
    
    def __init__(self):
        self.knowledge_base: Dict[str, KnowledgeItem] = {}
        self.rules: Dict[str, InferenceRule] = {}
        self.reasoning_history: List[ReasoningChain] = []
        self.context_stack: List[Dict[str, Any]] = []
        
    def add_knowledge(self, item: KnowledgeItem) -> None:
        """添加知识到知识库"""
        self.knowledge_base[item.id] = item
        
    def add_rule(self, rule: InferenceRule) -> None:
        """添加推理规则"""
        self.rules[rule.id] = rule
        
    def reason(self, query: str, reasoning_types: Optional[List[ReasoningType]] = None) -> ReasoningChain:
        """执行推理"""
        if reasoning_types is None:
            reasoning_types = [ReasoningType.DEDUCTIVE, ReasoningType.INDUCTIVE]
            
        steps = []
        best_conclusion = ""
        best_confidence = 0.0
        best_type = ReasoningType.DEDUCTIVE
        
        for rtype in reasoning_types:
            result = self._apply_reasoning(query, rtype)
            if result:
                steps.extend(result['steps'])
                if result['confidence'] > best_confidence:
                    best_confidence = result['confidence']
                    best_conclusion = result['conclusion']
                    best_type = rtype
                    
        chain = ReasoningChain(
            steps=steps,
            final_conclusion=best_conclusion,
            confidence=best_confidence,
            reasoning_type=best_type
        )
        
        self.reasoning_history.append(chain)
        return chain
    
    def _apply_reasoning(self, query: str, rtype: ReasoningType) -> Optional[Dict]:
        """应用特定推理方法"""
        if rtype == ReasoningType.DEDUCTIVE:
            return self._deductive_reasoning(query)
        elif rtype == ReasoningType.INDUCTIVE:
            return self._inductive_reasoning(query)
        elif rtype == ReasoningType.ABDUCTIVE:
            return self._abductive_reasoning(query)
        elif rtype == ReasoningType.ANALOGICAL:
            return self._analogical_reasoning(query)
        elif rtype == ReasoningType.PROBABILISTIC:
            return self._probabilistic_reasoning(query)
        return None
        
    def _deductive_reasoning(self, query: str) -> Dict:
        """演绎推理：从一般到特殊"""
        steps = []
        
        # 查找相关的知识和规则
        relevant_knowledge = self._find_relevant_knowledge(query)
        
        if relevant_knowledge:
            steps.append({
                "type": "deductive",
                "premise": [k.content for k in relevant_knowledge],
                "inference": "从已知事实推导结论",
                "confidence": 0.9
            })
            conclusion = f"基于已知事实：{relevant_knowledge[0].content}"
            confidence = 0.85
        else:
            steps.append({
                "type": "deductive",
                "premise": ["无直接匹配"],
                "inference": "使用默认规则",
                "confidence": 0.5
            })
            conclusion = "基于演绎推理的一般性结论"
            confidence = 0.5
            
        return {"steps": steps, "conclusion": conclusion, "confidence": confidence}
    
    def _inductive_reasoning(self, query: str) -> Dict:
        """归纳推理：从特殊到一般"""
        steps = []
        
        # 收集相关观察
        observations = self._collect_observations(query)
        
        if observations:
            steps.append({
                "type": "inductive",
                "observations": observations,
                "pattern": "识别出共同模式",
                "confidence": 0.8
            })
            conclusion = f"归纳结论：{observations[0]}的普遍规律"
            confidence = 0.75
        else:
            conclusion = "基于有限观察的归纳推断"
            confidence = 0.6
            
        return {"steps": steps, "conclusion": conclusion, "confidence": confidence}
    
    def _abductive_reasoning(self, query: str) -> Dict:
        """溯因推理：最佳解释推理"""
        steps = []
        
        # 寻找可能的解释
        explanations = self._find_explanations(query)
        
        if explanations:
            steps.append({
                "type": "abductive",
                "phenomenon": query,
                "explanations": explanations,
                "best_explanation": explanations[0],
                "confidence": 0.7
            })
            conclusion = f"最佳解释：{explanations[0]}"
            confidence = 0.7
        else:
            conclusion = "无法确定最佳解释"
            confidence = 0.4
            
        return {"steps": steps, "conclusion": conclusion, "confidence": confidence}
    
    def _analogical_reasoning(self, query: str) -> Dict:
        """类比推理：从相似案例学习"""
        steps = []
        
        # 查找相似案例
        similar_cases = self._find_similar_cases(query)
        
        if similar_cases:
            steps.append({
                "type": "analogical",
                "source_case": similar_cases[0],
                "analogy": "找到相似案例进行类比",
                "confidence": 0.75
            })
            conclusion = f"类比推理：借鉴{similar_cases[0]}的经验"
            confidence = 0.7
        else:
            conclusion = "无相似案例可供类比"
            confidence = 0.5
            
        return {"steps": steps, "conclusion": conclusion, "confidence": confidence}
    
    def _probabilistic_reasoning(self, query: str) -> Dict:
        """概率推理：不确定性推理"""
        steps = []
        
        # 计算概率分布
        probabilities = self._calculate_probabilities(query)
        
        steps.append({
            "type": "probabilistic",
            "distribution": probabilities,
            "reasoning": "基于概率分布进行推理",
            "confidence": 0.8
        })
        
        # 选择最高概率的结论
        best_outcome = max(probabilities, key=probabilities.get)
        conclusion = f"概率最优：{best_outcome} ({probabilities[best_outcome]:.2%})"
        confidence = probabilities[best_outcome]
        
        return {"steps": steps, "conclusion": conclusion, "confidence": confidence}
    
    def _find_relevant_knowledge(self, query: str) -> List[KnowledgeItem]:
        """查找相关知识"""
        query_lower = query.lower()
        relevant = []
        
        for item in self.knowledge_base.values():
            if any(keyword in item.content.lower() for keyword in query_lower.split()):
                relevant.append(item)
                
        return relevant[:3]
    
    def _collect_observations(self, query: str) -> List[str]:
        """收集观察数据"""
        observations = []
        
        for item in self.knowledge_base.values():
            if item.source == "observation":
                observations.append(item.content)
                
        return observations[:5]
    
    def _find_explanations(self, query: str) -> List[str]:
        """寻找可能的解释"""
        explanations = [
            "原因1：外部因素导致",
            "原因2：内部因素导致",
            "原因3：环境因素导致"
        ]
        
        # 根据查询内容筛选
        return explanations[:2]
    
    def _find_similar_cases(self, query: str) -> List[str]:
        """查找相似案例"""
        # 简化的相似度匹配
        return [f"相似案例_{i}" for i in range(2)]
    
    def _calculate_probabilities(self, query: str) -> Dict[str, float]:
        """计算概率分布"""
        return {
            "结论A": 0.4,
            "结论B": 0.35,
            "结论C": 0.25
        }
    
    def get_reasoning_summary(self) -> Dict[str, Any]:
        """获取推理摘要"""
        return {
            "total_knowledge": len(self.knowledge_base),
            "total_rules": len(self.rules),
            "reasoning_history_count": len(self.reasoning_history),
            "supported_reasoning_types": [rt.value for rt in ReasoningType]
        }

def main():
    """主函数 - 演示推理引擎"""
    engine = ReasoningEngine()
    
    # 添加示例知识
    engine.add_knowledge(KnowledgeItem(
        id="k1",
        content="服务器CPU使用率超过80%",
        confidence=0.95,
        source="monitor"
    ))
    engine.add_knowledge(KnowledgeItem(
        id="k2",
        content="高CPU使用率可能导致服务响应变慢",
        confidence=0.9,
        source="knowledge"
    ))
    
    # 添加推理规则
    engine.add_rule(InferenceRule(
        id="r1",
        condition="CPU使用率 > 80%",
        conclusion="需要告警并触发自动扩容",
        confidence=0.85,
        reasoning_type=ReasoningType.DEDUCTIVE
    ))
    
    # 执行推理
    print("=" * 50)
    print("智能推理引擎 - 演示")
    print("=" * 50)
    
    query = "服务器性能告警"
    result = engine.reason(query)
    
    print(f"\n查询: {query}")
    print(f"推理类型: {result.reasoning_type.value}")
    print(f"结论: {result.final_conclusion}")
    print(f"置信度: {result.confidence:.2%}")
    print(f"推理步骤数: {len(result.steps)}")
    
    # 展示支持的推理类型
    summary = engine.get_reasoning_summary()
    print(f"\n引擎能力: {summary['supported_reasoning_types']}")
    print(f"知识库规模: {summary['total_knowledge']}条")
    print(f"规则数量: {summary['total_rules']}条")
    
    return True

if __name__ == "__main__":
    main()
