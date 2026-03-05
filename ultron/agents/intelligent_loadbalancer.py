#!/usr/bin/env python3
"""
多智能体协作网络 - 智能负载均衡器
Intelligent Load Balancer with Adaptive Algorithms
"""

import time
import random
import threading
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import json

class AgentNode:
    """Agent节点"""
    
    def __init__(self, agent_id: str, agent_type: str, weight: int = 1):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.weight = weight
        self.active = True
        self.current_load = 0
        self.total_requests = 0
        self.failed_requests = 0
        self.avg_response_time = 0
        self.response_times = []
        self.last_health_check = datetime.now()
        self.consecutive_failures = 0
        
    def add_request(self, response_time: float, success: bool = True):
        """添加请求记录"""
        self.total_requests += 1
        self.response_times.append(response_time)
        if len(self.response_times) > 100:
            self.response_times = self.response_times[-100:]
        
        if not success:
            self.failed_requests += 1
            self.consecutive_failures += 1
        else:
            self.consecutive_failures = 0
            
        self.avg_response_time = sum(self.response_times) / len(self.response_times)
    
    @property
    def health_score(self) -> float:
        """健康评分 (0-100)"""
        if not self.active:
            return 0
        
        # 基础分数
        score = 100
        
        # 失败率扣分
        if self.total_requests > 0:
            fail_rate = self.failed_requests / self.total_requests
            score -= fail_rate * 50
        
        # 响应时间扣分 (以200ms为基准)
        if self.avg_response_time > 200:
            score -= (self.avg_response_time - 200) / 10
        
        # 连续失败扣分
        score -= self.consecutive_failures * 10
        
        return max(0, min(100, score))
    
    @property
    def effective_weight(self) -> int:
        """有效权重 (根据健康状况动态调整)"""
        health_factor = self.health_score / 100
        return int(self.weight * health_factor)


class IntelligentLoadBalancer:
    """智能负载均衡器"""
    
    ALGORITHMS = ['round_robin', 'weighted_rr', 'least_conn', 'adaptive', 'random']
    
    def __init__(self, algorithm: str = 'adaptive'):
        self.algorithm = algorithm
        self.nodes: Dict[str, AgentNode] = {}
        self._lock = threading.Lock()
        self._rr_index = defaultdict(int)
        self._conn_count = defaultdict(int)
        self._request_history = []
        
    def register_node(self, agent_id: str, agent_type: str, weight: int = 1):
        """注册节点"""
        with self._lock:
            node = AgentNode(agent_id, agent_type, weight)
            self.nodes[agent_id] = node
            print(f"✅ 注册节点: {agent_id} (type: {agent_type}, weight: {weight})")
    
    def unregister_node(self, agent_id: str):
        """注销节点"""
        with self._lock:
            if agent_id in self.nodes:
                del self.nodes[agent_id]
                print(f"❌ 注销节点: {agent_id}")
    
    def select_node(self, agent_type: str = None) -> Optional[AgentNode]:
        """选择最佳节点"""
        with self._lock:
            # 过滤活跃节点
            candidates = [n for n in self.nodes.values() 
                         if n.active and (agent_type is None or n.agent_type == agent_type)]
            
            if not candidates:
                return None
            
            if self.algorithm == 'round_robin':
                return self._round_robin(candidates)
            elif self.algorithm == 'weighted_rr':
                return self._weighted_rr(candidates)
            elif self.algorithm == 'least_conn':
                return self._least_connections(candidates)
            elif self.algorithm == 'adaptive':
                return self._adaptive(candidates)
            elif self.algorithm == 'random':
                return random.choice(candidates)
            else:
                return candidates[0]
    
    def _round_robin(self, candidates: List[AgentNode]) -> AgentNode:
        """轮询"""
        key = id(candidates)
        node = candidates[self._rr_index[key] % len(candidates)]
        self._rr_index[key] += 1
        return node
    
    def _weighted_rr(self, candidates: List[AgentNode]) -> AgentNode:
        """加权轮询"""
        total_weight = sum(n.effective_weight for n in candidates)
        if total_weight == 0:
            return random.choice(candidates)
        
        rand = random.randint(1, total_weight)
        cumulative = 0
        
        for node in candidates:
            cumulative += node.effective_weight
            if rand <= cumulative:
                return node
        
        return candidates[0]
    
    def _least_connections(self, candidates: List[AgentNode]) -> AgentNode:
        """最少连接数"""
        return min(candidates, key=lambda n: n.current_load)
    
    def _adaptive(self, candidates: List[AgentNode]) -> AgentNode:
        """自适应算法 - 综合考虑负载、响应时间、健康状况"""
        scored = []
        for node in candidates:
            # 归一化分数
            load_score = 100 - min(node.current_load * 10, 100)  # 负载越低越好
            response_score = max(0, 100 - node.avg_response_time)  # 响应越快越好
            health_score = node.health_score
            
            # 加权总分
            total_score = (
                load_score * 0.3 +
                response_score * 0.3 +
                health_score * 0.4
            )
            scored.append((node, total_score))
        
        # 选择分数最高的
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]
    
    def record_request(self, agent_id: str, response_time: float, success: bool = True):
        """记录请求结果"""
        with self._lock:
            if agent_id in self.nodes:
                node = self.nodes[agent_id]
                node.add_request(response_time, success)
                
                if success:
                    self._request_history.append({
                        'time': datetime.now(),
                        'agent_id': agent_id,
                        'response_time': response_time
                    })
                    
                    # 保留历史记录 (最近1000条)
                    if len(self._request_history) > 1000:
                        self._request_history = self._request_history[-1000:]
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        with self._lock:
            stats = {
                'algorithm': self.algorithm,
                'total_nodes': len(self.nodes),
                'active_nodes': sum(1 for n in self.nodes.values() if n.active),
                'nodes': []
            }
            
            for node in self.nodes.values():
                stats['nodes'].append({
                    'agent_id': node.agent_id,
                    'agent_type': node.agent_type,
                    'active': node.active,
                    'weight': node.weight,
                    'effective_weight': node.effective_weight,
                    'current_load': node.current_load,
                    'total_requests': node.total_requests,
                    'failed_requests': node.failed_requests,
                    'avg_response_time': node.avg_response_time,
                    'health_score': node.health_score
                })
            
            return stats
    
    def auto_recovery(self):
        """自动恢复 - 标记不健康节点"""
        with self._lock:
            for node in self.nodes.values():
                if node.health_score < 30:
                    node.active = False
                    print(f"⚠️ 节点 {node.agent_id} 健康分数过低 ({node.health_score}), 已禁用")
                elif node.health_score > 60 and not node.active:
                    node.active = True
                    print(f"✅ 节点 {node.agent_id} 恢复健康, 已启用")


class LoadBalancerAPI:
    """负载均衡API"""
    
    def __init__(self, lb: IntelligentLoadBalancer):
        self.lb = lb
        self._request_id = 0
        self._lock = threading.Lock()
    
    def route_request(self, agent_type: str = None) -> Dict:
        """路由请求"""
        with self._lock:
            self._request_id += 1
            request_id = self._request_id
        
        node = self.lb.select_node(agent_type)
        
        if not node:
            return {
                'request_id': request_id,
                'success': False,
                'error': 'No available nodes'
            }
        
        # 模拟请求处理
        node.current_load += 1
        
        # 返回路由信息
        return {
            'request_id': request_id,
            'success': True,
            'agent_id': node.agent_id,
            'agent_type': node.agent_type,
            'algorithm': self.lb.algorithm,
            'health_score': node.health_score
        }
    
    def complete_request(self, agent_id: str, response_time: float, success: bool = True):
        """完成请求"""
        with self._lock:
            if agent_id in self.lb.nodes:
                self.lb.nodes[agent_id].current_load = max(0, self.lb.nodes[agent_id].current_load - 1)
        
        self.lb.record_request(agent_id, response_time, success)


# 测试
if __name__ == '__main__':
    print("🔧 智能负载均衡器测试")
    print("="*50)
    
    lb = IntelligentLoadBalancer(algorithm='adaptive')
    api = LoadBalancerAPI(lb)
    
    # 注册测试节点
    lb.register_node('agent-001', 'executor', weight=10)
    lb.register_node('agent-002', 'executor', weight=8)
    lb.register_node('agent-003', 'analyzer', weight=5)
    lb.register_node('agent-004', 'coordinator', weight=7)
    
    print("\n📊 路由测试 (10个请求):")
    for i in range(10):
        result = api.route_request()
        if result['success']:
            print(f"  请求{i+1}: {result['agent_id']} (type: {result['agent_type']})")
            # 模拟完成请求
            api.complete_request(result['agent_id'], random.uniform(10, 100), True)
    
    print("\n📈 统计信息:")
    stats = lb.get_stats()
    print(json.dumps(stats, indent=2, default=str))
    
    print("\n✅ 负载均衡器测试完成")