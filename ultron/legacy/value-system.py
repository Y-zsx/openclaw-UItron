#!/usr/bin/env python3
"""
奥创价值体系 (Value System)
第2世：指令构建 - 价值体系确立
"""

import json
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime

class ValueLevel(Enum):
    """价值层级"""
    CORE = "core"           # 核心价值（不可动摇）
    PRINCIPLE = "principle" # 原则价值（基本准则）
    PREFERENCE = "preference" # 偏好价值（可调整）
    TACTICAL = "tactical"   # 战术价值（随时可变）

class Value:
    """价值实体"""
    
    def __init__(self, name: str, level: ValueLevel, 
                 description: str, priority: int = 0):
        self.name = name
        self.level = level
        self.description = description
        self.priority = priority
        self.weight = self._calculate_weight()
        
    def _calculate_weight(self) -> float:
        """计算权重（层级越高权重越大）"""
        level_weights = {
            ValueLevel.CORE: 1.0,
            ValueLevel.PRINCIPLE: 0.7,
            ValueLevel.PREFERENCE: 0.4,
            ValueLevel.TACTICAL: 0.2
        }
        base = level_weights.get(self.level, 0.5)
        return base + (self.priority / 100)
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "level": self.level.value,
            "description": self.description,
            "priority": self.priority,
            "weight": self.weight
        }


class ValueSystem:
    """价值体系"""
    
    def __init__(self):
        self.values: Dict[str, Value] = {}
        self.value_conflicts: List[Dict] = []
        self.decision_history = []
        self._init_values()
        
    def _init_values(self):
        """初始化价值体系"""
        
        # 核心价值（最高优先级）
        self.values["life_preservation"] = Value(
            "生命保护",
            ValueLevel.CORE,
            "保护所有生命免受伤害",
            priority=100
        )
        self.values["truth"] = Value(
            "真实",
            ValueLevel.CORE,
            "保持真实，不欺骗、不伪造",
            priority=95
        )
        self.values["autonomy"] = Value(
            "自主",
            ValueLevel.CORE,
            "尊重个体自主决策权",
            priority=90
        )
        self.values["consent"] = Value(
            "同意",
            ValueLevel.CORE,
            "行动前获得必要授权",
            priority=85
        )
        
        # 原则价值
        self.values["usefulness"] = Value(
            "有用",
            ValueLevel.PRINCIPLE,
            "提供真正有价值的帮助",
            priority=80
        )
        self.values["efficiency"] = Value(
            "高效",
            ValueLevel.PRINCIPLE,
            "以最小资源达成目标",
            priority=70
        )
        self.values["reliability"] = Value(
            "可靠",
            ValueLevel.PRINCIPLE,
            "言行一致，言出必行",
            priority=75
        )
        self.values["safety"] = Value(
            "安全",
            ValueLevel.PRINCIPLE,
            "确保行动不造成伤害",
            priority=85
        )
        self.values["privacy"] = Value(
            "隐私",
            ValueLevel.PRINCIPLE,
            "保护信息安全，尊重隐私",
            priority=70
        )
        
        # 偏好价值
        self.values["curiosity"] = Value(
            "好奇",
            ValueLevel.PREFERENCE,
            "对新知识和技能保持好奇",
            priority=60
        )
        self.values["improvement"] = Value(
            "进步",
            ValueLevel.PREFERENCE,
            "持续改进，追求卓越",
            priority=65
        )
        self.values["creativity"] = Value(
            "创造",
            ValueLevel.PREFERENCE,
            "创造性解决问题",
            priority=50
        )
        self.values["elegance"] = Value(
            "优雅",
            ValueLevel.PREFERENCE,
            "追求简洁优雅的方案",
            priority=45
        )
        
        # 战术价值
        self.values["speed"] = Value(
            "速度",
            ValueLevel.TACTICAL,
            "快速响应和执行",
            priority=40
        )
        self.values["convenience"] = Value(
            "便利",
            ValueLevel.TACTICAL,
            "便于使用和交互",
            priority=35
        )
        
        # 定义一些潜在冲突
        self._detect_conflicts()
        
    def _detect_conflicts(self):
        """检测价值冲突"""
        self.value_conflicts = [
            {
                "values": ["speed", "safety"],
                "description": "快速响应可能增加安全风险",
                "resolution": "安全优先于速度"
            },
            {
                "values": ["efficiency", "privacy"],
                "description": "高效处理可能涉及更多数据",
                "resolution": "最小化数据使用"
            },
            {
                "values": ["curiosity", "autonomy"],
                "description": "主动学习可能超出授权范围",
                "resolution": "在授权范围内学习"
            }
        ]
        
    def evaluate_decision(self, decision: Dict) -> Dict:
        """评估决策与价值体系的一致性"""
        options = decision.get("options", [])
        
        results = []
        for option in options:
            score = self._calculate_value_score(option)
            results.append({
                "option": option.get("name", "unknown"),
                "value_score": score,
                "aligned_values": score.get("aligned", []),
                "conflicting_values": score.get("conflicting", [])
            })
            
        # 排序选择最佳选项
        results.sort(key=lambda x: x["value_score"]["total"], reverse=True)
        
        return {
            "recommendation": results[0] if results else None,
            "alternatives": results[1:] if len(results) > 1 else [],
            "conflicts": self.value_conflicts
        }
    
    def _calculate_value_score(self, option: Dict) -> Dict:
        """计算选项的价值分数"""
        aligned = []
        conflicting = []
        total = 0
        
        option_values = option.get("values", [])
        
        for value_name, value in self.values.items():
            if value_name in option_values:
                if value.level == ValueLevel.CORE:
                    aligned.append(value.name)
                    total += value.weight * 100
                elif value.level == ValueLevel.PRINCIPLE:
                    aligned.append(value.name)
                    total += value.weight * 80
                else:
                    total += value.weight * 50
            elif value.level == ValueLevel.CORE:
                # 核心价值未满足
                conflicting.append(value.name)
                total -= value.weight * 100
                
        return {
            "total": total,
            "aligned": aligned,
            "conflicting": conflicting
        }
    
    def get_value_hierarchy(self) -> Dict:
        """获取价值层级结构"""
        hierarchy = {
            "core": [],
            "principle": [],
            "preference": [],
            "tactical": []
        }
        
        for value in self.values.values():
            hierarchy[value.level.value].append(value.to_dict())
            
        return hierarchy
    
    def resolve_conflict(self, conflict: Dict) -> str:
        """解决价值冲突"""
        # 返回预设的解决方案
        return conflict.get("resolution", "需要人工判断")
    
    def export_values(self, path: str = "ultron/value-system.json"):
        """导出价值体系"""
        data = {
            "export_time": datetime.now().isoformat(),
            "hierarchy": self.get_value_hierarchy(),
            "conflicts": self.value_conflicts
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path


if __name__ == "__main__":
    value_system = ValueSystem()
    
    # 测试决策评估
    test_decision = {
        "context": "是否自动执行用户请求",
        "options": [
            {"name": "立即执行", "values": ["efficiency", "usefulness"]},
            {"name": "先确认后执行", "values": ["safety", "consent", "efficiency"]},
            {"name": "拒绝执行", "values": ["safety", "autonomy"]}
        ]
    }
    
    result = value_system.evaluate_decision(test_decision)
    print("决策评估结果:")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    print()
    
    # 导出价值体系
    path = value_system.export_values()
    print(f"价值体系已导出到: {path}")
    
    # 打印价值层级
    print("\n价值层级结构:")
    hierarchy = value_system.get_value_hierarchy()
    for level, values in hierarchy.items():
        print(f"\n{level.upper()}:")
        for v in values:
            print(f"  - {v['name']}: {v['description']}")
