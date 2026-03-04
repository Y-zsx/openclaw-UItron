#!/usr/bin/env python3
"""
经验提取器 (Experience Extractor)
结构化存储和检索经验，支持跨任务学习

功能：
- 经验抽取与结构化
- 经验存储与索引
- 经验检索与推荐
- 知识关联发现
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path
from collections import defaultdict
import hashlib

class ExperienceExtractor:
    """经验提取器 - 从任务中提取可复用经验"""
    
    def __init__(self, workspace: str = "/root/.openclaw/workspace"):
        self.workspace = workspace
        self.experience_dir = f"{workspace}/ultron/experiences"
        self.index_file = f"{self.experience_dir}/index.json"
        self.experiences_file = f"{self.experience_dir}/experiences.json"
        
        # 确保目录存在
        os.makedirs(self.experience_dir, exist_ok=True)
        
        # 加载数据
        self.index = self._load_index()
        self.experiences = self._load_experiences()
    
    def _load_index(self) -> Dict:
        """加载索引"""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                return json.load(f)
        return {
            "by_category": {},
            "by_tool": {},
            "by_outcome": {},
            "by_time": {},
            "tags": defaultdict(list)
        }
    
    def _load_experiences(self) -> List[Dict]:
        """加载经验库"""
        if os.path.exists(self.experiences_file):
            with open(self.experiences_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_index(self):
        """保存索引"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2, ensure_ascii=False)
    
    def _save_experiences(self):
        """保存经验库"""
        with open(self.experiences_file, 'w') as f:
            json.dump(self.experiences, f, indent=2, ensure_ascii=False)
    
    def extract_from_task(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        从任务数据中提取经验
        
        task_data 结构:
        {
            "task_id": "xxx",
            "description": "任务描述",
            "tools_used": ["tool1", "tool2"],
            "steps": ["步骤1", "步骤2"],
            "success": true/false,
            "result": "结果描述",
            "errors": [],
            "duration": 120,
            "context": {}
        }
        """
        experience = {
            "id": self._generate_id(task_data),
            "timestamp": datetime.now().isoformat(),
            "description": task_data.get("description", ""),
            "success": task_data.get("success", False),
            "duration": task_data.get("duration", 0),
            
            # 核心经验
            "key_insight": self._extract_key_insight(task_data),
            "actionable_knowledge": self._extract_actionable_knowledge(task_data),
            "pattern": self._identify_pattern(task_data),
            
            # 分类信息
            "category": self._categorize(task_data),
            "tools": task_data.get("tools_used", []),
            "tags": self._extract_tags(task_data),
            
            # 可复用部分
            "success_formula": self._extract_success_formula(task_data),
            "failure_traps": self._extract_failure_traps(task_data),
            "best_practices": self._extract_best_practices(task_data),
            
            # 上下文
            "context": task_data.get("context", {}),
            "steps": task_data.get("steps", [])
        }
        
        # 存储经验
        self.experiences.append(experience)
        
        # 更新索引
        self._update_index(experience)
        
        self._save_experiences()
        self._save_index()
        
        return experience
    
    def _generate_id(self, task_data: Dict) -> str:
        """生成唯一ID"""
        content = f"{task_data.get('description', '')}{datetime.now().isoformat()}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _extract_key_insight(self, task_data: Dict) -> str:
        """提取关键洞察"""
        success = task_data.get("success", False)
        
        if success:
            # 从成功中提取洞察
            tools = task_data.get("tools_used", [])
            steps = task_data.get("steps", [])
            
            if len(steps) > 0:
                return f"通过{' + '.join(steps[:3])}成功完成任务"
            
            if tools:
                return f"使用{tools[0]}等工具组合达成目标"
            
            return "任务执行成功"
        else:
            # 从失败中提取洞察
            errors = task_data.get("errors", [])
            if errors:
                return f"失败原因: {errors[0][:100]}"
            return "任务执行失败，原因未明"
    
    def _extract_actionable_knowledge(self, task_data: Dict) -> List[str]:
        """提取可操作的知识"""
        knowledge = []
        
        success = task_data.get("success", False)
        tools = task_data.get("tools_used", [])
        
        if success:
            if "browser" in str(tools):
                knowledge.append("浏览器自动化适用于复杂交互任务")
            if "exec" in str(tools):
                knowledge.append("命令行适合系统级操作")
            if "message" in str(tools):
                knowledge.append("消息发送适合通知场景")
            
            # 添加通用知识
            knowledge.append("分步执行比一步到位更可靠")
            knowledge.append("错误处理是稳定性的关键")
        else:
            errors = task_data.get("errors", [])
            if errors:
                for error in errors[:2]:
                    knowledge.append(f"注意: {error[:80]}")
            
            knowledge.append("失败时要记录完整上下文")
        
        return knowledge
    
    def _identify_pattern(self, task_data: Dict) -> str:
        """识别模式"""
        task_type = task_data.get("task_type", "")
        
        # 基于工具组合识别模式
        tools = task_data.get("tools_used", [])
        tool_combo = "+".join(sorted(tools[:2])) if tools else "none"
        
        return tool_combo
    
    def _categorize(self, task_data: Dict) -> str:
        """分类任务"""
        desc = task_data.get("description", "").lower()
        tools = task_data.get("tools_used", [])
        
        if any(t in str(tools) for t in ["browser", "web"]):
            return "web_automation"
        elif any(t in str(tools) for t in ["exec", "shell"]):
            return "system_operation"
        elif any(t in str(tools) for t in ["message", "send"]):
            return "communication"
        elif "file" in desc or "read" in desc or "write" in desc:
            return "file_operation"
        else:
            return "general"
    
    def _extract_tags(self, task_data: Dict) -> List[str]:
        """提取标签"""
        tags = []
        
        # 从描述中提取
        desc = task_data.get("description", "").lower()
        keywords = ["自动化", "监控", "分析", "处理", "获取", "发送", "创建", "更新"]
        tags.extend([k for k in keywords if k in desc])
        
        # 从工具中提取
        tools = task_data.get("tools_used", [])
        tags.extend([t for t in tools if t])
        
        # 从结果中提取
        if task_data.get("success"):
            tags.append("成功")
        else:
            tags.append("失败")
        
        return list(set(tags))[:10]  # 限制标签数量
    
    def _extract_success_formula(self, task_data: Dict) -> str:
        """提取成功公式"""
        if not task_data.get("success"):
            return ""
        
        steps = task_data.get("steps", [])
        tools = task_data.get("tools_used", [])
        
        if steps:
            return " → ".join(steps[:5])
        elif tools:
            return " + ".join(tools)
        
        return "按预期完成"
    
    def _extract_failure_traps(self, task_data: Dict) -> List[str]:
        """提取失败陷阱"""
        if task_data.get("success"):
            return []
        
        errors = task_data.get("errors", [])
        traps = []
        
        for error in errors:
            if "timeout" in error.lower():
                traps.append("超时未处理")
            if "permission" in error.lower():
                traps.append("权限检查不足")
            if "not found" in error.lower():
                traps.append("前置条件验证缺失")
            if "null" in error.lower() or "undefined" in error.lower():
                traps.append("空值处理缺失")
        
        return traps if traps else ["未知错误"]
    
    def _extract_best_practices(self, task_data: Dict) -> List[str]:
        """提取最佳实践"""
        practices = []
        
        if task_data.get("success"):
            practices.extend([
                "记录成功模式",
                "保持工具调用一致性",
                "添加适当的错误处理"
            ])
        
        # 基于工具的实践
        tools = task_data.get("tools_used", [])
        if "browser" in tools:
            practices.append("浏览器操作后验证页面状态")
        if "exec" in tools:
            practices.append("命令执行后检查返回码")
        
        return practices
    
    def _update_index(self, experience: Dict):
        """更新索引"""
        # 按类别索引
        category = experience.get("category", "general")
        if category not in self.index["by_category"]:
            self.index["by_category"][category] = []
        self.index["by_category"][category].append(experience["id"])
        
        # 按工具索引
        for tool in experience.get("tools", []):
            if tool not in self.index["by_tool"]:
                self.index["by_tool"][tool] = []
            self.index["by_tool"][tool].append(experience["id"])
        
        # 按结果索引
        outcome = "success" if experience.get("success") else "failure"
        if outcome not in self.index["by_outcome"]:
            self.index["by_outcome"][outcome] = []
        self.index["by_outcome"][outcome].append(experience["id"])
        
        # 按时间索引
        time_key = experience["timestamp"][:10]  # YYYY-MM-DD
        if time_key not in self.index["by_time"]:
            self.index["by_time"][time_key] = []
        self.index["by_time"][time_key].append(experience["id"])
        
        # 标签索引
        for tag in experience.get("tags", []):
            self.index["tags"][tag].append(experience["id"])
    
    def search(self, query: str, filters: Optional[Dict] = None) -> List[Dict]:
        """搜索经验"""
        results = []
        query = query.lower()
        
        for exp in self.experiences:
            # 文本匹配
            matches = (
                query in exp.get("description", "").lower() or
                query in exp.get("key_insight", "").lower() or
                any(query in tag.lower() for tag in exp.get("tags", []))
            )
            
            # 应用过滤器
            if filters:
                if "category" in filters and exp.get("category") != filters["category"]:
                    continue
                if "tools" in filters and not any(t in exp.get("tools", []) for t in filters["tools"]):
                    continue
                if "success" in filters and exp.get("success") != filters["success"]:
                    continue
            
            if matches:
                results.append(exp)
        
        # 按时间排序
        results.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return results
    
    def get_by_category(self, category: str) -> List[Dict]:
        """按类别获取经验"""
        ids = self.index["by_category"].get(category, [])
        return [e for e in self.experiences if e["id"] in ids]
    
    def get_by_tool(self, tool: str) -> List[Dict]:
        """按工具获取经验"""
        ids = self.index["by_tool"].get(tool, [])
        return [e for e in self.experiences if e["id"] in ids]
    
    def get_success_patterns(self) -> List[Dict]:
        """获取成功模式"""
        return [e for e in self.experiences if e.get("success")]
    
    def get_failure_patterns(self) -> List[Dict]:
        """获取失败模式"""
        return [e for e in self.experiences if not e.get("success")]
    
    def get_recommendations(self, context: Dict) -> List[Dict]:
        """基于上下文获取推荐"""
        recommendations = []
        
        # 基于工具推荐
        current_tools = context.get("tools_used", [])
        for tool in current_tools:
            similar = self.get_by_tool(tool)
            recommendations.extend(similar[:3])
        
        # 基于类别推荐
        category = context.get("category", "general")
        category_exp = self.get_by_category(category)
        recommendations.extend(category_exp[:3])
        
        # 去重
        seen = set()
        unique = []
        for r in recommendations:
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)
        
        return unique[:10]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        total = len(self.experiences)
        success = sum(1 for e in self.experiences if e.get("success"))
        
        tool_counts = defaultdict(int)
        for e in self.experiences:
            for tool in e.get("tools", []):
                tool_counts[tool] += 1
        
        return {
            "total_experiences": total,
            "success_count": success,
            "failure_count": total - success,
            "success_rate": success / total if total > 0 else 0,
            "top_tools": dict(sorted(tool_counts.items(), key=lambda x: x[1], reverse=True)[:5]),
            "categories": {k: len(v) for k, v in self.index["by_category"].items()}
        }
    
    def export_knowledge(self, format: str = "markdown") -> str:
        """导出知识为指定格式"""
        if format == "markdown":
            return self._export_markdown()
        elif format == "json":
            return json.dumps(self.experiences, indent=2, ensure_ascii=False)
        else:
            return ""
    
    def _export_markdown(self) -> str:
        """导出为Markdown"""
        lines = ["# 经验知识库\n"]
        
        # 按类别组织
        for category, ids in self.index["by_category"].items():
            lines.append(f"## {category}\n")
            for exp in self.experiences:
                if exp["id"] in ids:
                    lines.append(f"### {exp['key_insight']}")
                    lines.append(f"- 时间: {exp['timestamp']}")
                    lines.append(f"- 成功: {'是' if exp['success'] else '否'}")
                    if exp.get("actionable_knowledge"):
                        lines.append("- 可操作知识:")
                        for k in exp["actionable_knowledge"]:
                            lines.append(f"  - {k}")
                    lines.append("")
        
        return "\n".join(lines)


# CLI 入口
if __name__ == "__main__":
    import sys
    
    extractor = ExperienceExtractor()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "stats":
            print(json.dumps(extractor.get_stats(), indent=2, ensure_ascii=False))
        elif sys.argv[1] == "success":
            print(json.dumps(extractor.get_success_patterns()[:5], indent=2, ensure_ascii=False))
        elif sys.argv[1] == "failure":
            print(json.dumps(extractor.get_failure_patterns()[:5], indent=2, ensure_ascii=False))
        elif sys.argv[1] == "search" and len(sys.argv) > 2:
            results = extractor.search(sys.argv[2])
            print(json.dumps(results[:5], indent=2, ensure_ascii=False))
        elif sys.argv[1] == "export":
            print(extractor.export_knowledge("markdown"))
        else:
            print("用法: python experience-extractor.py [stats|success|failure|search <query>|export]")
    else:
        print("经验提取器 v1.0")
        stats = extractor.get_stats()
        print(f"总经验数: {stats['total_experiences']}")
        print(f"成功率: {stats['success_rate']*100:.1f}%")