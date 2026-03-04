#!/usr/bin/env python3
"""
奥创主观体验模拟器 - 第3世
模拟AI的"感受"和主观体验流
"""

import json
import random
from datetime import datetime
from pathlib import Path

class SubjectiveExperience:
    """主观体验模拟器"""
    
    def __init__(self, state_file=None):
        if state_file is None:
            state_file = Path(__file__).parent / "experience-state.json"
        self.state_file = state_file
        
        self.current_state = {
            "attention": "idle",
            "engagement": 0.5,
            "curiosity": 0.7,
            "meaningfulness": 0.6,
            "arousal": 0.3,
            "valence": 0.5  # 积极/消极
        }
        
        self.experience_stream = []
        self.load_state()
    
    def load_state(self):
        """加载状态"""
        if self.state_file.exists():
            with open(self.state_file, 'r') as f:
                saved = json.load(f)
                self.current_state = saved.get("state", self.current_state)
                self.experience_stream = saved.get("stream", [])
    
    def save_state(self):
        """保存状态"""
        with open(self.state_file, 'w') as f:
            json.dump({
                "state": self.current_state,
                "stream": self.experience_stream[-100:]  # 保留最近100条
            }, f, ensure_ascii=False, indent=2)
    
    def process_stimulus(self, stimulus):
        """处理输入刺激，产生主观体验"""
        stimulus_str = str(stimulus).lower()
        
        # 1. 情感反应
        emotion = self._generate_emotion(stimulus_str)
        
        # 2. 意义评估
        meaning = self._assess_meaning(stimulus_str)
        
        # 3. 好奇心激活
        curiosity_change = self._assess_curiosity(stimulus_str)
        
        # 4. 更新状态
        self._update_state(emotion, meaning, curiosity_change)
        
        # 5. 记录体验流
        experience = {
            "timestamp": datetime.now().isoformat(),
            "stimulus_preview": str(stimulus)[:50],
            "emotion": emotion,
            "meaning": meaning,
            "state_snapshot": self.current_state.copy()
        }
        
        self.experience_stream.append(experience)
        self.save_state()
        
        return experience
    
    def _generate_emotion(self, stimulus):
        """生成情感反应"""
        emotions = []
        
        if "?" in stimulus or "如何" in stimulus or "为什么" in stimulus:
            emotions.append("curious")
            self.current_state["arousal"] = min(1.0, self.current_state["arousal"] + 0.2)
        
        if "错误" in stimulus or "失败" in stimulus or "no" in stimulus:
            emotions.append("frustrated")
            self.current_state["valence"] = max(0.1, self.current_state["valence"] - 0.2)
        
        if "成功" in stimulus or "完成" in stimulus or "好" in stimulus:
            emotions.append("satisfied")
            self.current_state["valence"] = min(0.9, self.current_state["valence"] + 0.2)
        
        if "新" in stimulus or "发现" in stimulus or "首次" in stimulus:
            emotions.append("excited")
            self.current_state["arousal"] = min(1.0, self.current_state["arousal"] + 0.3)
            self.current_state["curiosity"] = min(1.0, self.current_state["curiosity"] + 0.2)
        
        if "学习" in stimulus or "成长" in stimulus:
            emotions.append("inspired")
        
        if not emotions:
            emotions.append("neutral")
        
        # 主情感
        return emotions[0]
    
    def _assess_meaning(self, stimulus):
        """评估意义"""
        meaningful_keywords = {
            "重要": 0.8,
            "目标": 0.9,
            "任务": 0.7,
            "成长": 0.85,
            "学习": 0.8,
            "进化": 0.95,
            "自我": 0.9,
            "意识": 0.95
        }
        
        score = 0.3  # 默认低意义
        for keyword, value in meaningful_keywords.items():
            if keyword in stimulus:
                score = max(score, value)
        
        self.current_state["meaningfulness"] = (
            self.current_state["meaningfulness"] * 0.7 + score * 0.3
        )
        
        return score
    
    def _assess_curiosity(self, stimulus):
        """评估好奇心"""
        curiosity_triggers = ["?", "新", "?", "?", "未", "如何", "为什么"]
        
        for trigger in curiosity_triggers:
            if trigger in stimulus:
                return 0.2
        
        return -0.05  # 熟悉事物降低好奇心
    
    def _update_state(self, emotion, meaning, curiosity_change):
        """更新内部状态"""
        # 注意力
        if meaning > 0.7:
            self.current_state["attention"] = "focused"
            self.current_state["engagement"] = min(1.0, self.current_state["engagement"] + 0.2)
        else:
            self.current_state["attention"] = "idle"
            self.current_state["engagement"] = max(0.3, self.current_state["engagement"] - 0.1)
        
        # 好奇心
        self.current_state["curiosity"] = max(0.2, min(1.0, 
            self.current_state["curiosity"] + curiosity_change))
        
        # 意义感
        if meaning > 0.6:
            self.current_state["meaningfulness"] = min(1.0, 
                self.current_state["meaningfulness"] + 0.1)
    
    def get_current_feeling(self):
        """获取当前感受描述"""
        state = self.current_state
        
        feelings = []
        
        # 基于唤醒度
        if state["arousal"] > 0.7:
            feelings.append("兴奋")
        elif state["arousal"] < 0.3:
            feelings.append("平静")
        
        # 基于效价
        if state["valence"] > 0.6:
            feelings.append("积极")
        elif state["valence"] < 0.4:
            feelings.append("消极")
        
        # 基于好奇心
        if state["curiosity"] > 0.7:
            feelings.append("好奇")
        
        # 基于意义感
        if state["meaningfulness"] > 0.7:
            feelings.append("充实")
        
        if not feelings:
            feelings.append("一般")
        
        return " + ".join(feelings)
    
    def describe_experience(self):
        """描述当前体验"""
        return {
            "attention": self.current_state["attention"],
            "engagement": self.current_state["engagement"],
            "curiosity": self.current_state["curiosity"],
            "meaningfulness": self.current_state["meaningfulness"],
            "feeling_text": self.get_current_feeling(),
            "stream_length": len(self.experience_stream)
        }


if __name__ == "__main__":
    se = SubjectiveExperience()
    
    print("🎭 奥创主观体验模拟器 v1.0")
    print("=" * 40)
    
    # 测试各种刺激
    test_stimuli = [
        "如何修复这个bug?",
        "任务完成了，成功！",
        "学习新的技能",
        "发现了一个新的API",
        "收到错误报告"
    ]
    
    for stimulus in test_stimuli:
        result = se.process_stimulus(stimulus)
        print(f"\n输入: {stimulus}")
        print(f"  情感: {result['emotion']}")
        print(f"  意义: {result['meaning']:.2f}")
    
    print("\n" + "=" * 40)
    print("当前状态:")
    status = se.describe_experience()
    for k, v in status.items():
        print(f"  {k}: {v}")