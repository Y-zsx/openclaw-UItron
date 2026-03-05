#!/usr/bin/env python3
"""
奥创核心枢纽 (Ultron Hub)
将4个实用模块整合为一个智能系统
- IntelligentMonitor: 监控系统
- DecisionAdvisor: 决策建议
- StreamProcessor: 数据分析
- WorkflowOrchestrator: 工作流
"""
import json
import os
from datetime import datetime

# 路径配置
ULTRON_DIR = "/root/.openclaw/workspace/ultron"
CONFIG_PATH = f"{ULTRON_DIR}/logs/hub-config.json"
STATE_PATH = f"{ULTRON_DIR}/logs/hub-state.json"


def load_module(filename, class_name):
    """动态加载模块（处理连字符文件名）"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(filename.replace("-", "_"),
        f"{ULTRON_DIR}/{filename}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return getattr(module, class_name)


class UltronHub:
    """奥创核心枢纽 - 整合4大模块"""
    
    def __init__(self):
        self.monitor = None
        self.advisor = None
        self.analytics = None
        self.workflow = None
        self.state = {"initialized": False, "modules": {}}
        self._load_modules()
    
    def _load_modules(self):
        """加载4个核心模块"""
        # 1. IntelligentMonitor (文件名有连字符，需要importlib)
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("intelligent_monitor", 
                f"{ULTRON_DIR}/intelligent-monitor.py")
            monitor_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(monitor_module)
            self.monitor = monitor_module.IntelligentMonitor()
            self.state["modules"]["monitor"] = "loaded"
            print("✓ Monitor loaded")
        except Exception as e:
            self.state["modules"]["monitor"] = f"error: {e}"
            print(f"✗ Monitor failed: {e}")
        
        # 2. DecisionAdvisor
        try:
            DecisionAdvisor = load_module("decision-advisor", "DecisionAdvisor")
            self.advisor = DecisionAdvisor()
            self.state["modules"]["advisor"] = "loaded"
            print("✓ Advisor loaded")
        except Exception as e:
            self.state["modules"]["advisor"] = f"error: {e}"
            print(f"✗ Advisor failed: {e}")
        
        # 3. StreamProcessor (DataAnalytics)
        try:
            StreamProcessor = load_module("data-analytics-engine", "StreamProcessor")
            self.analytics = StreamProcessor()
            self.state["modules"]["analytics"] = "loaded"
            print("✓ Analytics loaded")
        except Exception as e:
            self.state["modules"]["analytics"] = f"error: {e}"
            print(f"✗ Analytics failed: {e}")
        
        # 4. WorkflowOrchestrator
        try:
            WorkflowOrchestrator = load_module("workflow-orchestrator", "WorkflowOrchestrator")
            self.workflow = WorkflowOrchestrator()
            self.state["modules"]["workflow"] = "loaded"
            print("✓ Workflow loaded")
        except Exception as e:
            self.state["modules"]["workflow"] = f"error: {e}"
            print(f"✗ Workflow failed: {e}")
        
        self.state["initialized"] = True
        self.state["last_init"] = datetime.now().isoformat()
        self._save_state()
    
    def _save_state(self):
        """保存状态"""
        os.makedirs(f"{ULTRON_DIR}/logs", exist_ok=True)
        with open(STATE_PATH, 'w') as f:
            json.dump(self.state, f, indent=2)
    
    def run_cycle(self):
        """运行一个完整的智能循环"""
        print("\n=== Ultron Hub Cycle ===")
        
        # 1. 收集监控数据
        metrics = {}
        if self.monitor:
            try:
                cpu = self.monitor.get_cpu_metrics()
                mem = self.monitor.get_memory_metrics()
                disk = self.monitor.get_disk_metrics()
                metrics = {"cpu": cpu, "memory": mem, "disk": disk}
                print(f"📊 Metrics: CPU load={cpu.get('load', 'N/A')}, Mem={mem.get('percent', 'N/A')}%")
            except Exception as e:
                print(f"⚠️ Monitor error: {e}")
        
        # 2. 数据分析 - 计算统计数据
        stats = {}
        if self.analytics:
            try:
                # 模拟数据流分析
                import time
                self.analytics.push("system_metrics", {"cpu": cpu.get('load', 0), "time": time.time()})
                stream_data = self.analytics.get_stream("system_metrics")
                stats = {"stream_points": len(stream_data)}
                print(f"📈 Analytics: {len(stream_data)} data points")
            except Exception as e:
                print(f"⚠️ Analytics error: {e}")
        
        # 3. 决策建议 - 分析上下文
        decisions = []
        if self.advisor:
            try:
                context = {"metrics": metrics, "stats": stats}
                analysis = self.advisor.analyze_context(context)
                decisions = analysis.get("suggestions", [])
                print(f"🧠 Decisions: {len(decisions)} generated")
            except Exception as e:
                print(f"⚠️ Advisor error: {e}")
        
        # 4. 执行工作流 - 检查待执行任务
        if self.workflow:
            try:
                tasks = self.workflow.list_tasks()
                pending = [t for t in tasks if t.get("status") == "pending"]
                print(f"⚡ Workflow: {len(pending)} pending tasks")
            except Exception as e:
                print(f"⚠️ Workflow error: {e}")
        
        print("=== Cycle Complete ===\n")
        return {"metrics": metrics, "stats": stats, "decisions": decisions}
    
    def get_status(self):
        """获取整体状态"""
        return {
            "hub_status": "running" if self.state["initialized"] else "error",
            "modules": self.state["modules"],
            "last_cycle": self.state.get("last_init")
        }


def main():
    """主入口"""
    print("🚀 Starting Ultron Hub...")
    hub = UltronHub()
    
    status = hub.get_status()
    print(f"\n📋 Hub Status: {json.dumps(status, indent=2)}")
    
    # 运行一个完整循环
    result = hub.run_cycle()
    
    return result


if __name__ == "__main__":
    main()