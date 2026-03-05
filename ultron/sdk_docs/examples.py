#!/usr/bin/env python3
"""
多智能体协作网络 SDK 示例代码
奥创第81世: SDK使用示例与教程
"""

import json
import time
from datetime import datetime

# ============================================================
# 示例1: Agent注册与发现
# ============================================================

def example_agent_registry():
    """Agent注册与发现示例"""
    
    class AgentRegistry:
        def __init__(self):
            self.agents = {}
            
        def register(self, name, capabilities, endpoint):
            agent_id = f"agent-{len(self.agents) + 1}"
            self.agents[agent_id] = {
                "name": name,
                "capabilities": capabilities,
                "endpoint": endpoint,
                "status": "active",
                "registered_at": datetime.now().isoformat()
            }
            return agent_id
        
        def find(self, capability):
            return [
                aid for aid, agent in self.agents.items()
                if capability in agent["capabilities"]
            ]
        
        def get_status(self, agent_id):
            return self.agents.get(agent_id, {}).get("status", "unknown")
    
    # 使用示例
    registry = AgentRegistry()
    
    # 注册多个Agent
    agent1 = registry.register(
        name="data-processor",
        capabilities=["etl", "transform", "validate"],
        endpoint="http://localhost:8001"
    )
    
    agent2 = registry.register(
        name="analytics-engine",
        capabilities=["analysis", "visualization", "reporting"],
        endpoint="http://localhost:8002"
    )
    
    agent3 = registry.register(
        name="ml-pipeline",
        capabilities=["ml", "prediction", "etl"],
        endpoint="http://localhost:8003"
    )
    
    # 查找具有分析能力的Agent
    analysts = registry.find("analysis")
    print(f"分析类Agent: {analysts}")
    
    # 查找具有ETL能力的Agent
    etl_agents = registry.find("etl")
    print(f"ETL类Agent: {etl_agents}")
    
    return {"agents": registry.agents, "analysts": analysts, "etl_agents": etl_agents}


# ============================================================
# 示例2: 协作会话管理
# ============================================================

def example_collaboration_session():
    """协作会话管理示例"""
    
    class CollaborationManager:
        def __init__(self):
            self.sessions = {}
            
        def create_session(self, name, agents, strategy="parallel"):
            session_id = f"session-{len(self.sessions) + 1}"
            self.sessions[session_id] = {
                "name": name,
                "agents": agents,
                "strategy": strategy,
                "status": "running",
                "created_at": datetime.now().isoformat(),
                "tasks": [],
                "results": []
            }
            return session_id
        
        def dispatch_task(self, session_id, task, context=None):
            session = self.sessions.get(session_id)
            if not session:
                raise ValueError(f"Session {session_id} not found")
            
            task_id = f"task-{len(session['tasks']) + 1}"
            task_obj = {
                "id": task_id,
                "task": task,
                "context": context or {},
                "status": "pending",
                "assigned_to": session["agents"][0]
            }
            session["tasks"].append(task_obj)
            return task_id
        
        def get_session_status(self, session_id):
            return self.sessions.get(session_id, {}).get("status")
    
    # 使用示例
    manager = CollaborationManager()
    
    # 创建并行处理会话
    session_id = manager.create_session(
        name="data-analysis-pipeline",
        agents=["agent-1", "agent-2", "agent-3"],
        strategy="parallel"
    )
    
    # 分发多个任务
    task1 = manager.dispatch_task(session_id, "收集数据", {"source": "db"})
    task2 = manager.dispatch_task(session_id, "清洗数据", {"rules": "standard"})
    task3 = manager.dispatch_task(session_id, "生成报告", {"format": "html"})
    
    print(f"会话 {session_id} 状态: {manager.get_session_status(session_id)}")
    
    return {"session_id": session_id, "tasks": [task1, task2, task3]}


# ============================================================
# 示例3: 结果聚合器
# ============================================================

def example_result_aggregator():
    """结果聚合器示例"""
    
    class ResultAggregator:
        def __init__(self):
            pass
        
        def aggregate(self, results, strategy="weighted"):
            if strategy == "weighted":
                return self._weighted_aggregate(results)
            elif strategy == "majority":
                return self._majority_aggregate(results)
            elif strategy == "chain":
                return self._chain_aggregate(results)
            else:
                raise ValueError(f"Unknown strategy: {strategy}")
        
        def _weighted_aggregate(self, results):
            total_weight = sum(r.get("weight", 1) for r in results)
            weighted_sum = sum(
                r.get("value", 0) * r.get("weight", 1) 
                for r in results
            )
            return {
                "strategy": "weighted",
                "result": weighted_sum / total_weight if total_weight > 0 else 0,
                "sources": len(results)
            }
        
        def _majority_aggregate(self, results):
            values = [r.get("value") for r in results]
            from collections import Counter
            counts = Counter(values)
            return {
                "strategy": "majority",
                "result": counts.most_common(1)[0][0],
                "sources": len(results)
            }
        
        def _chain_aggregate(self, results):
            # 链式传递，将前一个结果传给下一个
            chained = []
            for r in results:
                chained.append({
                    "value": r.get("value"),
                    "input_from": r.get("from")
                })
            return {
                "strategy": "chain",
                "result": chained,
                "sources": len(results)
            }
    
    # 使用示例
    aggregator = ResultAggregator()
    
    # 加权聚合
    weighted_results = [
        {"value": 100, "weight": 0.5},
        {"value": 200, "weight": 0.3},
        {"value": 150, "weight": 0.2}
    ]
    weighted = aggregator.aggregate(weighted_results, "weighted")
    print(f"加权聚合结果: {weighted}")
    
    # 多数投票
    majority_results = [
        {"value": "yes"},
        {"value": "yes"},
        {"value": "no"}
    ]
    majority = aggregator.aggregate(majority_results, "majority")
    print(f"多数投票结果: {majority}")
    
    return {"weighted": weighted, "majority": majority}


# ============================================================
# 示例4: 任务编排与管道
# ============================================================

def example_pipeline():
    """管道式任务处理示例"""
    
    class Pipeline:
        def __init__(self, stages):
            self.stages = stages
            self.results = []
            
        def run(self, input_data):
            current = input_data
            for stage in self.stages:
                print(f"执行阶段: {stage}")
                # 模拟每个阶段的处理
                current = self._process_stage(stage, current)
                self.results.append({"stage": stage, "result": current})
            return current
        
        def _process_stage(self, stage, data):
            # 模拟处理
            return {
                "stage": stage,
                "input": data,
                "output": f"{stage}-processed-{data.get('id', 'noid')}",
                "timestamp": datetime.now().isoformat()
            }
    
    # 使用示例
    pipeline = Pipeline([
        "data-collector",
        "preprocessor",
        "analyzer",
        "reporter"
    ])
    
    result = pipeline.run({"id": "task-001", "source": "api"})
    print(f"管道执行完成: {result['stage']}")
    
    return {"pipeline": pipeline.stages, "results": pipeline.results}


# ============================================================
# 示例5: 弹性会话与重试机制
# ============================================================

def example_resilient_session():
    """弹性会话与故障恢复示例"""
    
    class ResilientSession:
        def __init__(self, max_retries=3):
            self.max_retries = max_retries
            self.execution_log = []
            
        def execute_with_retry(self, task, on_failure=None):
            last_error = None
            
            for attempt in range(1, self.max_retries + 1):
                try:
                    self.execution_log.append({
                        "attempt": attempt,
                        "task": task,
                        "status": "success"
                    })
                    return {
                        "status": "success",
                        "attempt": attempt,
                        "result": f"Task '{task}' completed"
                    }
                except Exception as e:
                    last_error = str(e)
                    self.execution_log.append({
                        "attempt": attempt,
                        "task": task,
                        "status": "failed",
                        "error": last_error
                    })
                    print(f"尝试 {attempt} 失败: {last_error}")
                    
                    if on_failure:
                        task = on_failure(task, attempt)
            
            return {
                "status": "failed",
                "attempts": self.max_retries,
                "error": last_error
            }
    
    # 使用示例
    session = ResilientSession(max_retries=3)
    
    # 成功执行
    result1 = session.execute_with_retry("simple-task")
    print(f"任务1结果: {result1}")
    
    return {
        "execution_log": session.execution_log,
        "result": result1
    }


# ============================================================
# 主函数: 运行所有示例
# ============================================================

def main():
    print("=" * 60)
    print("多智能体协作网络 SDK 示例")
    print("=" * 60)
    
    print("\n[1] Agent注册与发现")
    print("-" * 40)
    result1 = example_agent_registry()
    print(f"结果: {json.dumps(result1, indent=2, ensure_ascii=False)[:200]}...")
    
    print("\n[2] 协作会话管理")
    print("-" * 40)
    result2 = example_collaboration_session()
    print(f"结果: {json.dumps(result2, indent=2, ensure_ascii=False)}")
    
    print("\n[3] 结果聚合器")
    print("-" * 40)
    result3 = example_result_aggregator()
    print(f"结果: {json.dumps(result3, indent=2, ensure_ascii=False)}")
    
    print("\n[4] 管道处理")
    print("-" * 40)
    result4 = example_pipeline()
    print(f"结果: 执行了 {len(result4['results'])} 个阶段")
    
    print("\n[5] 弹性会话")
    print("-" * 40)
    result5 = example_resilient_session()
    print(f"结果: {json.dumps(result5['result'], indent=2, ensure_ascii=False)}")
    
    print("\n" + "=" * 60)
    print("所有示例执行完成!")
    print("=" * 60)

if __name__ == "__main__":
    main()