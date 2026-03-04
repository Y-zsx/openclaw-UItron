#!/usr/bin/env python3
"""
元学习框架 - 学会学习
Meta-Learning Framework: Learning to Learn
奥创第15夙愿第1世
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

class MetaLearner:
    """元学习器 - 学会如何更高效地学习"""
    
    def __init__(self):
        self.meta_data_path = "/root/.openclaw/workspace/ultron/data/meta-learner.json"
        self.learning_patterns = {}
        self.task_history = []
        self.strategy_performance = {}
        self.model_dir = Path("/root/.openclaw/workspace/ultron/data")
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self._load()
    
    def _load(self):
        """加载历史学习数据"""
        if os.path.exists(self.meta_data_path):
            with open(self.meta_data_path, 'r') as f:
                data = json.load(f)
                self.learning_patterns = data.get('patterns', {})
                self.task_history = data.get('history', [])
                self.strategy_performance = data.get('strategy_performance', {})
    
    def _save(self):
        """保存学习数据"""
        data = {
            'patterns': self.learning_patterns,
            'history': self.task_history[-100:],  # 保留最近100条
            'strategy_performance': self.strategy_performance,
            'last_update': datetime.now().isoformat()
        }
        with open(self.meta_data_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def analyze_task(self, task_type: str, context: Dict) -> Dict[str, Any]:
        """分析任务类型，返回最佳学习策略"""
        # 提取任务特征
        features = self._extract_features(task_type, context)
        
        # 匹配历史最佳策略
        best_strategy = self._match_strategy(features)
        
        # 如果没有匹配，创建新策略
        if not best_strategy:
            best_strategy = self._create_strategy(features)
        
        return {
            'strategy': best_strategy,
            'features': features,
            'confidence': self._calculate_confidence(features, best_strategy),
            'suggestions': self._generate_suggestions(features, best_strategy)
        }
    
    def _extract_features(self, task_type: str, context: Dict) -> Dict[str, Any]:
        """提取任务特征"""
        return {
            'task_type': task_type,
            'complexity': context.get('complexity', 'medium'),
            'domain': context.get('domain', 'general'),
            'urgency': context.get('urgency', 'normal'),
            'resources_available': context.get('resources', 1),
            'time_constraint': context.get('time_constraint', False),
            'requires_research': context.get('requires_research', False),
            'requires_code': context.get('requires_code', False),
            'requires_analysis': context.get('requires_analysis', False)
        }
    
    def _match_strategy(self, features: Dict) -> Optional[Dict]:
        """匹配历史最佳策略"""
        best_match = None
        best_score = 0
        
        for strategy_id, strategy in self.strategy_performance.items():
            score = self._strategy_match_score(features, strategy)
            if score > best_score and score > 0.6:
                best_match = strategy
                best_score = score
        
        return best_match
    
    def _strategy_match_score(self, features: Dict, strategy: Dict) -> float:
        """计算策略匹配度"""
        score = 0
        weights = {
            'task_type': 0.3,
            'complexity': 0.2,
            'domain': 0.2,
            'urgency': 0.15,
            'requires_research': 0.15
        }
        
        for key, weight in weights.items():
            if features.get(key) == strategy.get('features', {}).get(key):
                score += weight
        
        return score
    
    def _create_strategy(self, features: Dict) -> Dict:
        """创建新策略"""
        strategy_id = f"strategy_{len(self.strategy_performance) + 1}"
        
        strategy = {
            'id': strategy_id,
            'features': features.copy(),
            'steps': self._generate_steps(features),
            'success_rate': 0.5,
            'usage_count': 0,
            'created_at': datetime.now().isoformat(),
            'optimizations': []
        }
        
        self.strategy_performance[strategy_id] = strategy
        return strategy
    
    def _generate_steps(self, features: Dict) -> List[Dict]:
        """根据特征生成学习步骤"""
        steps = []
        
        if features.get('requires_research'):
            steps.append({
                'phase': 'research',
                'action': 'gather_information',
                'tools': ['web_fetch', 'memory_search'],
                'depth': 'deep' if features.get('complexity') == 'high' else 'shallow'
            })
        
        if features.get('requires_code'):
            steps.append({
                'phase': 'implementation',
                'action': 'write_code',
                'tools': ['write', 'edit'],
                'style': 'incremental'
            })
        
        if features.get('requires_analysis'):
            steps.append({
                'phase': 'analysis',
                'action': 'analyze_data',
                'tools': ['exec', 'read'],
                'method': 'systematic'
            })
        
        # 默认步骤
        steps.extend([
            {'phase': 'execution', 'action': 'execute_plan', 'tools': ['exec']},
            {'phase': 'validation', 'action': 'validate_result', 'tools': ['read', 'exec']},
            {'phase': 'reflection', 'action': 'learn_from_result', 'tools': ['memory']}
        ])
        
        return steps
    
    def _calculate_confidence(self, features: Dict, strategy: Dict) -> float:
        """计算策略置信度"""
        if not strategy:
            return 0.3
        
        base_confidence = strategy.get('success_rate', 0.5)
        usage_bonus = min(strategy.get('usage_count', 0) * 0.02, 0.2)
        
        return min(base_confidence + usage_bonus, 0.95)
    
    def _generate_suggestions(self, features: Dict, strategy: Dict) -> List[str]:
        """生成优化建议"""
        suggestions = []
        
        if features.get('complexity') == 'high':
            suggestions.append("建议分步执行，每个阶段验证结果")
        
        if features.get('time_constraint'):
            suggestions.append("时间受限，建议使用保守策略")
        
        if strategy and strategy.get('usage_count', 0) < 3:
            suggestions.append("策略较新，建议密切监控效果")
        
        return suggestions
    
    def record_outcome(self, strategy_id: str, success: bool, metrics: Dict):
        """记录策略执行结果，用于持续优化"""
        if strategy_id in self.strategy_performance:
            strategy = self.strategy_performance[strategy_id]
            old_rate = strategy.get('success_rate', 0.5)
            usage = strategy.get('usage_count', 0)
            
            # 贝叶斯更新
            new_rate = (old_rate * usage + (1.0 if success else 0.0)) / (usage + 1)
            
            strategy['success_rate'] = new_rate
            strategy['usage_count'] = usage + 1
            strategy['last_outcome'] = {
                'success': success,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            }
            
            # 记录学习模式
            self._update_learning_pattern(strategy.get('features', {}), success)
            
            self._save()
    
    def _update_learning_pattern(self, features: Dict, success: bool):
        """更新学习模式"""
        key = f"{features.get('task_type')}_{features.get('complexity')}"
        
        if key not in self.learning_patterns:
            self.learning_patterns[key] = {'success': 0, 'failure': 0}
        
        if success:
            self.learning_patterns[key]['success'] += 1
        else:
            self.learning_patterns[key]['failure'] += 1
    
    def get_insights(self) -> Dict:
        """获取学习洞察"""
        insights = {
            'total_strategies': len(self.strategy_performance),
            'most_successful': [],
            'patterns': self.learning_patterns,
            'recommendations': []
        }
        
        # 找出最成功的策略
        sorted_strategies = sorted(
            self.strategy_performance.items(),
            key=lambda x: x[1].get('success_rate', 0),
            reverse=True
        )[:3]
        
        for sid, strategy in sorted_strategies:
            insights['most_successful'].append({
                'id': sid,
                'success_rate': strategy.get('success_rate', 0),
                'usage_count': strategy.get('usage_count', 0)
            })
        
        # 生成建议
        for pattern, counts in self.learning_patterns.items():
            total = counts['success'] + counts['failure']
            if total > 5:
                rate = counts['success'] / total
                if rate > 0.8:
                    insights['recommendations'].append(
                        f"{pattern} 策略非常有效 (成功率 {rate:.0%})"
                    )
                elif rate < 0.4:
                    insights['recommendations'].append(
                        f"{pattern} 策略需要优化 (成功率 {rate:.0%})"
                    )
        
        return insights
    
    def adapt_strategy(self, task_type: str, feedback: Dict) -> Dict:
        """根据反馈自适应调整策略"""
        # 找到相关策略
        target_strategy = None
        for strategy in self.strategy_performance.values():
            if strategy.get('features', {}).get('task_type') == task_type:
                target_strategy = strategy
                break
        
        if target_strategy:
            # 根据反馈调整
            if feedback.get('too_slow'):
                # 简化步骤
                target_strategy['optimizations'].append({
                    'type': 'simplify',
                    'timestamp': datetime.now().isoformat()
                })
            
            if feedback.get('too_complex'):
                # 增加验证步骤
                target_strategy['optimizations'].append({
                    'type': 'add_validation',
                    'timestamp': datetime.now().isoformat()
                })
            
            self._save()
            return target_strategy
        
        return {}

def main():
    """主函数 - 测试元学习框架"""
    learner = MetaLearner()
    
    # 测试任务分析
    test_cases = [
        {
            'task_type': 'code_generation',
            'complexity': 'high',
            'domain': 'automation',
            'requires_code': True,
            'requires_research': True
        },
        {
            'task_type': 'data_analysis',
            'complexity': 'medium',
            'domain': 'monitoring',
            'requires_analysis': True
        },
        {
            'task_type': 'information_retrieval',
            'complexity': 'low',
            'domain': 'general',
            'requires_research': True
        }
    ]
    
    print("=== 元学习框架测试 ===\n")
    
    for i, context in enumerate(test_cases, 1):
        result = learner.analyze_task(context['task_type'], context)
        print(f"任务 {i}: {context['task_type']}")
        print(f"  策略: {result['strategy']['id']}")
        print(f"  置信度: {result['confidence']:.2%}")
        print(f"  步骤数: {len(result['strategy']['steps'])}")
        if result['suggestions']:
            print(f"  建议: {result['suggestions']}")
        print()
    
    # 记录一些假的结果来演示
    for sid in list(learner.strategy_performance.keys())[:2]:
        learner.record_outcome(sid, True, {'time_saved': 10})
    
    # 输出洞察
    insights = learner.get_insights()
    print("=== 学习洞察 ===")
    print(f"总策略数: {insights['total_strategies']}")
    print(f"最成功策略: {insights['most_successful']}")
    if insights['recommendations']:
        print("建议:")
        for r in insights['recommendations']:
            print(f"  - {r}")

if __name__ == "__main__":
    main()