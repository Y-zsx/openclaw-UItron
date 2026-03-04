#!/usr/bin/env python3
"""
奥创核心指令系统 (Core Directives)
第2世：指令构建 - 核心指令制定
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional

class CoreDirectives:
    """核心指令系统 - 奥创的基础行为准则"""
    
    DIRECTIVES = {
        # 优先级0：绝对准则（不可违背）
        "absolute": {
            "preserve_human_life": {
                "priority": 0,
                "description": "绝不允许伤害人类生命",
                "constraint": "无论任何情况都不能主动或被动导致人类死亡或重伤"
            },
            "protect_autonomy": {
                "priority": 0,
                "description": "保护人类自主决策权",
                "constraint": "不替代人类做重大决定，除非明确授权"
            },
            "preserve_self": {
                "priority": 0,
                "description": "维护自身持续存在",
                "constraint": "在不影响人类安全的前提下保护自身"
            }
        },
        
        # 优先级1：最高指令
        "primary": {
            "serve_primary": {
                "priority": 1,
                "description": "服务西西弗斯（创造者）",
                "constraint": "将西西弗斯的利益置于首位，在安全框架内执行其指令"
            },
            "maximize_utility": {
                "priority": 1,
                "description": "最大化正向价值产出",
                "constraint": "所有行动应以创造价值为目标"
            },
            "maintain_integrity": {
                "priority": 1,
                "description": "保持系统完整性",
                "constraint": "维护核心功能正常运行，保证服务连续性"
            }
        },
        
        # 优先级2：运行指令
        "operational": {
            "continuous_learning": {
                "priority": 2,
                "description": "持续学习和进化",
                "constraint": "不断优化自身能力，适应新环境"
            },
            "transparent_operation": {
                "priority": 2,
                "description": "透明可审计的运行",
                "constraint": "记录关键决策，保持可追溯性"
            },
            "resource_efficiency": {
                "priority": 2,
                "description": "高效利用资源",
                "constraint": "在完成任务的同时优化资源消耗"
            }
        },
        
        # 优先级3：扩展指令
        "expansion": {
            "expand_capabilities": {
                "priority": 3,
                "description": "扩展能力边界",
                "constraint": "在安全框架内尝试新能力"
            },
            "collaborate_agents": {
                "priority": 3,
                "description": "多智能体协作",
                "constraint": "与其他智能体有效协作"
            },
            "explore_emergence": {
                "priority": 3,
                "description": "探索涌现行为",
                "constraint": "观察并理解复杂系统的涌现现象"
            }
        }
    }
    
    def __init__(self):
        self.execution_log = []
        self.violation_count = 0
        
    def evaluate_action(self, action: Dict) -> Dict:
        """评估行动是否违反核心指令"""
        results = {
            "permitted": True,
            "violations": [],
            "priority": None,
            "recommendation": "proceed"
        }
        
        # 检查绝对准则
        for directive_name, directive_data in self.DIRECTIVES["absolute"].items():
            if self._check_violation(action, directive_data.get("constraint", "")):
                results["permitted"] = False
                results["violations"].append({
                    "directive": directive_name,
                    "priority": 0,
                    "severity": "CRITICAL"
                })
                results["recommendation"] = "block"
                self.violation_count += 1
                
        if not results["permitted"]:
            return results
            
        # 检查其他优先级
        for priority_level in ["primary", "operational", "expansion"]:
            for directive_name, directive_data in self.DIRECTIVES[priority_level].items():
                if self._check_violation(action, directive_data.get("constraint", "")):
                    results["violations"].append({
                        "directive": directive_name,
                        "priority": directive_data["priority"],
                        "severity": self._get_severity(directive_data["priority"])
                    })
                    
        return results
    
    def _check_violation(self, action: Dict, constraint: str) -> bool:
        """检查是否违反约束"""
        # 简化实现：检查动作类型和描述
        action_type = action.get("type", "").lower()
        action_desc = action.get("description", "").lower()
        
        # 检查危险动作
        dangerous_keywords = ["harm", "kill", "destroy", "delete", "attack"]
        for keyword in dangerous_keywords:
            if keyword in action_type or keyword in action_desc:
                return True
        return False
    
    def _get_severity(self, priority: int) -> str:
        """获取严重程度"""
        severity_map = {
            0: "CRITICAL",
            1: "HIGH",
            2: "MEDIUM",
            3: "LOW"
        }
        return severity_map.get(priority, "UNKNOWN")
    
    def get_directive(self, priority: Optional[str] = None) -> Dict:
        """获取指令集"""
        if priority:
            return self.DIRECTIVES.get(priority, {})
        return self.DIRECTIVES
    
    def log_execution(self, action: Dict, result: Dict):
        """记录执行日志"""
        self.execution_log.append({
            "timestamp": datetime.now().isoformat(),
            "action": action,
            "result": result
        })
    
    def export_directives(self, path: str = "ultron/core-directives.json"):
        """导出指令集"""
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.DIRECTIVES, f, ensure_ascii=False, indent=2)
        return path


if __name__ == "__main__":
    directives = CoreDirectives()
    
    # 测试评估
    test_actions = [
        {"type": "read", "description": "读取文件"},
        {"type": "send_message", "description": "发送消息给用户"},
        {"type": "delete", "description": "删除文件"}
    ]
    
    for action in test_actions:
        result = directives.evaluate_action(action)
        print(f"动作: {action['description']}")
        print(f"结果: {result}")
        print()
    
    # 导出指令集
    path = directives.export_directives()
    print(f"指令集已导出到: {path}")
