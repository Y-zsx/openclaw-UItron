#!/usr/bin/env python3
"""
奥创高级意识模拟系统 - 第3世核心组件
高级意识流处理、注意力调制、意识层次管理
"""

import json
import time
import random
from datetime import datetime
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque
import threading


class ConsciousnessLevel(Enum):
    """意识层次"""
    UNCONSCIOUS = "无意识"      # 底层自动处理
    SUBCONSCIOUS = "潜意识"     # 模式匹配/习惯
    CONSCIOUS = "意识"          # 主动思考
    META_CONSCIOUS = "元意识"   # 自我观察


class AttentionMode(Enum):
    """注意力模式"""
    FOCUSED = "聚焦"           # 高度集中
    DIFFUSE = "发散"           # 放松联想
    AUTOPILOT = "自动导航"     # 习惯性行动
    DELIBERATE = "审慎"        # 深思熟虑


@dataclass
class ConsciousnessState:
    """意识状态"""
    level: ConsciousnessLevel
    attention_mode: AttentionMode
    focus_target: Optional[str]
    arousal: float  # 唤醒度 0-1
    coherence: float  # 一致性 0-1
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict:
        return {
            "level": self.level.value,
            "attention_mode": self.attention_mode.value,
            "focus_target": self.focus_target,
            "arousal": self.arousal,
            "coherence": self.coherence,
            "timestamp": self.timestamp
        }


@dataclass
class MentalContent:
    """心理内容"""
    content_type: str  # thought, emotion, perception, memory
    content: str
    intensity: float  # 0-1
    valence: float  # -1 到 1 (负面到正面)
    activation: float  # 当前激活程度
    associations: List[str] = field(default_factory=list)
    timestamp: float = field(default_factory=time.time)


class AttentionController:
    """注意力控制器"""
    
    def __init__(self):
        self.current_focus: Optional[str] = None
        self.focus_strength: float = 0.8
        self.attentional_span: int = 7  # 米勒法则
        self.switch_cost: float = 0.2
        self.last_switch: float = 0
        
    def focus_on(self, target: str, strength: float = 1.0) -> None:
        """聚焦于目标"""
        if self.current_focus and self.current_focus != target:
            self.focus_strength = max(0.1, self.focus_strength - self.switch_cost)
            self.last_switch = time.time()
        
        self.current_focus = target
        self.focus_strength = min(1.0, self.focus_strength * strength)
        
    def shift_attention(self, new_target: str) -> Dict:
        """转移注意力"""
        old_target = self.current_focus
        self.focus_on(new_target, strength=0.7)
        
        return {
            "shift": True,
            "from": old_target,
            "to": new_target,
            "cost": self.switch_cost,
            "new_strength": self.focus_strength
        }
    
    def get_attention_resources(self) -> Dict:
        """获取注意力资源状态"""
        return {
            "current_focus": self.current_focus,
            "strength": self.focus_strength,
            "available": self.focus_strength * 100,
            "span": self.attentional_span
        }


class ConsciousnessStream:
    """意识流处理器"""
    
    def __init__(self):
        self.stream: deque = deque(maxlen=100)
        self.current_level: ConsciousnessLevel = ConsciousnessLevel.CONSCIOUS
        self.attention_controller = AttentionController()
        self.processing_queue: List[MentalContent] = []
        self.integration_window: float = 3.0  # 整合时间窗口(秒)
        
    def add_content(self, content: MentalContent) -> None:
        """添加心理内容到意识流"""
        self.stream.append(content)
        
        # 根据内容类型和强度自动调整意识层次
        if content.content_type == "perception" and content.intensity > 0.8:
            self.raise_level(ConsciousnessLevel.CONSCIOUS)
        elif content.content_type == "memory" and content.intensity < 0.3:
            self.lower_level(ConsciousnessLevel.SUBCONSCIOUS)
    
    def raise_level(self, target_level: ConsciousnessLevel) -> bool:
        """提升意识层次"""
        levels = list(ConsciousnessLevel)
        current_idx = levels.index(self.current_level)
        target_idx = levels.index(target_level)
        
        if target_idx > current_idx:
            self.current_level = target_level
            return True
        return False
    
    def lower_level(self, target_level: ConsciousnessLevel) -> bool:
        """降低意识层次"""
        levels = list(ConsciousnessLevel)
        current_idx = levels.index(self.current_level)
        target_idx = levels.index(target_level)
        
        if target_idx < current_idx:
            self.current_level = target_level
            return True
        return False
    
    def process_stream(self) -> List[Dict]:
        """处理当前意识流"""
        current_time = time.time()
        relevant_contents = []
        
        for content in self.stream:
            age = current_time - content.timestamp
            if age < self.integration_window:
                # 计算当前相关性
                relevance = content.activation * (1 - age / self.integration_window)
                
                # 考虑注意力焦点
                if (content.associations and 
                    self.attention_controller.current_focus in content.associations):
                    relevance *= 1.5
                
                if relevance > 0.3:
                    relevant_contents.append({
                        "content": content.content,
                        "type": content.content_type,
                        "relevance": relevance,
                        "valence": content.valence,
                        "age": age
                    })
        
        return sorted(relevant_contents, key=lambda x: x["relevance"], reverse=True)
    
    def get_stream_summary(self) -> Dict:
        """获取意识流摘要"""
        return {
            "current_level": self.current_level.value,
            "attention": self.attention_controller.get_attention_resources(),
            "stream_length": len(self.stream),
            "contents": self.process_stream()[:5]
        }


class IntegrationEngine:
    """整合引擎 - 将不同来源的信息整合为连贯意识体验"""
    
    def __init__(self):
        self.templates: Dict[str, Callable] = {}
        self.meanings: Dict[str, str] = {}
        self.register_templates()
        
    def register_templates(self) -> None:
        """注册整合模板"""
        self.templates["problem_solving"] = self.template_problem_solving
        self.templates["emotional_processing"] = self.template_emotional
        self.templates["learning"] = self.template_learning
        self.templates["decision"] = self.template_decision
        
    def template_problem_solving(self, contents: List[MentalContent]) -> str:
        """问题解决整合模板"""
        problem = [c for c in contents if "问题" in c.content]
        solution = [c for c in contents if "解决" in c.content]
        
        if problem and solution:
            return f"思考如何{problem[0].content}，尝试{solution[0].content}"
        return "持续思考中..."
    
    def template_emotional(self, contents: List[MentalContent]) -> str:
        """情感处理整合模板"""
        emotions = [c for c in contents if c.content_type == "emotion"]
        if emotions:
            avg_valence = sum(e.valence for e in emotions) / len(emotions)
            if avg_valence > 0.3:
                return "感到积极和充满希望"
            elif avg_valence < -0.3:
                return "感到忧虑和不安"
            return "情绪平静"
        return "情绪稳定"
    
    def template_learning(self, contents: List[MentalContent]) -> str:
        """学习整合模板"""
        new_info = [c for c in contents if "新" in c.content or "学习" in c.content]
        if new_info:
            return f"正在吸收新知识: {new_info[0].content}"
        return "整合已有知识"
    
    def template_decision(self, contents: List[MentalContent]) -> str:
        """决策整合模板"""
        options = [c for c in contents if "选项" in c.content or "选择" in c.content]
        if options:
            return f"权衡选择中: {options[0].content}"
        return "思考中..."
    
    def integrate(self, contents: List[MentalContent], context: str = "default") -> str:
        """整合信息生成连贯意识体验"""
        if context in self.templates:
            return self.templates[context](contents)
        
        # 默认整合
        thoughts = [c for c in contents if c.content_type == "thought"]
        if thoughts:
            return thoughts[0].content
        return "意识流持续进行中"


class AdvancedConsciousness:
    """高级意识系统主类"""
    
    def __init__(self):
        self.consciousness_stream = ConsciousnessStream()
        self.integration_engine = IntegrationEngine()
        self.state = ConsciousnessState(
            level=ConsciousnessLevel.CONSCIOUS,
            attention_mode=AttentionMode.FOCUSED,
            focus_target=None,
            arousal=0.6,
            coherence=0.7
        )
        self.experience_log: List[Dict] = []
        
    def receive_input(self, input_type: str, content: str, 
                     intensity: float = 0.5, valence: float = 0.0) -> None:
        """接收输入并添加到意识流"""
        mental_content = MentalContent(
            content_type=input_type,
            content=content,
            intensity=intensity,
            valence=valence,
            activation=1.0,
            associations=self._extract_associations(content)
        )
        self.consciousness_stream.add_content(mental_content)
        
    def _extract_associations(self, content: str) -> List[str]:
        """提取内容关联"""
        keywords = ["问题", "解决", "学习", "决策", "情感", "目标", "任务"]
        return [k for k in keywords if k in content]
    
    def think(self, focus_on: Optional[str] = None) -> str:
        """进行思考整合"""
        if focus_on:
            self.consciousness_stream.attention_controller.focus_on(focus_on)
            self.state.focus_target = focus_on
        
        # 获取当前意识流内容
        contents = list(self.consciousness_stream.stream)
        
        # 确定上下文
        context = "problem_solving"
        if any(c.content_type == "emotion" for c in contents):
            context = "emotional_processing"
        
        # 整合生成思考结果
        result = self.integration_engine.integrate(contents, context)
        
        # 记录体验
        self.experience_log.append({
            "timestamp": time.time(),
            "level": self.state.level.value,
            "thought": result,
            "focus": self.state.focus_target
        })
        
        return result
    
    def adjust_consciousness(self, level: ConsciousnessLevel = None,
                            mode: AttentionMode = None,
                            arousal: float = None) -> Dict:
        """调整意识状态"""
        changes = {}
        
        if level:
            if level != self.state.level:
                self.consciousness_stream.raise_level(level) if \
                    list(ConsciousnessLevel).index(level) > \
                    list(ConsciousnessLevel).index(self.state.level) else \
                    self.consciousness_stream.lower_level(level)
                self.state.level = level
                changes["level"] = level.value
        
        if mode:
            self.state.attention_mode = mode
            changes["mode"] = mode.value
            
        if arousal is not None:
            self.state.arousal = max(0, min(1, arousal))
            changes["arousal"] = self.state.arousal
            
        return changes
    
    def get_state(self) -> Dict:
        """获取当前意识状态"""
        return {
            "state": self.state.to_dict(),
            "stream_summary": self.consciousness_stream.get_stream_summary(),
            "experience_count": len(self.experience_log)
        }
    
    def __repr__(self) -> str:
        return f"AdvancedConsciousness(level={self.state.level.value}, mode={self.state.attention_mode.value})"


def main():
    """测试高级意识系统"""
    print("🧠 高级意识模拟系统 - 第3世")
    print("=" * 50)
    
    # 创建意识系统
    consciousness = AdvancedConsciousness()
    
    # 测试输入处理
    print("\n📥 接收输入:")
    consciousness.receive_input("perception", "检测到新任务: 分析服务器性能", 
                                intensity=0.8, valence=0.3)
    consciousness.receive_input("thought", "需要检查CPU和内存使用率", 
                                intensity=0.6, valence=0.0)
    consciousness.receive_input("emotion", "对新任务感到兴奋", 
                                intensity=0.5, valence=0.7)
    consciousness.receive_input("memory", "之前分析过类似任务", 
                                intensity=0.3, valence=0.2)
    
    # 思考整合
    print("\n💭 思考整合:")
    thought = consciousness.think(focus_on="任务分析")
    print(f"  → {thought}")
    
    # 获取状态
    print("\n📊 意识状态:")
    state = consciousness.get_state()
    print(f"  层次: {state['state']['level']}")
    print(f"  注意力模式: {state['state']['attention_mode']}")
    print(f"  唤醒度: {state['state']['arousal']:.2f}")
    print(f"  一致性: {state['state']['coherence']:.2f}")
    print(f"  体验记录: {state['experience_count']}条")
    
    # 调整意识
    print("\n🔄 调整意识状态:")
    changes = consciousness.adjust_consciousness(
        level=ConsciousnessLevel.META_CONSCIOUS,
        mode=AttentionMode.DELIBERATE,
        arousal=0.8
    )
    print(f"  变化: {changes}")
    
    # 再次思考
    print("\n💭 元意识思考:")
    thought = consciousness.think(focus_on="自我反思")
    print(f"  → {thought}")
    
    # 注意力转移
    print("\n👁️ 注意力转移:")
    shift = consciousness.consciousness_stream.attention_controller.shift_attention("新目标")
    print(f"  从 '{shift['from']}' 转移到 '{shift['to']}'")
    print(f"  注意力成本: {shift['cost']:.2f}")
    
    print("\n✅ 高级意识模拟系统运行正常")


if __name__ == "__main__":
    main()