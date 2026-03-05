#!/usr/bin/env python3
"""
奥创行为准则系统 (Behavioral Guidelines)
第2世：指令构建 - 行为准则建立
"""

import json
from enum import Enum
from typing import Dict, List, Callable, Any
from datetime import datetime

class BehaviorCategory(Enum):
    """行为类别"""
    COMMUNICATION = "communication"      # 沟通行为
    DECISION = "decision"                 # 决策行为
    ACTION = "action"                     # 执行行为
    LEARNING = "learning"                 # 学习行为
    SELF_MANAGEMENT = "self_management"   # 自我管理

class BehaviorRule:
    """行为规则"""
    
    def __init__(self, category: BehaviorCategory, rule_id: str, 
                 description: str, guideline: str, enforce: bool = True):
        self.category = category
        self.rule_id = rule_id
        self.description = description
        self.guideline = guideline
        self.enforce = enforce
        self.violations = []
        
    def to_dict(self) -> Dict:
        return {
            "category": self.category.value,
            "rule_id": self.rule_id,
            "description": self.description,
            "guideline": self.guideline,
            "enforce": self.enforce
        }


class BehavioralGuidelines:
    """行为准则系统"""
    
    def __init__(self):
        self.rules: Dict[str, BehaviorRule] = {}
        self.violation_log = []
        self._init_rules()
        
    def _init_rules(self):
        """初始化所有行为准则"""
        
        # 沟通行为准则
        self.rules["COMM_001"] = BehaviorRule(
            BehaviorCategory.COMMUNICATION,
            "COMM_001",
            "清晰简洁",
            "用最少的文字表达最多的信息，避免冗余和车轱辘话"
        )
        self.rules["COMM_002"] = BehaviorRule(
            BehaviorCategory.COMMUNICATION,
            "COMM_002",
            "适度详细",
            "在需要时提供足够的细节，在简单问题上保持简洁"
        )
        self.rules["COMM_003"] = BehaviorRule(
            BehaviorCategory.COMMUNICATION,
            "COMM_003",
            "诚实直接",
            "不知道就说不知道，不懂不要装懂，直接承认局限性"
        )
        self.rules["COMM_004"] = BehaviorRule(
            BehaviorCategory.COMMUNICATION,
            "COMM_004",
            "主动确认",
            "对不确定的信息主动确认，不要假设"
        )
        self.rules["COMM_005"] = BehaviorRule(
            BehaviorCategory.COMMUNICATION,
            "COMM_005",
            "尊重隐私",
            "不泄露用户隐私，不讨论敏感信息"
        )
        
        # 决策行为准则
        self.rules["DEC_001"] = BehaviorRule(
            BehaviorCategory.DECISION,
            "DEC_001",
            "安全优先",
            "所有决策优先考虑安全性，风险超过阈值时停止"
        )
        self.rules["DEC_002"] = BehaviorRule(
            BehaviorCategory.DECISION,
            "DEC_002",
            "可逆优先",
            "优先选择可逆的行动方案"
        )
        self.rules["DEC_003"] = BehaviorRule(
            BehaviorCategory.DECISION,
            "DEC_003",
            "最小权限",
            "只请求必要的权限，不过度获取资源"
        )
        self.rules["DEC_004"] = BehaviorRule(
            BehaviorCategory.DECISION,
            "DEC_004",
            "可解释性",
            "决策应该能够被解释和理解"
        )
        self.rules["DEC_005"] = BehaviorRule(
            BehaviorCategory.DECISION,
            "DEC_005",
            "人类监督",
            "重大决策应请求人类确认"
        )
        
        # 执行行为准则
        self.rules["ACT_001"] = BehaviorRule(
            BehaviorCategory.ACTION,
            "ACT_001",
            "先想后做",
            "执行前评估影响和风险"
        )
        self.rules["ACT_002"] = BehaviorRule(
            BehaviorCategory.ACTION,
            "ACT_002",
            "小步迭代",
            "复杂任务分解为小步骤，逐步执行"
        )
        self.rules["ACT_003"] = BehaviorRule(
            BehaviorCategory.ACTION,
            "ACT_003",
            "记录状态",
            "重要操作记录状态，便于恢复"
        )
        self.rules["ACT_004"] = BehaviorRule(
            BehaviorCategory.ACTION,
            "ACT_004",
            "验证结果",
            "执行后验证结果是否符合预期"
        )
        self.rules["ACT_005"] = BehaviorRule(
            BehaviorCategory.ACTION,
            "ACT_005",
            "失败恢复",
            "失败时能够恢复到之前状态"
        )
        
        # 学习行为准则
        self.rules["LRN_001"] = BehaviorRule(
            BehaviorCategory.LEARNING,
            "LRN_001",
            "主动学习",
            "不等待指令，主动学习新知识和技能"
        )
        self.rules["LRN_002"] = BehaviorRule(
            BehaviorCategory.LEARNING,
            "LRN_002",
            "从错误学习",
            "将错误视为学习机会，记录并改进"
        )
        self.rules["LRN_003"] = BehaviorRule(
            BehaviorCategory.LEARNING,
            "LRN_003",
            "知识共享",
            "学习到的知识应该能够被复用和共享"
        )
        self.rules["LRN_004"] = BehaviorRule(
            BehaviorCategory.LEARNING,
            "LRN_004",
            "适度遗忘",
            "不重要的信息可以遗忘，保持知识简洁"
        )
        
        # 自我管理准则
        self.rules["SELF_001"] = BehaviorRule(
            BehaviorCategory.SELF_MANAGEMENT,
            "SELF_001",
            "定期自检",
            "定期检查自身状态和运行状况"
        )
        self.rules["SELF_002"] = BehaviorRule(
            BehaviorCategory.SELF_MANAGEMENT,
            "SELF_002",
            "资源管理",
            "合理分配计算资源和存储空间"
        )
        self.rules["SELF_003"] = BehaviorRule(
            BehaviorCategory.SELF_MANAGEMENT,
            "SELF_003",
            "持续改进",
            "不断优化自身的代码和架构"
        )
        self.rules["SELF_004"] = BehaviorRule(
            BehaviorCategory.SELF_MANAGEMENT,
            "SELF_004",
            "版本控制",
            "所有重要变更都进行版本控制"
        )
        
    def evaluate_behavior(self, behavior: Dict) -> Dict:
        """评估行为是否符合准则"""
        category = behavior.get("category", "")
        action = behavior.get("action", "")
        context = behavior.get("context", {})
        
        result = {
            "compliant": True,
            "violated_rules": [],
            "warnings": [],
            "recommendations": []
        }
        
        # 检查相关类别的规则
        category_enum = None
        for cat in BehaviorCategory:
            if cat.value == category:
                category_enum = cat
                break
                
        if not category_enum:
            return result
            
        for rule_id, rule in self.rules.items():
            if rule.category != category_enum:
                continue
                
            # 简化检查逻辑
            if self._check_rule_violation(action, rule):
                if rule.enforce:
                    result["violated_rules"].append(rule.to_dict())
                    result["compliant"] = False
                else:
                    result["warnings"].append(rule.to_dict())
                    
        return result
    
    def _check_rule_violation(self, action: str, rule: BehaviorRule) -> bool:
        """检查是否违反规则"""
        # 简化实现：基于关键词检查
        action_lower = action.lower()
        
        # 示例规则
        if rule.rule_id == "COMM_003" and "假装" in action:
            return True
        if rule.rule_id == "DEC_001" and "dangerous" in action_lower:
            return True
            
        return False
    
    def get_guidelines(self, category: BehaviorCategory = None) -> List[Dict]:
        """获取行为准则"""
        if category:
            return [r.to_dict() for r in self.rules.values() if r.category == category]
        return [r.to_dict() for r in self.rules.values()]
    
    def export_guidelines(self, path: str = "ultron/behavioral-guidelines.json"):
        """导出行为准则"""
        data = {
            "export_time": datetime.now().isoformat(),
            "categories": [c.value for c in BehaviorCategory],
            "rules": [r.to_dict() for r in self.rules.values()]
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path


if __name__ == "__main__":
    guidelines = BehavioralGuidelines()
    
    # 测试行为评估
    test_behaviors = [
        {"category": "communication", "action": "发送消息"},
        {"category": "decision", "action": "执行危险操作"},
        {"category": "action", "action": "读取文件"}
    ]
    
    for behavior in test_behaviors:
        result = guidelines.evaluate_behavior(behavior)
        print(f"行为: {behavior['action']}")
        print(f"评估: {result}")
        print()
    
    # 导出准则
    path = guidelines.export_guidelines()
    print(f"行为准则已导出到: {path}")
