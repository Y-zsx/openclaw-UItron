"""
Ultron Agent SDK CLI
命令行工具
"""

import os
import sys
import json
import argparse
from typing import Optional

from .client import (
    AgentClient,
    TaskClient, 
    CollaborationClient,
    MeshClient,
    MobileClient
)


def main():
    parser = argparse.ArgumentParser(
        description="奥创多智能体协作网络 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # Agent管理
  ultron agents list
  ultron agents get <agent-id>
  ultron agents register my-agent --capabilities compute,storage
  
  # 任务管理
  ultron tasks list --status pending
  ultron tasks create compute --payload '{"data": "test"}'
  ultron tasks wait <task-id>
  
  # 协作会话
  ultron sessions create --participants agent1,agent2
  ultron sessions list
  
  # 移动端API
  ultron mobile query '{agents{status}}'
  ultron mobile sync-token
        """
    )
    
    parser.add_argument("--url", default=os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3"),
                        help="API服务器地址")
    parser.add_argument("--key", default=os.getenv("ULTRON_API_KEY", ""),
                        help="API密钥")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # Agent命令
    agents_parser = subparsers.add_parser("agents", help="Agent管理")
    agents_sub = agents_parser.add_subparsers(dest="agent_command")
    
    list_cmd = agents_sub.add_parser("list", help="列出Agent")
    list_cmd.add_argument("--status", choices=["active", "idle", "busy", "offline"])
    list_cmd.add_argument("--capability")
    
    get_cmd = agents_sub.add_parser("get", help="获取Agent详情")
    get_cmd.add_argument("agent_id")
    
    reg_cmd = agents_sub.add_parser("register", help="注册Agent")
    reg_cmd.add_argument("name")
    reg_cmd.add_argument("--capabilities", required=True, help="逗号分隔的能力列表")
    reg_cmd.add_argument("--metadata", help="JSON元数据")
    
    # Task命令
    tasks_parser = subparsers.add_parser("tasks", help="任务管理")
    tasks_sub = tasks_parser.add_subparsers(dest="task_command")
    
    list_tasks = tasks_sub.add_parser("list", help="列出任务")
    list_tasks.add_argument("--status", choices=["pending", "running", "completed", "failed"])
    list_tasks.add_argument("--limit", type=int, default=50)
    
    create_task = tasks_sub.add_parser("create", help="创建任务")
    create_task.add_argument("task_type", help="任务类型")
    create_task.add_argument("--payload", required=True, help="JSON负载")
    create_task.add_argument("--priority", type=int, default=5)
    create_task.add_argument("--timeout", type=int, default=300)
    
    get_task = tasks_sub.add_parser("get", help="获取任务详情")
    get_task.add_argument("task_id")
    
    wait_task = tasks_sub.add_parser("wait", help="等待任务完成")
    wait_task.add_argument("task_id")
    wait_task.add_argument("--timeout", type=int, default=300)
    
    results_task = tasks_sub.add_parser("results", help="获取任务结果")
    results_task.add_argument("task_id")
    
    # Session命令
    sessions_parser = subparsers.add_parser("sessions", help="协作会话")
    sessions_sub = sessions_parser.add_subparsers(dest="session_command")
    
    list_sessions = sessions_sub.add_parser("list", help="列出会话")
    list_sessions.add_argument("--status", choices=["active", "paused", "completed"])
    
    create_session = sessions_sub.add_parser("create", help="创建会话")
    create_session.add_argument("--participants", required=True, help="逗号分隔的参与者")
    create_session.add_argument("--strategy", default="parallel", 
                               choices=["parallel", "sequential", "pipeline"])
    create_session.add_argument("--checkpoint", action="store_true", help="启用检查点")
    
    get_session = sessions_sub.add_parser("get", help="获取会话详情")
    get_session.add_argument("session_id")
    
    # 健康检查
    health_parser = subparsers.add_parser("health", help="健康检查")
    
    # 指标
    metrics_parser = subparsers.add_parser("metrics", help="监控指标")
    metrics_parser.add_argument("--period", default="5m", 
                               choices=["1m", "5m", "15m", "1h", "24h"])
    
    # 移动端API
    mobile_parser = subparsers.add_parser("mobile", help="移动端API")
    mobile_sub = mobile_parser.add_subparsers(dest="mobile_command")
    
    query_mobile = mobile_sub.add_parser("query", help="GraphQL查询")
    query_mobile.add_argument("query", help="查询语句")
    
    sync_token = mobile_sub.add_parser("sync-token", help="获取同步令牌")
    
    changes = mobile_sub.add_parser("changes", help="获取变更")
    changes.add_argument("since", help="从指定时间戳获取变更")
    
    batch = mobile_sub.add_parser("batch", help="批量操作")
    batch.add_argument("--operations", required=True, help="JSON操作数组")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化客户端
    base_kwargs = {"base_url": args.url, "api_key": args.key}
    
    try:
        if args.command == "agents":
            client = AgentClient(**base_kwargs)
            
            if args.agent_command == "list":
                agents = client.list(status=args.status, capability=args.capability)
                output = [a.__dict__ for a in agents]
                
            elif args.agent_command == "get":
                agent = client.get(args.agent_id)
                output = agent.__dict__
                
            elif args.agent_command == "register":
                capabilities = args.capabilities.split(",")
                metadata = json.loads(args.metadata) if args.metadata else {}
                agent = client.register(args.name, capabilities, metadata)
                output = agent.__dict__
            else:
                agents_parser.print_help()
                return
                
        elif args.command == "tasks":
            client = TaskClient(**base_kwargs)
            
            if args.task_command == "list":
                tasks = client.list(status=args.status, limit=args.limit)
                output = [t.__dict__ for t in tasks]
                
            elif args.task_command == "get":
                task = client.get(args.task_id)
                output = task.__dict__
                
            elif args.task_command == "create":
                payload = json.loads(args.payload)
                task = client.create(args.task_type, payload, args.priority, args.timeout)
                output = task.__dict__
                
            elif args.task_command == "wait":
                task = client.wait_for_completion(args.task_id, args.timeout)
                output = task.__dict__
                
            elif args.task_command == "results":
                result = client.results(args.task_id)
                output = result.__dict__
            else:
                tasks_parser.print_help()
                return
                
        elif args.command == "sessions":
            client = CollaborationClient(**base_kwargs)
            
            if args.session_command == "list":
                sessions = client.list_sessions(status=args.status)
                output = [s.__dict__ for s in sessions]
                
            elif args.session_command == "get":
                session = client.get_session(args.session_id)
                output = session.__dict__
                
            elif args.session_command == "create":
                participants = args.participants.split(",")
                session = client.create_session(participants, args.strategy, args.checkpoint)
                output = session.__dict__
            else:
                sessions_parser.print_help()
                return
                
        elif args.command == "health":
            client = AgentClient(**base_kwargs)
            health = client.health_check()
            output = health.__dict__
            
        elif args.command == "metrics":
            client = AgentClient(**base_kwargs)
            output = client.metrics(args.period)
            
        elif args.command == "mobile":
            client = MobileClient(**base_kwargs)
            
            if args.mobile_command == "query":
                output = client.query(args.query)
                
            elif args.mobile_command == "sync-token":
                token = client.get_sync_token()
                output = {"token": token}
                
            elif args.mobile_command == "changes":
                changes = client.get_changes(args.since)
                output = {"changes": changes}
                
            elif args.mobile_command == "batch":
                operations = json.loads(args.operations)
                results = client.batch(operations)
                output = {"results": results}
            else:
                mobile_parser.print_help()
                return
        else:
            parser.print_help()
            return
        
        # 输出结果
        if args.json:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
            
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()