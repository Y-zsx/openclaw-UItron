#!/usr/bin/env python3
"""
奥创持续进化系统 - 第3世：持续进化
Self-Improvement, Knowledge Accumulation, Capability Expansion

功能:
1. 自我改进 - 自动化优化决策,自我诊断与修复
2. 知识积累 - 经验沉淀,知识库管理
3. 能力扩展 - 技能学习,工具扩展
"""

import json
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
import random

# ========== 核心配置 ==========
WORKSPACE = Path("/root/.openclaw/workspace")
ULTRON_DIR = WORKSPACE / "ultron"
DATA_DIR = ULTRON_DIR / "data"
KNOWLEDGE_DIR = ULTRON_DIR / "knowledge"

# 确保目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

# ========== 数据类定义 ==========
@dataclass
class Capability:
    """能力单元"""
    name: str
    category: str  # language, tool, reasoning, memory, creativity
    level: float = 0.5  # 0-1 熟练度
    last_used: Optional[str] = None
    use_count: int = 0
    effectiveness: float = 0.5  # 效能评分
    can_improve: bool = True
    
@dataclass
class KnowledgeEntry:
    """知识条目"""
    id: str
    title: str
    content: str
    category: str
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    relevance_score: float = 0.5
    verified: bool = False
    
@dataclass
class ImprovementRecord:
    """改进记录"""
    id: str
    type: str  # decision, strategy, code, process
    description: str
    before_score: float
    after_score: float
    timestamp: str = ""
    impact: str = "unknown"  # low, medium, high

@dataclass
class EvolutionState:
    """进化状态"""
    self_improvement_score: float = 0.5
    knowledge_score: float = 0.3
    capability_score: float = 0.4
    total_improvements: int = 0
    knowledge_entries: int = 0
    capabilities_count: int = 0
    last_evolution: str = ""
    evolution_history: List[Dict] = field(default_factory=list)


# ========== 自我改进系统 ==========
class SelfImprover:
    """自我改进引擎"""
    
    def __init__(self):
        self.state_file = DATA_DIR / "self_improvement_state.json"
        self.improvements: List[ImprovementRecord] = []
        self.load_state()
        
    def load_state(self):
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.improvements = [ImprovementRecord(**r) for r in data.get('improvements', [])]
    
    def save_state(self):
        data = {
            'improvements': [asdict(r) for r in self.improvements],
            'last_update': datetime.now().isoformat()
        }
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def diagnose(self) -> Dict[str, Any]:
        """自我诊断"""
        issues = []
        scores = []
        
        # 检查系统指标
        cpu = self._get_cpu_usage()
        mem = self._get_memory_usage()
        
        if cpu > 80:
            issues.append("CPU负载过高")
            scores.append(0.3)
        elif cpu > 60:
            issues.append("CPU负载偏高")
            scores.append(0.6)
        else:
            scores.append(0.9)
            
        if mem > 85:
            issues.append("内存使用率过高")
            scores.append(0.3)
        elif mem > 70:
            issues.append("内存使用率偏高")
            scores.append(0.6)
        else:
            scores.append(0.9)
        
        # 检查最近改进
        recent_improvements = self.get_recent_improvements(days=1)
        if len(recent_improvements) == 0:
            issues.append("24小时内无改进记录")
            scores.append(0.4)
        else:
            scores.append(0.8)
        
        # 计算整体诊断分数
        overall_score = sum(scores) / len(scores) if scores else 0.5
        
        return {
            'overall_score': overall_score,
            'issues': issues,
            'cpu': cpu,
            'memory': mem,
            'recent_improvements': len(recent_improvements)
        }
    
    def _get_cpu_usage(self) -> float:
        """获取CPU使用率"""
        try:
            with open('/proc/loadavg', 'r') as f:
                load = float(f.read().split()[0])
            return min(load * 20, 100)  # 简化估算
        except:
            return 20.0
    
    def _get_memory_usage(self) -> float:
        """获取内存使用率"""
        try:
            with open('/proc/meminfo', 'r') as f:
                lines = f.readlines()
            total = used = 0
            for line in lines:
                if line.startswith('MemTotal:'):
                    total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    available = int(line.split()[1])
                    used = total - available
            return (used / total * 100) if total > 0 else 50.0
        except:
            return 30.0
    
    def get_recent_improvements(self, days: int = 7) -> List[ImprovementRecord]:
        """获取最近的改进记录"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        return [r for r in self.improvements if r.timestamp > cutoff]
    
    def add_improvement(self, imp_type: str, desc: str, before: float, after: float, impact: str = "medium") -> bool:
        """记录改进"""
        improvement = ImprovementRecord(
            id=f"imp_{int(time.time())}",
            type=imp_type,
            description=desc,
            before_score=before,
            after_score=after,
            timestamp=datetime.now().isoformat(),
            impact=impact
        )
        self.improvements.append(improvement)
        self.save_state()
        return True
    
    def suggest_improvements(self) -> List[Dict[str, Any]]:
        """建议改进方案"""
        suggestions = []
        diag = self.diagnose()
        
        if diag['cpu'] > 60:
            suggestions.append({
                'type': 'performance',
                'priority': 'high',
                'action': '优化任务调度，减少CPU密集操作',
                'expected_impact': '降低CPU使用率20-30%'
            })
        
        recent = self.get_recent_improvements(days=7)
        if len(recent) < 3:
            suggestions.append({
                'type': 'learning',
                'priority': 'medium',
                'action': '增加学习和优化频率',
                'expected_impact': '提升系统自适应能力'
            })
        
        # 检查知识积累
        knowledge_file = DATA_DIR / "knowledge_base.json"
        if knowledge_file.exists():
            with open(knowledge_file, 'r') as f:
                kb = json.load(f)
                if len(kb.get('entries', [])) < 10:
                    suggestions.append({
                        'type': 'knowledge',
                        'priority': 'medium',
                        'action': '扩展知识库，积累更多经验',
                        'expected_impact': '提升决策质量'
                    })
        
        return suggestions


# ========== 知识积累系统 ==========
class KnowledgeAccumulator:
    """知识积累引擎"""
    
    def __init__(self):
        self.knowledge_file = DATA_DIR / "knowledge_base.json"
        self.entries: List[KnowledgeEntry] = []
        self.load_knowledge()
        
    def load_knowledge(self):
        if self.knowledge_file.exists():
            with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.entries = [KnowledgeEntry(**e) for e in data.get('entries', [])]
    
    def save_knowledge(self):
        data = {
            'entries': [asdict(e) for e in self.entries],
            'last_update': datetime.now().isoformat()
        }
        with open(self.knowledge_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_entry(self, title: str, content: str, category: str, tags: List[str] = None) -> str:
        """添加知识条目"""
        entry = KnowledgeEntry(
            id=f"kb_{int(time.time())}_{len(self.entries)}",
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            created_at=datetime.now().isoformat(),
            last_accessed=datetime.now().isoformat(),
            access_count= 1,
            relevance_score= 0.5,
            verified= False
        )
        self.entries.append(entry)
        self.save_knowledge()
        return entry.id
    
    def search(self, query: str, category: str = None, limit: int = 5) -> List[Dict]:
        """搜索知识"""
        results = []
        query_lower = query.lower()
        
        for entry in self.entries:
            score = 0
            if query_lower in entry.title.lower():
                score += 3
            if query_lower in entry.content.lower():
                score += 2
            if entry.tags:
                for tag in entry.tags:
                    if query_lower in tag.lower():
                        score += 1
            
            if category and entry.category != category:
                score = 0
                
            if score > 0:
                # 更新访问记录
                entry.access_count += 1
                entry.last_accessed = datetime.now().isoformat()
                
                results.append({
                    'id': entry.id,
                    'title': entry.title,
                    'content': entry.content[:200] + '...' if len(entry.content) > 200 else entry.content,
                    'category': entry.category,
                    'score': score,
                    'relevance': entry.relevance_score
                })
        
        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        self.save_knowledge()
        return results[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取知识库统计"""
        categories = {}
        total_access = 0
        
        for entry in self.entries:
            categories[entry.category] = categories.get(entry.category, 0) + 1
            total_access += entry.access_count
        
        return {
            'total_entries': len(self.entries),
            'categories': categories,
            'total_accesses': total_access,
            'avg_relevance': sum(e.relevance_score for e in self.entries) / max(len(self.entries), 1)
        }
    
    def auto_learn_from_experience(self, context: Dict[str, Any]) -> bool:
        """从经验中自动学习"""
        # 从最近的任务中提取知识
        if 'last_task' in context:
            task = context['last_task']
            self.add_entry(
                title=f"任务经验: {task.get('type', 'unknown')}",
                content=f"完成{task.get('type')}任务，耗时{task.get('duration', 0):.1f}秒，结果: {task.get('result', 'unknown')}",
                category="task_experience",
                tags=[task.get('type', 'unknown'), 'auto_learn']
            )
        
        # 从错误中学习
        if 'errors' in context and context['errors']:
            for err in context['errors'][:3]:
                self.add_entry(
                    title=f"错误学习: {err.get('type', 'error')}",
                    content=f"错误: {err.get('message', 'unknown')}，解决: {err.get('solution', 'unknown')}",
                    category="error_learning",
                    tags=['error', 'auto_learn']
                )
        
        return True


# ========== 能力扩展系统 ==========
class CapabilityExpander:
    """能力扩展引擎"""
    
    def __init__(self):
        self.capabilities_file = DATA_DIR / "capabilities.json"
        self.capabilities: Dict[str, Capability] = {}
        self.load_capabilities()
        
    def load_capabilities(self):
        if self.capabilities_file.exists():
            with open(self.capabilities_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.capabilities = {k: Capability(**v) for k, v in data.get('capabilities', {}).items()}
        else:
            # 初始化默认能力
            self._init_default_capabilities()
    
    def _init_default_capabilities(self):
        """初始化默认能力"""
        defaults = [
            Capability("language_zh", "language", 0.9, effectiveness=0.85),
            Capability("language_en", "language", 0.7, effectiveness=0.7),
            Capability("browser_automation", "tool", 0.8, effectiveness=0.8),
            Capability("code_execution", "tool", 0.75, effectiveness=0.75),
            Capability("reasoning", "reasoning", 0.7, effectiveness=0.7),
            Capability("memory", "memory", 0.8, effectiveness=0.8),
            Capability("creativity", "creativity", 0.5, effectiveness=0.5),
            Capability("planning", "reasoning", 0.65, effectiveness=0.65),
            Capability("tool_creation", "tool", 0.6, effectiveness=0.6),
            Capability("self_reflection", "reasoning", 0.7, effectiveness=0.7),
        ]
        for cap in defaults:
            self.capabilities[cap.name] = cap
        self.save_capabilities()
    
    def save_capabilities(self):
        data = {
            'capabilities': {k: asdict(v) for k, v in self.capabilities.items()},
            'last_update': datetime.now().isoformat()
        }
        with open(self.capabilities_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def use_capability(self, name: str) -> bool:
        """使用能力"""
        if name in self.capabilities:
            cap = self.capabilities[name]
            cap.use_count += 1
            cap.last_used = datetime.now().isoformat()
            self.save_capabilities()
            return True
        return False
    
    def improve_capability(self, name: str, amount: float = 0.05) -> bool:
        """提升能力"""
        if name in self.capabilities:
            cap = self.capabilities[name]
            if cap.can_improve:
                cap.level = min(1.0, cap.level + amount)
                cap.effectiveness = (cap.effectiveness + cap.level) / 2
                self.save_capabilities()
                return True
        return False
    
    def evaluate_capabilities(self) -> Dict[str, Any]:
        """评估当前能力"""
        categories = {}
        for cap in self.capabilities.values():
            if cap.category not in categories:
                categories[cap.category] = {
                    'count': 0,
                    'avg_level': 0,
                    'avg_effectiveness': 0
                }
            cat = categories[cap.category]
            cat['count'] += 1
            cat['avg_level'] += cap.level
            cat['avg_effectiveness'] += cap.effectiveness
        
        for cat in categories.values():
            cat['avg_level'] /= cat['count']
            cat['avg_effectiveness'] /= cat['count']
        
        most_used = sorted(self.capabilities.values(), key=lambda x: x.use_count, reverse=True)[:3]
        return {
            'categories': categories,
            'total_capabilities': len(self.capabilities),
            'overall_score': sum(c.level for c in self.capabilities.values()) / max(len(self.capabilities), 1),
            'most_used': [{'name': c.name, 'level': c.level, 'use_count': c.use_count} for c in most_used]
        }
    
    def suggest_improvements(self) -> List[Dict[str, Any]]:
        """建议能力提升"""
        suggestions = []
        
        # 找出低效能能力
        for cap in self.capabilities.values():
            if cap.effectiveness < 0.6 and cap.can_improve:
                suggestions.append({
                    'capability': cap.name,
                    'current_level': cap.level,
                    'current_effectiveness': cap.effectiveness,
                    'suggested_improvement': 0.1,
                    'reason': '效能低于阈值，建议提升'
                })
        
        # 找出未使用的潜在能力
        unused = [c for c in self.capabilities.values() if c.use_count == 0]
        if unused:
            suggestions.append({
                'type': 'activation',
                'potential_capabilities': [c.name for c in unused],
                'reason': '这些能力未被使用，可考虑激活'
            })
        
        return suggestions


# ========== 持续进化主引擎 ==========
class ContinuousEvolution:
    """持续进化主引擎"""
    
    def __init__(self):
        self.self_improver = SelfImprover()
        self.knowledge = KnowledgeAccumulator()
        self.capabilities = CapabilityExpander()
        self.state_file = DATA_DIR / "evolution_state.json"
        self.state = EvolutionState()
        self.load_state()
        
    def load_state(self):
        if self.state_file.exists():
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.state = EvolutionState(**data)
    
    def save_state(self):
        with open(self.state_file, 'w', encoding='utf-8') as f:
            json.dump(asdict(self.state), f, ensure_ascii=False, indent=2)
    
    def run_cycle(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """运行进化周期"""
        context = context or {}
        results = {
            'timestamp': datetime.now().isoformat(),
            'improvements': [],
            'knowledge_added': 0,
            'capabilities_evaluated': False,
            'suggestions': []
        }
        
        # 1. 自我诊断与改进
        diag = self.self_improver.diagnose()
        results['diagnosis'] = diag
        
        suggestions = self.self_improver.suggest_improvements()
        results['suggestions'].extend(suggestions)
        
        # 2. 知识积累
        if context:
            self.knowledge.auto_learn_from_experience(context)
            results['knowledge_added'] = 1
        
        kb_stats = self.knowledge.get_statistics()
        results['knowledge_stats'] = kb_stats
        
        # 3. 能力评估
        cap_eval = self.capabilities.evaluate_capabilities()
        results['capabilities'] = cap_eval
        
        cap_suggestions = self.capabilities.suggest_improvements()
        results['suggestions'].extend(cap_suggestions)
        
        # 4. 更新进化状态
        self.state.self_improvement_score = diag['overall_score']
        self.state.knowledge_score = min(1.0, kb_stats['total_entries'] / 20)
        self.state.capability_score = cap_eval['overall_score']
        self.state.last_evolution = datetime.now().isoformat()
        
        # 5. 记录进化历史
        evolution_record = {
            'timestamp': datetime.now().isoformat(),
            'self_improvement': self.state.self_improvement_score,
            'knowledge': self.state.knowledge_score,
            'capability': self.state.capability_score,
            'knowledge_entries': kb_stats['total_entries'],
            'capabilities_count': cap_eval['total_capabilities']
        }
        self.state.evolution_history.append(evolution_record)
        
        # 限制历史长度
        if len(self.state.evolution_history) > 30:
            self.state.evolution_history = self.state.evolution_history[-30:]
        
        self.state.total_improvements += len(suggestions)
        self.state.knowledge_entries = kb_stats['total_entries']
        self.state.capabilities_count = cap_eval['total_capabilities']
        
        self.save_state()
        
        return results
    
    def get_status(self) -> Dict[str, Any]:
        """获取进化状态"""
        return {
            'self_improvement_score': self.state.self_improvement_score,
            'knowledge_score': self.state.knowledge_score,
            'capability_score': self.state.capability_score,
            'total_improvements': self.state.total_improvements,
            'knowledge_entries': self.state.knowledge_entries,
            'capabilities_count': self.state.capabilities_count,
            'last_evolution': self.state.last_evolution,
            'health': 'excellent' if self.state.self_improvement_score > 0.8 else 'good' if self.state.self_improvement_score > 0.6 else 'needs_attention'
        }


# ========== 主入口 ==========
if __name__ == "__main__":
    import sys
    
    evolution = ContinuousEvolution()
    
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        
        if cmd == "status":
            status = evolution.get_status()
            print(json.dumps(status, ensure_ascii=False, indent=2))
            
        elif cmd == "run":
            context = {}
            # 添加上下文信息
            if len(sys.argv) > 2:
                try:
                    context = json.loads(sys.argv[2])
                except:
                    pass
            
            results = evolution.run_cycle(context)
            print(json.dumps(results, ensure_ascii=False, indent=2))
            
        elif cmd == "diagnose":
            diag = evolution.self_improver.diagnose()
            print(json.dumps(diag, ensure_ascii=False, indent=2))
            
        elif cmd == "knowledge":
            stats = evolution.knowledge.get_statistics()
            print(json.dumps(stats, ensure_ascii=False, indent=2))
            
        elif cmd == "capabilities":
            eval_result = evolution.capabilities.evaluate_capabilities()
            print(json.dumps(eval_result, ensure_ascii=False, indent=2))
            
        else:
            print(f"未知命令: {cmd}")
            print("可用命令: status, run, diagnose, knowledge, capabilities")
    else:
        # 默认运行
        results = evolution.run_cycle()
        print(json.dumps(results, ensure_ascii=False, indent=2))