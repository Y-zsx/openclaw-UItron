#!/usr/bin/env python3
"""
自动扩缩容 REST API 服务
=======================
提供Agent服务自动扩缩容管理的RESTful接口

端口: 18160
"""

import json
import time
from flask import Flask, jsonify, request
from autoscaler import (
    AutoScaler, ScalingConfig, ScalingAction, 
    get_scaler, get_scaler_manager
)

app = Flask(__name__)

# 全局自动扩缩容管理器
_scaler_manager = get_scaler_manager()


def get_scaler_from_request():
    """从请求获取scaler"""
    agent_type = request.args.get('agent_type', 'default')
    config = None
    
    # 从请求体获取配置
    if request.is_json:
        data = request.json or {}
        config = ScalingConfig(
            min_instances=data.get('min_instances', 1),
            max_instances=data.get('max_instances', 10),
            scale_up_threshold=data.get('scale_up_threshold', 0.8),
            scale_down_threshold=data.get('scale_down_threshold', 0.3),
            scale_up_cooldown=data.get('scale_up_cooldown', 60),
            scale_down_cooldown=data.get('scale_down_cooldown', 300),
            scale_step=data.get('scale_step', 1),
            policy=data.get('policy', 'hybrid')
        )
    
    return get_scaler(agent_type, config)


# ========== 健康检查 ==========

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'autoscaler',
        'port': 18160,
        'timestamp': time.time()
    })


# ========== 扩缩容管理 ==========

@app.route('/api/scaler/create', methods=['POST'])
def create_scaler():
    """创建自动扩缩容器"""
    data = request.json or {}
    agent_type = data.get('agent_type', 'default')
    
    config = ScalingConfig(
        min_instances=data.get('min_instances', 1),
        max_instances=data.get('max_instances', 10),
        scale_up_threshold=data.get('scale_up_threshold', 0.8),
        scale_down_threshold=data.get('scale_down_threshold', 0.3),
        scale_up_cooldown=data.get('scale_up_cooldown', 60),
        scale_down_cooldown=data.get('scale_down_cooldown', 300),
        scale_step=data.get('scale_step', 1),
        policy=data.get('policy', 'hybrid')
    )
    
    scaler = get_scaler(agent_type, config)
    
    return jsonify({
        'success': True,
        'agent_type': agent_type,
        'config': {
            'min_instances': config.min_instances,
            'max_instances': config.max_instances,
            'scale_up_threshold': config.scale_up_threshold,
            'scale_down_threshold': config.scale_down_threshold,
            'scale_up_cooldown': config.scale_up_cooldown,
            'scale_down_cooldown': config.scale_down_cooldown,
            'scale_step': config.scale_step,
            'policy': config.policy
        }
    })


@app.route('/api/scaler/<agent_type>/start', methods=['POST'])
def start_scaling(agent_type):
    """启动自动扩缩容"""
    scaler = get_scaler(agent_type)
    interval = request.json.get('interval', 30) if request.json else 30
    
    scaler.start_auto_scaling(interval)
    
    return jsonify({
        'success': True,
        'agent_type': agent_type,
        'status': 'running',
        'interval': interval
    })


@app.route('/api/scaler/<agent_type>/stop', methods=['POST'])
def stop_scaling(agent_type):
    """停止自动扩缩容"""
    scaler = get_scaler(agent_type)
    scaler.stop_auto_scaling()
    
    return jsonify({
        'success': True,
        'agent_type': agent_type,
        'status': 'stopped'
    })


@app.route('/api/scaler/<agent_type>/status', methods=['GET'])
def get_status(agent_type):
    """获取扩缩容状态"""
    scaler = get_scaler(agent_type)
    return jsonify(scaler.get_status())


@app.route('/api/scaler/<agent_type>/scale_up', methods=['POST'])
def manual_scale_up(agent_type):
    """手动扩容"""
    scaler = get_scaler(agent_type)
    reason = (request.json.get('reason') if request.json else None) or "手动触发"
    
    success = scaler.scale_up(reason)
    
    return jsonify({
        'success': success,
        'agent_type': agent_type,
        'action': 'scale_up',
        'current_instances': len(scaler.instances),
        'reason': reason
    })


@app.route('/api/scaler/<agent_type>/scale_down', methods=['POST'])
def manual_scale_down(agent_type):
    """手动缩容"""
    scaler = get_scaler(agent_type)
    reason = (request.json.get('reason') if request.json else None) or "手动触发"
    
    success = scaler.scale_down(reason)
    
    return jsonify({
        'success': success,
        'agent_type': agent_type,
        'action': 'scale_down',
        'current_instances': len(scaler.instances),
        'reason': reason
    })


@app.route('/api/scaler/<agent_type>/config', methods=['PUT'])
def update_config(agent_type):
    """更新扩缩容配置"""
    scaler = get_scaler(agent_type)
    data = request.json or {}
    
    # 更新配置
    if 'min_instances' in data:
        scaler.config.min_instances = data['min_instances']
    if 'max_instances' in data:
        scaler.config.max_instances = data['max_instances']
    if 'scale_up_threshold' in data:
        scaler.config.scale_up_threshold = data['scale_up_threshold']
    if 'scale_down_threshold' in data:
        scaler.config.scale_down_threshold = data['scale_down_threshold']
    if 'scale_up_cooldown' in data:
        scaler.config.scale_up_cooldown = data['scale_up_cooldown']
    if 'scale_down_cooldown' in data:
        scaler.config.scale_down_cooldown = data['scale_down_cooldown']
    if 'scale_step' in data:
        scaler.config.scale_step = data['scale_step']
    if 'policy' in data:
        scaler.config.policy = data['policy']
    
    return jsonify({
        'success': True,
        'agent_type': agent_type,
        'config': {
            'min_instances': scaler.config.min_instances,
            'max_instances': scaler.config.max_instances,
            'scale_up_threshold': scaler.config.scale_up_threshold,
            'scale_down_threshold': scaler.config.scale_down_threshold,
            'scale_up_cooldown': scaler.config.scale_up_cooldown,
            'scale_down_cooldown': scaler.config.scale_down_cooldown,
            'scale_step': scaler.config.scale_step,
            'policy': scaler.config.policy
        }
    })


# ========== 全局状态 ==========

@app.route('/api/scalers', methods=['GET'])
def list_scalers():
    """列出所有扩缩容器"""
    all_status = _scaler_manager.get_all_status()
    return jsonify({
        'total': len(all_status),
        'scalers': list(all_status.keys()),
        'status': all_status
    })


@app.route('/api/metrics/<agent_type>', methods=['GET'])
def get_metrics(agent_type):
    """获取实时指标"""
    scaler = get_scaler(agent_type)
    metrics = scaler.calculate_avg_metrics()
    
    return jsonify({
        'agent_type': agent_type,
        'timestamp': time.time(),
        'metrics': metrics,
        'instance_count': len(scaler.instances)
    })


@app.route('/api/history/<agent_type>', methods=['GET'])
def get_history(agent_type):
    """获取扩缩容历史"""
    scaler = get_scaler(agent_type)
    limit = request.args.get('limit', 10, type=int)
    
    history = scaler.scaling_history[-limit:]
    
    return jsonify({
        'agent_type': agent_type,
        'total_events': len(scaler.scaling_history),
        'events': [
            {
                'timestamp': e.timestamp,
                'action': e.action,
                'reason': e.reason,
                'old_instances': e.old_instances,
                'new_instances': e.new_instances,
                'metrics': e.metrics
            }
            for e in history
        ]
    })


# ========== 批量操作 ==========

@app.route('/api/scalers/start_all', methods=['POST'])
def start_all_scalers():
    """启动所有扩缩容器"""
    data = request.json or {}
    interval = data.get('interval', 30)
    
    all_status = _scaler_manager.get_all_status()
    results = {}
    
    for agent_type in all_status.keys():
        scaler = get_scaler(agent_type)
        scaler.start_auto_scaling(interval)
        results[agent_type] = 'started'
    
    return jsonify({
        'success': True,
        'interval': interval,
        'results': results
    })


@app.route('/api/scalers/stop_all', methods=['POST'])
def stop_all_scalers():
    """停止所有扩缩容器"""
    all_status = _scaler_manager.get_all_status()
    results = {}
    
    for agent_type in all_status.keys():
        scaler = get_scaler(agent_type)
        scaler.stop_auto_scaling()
        results[agent_type] = 'stopped'
    
    return jsonify({
        'success': True,
        'results': results
    })


# ========== 评估 ==========

@app.route('/api/scaler/<agent_type>/evaluate', methods=['POST'])
def evaluate(agent_type):
    """手动触发扩缩容评估"""
    scaler = get_scaler(agent_type)
    action = scaler.evaluate_scaling()
    
    return jsonify({
        'agent_type': agent_type,
        'action': action.value,
        'metrics': scaler.calculate_avg_metrics(),
        'current_instances': len(scaler.instances)
    })


def main():
    """启动服务"""
    import os
    
    port = int(os.environ.get('PORT', 18160))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starting AutoScaler API on {host}:{port}")
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()