#!/usr/bin/env python3
"""
奥创SDK完整教程 - 一步步学习SDK使用
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultron_agent_sdk import AgentClient, TaskClient, CollaborationClient
from ultron_agent_sdk.client import MeshClient, MobileClient

print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    奥创SDK完整教程                                    ║
║                 Ultron Agent SDK Tutorial                             ║
╚══════════════════════════════════════════════════════════════════════╝

本教程将带你从零开始学习如何使用奥创多智能体协作网络SDK。

目录:
--------
1. 环境准备
2. 基础概念
3. 第一个示例程序
4. 核心功能详解
5. 最佳实践
6. 故障排查

""")

print("""
═══════════════════════════════════════════════════════════════════════
1. 环境准备
═══════════════════════════════════════════════════════════════════════

安装SDK:
---------
    pip install ultron-agent-sdk

或开发模式安装:
---------
    cd ultron/agents/sdk
    pip install -e .

环境变量配置:
---------
    export ULTRON_API_URL="http://your-server:18789/api/v3"
    export ULTRON_API_KEY="your-api-key"

""")

print("""
═══════════════════════════════════════════════════════════════════════
2. 基础概念
═══════════════════════════════════════════════════════════════════════

奥创SDK包含5个核心客户端:

┌─────────────────┬──────────────────────────────────────────────────┐
│ 客户端           │ 职责                                             │
├─────────────────┼──────────────────────────────────────────────────┤
│ AgentClient     │ Agent注册、查询、管理                             │
│ TaskClient      │ 任务创建、查询、执行、结果获取                    │
│ CollaborationClient │ 协作会话管理                               │
│ MeshClient      │ 服务网格、负载均衡、熔断器                       │
│ MobileClient    │ 移动端API、GraphQL、离线同步                     │
└─────────────────┴──────────────────────────────────────────────────┘

""")

print("""
═══════════════════════════════════════════════════════════════════════
3. 第一个示例程序
═══════════════════════════════════════════════════════════════════════
""")

# 实际运行代码
base_url = os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")

print(f"连接到: {base_url}\n")

try:
    # 初始化客户端
    agent_client = AgentClient(base_url=base_url)
    task_client = TaskClient(base_url=base_url)
    
    # 健康检查
    print(">>> 健康检查")
    health = agent_client.health_check()
    print(f"系统状态: {health.status}")
    print(f"版本: {health.version}")
    print(f"运行时间: {health.uptime}秒\n")
    
    # 获取Agent列表
    print(">>> 获取Agent列表")
    agents = agent_client.list()
    print(f"总Agent数: {len(agents)}")
    
    # 显示前3个
    for agent in agents[:3]:
        print(f"  - {agent.name}: {agent.status}")
    print()
    
    # 获取任务列表
    print(">>> 获取任务列表")
    tasks = task_client.list(limit=5)
    print(f"最近任务数: {len(tasks)}")
    
    for task in tasks[:3]:
        print(f"  - {task.type}: {task.status}")
    print()
    
except Exception as e:
    print(f"连接错误: {e}")
    print("\n请确保:")
    print("1. 奥创服务正在运行")
    print("2. API地址配置正确")
    print("3. 网络连接正常")

print("""
═══════════════════════════════════════════════════════════════════════
4. 核心功能详解
═══════════════════════════════════════════════════════════════════════

4.1 Agent管理
-------------
""")

print("""
# 代码示例

from ultron_agent_sdk import AgentClient

client = AgentClient()

# 列出所有Agent
agents = client.list()

# 按状态筛选
active = client.list(status="active")

# 按能力筛选
compute_agents = client.list(capability="compute")

# 获取单个Agent
agent = client.get("agent-1")

# 注册新Agent
new_agent = client.register(
    name="my-agent",
    capabilities=["compute", "storage"]
)

# 更新Agent
updated = client.update("agent-1", status="busy")

# 注销Agent
client.unregister("agent-1")

""")

print("""
4.2 任务管理
-------------
""")

print("""
# 代码示例

from ultron_agent_sdk import TaskClient

client = TaskClient()

# 创建任务
task = client.create(
    task_type="compute",
    payload={"operation": "add", "a": 1, "b": 2},
    priority=5,
    timeout=60
)

# 等待完成
result = client.wait_for_completion(task.id, timeout=300)

# 获取结果
task_result = client.results(task.id)

# 取消任务
client.cancel(task.id)

""")

print("""
4.3 协作会话
-------------
""")

print("""
# 代码示例

from ultron_agent_sdk import CollaborationClient

client = CollaborationClient()

# 创建协作会话
session = client.create_session(
    participants=["agent-1", "agent-2", "agent-3"],
    strategy="parallel",  # 或 "sequential"
    checkpoint_enabled=True
)

# 获取会话详情
session = client.get_session(session.id)

# 列出所有会话
sessions = client.list_sessions()

# 结束会话
client.end_session(session.id)

""")

print("""
4.4 服务网格
-------------
""")

print("""
# 代码示例

from ultron_agent_sdk.client import MeshClient

client = MeshClient()

# 获取服务列表
services = client.list_services()

# 获取熔断器状态
breakers = client.circuit_breakers()

# (需要更多API...)

""")

print("""
═══════════════════════════════════════════════════════════════════════
5. 最佳实践
═══════════════════════════════════════════════════════════════════════

1. 错误处理
---------
    try:
        agent = client.get("agent-1")
    except AgentNotFoundError:
        print("Agent不存在")
    except AuthenticationError:
        print("认证失败")
    except UltronSDKError as e:
        print(f"SDK错误: {e}")

2. 资源管理
---------
    - 使用连接池（SDK内置）
    - 设置适当的超时时间
    - 及时释放资源

3. 性能优化
---------
    - 使用批量操作替代循环
    - 适当设置轮询间隔
    - 使用异步回调（如果支持）

4. 安全最佳实践
---------
    - 不要在代码中硬编码API密钥
    - 使用环境变量
    - 定期轮换密钥

""")

print("""
═══════════════════════════════════════════════════════════════════════
6. 故障排查
═══════════════════════════════════════════════════════════════════════

常见问题:
---------

Q: 连接超时
A: 检查服务器地址是否正确，网络是否通畅

Q: 认证失败
A: 确认API密钥是否正确，是否已过期

Q: 任务一直pending
A: 检查是否有可用的Agent，可能需要等待

Q: 返回数据为空
A: 可能是权限问题或数据不存在

获取帮助:
---------
- 查看API文档: openapi.yaml
- 查看SDK源码: client.py
- 运行示例: python examples/

═══════════════════════════════════════════════════════════════════════

教程完成！开始使用SDK构建你的应用吧。

""")

print("""
快速参考
=========

安装:     pip install ultron-agent-sdk
导入:     from ultron_agent_sdk import AgentClient, TaskClient
初始化:   client = AgentClient(base_url="http://localhost:18789/api/v3")
使用:     agents = client.list()

示例文件:
- 01_basic_usage.py    基础示例
- 02_advanced_workflow.py  高级工作流
- 03_monitoring.py     监控示例
- 04_mobile.py         移动端示例
""")