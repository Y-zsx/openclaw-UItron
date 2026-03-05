#!/usr/bin/env python3
"""
智能负载均衡器 (集成自动扩缩容)
===============================
增强版负载均衡器，结合自动扩缩容系统

功能:
- 多种负载均衡策略
- 与AutoScaler集成实现自动扩缩容
- 实时健康检查
- 流量分配优化
- 性能指标收集

端口: 18161
"""

import json
import time
import threading
import requests
from datetime import datetime
from typing import Dict, List, Optional, Any
from flask import Flask, jsonify, request
from collections import defaultdict

# 导入自动扩缩容模块
import sys
sys.path.insert(0, '/root/.openclaw/workspace/ultron/agents')
from autoscaler import get_scaler, ScalingAction


app = Flask(__name__)

# 全局配置
class LoadBalancerConfig:
    """负载均衡配置"""
    def __init__(self):
        self.strategy = "least_load"  # 策略
        self.health_check_interval = 10  # 健康检查间隔(秒)
        self.health_check_timeout = 3  # 健康检查超时(秒)
        self.max_retries = 3  # 最大重试次数
        self.connection_timeout = 5  # 连接超时
        self.read_timeout = 30  # 读取超时
        self.enable_autoscaling = True  # 启用自动扩缩容
        self.auto_scale_callback = None


# Agent后端
class Backend:
    """后端Agent"""
    def __init__(self, agent_id: str, url: str, weight: int = 100):
        self.agent_id = agent_id
        self.url = url
        self.weight = weight
        self.status = "unknown"
        self.is_healthy = False
        self.current_connections = 0
        self.total_requests = 0
        self.failed_requests = 0
        self.avg_response_time = 0.0
        self.last_health_check = None
        self.health_check_failures = 0
        self.metadata = {}
    
    def to_dict(self) -> Dict:
        return {
            'agent_id': self.agent_id,
            'url': self.url,
            'weight': self.weight,
            'status': self.status,
            'is_healthy': self.is_healthy,
            'current_connections': self.current_connections,
            'total_requests': self.total_requests,
            'failed_requests': self.failed_requests,
            'avg_response_time': self.avg_response_time,
            'last_health_check': self.last_health_check,
            'health_check_failures': self.health_check_failures,
            'metadata': self.metadata
        }


class SmartLoadBalancer:
    """智能负载均衡器"""
    
    def __init__(self, name: str = "default"):
        self.name = name
        self.backends: Dict[str, Backend] = {}
        self.config = LoadBalancerConfig()
        self._lock = threading.Lock()
        self._health_check_thread = None
        self._running = False
        self._stats = {
            'total_requests': 0,
            'total_response_time': 0.0,
            'total_errors': 0,
            'last_updated': time.time()
        }
        
        # 策略权重
        self.strategy_weights = {
            'round_robin': 1,
            'least_connections': 2,
            'least_load': 3,
            'weighted': 2,
            'performance': 3,
            'adaptive': 4
        }
    
    def add_backend(self, agent_id: str, url: str, weight: int = 100) -> bool:
        """添加后端"""
        with self._lock:
            if agent_id in self.backends:
                return False
            
            backend = Backend(agent_id, url, weight)
            self.backends[agent_id] = backend
            return True
    
    def remove_backend(self, agent_id: str) -> bool:
        """移除后端"""
        with self._lock:
            if agent_id in self.backends:
                del self.backends[agent_id]
                return True
            return False
    
    def update_backend(self, agent_id: str, **kwargs) -> bool:
        """更新后端配置"""
        with self._lock:
            if agent_id not in self.backends:
                return False
            
            backend = self.backends[agent_id]
            for key, value in kwargs.items():
                if hasattr(backend, key):
                    setattr(backend, key, value)
            return True
    
    def get_healthy_backends(self) -> List[Backend]:
        """获取健康的后端列表"""
        with self._lock:
            return [b for b in self.backends.values() if b.is_healthy]
    
    def _select_round_robin(self, backends: List[Backend]) -> Optional[Backend]:
        """轮询策略"""
        if not backends:
            return None
        # 简单轮询
        index = int(time.time() * 1000) % len(backends)
        return backends[index]
    
    def _select_least_connections(self, backends: List[Backend]) -> Optional[Backend]:
        """最少连接策略"""
        if not backends:
            return None
        return min(backends, key=lambda b: b.current_connections)
    
    def _select_least_load(self, backends: List[Backend]) -> Optional[Backend]:
        """最低负载策略"""
        if not backends:
            return None
        # 综合考虑连接数和响应时间
        scored = []
        for b in backends:
            score = b.current_connections * (1 + b.avg_response_time / 1000)
            scored.append((b, score))
        return min(scored, key=lambda x: x[1])[0]
    
    def _select_weighted(self, backends: List[Backend]) -> Optional[Backend]:
        """加权策略"""
        if not backends:
            return None
        total_weight = sum(b.weight for b in backends)
        if total_weight == 0:
            return backends[0]
        
        rand = (time.time() * 1000) % total_weight
        cumulative = 0
        for b in backends:
            cumulative += b.weight
            if rand <= cumulative:
                return b
        return backends[0]
    
    def _select_performance(self, backends: List[Backend]) -> Optional[Backend]:
        """性能最优策略"""
        if not backends:
            return None
        # 选择平均响应时间最短的
        return min(backends, key=lambda b: b.avg_response_time if b.avg_response_time > 0 else float('inf'))
    
    def _select_adaptive(self, backends: List[Backend]) -> Optional[Backend]:
        """自适应策略 - 根据实时状态动态选择"""
        if not backends:
            return None
        
        # 计算综合得分
        scored = []
        for b in backends:
            # 考虑：连接数、响应时间、健康状态、权重
            conn_score = b.current_connections / 10  # 归一化
            resp_score = b.avg_response_time / 1000 if b.avg_response_time else 0
            health_bonus = 2 if b.is_healthy else -2
            weight_bonus = b.weight / 100
            
            total_score = health_bonus + weight_bonus - conn_score - resp_score
            scored.append((b, total_score))
        
        return max(scored, key=lambda x: x[1])[0]
    
    def select_backend(self, strategy: str = None) -> Optional[Backend]:
        """选择后端"""
        strategy = strategy or self.config.strategy
        healthy = self.get_healthy_backends()
        
        if not healthy:
            # 如果没有健康的，返回所有后端尝试
            with self._lock:
                if self.backends:
                    return list(self.backends.values())[0]
            return None
        
        selectors = {
            'round_robin': self._select_round_robin,
            'least_connections': self._select_least_connections,
            'least_load': self._select_least_load,
            'weighted': self._select_weighted,
            'performance': self._select_performance,
            'adaptive': self._select_adaptive
        }
        
        selector = selectors.get(strategy, self._select_adaptive)
        return selector(healthy)
    
    def _health_check(self, backend: Backend) -> bool:
        """健康检查"""
        try:
            # 尝试多个端口的健康检查端点
            resp = requests.get(
                f"{backend.url}/health",
                timeout=self.config.health_check_timeout
            )
            return resp.status_code == 200
        except:
            return False
    
    def _perform_health_check(self):
        """执行健康检查"""
        with self._lock:
            backends_copy = list(self.backends.values())
        
        for backend in backends_copy:
            is_healthy = self._health_check(backend)
            
            with self._lock:
                b = self.backends.get(backend.agent_id)
                if b:
                    b.last_health_check = datetime.now().isoformat()
                    
                    if is_healthy:
                        b.is_healthy = True
                        b.status = "healthy"
                        b.health_check_failures = 0
                    else:
                        b.health_check_failures += 1
                        if b.health_check_failures >= 3:
                            b.is_healthy = False
                            b.status = "unhealthy"
    
    def start_health_check(self):
        """启动健康检查"""
        if self._running:
            return
        
        self._running = True
        
        def health_check_loop():
            while self._running:
                try:
                    self._perform_health_check()
                except Exception as e:
                    print(f"Health check error: {e}")
                time.sleep(self.config.health_check_interval)
        
        self._health_check_thread = threading.Thread(
            target=health_check_loop, daemon=True
        )
        self._health_check_thread.start()
    
    def stop_health_check(self):
        """停止健康检查"""
        self._running = False
        if self._health_check_thread:
            self._health_check_thread.join(timeout=5)
    
    def record_request(self, backend_id: str, success: bool, response_time: float):
        """记录请求结果"""
        with self._lock:
            if backend_id not in self.backends:
                return
            
            backend = self.backends[backend_id]
            backend.total_requests += 1
            backend.current_connections = max(0, backend.current_connections - 1)
            
            if not success:
                backend.failed_requests += 1
            else:
                # 更新平均响应时间
                if backend.avg_response_time == 0:
                    backend.avg_response_time = response_time
                else:
                    backend.avg_response_time = (
                        backend.avg_response_time * 0.9 + response_time * 0.1
                    )
            
            # 更新全局统计
            self._stats['total_requests'] += 1
            self._stats['total_response_time'] += response_time
            if not success:
                self._stats['total_errors'] += 1
            self._stats['last_updated'] = time.time()
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            avg_response = 0
            if self._stats['total_requests'] > 0:
                avg_response = (
                    self._stats['total_response_time'] / 
                    self._stats['total_requests']
                )
            
            return {
                'total_requests': self._stats['total_requests'],
                'total_errors': self._stats['total_errors'],
                'avg_response_time': avg_response,
                'error_rate': (
                    self._stats['total_errors'] / 
                    max(1, self._stats['total_requests'])
                ),
                'strategy': self.config.strategy,
                'backends_count': len(self.backends),
                'healthy_backends': len(self.get_healthy_backends())
            }
    
    def get_backends(self) -> List[Dict]:
        """获取所有后端"""
        with self._lock:
            return [b.to_dict() for b in self.backends.values()]


# 全局负载均衡器
_lb = SmartLoadBalancer("main-lb")


# ========== API 端点 ==========

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        'status': 'ok',
        'service': 'smart-loadbalancer',
        'port': 18161
    })


@app.route('/api/backends', methods=['GET'])
def list_backends():
    return jsonify({
        'backends': _lb.get_backends(),
        'count': len(_lb.backends)
    })


@app.route('/api/backends', methods=['POST'])
def add_backend():
    data = request.json or {}
    agent_id = data.get('agent_id')
    url = data.get('url')
    weight = data.get('weight', 100)
    
    if not agent_id or not url:
        return jsonify({'error': 'agent_id and url required'}), 400
    
    success = _lb.add_backend(agent_id, url, weight)
    
    return jsonify({
        'success': success,
        'agent_id': agent_id,
        'url': url
    })


@app.route('/api/backends/<agent_id>', methods=['DELETE'])
def remove_backend(agent_id):
    success = _lb.remove_backend(agent_id)
    return jsonify({'success': success, 'agent_id': agent_id})


@app.route('/api/backends/<agent_id>', methods=['PUT'])
def update_backend(agent_id):
    data = request.json or {}
    success = _lb.update_backend(agent_id, **data)
    return jsonify({'success': success, 'agent_id': agent_id})


@app.route('/api/select', methods=['GET'])
def select_backend():
    """选择后端"""
    strategy = request.args.get('strategy', _lb.config.strategy)
    backend = _lb.select_backend(strategy)
    
    if not backend:
        return jsonify({'error': 'no available backend'}), 503
    
    # 增加连接数
    with _lb._lock:
        if backend.agent_id in _lb.backends:
            _lb.backends[backend.agent_id].current_connections += 1
    
    return jsonify({
        'selected': backend.agent_id,
        'url': backend.url,
        'strategy': strategy,
        'current_connections': backend.current_connections
    })


@app.route('/api/stats', methods=['GET'])
def get_stats():
    return jsonify(_lb.get_stats())


@app.route('/api/stats/reset', methods=['POST'])
def reset_stats():
    _lb._stats = {
        'total_requests': 0,
        'total_response_time': 0.0,
        'total_errors': 0,
        'last_updated': time.time()
    }
    return jsonify({'success': True})


@app.route('/api/strategy', methods=['GET'])
def get_strategy():
    return jsonify({
        'strategy': _lb.config.strategy,
        'available_strategies': list(_lb.strategy_weights.keys())
    })


@app.route('/api/strategy', methods=['PUT'])
def set_strategy():
    data = request.json or {}
    strategy = data.get('strategy')
    
    if strategy not in _lb.strategy_weights:
        return jsonify({
            'error': f'invalid strategy. available: {list(_lb.strategy_weights.keys())}'
        }), 400
    
    _lb.config.strategy = strategy
    return jsonify({'success': True, 'strategy': strategy})


# ========== 与AutoScaler集成 ==========

@app.route('/api/autoscale/integrate', methods=['POST'])
def integrate_autoscaler():
    """集成自动扩缩容"""
    data = request.json or {}
    agent_type = data.get('agent_type', 'default-agent')
    
    # 创建或获取AutoScaler
    scaler = get_scaler(agent_type)
    
    # 注册扩缩容回调
    def scale_callback(action, old_count, new_count, reason):
        if action == ScalingAction.SCALE_UP:
            # 添加新的后端实例
            for i in range(old_count, new_count):
                instance_id = f"{agent_type}-{i+1}"
                url = f"http://localhost:{18090 + i}"
                _lb.add_backend(instance_id, url)
                print(f"[LoadBalancer] Scaled up: added {instance_id}")
        
        elif action == ScalingAction.SCALE_DOWN:
            # 移除后端实例
            for i in range(new_count, old_count):
                instance_id = f"{agent_type}-{i+1}"
                _lb.remove_backend(instance_id)
                print(f"[LoadBalancer] Scaled down: removed {instance_id}")
    
    scaler.register_scale_callback(scale_callback)
    
    return jsonify({
        'success': True,
        'agent_type': agent_type,
        'autoscaling_enabled': True
    })


@app.route('/api/health-check/start', methods=['POST'])
def start_health_check():
    """启动健康检查"""
    _lb.start_health_check()
    return jsonify({'success': True, 'status': 'running'})


@app.route('/api/health-check/stop', methods=['POST'])
def stop_health_check():
    """停止健康检查"""
    _lb.stop_health_check()
    return jsonify({'success': True, 'status': 'stopped'})


@app.route('/api/health-check/trigger', methods=['POST'])
def trigger_health_check():
    """触发一次健康检查"""
    _lb._perform_health_check()
    return jsonify({
        'success': True,
        'backends': _lb.get_backends()
    })


# ========== 请求代理 ==========

@app.route('/api/proxy/<path:subpath>', methods=['GET', 'POST', 'PUT', 'DELETE'])
def proxy_request(subpath):
    """代理请求到后端"""
    backend = _lb.select_backend()
    
    if not backend:
        return jsonify({'error': 'no available backend'}), 503
    
    # 增加连接数
    with _lb._lock:
        if backend.agent_id in _lb.backends:
            _lb.backends[backend.agent_id].current_connections += 1
    
    # 转发请求
    target_url = f"{backend.url}/{subpath}"
    
    try:
        start_time = time.time()
        
        if request.method == 'GET':
            resp = requests.get(
                target_url,
                params=request.args,
                timeout=(_lb.config.connection_timeout, _lb.config.read_timeout)
            )
        elif request.method == 'POST':
            resp = requests.post(
                target_url,
                json=request.json,
                timeout=(_lb.config.connection_timeout, _lb.config.read_timeout)
            )
        elif request.method == 'PUT':
            resp = requests.put(
                target_url,
                json=request.json,
                timeout=(_lb.config.connection_timeout, _lb.config.read_timeout)
            )
        elif request.method == 'DELETE':
            resp = requests.delete(
                target_url,
                timeout=(_lb.config.connection_timeout, _lb.config.read_timeout)
            )
        else:
            return jsonify({'error': 'method not supported'}), 405
        
        response_time = (time.time() - start_time) * 1000
        success = 200 <= resp.status_code < 400
        
        # 记录请求
        _lb.record_request(backend.agent_id, success, response_time)
        
        return resp.content, resp.status_code, dict(resp.headers)
    
    except Exception as e:
        _lb.record_request(backend.agent_id, False, 0)
        return jsonify({'error': str(e)}), 502


def main():
    import os
    port = int(os.environ.get('PORT', 18161))
    host = os.environ.get('HOST', '0.0.0.0')
    
    print(f"Starting Smart LoadBalancer on {host}:{port}")
    
    # 启动健康检查
    _lb.start_health_check()
    
    app.run(host=host, port=port, debug=False, threaded=True)


if __name__ == '__main__':
    main()