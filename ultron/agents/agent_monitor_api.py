#!/usr/bin/env python3
"""
Agent Monitor API Service - 端口18098
提供RESTful API访问Agent监控数据
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from agent_monitor import get_monitor
from functools import wraps
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('AgentMonitorAPI')

app = Flask(__name__)
monitor = get_monitor()

# 简单的健康检查
@app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "service": "agent-monitor",
        "port": 18098,
        "timestamp": monitor.get_summary()["timestamp"]
    })

# 监控汇总
@app.route('/api/monitor/summary')
def api_summary():
    """获取监控汇总"""
    return jsonify(monitor.get_summary())

# 所有Agent列表
@app.route('/api/agents')
def api_agents():
    """获取所有Agent"""
    agents = monitor.get_all_agents()
    return jsonify({
        "total": len(agents),
        "agents": agents
    })

# 单个Agent详情
@app.route('/api/agents/<agent_id>')
def api_agent(agent_id):
    """获取指定Agent详情"""
    agent = monitor.get_agent(agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(agent)

# Agent统计
@app.route('/api/agents/<agent_id>/stats')
def api_agent_stats(agent_id):
    """获取Agent统计"""
    stats = monitor.get_agent_stats(agent_id)
    if not stats:
        return jsonify({"error": "Agent not found"}), 404
    return jsonify(stats)

# Agent历史指标
@app.route('/api/agents/<agent_id>/history')
def api_agent_history(agent_id):
    """获取Agent历史指标"""
    minutes = request.args.get('minutes', 60, type=int)
    history = monitor.get_history(agent_id, minutes)
    return jsonify({
        "agent_id": agent_id,
        "minutes": minutes,
        "data_points": len(history),
        "history": history
    })

# Agent趋势分析
@app.route('/api/agents/<agent_id>/trends')
def api_agent_trends(agent_id):
    """获取Agent趋势分析"""
    trends = monitor.get_trends(agent_id)
    return jsonify(trends)

# 收集快照
@app.route('/api/snapshot')
def api_snapshot():
    """收集并返回当前快照"""
    snapshot = monitor.collect_snapshot()
    return jsonify(snapshot)

# 告警列表
@app.route('/api/alerts')
def api_alerts():
    """获取当前告警"""
    alerts = monitor.check_alerts()
    return jsonify({
        "total": len(alerts),
        "alerts": alerts
    })

# 未解决告警
@app.route('/api/alerts/unresolved')
def api_unresolved_alerts():
    """获取未解决的告警"""
    alerts = monitor.get_unresolved_alerts()
    return jsonify({
        "total": len(alerts),
        "alerts": alerts
    })

# 解决告警
@app.route('/api/alerts/<int:alert_id>/resolve', methods=['POST'])
def api_resolve_alert(alert_id):
    """解决告警"""
    success = monitor.resolve_alert(alert_id)
    return jsonify({"success": success, "alert_id": alert_id})

# 注册Agent
@app.route('/api/agents/register', methods=['POST'])
def api_register_agent():
    """注册新Agent"""
    data = request.json
    agent_id = data.get('agent_id')
    agent_name = data.get('agent_name')
    metadata = data.get('metadata', {})
    
    if not agent_id or not agent_name:
        return jsonify({"error": "agent_id and agent_name required"}), 400
    
    success = monitor.register_agent(agent_id, agent_name, metadata)
    return jsonify({"success": success, "agent_id": agent_id})

# 注销Agent
@app.route('/api/agents/<agent_id>', methods=['DELETE'])
def api_unregister_agent(agent_id):
    """注销Agent"""
    success = monitor.unregister_agent(agent_id)
    return jsonify({"success": success, "agent_id": agent_id})

# 更新Agent状态
@app.route('/api/agents/<agent_id>/status', methods=['PUT'])
def api_update_status(agent_id):
    """更新Agent状态"""
    data = request.json
    status = data.get('status')
    if not status:
        return jsonify({"error": "status required"}), 400
    monitor.update_status(agent_id, status)
    return jsonify({"success": True, "agent_id": agent_id, "status": status})

# 记录任务
@app.route('/api/agents/<agent_id>/tasks', methods=['POST'])
def api_record_task(agent_id):
    """记录任务执行"""
    data = request.json
    success = data.get('success', False)
    response_time = data.get('response_time', 0)
    error = data.get('error')
    task_id = data.get('task_id')
    
    monitor.record_task(agent_id, success, response_time, error, task_id)
    return jsonify({"success": True, "agent_id": agent_id})

# 更新资源使用
@app.route('/api/agents/<agent_id>/resources', methods=['PUT'])
def api_update_resources(agent_id):
    """更新资源使用"""
    data = request.json
    cpu = data.get('cpu')
    memory = data.get('memory')
    monitor.update_resources(agent_id, cpu, memory)
    return jsonify({"success": True, "agent_id": agent_id})

# 配置阈值
@app.route('/api/config/thresholds', methods=['PUT'])
def api_set_thresholds():
    """设置阈值"""
    data = request.json
    monitor.set_thresholds(**data)
    return jsonify({"success": True, "thresholds": monitor.thresholds})

# 获取阈值
@app.route('/api/config/thresholds')
def api_get_thresholds():
    """获取当前阈值"""
    return jsonify(monitor.thresholds)

# 启动后台收集
@app.route('/api/background/start', methods=['POST'])
def api_start_background():
    """启动后台收集"""
    monitor.start_background_collection()
    return jsonify({"success": True, "message": "Background collection started"})

# 停止后台收集
@app.route('/api/background/stop', methods=['POST'])
def api_stop_background():
    """停止后台收集"""
    monitor.stop_background_collection()
    return jsonify({"success": True, "message": "Background collection stopped"})


if __name__ == '__main__':
    logger.info("启动 Agent Monitor API 服务 (端口 18098)")
    app.run(host='0.0.0.0', port=18098, debug=False)