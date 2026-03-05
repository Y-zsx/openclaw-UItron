#!/usr/bin/env python3
"""
Agent协作网络统一入口CLI
Unified CLI for Agent Collaboration Network
集成了: API网关、Agent管理、任务队列、消息传递、监控告警

用法:
    python collab_cli_unified.py <command> [options]
    python collab_cli_unified.py status                    # 查看整体状态
    python collab_cli_unified.py agent list                # 列出Agent
    python collab_cli_unified.py task submit --type test   # 提交任务
    python collab_cli_unified.py message send --to xxxx    # 发送消息
    python collab_cli_unified.py monitor                   # 查看监控状态
"""

import argparse
import json
import sys
import uuid
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any

# Add parent to path
SCRIPT_DIR = Path(__file__).parent
ULTRON_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(ULTRON_DIR))

# Try importing collaboration modules
try:
    from agents.multi_agent_collaboration import (
        AgentNetwork, TaskRouter, CollaborationStateMachine,
        MessageBroker, AgentInfo, AgentCapability, CollaborationTask,
        CollaborationPattern, TaskStatus
    )
    COLLAB_AVAILABLE = True
except ImportError:
    COLLAB_AVAILABLE = False
    print("Warning: collaboration modules not fully available")

# Data directory - use agents/data in the ultron folder
DATA_DIR = Path("/root/.openclaw/workspace/ultron/agents/data")
DATA_DIR.mkdir(parents=True, exist_ok=True)

# State files
STATE_FILE = DATA_DIR / "unified_state.json"


class UnifiedCollabCLI:
    """统一协作网络CLI"""
    
    def __init__(self, json_output: bool = False):
        self.json_output = json_output
        self.state = self._load_state()
        
    def _load_state(self) -> dict:
        """加载状态"""
        if STATE_FILE.exists():
            with open(STATE_FILE) as f:
                return json.load(f)
        return {
            "agents": {},
            "tasks": {},
            "messages": [],
            "last_update": None
        }
    
    def _save_state(self):
        """保存状态"""
        self.state["last_update"] = datetime.now().isoformat()
        with open(STATE_FILE, 'w') as f:
            json.dump(self.state, f, indent=2, ensure_ascii=False)
    
    def _output(self, data: Any, error: str = None):
        """输出结果"""
        if self.json_output:
            if error:
                print(json.dumps({"success": False, "error": error}, ensure_ascii=False))
            else:
                print(json.dumps(data, indent=2, ensure_ascii=False))
        else:
            if error:
                print(f"❌ {error}", file=sys.stderr)
                sys.exit(1)
            # Pretty print for non-JSON
            if isinstance(data, dict):
                if "success" in data and not data.get("success"):
                    print(f"❌ {data.get('error', 'Unknown error')}")
                    return
                self._pretty_print(data)
            elif isinstance(data, list):
                for item in data:
                    self._pretty_print(item)
            else:
                print(data)
    
    def _pretty_print(self, data: dict, indent: int = 0):
        """美化输出"""
        prefix = "  " * indent
        if "message" in data:
            print(f"{prefix}📨 {data['message']}")
        elif "error" in data:
            print(f"{prefix}❌ {data['error']}")
        else:
            for key, value in data.items():
                if isinstance(value, (dict, list)) and key not in ["results", "data"]:
                    print(f"{prefix}{key}:")
                    self._pretty_print(value if isinstance(value, dict) else {str(i): v for i, v in enumerate(value)}, indent + 1)
                else:
                    print(f"{prefix}{key}: {value}")
    
    # ========== Status Commands ==========
    
    def cmd_status(self):
        """查看整体状态"""
        agents = self.state.get("agents", {})
        tasks = self.state.get("tasks", {})
        messages = self.state.get("messages", [])
        
        # Count statuses
        agent_stats = {"active": 0, "idle": 0, "offline": 0}
        for a in agents.values():
            status = a.get("status", "idle")
            if status in agent_stats:
                agent_stats[status] += 1
            else:
                agent_stats["idle"] += 1
        
        task_stats = {"pending": 0, "running": 0, "completed": 0, "failed": 0}
        for t in tasks.values():
            status = t.get("status", "pending")
            if status in task_stats:
                task_stats[status] += 1
            else:
                task_stats["pending"] += 1
        
        return {
            "status": "healthy",
            "agents": {
                "total": len(agents),
                "active": agent_stats["active"],
                "idle": agent_stats["idle"],
                "offline": agent_stats["offline"]
            },
            "tasks": {
                "total": len(tasks),
                "pending": task_stats["pending"],
                "running": task_stats["running"],
                "completed": task_stats["completed"],
                "failed": task_stats["failed"]
            },
            "messages": len(messages),
            "last_update": self.state.get("last_update")
        }
    
    # ========== Agent Commands ==========
    
    def cmd_agent_list(self, status: str = None, capability: str = None):
        """列出Agent"""
        agents = self.state.get("agents", {})
        result = []
        
        for agent_id, info in agents.items():
            if status and info.get("status") != status:
                continue
            if capability and capability not in info.get("capabilities", []):
                continue
            result.append({
                "id": agent_id,
                "name": info.get("name", agent_id),
                "status": info.get("status", "idle"),
                "capabilities": info.get("capabilities", []),
                "load": info.get("load", 0),
                "health_score": info.get("health_score", 100),
                "registered_at": info.get("registered_at")
            })
        
        return {"agents": result, "total": len(result)}
    
    def cmd_agent_register(self, name: str, capabilities: List[str], metadata: dict = None):
        """注册Agent"""
        agent_id = f"agent-{uuid.uuid4().hex[:8]}"
        self.state["agents"][agent_id] = {
            "agent_id": agent_id,
            "name": name,
            "capabilities": capabilities,
            "status": "active",
            "load": 0,
            "health_score": 100,
            "metadata": metadata or {},
            "registered_at": datetime.now().isoformat(),
            "last_heartbeat": datetime.now().isoformat()
        }
        self._save_state()
        return {"success": True, "message": f"Agent注册成功", "agent_id": agent_id}
    
    def cmd_agent_unregister(self, agent_id: str):
        """注销Agent"""
        if agent_id not in self.state["agents"]:
            return {"success": False, "error": f"Agent不存在: {agent_id}"}
        del self.state["agents"][agent_id]
        self._save_state()
        return {"success": True, "message": f"Agent已注销: {agent_id}"}
    
    def cmd_agent_heartbeat(self, agent_id: str, status: str = None, health_score: float = None):
        """Agent心跳"""
        if agent_id not in self.state["agents"]:
            return {"success": False, "error": f"Agent不存在: {agent_id}"}
        
        agent = self.state["agents"][agent_id]
        if status:
            agent["status"] = status
        if health_score is not None:
            agent["health_score"] = health_score
        agent["last_heartbeat"] = datetime.now().isoformat()
        self._save_state()
        return {"success": True, "message": "心跳已更新"}
    
    def cmd_agent_info(self, agent_id: str):
        """获取Agent详情"""
        if agent_id not in self.state["agents"]:
            return {"success": False, "error": f"Agent不存在: {agent_id}"}
        return self.state["agents"][agent_id]
    
    # ========== Task Commands ==========
    
    def cmd_task_list(self, status: str = None, agent_id: str = None, limit: int = 50):
        """列出任务"""
        tasks = self.state.get("tasks", {})
        result = []
        
        for task_id, info in tasks.items():
            if status and info.get("status") != status:
                continue
            if agent_id and info.get("assigned_agent") != agent_id:
                continue
            result.append({
                "task_id": task_id,
                "type": info.get("type"),
                "description": info.get("description"),
                "status": info.get("status", "pending"),
                "priority": info.get("priority", 5),
                "assigned_agent": info.get("assigned_agent"),
                "created_at": info.get("created_at"),
                "completed_at": info.get("completed_at")
            })
        
        return {"tasks": result[:limit], "total": len(result)}
    
    def cmd_task_submit(self, task_type: str, description: str = None, 
                        priority: int = 5, target_agent: str = None, 
                        payload: dict = None):
        """提交任务"""
        task_id = f"task-{uuid.uuid4().hex[:8]}"
        self.state["tasks"][task_id] = {
            "task_id": task_id,
            "type": task_type,
            "description": description or task_type,
            "status": "pending",
            "priority": priority,
            "assigned_agent": target_agent,
            "payload": payload or {},
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        self._save_state()
        return {"success": True, "message": "任务已提交", "task_id": task_id}
    
    def cmd_task_status(self, task_id: str):
        """获取任务状态"""
        if task_id not in self.state["tasks"]:
            return {"success": False, "error": f"任务不存在: {task_id}"}
        return self.state["tasks"][task_id]
    
    def cmd_task_update(self, task_id: str, status: str, result: any = None, error: str = None):
        """更新任务状态"""
        if task_id not in self.state["tasks"]:
            return {"success": False, "error": f"任务不存在: {task_id}"}
        
        task = self.state["tasks"][task_id]
        task["status"] = status
        if result is not None:
            task["result"] = result
        if error:
            task["error"] = error
        if status in ["completed", "failed"]:
            task["completed_at"] = datetime.now().isoformat()
        
        self._save_state()
        return {"success": True, "message": f"任务状态已更新: {status}"}
    
    def cmd_task_cancel(self, task_id: str):
        """取消任务"""
        return self.cmd_task_update(task_id, "cancelled")
    
    def cmd_task_pending(self):
        """获取待处理任务"""
        return self.cmd_task_list(status="pending")
    
    # ========== Message Commands ==========
    
    def cmd_message_list(self, agent_id: str = None, unread_only: bool = False):
        """获取消息"""
        messages = self.state.get("messages", [])
        result = []
        
        for msg in messages:
            if agent_id and msg.get("receiver_id") != agent_id:
                continue
            if unread_only and msg.get("read", False):
                continue
            result.append(msg)
        
        return {"messages": result, "total": len(result)}
    
    def cmd_message_send(self, from_agent: str, to_agent: str, 
                         content: str, msg_type: str = "text"):
        """发送消息"""
        message_id = f"msg-{uuid.uuid4().hex[:8]}"
        message = {
            "message_id": message_id,
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "type": msg_type,
            "timestamp": datetime.now().isoformat(),
            "read": False
        }
        self.state["messages"].append(message)
        self._save_state()
        return {"success": True, "message": "消息已发送", "message_id": message_id}
    
    def cmd_message_mark_read(self, agent_id: str, message_id: str):
        """标记已读"""
        messages = self.state.get("messages", [])
        for msg in messages:
            if msg.get("message_id") == message_id and msg.get("receiver_id") == agent_id:
                msg["read"] = True
                self._save_state()
                return {"success": True, "message": "消息已标记为已读"}
        return {"success": False, "error": "消息不存在"}
    
    # ========== Monitor Commands ==========
    
    def cmd_monitor(self):
        """监控状态"""
        agents = self.state.get("agents", {})
        tasks = self.state.get("tasks", {})
        
        # Check agent health
        unhealthy = []
        for agent_id, info in agents.items():
            hs = info.get("health_score", 100)
            if hs < 70:
                unhealthy.append({"id": agent_id, "health": hs})
        
        # Check pending tasks
        pending = sum(1 for t in tasks.values() if t.get("status") == "pending")
        
        return {
            "monitor": {
                "unhealthy_agents": unhealthy,
                "pending_tasks": pending,
                "total_agents": len(agents),
                "total_tasks": len(tasks)
            },
            "status": "warning" if unhealthy or pending > 10 else "healthy"
        }
    
    # ========== Stats Commands ==========
    
    def cmd_stats(self):
        """统计信息"""
        agents = self.state.get("agents", {})
        tasks = self.state.get("tasks", {})
        messages = self.state.get("messages", [])
        
        return {
            "statistics": {
                "agents": len(agents),
                "tasks": len(tasks),
                "messages": len(messages),
                "completed_tasks": sum(1 for t in tasks.values() if t.get("status") == "completed"),
                "failed_tasks": sum(1 for t in tasks.values() if t.get("status") == "failed")
            }
        }


def main():
    parser = argparse.ArgumentParser(
        description="Agent协作网络统一CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s status                      查看整体状态
  %(prog)s agent list                  列出所有Agent
  %(prog)s agent register --name test --caps monitor,execute
  %(prog)s task submit --type analyze --desc "分析数据"
  %(prog)s message send --from a1 --to a2 --content "hello"
  %(prog)s monitor                     查看监控状态
  %(prog)s stats                       统计信息
        """
    )
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--quiet", "-q", action="store_true", help="静默模式")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # Status command
    subparsers.add_parser("status", help="查看整体状态")
    
    # Stats command
    subparsers.add_parser("stats", help="统计信息")
    
    # Monitor command
    subparsers.add_parser("monitor", help="监控状态")
    
    # Agent sub-commands
    agent_parser = subparsers.add_parser("agent", help="Agent管理")
    agent_sub = agent_parser.add_subparsers(dest="agent_cmd", help="Agent子命令")
    
    list_parser = agent_sub.add_parser("list", help="列出Agent")
    list_parser.add_argument("--status", help="按状态过滤")
    list_parser.add_argument("--capability", help="按能力过滤")
    
    reg_parser = agent_sub.add_parser("register", help="注册Agent")
    reg_parser.add_argument("--name", required=True, help="Agent名称")
    reg_parser.add_argument("--caps", required=True, help="能力列表(逗号分隔)")
    reg_parser.add_argument("--metadata", help="元数据(JSON)")
    
    unreg_parser = agent_sub.add_parser("unregister", help="注销Agent")
    unreg_parser.add_argument("agent_id", help="Agent ID")
    
    hb_parser = agent_sub.add_parser("heartbeat", help="发送心跳")
    hb_parser.add_argument("agent_id", help="Agent ID")
    hb_parser.add_argument("--status", help="状态")
    hb_parser.add_argument("--health", type=float, help="健康分数")
    
    info_parser = agent_sub.add_parser("info", help="Agent详情")
    info_parser.add_argument("agent_id", help="Agent ID")
    
    # Task sub-commands
    task_parser = subparsers.add_parser("task", help="任务管理")
    task_sub = task_parser.add_subparsers(dest="task_cmd", help="任务子命令")
    
    task_list_parser = task_sub.add_parser("list", help="列出任务")
    task_list_parser.add_argument("--status", help="按状态过滤")
    task_list_parser.add_argument("--agent-id", help="按Agent过滤")
    task_list_parser.add_argument("--limit", type=int, default=50, help="限制数量")
    
    submit_parser = task_sub.add_parser("submit", help="提交任务")
    submit_parser.add_argument("--type", required=True, help="任务类型")
    submit_parser.add_argument("--desc", help="任务描述")
    submit_parser.add_argument("--priority", type=int, default=5, help="优先级")
    submit_parser.add_argument("--target", help="目标Agent")
    submit_parser.add_argument("--payload", help="任务数据(JSON)")
    
    task_status_parser = task_sub.add_parser("status", help="任务状态")
    task_status_parser.add_argument("task_id", help="任务ID")
    
    task_update_parser = task_sub.add_parser("update", help="更新任务")
    task_update_parser.add_argument("task_id", help="任务ID")
    task_update_parser.add_argument("--status", required=True, help="状态")
    task_update_parser.add_argument("--result", help="结果(JSON)")
    task_update_parser.add_argument("--error", help="错误信息")
    
    task_cancel_parser = task_sub.add_parser("cancel", help="取消任务")
    task_cancel_parser.add_argument("task_id", help="任务ID")
    
    task_sub.add_parser("pending", help="待处理任务")
    
    # Message sub-commands
    msg_parser = subparsers.add_parser("message", help="消息管理")
    msg_sub = msg_parser.add_subparsers(dest="msg_cmd", help="消息子命令")
    
    msg_list_parser = msg_sub.add_parser("list", help="列出消息")
    msg_list_parser.add_argument("--agent-id", help="Agent ID")
    msg_list_parser.add_argument("--unread", action="store_true", help="仅未读")
    
    msg_send_parser = msg_sub.add_parser("send", help="发送消息")
    msg_send_parser.add_argument("--from", dest="from_agent", required=True, help="发送者")
    msg_send_parser.add_argument("--to", dest="to_agent", required=True, help="接收者")
    msg_send_parser.add_argument("--content", required=True, help="内容")
    msg_send_parser.add_argument("--type", default="text", help="消息类型")
    
    msg_read_parser = msg_sub.add_parser("mark-read", help="标记已读")
    msg_read_parser.add_argument("agent_id", help="Agent ID")
    msg_read_parser.add_argument("message_id", help="消息ID")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    cli = UnifiedCollabCLI(json_output=args.json)
    
    try:
        # Status
        if args.command == "status":
            cli._output(cli.cmd_status())
        
        # Stats
        elif args.command == "stats":
            cli._output(cli.cmd_stats())
        
        # Monitor
        elif args.command == "monitor":
            cli._output(cli.cmd_monitor())
        
        # Agent commands
        elif args.command == "agent":
            if args.agent_cmd == "list":
                cli._output(cli.cmd_agent_list(args.status, args.capability))
            elif args.agent_cmd == "register":
                capabilities = [c.strip() for c in args.caps.split(",")]
                metadata = json.loads(args.metadata) if args.metadata else None
                cli._output(cli.cmd_agent_register(args.name, capabilities, metadata))
            elif args.agent_cmd == "unregister":
                cli._output(cli.cmd_agent_unregister(args.agent_id))
            elif args.agent_cmd == "heartbeat":
                cli._output(cli.cmd_agent_heartbeat(args.agent_id, args.status, args.health))
            elif args.agent_cmd == "info":
                cli._output(cli.cmd_agent_info(args.agent_id))
            else:
                agent_parser.print_help()
        
        # Task commands
        elif args.command == "task":
            if args.task_cmd == "list":
                cli._output(cli.cmd_task_list(args.status, args.agent_id, args.limit))
            elif args.task_cmd == "submit":
                payload = json.loads(args.payload) if args.payload else None
                cli._output(cli.cmd_task_submit(args.type, args.desc, args.priority, args.target, payload))
            elif args.task_cmd == "status":
                cli._output(cli.cmd_task_status(args.task_id))
            elif args.task_cmd == "update":
                result = json.loads(args.result) if args.result else None
                cli._output(cli.cmd_task_update(args.task_id, args.status, result, args.error))
            elif args.task_cmd == "cancel":
                cli._output(cli.cmd_task_cancel(args.task_id))
            elif args.task_cmd == "pending":
                cli._output(cli.cmd_task_pending())
            else:
                task_parser.print_help()
        
        # Message commands
        elif args.command == "message":
            if args.msg_cmd == "list":
                cli._output(cli.cmd_message_list(args.agent_id, args.unread))
            elif args.msg_cmd == "send":
                cli._output(cli.cmd_message_send(args.from_agent, args.to_agent, args.content, args.type))
            elif args.msg_cmd == "mark-read":
                cli._output(cli.cmd_message_mark_read(args.agent_id, args.message_id))
            else:
                msg_parser.print_help()
        
        else:
            parser.print_help()
    
    except Exception as e:
        if args.json:
            print(json.dumps({"success": False, "error": str(e)}, ensure_ascii=False))
        else:
            print(f"❌ 错误: {e}", file=sys.stderr)
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())