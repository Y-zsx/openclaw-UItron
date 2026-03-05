#!/usr/bin/env python3
"""
 swarm-behavior.py - 群体行为引擎
 夙愿二十六第2世：涌现智能
 功能：模拟智能体群体行为、协调运动、信息传递
"""

import asyncio
import random
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Set
from enum import Enum
import json
from collections import defaultdict
import time


class BehaviorType(Enum):
    """行为类型"""
    COHESION = "cohesion"          # 凝聚：向群体中心移动
    ALIGNMENT = "alignment"        # 对齐：模仿邻居方向
    SEPARATION = "separation"      # 分离：避免碰撞
    EXPLORATION = "exploration"    # 探索：随机搜索
    FOLLOW_LEADER = "follow_leader" # 跟随：跟随领导者
    FLOCKING = "flocking"          # 群集：综合行为
    HUNTING = "hunting"            # 狩猎：包围目标
    ESCAPE = "escape"              # 逃跑：逃离威胁
    MIGRATION = "migration"        # 迁移：群体移动
    COOPERATIVE = "cooperative"    # 协作：完成共同目标


@dataclass
class Vector2D:
    """二维向量"""
    x: float = 0.0
    y: float = 0.0
    
    def __add__(self, other: 'Vector2D') -> 'Vector2D':
        return Vector2D(self.x + other.x, self.y + other.y)
    
    def __sub__(self, other: 'Vector2D') -> 'Vector2D':
        return Vector2D(self.x - other.x, self.y - other.y)
    
    def __mul__(self, scalar: float) -> 'Vector2D':
        return Vector2D(self.x * scalar, self.y * scalar)
    
    def __truediv__(self, scalar: float) -> 'Vector2D':
        return Vector2D(self.x / scalar, self.y / scalar) if scalar != 0 else Vector2D()
    
    def magnitude(self) -> float:
        return math.sqrt(self.x ** 2 + self.y ** 2)
    
    def normalize(self) -> 'Vector2D':
        mag = self.magnitude()
        return self / mag if mag > 0 else Vector2D()
    
    def dot(self, other: 'Vector2D') -> float:
        return self.x * other.x + self.y * other.y
    
    def distance_to(self, other: 'Vector2D') -> float:
        return (self - other).magnitude()
    
    def angle_to(self, other: 'Vector2D') -> float:
        if self.magnitude() == 0 or other.magnitude() == 0:
            return 0.0
        cos_angle = self.normalize().dot(other.normalize())
        return math.acos(max(-1, min(1, cos_angle)))


@dataclass
class Agent:
    """智能体"""
    id: str
    position: Vector2D
    velocity: Vector2D = field(default_factory=Vector2D)
    acceleration: Vector2D = field(default_factory=Vector2D)
    max_speed: float = 2.0
    max_force: float = 0.1
    neighbors: List['Agent'] = field(default_factory=list)
    role: str = "worker"
    energy: float = 100.0
    health: float = 100.0
    state: Dict = field(default_factory=dict)
    
    @property
    def heading(self) -> Vector2D:
        return self.velocity.normalize() if self.velocity.magnitude() > 0 else Vector2D()


@dataclass
class SwarmConfig:
    """群体配置"""
    cohesion_weight: float = 1.0
    alignment_weight: float = 1.0
    separation_weight: float = 1.5
    exploration_weight: float = 0.5
    perception_radius: float = 50.0
    separation_radius: float = 25.0
    max_neighbors: int = 20
    enable_async: bool = True


class BoidBehavior:
    """Boid算法实现（凝聚、对齐、分离）"""
    
    def __init__(self, config: SwarmConfig):
        self.config = config
    
    def cohesion(self, agent: Agent, neighbors: List[Agent]) -> Vector2D:
        """凝聚行为：向邻居中心移动"""
        if not neighbors:
            return Vector2D()
        
        center = Vector2D()
        for n in neighbors:
            center = center + n.position
        center = center / len(neighbors)
        
        desired = center - agent.position
        desired = desired.normalize() * agent.max_speed
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force)
        
        return steering * self.config.cohesion_weight
    
    def alignment(self, agent: Agent, neighbors: List[Agent]) -> Vector2D:
        """对齐行为：匹配邻居速度方向"""
        if not neighbors:
            return Vector2D()
        
        avg_velocity = Vector2D()
        for n in neighbors:
            avg_velocity = avg_velocity + n.velocity
        avg_velocity = avg_velocity / len(neighbors)
        
        desired = avg_velocity.normalize() * agent.max_speed
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force)
        
        return steering * self.config.alignment_weight
    
    def separation(self, agent: Agent, neighbors: List[Agent]) -> Vector2D:
        """分离行为：避免与邻居碰撞"""
        if not neighbors:
            return Vector2D()
        
        steer = Vector2D()
        count = 0
        
        for n in neighbors:
            dist = agent.position.distance_to(n.position)
            if 0 < dist < self.config.separation_radius:
                diff = agent.position - n.position
                diff = diff.normalize() / dist  # 距离越近，排斥越强
                steer = steer + diff
                count += 1
        
        if count > 0:
            steer = steer / count
            if steer.magnitude() > 0:
                steer = steer.normalize() * agent.max_speed
                steering = self._limit(steer - agent.velocity, agent.max_force)
                return steering * self.config.separation_weight
        
        return Vector2D()
    
    def _limit(self, vector: Vector2D, max_mag: float) -> Vector2D:
        mag = vector.magnitude()
        if mag > max_mag:
            return vector.normalize() * max_mag
        return vector


class FlockingSystem:
    """群集系统"""
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.config = config or SwarmConfig()
        self.agents: Dict[str, Agent] = {}
        self.boid = BoidBehavior(self.config)
        self.spatial_grid: Dict[Tuple[int, int], Set[str]] = defaultdict(set)
        self.cell_size = self.config.perception_radius
    
    def add_agent(self, agent: Agent) -> None:
        self.agents[agent.id] = agent
        self._update_spatial_grid(agent)
    
    def remove_agent(self, agent_id: str) -> None:
        if agent_id in self.agents:
            agent = self.agents[agent_id]
            cell = self._get_cell(agent.position)
            self.spatial_grid[cell].discard(agent_id)
            del self.agents[agent_id]
    
    def _get_cell(self, pos: Vector2D) -> Tuple[int, int]:
        return (int(pos.x / self.cell_size), int(pos.y / self.cell_size))
    
    def _update_spatial_grid(self, agent: Agent) -> None:
        cell = self._get_cell(agent.position)
        self.spatial_grid[cell].add(agent.id)
    
    def get_neighbors(self, agent: Agent, radius: Optional[float] = None) -> List[Agent]:
        radius = radius or self.config.perception_radius
        neighbors = []
        cell_radius = int(radius / self.cell_size) + 1
        
        agent_cell = self._get_cell(agent.position)
        
        for dx in range(-cell_radius, cell_radius + 1):
            for dy in range(-cell_radius, cell_radius + 1):
                cell = (agent_cell[0] + dx, agent_cell[1] + dy)
                for neighbor_id in self.spatial_grid.get(cell, []):
                    if neighbor_id != agent.id:
                        neighbor = self.agents.get(neighbor_id)
                        if neighbor:
                            dist = agent.position.distance_to(neighbor.position)
                            if dist <= radius:
                                neighbors.append(neighbor)
        
        return neighbors[:self.config.max_neighbors]
    
    def apply_flocking(self, agent: Agent) -> Vector2D:
        neighbors = self.get_neighbors(agent)
        agent.neighbors = neighbors
        
        if not neighbors:
            return self._exploration(agent)
        
        cohesion = self.boid.cohesion(agent, neighbors)
        alignment = self.boid.alignment(agent, neighbors)
        separation = self.boid.separation(agent, neighbors)
        
        return cohesion + alignment + separation
    
    def _exploration(self, agent: Agent) -> Vector2D:
        """探索行为：随机方向"""
        angle = random.uniform(0, 2 * math.pi)
        desired = Vector2D(math.cos(angle), math.sin(angle)) * agent.max_speed
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force)
        return steering * self.config.exploration_weight
    
    def _limit(self, vector: Vector2D, max_mag: float) -> Vector2D:
        mag = vector.magnitude()
        if mag > max_mag:
            return vector.normalize() * max_mag
        return vector


class BehaviorTree:
    """行为树实现"""
    
    def __init__(self):
        self.root: Optional[Node] = None
    
    class Node:
        def __init__(self, node_type: str):
            self.node_type = node_type
            self.children: List['BehaviorTree.Node'] = []
        
        def execute(self, agent: Agent, context: Dict) -> bool:
            return False
    
    class Selector(Node):
        """选择器：返回第一个成功的子节点"""
        def execute(self, agent: Agent, context: Dict) -> bool:
            for child in self.children:
                if child.execute(agent, context):
                    return True
            return False
    
    class Sequence(Node):
        """序列：所有子节点都成功才成功"""
        def execute(self, agent: Agent, context: Dict) -> bool:
            for child in self.children:
                if not child.execute(agent, context):
                    return False
            return True
    
    class Action(Node):
        def __init__(self, action_fn):
            super().__init__("action")
            self.action_fn = action_fn
        
        def execute(self, agent: Agent, context: Dict) -> bool:
            return self.action_fn(agent, context)
    
    class Condition(Node):
        def __init__(self, condition_fn):
            super().__init__("condition")
            self.condition_fn = condition_fn
        
        def execute(self, agent: Agent, context: Dict) -> bool:
            return self.condition_fn(agent, context)


class SwarmController:
    """群体控制器"""
    
    def __init__(self):
        self.flocking = FlockingSystem()
        self.behavior_tree = BehaviorTree()
        self.target: Optional[Vector2D] = None
        self.threat: Optional[Vector2D] = None
        self.leader_id: Optional[str] = None
        self.behavior_enabled: Dict[BehaviorType, bool] = {
            BehaviorType.FLOCKING: True,
            BehaviorType.HUNTING: False,
            BehaviorType.ESCAPE: False,
            BehaviorType.MIGRATION: False,
        }
    
    def set_target(self, position: Vector2D) -> None:
        self.target = position
    
    def set_threat(self, position: Vector2D) -> None:
        self.threat = position
    
    def set_leader(self, agent_id: str) -> None:
        self.leader_id = agent_id
    
    def compute_behavior(self, agent: Agent) -> Vector2D:
        result = Vector2D()
        
        if self.behavior_enabled.get(BehaviorType.ESCAPE) and self.threat:
            escape_force = self._compute_escape(agent)
            result = result + escape_force * 2.0
        
        if self.behavior_enabled.get(BehaviorType.FLOCKING):
            flocking_force = self.flocking.apply_flocking(agent)
            result = result + flocking_force
        
        if self.behavior_enabled.get(BehaviorType.MIGRATION) and self.target:
            migration_force = self._compute_migration(agent)
            result = result + migration_force
        
        if self.behavior_enabled.get(BehaviorType.HUNTING) and self.target:
            hunting_force = self._compute_hunting(agent)
            result = result + hunting_force
        
        if self.leader_id and agent.id != self.leader_id:
            leader = self.flocking.agents.get(self.leader_id)
            if leader:
                follow_force = self._compute_follow(agent, leader)
                result = result + follow_force
        
        return result
    
    def _compute_escape(self, agent: Agent) -> Vector2D:
        if not self.threat:
            return Vector2D()
        
        direction = agent.position - self.threat
        distance = direction.magnitude()
        
        if distance < 1:
            direction = Vector2D(random.uniform(-1, 1), random.uniform(-1, 1))
        
        desired = direction.normalize() * agent.max_speed * 2
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force * 3)
        
        return steering
    
    def _compute_migration(self, agent: Agent) -> Vector2D:
        if not self.target:
            return Vector2D()
        
        direction = self.target - agent.position
        distance = direction.magnitude()
        
        desired = direction.normalize() * agent.max_speed
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force)
        
        arrival = 1.0 if distance < 50 else 0.0
        if arrival > 0:
            desired = Vector2D()
            steering = desired - agent.velocity
        
        return steering
    
    def _compute_hunting(self, agent: Agent) -> Vector2D:
        if not self.target:
            return Vector2D()
        
        direction = self.target - agent.position
        distance = direction.magnitude()
        
        desired = direction.normalize() * agent.max_speed * 1.5
        steering = desired - agent.velocity
        steering = self._limit(steering, agent.max_force * 2)
        
        if distance < 10:
            return steering * 0.1
        
        return steering
    
    def _compute_follow(self, agent: Agent, leader: Agent) -> Vector2D:
        direction = leader.position - agent.position
        distance = direction.magnitude()
        
        if distance > 100:
            desired = direction.normalize() * agent.max_speed
            steering = desired - agent.velocity
            steering = self._limit(steering, agent.max_force)
            return steering
        
        return Vector2D()
    
    def _limit(self, vector: Vector2D, max_mag: float) -> Vector2D:
        mag = vector.magnitude()
        if mag > max_mag:
            return vector.normalize() * max_mag
        return vector


class EmergentPattern:
    """涌现模式检测"""
    
    def __init__(self):
        self.patterns: Dict[str, List[str]] = {
            "flock": [],
            "line": [],
            "v_shape": [],
            "circle": [],
            "cluster": [],
        }
    
    def detect_pattern(self, agents: List[Agent]) -> Dict[str, float]:
        if len(agents) < 3:
            return {}
        
        positions = [a.position for a in agents]
        
        # 计算群体紧密度
        cohesion_score = self._calculate_cohesion(positions)
        
        # 计算对齐度
        alignment_score = self._calculate_alignment(agents)
        
        # 检测是否形成特定模式
        pattern_scores = {
            "flock": cohesion_score * alignment_score,
            "line": self._detect_line(positions),
            "v_shape": self._detect_v_shape(positions),
            "circle": self._detect_circle(positions),
            "cluster": self._detect_cluster(positions),
        }
        
        return pattern_scores
    
    def _calculate_cohesion(self, positions: List[Vector2D]) -> float:
        if not positions:
            return 0.0
        
        center = sum(p.x for p in positions) / len(positions), sum(p.y for p in positions) / len(positions)
        avg_distance = sum(math.sqrt((p.x - center[0])**2 + (p.y - center[1])**2) for p in positions) / len(positions)
        
        return max(0, 1 - avg_distance / 200)
    
    def _calculate_alignment(self, agents: List[Agent]) -> float:
        if len(agents) < 2:
            return 0.0
        
        velocities = [a.velocity for a in agents if a.velocity.magnitude() > 0]
        if not velocities:
            return 0.0
        
        avg_direction = sum((v.x for v in velocities), 0) / len(velocities), sum((v.y for v in velocities), 0) / len(velocities)
        mag = math.sqrt(avg_direction[0]**2 + avg_direction[1]**2)
        
        return min(1.0, mag / (sum(v.magnitude() for v in velocities) / len(velocities)))
    
    def _detect_line(self, positions: List[Vector2D]) -> float:
        if len(positions) < 3:
            return 0.0
        
        # 简化的线形检测
        xs = [p.x for p in positions]
        ys = [p.y for p in positions]
        
        x_std = math.sqrt(sum((x - sum(xs)/len(xs))**2 for x in xs) / len(xs))
        y_std = math.sqrt(sum((y - sum(ys)/len(ys))**2 for y in ys) / len(ys))
        
        if x_std < y_std:
            return min(1.0, y_std / (x_std + 1))
        else:
            return min(1.0, x_std / (y_std + 1))
    
    def _detect_v_shape(self, positions: List[Vector2D]) -> float:
        return 0.0
    
    def _detect_circle(self, positions: List[Vector2D]) -> float:
        if len(positions) < 4:
            return 0.0
        
        center = Vector2D(sum(p.x for p in positions) / len(positions),
                         sum(p.y for p in positions) / len(positions))
        
        distances = [center.distance_to(p) for p in positions]
        avg_dist = sum(distances) / len(distances)
        
        if avg_dist < 1:
            return 0.0
        
        variance = sum((d - avg_dist)**2 for d in distances) / len(distances)
        
        return max(0, 1 - variance / (avg_dist ** 2 + 1))
    
    def _detect_cluster(self, positions: List[Vector2D]) -> float:
        return self._calculate_cohesion(positions)


class SwarmSimulation:
    """群体模拟器"""
    
    def __init__(self, config: Optional[SwarmConfig] = None):
        self.controller = SwarmController()
        self.config = config or SwarmConfig()
        self.agents: Dict[str, Agent] = {}
        self.pattern_detector = EmergentPattern()
        self.history: List[Dict] = []
        self.running = False
    
    def add_agent(self, agent: Agent) -> None:
        self.agents[agent.id] = agent
        self.controller.flocking.add_agent(agent)
    
    def remove_agent(self, agent_id: str) -> None:
        if agent_id in self.agents:
            self.controller.flocking.remove_agent(agent_id)
            del self.agents[agent_id]
    
    async def update(self, dt: float = 1.0) -> Dict:
        updates = []
        patterns = []
        
        for agent in list(self.agents.values()):
            behavior = self.controller.compute_behavior(agent)
            agent.acceleration = agent.acceleration + behavior
            
            agent.velocity = agent.velocity + agent.acceleration
            speed = agent.velocity.magnitude()
            if speed > agent.max_speed:
                agent.velocity = agent.velocity.normalize() * agent.max_speed
            
            agent.position = agent.position + agent.velocity
            agent.acceleration = Vector2D()
            
            self.controller.flocking._update_spatial_grid(agent)
            
            updates.append({
                "id": agent.id,
                "position": (agent.position.x, agent.position.y),
                "velocity": (agent.velocity.x, agent.velocity.y),
            })
        
        # 检测涌现模式
        if len(self.agents) >= 3:
            patterns = self.pattern_detector.detect_pattern(list(self.agents.values()))
        
        state = {
            "timestamp": time.time(),
            "agent_count": len(self.agents),
            "updates": updates,
            "patterns": patterns,
        }
        
        self.history.append(state)
        
        return state
    
    def get_statistics(self) -> Dict:
        if not self.agents:
            return {}
        
        positions = [a.position for a in self.agents.values()]
        velocities = [a.velocity for a in self.agents.values()]
        
        center = Vector2D(sum(p.x for p in positions) / len(positions),
                         sum(p.y for p in positions) / len(positions))
        
        return {
            "agent_count": len(self.agents),
            "center": (center.x, center.y),
            "avg_speed": sum(v.magnitude() for v in velocities) / len(velocities),
            "total_energy": sum(a.energy for a in self.agents.values()),
            "avg_health": sum(a.health for a in self.agents.values()) / len(self.agents),
        }


class TaskAllocation:
    """任务分配系统"""
    
    def __init__(self):
        self.tasks: Dict[str, Dict] = {}
        self.assignments: Dict[str, str] = {}  # task_id -> agent_id
        self.task_counter = 0
    
    def create_task(self, task_type: str, priority: int = 5, requirements: Optional[Dict] = None) -> str:
        task_id = f"task_{self.task_counter}"
        self.task_counter += 1
        
        self.tasks[task_id] = {
            "type": task_type,
            "priority": priority,
            "requirements": requirements or {},
            "status": "pending",
            "assigned_to": None,
        }
        
        return task_id
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        if task_id not in self.tasks:
            return False
        
        self.tasks[task_id]["assigned_to"] = agent_id
        self.tasks[task_id]["status"] = "assigned"
        self.assignments[task_id] = agent_id
        
        return True
    
    def get_available_tasks(self, agent_id: str) -> List[Dict]:
        available = []
        for task_id, task in self.tasks.items():
            if task["assigned_to"] is None and task["status"] == "pending":
                available.append({**task, "id": task_id})
        
        available.sort(key=lambda t: t["priority"], reverse=True)
        return available
    
    def complete_task(self, task_id: str) -> bool:
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = "completed"
            if task_id in self.assignments:
                del self.assignments[task_id]
            return True
        return False


class SwarmIntelligence:
    """群体智能系统 - 主入口"""
    
    def __init__(self):
        self.simulation = SwarmSimulation()
        self.task_allocation = TaskAllocation()
        self.behavior_controller = self.simulation.controller
        self.emergence_detector = EmergentPattern()
    
    def create_agent(self, agent_id: str, x: float, y: float, role: str = "worker") -> Agent:
        angle = random.uniform(0, 2 * math.pi)
        velocity = Vector2D(math.cos(angle), math.sin(angle)) * random.uniform(0.5, 1.5)
        
        agent = Agent(
            id=agent_id,
            position=Vector2D(x, y),
            velocity=velocity,
            role=role,
            energy=random.uniform(80, 100),
            health=random.uniform(90, 100),
        )
        
        self.simulation.add_agent(agent)
        return agent
    
    def set_swarm_target(self, x: float, y: float) -> None:
        self.behavior_controller.set_target(Vector2D(x, y))
        self.behavior_controller.behavior_enabled[BehaviorType.MIGRATION] = True
    
    def set_swarm_threat(self, x: float, y: float) -> None:
        self.behavior_controller.set_threat(Vector2D(x, y))
        self.behavior_controller.behavior_enabled[BehaviorType.ESCAPE] = True
    
    def enable_hunting(self) -> None:
        self.behavior_controller.behavior_enabled[BehaviorType.HUNTING] = True
    
    def disable_hunting(self) -> None:
        self.behavior_controller.behavior_enabled[BehaviorType.HUNTING] = False
    
    async def update(self, dt: float = 1.0) -> Dict:
        return await self.simulation.update(dt)
    
    def get_swarm_state(self) -> Dict:
        stats = self.simulation.get_statistics()
        patterns = self.emergence_detector.detect_pattern(list(self.simulation.agents.values()))
        
        return {
            "statistics": stats,
            "patterns": patterns,
            "tasks": {
                "total": len(self.task_allocation.tasks),
                "pending": sum(1 for t in self.task_allocation.tasks.values() if t["status"] == "pending"),
                "assigned": len(self.task_allocation.assignments),
                "completed": sum(1 for t in self.task_allocation.tasks.values() if t["status"] == "completed"),
            },
        }


# 主函数
async def main():
    print("=== 群体行为引擎测试 ===")
    
    swarm = SwarmIntelligence()
    
    # 创建50个智能体
    for i in range(50):
        x = random.uniform(0, 500)
        y = random.uniform(0, 500)
        role = "leader" if i == 0 else "worker"
        swarm.create_agent(f"agent_{i}", x, y, role)
    
    print(f"创建了 {len(swarm.simulation.agents)} 个智能体")
    
    # 设置目标
    swarm.set_swarm_target(400, 400)
    
    # 模拟100步
    for step in range(100):
        state = await swarm.update()
        
        if step % 20 == 0:
            stats = state.get("statistics", {})
            patterns = state.get("patterns", {})
            print(f"步骤 {step}: 智能体数={stats.get('agent_count', 0)}, "
                  f"中心=({stats.get('center', (0,0))[0]:.1f}, {stats.get('center', (0,0))[1]:.1f}), "
                  f"平均速度={stats.get('avg_speed', 0):.2f}")
            
            if patterns:
                best_pattern = max(patterns.items(), key=lambda x: x[1])
                if best_pattern[1] > 0.3:
                    print(f"  检测到模式: {best_pattern[0]} (置信度: {best_pattern[1]:.2f})")
    
    # 最终状态
    final_state = swarm.get_swarm_state()
    print("\n=== 最终状态 ===")
    print(f"智能体数: {final_state['statistics']['agent_count']}")
    print(f"总能量: {final_state['statistics']['total_energy']:.1f}")
    print(f"任务统计: {final_state['tasks']}")


if __name__ == "__main__":
    asyncio.run(main())