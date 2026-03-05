#!/usr/bin/env python3
"""
多Agent协作增强API
第64世: 协作框架完善 - 添加增强功能

增强功能:
- 协作组管理 (Agent Groups)
- 智能任务分发 (Smart Task Distribution)
- 协作指标收集 (Collaboration Metrics)
- 跨组协作 (Cross-Group Collaboration)
"""

import asyncio
import json
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from flask import Flask, jsonify, request
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("collab-enhanced-api")

app = Flask(__name__)


@dataclass
class AgentGroup:
    """Agent组"""
    group_id: str
    name: str
    description: str
    agent_ids: List[str] = field(default_factory=list)
    capabilities: List[str] = field(default_factory=list)
    load_strategy: str = "balanced"  # balanced, fastest, priority
    created_at: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)


@dataclass
class CollaborationMetrics:
    """协作指标"""
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    avg_response_time: float = 0.0
    group_collaborations: int = 0
    cross_group_tasks: int = 0
    task_distribution: Dict[str, int] = field(default_factory=dict)


@dataclass
class CrossGroupTask:
    """跨组任务"""
    task_id: str
    source_group: str
    target_groups: List[str]
    task_type: str
    payload: Dict
    status: str = "pending"
    results: Dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class CollaborationEnhancer:
    """协作增强器"""
    
    def __init__(self):
        self.groups: Dict[str, AgentGroup] = {}
        self.metrics = CollaborationMetrics()
        self.cross_group_tasks: Dict[str, CrossGroupTask] = {}
        self.task_history: List[Dict] = []
        
        # 初始化默认组
        self._init_default_groups()
    
    def _init_default_groups(self):
        """初始化默认组"""
        default_groups = [
            AgentGroup(
                group_id="monitor-group",
                name="监控组",
                description="负责系统监控和数据收集",
                capabilities=["monitor", "collect", "alert"]
            ),
            AgentGroup(
                group_id="execution-group",
                name="执行组",
                description="负责任务执行和操作",
                capabilities=["execute", "deploy", "repair"]
            ),
            AgentGroup(
                group_id="analysis-group",
                name="分析组",
                description="负责数据分析和决策",
                capabilities=["analyze", "predict", "optimize"]
            )
        ]
        for group in default_groups:
            self.groups[group.group_id] = group
        logger.info(f"初始化了 {len(default_groups)} 个默认组")
    
    def create_group(self, name: str, description: str, 
                     capabilities: List[str], load_strategy: str = "balanced") -> AgentGroup:
        """创建Agent组"""
        group_id = f"group_{uuid.uuid4().hex[:8]}"
        group = AgentGroup(
            group_id=group_id,
            name=name,
            description=description,
            capabilities=capabilities,
            load_strategy=load_strategy
        )
        self.groups[group_id] = group
        logger.info(f"创建组: {name} ({group_id})")
        return group
    
    def add_agent_to_group(self, group_id: str, agent_id: str) -> bool:
        """添加Agent到组"""
        if group_id not in self.groups:
            return False
        group = self.groups[group_id]
        if agent_id not in group.agent_ids:
            group.agent_ids.append(agent_id)
        return True
    
    def remove_agent_from_group(self, group_id: str, agent_id: str) -> bool:
        """从组移除Agent"""
        if group_id not in self.groups:
            return False
        group = self.groups[group_id]
        if agent_id in group.agent_ids:
            group.agent_ids.remove(agent_id)
        return True
    
    def get_group_status(self, group_id: str) -> Optional[Dict]:
        """获取组状态"""
        if group_id not in self.groups:
            return None
        group = self.groups[group_id]
        return {
            "group_id": group.group_id,
            "name": group.name,
            "description": group.description,
            "agent_count": len(group.agent_ids),
            "agent_ids": group.agent_ids,
            "capabilities": group.capabilities,
            "load_strategy": group.load_strategy,
            "created_at": group.created_at
        }
    
    def list_groups(self) -> List[Dict]:
        """列出所有组"""
        return [self.get_group_status(g.group_id) for g in self.groups.values()]
    
    def execute_cross_group_task(self, source_group: str, target_groups: List[str],
                                  task_type: str, payload: Dict) -> str:
        """执行跨组任务"""
        task_id = f"cross_task_{uuid.uuid4().hex[:12]}"
        task = CrossGroupTask(
            task_id=task_id,
            source_group=source_group,
            target_groups=target_groups,
            task_type=task_type,
            payload=payload
        )
        self.cross_group_tasks[task_id] = task
        self.metrics.cross_group_tasks += 1
        self.metrics.group_collaborations += 1
        
        # 模拟任务执行
        task.status = "completed"
        task.results = {
            "status": "success",
            "executed_by": target_groups,
            "task_type": task_type
        }
        
        logger.info(f"跨组任务完成: {task_id}, 从 {source_group} 到 {target_groups}")
        return task_id
    
    def get_metrics(self) -> Dict:
        """获取协作指标"""
        return {
            "total_tasks": self.metrics.total_tasks,
            "successful_tasks": self.metrics.successful_tasks,
            "failed_tasks": self.metrics.failed_tasks,
            "avg_response_time": self.metrics.avg_response_time,
            "group_collaborations": self.metrics.group_collaborations,
            "cross_group_tasks": self.metrics.cross_group_tasks,
            "task_distribution": self.metrics.task_distribution,
            "active_groups": len(self.groups),
            "timestamp": time.time()
        }
    
    def distribute_task(self, task_type: str, payload: Dict, 
                        preferred_groups: List[str] = None) -> Dict:
        """智能任务分发"""
        self.metrics.total_tasks += 1
        
        # 选择最佳组
        target_group = None
        if preferred_groups:
            for g in preferred_groups:
                if g in self.groups:
                    target_group = self.groups[g]
                    break
        
        if not target_group:
            # 使用负载均衡策略选择
            target_group = self._select_best_group(task_type)
        
        if target_group:
            self.metrics.task_distribution[target_group.name] = \
                self.metrics.task_distribution.get(target_group.name, 0) + 1
            self.metrics.successful_tasks += 1
            
            return {
                "task_id": f"task_{uuid.uuid4().hex[:12]}",
                "status": "distributed",
                "assigned_group": target_group.name,
                "group_id": target_group.group_id,
                "task_type": task_type
            }
        else:
            self.metrics.failed_tasks += 1
            return {
                "task_id": None,
                "status": "failed",
                "reason": "no available group"
            }
    
    def _select_best_group(self, task_type: str) -> Optional[AgentGroup]:
        """根据任务类型选择最佳组"""
        task_capability_map = {
            "monitor": "monitor-group",
            "execute": "execution-group", 
            "analyze": "analysis-group",
            "deploy": "execution-group",
            "repair": "execution-group",
            "alert": "monitor-group",
            "predict": "analysis-group"
        }
        
        group_id = task_capability_map.get(task_type)
        if group_id and group_id in self.groups:
            return self.groups[group_id]
        
        # 返回负载最低的组
        return min(self.groups.values(), key=lambda g: len(g.agent_ids)) if self.groups else None


# 全局实例
enhancer = CollaborationEnhancer()


# API 端点
@app.route('/health', methods=['GET'])
def health():
    return jsonify({"healthy": True, "service": "collab-enhanced-api"})


@app.route('/groups', methods=['GET'])
def list_groups():
    return jsonify({"groups": enhancer.list_groups(), "count": len(enhancer.groups)})


@app.route('/groups', methods=['POST'])
def create_group():
    data = request.json
    group = enhancer.create_group(
        name=data.get('name'),
        description=data.get('description', ''),
        capabilities=data.get('capabilities', []),
        load_strategy=data.get('load_strategy', 'balanced')
    )
    return jsonify({"group_id": group.group_id, "status": "created"})


@app.route('/groups/<group_id>', methods=['GET'])
def get_group(group_id):
    status = enhancer.get_group_status(group_id)
    if status:
        return jsonify(status)
    return jsonify({"error": "group not found"}), 404


@app.route('/groups/<group_id>/agents', methods=['POST'])
def add_agent(group_id):
    data = request.json
    agent_id = data.get('agent_id')
    if enhancer.add_agent_to_group(group_id, agent_id):
        return jsonify({"status": "added", "agent_id": agent_id})
    return jsonify({"error": "group not found"}), 404


@app.route('/groups/<group_id>/agents/<agent_id>', methods=['DELETE'])
def remove_agent(group_id, agent_id):
    if enhancer.remove_agent_from_group(group_id, agent_id):
        return jsonify({"status": "removed"})
    return jsonify({"error": "group not found"}), 404


@app.route('/cross-group', methods=['POST'])
def cross_group_task():
    data = request.json
    task_id = enhancer.execute_cross_group_task(
        source_group=data.get('source_group'),
        target_groups=data.get('target_groups', []),
        task_type=data.get('task_type'),
        payload=data.get('payload', {})
    )
    return jsonify({"task_id": task_id, "status": "executed"})


@app.route('/distribute', methods=['POST'])
def distribute_task():
    data = request.json
    result = enhancer.distribute_task(
        task_type=data.get('task_type'),
        payload=data.get('payload', {}),
        preferred_groups=data.get('preferred_groups')
    )
    return jsonify(result)


@app.route('/metrics', methods=['GET'])
def metrics():
    return jsonify(enhancer.get_metrics())


if __name__ == '__main__':
    logger.info("启动协作增强API服务 (端口 18127)")
    app.run(host='0.0.0.0', port=18127, debug=False)