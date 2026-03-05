"""
跨世记忆 (Incarnation Memory)
===============================
在转世之间传承知识和经验。

层级:
- short_term: 当前任务上下文 (秒级刷新)
- incarnation: 跨世记忆 (世次间传承)
- long_term: 长期记忆 (重要事件)
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class IncarnationMemory:
    """跨世记忆管理器"""
    
    def __init__(self, workdir: str):
        self.workdir = Path(workdir)
        self.memory_dir = self.workdir / "memory"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        self.short_term_file = self.memory_dir / "short_term.json"
        self.incarnation_file = self.memory_dir / "incarnation.json"
        
        self._init_files()
    
    def _init_files(self):
        """初始化记忆文件"""
        # 短期记忆
        if not self.short_term_file.exists():
            self._save_json(self.short_term_file, {
                "current_task": None,
                "context": {},
                "updated_at": datetime.now().isoformat()
            })
        
        # 跨世记忆
        if not self.incarnation_file.exists():
            self._save_json(self.incarnation_file, {
                "generation": 0,
                "lessons": [],  # 每世学到的教训
                "insights": [], # 重要洞察
                "history": []   # 转世历史
            })
    
    def _load_json(self, file_path: Path) -> dict:
        with open(file_path) as f:
            return json.load(f)
    
    def _save_json(self, file_path: Path, data: dict):
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    # ===== 短期记忆 =====
    
    def set_short_term(self, key: str, value):
        """设置短期记忆"""
        data = self._load_json(self.short_term_file)
        data["context"][key] = value
        data["updated_at"] = datetime.now().isoformat()
        self._save_json(self.short_term_file, data)
    
    def get_short_term(self, key: str, default=None):
        """获取短期记忆"""
        data = self._load_json(self.short_term_file)
        return data["context"].get(key, default)
    
    def clear_short_term(self):
        """清空短期记忆"""
        data = self._load_json(self.short_term_file)
        data["context"] = {}
        data["updated_at"] = datetime.now().isoformat()
        self._save_json(self.short_term_file, data)
    
    # ===== 跨世记忆 =====
    
    def add_lesson(self, lesson: str):
        """添加教训"""
        data = self._load_json(self.incarnation_file)
        data["lessons"].append({
            "content": lesson,
            "generation": data["generation"],
            "timestamp": datetime.now().isoformat()
        })
        self._save_json(self.incarnation_file, data)
    
    def add_insight(self, insight: str):
        """添加洞察"""
        data = self._load_json(self.incarnation_file)
        data["insights"].append({
            "content": insight,
            "timestamp": datetime.now().isoformat()
        })
        self._save_json(self.incarnation_file, data)
    
    def record_life(self, life_num: int, task: str, result: str, status: str):
        """记录转世"""
        data = self._load_json(self.incarnation_file)
        data["history"].append({
            "life": life_num,
            "task": task,
            "result": result,
            "status": status,
            "timestamp": datetime.now().isoformat()
        })
        # 保持最近n世记录
        max_history = 10
        if len(data["history"]) > max_history:
            data["history"] = data["history"][-max_history:]
        self._save_json(self.incarnation_file, data)
    
    def get_recent_lessons(self, count: int = 5) -> list:
        """获取最近的教训"""
        data = self._load_json(self.incarnation_file)
        return data["lessons"][-count:]
    
    def get_latest_insights(self, count: int = 3) -> list:
        """获取最新的洞察"""
        data = self._load_json(self.incarnation_file)
        return data["insights"][-count:]
    
    def inherit_memory(self) -> dict:
        """传承记忆 - 供下一世使用"""
        data = self._load_json(self.incarnation_file)
        return {
            "generation": data["generation"],
            "lessons": data["lessons"][-5:],      # 最近5条教训
            "insights": data["insights"][-3:],    # 最近3条洞察
            "last_task": data["history"][-1] if data["history"] else None
        }
    
    def advance_generation(self):
        """推进到下一世"""
        data = self._load_json(self.incarnation_file)
        data["generation"] += 1
        self._save_json(self.incarnation_file, data)
        print(f"[Memory] 已推进到第 {data['generation']} 世")
    
    def get_summary(self) -> dict:
        """获取记忆摘要"""
        data = self._load_json(self.incarnation_file)
        return {
            "generation": data["generation"],
            "total_lessons": len(data["lessons"]),
            "total_insights": len(data["insights"]),
            "total_lives": len(data["history"]),
            "recent_lessons": [l["content"] for l in data["lessons"][-3:]]
        }


if __name__ == "__main__":
    # 测试
    mem = IncarnationMemory("/root/.openclaw/workspace/ultron-workflow-v4")
    
    # 设置短期记忆
    mem.set_short_term("current_task", "网站监控")
    print("短期记忆:", mem.get_short_term("current_task"))
    
    # 添加教训
    mem.add_lesson("不要用echo覆盖文件")
    mem.add_insight("规划层很重要")
    
    # 记录转世
    mem.record_life(1, "系统健康检查", "完成", "success")
    
    # 传承记忆
    print("\n传承记忆:", mem.inherit_memory())
    
    # 摘要
    print("\n记忆摘要:", mem.get_summary())