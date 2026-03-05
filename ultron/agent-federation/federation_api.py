#!/usr/bin/env python3
"""
Agent联邦学习与协同推理 API
端口: 18129
"""

import asyncio
import json
import time
import hashlib
from aiohttp import web
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 联邦学习状态
class FederationState:
    def __init__(self):
        self.agents = {}  # agent_id -> {capabilities, model_weights, last_update}
        self.tasks = {}   # task_id -> {type, status, participants, results}
        self.knowledge_base = {}  # 共享知识
        self.global_model = {}    # 全局模型
        self.fed_rounds = 0
        
    def register_agent(self, agent_id, capabilities):
        self.agents[agent_id] = {
            'capabilities': capabilities,
            'model_weights': {},
            'local_model': {},
            'last_update': time.time(),
            'contribution': 0,
            'accuracy': 0.0
        }
        logger.info(f"Agent {agent_id} 注册到联邦学习网络")
        
    def submit_local_update(self, agent_id, model_weights, metrics):
        if agent_id not in self.agents:
            return {'error': 'Agent not registered'}
        
        agent = self.agents[agent_id]
        agent['model_weights'] = model_weights
        agent['local_model'] = model_weights
        agent['last_update'] = time.time()
        agent['accuracy'] = metrics.get('accuracy', 0.0)
        agent['contribution'] += 1
        
        return {'status': 'accepted', 'round': self.fed_rounds}
    
    def aggregate_models(self, strategy='fedavg'):
        """联邦聚合"""
        if not self.agents:
            return {'error': 'No agents'}
        
        # FedAvg: 加权平均
        if strategy == 'fedavg':
            total_weight = sum(a['contribution'] for a in self.agents.values()) or 1
            aggregated = {}
            
            for agent_id, agent in self.agents.items():
                weight = agent['contribution'] / total_weight
                for key, value in agent['model_weights'].items():
                    # 简单的加权平均
                    if isinstance(value, (int, float)):
                        if key not in aggregated:
                            aggregated[key] = 0
                        aggregated[key] += value * weight
                    elif isinstance(value, list):
                        if key not in aggregated:
                            aggregated[key] = [0] * len(value)
                        for i, v in enumerate(value):
                            if isinstance(v, (int, float)):
                                aggregated[key][i] += v * weight
            
            self.global_model = aggregated
            self.fed_rounds += 1
            return {'status': 'aggregated', 'round': self.fed_rounds, 'agents': len(self.agents)}
        
        return {'error': 'Unknown strategy'}
    
    def collaborative_inference(self, task, max_agents=3):
        """协同推理 - 多个Agent共同推理"""
        task_id = hashlib.md5(f"{task}{time.time()}".encode()).hexdigest()[:8]
        
        # 选择最合适的Agent
        sorted_agents = sorted(
            self.agents.items(),
            key=lambda x: x[1]['accuracy'],
            reverse=True
        )[:max_agents]
        
        self.tasks[task_id] = {
            'type': 'inference',
            'task': task,
            'status': 'processing',
            'participants': [a[0] for a in sorted_agents],
            'results': [],
            'created': time.time()
        }
        
        return {'task_id': task_id, 'participants': [a[0] for a in sorted_agents]}
    
    def submit_inference_result(self, task_id, agent_id, result):
        if task_id not in self.tasks:
            return {'error': 'Task not found'}
        
        task = self.tasks[task_id]
        task['results'].append({
            'agent_id': agent_id,
            'result': result,
            'timestamp': time.time()
        })
        
        # 所有参与Agent都提交了
        if len(task['results']) >= len(task['participants']):
            task['status'] = 'completed'
            # 融合结果
            task['final_result'] = self._fuse_results(task['results'])
        
        return {'status': 'accepted'}
    
    def _fuse_results(self, results):
        """结果融合 - 简单投票或平均"""
        if not results:
            return {}
        
        # 取最高置信度的结果
        best = max(results, key=lambda x: x.get('confidence', 0.5))
        return best.get('result', {})

    def share_knowledge(self, agent_id, knowledge_key, knowledge_value):
        """知识共享"""
        self.knowledge_base[knowledge_key] = {
            'value': knowledge_value,
            'contributor': agent_id,
            'timestamp': time.time()
        }
        return {'status': 'shared', 'key': knowledge_key}
    
    def get_knowledge(self, knowledge_key):
        return self.knowledge_base.get(knowledge_key, {})

federation = FederationState()

# 路由
async def register(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    capabilities = data.get('capabilities', [])
    
    federation.register_agent(agent_id, capabilities)
    return web.json_response({'status': 'registered', 'agent_id': agent_id})

async def submit_update(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    model_weights = data.get('model_weights', {})
    metrics = data.get('metrics', {})
    
    result = federation.submit_local_update(agent_id, model_weights, metrics)
    return web.json_response(result)

async def aggregate(request):
    data = await request.json()
    strategy = data.get('strategy', 'fedavg')
    
    result = federation.aggregate_models(strategy)
    return web.json_response(result)

async def inference(request):
    data = await request.json()
    task = data.get('task')
    max_agents = data.get('max_agents', 3)
    
    result = federation.collaborative_inference(task, max_agents)
    return web.json_response(result)

async def submit_inference(request):
    data = await request.json()
    task_id = data.get('task_id')
    agent_id = data.get('agent_id')
    result = data.get('result')
    
    response = federation.submit_inference_result(task_id, agent_id, result)
    return web.json_response(response)

async def share_knowledge(request):
    data = await request.json()
    agent_id = data.get('agent_id')
    knowledge_key = data.get('key')
    knowledge_value = data.get('value')
    
    result = federation.share_knowledge(agent_id, knowledge_key, knowledge_value)
    return web.json_response(result)

async def get_knowledge(request):
    key = request.query.get('key')
    result = federation.get_knowledge(key)
    return web.json_response(result)

async def status(request):
    return web.json_response({
        'agents': len(federation.agents),
        'rounds': federation.fed_rounds,
        'tasks': len(federation.tasks),
        'knowledge_entries': len(federation.knowledge_base),
        'agent_details': {
            aid: {
                'capabilities': a['capabilities'],
                'accuracy': a['accuracy'],
                'contribution': a['contribution'],
                'last_update': a['last_update']
            }
            for aid, a in federation.agents.items()
        }
    })

async def health(request):
    return web.json_response({'status': 'ok', 'service': 'federation', 'port': 18129})

app = web.Application()
app.router.add_post('/register', register)
app.router.add_post('/submit_update', submit_update)
app.router.add_post('/aggregate', aggregate)
app.router.add_post('/inference', inference)
app.router.add_post('/submit_inference', submit_inference)
app.router.add_post('/share_knowledge', share_knowledge)
app.router.add_get('/get_knowledge', get_knowledge)
app.router.add_get('/status', status)
app.router.add_get('/health', health)

if __name__ == '__main__':
    logger.info("联邦学习API启动在端口 18129")
    web.run_app(app, host='0.0.0.0', port=18129)