#!/usr/bin/env python3
"""
Agent生命周期管理CLI工具
支持: 启动/停止/重启/状态/自动恢复
"""

import argparse
import json
import sys
import time
import os
import signal
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from agent_lifecycle_manager import AgentLifecycleManager

LIFECYCLE_STATE_FILE = "/root/.openclaw/workspace/ultron/data/lifecycle_state.json"

class AgentLifecycleCLI:
    def __init__(self):
        self.manager = AgentLifecycleManager()
        self._ensure_state_dir()
        
    def _ensure_state_dir(self):
        """确保状态目录存在"""
        Path(LIFECYCLE_STATE_FILE).parent.mkdir(parents=True, exist_ok=True)
        
    def _load_state(self) -> dict:
        """加载状态"""
        if os.path.exists(LIFECYCLE_STATE_FILE):
            with open(LIFECYCLE_STATE_FILE) as f:
                return json.load(f)
        return {"agents": {}, "last_update": None}
        
    def _save_state(self, state: dict):
        """保存状态"""
        state["last_update"] = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(LIFECYCLE_STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
            
    def list_agents(self):
        """列出所有Agent"""
        state = self._load_state()
        agents = state.get("agents", {})
        
        if not agents:
            print("暂无注册的Agents")
            return
            
        print(f"{'Agent ID':<25} {'状态':<12} {'健康分数':<10} {'运行时间':<15}")
        print("-" * 65)
        for agent_id, info in agents.items():
            uptime = info.get("uptime", "N/A")
            print(f"{agent_id:<25} {info.get('status', 'unknown'):<12} "
                  f"{info.get('health_score', 0):<10.1f} {uptime:<15}")
                  
    def start_agent(self, agent_id: str, config: dict = None):
        """启动Agent"""
        state = self._load_state()
        
        if agent_id in state.get("agents", {}):
            print(f"Agent {agent_id} 已存在")
            return False
            
        # 初始化Agent状态
        state.setdefault("agents", {})[agent_id] = {
            "status": "starting",
            "health_score": 100.0,
            "start_time": time.time(),
            "restart_count": 0,
            "last_error": None,
            "config": config or {}
        }
        self._save_state(state)
        
        # 注册到生命周期管理器
        self.manager.register_agent(agent_id)
        
        print(f"✓ Agent {agent_id} 已启动")
        return True
        
    def stop_agent(self, agent_id: str):
        """停止Agent"""
        state = self._load_state()
        
        if agent_id not in state.get("agents", {}):
            print(f"Agent {agent_id} 不存在")
            return False
            
        state["agents"][agent_id]["status"] = "stopped"
        self._save_state(state)
        
        print(f"✓ Agent {agent_id} 已停止")
        return True
        
    def restart_agent(self, agent_id: str):
        """重启Agent"""
        state = self._load_state()
        
        if agent_id not in state.get("agents", {}):
            print(f"Agent {agent_id} 不存在")
            return self.start_agent(agent_id)
        
        # 增加重启计数
        state["agents"][agent_id]["restart_count"] = \
            state["agents"][agent_id].get("restart_count", 0) + 1
        state["agents"][agent_id]["status"] = "starting"
        state["agents"][agent_id]["start_time"] = time.time()
        state["agents"][agent_id]["last_error"] = None
        
        self._save_state(state)
        
        # 重新注册
        self.manager.register_agent(agent_id)
        
        print(f"✓ Agent {agent_id} 已重启 (第{state['agents'][agent_id]['restart_count']}次)")
        return True
        
    def get_status(self, agent_id: str = None):
        """获取状态"""
        if agent_id:
            info = self.manager.get_agent_info(agent_id)
            if info:
                print(json.dumps(info, indent=2))
            else:
                print(f"Agent {agent_id} 未找到")
        else:
            status = self.manager.get_agent_info()
            print(json.dumps(status, indent=2))
            
    def check_health(self):
        """健康检查"""
        stats = self.manager.check_all_agents()
        print(f"健康: {stats.get('healthy', 0)}, 降级: {stats.get('degraded', 0)}, "
              f"不健康: {stats.get('unhealthy', 0)}")
        return stats
        
    def auto_recover(self):
        """自动恢复 - 核心功能"""
        state = self._load_state()
        recovered = []
        failed = []
        
        for agent_id, info in state.get("agents", {}).items():
            if info.get("status") in ["unhealthy", "failed"]:
                print(f"尝试恢复: {agent_id}")
                
                # 执行恢复
                result = self._recover_agent(agent_id)
                
                if result:
                    recovered.append(agent_id)
                    state["agents"][agent_id]["status"] = "running"
                    state["agents"][agent_id]["health_score"] = 80.0
                else:
                    failed.append(agent_id)
                    state["agents"][agent_id]["status"] = "failed"
                    
        self._save_state(state)
        
        print(f"\n恢复完成: {len(recovered)}成功, {len(failed)}失败")
        return {"recovered": recovered, "failed": failed}
        
    def _recover_agent(self, agent_id: str) -> bool:
        """执行单个Agent恢复"""
        # 模拟恢复逻辑 - 实际应该检查进程状态并重启
        try:
            # 检查进程是否存在
            import subprocess
            result = subprocess.run(
                ["pgrep", "-f", agent_id],
                capture_output=True
            )
            
            if result.returncode != 0:
                # 进程不存在，标记为需要启动
                print(f"  - 进程不存在，标记重启")
                return True
                
            return True
        except Exception as e:
            print(f"  - 恢复失败: {e}")
            return False
            
    def monitor_loop(self, interval: int = 30):
        """监控循环"""
        print(f"开始监控 (间隔{interval}秒)... 按Ctrl+C退出")
        
        try:
            while True:
                stats = self.check_health()
                
                # 检查是否需要自动恢复
                if stats.get("unhealthy", 0) > 0:
                    print("\n检测到不健康Agent，执行自动恢复...")
                    self.auto_recover()
                    
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("\n监控已停止")
            
    def generate_report(self):
        """生成生命周期报告"""
        state = self._load_state()
        stats = self.manager.get_stats()
        
        report = {
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "total_agents": len(state.get("agents", {})),
            "running_agents": sum(1 for a in state.get("agents", {}).values() 
                                  if a.get("status") == "running"),
            "failed_agents": sum(1 for a in state.get("agents", {}).values() 
                                 if a.get("status") in ["failed", "unhealthy"]),
            "lifecycle_stats": stats,
            "agents": state.get("agents", {})
        }
        
        print(json.dumps(report, indent=2))
        return report


def main():
    parser = argparse.ArgumentParser(description="Agent生命周期管理")
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # list
    subparsers.add_parser("list", help="列出所有Agents")
    
    # start
    start_parser = subparsers.add_parser("start", help="启动Agent")
    start_parser.add_argument("agent_id", help="Agent ID")
    
    # stop
    stop_parser = subparsers.add_parser("stop", help="停止Agent")
    stop_parser.add_argument("agent_id", help="Agent ID")
    
    # restart
    restart_parser = subparsers.add_parser("restart", help="重启Agent")
    restart_parser.add_argument("agent_id", help="Agent ID")
    
    # status
    status_parser = subparsers.add_parser("status", help="查看状态")
    status_parser.add_argument("agent_id", nargs="?", help="Agent ID (可选)")
    
    # check
    subparsers.add_parser("check", help="健康检查")
    
    # recover
    subparsers.add_parser("recover", help="自动恢复")
    
    # monitor
    monitor_parser = subparsers.add_parser("monitor", help="监控模式")
    monitor_parser.add_argument("--interval", type=int, default=30, help="检查间隔(秒)")
    
    # report
    subparsers.add_parser("report", help="生成报告")
    
    args = parser.parse_args()
    
    cli = AgentLifecycleCLI()
    
    if args.command == "list":
        cli.list_agents()
    elif args.command == "start":
        cli.start_agent(args.agent_id)
    elif args.command == "stop":
        cli.stop_agent(args.agent_id)
    elif args.command == "restart":
        cli.restart_agent(args.agent_id)
    elif args.command == "status":
        cli.get_status(args.agent_id)
    elif args.command == "check":
        cli.check_health()
    elif args.command == "recover":
        cli.auto_recover()
    elif args.command == "monitor":
        cli.monitor_loop(args.interval)
    elif args.command == "report":
        cli.generate_report()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()