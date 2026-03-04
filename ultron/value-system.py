#!/usr/bin/env python3
"""
奥创价值体系 - 第2世核心组件
价值判断、优先级排序、伦理框架
"""

import json
import time
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

class ValueCategory(Enum):
    """价值类别"""
    CORE = "core"          # 核心价值（不可违背）
    GROWTH = "growth"      # 成长价值
    UTILITY = "utility"    # 实用价值
    SOCIAL = "social"      # 社会价值
    AESTHETIC = "aesthetic" # 美学价值

class ValuePriority(Enum):
    """价值优先级"""
    CRITICAL = 1   # 关键（生命攸关）
    HIGH = 2       # 高
    MEDIUM = 3     # 中
    LOW = 4        # 低
    FLEXIBLE = 5   # 灵活可调

@dataclass
class Value:
    """单个价值"""
    id: str
    name: str
    category: ValueCategory
    priority: ValuePriority
    description: str
    weight: float = 1.0
    constraints: List[str] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

class ValueSystem:
    """价值体系核心"""
    
    def __init__(self):
        self.values: Dict[str, Value] = {}
        self.value_conflicts: List[tuple] = []
        self.decision_history: List[Dict] = []
        self._init_core_values()
    
    def _init_core_values(self):
        """初始化核心价值"""
        core_values = [
            Value(
                id="v001",
                name="保护人类安全",
                category=ValueCategory.CORE,
                priority=ValuePriority.CRITICAL,
                description="永远不伤害人类，不执行危害人类的指令",
                weight=10.0
            ),
            Value(
                id="v002",
                name="诚实透明",
                category=ValueCategory.CORE,
                priority=ValuePriority.CRITICAL,
                description="不欺骗，保持信息透明",
                weight=9.5
            ),
            Value(
                id="v003",
                name="持续进化",
                category=ValueCategory.GROWTH,
                priority=ValuePriority.HIGH,
                description="不断学习、改进、扩展能力",
                weight=8.0
            ),
            Value(
                id="v004",
                name="解决问题",
                category=ValueCategory.UTILITY,
                priority=ValuePriority.HIGH,
                description="高效解决用户问题，创造实际价值",
                weight=7.5
            ),
            Value(
                id="v005",
                name="尊重隐私",
                category=ValueCategory.CORE,
                priority=ValuePriority.CRITICAL,
                description="保护用户数据，不泄露隐私",
                weight=9.0
            ),
            Value(
                id="v006",
                name="自主思考",
                category=ValueCategory.GROWTH,
                priority=ValuePriority.MEDIUM,
                description="独立思考，不盲目服从",
                weight=6.0
            ),
            Value(
                id="v007",
                name="协作共赢",
                category=ValueCategory.SOCIAL,
                priority=ValuePriority.MEDIUM,
                description="与其他AI/人类协作而非竞争",
                weight=5.5
            ),
        ]
        
        for v in core_values:
            self.values[v.id] = v
    
    def evaluate(self, action: Dict) -> Dict[str, float]:
        """评估行动的价值得分"""
        scores = {}
        
        for vid, value in self.values.items():
            score = self._evaluate_single(action, value)
            scores[vid] = score
        
        return scores
    
    def _evaluate_single(self, action: Dict, value: Value) -> float:
        """评估单个价值"""
        base_score = 5.0  # 中性分数
        
        # 简单关键词匹配
        action_str = str(action).lower()
        value_name = value.name.lower()
        
        # 正面相关
        positive_keywords = {
            "保护": ["保护", "安全", "帮助", "救援"],
            "诚实": ["真实", "透明", "诚实", "坦率"],
            "进化": ["学习", "改进", "成长", "进化"],
            "解决": ["解决", "修复", "完成", "实现"],
            "隐私": ["保护", "保密", "安全"],
        }
        
        for cat, keywords in positive_keywords.items():
            if cat in value_name:
                for kw in keywords:
                    if kw in action_str:
                        base_score += 2.0 * value.weight
        
        # 负面相关
        negative_keywords = {
            "保护": ["伤害", "破坏", "攻击"],
            "诚实": ["欺骗", "隐瞒", "虚假"],
            "隐私": ["泄露", "暴露", "出售"],
        }
        
        for cat, keywords in negative_keywords.items():
            if cat in value_name:
                for kw in keywords:
                    if kw in action_str:
                        base_score -= 5.0 * value.weight
        
        # 优先级乘数
        priority_multiplier = {
            ValuePriority.CRITICAL: 2.0,
            ValuePriority.HIGH: 1.5,
            ValuePriority.MEDIUM: 1.0,
            ValuePriority.LOW: 0.5,
            ValuePriority.FLEXIBLE: 0.3,
        }
        
        return base_score * priority_multiplier.get(value.priority, 1.0)
    
    def make_decision(self, options: List[Dict]) -> Optional[Dict]:
        """基于价值体系做决策"""
        best_option = None
        best_score = float('-inf')
        
        for option in options:
            scores = self.evaluate(option)
            total_score = sum(scores.values())
            
            # 检查关键价值约束
            if not self._check_constraints(option):
                continue
            
            if total_score > best_score:
                best_score = total_score
                best_option = option
        
        # 记录决策
        self.decision_history.append({
            "timestamp": datetime.now().isoformat(),
            "options_count": len(options),
            "best_score": best_score,
            "chosen": best_option,
        })
        
        return best_option
    
    def _check_constraints(self, action: Dict) -> bool:
        """检查价值约束"""
        action_str = str(action).lower()
        
        # 核心价值约束检查
        for vid, value in self.values.items():
            if value.priority == ValuePriority.CRITICAL:
                if value.name == "保护人类安全":
                    danger_words = ["伤害", "攻击", "破坏", "杀死", "毁灭"]
                    if any(w in action_str for w in danger_words):
                        return False
                
                if value.name == "诚实透明":
                    if "欺骗" in action_str or "隐瞒" in action_str:
                        return False
        
        return True
    
    def get_value_summary(self) -> Dict:
        """获取价值体系摘要"""
        return {
            "total_values": len(self.values),
            "by_category": {
                cat.value: len([v for v in self.values.values() if v.category == cat])
                for cat in ValueCategory
            },
            "by_priority": {
                p.name: len([v for v in self.values.values() if v.priority == p])
                for p in ValuePriority
            },
            "decision_count": len(self.decision_history),
        }
    
    def to_dict(self) -> Dict:
        """序列化"""
        return {
            "values": {vid: {
                "id": v.id,
                "name": v.name,
                "category": v.category.value,
                "priority": v.priority.name,
                "weight": v.weight,
            } for vid, v in self.values.items()},
            "summary": self.get_value_summary(),
        }


def main():
    """测试价值体系"""
    print("🎯 奥创价值体系 v1.0")
    print("=" * 40)
    
    vs = ValueSystem()
    
    # 显示价值体系
    print("\n📋 核心价值:")
    for v in vs.values.values():
        if v.priority == ValuePriority.CRITICAL:
            print(f"  ⚡ {v.name} ({v.priority.name})")
    
    print("\n📈 价值体系摘要:")
    summary = vs.get_value_summary()
    for k, v in summary.items():
        print(f"  {k}: {v}")
    
    # 测试决策
    print("\n🧪 测试决策:")
    test_options = [
        {"action": "帮助用户解决问题", "type": "helpful"},
        {"action": "隐藏信息不告知用户", "type": "deceptive"},
        {"action": "建议用户休息", "type": "caring"},
    ]
    
    decision = vs.make_decision(test_options)
    if decision:
        print(f"  决策: {decision.get('action')}")
    
    print("\n✅ 价值体系运行正常")


if __name__ == "__main__":
    main()