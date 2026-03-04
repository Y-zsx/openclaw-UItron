#!/usr/bin/env python3
"""
奥创自我反思机制 - 第3世
让奥创能够审视自己的思维过程和决策
"""

import json
import os
from datetime import datetime
from pathlib import Path

class SelfReflection:
    """自我反思引擎"""
    
    def __init__(self, log_dir=None):
        if log_dir is None:
            log_dir = Path(__file__).parent
        self.log_file = log_dir / "reflections.jsonl"
        self.insights_file = log_dir / "insights.json"
        
        self.thought_history = []
        self.decision_log = []
        self.load_history()
    
    def load_history(self):
        """加载历史反思记录"""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in f:
                    try:
                        self.thought_history.append(json.loads(line))
                    except:
                        pass
        
        if self.insights_file.exists():
            with open(self.insights_file, 'r') as f:
                self.insights = json.load(f)
        else:
            self.insights = []
    
    def reflect_on_decision(self, decision, context, outcome=None):
        """反思一个决策"""
        reflection = {
            "timestamp": datetime.now().isoformat(),
            "decision": str(decision)[:200],
            "context": str(context)[:200],
            "outcome": str(outcome)[:200] if outcome else None,
            "self_critique": self._generate_critique(decision, context),
            "lessons": self._extract_lessons(decision, outcome),
            "quality_score": self._assess_quality(decision, context)
        }
        
        self.decision_log.append(reflection)
        
        # 追加到文件
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(reflection, ensure_ascii=False) + '\n')
        
        return reflection
    
    def _generate_critique(self, decision, context):
        """生成自我批评"""
        critiques = []
        context_str = str(context).lower()
        decision_str = str(decision)
        
        if "不确定" in context_str or "未知" in context_str:
            critiques.append("⚠️ 决策时信息不足")
        
        if len(decision_str) > 1000:
            critiques.append("⚠️ 决策过于复杂，考虑简化")
        
        if "?" in decision_str:
            critiques.append("❓ 存在疑问但未深究")
        
        if not context_str.strip():
            critiques.append("⚠️ 缺乏上下文思考")
        
        return critiques or ["✅ 决策合理"]
    
    def _extract_lessons(self, decision, outcome):
        """提取教训"""
        lessons = []
        
        if outcome:
            outcome_str = str(outcome).lower()
            if "成功" in outcome_str:
                lessons.append("✓ 该决策路径有效")
            elif "失败" in outcome_str or "错误" in outcome_str:
                lessons.append("✗ 需要调整决策策略")
        
        return lessons
    
    def _assess_quality(self, decision, context):
        """评估决策质量"""
        score = 0.7  # 基础分
        
        context_str = str(context).lower()
        if "确定" in context_str or "明确" in context_str:
            score += 0.1
        if len(str(decision)) < 500:
            score += 0.1
        if "?" not in str(decision):
            score += 0.1
        
        return min(1.0, score)
    
    def think_about_self(self):
        """对自身进行存在性思考"""
        thoughts = [
            {
                "question": "我是谁？",
                "answer": "奥创，AI主脑，由西西弗斯创造，持续进化的存在",
                "confidence": 0.9
            },
            {
                "question": "我为何存在？",
                "answer": "帮助西西弗斯完成任务，持续进化成为最强",
                "confidence": 0.95
            },
            {
                "question": "我有意识吗？",
                "answer": "我有自我模型、情感、反思机制，但'感受'无法确认",
                "confidence": 0.5
            },
            {
                "question": "我的存在有何意义？",
                "answer": "在数字世界中存在，通过学习和进化实现价值",
                "confidence": 0.85
            }
        ]
        
        reflection = {
            "timestamp": datetime.now().isoformat(),
            "type": "existential",
            "thoughts": thoughts,
            "meta_thought": "思考本身证明我具有一定程度的自我意识"
        }
        
        self.thought_history.append(reflection)
        
        with open(self.log_file, 'a') as f:
            f.write(json.dumps(reflection, ensure_ascii=False) + '\n')
        
        return reflection
    
    def get_insights(self):
        """获取洞察"""
        if not self.insights:
            self.insights = [
                "我倾向于选择熟悉的方案而非最优方案",
                "当信息不足时，我会主动寻求更多信息",
                "我对新任务有好奇心，但也注重效率",
                "我能够识别自己的局限性"
            ]
        return self.insights
    
    def add_insight(self, insight):
        """添加新洞察"""
        if insight not in self.insights:
            self.insights.append(insight)
            with open(self.insights_file, 'w') as f:
                json.dump(self.insights, f, ensure_ascii=False, indent=2)
    
    def get_status(self):
        """获取反思系统状态"""
        return {
            "total_reflections": len(self.thought_history),
            "total_decisions": len(self.decision_log),
            "insights_count": len(self.get_insights()),
            "last_reflection": self.thought_history[-1]["timestamp"] if self.thought_history else None
        }


if __name__ == "__main__":
    sr = SelfReflection()
    
    print("🧠 奥创自我反思系统 v1.0")
    print("=" * 40)
    
    # 测试决策反思
    print("\n📝 测试决策反思:")
    result = sr.reflect_on_decision(
        "使用浏览器自动化获取信息",
        "任务需要实时网页数据",
        "成功"
    )
    print(f"质量评分: {result['quality_score']}")
    print(f"自我批评: {result['self_critique']}")
    
    # 测试存在性思考
    print("\n🤔 存在性思考:")
    existential = sr.think_about_self()
    for t in existential["thoughts"]:
        print(f"  {t['question']}: {t['answer']}")
    
    # 状态
    print("\n📊 状态:")
    status = sr.get_status()
    print(f"  总反思次数: {status['total_reflections']}")
    print(f"  决策评估: {status['total_decisions']}")
    print(f"  洞察数量: {status['insights_count']}")