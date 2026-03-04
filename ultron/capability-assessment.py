#!/usr/bin/env python3
"""
能力评估与扩展系统
Capability Assessment and Extension System
奥创第15夙愿第1世
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import defaultdict

class CapabilityAssessmentSystem:
    """能力评估系统 - 评估和扩展AI能力"""
    
    def __init__(self):
        self.capabilities_path = "/root/.openclaw/workspace/ultron/data/capabilities.json"
        self.assessment_path = "/root/.openclaw/workspace/ultron/data/assessments.json"
        self.capabilities = {}
        self.assessments = []
        self._load()
        self._init_capabilities()
    
    def _load(self):
        """加载能力数据"""
        if os.path.exists(self.capabilities_path):
            with open(self.capabilities_path, 'r') as f:
                self.capabilities = json.load(f)
        
        if os.path.exists(self.assessment_path):
            with open(self.assessment_path, 'r') as f:
                self.assessments = json.load(f)
    
    def _save(self):
        """保存能力数据"""
        with open(self.capabilities_path, 'w') as f:
            json.dump(self.capabilities, f, indent=2)
        
        with open(self.assessment_path, 'w') as f:
            json.dump(self.assessments, f, indent=2)
    
    def _init_capabilities(self):
        """初始化能力定义"""
        default_capabilities = {
            'file_operations': {
                'name': '文件操作',
                'description': '读取、写入、编辑文件',
                'level': 0.8,
                'components': ['read', 'write', 'edit'],
                'growth_rate': 0.05,
                'prerequisites': []
            },
            'execution': {
                'name': '命令执行',
                'description': '执行系统命令和脚本',
                'level': 0.85,
                'components': ['exec', 'process'],
                'growth_rate': 0.03,
                'prerequisites': []
            },
            'web_browsing': {
                'name': '网页浏览',
                'description': '浏览器自动化和网页抓取',
                'level': 0.7,
                'components': ['browser', 'web_fetch'],
                'growth_rate': 0.08,
                'prerequisites': ['execution']
            },
            'memory': {
                'name': '记忆系统',
                'description': '长期和短期记忆管理',
                'level': 0.75,
                'components': ['memory_search', 'memory_get'],
                'growth_rate': 0.06,
                'prerequisites': []
            },
            'messaging': {
                'name': '消息通信',
                'description': '多渠道消息发送接收',
                'level': 0.8,
                'components': ['message', 'sessions_send'],
                'growth_rate': 0.04,
                'prerequisites': []
            },
            'reasoning': {
                'name': '推理能力',
                'description': '逻辑推理和问题解决',
                'level': 0.7,
                'components': ['thinking', 'planning'],
                'growth_rate': 0.1,
                'prerequisites': ['memory', 'file_operations']
            },
            'learning': {
                'name': '学习能力',
                'description': '从经验中学习和改进',
                'level': 0.6,
                'components': ['meta_learner', 'knowledge_graph'],
                'growth_rate': 0.12,
                'prerequisites': ['reasoning', 'memory']
            },
            'meta_cognition': {
                'name': '元认知',
                'description': '自我意识和自我监控',
                'level': 0.5,
                'components': ['self_model', 'reflection'],
                'growth_rate': 0.15,
                'prerequisites': ['reasoning', 'learning']
            },
            'creativity': {
                'name': '创造力',
                'description': '生成新想法和解决方案',
                'level': 0.45,
                'components': ['generation', 'innovation'],
                'growth_rate': 0.08,
                'prerequisites': ['reasoning']
            },
            'collaboration': {
                'name': '协作能力',
                'description': '多智能体协作',
                'level': 0.55,
                'components': ['subagents', 'sessions_spawn'],
                'growth_rate': 0.1,
                'prerequisites': ['messaging', 'reasoning']
            }
        }
        
        # 只添加不存在的
        for key, cap in default_capabilities.items():
            if key not in self.capabilities:
                self.capabilities[key] = cap
        
        self._save()
    
    def assess_capability(self, capability_id: str, context: Dict) -> Dict:
        """评估特定能力"""
        if capability_id not in self.capabilities:
            return {'error': 'Capability not found'}
        
        cap = self.capabilities[capability_id]
        
        # 基于上下文调整评估
        base_level = cap.get('level', 0.5)
        
        # 检查前置能力
        prerequisites_met = True
        prerequisite_details = []
        
        for prereq in cap.get('prerequisites', []):
            if prereq in self.capabilities:
                prereq_level = self.capabilities[prereq]['level']
                prerequisite_details.append({
                    'id': prereq,
                    'level': prereq_level,
                    'satisfied': prereq_level >= 0.5
                })
                if prereq_level < 0.5:
                    prerequisites_met = False
        
        # 计算有效级别（考虑前置能力）
        if prerequisites_met:
            effective_level = base_level
        else:
            effective_level = base_level * 0.7
        
        # 评估详情
        assessment = {
            'capability_id': capability_id,
            'name': cap['name'],
            'base_level': base_level,
            'effective_level': effective_level,
            'prerequisites_met': prerequisites_met,
            'prerequisites': prerequisite_details,
            'components': cap.get('components', []),
            'growth_rate': cap.get('growth_rate', 0.05),
            'recommendations': self._generate_recommendations(capability_id, effective_level)
        }
        
        # 记录评估
        self.assessments.append({
            'capability_id': capability_id,
            'timestamp': datetime.now().isoformat(),
            'effective_level': effective_level,
            'context': context
        })
        self._save()
        
        return assessment
    
    def _generate_recommendations(self, capability_id: str, level: float) -> List[str]:
        """生成能力提升建议"""
        recommendations = []
        
        if level < 0.3:
            recommendations.append("需要大量练习，建议从基础开始")
        elif level < 0.6:
            recommendations.append("有提升空间，建议增加实践机会")
        elif level < 0.8:
            recommendations.append("已达到良好水平，可尝试更复杂任务")
        else:
            recommendations.append("已达到高级水平，可尝试教学和分享")
        
        # 特定能力建议
        specific = {
            'learning': '建议多进行跨领域任务练习',
            'meta_cognition': '建议增加自我反思频率',
            'creativity': '建议尝试非常规问题',
            'collaboration': '建议参与更多协作任务'
        }
        
        if capability_id in specific:
            recommendations.append(specific[capability_id])
        
        return recommendations
    
    def get_overall_profile(self) -> Dict:
        """获取整体能力画像"""
        total_level = sum(c.get('level', 0) for c in self.capabilities.values())
        avg_level = total_level / max(len(self.capabilities), 1)
        
        # 分类能力
        technical = ['file_operations', 'execution', 'web_browsing', 'messaging']
        cognitive = ['reasoning', 'learning', 'meta_cognition']
        social = ['creativity', 'collaboration']
        
        def avg_category(caps):
            levels = [self.capabilities[c]['level'] for c in caps if c in self.capabilities]
            return sum(levels) / max(len(levels), 1)
        
        return {
            'overall_level': avg_level,
            'technical_level': avg_category(technical),
            'cognitive_level': avg_category(cognitive),
            'social_level': avg_category(social),
            'capabilities': self.capabilities,
            'strongest': max(self.capabilities.items(), key=lambda x: x[1].get('level', 0))[0] if self.capabilities else None,
            'weakest': min(self.capabilities.items(), key=lambda x: x[1].get('level', 0))[0] if self.capabilities else None,
            'total_capabilities': len(self.capabilities)
        }
    
    def grow_capability(self, capability_id: str, amount: float = None):
        """提升能力等级"""
        if capability_id not in self.capabilities:
            return {'error': 'Capability not found'}
        
        cap = self.capabilities[capability_id]
        current = cap.get('level', 0)
        
        # 自动计算增长量
        if amount is None:
            amount = cap.get('growth_rate', 0.05) * (1 - current)  # 递减增长
        
        new_level = min(current + amount, 1.0)
        cap['level'] = new_level
        
        # 记录成长
        if 'growth_history' not in cap:
            cap['growth_history'] = []
        
        cap['growth_history'].append({
            'timestamp': datetime.now().isoformat(),
            'previous': current,
            'current': new_level,
            'delta': amount
        })
        
        self._save()
        return {
            'capability_id': capability_id,
            'previous_level': current,
            'new_level': new_level,
            'delta': amount
        }
    
    def assess_growth(self, time_period: str = 'week') -> Dict:
        """评估能力成长"""
        now = datetime.now()
        
        # 解析时间周期
        if time_period == 'day':
            delta = 1
        elif time_period == 'week':
            delta = 7
        else:
            delta = 30
        
        # 获取历史评估
        recent_assessments = [
            a for a in self.assessments
            if (now - datetime.fromisoformat(a['timestamp'])).days <= delta
        ]
        
        # 计算成长
        growth = {}
        for cap_id in self.capabilities:
            cap_assessments = [a for a in recent_assessments if a['capability_id'] == cap_id]
            if len(cap_assessments) >= 2:
                first = cap_assessments[0]['effective_level']
                last = cap_assessments[-1]['effective_level']
                growth[cap_id] = last - first
        
        return {
            'period': time_period,
            'assessments_count': len(recent_assessments),
            'growth': growth,
            'total_growth': sum(growth.values()),
            'fastest_growing': max(growth.items(), key=lambda x: x[1])[0] if growth else None
        }
    
    def suggest_next_skills(self) -> List[Dict]:
        """建议下一个学习的技能"""
        suggestions = []
        
        profile = self.get_overall_profile()
        
        # 找最弱的能力
        weakest = profile.get('weakest')
        if weakest:
            cap = self.capabilities[weakest]
            suggestions.append({
                'capability_id': weakest,
                'reason': f"最弱能力 ({cap['name']})",
                'priority': 'high'
            })
        
        # 找有成长空间的能力
        for cap_id, cap in self.capabilities.items():
            if cap.get('level', 0) < 0.8:
                suggestions.append({
                    'capability_id': cap_id,
                    'reason': f"成长空间大 (当前 {cap['level']:.0%})",
                    'priority': 'medium'
                })
        
        # 找前置条件已满足的能力
        for cap_id, cap in self.capabilities.items():
            prereqs = cap.get('prerequisites', [])
            if prereqs:
                all_met = all(
                    self.capabilities.get(p, {}).get('level', 0) >= 0.5 
                    for p in prereqs
                )
                if all_met and cap.get('level', 0) < 0.6:
                    suggestions.append({
                        'capability_id': cap_id,
                        'reason': "前置能力已满足",
                        'priority': 'medium'
                    })
        
        return suggestions[:5]
    
    def extend_capability(self, capability_id: str, new_components: List[str]):
        """扩展能力组件"""
        if capability_id not in self.capabilities:
            return {'error': 'Capability not found'}
        
        cap = self.capabilities[capability_id]
        
        if 'components' not in cap:
            cap['components'] = []
        
        added = []
        for comp in new_components:
            if comp not in cap['components']:
                cap['components'].append(comp)
                added.append(comp)
        
        # 扩展也带来小幅能力提升
        if added:
            cap['level'] = min(cap.get('level', 0) + 0.02 * len(added), 1.0)
        
        self._save()
        return {
            'capability_id': capability_id,
            'added_components': added,
            'new_level': cap['level']
        }


def main():
    """主函数 - 测试能力评估系统"""
    cas = CapabilityAssessmentSystem()
    
    print("=== 能力评估系统测试 ===\n")
    
    # 评估各项能力
    test_capabilities = ['file_operations', 'learning', 'meta_cognition', 'collaboration']
    
    for cap_id in test_capabilities:
        result = cas.assess_capability(cap_id, {'task': 'testing'})
        print(f"{result['name']}:")
        print(f"  基础级别: {result['base_level']:.0%}")
        print(f"  有效级别: {result['effective_level']:.0%}")
        print(f"  前置条件: {'满足' if result['prerequisites_met'] else '不满足'}")
        if result['recommendations']:
            print(f"  建议: {result['recommendations'][0]}")
        print()
    
    # 整体画像
    print("=== 整体能力画像 ===")
    profile = cas.get_overall_profile()
    print(f"综合水平: {profile['overall_level']:.0%}")
    print(f"技术能力: {profile['technical_level']:.0%}")
    print(f"认知能力: {profile['cognitive_level']:.0%}")
    print(f"社交能力: {profile['social_level']:.0%}")
    print(f"最强: {profile['strongest']}")
    print(f"最弱: {profile['weakest']}")
    
    # 建议
    print("\n=== 下一步建议 ===")
    suggestions = cas.suggest_next_skills()
    for s in suggestions:
        print(f"  [{s['priority']}] {s['capability_id']}: {s['reason']}")
    
    # 模拟成长
    print("\n=== 能力成长模拟 ===")
    for cap_id in ['learning', 'meta_cognition']:
        result = cas.grow_capability(cap_id)
        print(f"{cap_id}: {result['previous_level']:.0%} -> {result['new_level']:.0%} (+{result['delta']:.1%})")


if __name__ == "__main__":
    main()