#!/usr/bin/env python3
"""
Agent任务执行器集成验证脚本
验证决策系统与Agent执行器的完整集成
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import json
from datetime import datetime

# 配置
DECISION_ENGINE_URL = "http://localhost:18120"
AGENT_EXECUTOR_URL = "http://localhost:8096"

class IntegrationValidator:
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def test(self, name: str, func):
        """执行测试"""
        print(f"\n🧪 测试: {name}")
        try:
            result = func()
            if result:
                print(f"   ✅ 通过")
                self.passed += 1
                self.results.append({"test": name, "status": "passed"})
            else:
                print(f"   ❌ 失败")
                self.failed += 1
                self.results.append({"test": name, "status": "failed"})
            return result
        except Exception as e:
            print(f"   ❌ 异常: {e}")
            self.failed += 1
            self.results.append({"test": name, "status": "error", "error": str(e)})
            return False
    
    def summary(self):
        """输出总结"""
        print("\n" + "="*50)
        print(f"📊 测试总结: {self.passed} 通过, {self.failed} 失败")
        print("="*50)
        return self.failed == 0


def test_agent_executor_health():
    """测试Agent执行器健康状态"""
    resp = requests.get(f"{AGENT_EXECUTOR_URL}/health", timeout=5)
    data = resp.json()
    return data.get("status") == "healthy"


def test_agent_executor_stats():
    """测试Agent执行器统计"""
    resp = requests.get(f"{AGENT_EXECUTOR_URL}/api/stats", timeout=5)
    data = resp.json()
    return "total_executions" in data


def test_shell_execution():
    """测试Shell命令执行"""
    from agent_executor_integration import AgentExecutorIntegration
    integration = AgentExecutorIntegration()
    result = integration.execute_shell("echo 'Integration Test'")
    return result.get("success", False)


def test_decision_engine_health():
    """测试决策引擎健康状态"""
    resp = requests.get(f"{DECISION_ENGINE_URL}/health", timeout=5)
    data = resp.json()
    return data.get("status") == "ok"


def test_decision_creation():
    """测试决策创建"""
    resp = requests.post(
        f"{DECISION_ENGINE_URL}/decide",
        json={
            "context": {"type": "integration_test", "source": "agent_executor"},
            "options": ["continue", "stop"]
        },
        timeout=10
    )
    data = resp.json()
    return data.get("success", False)


def test_integration_module_import():
    """测试集成模块导入"""
    try:
        from agent_executor_integration import AgentExecutorIntegration
        integration = AgentExecutorIntegration()
        return integration.is_available()
    except Exception as e:
        print(f"   导入错误: {e}")
        return False


def test_all_services():
    """测试所有相关服务端口"""
    ports = [18120, 18121, 18122, 18123, 18124, 18125, 8096]
    all_ok = True
    for port in ports:
        try:
            resp = requests.get(f"http://localhost:{port}/health", timeout=3)
            if resp.status_code != 200:
                all_ok = False
                print(f"   端口 {port} 返回状态码 {resp.status_code}")
        except:
            all_ok = False
            print(f"   端口 {port} 无响应")
    return all_ok


def main():
    print("="*50)
    print("🔍 Agent任务执行器集成验证")
    print("="*50)
    
    validator = IntegrationValidator()
    
    # 1. 服务健康检查
    validator.test("决策引擎健康检查", test_decision_engine_health)
    validator.test("Agent执行器健康检查", test_agent_executor_health)
    validator.test("所有服务端口可用", test_all_services)
    
    # 2. Agent执行器功能测试
    validator.test("Agent执行器统计API", test_agent_executor_stats)
    validator.test("集成模块导入", test_integration_module_import)
    validator.test("Shell命令执行", test_shell_execution)
    
    # 3. 决策系统集成测试
    validator.test("决策创建功能", test_decision_creation)
    
    # 输出总结
    success = validator.summary()
    
    # 保存测试结果
    result_data = {
        "timestamp": datetime.now().isoformat(),
        "passed": validator.passed,
        "failed": validator.failed,
        "results": validator.results
    }
    
    with open("/root/.openclaw/workspace/ultron/agent-executor/integration_test_results.json", "w") as f:
        json.dump(result_data, f, indent=2)
    
    print(f"\n📁 测试结果已保存")
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())