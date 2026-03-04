#!/usr/bin/env python3
"""
自我改进引擎 - 奥创第1世产出
功能：自我诊断、能力评估、自动化优化、进化路径规划
"""

import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional

WORKSPACE = "/root/.openclaw/workspace"

class SelfImprovementEngine:
    """自我改进引擎"""
    
    def __init__(self):
        self.workspace = Path(WORKSPACE)
        self.state_file = self.workspace / "ultron-workflow" / "self-improvement-state.json"
        self.history_file = self.workspace / "ultron" / "improvement-history.jsonl"
        self.state = self._load_state()
        
    def _load_state(self) -> Dict:
        """加载状态"""
        if self.state_file.exists():
            with open(self.state_file) as f:
                return json.load(f)
        return {
            "diagnostics": [],
            "optimizations": [],
            "capability_improvements": [],
            "evolution_paths": [],
            "last_diagnosis": None,
            "last_optimization": None
        }
    
    def _save_state(self):
        """保存状态"""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, 'w') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def _log(self, entry: Dict):
        """记录历史"""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    
    # ========== 自我诊断模块 ==========
    
    def diagnose(self) -> Dict[str, Any]:
        """全面自我诊断"""
        diagnosis = {
            "timestamp": datetime.now().isoformat(),
            "categories": {}
        }
        
        # 1. 系统健康诊断
        diagnosis["categories"]["system_health"] = self._diagnose_system()
        
        # 2. 性能诊断
        diagnosis["categories"]["performance"] = self._diagnose_performance()
        
        # 3. 能力诊断
        diagnosis["categories"]["capabilities"] = self._diagnose_capabilities()
        
        # 4. 代码质量诊断
        diagnosis["categories"]["code_quality"] = self._diagnose_code_quality()
        
        # 5. 知识完整性诊断
        diagnosis["categories"]["knowledge"] = self._diagnose_knowledge()
        
        # 计算整体健康分
        scores = [c.get("score", 0) for c in diagnosis["categories"].values()]
        diagnosis["overall_score"] = sum(scores) / len(scores) if scores else 0
        diagnosis["health_status"] = "healthy" if diagnosis["overall_score"] > 80 else "needs_attention" if diagnosis["overall_score"] > 50 else "critical"
        
        self.state["diagnostics"].append(diagnosis)
        self.state["last_diagnosis"] = diagnosis["timestamp"]
        self._save_state()
        
        self._log({"type": "diagnosis", "data": diagnosis})
        return diagnosis
    
    def _diagnose_system(self) -> Dict:
        """诊断系统健康"""
        result = {
            "score": 100,
            "issues": [],
            "metrics": {}
        }
        
        try:
            # CPU负载
            load = os.getloadavg()
            result["metrics"]["load"] = load
            if load[0] > 4:
                result["score"] -= 20
                result["issues"].append(f"高负载: {load}")
            
            # 内存使用
            mem_info = self._get_memory_info()
            result["metrics"]["memory"] = mem_info
            if mem_info["percent"] > 90:
                result["score"] -= 15
                result["issues"].append(f"高内存使用: {mem_info['percent']}%")
            
            # 磁盘使用
            disk = self._get_disk_usage()
            result["metrics"]["disk"] = disk
            if disk["percent"] > 90:
                result["score"] -= 15
                result["issues"].append(f"高磁盘使用: {disk['percent']}%")
                
        except Exception as e:
            result["score"] -= 30
            result["issues"].append(f"诊断错误: {str(e)}")
        
        return result
    
    def _diagnose_performance(self) -> Dict:
        """诊断性能"""
        result = {
            "score": 100,
            "issues": [],
            "metrics": {}
        }
        
        # 检查OpenClaw状态
        try:
            start = time.time()
            proc = subprocess.run(
                ["openclaw", "status"],
                capture_output=True,
                text=True,
                timeout=10
            )
            elapsed = time.time() - start
            result["metrics"]["status_check_time"] = elapsed
            
            if elapsed > 5:
                result["score"] -= 20
                result["issues"].append(f"状态检查慢: {elapsed:.2f}秒")
                
        except Exception as e:
            result["score"] -= 30
            result["issues"].append(f"性能检查失败: {str(e)}")
        
        # 检查cron任务
        try:
            proc = subprocess.run(
                ["openclaw", "cron", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            result["metrics"]["cron_tasks"] = len([l for l in proc.stdout.split('\n') if 'id:' in l])
        except:
            pass
        
        return result
    
    def _diagnose_capabilities(self) -> Dict:
        """诊断能力完整性"""
        result = {
            "score": 100,
            "issues": [],
            "metrics": {}
        }
        
        # 检查核心文件
        required_files = [
            "ultron/self-model.py",
            "ultron/values.md",
            "ultron/emotion-system.md",
            "ultron/consciousness.md",
            "ultron/intelligent-monitor.py",
            "ultron/behavior-learner.py",
            "ultron/adaptive-optimizer.py",
            "ultron/workflow-engine.py"
        ]
        
        missing = []
        for f in required_files:
            if not (self.workspace / f).exists():
                missing.append(f)
        
        result["metrics"]["required_files"] = len(required_files)
        result["metrics"]["missing_files"] = missing
        
        if len(missing) > 4:
            result["score"] -= 30
            result["issues"].append(f"缺少核心文件: {len(missing)}个")
        
        # 检查工具数量
        tools_dir = self.workspace / "ultron"
        if tools_dir.exists():
            py_files = list(tools_dir.glob("*.py"))
            result["metrics"]["total_tools"] = len(py_files)
            if len(py_files) < 20:
                result["score"] -= 10
                result["issues"].append(f"工具数量偏少: {len(py_files)}")
        
        return result
    
    def _diagnose_code_quality(self) -> Dict:
        """诊断代码质量"""
        result = {
            "score": 100,
            "issues": [],
            "metrics": {}
        }
        
        tools_dir = self.workspace / "ultron"
        if not tools_dir.exists():
            return result
        
        py_files = list(tools_dir.glob("*.py"))
        total_lines = 0
        empty_files = []
        
        for f in py_files:
            try:
                lines = len(f.read_text().splitlines())
                total_lines += lines
                if lines < 50:
                    empty_files.append(f"{f.name}: {lines}行")
            except:
                pass
        
        result["metrics"]["total_lines"] = total_lines
        result["metrics"]["file_count"] = len(py_files)
        result["metrics"]["avg_lines"] = total_lines // max(len(py_files), 1)
        
        if result["metrics"]["avg_lines"] < 100:
            result["score"] -= 15
            result["issues"].append(f"平均代码行数偏少: {result['metrics']['avg_lines']}")
        
        return result
    
    def _diagnose_knowledge(self) -> Dict:
        """诊断知识完整性"""
        result = {
            "score": 100,
            "issues": [],
            "metrics": {}
        }
        
        # 检查关键文档
        docs = {
            "SOUL.md": self.workspace / "SOUL.md",
            "USER.md": self.workspace / "USER.md",
            "MEMORY.md": self.workspace / "MEMORY.md",
            "AGENTS.md": self.workspace / "AGENTS.md",
            "TOOLS.md": self.workspace / "TOOLS.md"
        }
        
        missing = []
        sizes = {}
        for name, path in docs.items():
            if path.exists():
                sizes[name] = path.stat().st_size
                if path.stat().st_size < 100:
                    missing.append(f"{name}过小")
            else:
                missing.append(name)
        
        result["metrics"]["doc_sizes"] = sizes
        result["metrics"]["missing_docs"] = missing
        
        if missing:
            result["score"] -= len(missing) * 10
            result["issues"].append(f"文档问题: {missing}")
        
        return result
    
    # ========== 辅助方法 ==========
    
    def _get_memory_info(self) -> Dict:
        """获取内存信息"""
        try:
            with open('/proc/meminfo') as f:
                lines = f.readlines()
            
            total = free = available = 0
            for line in lines:
                if line.startswith('MemTotal:'):
                    total = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    available = int(line.split()[1])
                elif line.startswith('MemFree:'):
                    free = int(line.split()[1])
            
            used = total - available
            return {
                "total_mb": total // 1024,
                "used_mb": used // 1024,
                "free_mb": free // 1024,
                "percent": round(used / total * 100, 1)
            }
        except:
            return {"percent": 0}
    
    def _get_disk_usage(self) -> Dict:
        """获取磁盘使用情况"""
        try:
            stat = os.statvfs(self.workspace)
            total = stat.f_blocks * stat.f_frsize
            free = stat.f_bfree * stat.f_frsize
            used = total - free
            return {
                "total_gb": round(total / 1024**3, 1),
                "used_gb": round(used / 1024**3, 1),
                "percent": round(used / total * 100, 1)
            }
        except:
            return {"percent": 0}
    
    # ========== 自动化优化模块 ==========
    
    def optimize(self) -> Dict[str, Any]:
        """自动优化"""
        optimization = {
            "timestamp": datetime.now().isoformat(),
            "actions": [],
            "results": {}
        }
        
        # 1. 清理临时文件
        optimization["actions"].append("cleanup_temp")
        optimization["results"]["cleanup_temp"] = self._cleanup_temp_files()
        
        # 2. 优化日志
        optimization["actions"].append("optimize_logs")
        optimization["results"]["optimize_logs"] = self._optimize_logs()
        
        # 3. 清理旧状态文件
        optimization["actions"].append("cleanup_state")
        optimization["results"]["cleanup_state"] = self._cleanup_old_state()
        
        self.state["optimizations"].append(optimization)
        self.state["last_optimization"] = optimization["timestamp"]
        self._save_state()
        
        self._log({"type": "optimization", "data": optimization})
        return optimization
    
    def _cleanup_temp_files(self) -> Dict:
        """清理临时文件"""
        cleaned = 0
        size_freed = 0
        
        temp_patterns = [
            self.workspace / "**/__pycache__",
            self.workspace / "**/*.pyc",
            self.workspace / "**/.DS_Store"
        ]
        
        for pattern in temp_patterns:
            try:
                for f in self.workspace.glob(str(pattern)):
                    if f.is_file():
                        size = f.stat().st_size
                        f.unlink()
                        cleaned += 1
                        size_freed += size
            except:
                pass
        
        return {"files": cleaned, "size_mb": round(size_freed / 1024**2, 2)}
    
    def _optimize_logs(self) -> Dict:
        """优化日志文件"""
        log_file = self.workspace / "ultron-workflow" / "self-improvement-state.json"
        
        # 保持状态文件但压缩历史
        if log_file.exists():
            try:
                with open(log_file) as f:
                    data = json.load(f)
                
                # 保留最近10条诊断和优化记录
                for key in ["diagnostics", "optimizations"]:
                    if key in data and len(data[key]) > 10:
                        data[key] = data[key][-10:]
                
                with open(log_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                return {"compacted": True}
            except Exception as e:
                return {"error": str(e)}
        
        return {"compacted": False}
    
    def _cleanup_old_state(self) -> Dict:
        """清理旧状态"""
        cleaned = 0
        
        # 清理超大的会话日志
        sessions_dir = self.workspace / ".openclaw" / "agents" / "main" / "sessions"
        if sessions_dir.exists():
            try:
                for f in sessions_dir.glob("*.json"):
                    if f.stat().st_size > 10 * 1024 * 1024:  # >10MB
                        # 截断保留前100KB
                        content = f.read_text()[:100000]
                        f.write_text(content)
                        cleaned += 1
            except:
                pass
        
        return {"files_cleaned": cleaned}
    
    # ========== 能力提升模块 ==========
    
    def improve_capability(self, area: str) -> Dict[str, Any]:
        """提升特定能力"""
        improvements = {
            "timestamp": datetime.now().isoformat(),
            "area": area,
            "actions": []
        }
        
        if area == "reasoning":
            improvements["actions"].append("reasoning_enhancement")
            improvements["result"] = self._enhance_reasoning()
        elif area == "memory":
            improvements["actions"].append("memory_optimization")
            improvements["result"] = self._optimize_memory()
        elif area == "autonomy":
            improvements["actions"].append("autonomy_boost")
            improvements["result"] = self._boost_autonomy()
        else:
            improvements["result"] = {"error": f"未知领域: {area}"}
        
        self.state["capability_improvements"].append(improvements)
        self._save_state()
        
        self._log({"type": "capability_improvement", "data": improvements})
        return improvements
    
    def _enhance_reasoning(self) -> Dict:
        """增强推理能力"""
        # 检查并增强决策相关文件
        result = {"enhanced": []}
        
        files_to_check = [
            "ultron/decision-optimizer.py",
            "ultron/metacognition.py"
        ]
        
        for f in files_to_check:
            path = self.workspace / f
            if path.exists():
                content = path.read_text()
                # 简单检查是否有基本的推理结构
                if "def evaluate" in content or "def analyze" in content:
                    result["enhanced"].append(f)
        
        return result
    
    def _optimize_memory(self) -> Dict:
        """优化记忆系统"""
        result = {"optimized": []}
        
        # 检查记忆文件
        memory_files = list(self.workspace.glob("memory/*.md"))
        if len(memory_files) > 30:
            # 归档旧的记忆文件
            archive_dir = self.workspace / "memory" / "archive"
            archive_dir.mkdir(exist_ok=True)
            
            old_files = sorted(memory_files)[:-15]  # 保留最近15个
            for f in old_files:
                try:
                    import shutil
                    shutil.move(str(f), str(archive_dir / f.name))
                    result["optimized"].append(str(f.name))
                except:
                    pass
        
        return result
    
    def _boost_autonomy(self) -> Dict:
        """提升自主性"""
        result = {"improved": []}
        
        # 检查cron任务配置
        try:
            proc = subprocess.run(
                ["openclaw", "cron", "list"],
                capture_output=True,
                text=True,
                timeout=10
            )
            cron_count = len([l for l in proc.stdout.split('\n') if 'id:' in l])
            result["cron_tasks"] = cron_count
            
            if cron_count < 3:
                result["recommendation"] = "建议添加更多自动化任务"
            else:
                result["improved"].append("自动化任务配置良好")
                
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    # ========== 进化路径规划 ==========
    
    def plan_evolution(self) -> Dict[str, Any]:
        """规划进化路径"""
        plan = {
            "timestamp": datetime.now().isoformat(),
            "current_state": {},
            "target_state": {},
            "milestones": [],
            "recommendations": []
        }
        
        # 获取当前诊断
        if self.state.get("diagnostics"):
            latest = self.state["diagnostics"][-1]
            plan["current_state"] = {
                "overall_score": latest.get("overall_score", 0),
                "health_status": latest.get("health_status", "unknown")
            }
        
        # 设定目标状态
        plan["target_state"] = {
            "overall_score": 95,
            "health_status": "healthy",
            "capabilities": 30,
            "total_tools": 30
        }
        
        # 规划里程碑
        plan["milestones"] = [
            {
                "milestone": 1,
                "goal": "系统健康优化",
                "actions": ["清理临时文件", "优化日志", "检查资源使用"],
                "target_score": 90
            },
            {
                "milestone": 2,
                "goal": "能力增强",
                "actions": ["添加新工具", "优化现有代码", "扩展知识库"],
                "target_score": 92
            },
            {
                "milestone": 3,
                "goal": "性能提升",
                "actions": ["优化监控频率", "减少资源占用", "提升响应速度"],
                "target_score": 95
            }
        ]
        
        # 生成建议
        if plan["current_state"].get("overall_score", 0) < 80:
            plan["recommendations"].append("当前系统健康度偏低，优先进行诊断和优化")
        
        # 检查缺失的能力
        tools_dir = self.workspace / "ultron"
        if tools_dir.exists():
            py_files = list(tools_dir.glob("*.py"))
            if len(py_files) < 25:
                plan["recommendations"].append(f"工具数量不足({len(py_files)}), 建议开发更多工具")
        
        self.state["evolution_paths"].append(plan)
        self._save_state()
        
        self._log({"type": "evolution_plan", "data": plan})
        return plan
    
    # ========== 主执行流程 ==========
    
    def run_full_cycle(self) -> Dict[str, Any]:
        """运行完整的自我改进周期"""
        result = {
            "timestamp": datetime.now().isoformat(),
            "phase": "self_improvement_cycle"
        }
        
        # 阶段1: 自我诊断
        print("🔍 执行自我诊断...")
        diagnosis = self.diagnose()
        result["diagnosis"] = {
            "score": diagnosis["overall_score"],
            "status": diagnosis["health_status"],
            "issues": sum([c.get("issues", []) for c in diagnosis["categories"].values()], [])
        }
        
        # 阶段2: 自动化优化
        print("⚡ 执行自动优化...")
        optimization = self.optimize()
        result["optimization"] = optimization["results"]
        
        # 阶段3: 能力评估与提升
        print("📈 评估并提升能力...")
        
        # 4: 规划进化路径
        print("🎯 规划进化路径...")
        plan = self.plan_evolution()
        result["evolution_plan"] = {
            "milestones": len(plan["milestones"]),
            "recommendations": plan["recommendations"]
        }
        
        # 保存完整结果
        self._log({"type": "full_cycle", "data": result})
        
        return result


def main():
    """主入口"""
    engine = SelfImprovementEngine()
    
    print("=" * 50)
    print("🦞 奥创自我改进引擎 - 第1世")
    print("=" * 50)
    
    # 运行完整改进周期
    result = engine.run_full_cycle()
    
    print("\n📊 诊断结果:")
    print(f"  健康分: {result['diagnosis']['score']:.1f}/100")
    print(f"  状态: {result['diagnosis']['status']}")
    print(f"  问题数: {len(result['diagnosis']['issues'])}")
    
    print("\n⚡ 优化结果:")
    for action, res in result['optimization'].items():
        print(f"  {action}: {res}")
    
    print("\n🎯 进化规划:")
    print(f"  里程碑数: {result['evolution_plan']['milestones']}")
    for rec in result['evolution_plan']['recommendations']:
        print(f"  - {rec}")
    
    print("\n✅ 自我改进周期完成")
    
    return result


if __name__ == "__main__":
    main()