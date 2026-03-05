#!/usr/bin/env python3
"""
协作网络API网关CLI
提供命令行接口管理Agent、任务、消息
"""

import argparse
import json
import requests
import sys
import time
from typing import Optional

DEFAULT_URL = "http://localhost:8089"


class GatewayCLI:
    """API网关命令行客户端"""
    
    def __init__(self, base_url: str = DEFAULT_URL):
        self.base_url = base_url.rstrip("/")
        
    def request(self, method: str, path: str, data: dict = None) -> dict:
        """发送请求"""
        url = f"{self.base_url}{path}"
        try:
            if method == "GET":
                resp = requests.get(url, params=data)
            elif method == "POST":
                resp = requests.post(url, json=data)
            elif method == "PUT":
                resp = requests.put(url, json=data)
            elif method == "DELETE":
                resp = requests.delete(url)
            else:
                return {"success": False, "error": f"未知方法: {method}"}
            
            return resp.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "error": f"无法连接到 {self.base_url}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    # 健康检查
    def health(self) -> dict:
        """健康检查"""
        return self.request("GET", "/health")
    
    def metrics(self) -> dict:
        """系统指标"""
        return self.request("GET", "/metrics")
    
    # Agent管理
    def list_agents(self, status: str = None, capability: str = None) -> dict:
        """列出Agent"""
        params = {}
        if status:
            params["status"] = status
        if capability:
            params["capability"] = capability
        return self.request("GET", "/agents", params)
    
    def get_agent(self, agent_id: str) -> dict:
        """获取Agent详情"""
        return self.request("GET", f"/agents/{agent_id}")
    
    def register_agent(self, agent_id: str, capabilities: list = None, 
                       metadata: dict = None) -> dict:
        """注册Agent"""
        data = {
            "agent_id": agent_id,
            "capabilities": capabilities or [],
            "metadata": metadata or {}
        }
        return self.request("POST", "/agents", data)
    
    def unregister_agent(self, agent_id: str) -> dict:
        """注销Agent"""
        return self.request("DELETE", f"/agents/{agent_id}")
    
    def heartbeat(self, agent_id: str, status: str = None, 
                  health_score: float = None) -> dict:
        """发送心跳"""
        data = {}
        if status:
            data["status"] = status
        if health_score is not None:
            data["health_score"] = health_score
        return self.request("POST", f"/agents/{agent_id}/heartbeat", data)
    
    def update_status(self, agent_id: str, status: str) -> dict:
        """更新状态"""
        return self.request("PUT", f"/agents/{agent_id}/status", {"status": status})
    
    # 任务管理
    def list_tasks(self, status: str = None, agent_id: str = None, 
                   limit: int = 50) -> dict:
        """列出任务"""
        params = {"limit": limit}
        if status:
            params["status"] = status
        if agent_id:
            params["agent_id"] = agent_id
        return self.request("GET", "/tasks", params)
    
    def get_task(self, task_id: str) -> dict:
        """获取任务详情"""
        return self.request("GET", f"/tasks/{task_id}")
    
    def submit_task(self, task_type: str, payload: dict = None, 
                    priority: int = 5, target_agent: str = None) -> dict:
        """提交任务"""
        data = {
            "task_type": task_type,
            "payload": payload or {},
            "priority": priority
        }
        if target_agent:
            data["target_agent"] = target_agent
        return self.request("POST", "/tasks", data)
    
    def update_task(self, task_id: str, status: str, 
                    result: any = None, error: str = None) -> dict:
        """更新任务状态"""
        data = {"status": status}
        if result:
            data["result"] = result
        if error:
            data["error"] = error
        return self.request("PUT", f"/tasks/{task_id}/status", data)
    
    def cancel_task(self, task_id: str) -> dict:
        """取消任务"""
        return self.request("POST", f"/tasks/{task_id}/cancel")
    
    def pending_tasks(self) -> dict:
        """获取待处理任务"""
        return self.request("GET", "/tasks/pending")
    
    # 消息
    def get_messages(self, agent_id: str, unread_only: bool = False) -> dict:
        """获取消息"""
        params = {"unread_only": str(unread_only).lower()}
        return self.request("GET", f"/messages/{agent_id}", params)
    
    def send_message(self, from_agent: str, to_agent: str, 
                     content: str, msg_type: str = "text") -> dict:
        """发送消息"""
        data = {
            "from": from_agent,
            "to": to_agent,
            "content": content,
            "type": msg_type
        }
        return self.request("POST", "/messages", data)
    
    def mark_read(self, agent_id: str, message_id: str) -> dict:
        """标记已读"""
        return self.request("POST", f"/messages/{agent_id}/{message_id}/read")


def main():
    parser = argparse.ArgumentParser(description="协作网络API网关CLI")
    parser.add_argument("--url", default=DEFAULT_URL, help="API网关地址")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # 健康检查
    subparsers.add_parser("health", help="健康检查")
    subparsers.add_parser("metrics", help="系统指标")
    
    # Agent命令
    agents_parser = subparsers.add_parser("agents", help="列出Agent")
    agents_parser.add_argument("--status", help="按状态过滤")
    agents_parser.add_argument("--capability", help="按能力过滤")
    
    subparsers.add_parser("register", help="注册Agent")
    register_parser = subparsers.add_parser("register")
    register_parser.add_argument("agent_id", help="Agent ID")
    register_parser.add_argument("--capabilities", nargs="+", help="能力列表")
    
    subparsers.add_parser("unregister", help="注销Agent")
    unreg_parser = subparsers.add_parser("unregister")
    unreg_parser.add_argument("agent_id", help="Agent ID")
    
    # 任务命令
    tasks_parser = subparsers.add_parser("tasks", help="列出任务")
    tasks_parser.add_argument("--status", help="按状态过滤")
    tasks_parser.add_argument("--agent-id", help="按Agent过滤")
    
    submit_parser = subparsers.add_parser("submit", help="提交任务")
    submit_parser.add_argument("task_type", help="任务类型")
    submit_parser.add_argument("--payload", help="任务数据 (JSON)")
    submit_parser.add_argument("--priority", type=int, default=5, help="优先级")
    
    # 消息命令
    msg_parser = subparsers.add_parser("messages", help="获取消息")
    msg_parser.add_argument("agent_id", help="Agent ID")
    msg_parser.add_argument("--unread", action="store_true", help="仅未读")
    
    args = parser.parse_args()
    
    cli = GatewayCLI(args.url)
    output = {}
    
    if args.command == "health":
        output = cli.health()
    elif args.command == "metrics":
        output = cli.metrics()
    elif args.command == "agents":
        output = cli.list_agents(args.status, args.capability)
    elif args.command == "register":
        output = cli.register_agent(args.agent_id, args.capabilities)
    elif args.command == "unregister":
        output = cli.unregister_agent(args.agent_id)
    elif args.command == "tasks":
        output = cli.list_tasks(args.status, args.agent_id)
    elif args.command == "submit":
        payload = json.loads(args.payload) if args.payload else None
        output = cli.submit_task(args.task_type, payload, args.priority)
    elif args.command == "messages":
        output = cli.get_messages(args.agent_id, args.unread)
    else:
        # 默认显示健康状态
        output = cli.health()
    
    if args.json:
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        if "success" in output and not output.get("success"):
            print(f"错误: {output.get('error')}", file=sys.stderr)
            sys.exit(1)
        
        # 格式化输出
        if "agents" in output:
            for agent in output["agents"]:
                print(f"{agent['agent_id']}: {agent['status']} "
                      f"(健康度: {agent['health_score']:.0f}%)")
        elif "tasks" in output:
            for task in output["tasks"]:
                print(f"{task['task_id']}: {task['task_type']} - {task['status']}")
        elif "messages" in output:
            for msg in output["messages"]:
                print(f"{msg['from']} -> {msg['to']}: {msg['content']}")
        elif "healthy" in output:
            status = "✓ 健康" if output["healthy"] else "✗ 异常"
            print(f"{status} | Agent: {output['total_agents']} | "
                  f"任务: {output['pending_tasks']}/{output['total_tasks']}")
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
    
    return 0 if output.get("success", True) else 1


if __name__ == "__main__":
    sys.exit(main())