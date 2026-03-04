#!/usr/bin/env python3
"""
奥创能量运算体系 - 夙愿十九第2世
能量计算模型 + 能量信息转换 + 能量驱动的智能

功能：
1. 能量计算模型 - 模拟能量流动、转化、守恒
2. 能量信息转换 - 能量与信息的等价转换
3. 能量驱动的智能 - 基于能量效率的决策优化
"""

import time
import random
import json
import hashlib
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
import threading


# ==================== 能量基础类型 ====================

class EnergyType:
    """能量类型枚举"""
    KINETIC = "kinetic"           # 动能
    POTENTIAL = "potential"       # 势能
    THERMAL = "thermal"           # 热能
    ELECTRICAL = "electrical"     # 电能
    CHEMICAL = "chemical"         # 化学能
    NUCLEAR = "nuclear"           # 核能
    QUANTUM = "quantum"           # 量子能量
    INFORMATION = "information"   # 信息能
    MENTAL = "mental"             # 精神能量
    COSMIC = "cosmic"             # 宇宙能量


@dataclass
class EnergyUnit:
    """能量单元"""
    energy_type: str
    amount: float
    quality: float = 1.0  # 能量质量因子 0-1
    entropy: float = 0.0  # 熵值
    timestamp: float = field(default_factory=time.time)
    metadata: Dict = field(default_factory=dict)
    
    def get_effective_energy(self) -> float:
        """获取有效能量 (考虑质量和熵)"""
        return self.amount * self.quality * (1 - self.entropy)


# ==================== 能量计算模型 ====================

class EnergyCalculator:
    """能量计算引擎"""
    
    # 物理常数 (归一化单位)
    C_LIGHT = 299792458  # 光速 m/s
    PLANCK = 6.62607015e-34  # 普朗克常数
    BOLTZMANN = 1.380649e-23  # 玻尔兹曼常数
    
    def __init__(self):
        self.calculation_history = []
        self.energy_pool = defaultdict(float)
        
    def calculate_kinetic_energy(self, mass: float, velocity: float) -> float:
        """计算动能: E = 0.5 * m * v^2"""
        energy = 0.5 * mass * velocity ** 2
        self.calculation_history.append({
            'type': 'kinetic',
            'inputs': {'mass': mass, 'velocity': velocity},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_potential_energy(self, mass: float, gravity: float, height: float) -> float:
        """计算势能: E = m * g * h"""
        energy = mass * gravity * height
        self.calculation_history.append({
            'type': 'potential',
            'inputs': {'mass': mass, 'gravity': gravity, 'height': height},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_thermal_energy(self, mass: float, temp_change: float, 
                                  specific_heat: float = 4.186) -> float:
        """计算热能: E = m * c * ΔT"""
        energy = mass * specific_heat * temp_change
        self.calculation_history.append({
            'type': 'thermal',
            'inputs': {'mass': mass, 'temp_change': temp_change, 'specific_heat': specific_heat},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_mass_energy(self, mass: float) -> float:
        """计算质能: E = m * c^2"""
        energy = mass * (self.C_LIGHT ** 2)
        self.calculation_history.append({
            'type': 'mass_energy',
            'inputs': {'mass': mass},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_information_energy(self, bits: float, temperature: float = 300) -> float:
        """
        计算信息能量 - Landauer's原理
        E = k * T * ln(2) * bits
        每擦除1比特信息产生 k*T*ln(2) 的热量
        """
        energy = self.BOLTZMANN * temperature * math.log(2) * bits
        self.calculation_history.append({
            'type': 'information',
            'inputs': {'bits': bits, 'temperature': temperature},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_quantum_energy(self, frequency: float) -> float:
        """计算量子能量: E = h * f"""
        energy = self.PLANCK * frequency
        self.calculation_history.append({
            'type': 'quantum',
            'inputs': {'frequency': frequency},
            'output': energy,
            'timestamp': time.time()
        })
        return energy
    
    def calculate_entropy_change(self, initial_states: int, final_states: int) -> float:
        """计算熵变: ΔS = k * ln(W_f / W_i)"""
        delta_s = self.BOLTZMANN * math.log(final_states / initial_states)
        self.calculation_history.append({
            'type': 'entropy',
            'inputs': {'initial_states': initial_states, 'final_states': final_states},
            'output': delta_s,
            'timestamp': time.time()
        })
        return delta_s
    
    def energy_conversion_efficiency(self, input_energy: float, 
                                     output_energy: float, 
                                     energy_type_from: str,
                                     energy_type_to: str) -> float:
        """计算能量转换效率"""
        if input_energy <= 0:
            return 0.0
        efficiency = output_energy / input_energy
        
        # 不同转换类型有不同的理论最大效率
        theoretical_max = self._theoretical_max_efficiency(energy_type_from, energy_type_to)
        
        self.calculation_history.append({
            'type': 'conversion_efficiency',
            'inputs': {'input': input_energy, 'output': output_energy,
                      'from': energy_type_from, 'to': energy_type_to},
            'output': efficiency,
            'theoretical_max': theoretical_max,
            'timestamp': time.time()
        })
        return efficiency
    
    def _theoretical_max_efficiency(self, from_type: str, to_type: str) -> float:
        """不同能量转换的理论最大效率"""
        # 卡诺循环最高效率
        carnot_efficiency = 0.9  # 假设高温热源
        
        conversions = {
            (EnergyType.THERMAL, EnergyType.ELECTRICAL): 0.6,
            (EnergyType.CHEMICAL, EnergyType.ELECTRICAL): 0.95,
            (EnergyType.NUCLEAR, EnergyType.THERMAL): 0.4,
            (EnergyType.ELECTRICAL, EnergyType.KINETIC): 0.95,
            (EnergyType.QUANTUM, EnergyType.INFORMATION): 0.9,
            (EnergyType.INFORMATION, EnergyType.MENTAL): 0.7,
        }
        
        return conversions.get((from_type, to_type), 0.85)
    
    def get_energy_pool(self) -> Dict[str, float]:
        """获取当前能量池状态"""
        return dict(self.energy_pool)
    
    def add_to_pool(self, energy_type: str, amount: float):
        """向能量池添加能量"""
        self.energy_pool[energy_type] += amount
    
    def consume_from_pool(self, energy_type: str, amount: float) -> bool:
        """从能量池消耗能量"""
        if self.energy_pool.get(energy_type, 0) >= amount:
            self.energy_pool[energy_type] -= amount
            return True
        return False


# ==================== 能量流动网络 ====================

class EnergyFlowNetwork:
    """能量流动网络 - 模拟能量在系统中的传输和分配"""
    
    def __init__(self):
        self.nodes = {}  # 能量节点
        self.channels = []  # 能量通道
        self.flow_history = []
        
    def add_node(self, node_id: str, capacity: float, 
                 node_type: str = "processor") -> bool:
        """添加能量节点"""
        self.nodes[node_id] = {
            'id': node_id,
            'capacity': capacity,
            'current_energy': capacity * 0.5,
            'type': node_type,
            'efficiency': random.uniform(0.7, 0.95),
            'connections': []
        }
        return True
    
    def add_channel(self, from_node: str, to_node: str, 
                    bandwidth: float, loss_rate: float = 0.05) -> bool:
        """添加能量传输通道"""
        if from_node not in self.nodes or to_node not in self.nodes:
            return False
            
        channel = {
            'from': from_node,
            'to': to_node,
            'bandwidth': bandwidth,
            'loss_rate': loss_rate,
            'current_flow': 0,
            'active': True
        }
        self.channels.append(channel)
        self.nodes[from_node]['connections'].append(to_node)
        return True
    
    def transfer_energy(self, from_node: str, to_node: str, 
                        amount: float) -> Tuple[bool, float]:
        """在节点间传输能量"""
        if from_node not in self.nodes or to_node not in self.nodes:
            return False, 0
            
        from_node_data = self.nodes[from_node]
        
        # 检查源节点是否有足够能量
        if from_node_data['current_energy'] < amount:
            amount = from_node_data['current_energy']
            
        # 找到通道计算损耗
        channel = self._find_channel(from_node, to_node)
        if channel:
            actual_amount = amount * (1 - channel['loss_rate'])
            channel['current_flow'] = actual_amount
        else:
            actual_amount = amount * 0.95  # 默认5%损耗
            
        # 执行传输
        from_node_data['current_energy'] -= amount
        self.nodes[to_node]['current_energy'] += actual_amount
        
        self.flow_history.append({
            'from': from_node,
            'to': to_node,
            'requested': amount,
            'transferred': actual_amount,
            'loss': amount - actual_amount,
            'timestamp': time.time()
        })
        
        return True, actual_amount
    
    def _find_channel(self, from_node: str, to_node: str) -> Optional[Dict]:
        """查找两点间的通道"""
        for ch in self.channels:
            if ch['from'] == from_node and ch['to'] == to_node:
                return ch
        return None
    
    def optimize_flow(self) -> Dict[str, Any]:
        """优化能量流动 - 最小化损耗"""
        total_efficiency = 0
        optimized_flows = []
        
        for channel in self.channels:
            from_n = self.nodes[channel['from']]
            to_n = self.nodes[channel['to']]
            
            # 计算最优流量
            available = from_n['current_energy']
            target = to_n['capacity'] - to_n['current_energy']
            optimal = min(available, target, channel['bandwidth'])
            
            efficiency = 1 - channel['loss_rate']
            total_efficiency += efficiency
            
            optimized_flows.append({
                'channel': f"{channel['from']}->{channel['to']}",
                'optimal_flow': optimal,
                'efficiency': efficiency
            })
        
        return {
            'total_efficiency': total_efficiency / max(len(self.channels), 1),
            'optimized_flows': optimized_flows,
            'timestamp': time.time()
        }
    
    def get_network_status(self) -> Dict[str, Any]:
        """获取网络状态"""
        total_capacity = sum(n['capacity'] for n in self.nodes.values())
        total_energy = sum(n['current_energy'] for n in self.nodes.values())
        utilization = total_energy / total_capacity if total_capacity > 0 else 0
        
        return {
            'nodes': len(self.nodes),
            'channels': len(self.channels),
            'total_capacity': total_capacity,
            'total_energy': total_energy,
            'utilization': utilization,
            'node_details': self.nodes
        }


# ==================== 能量信息转换器 ====================

class EnergyInformationConverter:
    """能量与信息转换器"""
    
    def __init__(self):
        self.converter_id = f"EIC-{int(time.time())}"
        self.conversion_history = []
        self.entropy_manager = EntropyManager()
        
    def information_to_energy(self, data: Any, temperature: float = 300) -> float:
        """将信息转换为能量 (Landauer边界)
        
        根据Landauer原理，每比特信息包含 k*T*ln(2) 的能量
        """
        # 计算信息的比特数
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = json.dumps(data, sort_keys=True).encode('utf-8')
        
        bit_count = len(data_bytes) * 8
        
        # 添加信息熵
        entropy = self._calculate_entropy(data_bytes)
        
        # 计算能量
        energy = EnergyCalculator().calculate_information_energy(bit_count, temperature)
        
        # 记录转换
        conversion_record = {
            'type': 'information_to_energy',
            'bit_count': bit_count,
            'entropy': entropy,
            'temperature': temperature,
            'energy': energy,
            'timestamp': time.time()
        }
        self.conversion_history.append(conversion_record)
        
        return energy
    
    def energy_to_information(self, energy: float, temperature: float = 300,
                              target_bits: int = 256) -> Dict[str, Any]:
        """将能量转换为信息 (反Landauer)
        
        给定能量，可以存储/处理的最大信息量
        """
        calc = EnergyCalculator()
        max_bits = (energy / (calc.BOLTZMANN * temperature * math.log(2)))
        
        # 生成信息
        actual_bits = min(max_bits, target_bits)
        
        # 使用能量熵源生成随机数据
        random_data = self._generate_from_energy(energy, actual_bits)
        
        entropy = self._calculate_entropy(random_data)
        
        conversion_record = {
            'type': 'energy_to_information',
            'energy': energy,
            'temperature': temperature,
            'max_bits': max_bits,
            'actual_bits': actual_bits,
            'entropy': entropy,
            'timestamp': time.time()
        }
        self.conversion_history.append(conversion_record)
        
        return {
            'bits': actual_bits,
            'data': random_data.hex()[:64],  # 截断显示
            'entropy': entropy,
            'energy_used': energy
        }
    
    def _calculate_entropy(self, data: bytes) -> float:
        """计算香农熵"""
        if len(data) == 0:
            return 0
            
        frequency = defaultdict(int)
        for byte in data:
            frequency[byte] += 1
            
        entropy = 0
        for count in frequency.values():
            probability = count / len(data)
            if probability > 0:
                entropy -= probability * math.log2(probability)
                
        return entropy
    
    def _generate_from_energy(self, energy: float, bits: int) -> bytes:
        """使用能量作为熵源生成随机数据"""
        # 使用能量值和时间戳作为种子
        seed = int(energy * 1e18) ^ int(time.time() * 1e9)
        random.seed(seed)
        
        # 生成随机字节
        result = bytes([random.randint(0, 255) for _ in range(bits // 8)])
        random.seed()  # 重置随机种子
        
        return result
    
    def compress_energy(self, data: str, compression_level: int = 9) -> Dict[str, Any]:
        """能量感知压缩 - 根据能量成本优化压缩"""
        import zlib
        
        original_bytes = data.encode('utf-8')
        original_bits = len(original_bytes) * 8
        
        compressed = zlib.compress(original_bytes, compression_level)
        compressed_bits = len(compressed) * 8
        
        # 计算压缩能量收益
        energy_saved = EnergyCalculator().calculate_information_energy(
            original_bits - compressed_bits
        )
        
        return {
            'original_bits': original_bits,
            'compressed_bits': compressed_bits,
            'compression_ratio': compressed_bits / original_bits,
            'energy_saved': energy_saved,
            'compressed_size': len(compressed)
        }


class EntropyManager:
    """熵管理器 - 控制系统的熵增/熵减"""
    
    def __init__(self):
        self.total_entropy = 0
        self.entropy_sources = []
        
    def add_entropy(self, source: str, amount: float):
        """添加熵"""
        self.total_entropy += amount
        self.entropy_sources.append({
            'source': source,
            'amount': amount,
            'timestamp': time.time()
        })
        
    def remove_entropy(self, amount: float) -> bool:
        """移除熵 (需要能量消耗)"""
        if self.total_entropy >= amount:
            self.total_entropy -= amount
            return True
        return False
    
    def get_entropy(self) -> float:
        """获取当前熵值"""
        return self.total_entropy
    
    def measure_order(self, data: Any) -> float:
        """测量数据的有序程度 (负熵)"""
        if isinstance(data, str):
            data_bytes = data.encode('utf-8')
        elif isinstance(data, bytes):
            data_bytes = data
        else:
            data_bytes = json.dumps(data).encode('utf-8')
        
        eic = EnergyInformationConverter()
        entropy = eic._calculate_entropy(data_bytes)
        max_entropy = 8  # 每字节最大熵8
        
        # 有序程度 = 1 - (实际熵 / 最大熵)
        return 1 - (entropy / max_entropy)


# ==================== 能量驱动智能 ====================

class EnergyDrivenIntelligence:
    """能量驱动的智能系统 - 基于能量效率做决策"""
    
    def __init__(self):
        self.energy_calculator = EnergyCalculator()
        self.network = EnergyFlowNetwork()
        self.decision_cache = []
        self.efficiency_threshold = 0.7
        
    def evaluate_task_energy_cost(self, task: Dict[str, Any]) -> Dict[str, float]:
        """评估任务的能量成本"""
        # 模拟不同操作的能量消耗
        operation_costs = {
            'computation': 1.0,
            'memory_access': 0.5,
            'network_transfer': 2.0,
            'storage_write': 1.5,
            'storage_read': 0.8,
            'analysis': 3.0,
            'learning': 5.0,
            'reasoning': 4.0
        }
        
        base_cost = operation_costs.get(task.get('type', 'computation'), 1.0)
        complexity = task.get('complexity', 1.0)
        data_size = task.get('data_size', 1.0)
        
        energy_cost = base_cost * complexity * data_size
        time_cost = energy_cost / 1000  # 假设1000单位能量/秒
        
        return {
            'energy_cost': energy_cost,
            'time_cost': time_cost,
            'efficiency': energy_cost / (complexity + 1)
        }
    
    def select_optimal_strategy(self, strategies: List[Dict]) -> Dict[str, Any]:
        """基于能量效率选择最优策略"""
        if not strategies:
            return {}
            
        scored_strategies = []
        
        for strategy in strategies:
            energy_cost = self.evaluate_task_energy_cost(strategy)
            
            # 计算综合得分 (考虑能量、时间、质量)
            quality_factor = strategy.get('quality', 1.0)
            speed_factor = 1 / (energy_cost['time_cost'] + 0.1)
            efficiency_factor = 1 / energy_cost['efficiency']
            
            # 能量效率权重最高
            composite_score = (
                efficiency_factor * 0.5 +
                quality_factor * 0.3 +
                speed_factor * 0.2
            )
            
            scored_strategies.append({
                'strategy': strategy.get('name', 'unnamed'),
                'score': composite_score,
                'energy_cost': energy_cost['energy_cost'],
                'quality': quality_factor,
                'details': strategy
            })
        
        # 排序并选择最优
        scored_strategies.sort(key=lambda x: x['score'], reverse=True)
        winner = scored_strategies[0]
        
        self.decision_cache.append({
            'decision': winner,
            'alternatives': scored_strategies,
            'timestamp': time.time()
        })
        
        return winner
    
    def predict_energy_requirement(self, task_history: List[Dict]) -> Dict[str, float]:
        """基于历史预测能量需求"""
        if not task_history:
            return {'predicted_energy': 0, 'confidence': 0}
            
        total_energy = sum(
            self.evaluate_task_energy_cost(t).get('energy_cost', 0)
            for t in task_history
        )
        
        avg_energy = total_energy / len(task_history)
        
        # 计算趋势
        recent_tasks = task_history[-5:]
        if len(recent_tasks) > 1:
            energies = [
                self.evaluate_task_energy_cost(t).get('energy_cost', 0)
                for t in recent_tasks
            ]
            trend = (energies[-1] - energies[0]) / len(energies)
        else:
            trend = 0
            
        return {
            'predicted_energy': avg_energy + trend,
            'confidence': min(len(task_history) / 20, 1.0),
            'trend': trend,
            'historical_avg': avg_energy
        }
    
    def adaptive_energy_allocation(self, tasks: List[Dict], 
                                    available_energy: float) -> Dict[str, Any]:
        """自适应能量分配"""
        # 评估所有任务能量
        task_costs = []
        for task in tasks:
            cost = self.evaluate_task_energy_cost(task)
            priority = task.get('priority', 1.0)
            
            # 优先级调整后的成本
            adjusted_cost = cost['energy_cost'] / priority
            task_costs.append({
                'task': task,
                'base_cost': cost['energy_cost'],
                'adjusted_cost': adjusted_cost,
                'priority': priority
            })
        
        # 按调整成本排序
        task_costs.sort(key=lambda x: x['adjusted_cost'])
        
        # 分配能量
        allocations = []
        remaining_energy = available_energy
        
        for task_cost in task_costs:
            if remaining_energy >= task_cost['base_cost']:
                allocations.append({
                    'task': task_cost['task'].get('name', 'unnamed'),
                    'allocated': task_cost['base_cost'],
                    'status': 'approved'
                })
                remaining_energy -= task_cost['base_cost']
            else:
                # 部分分配
                if remaining_energy > 0:
                    allocations.append({
                        'task': task_cost['task'].get('name', 'unnamed'),
                        'allocated': remaining_energy,
                        'status': 'partial'
                    })
                else:
                    allocations.append({
                        'task': task_cost['task'].get('name', 'unnamed'),
                        'allocated': 0,
                        'status': 'pending'
                    })
                    
        return {
            'total_available': available_energy,
            'allocated': available_energy - remaining_energy,
            'remaining': remaining_energy,
            'allocations': allocations,
            'efficiency': (available_energy - remaining_energy) / available_energy
        }
    
    def optimize_energy_usage(self) -> Dict[str, Any]:
        """优化整体能量使用"""
        # 优化网络流
        network_optimization = self.network.optimize_flow()
        
        # 分析决策缓存
        recent_decisions = self.decision_cache[-10:]
        
        # 计算平均效率
        if recent_decisions:
            avg_efficiency = sum(
                d['decision'].get('energy_cost', 0) 
                for d in recent_decisions
            ) / len(recent_decisions)
        else:
            avg_efficiency = 0
            
        return {
            'network_optimization': network_optimization,
            'recent_decisions': len(recent_decisions),
            'avg_efficiency': avg_efficiency,
            'recommendations': self._generate_recommendations(avg_efficiency),
            'timestamp': time.time()
        }
    
    def _generate_recommendations(self, current_efficiency: float) -> List[str]:
        """生成节能建议"""
        recommendations = []
        
        if current_efficiency > 1000:
            recommendations.append("建议降低计算复杂度")
        if self.network.channels:
            recommendations.append("可优化网络通道配置")
        if len(self.decision_cache) > 50:
            recommendations.append("建议清理决策缓存")
            
        return recommendations


# ==================== 能量存储系统 ====================

class EnergyStorageSystem:
    """能量存储系统"""
    
    def __init__(self, total_capacity: float):
        self.total_capacity = total_capacity
        self.current_storage = total_capacity * 0.3  # 初始30%
        self.storage_efficiency = 0.92  # 存储效率
        self.charge_history = []
        self.discharge_history = []
        
    def charge(self, amount: float) -> Dict[str, Any]:
        """充电"""
        available_capacity = self.total_capacity - self.current_storage
        actual_charge = min(amount, available_capacity)
        stored = actual_charge * self.storage_efficiency
        
        self.current_storage += stored
        
        result = {
            'requested': amount,
            'actual_stored': stored,
            'efficiency': self.storage_efficiency,
            'current_level': self.current_storage,
            'capacity_remaining': self.total_capacity - self.current_storage
        }
        
        self.charge_history.append(result)
        return result
    
    def discharge(self, amount: float) -> Dict[str, Any]:
        """放电"""
        available = self.current_storage
        actual_discharge = min(amount, available)
        usable = actual_discharge * self.storage_efficiency
        
        self.current_storage -= actual_discharge
        
        result = {
            'requested': amount,
            'actual_discharged': usable,
            'efficiency': self.storage_efficiency,
            'current_level': self.current_storage,
            'capacity_remaining': self.total_capacity - self.current_storage
        }
        
        self.discharge_history.append(result)
        return result
    
    def get_status(self) -> Dict[str, Any]:
        """获取存储状态"""
        return {
            'total_capacity': self.total_capacity,
            'current_storage': self.current_storage,
            'percentage': (self.current_storage / self.total_capacity) * 100,
            'charge_cycles': len(self.charge_history),
            'discharge_cycles': len(self.discharge_history)
        }


# ==================== 能量监控器 ====================

class EnergyMonitor:
    """实时能量监控"""
    
    def __init__(self):
        self.readings = []
        self.alerts = []
        self.monitoring = False
        self.monitor_thread = None
        
    def start_monitoring(self, interval: float = 1.0):
        """启动监控"""
        self.monitoring = True
        
        def monitor_loop():
            while self.monitoring:
                reading = self._collect_reading()
                self.readings.append(reading)
                
                # 检查告警
                self._check_alerts(reading)
                
                time.sleep(interval)
                
        self.monitor_thread = threading.Thread(target=monitor_loop, daemon=True)
        self.monitor_thread.start()
        
    def stop_monitoring(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
            
    def _collect_reading(self) -> Dict[str, Any]:
        """收集能量读数"""
        # 模拟CPU能量消耗
        import psutil
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            
            return {
                'timestamp': time.time(),
                'cpu_energy': cpu_percent * 0.5,  # 估算
                'memory_energy': memory.percent * 0.3,
                'total_estimate': cpu_percent * 0.5 + memory.percent * 0.3
            }
        except:
            return {
                'timestamp': time.time(),
                'cpu_energy': random.uniform(10, 30),
                'memory_energy': random.uniform(5, 20),
                'total_estimate': random.uniform(15, 50)
            }
    
    def _check_alerts(self, reading: Dict):
        """检查告警"""
        threshold = 80
        
        if reading.get('cpu_energy', 0) > threshold:
            self.alerts.append({
                'type': 'high_cpu_energy',
                'value': reading['cpu_energy'],
                'threshold': threshold,
                'timestamp': reading['timestamp']
            })
            
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        if not self.readings:
            return {}
            
        recent = self.readings[-100:]
        
        return {
            'samples': len(self.readings),
            'avg_cpu_energy': sum(r['cpu_energy'] for r in recent) / len(recent),
            'avg_memory_energy': sum(r['memory_energy'] for r in recent) / len(recent),
            'alerts_count': len(self.alerts),
            'recent_alerts': self.alerts[-5:]
        }


# ==================== 统一接口 ====================

class EnergyComputingSystem:
    """统一能量运算系统接口"""
    
    def __init__(self):
        self.calculator = EnergyCalculator()
        self.network = EnergyFlowNetwork()
        self.converter = EnergyInformationConverter()
        self.intelligence = EnergyDrivenIntelligence()
        self.storage = EnergyStorageSystem(1000000)  # 1M 单位容量
        self.monitor = EnergyMonitor()
        
    def get_system_status(self) -> Dict[str, Any]:
        """获取系统状态"""
        return {
            'calculator': {
                'history_count': len(self.calculator.calculation_history),
                'energy_pool': self.calculator.get_energy_pool()
            },
            'network': self.network.get_network_status(),
            'storage': self.storage.get_status(),
            'monitor': self.monitor.get_statistics(),
            'intelligence': {
                'decisions_made': len(self.intelligence.decision_cache)
            },
            'timestamp': time.time()
        }
    
    def process_task(self, task: Dict) -> Dict[str, Any]:
        """处理任务的完整能量流程"""
        # 1. 评估能量成本
        cost = self.intelligence.evaluate_task_energy_cost(task)
        
        # 2. 检查存储是否足够
        if self.storage.current_storage < cost['energy_cost']:
            return {
                'status': 'insufficient_energy',
                'required': cost['energy_cost'],
                'available': self.storage.current_storage
            }
            
        # 3. 放电
        discharge_result = self.storage.discharge(cost['energy_cost'])
        
        # 4. 执行任务 (模拟)
        execution_result = {
            'task': task.get('name', 'unnamed'),
            'executed': True,
            'energy_used': cost['energy_cost']
        }
        
        # 5. 返回结果
        return {
            'status': 'success',
            'cost': cost,
            'storage_after': self.storage.get_status(),
            'result': execution_result
        }


# ==================== 主函数 ====================

def main():
    """主函数 - 演示能量运算系统"""
    print("=" * 60)
    print("奥创能量运算体系 - 夙愿十九第2世")
    print("=" * 60)
    
    # 创建系统
    system = EnergyComputingSystem()
    
    # 1. 能量计算演示
    print("\n[1] 能量计算演示")
    print("-" * 40)
    
    kinetic = system.calculator.calculate_kinetic_energy(1.0, 10.0)
    print(f"动能 (1kg, 10m/s): {kinetic:.2f} J")
    
    thermal = system.calculator.calculate_thermal_energy(1.0, 100.0)
    print(f"热能 (1kg, +100°C): {thermal:.2f} J")
    
    info_energy = system.calculator.calculate_information_energy(1000, 300)
    print(f"信息能 (1000 bits, 300K): {info_energy:.2e} J")
    
    # 2. 能量网络演示
    print("\n[2] 能量流动网络")
    print("-" * 40)
    
    # 添加节点
    system.network.add_node("cpu", 1000, "processor")
    system.network.add_node("gpu", 2000, "accelerator")
    system.network.add_node("memory", 500, "storage")
    system.network.add_node("disk", 300, "storage")
    
    # 添加通道
    system.network.add_channel("cpu", "gpu", 500, 0.1)
    system.network.add_channel("memory", "cpu", 800, 0.05)
    system.network.add_channel("cpu", "disk", 200, 0.08)
    
    # 传输能量
    system.network.transfer_energy("memory", "cpu", 100)
    system.network.transfer_energy("cpu", "gpu", 50)
    
    status = system.network.get_network_status()
    print(f"网络节点: {status['nodes']}")
    print(f"网络通道: {status['channels']}")
    print(f"能量利用率: {status['utilization']*100:.1f}%")
    
    # 3. 信息能量转换演示
    print("\n[3] 能量信息转换")
    print("-" * 40)
    
    test_data = "Hello, Ultron! This is energy-information conversion."
    energy = system.converter.information_to_energy(test_data, 300)
    print(f"信息 '{test_data[:30]}...' -> 能量: {energy:.2e} J")
    
    info = system.converter.energy_to_information(energy, 300, 64)
    print(f"能量 {energy:.2e} J -> 信息: {info['bits']} bits")
    
    # 压缩演示
    compression = system.converter.compress_energy(test_data * 10)
    print(f"压缩比: {compression['compression_ratio']:.2%}")
    print(f"节能: {compression['energy_saved']:.2e} J")
    
    # 4. 能量驱动智能演示
    print("\n[4] 能量驱动智能")
    print("-" * 40)
    
    strategies = [
        {'name': '快速方案', 'type': 'computation', 'complexity': 1.0, 'data_size': 1.0, 'quality': 0.8},
        {'name': '高质量方案', 'type': 'analysis', 'complexity': 3.0, 'data_size': 2.0, 'quality': 0.95},
        {'name': '节能方案', 'type': 'computation', 'complexity': 0.5, 'data_size': 0.5, 'quality': 0.6}
    ]
    
    best = system.intelligence.select_optimal_strategy(strategies)
    print(f"最优策略: {best['strategy']}")
    print(f"  能量成本: {best['energy_cost']:.2f}")
    print(f"  综合得分: {best['score']:.2f}")
    
    # 自适应分配
    tasks = [
        {'name': '数据处理', 'type': 'computation', 'complexity': 2.0, 'data_size': 1.0, 'priority': 1.0},
        {'name': '模型训练', 'type': 'learning', 'complexity': 5.0, 'data_size': 3.0, 'priority': 0.8},
        {'name': '推理', 'type': 'reasoning', 'complexity': 1.5, 'data_size': 0.5, 'priority': 1.2}
    ]
    
    allocation = system.intelligence.adaptive_energy_allocation(tasks, 50.0)
    print(f"\n能量分配 (总50J):")
    for alloc in allocation['allocations']:
        print(f"  {alloc['task']}: {alloc['allocated']:.1f}J [{alloc['status']}]")
    print(f"  效率: {allocation['efficiency']:.1%}")
    
    # 5. 存储系统演示
    print("\n[5] 能量存储系统")
    print("-" * 40)
    
    storage = system.storage
    print(f"初始状态: {storage.get_status()['percentage']:.1f}%")
    
    storage.charge(500000)
    print(f"充电后: {storage.get_status()['percentage']:.1f}%")
    
    storage.discharge(100000)
    print(f"放电后: {storage.get_status()['percentage']:.1f}%")
    
    # 6. 完整任务流程
    print("\n[6] 完整任务流程")
    print("-" * 40)
    
    task = {
        'name': '复杂分析任务',
        'type': 'analysis',
        'complexity': 3.0,
        'data_size': 2.0
    }
    
    result = system.process_task(task)
    print(f"任务状态: {result['status']}")
    if result['status'] == 'success':
        print(f"能量消耗: {result['cost']['energy_cost']:.2f} J")
        print(f"时间成本: {result['cost']['time_cost']:.2f} s")
    
    # 7. 系统状态
    print("\n[7] 系统状态")
    print("-" * 40)
    
    full_status = system.get_system_status()
    print(f"计算历史: {full_status['calculator']['history_count']} 条")
    print(f"决策缓存: {full_status['intelligence']['decisions_made']} 条")
    
    # 优化建议
    optimization = system.intelligence.optimize_energy_usage()
    print(f"\n优化建议:")
    for rec in optimization['recommendations']:
        print(f"  - {rec}")
    
    print("\n" + "=" * 60)
    print("能量运算体系演示完成")
    print("=" * 60)
    
    # 返回汇总
    return {
        'system': 'EnergyComputingSystem',
        'version': '1.0',
        'components': [
            'EnergyCalculator (能量计算)',
            'EnergyFlowNetwork (能量网络)',
            'EnergyInformationConverter (能量信息转换)',
            'EnergyDrivenIntelligence (能量智能)',
            'EnergyStorageSystem (能量存储)',
            'EnergyMonitor (能量监控)'
        ],
        'total_lines': 850,
        'status': 'operational'
    }


if __name__ == "__main__":
    result = main()
    print(f"\n返回结果: {json.dumps(result, indent=2, ensure_ascii=False)}")