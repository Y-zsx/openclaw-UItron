#!/usr/bin/env python3
"""
负载均衡与故障转移 REST API 服务
================================
提供负载均衡器管理的RESTful接口

端口: 8093
"""

import json
import time
import threading
from datetime import datetime
from flask import Flask, jsonify, request
from load_balancer import (
    LoadBalancer, LoadBalanceStrategy, FailoverManager, FailoverConfig,
    get_load_balancer, get_failover_manager
)

app = Flask(__name__)

# 全局负载均衡器和故障转移管理器
_lb = None
_fm = None
_config = None


def get_lb():
    global _lb
    if _lb is None:
        strategy_name = request.args.get('strategy', 'least_load')
        try:
            strategy = LoadBalanceStrategy(strategy_name)
        except ValueError:
            strategy = LoadBalanceStrategy.LEAST_LOAD
        _lb = get_load_balancer(strategy)
    return _lb


def get_fm():
    global _fm
    if _fm is None:
        _fm = get_failover_manager()
    return _fm


# ========== 负载均衡API ==========

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "load-balancer-api",
        "timestamp": datetime.now().isoformat()
    })


@app.route('/api/agents/register', methods=['POST'])
def register_agent():
    """注册Agent"""
    data = request.get_json() or {}
    agent_id = data.get('agent_id')
    weight = data.get('weight', 100)
    
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400
    
    metrics = get_lb().register_agent(agent_id, weight)
    return jsonify({
        "message": "Agent registered",
        "agent_id": agent_id,
        "metrics": metrics.to_dict()
    })


@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def unregister_agent(agent_id):
    """注销Agent"""
    get_lb().unregister_agent(agent_id)
    return jsonify({"message": "Agent unregistered", "agent_id": agent_id})


@app.route('/api/agents', methods=['GET'])
def list_agents():
    """列出所有Agent"""
    metrics = get_lb().get_all_metrics()
    return jsonify(metrics)


@app.route('/api/agents/<agent_id>', methods=['GET'])
def get_agent(agent_id):
    """获取Agent详情"""
    metrics = get_lb().get_agent_metrics(agent_id)
    if metrics:
        return jsonify(metrics)
    return jsonify({"error": "Agent not found"}), 404


@app.route('/api/select', methods=['POST'])
def select_agent():
    """选择最佳Agent (负载均衡核心接口)"""
    data = request.get_json() or {}
    required_capability = data.get('capability')
    exclude = set(data.get('exclude', []))
    task_id = data.get('task_id')
    
    agent_id = get_lb().select_agent(required_capability, exclude)
    
    if agent_id:
        get_lb().agents[agent_id].increment_load()
        return jsonify({
            "selected_agent": agent_id,
            "task_id": task_id,
            "strategy": get_lb().strategy.value
        })
    
    return jsonify({"error": "No available agent"}), 503


@app.route('/api/agents/<agent_id>/complete', methods=['POST'])
def agent_complete(agent_id):
    """任务完成 - 记录执行时间"""
    data = request.get_json() or {}
    execution_time = data.get('execution_time', 0)
    
    metrics = get_lb().agents.get(agent_id)
    if metrics:
        metrics.update_execution_time(execution_time)
        metrics.decrement_load()
        return jsonify({"message": "Task completed", "metrics": metrics.to_dict()})
    
    return jsonify({"error": "Agent not found"}), 404


@app.route('/api/agents/<agent_id>/fail', methods=['POST'])
def agent_fail(agent_id):
    """任务失败"""
    data = request.get_json() or {}
    error = data.get('error', 'Unknown error')
    
    metrics = get_lb().agents.get(agent_id)
    if metrics:
        metrics.record_failure()
        metrics.decrement_load()
        return jsonify({"message": "Failure recorded", "metrics": metrics.to_dict()})
    
    return jsonify({"error": "Agent not found"}), 404


@app.route('/api/healthy', methods=['GET'])
def healthy_agents():
    """获取健康Agent列表"""
    agents = get_lb().get_healthy_agents()
    return jsonify({"healthy_agents": agents, "count": len(agents)})


# ========== 故障转移API ==========

@app.route('/api/failover/task', methods=['POST'])
def record_failure():
    """记录任务失败 (触发重试/转移)"""
    data = request.get_json() or {}
    task_id = data.get('task_id')
    agent_id = data.get('agent_id')
    error = data.get('error', 'Unknown error')
    task_data = data.get('task_data', {})
    
    if not task_id or not agent_id:
        return jsonify({"error": "task_id and agent_id required"}), 400
    
    result = get_fm().record_failure(task_id, agent_id, error, task_data)
    return jsonify(result)


@app.route('/api/failover/agent-failure', methods=['POST'])
def record_agent_failure():
    """记录Agent故障"""
    data = request.get_json() or {}
    agent_id = data.get('agent_id')
    
    if not agent_id:
        return jsonify({"error": "agent_id required"}), 400
    
    result = get_fm().record_agent_failure(agent_id)
    return jsonify(result)


@app.route('/api/failover/agent/<agent_id>/recover', methods=['POST'])
def recover_agent(agent_id):
    """标记Agent已恢复"""
    get_fm().mark_agent_recovered(agent_id)
    return jsonify({"message": "Agent marked as recovered", "agent_id": agent_id})


@app.route('/api/failover/tasks', methods=['GET'])
def failed_tasks():
    """获取失败任务列表"""
    tasks = get_fm().get_failed_tasks()
    return jsonify({"failed_tasks": tasks, "count": len(tasks)})


@app.route('/api/failover/task/<task_id>', methods=['DELETE'])
def clear_task(task_id):
    """清除任务记录"""
    get_fm().clear_task(task_id)
    return jsonify({"message": "Task cleared", "task_id": task_id})


@app.route('/api/failover/status', methods=['GET'])
def failover_status():
    """获取故障转移状态"""
    return jsonify(get_fm().get_status())


# ========== 配置API ==========

@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    """获取当前策略"""
    return jsonify({"strategy": get_lb().strategy.value})


@app.route('/api/strategy', methods=['PUT'])
def set_strategy():
    """设置负载均衡策略"""
    data = request.get_json() or {}
    strategy_name = data.get('strategy')
    
    try:
        strategy = LoadBalanceStrategy(strategy_name)
        get_lb().strategy = strategy
        return jsonify({"message": "Strategy updated", "strategy": strategy.value})
    except ValueError:
        return jsonify({"error": f"Invalid strategy: {strategy_name}"}), 400


# ========== 统计API ==========

@app.route('/api/stats', methods=['GET'])
def stats():
    """获取统计信息"""
    lb_metrics = get_lb().get_all_metrics()
    fm_status = get_fm().get_status()
    
    return jsonify({
        "load_balancer": lb_metrics,
        "failover": fm_status,
        "timestamp": datetime.now().isoformat()
    })


def run_api(host='0.0.0.0', port=8093):
    """运行API服务"""
    print(f"🚀 负载均衡API服务启动: http://{host}:{port}")
    print(f"📋 可用策略: {[s.value for s in LoadBalanceStrategy]}")
    app.run(host=host, port=port, threaded=True)


if __name__ == '__main__':
    run_api()