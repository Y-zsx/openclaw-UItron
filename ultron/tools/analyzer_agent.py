#!/usr/bin/env python3
"""
分析Agent (Analyzer Agent)
多智能体协作网络 - 第16世核心组件

职责:
- 分析任务请求，提取关键信息
- 数据分析与模式识别
- 问题诊断与根因分析
- 决策建议生成
"""

import json
import time
import re
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


# ===== Agent基础类型 (内联避免依赖) =====

class AgentState(Enum):
    """智能体状态"""
    CREATED = "created"
    ACTIVE = "active"
    IDLE = "idle"
    PROCESSING = "processing"
    ERROR = "error"


class AgentType(Enum):
    """智能体类型"""
    GENERAL = "general"
    COORDINATOR = "coordinator"
    MONITOR = "monitor"
    EXECUTOR = "executor"
    ANALYZER = "analyzer"


class AnalysisDepth(Enum):
    """分析深度"""
    SURFACE = "surface"       # 表面分析
    DETAILED = "detailed"     # 详细分析
    DEEP = "deep"             # 深度分析


class AnalysisType(Enum):
    """分析类型"""
    TASK = "task"             # 任务分析
    DATA = "data"             # 数据分析
    PROBLEM = "problem"       # 问题分析
    PATTERN = "pattern"       # 模式分析
    DECISION = "decision"     # 决策分析


@dataclass
class AnalysisResult:
    """分析结果"""
    analysis_type: AnalysisType
    depth: AnalysisDepth
    findings: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    confidence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class AnalyzerAgent:
    """分析Agent - 智能数据分析与问题诊断"""
    
    def __init__(self, name: str = "Analyzer"):
        self.name = name
        self.agent_type = AgentType.ANALYZER
        self.state = AgentState.ACTIVE
        self.analysis_count = 0
        self.total_analysis_time = 0.0
        self.analysis_history: List[AnalysisResult] = []
        
        # 分析模式库
        self.patterns = {
            "error_patterns": [
                r"(error|错误|失败|failed|exception)",
                r"(\d{3,}|timeout|timeout)",
                r"(permission|denied|拒绝)",
            ],
            "priority_patterns": [
                r"(紧急|urgent|重要|critical)",
                r"(立即|immediately|马上|asap)",
            ],
            "complexity_patterns": [
                r"(复杂|complex|困难|difficult)",
                r"(简单|simple|容易|easy)",
            ]
        }
        
    def analyze(self, data: Any, analysis_type: AnalysisType = AnalysisType.TASK,
                depth: AnalysisDepth = AnalysisDepth.DETAILED) -> AnalysisResult:
        """执行分析"""
        start_time = time.time()
        
        if analysis_type == AnalysisType.TASK:
            result = self._analyze_task(data, depth)
        elif analysis_type == AnalysisType.DATA:
            result = self._analyze_data(data, depth)
        elif analysis_type == AnalysisType.PROBLEM:
            result = self._analyze_problem(data, depth)
        elif analysis_type == AnalysisType.PATTERN:
            result = self._analyze_pattern(data, depth)
        elif analysis_type == AnalysisType.DECISION:
            result = self._analyze_decision(data, depth)
        else:
            result = AnalysisResult(analysis_type, depth, ["Unknown analysis type"], confidence=0.0)
        
        # 记录指标
        analysis_time = time.time() - start_time
        self.analysis_count += 1
        self.total_analysis_time += analysis_time
        self.analysis_history.append(result)
        
        return result
    
    def _analyze_task(self, task: Any, depth: AnalysisDepth) -> AnalysisResult:
        """任务分析 - 解析任务请求"""
        findings = []
        recommendations = []
        
        if isinstance(task, dict):
            # 提取任务信息
            task_desc = task.get("description", str(task))
            task_type = task.get("type", "unknown")
            
            findings.append(f"任务类型: {task_type}")
            
            # 优先级分析
            priority = self._detect_priority(task_desc)
            findings.append(f"优先级: {priority}")
            
            # 复杂度分析
            complexity = self._analyze_complexity(task_desc)
            findings.append(f"复杂度: {complexity}")
            
            # 依赖分析
            dependencies = task.get("dependencies", [])
            if dependencies:
                findings.append(f"依赖任务: {len(dependencies)}个")
            else:
                findings.append("无依赖任务")
            
            # 建议
            if priority == "高":
                recommendations.append("建议立即处理")
            if complexity == "高":
                recommendations.append("建议分步执行")
                
        elif isinstance(task, str):
            # 简单字符串任务
            priority = self._detect_priority(task)
            complexity = self._analyze_complexity(task)
            
            findings.append(f"优先级: {priority}")
            findings.append(f"复杂度: {complexity}")
            
            if priority == "高":
                recommendations.append("高优先级任务")
            if complexity == "高":
                recommendations.append("需要详细规划")
        
        confidence = min(0.5 + (len(findings) * 0.1), 0.95)
        
        return AnalysisResult(
            analysis_type=AnalysisType.TASK,
            depth=depth,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence,
            metadata={"task": str(task)[:100]}
        )
    
    def _analyze_data(self, data: Any, depth: AnalysisDepth) -> AnalysisResult:
        """数据分析 - 数据质量与模式"""
        findings = []
        recommendations = []
        
        if isinstance(data, dict):
            findings.append(f"数据类型: 字典, 键数: {len(data)}")
            
            # 数据质量检查
            null_count = sum(1 for v in data.values() if v is None)
            if null_count > 0:
                findings.append(f"空值数量: {null_count}")
                recommendations.append("建议处理空值")
            else:
                findings.append("数据完整性: 良好")
                
        elif isinstance(data, list):
            findings.append(f"数据类型: 列表, 元素数: {len(data)}")
            
            if len(data) > 0:
                elem_type = type(data[0]).__name__
                findings.append(f"元素类型: {elem_type}")
                
        elif isinstance(data, str):
            findings.append(f"数据类型: 字符串, 长度: {len(data)}")
            
        confidence = 0.8
        
        return AnalysisResult(
            analysis_type=AnalysisType.DATA,
            depth=depth,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence
        )
    
    def _analyze_problem(self, problem: Any, depth: AnalysisDepth) -> AnalysisResult:
        """问题分析 - 根因诊断"""
        findings = []
        recommendations = []
        
        problem_str = str(problem)
        
        # 错误类型识别
        if re.search(r"timeout|超时", problem_str, re.I):
            findings.append("问题类型: 超时")
            recommendations.append("检查网络连接或增加超时时间")
        elif re.search(r"permission|denied|权限", problem_str, re.I):
            findings.append("问题类型: 权限不足")
            recommendations.append("检查访问权限设置")
        elif re.search(r"not found|不存在", problem_str, re.I):
            findings.append("问题类型: 资源不存在")
            recommendations.append("验证资源路径或创建缺失资源")
        elif re.search(r"error|错误|失败", problem_str, re.I):
            findings.append("问题类型: 一般错误")
            recommendations.append("查看详细错误日志")
            
        # 严重程度评估
        if "critical" in problem_str.lower() or "严重" in problem_str:
            findings.append("严重程度: 高")
            recommendations.append("需要立即处理")
        else:
            findings.append("严重程度: 中")
            
        confidence = 0.75
        
        return AnalysisResult(
            analysis_type=AnalysisType.PROBLEM,
            depth=depth,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence
        )
    
    def _analyze_pattern(self, data: Any, depth: AnalysisDepth) -> AnalysisResult:
        """模式分析 - 识别规律"""
        findings = []
        recommendations = []
        
        # 检查是否有明显的模式
        if isinstance(data, list) and len(data) > 1:
            # 尝试检测序列模式
            try:
                if all(isinstance(x, (int, float)) for x in data):
                    # 数值序列
                    diffs = [data[i+1] - data[i] for i in range(len(data)-1)]
                    if len(set(diffs)) == 1:
                        findings.append("模式: 等差数列")
                        recommendations.append("可用等差公式预测")
                    elif len(set(diffs)) == 1:
                        findings.append("模式: 等比数列")
                    else:
                        findings.append("模式: 无明显规律")
            except:
                findings.append("模式检测失败")
                
        confidence = 0.65
        
        return AnalysisResult(
            analysis_type=AnalysisType.PATTERN,
            depth=depth,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence
        )
    
    def _analyze_decision(self, context: Any, depth: AnalysisDepth) -> AnalysisResult:
        """决策分析 - 提供建议"""
        findings = []
        recommendations = []
        
        if isinstance(context, dict):
            options = context.get("options", [])
            criteria = context.get("criteria", {})
            
            if options:
                findings.append(f"决策选项数: {len(options)}")
                recommendations.append(f"建议选择: {options[0]}")
            if criteria:
                findings.append(f"决策标准数: {len(criteria)}")
                
        confidence = 0.7
        
        return AnalysisResult(
            analysis_type=AnalysisType.DECISION,
            depth=depth,
            findings=findings,
            recommendations=recommendations,
            confidence=confidence
        )
    
    def _detect_priority(self, text: str) -> str:
        """检测优先级"""
        text_lower = text.lower()
        if any(p in text_lower for p in ["紧急", "urgent", "重要", "critical", "立即", "asap"]):
            return "高"
        elif any(p in text_lower for p in ["普通", "normal", "一般"]):
            return "中"
        return "低"
    
    def _analyze_complexity(self, text: str) -> str:
        """分析复杂度"""
        text_lower = text.lower()
        if any(p in text_lower for p in ["复杂", "complex", "困难", "difficult", "多步"]):
            return "高"
        elif any(p in text_lower for p in ["简单", "simple", "容易", "easy"]):
            return "低"
        return "中"
    
    def get_metrics(self) -> Dict[str, Any]:
        """获取指标"""
        return {
            "name": self.name,
            "agent_type": self.agent_type.value,
            "state": self.state.value,
            "analysis_count": self.analysis_count,
            "total_analysis_time": round(self.total_analysis_time, 2),
            "avg_analysis_time": round(self.total_analysis_time / max(self.analysis_count, 1), 2),
        }


def main():
    """测试运行"""
    print("=" * 50)
    print("Analyzer Agent 测试")
    print("=" * 50)
    
    analyzer = AnalyzerAgent("TestAnalyzer")
    
    # 测试任务分析
    print("\n[1] 任务分析测试")
    task_result = analyzer.analyze({
        "description": "紧急修复服务器超时问题",
        "type": "maintenance",
        "dependencies": ["backup"]
    }, AnalysisType.TASK)
    
    print(f"类型: {task_result.analysis_type.value}")
    print(f"发现: {task_result.findings}")
    print(f"建议: {task_result.recommendations}")
    print(f"置信度: {task_result.confidence}")
    
    # 测试问题分析
    print("\n[2] 问题分析测试")
    problem_result = analyzer.analyze("Error: Connection timeout after 30s", AnalysisType.PROBLEM)
    print(f"发现: {problem_result.findings}")
    print(f"建议: {problem_result.recommendations}")
    
    # 测试数据分析
    print("\n[3] 数据分析测试")
    data_result = analyzer.analyze({"name": "test", "value": 123, "status": None}, AnalysisType.DATA)
    print(f"发现: {data_result.findings}")
    
    # 打印指标
    print("\n[4] Agent指标")
    print(json.dumps(analyzer.get_metrics(), indent=2, ensure_ascii=False))
    
    print("\n✅ Analyzer Agent 测试完成")


if __name__ == "__main__":
    main()