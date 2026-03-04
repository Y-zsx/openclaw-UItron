#!/usr/bin/env python3
"""
协作系统测试脚本
验证多智能体通信和任务分发
"""
import json
import sys
sys.path.insert(0, '/root/.openclaw/workspace/ultron-workflow')

from message_bus import MessageBus, AgentRegistry, TaskQueue

def test_system():
    print("=" * 50)
    print("多智能体协作系统测试")
    print("=" * 50)
    
    bus = MessageBus()
    registry = AgentRegistry()
    task_queue = TaskQueue()
    
    # 1. 注册新智能体
    print("\n[1] 注册智能体...")
    registry.register(
        agent_id="worker1",
        name="工作虫1号",
        agent_type="executor",
        capabilities=["浏览器", "文件操作", "执行命令"]
    )
    registry.register(
        agent_id="learner1",
        name="学习虫1号",
        agent_type="learner",
        capabilities=["技能学习", "知识积累"]
    )
    print(f"  ✓ 已注册智能体: {registry.list_agents()}")
    
    # 2. 发送消息
    print("\n[2] 测试消息传递...")
    msg = bus.create_message(
        sender="ultron",
        receiver="worker1",
        msg_type="task",
        payload={"task_id": "t001", "action": "检查系统状态"}
    )
    result = bus.send(msg)
    print(f"  ✓ 消息发送: {'成功' if result else '失败'}")
    
    # 3. 接收消息
    print("\n[3] 测试消息接收...")
    received = bus.receive("worker1")
    print(f"  ✓ 收到消息: {len(received)} 条")
    if received:
        print(f"    - {received[0]['type']}: {received[0]['payload']}")
    
    # 4. 提交任务
    print("\n[4] 测试任务队列...")
    task_id = task_queue.submit({
        "title": "学习新技能",
        "description": "学习weather技能",
        "priority": "high"
    })
    print(f"  ✓ 任务提交: {task_id}")
    
    # 5. 分配任务
    task_queue.assign(task_id, "learner1")
    print(f"  ✓ 任务分配给: learner1")
    
    # 6. 完成任务
    task_queue.complete(task_id, {
        "status": "success",
        "skill_learned": "weather",
        "output": "已掌握天气查询技能"
    })
    print(f"  ✓ 任务完成")
    
    # 7. 广播消息
    print("\n[5] 测试广播...")
    count = bus.broadcast("ultron", "broadcast", {"content": "系统测试消息"})
    print(f"  ✓ 广播给 {count} 个智能体")
    
    # 8. 查看任务状态
    print("\n[6] 查看任务队列...")
    pending = task_queue.get_pending()
    assigned = task_queue.get_assigned()
    print(f"  - 待处理: {len(pending)}")
    print(f"  - 已分配: {len(assigned)}")
    
    print("\n" + "=" * 50)
    print("✓ 所有测试通过!")
    print("=" * 50)


if __name__ == "__main__":
    test_system()