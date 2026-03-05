#!/usr/bin/env python3
"""
奥创SDK移动端示例 - 移动端API与离线同步
展示移动端适配功能
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ultron_agent_sdk.client import MobileClient

def graphql_query_example(mobile_client: MobileClient):
    """GraphQL风格查询"""
    print("=" * 50)
    print("📱 GraphQL风格查询")
    print("=" * 50)
    
    # 查询Agent列表
    query = """
    {
        agents(status: "active") {
            id
            name
            status
            capabilities
        }
    }
    """
    
    print("\n查询: 获取活跃Agent列表")
    try:
        result = mobile_client.query(query)
        agents = result.get("data", {}).get("agents", [])
        print(f"   找到 {len(agents)} 个活跃Agent")
        for agent in agents[:3]:
            print(f"   - {agent['name']}: {agent['status']}")
    except Exception as e:
        print(f"   查询失败: {e}")
    
    # 带变量的查询
    query_with_vars = """
    query GetAgent($id: String!) {
        agent(id: $id) {
            id
            name
            status
            uptime
        }
    }
    """
    
    print("\n带变量的查询:")
    try:
        result = mobile_client.query(
            query_with_vars, 
            {"id": "agent-1"}
        )
        agent = result.get("data", {}).get("agent")
        if agent:
            print(f"   Agent: {agent['name']}, 运行时间: {agent.get('uptime', 0)}s")
    except Exception as e:
        print(f"   查询失败: {e}")


def batch_operations_example(mobile_client: MobileClient):
    """批量操作示例"""
    print("\n" + "=" * 50)
    print("📦 批量操作")
    print("=" * 50)
    
    operations = [
        {
            "operation": "get",
            "endpoint": "/agents",
            "params": {"status": "active"}
        },
        {
            "operation": "get", 
            "endpoint": "/agents",
            "params": {"status": "idle"}
        },
        {
            "operation": "get",
            "endpoint": "/health",
            "params": {}
        }
    ]
    
    print("\n执行3个批量操作:")
    try:
        results = mobile_client.batch(operations)
        print(f"   成功 {len(results)} 个结果")
        
        for i, result in enumerate(results):
            print(f"   操作{i+1}: {list(result.keys())[:3]}...")
    except Exception as e:
        print(f"   批量操作失败: {e}")


def offline_sync_example(mobile_client: MobileClient):
    """离线同步示例"""
    print("\n" + "=" * 50)
    print("🔄 离线同步")
    print("=" * 50)
    
    # 1. 获取同步令牌
    print("\n1. 获取同步令牌:")
    try:
        token = mobile_client.get_sync_token()
        print(f"   令牌: {token[:20]}..." if len(token) > 20 else f"   令牌: {token}")
    except Exception as e:
        print(f"   获取失败: {e}")
        token = None
    
    # 2. 获取初始变更
    print("\n2. 获取初始变更:")
    try:
        changes = mobile_client.get_changes("0")
        print(f"   变更数量: {len(changes)}")
        
        for change in changes[:3]:
            print(f"   - {change.get('type')}: {change.get('entity')}")
    except Exception as e:
        print(f"   获取变更失败: {e}")
    
    # 3. 增量同步
    print("\n3. 增量同步:")
    try:
        # 模拟同步点
        sync_point = "2026-03-06T00:00:00Z"
        changes = mobile_client.get_changes(sync_point)
        print(f"   自 {sync_point} 后的变更: {len(changes)}")
    except Exception as e:
        print(f"   增量同步失败: {e}")


def connection_management_example(mobile_client: MobileClient):
    """连接管理示例"""
    print("\n" + "=" * 50)
    print("📡 连接管理")
    print("=" * 50)
    
    # 注册设备连接
    print("\n1. 注册移动设备:")
    try:
        device_id = "mobile-device-001"
        platform = "android"
        
        success = mobile_client.register_connection(device_id, platform)
        print(f"   设备注册: {'成功' if success else '失败'}")
        print(f"   设备ID: {device_id}")
        print(f"   平台: {platform}")
    except Exception as e:
        print(f"   注册失败: {e}")
    
    # 注册iOS设备
    print("\n2. 注册iOS设备:")
    try:
        device_id = "mobile-device-002"
        platform = "ios"
        
        success = mobile_client.register_connection(device_id, platform)
        print(f"   设备注册: {'成功' if success else '失败'}")
    except Exception as e:
        print(f"   注册失败: {e}")


def main():
    base_url = os.getenv("ULTRON_API_URL", "http://localhost:18789/api/v3")
    
    print("=" * 50)
    print("📱 奥创SDK移动端示例")
    print("=" * 50)
    
    mobile_client = MobileClient(base_url=base_url)
    
    try:
        # GraphQL查询
        graphql_query_example(mobile_client)
        
        # 批量操作
        batch_operations_example(mobile_client)
        
        # 离线同步
        offline_sync_example(mobile_client)
        
        # 连接管理
        connection_management_example(mobile_client)
        
    except Exception as e:
        print(f"\n❌ 移动端示例错误: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n✅ 移动端示例完成!")

if __name__ == "__main__":
    main()