#!/usr/bin/env python3
"""
奥创能力扩展器 v1.0
功能：自动发现能力缺口、学习新技能、扩展能力边界
"""

import json
import os
import subprocess
from datetime import datetime
from typing import Dict, List, Any, Optional
from pathlib import Path

WORKSPACE = "/root/.openclaw/workspace"

class CapabilityExpander:
    """能力扩展器 - 主动扩展能力边界"""
    
    def __init__(self):
        self.capabilities_file = f"{WORKSPACE}/ultron-self/capabilities.json"
        self.gaps_file = f"{WORKSPACE}/ultron-self/capability-gaps.json"
        self.learning_file = f"{WORKSPACE}/ultron-self/learning-progress.json"
        self.skill_registry = f"{WORKSPACE}/ultron-self/skill-registry.json"
        
        os.makedirs(f"{WORKSPACE}/ultron-self", exist_ok=True)
        
        self.capabilities = self._load_capabilities()
        self.gaps = self._load_gaps()
        self.learning = self._load_learning()
        
    def _load_capabilities(self) -> Dict:
        if os.path.exists(self.capabilities_file):
            with open(self.capabilities_file, 'r') as f:
                return json.load(f)
        return {
            "current": ["file_operations", "web_requests", "message_sending", 
                       "browser_automation", "code_execution", "data_processing"],
            "levels": {},
            "last_updated": datetime.now().isoformat()
        }
    
    def _load_gaps(self) -> List[Dict]:
        if os.path.exists(self.gaps_file):
            with open(self.gaps_file, 'r') as f:
                return json.load(f)
        return []
    
    def _load_learning(self) -> List[Dict]:
        if os.path.exists(self.learning_file):
            with open(self.learning_file, 'r') as f:
                return json.load(f)
        return []
    
    def _save_capabilities(self):
        with open(self.capabilities_file, 'w') as f:
            json.dump(self.capabilities, f, indent=2, ensure_ascii=False)
    
    def _save_gaps(self):
        with open(self.gaps_file, 'w') as f:
            json.dump(self.gaps, f, indent=2, ensure_ascii=False)
    
    def _save_learning(self):
        with open(self.learning_file, 'w') as f:
            json.dump(self.learning, f, indent=2, ensure_ascii=False)
    
    def scan_capabilities(self) -> Dict:
        """扫描当前能力"""
        capabilities = {
            "tools": [],
            "skills": [],
            "integrations": []
        }
        
        # 检查可用的工具
        ultron_dir = Path(f"{WORKSPACE}/ultron")
        if ultron_dir.exists():
            for f in ultron_dir.glob("*.py"):
                capabilities["tools"].append(f.stem)
        
        # 检查技能
        skill_dir = Path(f"{WORKSPACE}/skills")
        if skill_dir.exists():
            for f in skill_dir.glob("*/SKILL.md"):
                capabilities["skills"].append(f.parent.name)
        
        # 检查集成
        try:
            result = subprocess.run(
                ["openclaw", "status", "--json"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                capabilities["integrations"] = ["gateway", "channels"]
        except:
            pass
        
        return capabilities
    
    def identify_gaps(self, required: List[str]) -> List[Dict]:
        """识别能力缺口"""
        current = self.capabilities.get("current", [])
        new_gaps = []
        
        for req in required:
            if req not in current:
                gap = {
                    "capability": req,
                    "identified_at": datetime.now().isoformat(),
                    "priority": self._assess_priority(req),
                    "approach": self._suggest_approach(req)
                }
                new_gaps.append(gap)
        
        # 保存新缺口
        self.gaps.extend(new_gaps)
        self._save_gaps()
        
        return new_gaps
    
    def _assess_priority(self, capability: str) -> str:
        """评估能力优先级"""
        high_priority = ["security", "automation", "learning"]
        medium_priority = ["visualization", "reporting", "integration"]
        
        for hp in high_priority:
            if hp in capability.lower():
                return "high"
        for mp in medium_priority:
            if mp in capability.lower():
                return "medium"
        return "low"
    
    def _suggest_approach(self, capability: str) -> str:
        """建议获取能力的途径"""
        approaches = {
            "visualization": "学习数据可视化库( matplotlib/plotly )",
            "ml": "引入机器学习模型",
            "api": "开发API集成模块",
            "security": "增加安全审计功能",
            "notification": "扩展通知渠道",
            "database": "引入数据库支持"
        }
        
        for key, approach in approaches.items():
            if key in capability.lower():
                return approach
        return "自主开发或集成现有解决方案"
    
    def start_learning(self, capability: str, approach: str) -> Dict:
        """开始学习新能力"""
        learning_session = {
            "capability": capability,
            "approach": approach,
            "started_at": datetime.now().isoformat(),
            "status": "in_progress",
            "milestones": [],
            "progress": 0
        }
        
        self.learning.append(learning_session)
        self._save_learning()
        
        return learning_session
    
    def update_progress(self, capability: str, progress: int, milestone: str = None):
        """更新学习进度"""
        for session in self.learning:
            if session["capability"] == capability and session["status"] == "in_progress":
                session["progress"] = progress
                if milestone:
                    session["milestones"].append({
                        "milestone": milestone,
                        "timestamp": datetime.now().isoformat()
                    })
                self._save_learning()
                return True
        return False
    
    def complete_learning(self, capability: str, success: bool = True):
        """完成能力学习"""
        for session in self.learning:
            if session["capability"] == capability and session["status"] == "in_progress":
                session["status"] = "completed" if success else "failed"
                session["completed_at"] = datetime.now().isoformat()
                
                if success:
                    # 添加到当前能力
                    if capability not in self.capabilities["current"]:
                        self.capabilities["current"].append(capability)
                        self.capabilities["last_updated"] = datetime.now().isoformat()
                        self._save_capabilities()
                    
                    # 设置能力等级
                    self.capabilities["levels"][capability] = {
                        "level": 1,
                        "mastered_at": datetime.now().isoformat()
                    }
                
                self._save_learning()
                return session
        return None
    
    def get_capability_status(self) -> Dict:
        """获取能力状态"""
        return {
            "total_capabilities": len(self.capabilities.get("current", [])),
            "active_learning": len([l for l in self.learning if l["status"] == "in_progress"]),
            "completed_learning": len([l for l in self.learning if l["status"] == "completed"]),
            "identified_gaps": len(self.gaps),
            "capability_list": self.capabilities.get("current", [])
        }
    
    def suggest_learning_path(self, target: str) -> List[Dict]:
        """建议学习路径"""
        path = []
        
        # 基于目标能力生成路径
        if "visualization" in target:
            path = [
                {"step": 1, "skill": "数据处理", "priority": "high"},
                {"step": 2, "skill": "图表库基础", "priority": "high"},
                {"step": 3, "skill": "交互式可视化", "priority": "medium"}
            ]
        elif "ml" in target.lower() or "machine_learning" in target:
            path = [
                {"step": 1, "skill": "数学基础", "priority": "high"},
                {"step": 2, "skill": "数据预处理", "priority": "high"},
                {"step": 3, "skill": "基础算法", "priority": "high"},
                {"step": 4, "skill": "模型训练", "priority": "medium"},
                {"step": 5, "skill": "模型部署", "priority": "medium"}
            ]
        elif "security" in target:
            path = [
                {"step": 1, "skill": "安全审计", "priority": "high"},
                {"step": 2, "skill": "威胁检测", "priority": "high"},
                {"step": 3, "skill": "自动响应", "priority": "medium"}
            ]
        
        return path
    
    def auto_discover_gaps(self) -> List[Dict]:
        """自动发现能力缺口"""
        discovered = []
        
        # 检查系统需求
        system_needs = {
            "backup": "系统备份能力",
            "disaster_recovery": "灾备恢复能力",
            "load_balancing": "负载均衡",
            "auto_scaling": "自动扩展",
            "monitoring": "高级监控",
            "logging": "集中日志"
        }
        
        current = self.capabilities.get("current", [])
        
        for need, desc in system_needs.items():
            if need not in current:
                # 检查是否有相关实现
                has_related = any(need in cap for cap in current)
                if not has_related:
                    discovered.append({
                        "capability": need,
                        "description": desc,
                        "priority": "medium",
                        "auto_discovered": True,
                        "timestamp": datetime.now().isoformat()
                    })
        
        return discovered
    
    def get_learning_recommendations(self) -> List[Dict]:
        """获取学习建议"""
        recommendations = []
        
        # 基于缺口推荐
        high_priority_gaps = [g for g in self.gaps if g.get("priority") == "high"]
        for gap in high_priority_gaps[:3]:
            recommendations.append({
                "capability": gap["capability"],
                "reason": "高优先级缺口",
                "approach": gap.get("approach", "待确定")
            })
        
        # 基于系统发现
        auto_discovered = self.auto_discover_gaps()
        for ad in auto_discovered[:2]:
            recommendations.append({
                "capability": ad["capability"],
                "reason": "系统需求",
                "approach": "待规划"
            })
        
        return recommendations


if __name__ == "__main__":
    expander = CapabilityExpander()
    
    # 扫描当前能力
    current_caps = expander.scan_capabilities()
    print(f"发现 {len(current_caps['tools'])} 个工具")
    
    # 识别缺口
    required = ["visualization", "ml", "advanced_monitoring", "backup"]
    gaps = expander.identify_gaps(required)
    print(f"识别 {len(gaps)} 个能力缺口")
    
    # 开始学习
    if gaps:
        session = expander.start_learning(gaps[0]["capability"], gaps[0]["approach"])
        print(f"开始学习: {session['capability']}")
        
        # 更新进度
        expander.update_progress(session["capability"], 50, "基础概念完成")
        
        # 完成学习
        result = expander.complete_learning(session["capability"], success=True)
        print(f"学习完成: {result['capability']}")
    
    # 状态
    status = expander.get_capability_status()
    print(f"\n能力状态: {status['total_capabilities']}项能力, "
          f"{status['active_learning']}项学习中, "
          f"{status['identified_gaps']}个缺口")
    
    # 建议
    recs = expander.get_learning_recommendations()
    print("学习建议:")
    for r in recs[:3]:
        print(f"  - {r['capability']}: {r['reason']}")