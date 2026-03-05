#!/usr/bin/env python3
"""
群体行为引擎 (Swarm Behavior Engine)
奥创智能体生态系统 - 第2世：涌现智能
"""

import asyncio
import random
import math
from typing import List, Dict, Any, Optional, Tuple, Callable
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum
import json
import time


class BehaviorType(Enum):
    """群体行为类型"""
    ALIGNMENT = "alignment"          # 对齐：向邻居平均方向移动
    COHESION = "cohesion"            # 聚合：向邻居中心聚集
    SEPARATION = "separation"        # 分离：避免与邻居过于接近
    FLOCKING = "flocking"            # 群集：综合行为
    EXPLORATION = "exploration"      # 探索：随机探索
    FORAGING = "foraging"            # 觅食：寻找目标
    MIGRATION = "migration"          # 迁移：群体移动
    HUNTING = "hunting"              # 狩猎：协同捕猎
    DEFENSE = "defense"              # 防御：保护群体
    NESTING = "nesting"              # 筑巢：建立家园


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
    
    def limit(self, max_magnitude: float) -> 'Vector2D':
        mag = self.magnitude()
        if mag > max_magnitude:
            return self.normalize() * max_magnitude
        return self
    
    def distance_to(self, other: 'Vector2D') -> float:
        return (self - other).magnitude()
    
    def dot(self, other: 'Vector2D') -> float:
        return self.x * other.x + self.y * other.y
    
    def angle_to(self, other: 'Vector2D') -> float:
        return math.atan2(other.y - self.y, other.x - self.x)


@dataclass
class AgentState:
    """智能体状态"""
    id: str
    position: Vector2D
    velocity: Vector2D = field(default_factory=Vector2D)
    acceleration: Vector2D = field(default_factory=Vector2D)
    heading: float = 0.0
    energy: float = 100.0
    health: float = 100.0
    age: int = 0
    role: str = "worker"
    state: str = "idle"
    last_update: float = field(default_factory=time.time)
    neighbors: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BehaviorConfig:
    """行为配置"""
    max_speed: float = 5.0
    max_force: float = 0.5
    perception_radius: float = 50.0
    separation_radius: float = 25.0
    alignment_weight: float = 1.0
    cohesion_weight: float = 1.0
    separation_weight: float = 1.5
    wander_strength: float = 0.1
    separation_force: float = 1.0
    cohesion_force: float = 1.0
    alignment_force: float = 1.0
    boundary_force: float = 2.0
    boundary_margin: float = 10.0


@dataclass
class Boid:
    """群体单元(Boid)"""
    id: str
    position: Vector2D
    velocity: Vector2D
    acceleration: Vector2D = field(default_factory=Vector2D)
    config: BehaviorConfig = field(default_factory=BehaviorConfig)
    behavior_weights: Dict[str, float] = field(default_factory=lambda: {
        "alignment": 1.0,
        "cohesion": 1.0,
        "separation": 1.5
    })
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def apply_force(self, force: Vector2D):
        self.acceleration = self.acceleration + force
    
    def update(self, dt: float = 1.0):
        self.velocity = self.velocity + self.acceleration * dt
        self.velocity = self.velocity.limit(self.config.max_speed)
        self.position = self.position + self.velocity * dt
        self.acceleration = Vector2D()
    
    def heading(self) -> float:
        return math.atan2(self.velocity.y, self.velocity.x)


class SwarmBehaviorEngine:
    """群体行为引擎"""
    
    def __init__(self, space_bounds: Tuple[float, float] = (1000, 1000)):
        self.space_bounds = space_bounds
        self.agents: Dict[str, AgentState] = {}
        self.boids: Dict[str, Boid] = {}
        self.config = BehaviorConfig()
        self.behavior_log: List[Dict[str, Any]] = []
        self.group_behaviors: Dict[str, Callable] = {}
        self.emergent_patterns: List[Dict[str, Any]] = []
        self.behavior_history: List[Dict[str, float]] = []
        self.performance_metrics = {
            "cohesion_score": 0.0,
            "separation_score": 0.0,
            "alignment_score": 0.0,
            "efficiency": 0.0
        }
        
        self._init_group_behaviors()
    
    def _init_group_behaviors(self):
        """初始化群体行为"""
        self.group_behaviors = {
            "alignment": self._alignment,
            "cohesion": self._cohesion,
            "separation": self._separation,
            "exploration": self._exploration,
            "foraging": self._foraging,
            "defense": self._defense,
            "nesting": self._nesting
        }
    
    # ==================== 核心行为算法 ====================
    
    def _alignment(self, boid: Boid, neighbors: List[Boid]) -> Vector2D:
        """对齐行为：向邻居平均方向移动"""
        if not neighbors:
            return Vector2D()
        
        avg_velocity = Vector2D()
        for n in neighbors:
            avg_velocity = avg_velocity + n.velocity
        
        avg_velocity = avg_velocity / len(neighbors)
        steering = avg_velocity - boid.velocity
        steering = steering.normalize() * self.config.max_force
        
        self.performance_metrics["alignment_score"] = min(1.0, steering.magnitude() / self.config.max_force)
        return steering
    
    def _cohesion(self, boid: Boid, neighbors: List[Boid]) -> Vector2D:
        """聚合行为：向邻居中心聚集"""
        if not neighbors:
            return Vector2D()
        
        center = Vector2D()
        for n in neighbors:
            center = center + n.position
        
        center = center / len(neighbors)
        desired = center - boid.position
        steering = desired.normalize() * self.config.max_speed - boid.velocity
        steering = steering.limit(self.config.max_force)
        
        self.performance_metrics["cohesion_score"] = min(1.0, steering.magnitude() / self.config.max_force)
        return steering
    
    def _separation(self, boid: Boid, neighbors: List[Boid]) -> Vector2D:
        """分离行为：避免过于接近"""
        if not neighbors:
            return Vector2D()
        
        steer = Vector2D()
        count = 0
        
        for n in neighbors:
            dist = boid.position.distance_to(n.position)
            if 0 < dist < self.config.separation_radius:
                diff = boid.position - n.position
                diff = diff.normalize() / dist
                steer = steer + diff
                count += 1
        
        if count > 0:
            steer = steer / count
            steer = steer.normalize() * self.config.max_speed - boid.velocity
            steer = steer.limit(self.config.max_force)
        
        self.performance_metrics["separation_score"] = min(1.0, steer.magnitude() / self.config.max_force)
        return steer
    
    def _exploration(self, boid: Boid) -> Vector2D:
        """探索行为：随机游走"""
        angle = random.uniform(0, 2 * math.pi)
        wander_force = Vector2D(
            math.cos(angle) * self.config.wander_strength,
            math.sin(angle) * self.config.wander_strength
        )
        return wander_force
    
    def _foraging(self, boid: Boid, target: Vector2D) -> Vector2D:
        """觅食行为：向目标移动"""
        desired = target - boid.position
        dist = desired.magnitude()
        
        if dist < 5.0:
            return Vector2D()
        
        desired = desired.normalize() * self.config.max_speed
        steering = desired - boid.velocity
        return steering.limit(self.config.max_force)
    
    def _defense(self, agent_id: str, threat_position: Vector2D) -> Vector2D:
        """防御行为：逃离威胁"""
        agent = self.agents.get(agent_id)
        if not agent:
            return Vector2D()
        
        away = agent.position - threat_position
        desired = away.normalize() * self.config.max_speed
        steering = desired - agent.velocity
        return steering.limit(self.config.max_force)
    
    def _nesting(self, boid: Boid, nest_position: Vector2D) -> Vector2D:
        """筑巢行为：返回巢穴"""
        to_nest = nest_position - boid.position
        dist = to_nest.magnitude()
        
        if dist < 50.0:
            return Vector2D()
        
        desired = to_nest.normalize() * self.config.max_speed
        steering = desired - boid.velocity
        return steering.limit(self.config.max_force * 0.5)
    
    # ==================== 群体行为管理 ====================
    
    def add_boid(self, boid: Boid):
        """添加群体单元"""
        self.boids[boid.id] = boid
    
    def remove_boid(self, boid_id: str):
        """移除群体单元"""
        if boid_id in self.boids:
            del self.boids[boid_id]
    
    def add_agent(self, agent: AgentState):
        """添加智能体"""
        self.agents[agent.id] = agent
    
    def get_neighbors(self, boid: Boid, radius: Optional[float] = None) -> List[Boid]:
        """获取邻居"""
        if radius is None:
            radius = self.config.perception_radius
        
        neighbors = []
        for other_id, other_boid in self.boids.items():
            if other_id != boid.id:
                dist = boid.position.distance_to(other_boid.position)
                if dist < radius:
                    neighbors.append(other_boid)
        return neighbors
    
    def apply_behavior(self, boid: Boid, behavior_type: str, **kwargs) -> Vector2D:
        """应用特定行为"""
        behavior_func = self.group_behaviors.get(behavior_type)
        if not behavior_func:
            return Vector2D()
        
        neighbors = self.get_neighbors(boid)
        
        if behavior_type == "foraging":
            target = kwargs.get("target", Vector2D())
            return behavior_func(boid, target)
        elif behavior_type == "defense":
            threat = kwargs.get("threat", Vector2D())
            agent_id = kwargs.get("agent_id", boid.id)
            if agent_id in self.agents:
                return self._defense(agent_id, threat)
            return Vector2D()
        elif behavior_type == "nesting":
            nest = kwargs.get("nest", Vector2D())
            return behavior_func(boid, nest)
        else:
            return behavior_func(boid, neighbors)
    
    def apply_flocking(self, boid: Boid) -> Vector2D:
        """应用群集行为（Boids算法）"""
        neighbors = self.get_neighbors(boid)
        
        alignment = self._alignment(boid, neighbors) * boid.behavior_weights.get("alignment", 1.0)
        cohesion = self._cohesion(boid, neighbors) * boid.behavior_weights.get("cohesion", 1.0)
        separation = self._separation(boid, neighbors) * boid.behavior_weights.get("separation", 1.0)
        
        total = alignment + cohesion + separation
        return total
    
    def apply_boundary(self, boid: Boid) -> Vector2D:
        """边界行为"""
        steer = Vector2D()
        margin = self.config.boundary_margin
        width, height = self.space_bounds
        
        if boid.position.x < margin:
            steer.x = self.config.boundary_force * (margin - boid.position.x) / margin
        elif boid.position.x > width - margin:
            steer.x = -self.config.boundary_force * (boid.position.x - (width - margin)) / margin
        
        if boid.position.y < margin:
            steer.y = self.config.boundary_force * (margin - boid.position.y) / margin
        elif boid.position.y > height - margin:
            steer.y = -self.config.boundary_force * (boid.position.y - (height - margin)) / margin
        
        return steer
    
    # ==================== 群体动态 ====================
    
    def update(self, dt: float = 1.0):
        """更新所有群体单元"""
        for boid in self.boids.values():
            flocking = self.apply_flocking(boid)
            boundary = self.apply_boundary(boid)
            
            boid.apply_force(flocking)
            boid.apply_force(boundary)
            boid.update(dt)
        
        self._update_emergent_patterns()
        self._record_metrics()
    
    def _update_emergent_patterns(self):
        """检测涌现模式"""
        patterns = []
        
        if len(self.boids) > 2:
            avg_position = Vector2D()
            for boid in self.boids.values():
                avg_position = avg_position + boid.position
            avg_position = avg_position / len(self.boids)
            
            variance = 0.0
            for boid in self.boids.values():
                variance += boid.position.distance_to(avg_position) ** 2
            variance /= len(self.boids)
            
            if variance < 1000:
                patterns.append({
                    "type": "cluster",
                    "strength": 1.0 - (variance / 1000),
                    "center": (avg_position.x, avg_position.y)
                })
            
            velocities = [b.velocity.magnitude() for b in self.boids.values()]
            avg_velocity = sum(velocities) / len(velocities)
            velocity_variance = sum((v - avg_velocity) ** 2 for v in velocities) / len(velocities)
            
            if velocity_variance < 10:
                patterns.append({
                    "type": "coordinated_movement",
                    "strength": 1.0 - (velocity_variance / 10),
                    "direction": math.atan2(avg_position.y, avg_position.x)
                })
        
        self.emergent_patterns = patterns
    
    def _record_metrics(self):
        """记录性能指标"""
        metrics = {
            "timestamp": time.time(),
            **self.performance_metrics,
            "agent_count": len(self.agents),
            "boid_count": len(self.boids),
            "pattern_count": len(self.emergent_patterns)
        }
        self.behavior_history.append(metrics)
        
        if len(self.behavior_history) > 1000:
            self.behavior_history = self.behavior_history[-1000:]
        
        total_cohesion = sum(m["cohesion_score"] for m in self.behavior_history[-10:]) / 10
        total_separation = sum(m["separation_score"] for m in self.behavior_history[-10:]) / 10
        total_alignment = sum(m["alignment_score"] for m in self.behavior_history[-10:]) / 10
        
        self.performance_metrics["efficiency"] = (total_cohesion + total_separation + total_alignment) / 3
    
    # ==================== 高级群体行为 ====================
    
    def form_v_shape(self, leader_id: str, follower_ids: List[str]):
        """形成V字形编队"""
        leader = self.boids.get(leader_id)
        if not leader:
            return
        
        for i, follower_id in enumerate(follower_ids):
            follower = self.boids.get(follower_id)
            if not follower:
                continue
            
            offset_angle = math.radians(45 if i % 2 == 0 else -45)
            offset_distance = 30 + (i // 2) * 20
            
            target = Vector2D(
                leader.position.x - math.cos(leader.heading() + offset_angle) * offset_distance,
                leader.position.y - math.sin(leader.heading() + offset_angle) * offset_distance
            )
            
            follower.behavior_weights["cohesion"] = 3.0
            follower.behavior_weights["alignment"] = 2.0
            follower.behavior_weights["separation"] = 0.5
    
    def form_circle(self, center: Vector2D, radius: float):
        """形成圆形编队"""
        sorted_boids = sorted(self.boids.values(), key=lambda b: b.position.distance_to(center))
        
        for i, boid in enumerate(sorted_boids):
            angle = (2 * math.pi * i) / len(sorted_boids)
            target = Vector2D(
                center.x + radius * math.cos(angle),
                center.y + radius * math.sin(angle)
            )
            
            desired = target - boid.position
            steer = desired.normalize() * self.config.max_speed - boid.velocity
            boid.apply_force(steer.limit(self.config.max_force * 0.5))
    
    def create_swarm_motion(self, target: Vector2D, formation: str = "flocking"):
        """创建群体运动"""
        if formation == "flocking":
            for boid in self.boids.values():
                flocking = self.apply_flocking(boid)
                to_target = self._foraging(boid, target)
                boid.apply_force(flocking * 0.7 + to_target * 0.3)
        elif formation == "line":
            sorted_boids = sorted(self.boids.values(), 
                                  key=lambda b: b.position.distance_to(target))
            for i, boid in enumerate(sorted_boids):
                offset = Vector2D(0, i * 20)
                target_with_offset = target + offset
                steer = self._foraging(boid, target_with_offset)
                boid.apply_force(steer)
        elif formation == "radial":
            center = target
            for i, boid in enumerate(self.boids.values()):
                angle = (2 * math.pi * i) / len(self.boids)
                offset = Vector2D(math.cos(angle) * 50, math.sin(angle) * 50)
                target_with_offset = center + offset
                steer = self._foraging(boid, target_with_offset)
                boid.apply_force(steer)
    
    # ==================== 自适应行为 ====================
    
    def adapt_behavior_weights(self):
        """自适应调整行为权重"""
        if not self.emergent_patterns:
            return
        
        for pattern in self.emergent_patterns:
            if pattern["type"] == "cluster":
                for boid in self.boids.values():
                    boid.behavior_weights["separation"] *= 1.2
                    boid.behavior_weights["cohesion"] *= 0.8
            elif pattern["type"] == "coordinated_movement":
                for boid in self.boids.values():
                    boid.behavior_weights["alignment"] *= 1.2
    
    def detect_formation(self) -> str:
        """检测当前编队"""
        if len(self.boids) < 3:
            return "insufficient_agents"
        
        positions = [b.position for b in self.boids.values()]
        center = sum(p.x for p in positions) / len(positions), sum(p.y for p in positions) / len(positions)
        
        distances = [math.sqrt((p.x - center[0])**2 + (p.y - center[1])**2) for p in positions]
        avg_distance = sum(distances) / len(distances)
        
        if avg_distance < 30:
            return "cluster"
        
        velocities = [b.velocity.magnitude() for b in self.boids.values()]
        velocity_variance = sum((v - sum(velocities)/len(velocities))**2 for v in velocities) / len(velocities)
        
        if velocity_variance < 5:
            return "coordinated"
        
        return "dispersed"
    
    # ==================== 状态查询 ====================
    
    def get_swarm_state(self) -> Dict[str, Any]:
        """获取群体状态"""
        return {
            "agent_count": len(self.agents),
            "boid_count": len(self.boids),
            "formation": self.detect_formation(),
            "emergent_patterns": self.emergent_patterns,
            "performance": self.performance_metrics,
            "bounds": self.space_bounds
        }
    
    def get_agent_positions(self) -> Dict[str, Tuple[float, float]]:
        """获取所有智能体位置"""
        return {bid: (b.position.x, b.position.y) for bid, b in self.boids.items()}
    
    def get_statistics(self) -> Dict[str, float]:
        """获取统计数据"""
        if not self.boids:
            return {}
        
        velocities = [b.velocity.magnitude() for b in self.boids.values()]
        positions = [b.position for b in self.boids.values()]
        
        center = Vector2D(sum(p.x for p in positions) / len(positions),
                         sum(p.y for p in positions) / len(positions))
        
        avg_dist_to_center = sum(p.distance_to(center) for p in positions) / len(positions)
        
        return {
            "avg_velocity": sum(velocities) / len(velocities),
            "max_velocity": max(velocities),
            "min_velocity": min(velocities),
            "avg_distance_to_center": avg_dist_to_center,
            "total_agents": len(self.boids),
            "efficiency": self.performance_metrics["efficiency"]
        }
    
    # ==================== 仿真控制 ====================
    
    async def run_simulation(self, steps: int = 100, dt: float = 1.0):
        """运行模拟"""
        for step in range(steps):
            self.update(dt)
            await asyncio.sleep(0.01)
            
            if step % 10 == 0:
                self.behavior_log.append({
                    "step": step,
                    "state": self.get_swarm_state()
                })
    
    def export_state(self, filepath: str):
        """导出状态"""
        state = {
            "swarm_state": self.get_swarm_state(),
            "statistics": self.get_statistics(),
            "behavior_history": self.behavior_history[-100:],
            "timestamp": time.time()
        }
        with open(filepath, 'w') as f:
            json.dump(state, f, indent=2)


class MultiSwarmCoordinator:
    """多群体协调器"""
    
    def __init__(self):
        self.swarms: Dict[str, SwarmBehaviorEngine] = {}
        self.inter_swarm_forces: Dict[Tuple[str, str], float] = {}
        self.coordination_history: List[Dict[str, Any]] = []
    
    def add_swarm(self, swarm_id: str, swarm: SwarmBehaviorEngine):
        """添加群体"""
        self.swarms[swarm_id] = swarm
    
    def set_inter_force(self, swarm1_id: str, swarm2_id: str, force: float):
        """设置群体间作用力"""
        self.inter_swarm_forces[(swarm1_id, swarm2_id)] = force
        self.inter_swarm_forces[(swarm2_id, swarm1_id)] = force
    
    def coordinate_swarms(self):
        """协调多个群体"""
        for (swarm1_id, swarm2_id), force in self.inter_swarm_forces.items():
            if swarm1_id not in self.swarms or swarm2_id not in self.swarms:
                continue
            
            swarm1 = self.swarms[swarm1_id]
            swarm2 = self.swarms[swarm2_id]
            
            center1 = self._get_swarm_center(swarm1)
            center2 = self._get_swarm_center(swarm2)
            
            direction = center2 - center1
            if direction.magnitude() > 0:
                for boid in swarm1.boids.values():
                    boid.apply_force(direction.normalize() * force)
    
    def _get_swarm_center(self, swarm: SwarmBehaviorEngine) -> Vector2D:
        """获取群体中心"""
        if not swarm.boids:
            return Vector2D()
        
        positions = [b.position for b in swarm.boids.values()]
        return Vector2D(sum(p.x for p in positions) / len(positions),
                       sum(p.y for p in positions) / len(positions))


# 辅助函数
def create_boid(boid_id: str, x: float, y: float, 
                vx: float = 0, vy: float = 0,
                config: Optional[BehaviorConfig] = None) -> Boid:
    """创建群体单元"""
    return Boid(
        id=boid_id,
        position=Vector2D(x, y),
        velocity=Vector2D(vx, vy),
        config=config or BehaviorConfig()
    )


if __name__ == "__main__":
    engine = SwarmBehaviorEngine(space_bounds=(500, 500))
    
    for i in range(20):
        boid = create_boid(
            f"boid_{i}",
            random.uniform(0, 500),
            random.uniform(0, 500),
            random.uniform(-2, 2),
            random.uniform(-2, 2)
        )
        engine.add_boid(boid)
    
    print(f"群体行为引擎初始化完成")
    print(f"初始单元数: {len(engine.boids)}")
    
    for step in range(50):
        engine.update()
        
        if step % 10 == 0:
            stats = engine.get_statistics()
            print(f"步骤 {step}: 效率={stats.get('efficiency', 0):.2f}, 编队={engine.detect_formation()}")