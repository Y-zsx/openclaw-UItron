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
        cpu = mem = disk = {}
        if self.monitor:
            try:
                cpu = self.monitor.get_cpu_metrics()
                mem = self.monitor.get_memory_metrics()
                disk = self.monitor.get_disk_metrics()
                metrics = {"cpu": cpu, "memory": mem, "disk": disk}
                load = cpu.get('load_1m', cpu.get('load_5m', 'N/A'))
                print(f"📊 Metrics: CPU load={load}, Mem={mem.get('usage_percent', 'N/A')}%")
            except Exception as e:
                print(f"⚠️ Monitor error: {e}")
        
        # 1.5 服务健康检查
        services_ok = {}
        if self.monitor:
            try:
                services = self.monitor.check_services()
                services_ok = {k: v == "running" for k, v in services.items()}
                stopped = [k for k, ok in services_ok.items() if not ok]
                if stopped:
                    print(f"🔴 Services stopped: {stopped}")
                else:
                    print(f"✅ All services running")
            except Exception as e:
                print(f"⚠️ Service check error: {e}")
        
        # 2. 数据分析 - 计算统计数据
        stats = {}
        if self.analytics and self.monitor:
            try:
                import time
                load_val = cpu.get('load_1m', 0)
                self.analytics.push("system_metrics", {"cpu": load_val, "time": time.time()})
                stream_data = self.analytics.get_stream("system_metrics")
                stats = {"stream_points": len(stream_data)}
                print(f"📈 Analytics: {len(stream_data)} data points")
            except Exception as e:
                print(f"⚠️ Analytics error: {e}")
        
        # 3. 决策建议 - 基于监控数据生成
        decisions = []
        alerts = []
        if metrics:
            try:
                # 简单的规则引擎
                cpu_load = cpu.get('load_1m', 0)
                mem_pct = mem.get('usage_percent', 0)
                disk_pct = disk.get('usage_percent', 0) if isinstance(disk, dict) else 0
                
                if cpu_load > 0.8:
                    alerts.append(f"⚠️ CPU高负载: {cpu_load}")
                    decisions.append({"type": "high_cpu", "priority": "high", "action": "检查高负载进程"})
                if mem_pct > 80:
                    alerts.append(f"⚠️ 内存高使用: {mem_pct}%")
                    decisions.append({"type": "high_mem", "priority": "high", "action": "释放内存"})
                if disk_pct > 85:
                    alerts.append(f"⚠️ 磁盘空间不足: {disk_pct}%")
                    decisions.append({"type": "low_disk", "priority": "critical", "action": "清理磁盘"})
                
                # 告警输出
                for alert in alerts:
                    print(alert)
                print(f"🧠 Decisions: {len(decisions)} generated")
            except Exception as e:
                print(f"⚠️ Advisor error: {e}")
        
        # 4. 工作流 - 列出可用工作流
        if self.workflow:
            try:
                workflows = self.workflow.list_workflows()
                print(f"⚡ Workflow: {len(workflows)} workflows available")
            except Exception as e:
                print(f"⚠️ Workflow error: {e}")
        
        # 5. 保存告警日志
        if alerts:
            try:
                alert_log = f"{ULTRON_DIR}/logs/hub-alerts.json"
                os.makedirs(f"{ULTRON_DIR}/logs", exist_ok=True)
                # 追加告警
                import time
                alerts_history = []
                if os.path.exists(alert_log):
                    with open(alert_log, 'r') as f:
                        alerts_history = json.load(f)
                alerts_history.append({"time": time.time(), "alerts": alerts, "metrics": {
                    "cpu": cpu.get('load_1m', 0),
                    "mem": mem.get('usage_percent', 0),
                    "disk": disk.get('usage_percent', 0) if isinstance(disk, dict) else 0
                }})
                # 只保留最近100条
                alerts_history = alerts_history[-100:]
                with open(alert_log, 'w') as f:
                    json.dump(alerts_history, f, indent=2)
            except Exception as e:
                print(f"⚠️ Alert log error: {e}")
        
        print("=== Cycle Complete ===\n")
        return {"metrics": metrics, "stats": stats, "decisions": decisions, "alerts": alerts}
    
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