#!/usr/bin/env python3
"""
奥创智能体系统 v1.0
Multi-Agent Collaboration Network
"""
import sys
import json
from pathlib import Path
from datetime import datetime

# 添加agents目录
AGENTS_DIR = Path(__file__).parent / "agents"
sys.path.insert(0, str(AGENTS_DIR))

from enhanced_message_bus import EnhancedMessageBus
from monitor_agent import MonitorAgent
from orchestrator_agent import OrchestratorAgent
from executor_agent import ExecutorAgent
from analyzer_agent import AnalyzerAgent
from learner_agent import LearnerAgent
from messenger_agent import MessengerAgent

class UltronSystem:
    """奥创智能体系统"""
    
    def __init__(self):
        self.name = "Ultron"
        self.version = "1.0"
        self.bus = EnhancedMessageBus()
        
        # 初始化所有Agent
        self.agents = {
            "monitor": MonitorAgent(),
            "orchestrator": OrchestratorAgent(),
            "executor": ExecutorAgent(),
            "analyzer": AnalyzerAgent(),
            "learner": LearnerAgent(),
            "messenger": MessengerAgent()
        }
        
        print(f"[Ultron] 系统启动 v{self.version}")
        print(f"[Ultron] 已加载 {len(self.agents)} 个Agent")
    
    def status(self) -> dict:
        """获取系统状态"""
        return {
            "name": self.name,
            "version": self.version,
            "agents": list(self.agents.keys()),
            "timestamp": datetime.now().isoformat()
        }
    
    def run_cycle(self):
        """运行一个完整的协作周期"""
        print("\n=== 奥创智能体系统周期 ===")
        
        # 1. 监控
        status = self.agents["monitor"].check_system()
        print(f"[Monitor] 系统状态: Load={status['load']}, Mem={status['memory_pct']}%")
        
        # 2. 分析
        analysis = self.agents["analyzer"].analyze_task({"status": status})
        print(f"[Analyzer] 分析结果: {analysis}")
        
        # 3. 编排
        workflow = self.agents["orchestrator"].orchestrate(analysis)
        print(f"[Orchestrator] 工作流: {workflow}")
        
        # 4. 执行 (从消息队列获取任务)
        result = self.agents["executor"].run()
        print(f"[Executor] 执行结果: {result}")
        
        print("=== 周期完成 ===\n")
        return result

if __name__ == "__main__":
    system = UltronSystem()
    print(json.dumps(system.status(), indent=2, ensure_ascii=False))
    system.run_cycle()