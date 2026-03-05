#!/usr/bin/env python3
"""
Agent协作网络负载均衡与性能优化API
====================================
增强的负载均衡优化服务

端口: 18142

功能:
- 智能扩缩容建议
- 性能瓶颈分析
- 负载趋势预测
- 自动优化推荐
"""

import json
import time
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from collections import deque
from aiohttp import web
import requests

routes = web.RouteTableDef()

# 配置
LB_API = "http://localhost:8093"
PERF_API = "http://localhost:18141"


class OptimizationPriority(Enum):
    """优化优先级"""
    CRITICAL = "critical"      # 立即处理
    HIGH = "high"             # 24小时内
    MEDIUM = "medium"         # 本周
    LOW = "low"               # 计划中


@dataclass
class AgentStatus:
    """Agent状态"""
    agent_id: str
    current_load: int
    success_rate: float
    avg_execution_time: float
    weight: int
    consecutive_failures: int
    health: str


@dataclass
class OptimizationRecommendation:
    """优化建议"""
    priority: str
    category: str
    title: str
    description: str
    action: str
    expected_impact: str
    agents_affected: List[str]


class LoadBalancerOptimizer:
    """负载均衡优化器"""
    
    def __init__(self):
        self.history = deque(maxlen=100)  # 保留100条历史记录
        self.thresholds = {
            "max_load": 5,
            "min_success_rate": 70.0,
            "max_execution_time": 100.0,
            "max_failures": 3,
            "scale_up_threshold": 4,
            "scale_down_threshold": 1
        }
        self.lock = threading.RLock()
    
    async def fetch_lb_data(self) -> Dict:
        """获取负载均衡数据"""
        try:
            r = requests.get(f"{LB_API}/api/agents", timeout=5)
            return r.json()
        except:
            return {"agents": {}, "healthy_agents": 0, "strategy": "unknown"}
    
    async def fetch_perf_data(self) -> Dict:
        """获取性能数据"""
        try:
            r = requests.get(f"{PERF_API}/metrics", timeout=5)
            return r.json()
        except:
            return {}
    
    def analyze_agents(self, lb_data: Dict) -> List[AgentStatus]:
        """分析Agent状态"""
        agents = []
        for agent_id, data in lb_data.get("agents", {}).items():
            # 确定健康状态
            if data.get("success_rate", 100) < self.thresholds["min_success_rate"]:
                health = "unhealthy"
            elif data.get("consecutive_failures", 0) >= self.thresholds["max_failures"]:
                health = "degraded"
            elif data.get("current_load", 0) >= self.thresholds["max_load"]:
                health = "overloaded"
            else:
                health = "healthy"
            
            agents.append(AgentStatus(
                agent_id=agent_id,
                current_load=data.get("current_load", 0),
                success_rate=data.get("success_rate", 100),
                avg_execution_time=data.get("avg_execution_time", 0),
                weight=data.get("weight", 100),
                consecutive_failures=data.get("consecutive_failures", 0),
                health=health
            ))
        return agents
    
    def generate_recommendations(self, agents: List[AgentStatus], perf_data: Dict) -> List[OptimizationRecommendation]:
        """生成优化建议"""
        recommendations = []
        
        # 分析每个Agent
        overloaded = [a for a in agents if a.current_load >= self.thresholds["scale_up_threshold"]]
        underloaded = [a for a in agents if a.current_load <= self.thresholds["scale_down_threshold"] and a.current_load > 0]
        unhealthy = [a for a in agents if a.health in ["unhealthy", "degraded"]]
        slow = [a for a in agents if a.avg_execution_time > self.thresholds["max_execution_time"]]
        
        # 扩缩容建议
        if len(overloaded) >= len(agents) * 0.5 and len(agents) > 1:
            recommendations.append(OptimizationRecommendation(
                priority=OptimizationPriority.CRITICAL.value,
                category="scaling",
                title="系统过载 - 建议紧急扩容",
                description=f"当前 {len(overloaded)}/{len(agents)} Agent负载过高，需要立即扩容",
                action="horizontal_scale_up",
                expected_impact="提升整体处理能力",
                agents_affected=[a.agent_id for a in overloaded]
            ))
        
        if len(underloaded) >= len(agents) * 0.5 and len(agents) > 2:
            recommendations.append(OptimizationRecommendation(
                priority=OptimizationPriority.MEDIUM.value,
                category="scaling",
                title="资源浪费 - 建议缩减",
                description=f"当前 {len(underloaded)}/{len(agents)} Agent负载过低，可以缩减",
                action="horizontal_scale_down",
                expected_impact="降低成本",
                agents_affected=[a.agent_id for a in underloaded]
            ))
        
        # 健康问题建议
        for a in unhealthy:
            if a.consecutive_failures >= self.thresholds["max_failures"]:
                recommendations.append(OptimizationRecommendation(
                    priority=OptimizationPriority.HIGH.value,
                    category="health",
                    title=f"Agent {a.agent_id} 连续失败",
                    description=f"连续 {a.consecutive_failures} 次失败，成功率仅 {a.success_rate}%",
                    action="investigate_agent",
                    expected_impact="恢复服务稳定性",
                    agents_affected=[a.agent_id]
                ))
        
        # 性能优化建议
        for a in slow:
            recommendations.append(OptimizationRecommendation(
                priority=OptimizationPriority.MEDIUM.value,
                category="performance",
                title=f"Agent {a.agent_id} 执行缓慢",
                description=f"平均执行时间 {a.avg_execution_time:.1f}ms，超过阈值 {self.thresholds['max_execution_time']}ms",
                action="optimize_execution",
                expected_impact="提升响应速度",
                agents_affected=[a.agent_id]
            ))
        
        # 权重优化建议
        high_load_low_weight = [a for a in agents if a.current_load >= 3 and a.weight < 80]
        if high_load_low_weight:
            recommendations.append(OptimizationRecommendation(
                priority=OptimizationPriority.MEDIUM.value,
                category="load_balancing",
                title="权重分配不均",
                description="高负载Agent权重过低，导致负载不均",
                action="rebalance_weights",
                expected_impact="优化负载分布",
                agents_affected=[a.agent_id for a in high_load_low_weight]
            ))
        
        # 总体建议
        if not recommendations:
            recommendations.append(OptimizationRecommendation(
                priority=OptimizationPriority.LOW.value,
                category="monitoring",
                title="系统运行良好",
                description="所有Agent正常运行，无需干预",
                action="continue_monitoring",
                expected_impact="保持现状",
                agents_affected=[]
            ))
        
        return recommendations
    
    def analyze_trends(self, lb_data: Dict) -> Dict:
        """分析趋势"""
        agents = lb_data.get("agents", {})
        
        total_load = sum(a.get("current_load", 0) for a in agents.values())
        total_capacity = len(agents) * self.thresholds["max_load"]
        utilization = (total_load / total_capacity * 100) if total_capacity > 0 else 0
        
        avg_success = 0
        if agents:
            avg_success = sum(a.get("success_rate", 100) for a in agents.values()) / len(agents)
        
        trend = "stable"
        if utilization > 80:
            trend = "increasing"  # 负载上升
        elif utilization < 30:
            trend = "decreasing"  # 负载下降
        
        return {
            "total_load": total_load,
            "total_capacity": total_capacity,
            "utilization_percent": round(utilization, 1),
            "average_success_rate": round(avg_success, 1),
            "trend": trend,
            "status": "healthy" if utilization < 80 else "overloaded"
        }
    
    async def get_full_analysis(self) -> Dict:
        """获取完整分析"""
        lb_data = await self.fetch_lb_data()
        perf_data = await self.fetch_perf_data()
        
        agents = self.analyze_agents(lb_data)
        recommendations = self.generate_recommendations(agents, perf_data)
        trends = self.analyze_trends(lb_data)
        
        return {
            "timestamp": datetime.now().isoformat(),
            "agents": [asdict(a) for a in agents],
            "trends": trends,
            "recommendations": [asdict(r) for r in recommendations],
            "thresholds": self.thresholds
        }


# 全局优化器
_optimizer = LoadBalancerOptimizer()


# ========== API路由 ==========

@routes.get("/health")
async def health(request):
    return web.json_response({"status": "ok", "service": "lb-perf-optimizer"})


@routes.get("/api/analysis")
async def get_analysis(request):
    """获取完整分析"""
    result = await _optimizer.get_full_analysis()
    return web.json_response(result)


@routes.get("/api/recommendations")
async def get_recommendations(request):
    """获取优化建议"""
    lb_data = await _optimizer.fetch_lb_data()
    perf_data = await _optimizer.fetch_perf_data()
    agents = _optimizer.analyze_agents(lb_data)
    recommendations = _optimizer.generate_recommendations(agents, perf_data)
    return web.json_response({
        "recommendations": [asdict(r) for r in recommendations]
    })


@routes.get("/api/trends")
async def get_trends(request):
    """获取趋势分析"""
    lb_data = await _optimizer.fetch_lb_data()
    trends = _optimizer.analyze_trends(lb_data)
    return web.json_response(trends)


@routes.get("/api/thresholds")
async def get_thresholds(request):
    """获取阈值配置"""
    return web.json_response(_optimizer.thresholds)


@routes.post("/api/thresholds")
async def set_thresholds(request):
    """设置阈值"""
    data = await request.json()
    with _optimizer.lock:
        for key, value in data.items():
            if key in _optimizer.thresholds:
                _optimizer.thresholds[key] = value
    return web.json_response({"status": "updated", "thresholds": _optimizer.thresholds})


@routes.get("/api/agents/{agent_id}/optimize")
async def optimize_agent(request):
    """获取单个Agent优化建议"""
    agent_id = request.match_info["agent_id"]
    lb_data = await _optimizer.fetch_lb_data()
    
    agent_data = lb_data.get("agents", {}).get(agent_id)
    if not agent_data:
        return web.json_response({"error": "Agent not found"}), 404
    
    suggestions = []
    
    if agent_data.get("current_load", 0) >= _optimizer.thresholds["scale_up_threshold"]:
        suggestions.append({
            "type": "scaling",
            "action": "scale_up",
            "description": "负载过高，建议扩容或分散任务"
        })
    
    if agent_data.get("success_rate", 100) < _optimizer.thresholds["min_success_rate"]:
        suggestions.append({
            "type": "health",
            "action": "investigate",
            "description": "成功率过低，建议检查执行逻辑"
        })
    
    if agent_data.get("avg_execution_time", 0) > _optimizer.thresholds["max_execution_time"]:
        suggestions.append({
            "type": "performance",
            "action": "optimize",
            "description": "执行时间过长，建议优化代码"
        })
    
    return web.json_response({
        "agent_id": agent_id,
        "current_status": agent_data,
        "suggestions": suggestions
    })


async def background_monitor():
    """后台监控任务"""
    while True:
        await asyncio.sleep(60)
        try:
            analysis = await _optimizer.get_full_analysis()
            critical = [r for r in analysis.get("recommendations", []) 
                       if r.get("priority") == "critical"]
            if critical:
                print(f"[LB-OPTIMIZER] 发现 {len(critical)} 个严重问题需要关注")
        except Exception as e:
            print(f"[LB-OPTIMIZER] 监控错误: {e}")


def create_app():
    app = web.Application()
    app.add_routes(routes)
    return app


async def start_background(app):
    asyncio.create_task(background_monitor())


if __name__ == "__main__":
    app = create_app()
    app.on_startup.append(start_background)
    
    print("🚀 Agent协作网络负载均衡优化服务 - Port 18142")
    web.run_app(app, host="0.0.0.0", port=18142)