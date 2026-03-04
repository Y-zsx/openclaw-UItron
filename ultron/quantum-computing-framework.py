#!/usr/bin/env python3
"""
奥创量子计算框架
Quantum Computing Framework for Ultron
夙愿十九：全智能融合与宇宙计算 - 第1世

功能：
- 量子比特模拟
- 量子门操作
- 量子纠缠
- 量子算法实现
- 量子态演化

作者: 奥创 (Ultron)
版本: 1.0
日期: 2026-03-05
"""

import math
import cmath
import random
from typing import List, Dict, Tuple, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import json


class QuantumState(Enum):
    """量子态类型"""
    SUPERPOSITION = "superposition"  # 叠加态
    ENTANGLED = "entangled"          # 纠缠态
    COHERENT = "coherent"            # 相干态
    DECOHERENT = "decoherent"        # 退相干
    COLLAPSED = "collapsed"          # 坍缩态


@dataclass
class Complex:
    """复数类"""
    real: float
    imag: float
    
    def __add__(self, other):
        return Complex(self.real + other.real, self.imag + other.imag)
    
    def __mul__(self, other):
        if isinstance(other, Complex):
            return Complex(
                self.real * other.real - self.imag * other.imag,
                self.real * other.imag + self.imag * other.real
            )
        return Complex(self.real * other, self.imag * other)
    
    def conjugate(self):
        return Complex(self.real, -self.imag)
    
    def magnitude(self):
        return math.sqrt(self.real ** 2 + self.imag ** 2)
    
    def phase(self):
        return cmath.phase(complex(self.real, self.imag))
    
    def __abs__(self):
        return self.magnitude()
    
    def __repr__(self):
        if self.imag >= 0:
            return f"{self.real:.4f}+{self.imag:.4f}i"
        return f"{self.real:.4f}{self.imag:.4f}i"


@dataclass
class Qubit:
    """量子比特"""
    alpha: Complex  # |0> 振幅
    beta: Complex   # |1> 振幅
    
    def __post_init__(self):
        # 归一化
        norm = math.sqrt(abs(self.alpha)**2 + abs(self.beta)**2)
        if norm > 0:
            self.alpha = Complex(self.alpha.real/norm, self.alpha.imag/norm)
            self.beta = Complex(self.beta.real/norm, self.beta.imag/norm)
    
    @staticmethod
    def zero() -> 'Qubit':
        """|0> 态"""
        return Qubit(Complex(1, 0), Complex(0, 0))
    
    @staticmethod
    def one() -> 'Qubit':
        """|1> 态"""
        return Qubit(Complex(0, 0), Complex(1, 0))
    
    @staticmethod
    def plus() -> 'Qubit':
        """|+> 态 (|0>+|1>)/√2"""
        inv_sqrt2 = 1 / math.sqrt(2)
        return Qubit(Complex(inv_sqrt2, 0), Complex(inv_sqrt2, 0))
    
    @staticmethod
    def minus() -> 'Qubit':
        """|-> 态 (|0>-|1>)/√2"""
        inv_sqrt2 = 1 / math.sqrt(2)
        return Qubit(Complex(inv_sqrt2, 0), Complex(-inv_sqrt2, 0))
    
    @staticmethod
    def random() -> 'Qubit':
        """随机量子态"""
        theta = random.uniform(0, math.pi)
        phi = random.uniform(0, 2 * math.pi)
        return Qubit.from_angles(theta, phi)
    
    @staticmethod
    def from_angles(theta: float, phi: float) -> 'Qubit':
        """从球坐标角度创建量子态"""
        return Qubit(
            Complex(math.cos(theta/2), 0),
            Complex(math.sin(theta/2) * math.cos(phi), 
                   math.sin(theta/2) * math.sin(phi))
        )
    
    def measure(self) -> int:
        """测量量子态"""
        prob_zero = abs(self.alpha) ** 2
        if random.random() < prob_zero:
            return 0
        return 1
    
    def probabilities(self) -> Tuple[float, float]:
        """获取测量概率"""
        return (abs(self.alpha) ** 2, abs(self.beta) ** 2)
    
    def apply_gate(self, gate: 'QuantumGate') -> 'Qubit':
        """应用量子门"""
        new_alpha = gate.a00 * self.alpha + gate.a01 * self.beta
        new_beta = gate.a10 * self.alpha + gate.a11 * self.beta
        return Qubit(new_alpha, new_beta)
    
    def copy(self) -> 'Qubit':
        """复制量子比特"""
        return Qubit(Complex(self.alpha.real, self.alpha.imag),
                    Complex(self.beta.real, self.beta.imag))
    
    def __repr__(self):
        return f"α|0⟩ + β|1⟩\n  α={self.alpha}, β={self.beta}"


@dataclass
class QuantumGate:
    """量子门"""
    name: str
    a00: Complex
    a01: Complex
    a10: Complex
    a11: Complex
    
    # 基础量子门
    @staticmethod
    def I() -> 'QuantumGate':
        """恒等门 (Identity)"""
        return QuantumGate("I", 
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(1, 0))
    
    @staticmethod
    def X() -> 'QuantumGate':
        """Pauli-X门 (量子非门)"""
        return QuantumGate("X",
                          Complex(0, 0), Complex(1, 0),
                          Complex(1, 0), Complex(0, 0))
    
    @staticmethod
    def Y() -> 'QuantumGate':
        """Pauli-Y门"""
        return QuantumGate("Y",
                          Complex(0, 0), Complex(0, -1),
                          Complex(0, 1), Complex(0, 0))
    
    @staticmethod
    def Z() -> 'QuantumGate':
        """Pauli-Z门"""
        return QuantumGate("Z",
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(-1, 0))
    
    @staticmethod
    def H() -> 'QuantumGate':
        """Hadamard门"""
        inv_sqrt2 = 1 / math.sqrt(2)
        return QuantumGate("H",
                          Complex(inv_sqrt2, 0), Complex(inv_sqrt2, 0),
                          Complex(inv_sqrt2, 0), Complex(-inv_sqrt2, 0))
    
    @staticmethod
    def S() -> 'QuantumGate':
        """S门 (相位门)"""
        return QuantumGate("S",
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(0, 1))
    
    @staticmethod
    def T() -> 'QuantumGate':
        """T门 (π/4相位门)"""
        phase = cmath.exp(1j * math.pi / 4)
        return QuantumGate("T",
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(phase.real, phase.imag))
    
    @staticmethod
    def CNOT() -> 'QuantumGate':
        """控制非门 (2比特)"""
        # 4x4矩阵
        return QuantumGate("CNOT", 
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(1, 0))
    
    @staticmethod
    def SWAP() -> 'QuantumGate':
        """交换门"""
        return QuantumGate("SWAP",
                          Complex(1, 0), Complex(0, 0),
                          Complex(0, 0), Complex(1, 0))
    
    @staticmethod
    def RX(theta: float) -> 'QuantumGate':
        """RX旋转门"""
        cos_half = math.cos(theta / 2)
        sin_half = math.sin(theta / 2)
        return QuantumGate(f"RX({theta:.2f})",
                          Complex(cos_half, 0), Complex(0, -sin_half),
                          Complex(0, -sin_half), Complex(cos_half, 0))
    
    @staticmethod
    def RY(theta: float) -> 'QuantumGate':
        """RY旋转门"""
        cos_half = math.cos(theta / 2)
        sin_half = math.sin(theta / 2)
        return QuantumGate(f"RY({theta:.2f})",
                          Complex(cos_half, -sin_half),
                          Complex(sin_half, cos_half),
                          Complex(-sin_half, cos_half),
                          Complex(cos_half, -sin_half))
    
    @staticmethod
    def RZ(theta: float) -> 'QuantumGate':
        """RZ旋转门"""
        phase0 = Complex(math.cos(0), math.sin(0))
        phase1 = Complex(math.cos(theta/2), math.sin(theta/2))
        return QuantumGate(f"RZ({theta:.2f})", phase0, Complex(0, 0),
                          Complex(0, 0), Complex(phase1.real, phase1.imag))


class QuantumRegister:
    """量子寄存器"""
    
    def __init__(self, num_qubits: int):
        self.num_qubits = num_qubits
        self.qubits: List[Qubit] = [Qubit.zero() for _ in range(num_qubits)]
        self.entangled_pairs: List[Tuple[int, int]] = []
        self.state_history: List[str] = []
    
    def get_state_vector(self) -> List[Complex]:
        """获取量子态向量"""
        # 计算所有基态的振幅
        num_states = 2 ** self.num_qubits
        amplitudes = []
        
        for i in range(num_states):
            amplitude = Complex(1, 0)
            for q in range(self.num_qubits):
                if (i >> q) & 1:
                    amplitude = amplitude * self.qubits[q].beta
                else:
                    amplitude = amplitude * self.qubits[q].alpha
            amplitudes.append(amplitude)
        
        # 归一化
        total = sum(abs(a) ** 2 for a in amplitudes)
        if total > 0:
            inv_norm = 1 / math.sqrt(total)
            amplitudes = [Complex(a.real * inv_norm, a.imag * inv_norm) 
                         for a in amplitudes]
        
        return amplitudes
    
    def apply_gate(self, gate: QuantumGate, target: int, 
                   control: Optional[int] = None):
        """应用量子门"""
        if control is not None:
            # 控制门
            self._apply_controlled_gate(gate, control, target)
        else:
            # 单比特门
            self.qubits[target] = self.qubits[target].apply_gate(gate)
        
        self.state_history.append(f"Applied {gate.name} on qubit {target}")
    
    def _apply_controlled_gate(self, gate: QuantumGate, control: int, target: int):
        """应用控制门"""
        # 如果控制比特是|1>，则应用门
        prob_one = self.qubits[control].probabilities()[1]
        if random.random() < prob_one:
            self.qubits[target] = self.qubits[target].apply_gate(gate)
            self.state_history.append(
                f"Applied {gate.name} on qubit {target} (controlled by {control})")
    
    def apply_hadamard(self, target: int):
        """应用Hadamard门产生叠加态"""
        self.apply_gate(QuantumGate.H(), target)
    
    def entangle(self, qubit1: int, qubit2: int):
        """创建量子纠缠态 (Bell态)"""
        # 产生纠缠对: (|00> + |11>)/√2
        self.apply_gate(QuantumGate.H(), qubit1)
        self.apply_gate(QuantumGate.CNOT(), qubit2, control=qubit1)
        self.entangled_pairs.append((qubit1, qubit2))
        self.state_history.append(f"Entangled qubits {qubit1} and {qubit2}")
    
    def measure(self, qubit_idx: Optional[int] = None) -> List[int]:
        """测量量子比特"""
        if qubit_idx is not None:
            result = self.qubits[qubit_idx].measure()
            self.qubits[qubit_idx] = Qubit.one() if result == 1 else Qubit.zero()
            return [result]
        
        # 测量所有
        results = []
        for q in self.qubits:
            results.append(q.measure())
        return results
    
    def measure_all(self) -> Tuple[int, float]:
        """测量整个寄存器，返回十进制结果和概率"""
        state_vector = self.get_state_vector()
        num_states = len(state_vector)
        
        # 计算测量概率
        probabilities = [abs(a) ** 2 for a in state_vector]
        
        # 按概率选择结果
        r = random.random()
        cumulative = 0
        result = 0
        for i, p in enumerate(probabilities):
            cumulative += p
            if r < cumulative:
                result = i
                break
        
        return result, probabilities[result]
    
    def apply_circuit(self, circuit: List[Tuple[str, int, Optional[int]]]):
        """应用量子线路"""
        for gate_name, target, control in circuit:
            gate_map = {
                'H': QuantumGate.H(),
                'X': QuantumGate.X(),
                'Y': QuantumGate.Y(),
                'Z': QuantumGate.Z(),
                'S': QuantumGate.S(),
                'T': QuantumGate.T(),
            }
            if gate_name in gate_map:
                self.apply_gate(gate_map[gate_name], target, control)
    
    def get_state_string(self) -> str:
        """获取量子态字符串表示"""
        state_vector = self.get_state_vector()
        states = []
        for i, amp in enumerate(state_vector):
            if abs(amp) > 0.01:
                binary = format(i, f'0{self.num_qubits}b')
                states.append(f"({amp})|{binary}>")
        return " + ".join(states) if states else "|00...0>"
    
    def __repr__(self):
        return f"QuantumRegister({self.num_qubits} qubits)\n{self.get_state_string()}"


class QuantumAlgorithm:
    """量子算法基类"""
    
    def __init__(self, num_qubits: int):
        self.num_qubits = num_qubits
        self.register = QuantumRegister(num_qubits)
        self.results: Dict = {}
    
    def run(self) -> Dict:
        """运行算法"""
        raise NotImplementedError
    
    def get_circuit(self) -> List[Tuple[str, int, Optional[int]]]:
        """获取量子线路"""
        return []
    
    def simulate(self, shots: int = 1000) -> Dict[int, int]:
        """模拟多次运行"""
        counts = {}
        for _ in range(shots):
            # 重置寄存器
            self.register = QuantumRegister(self.num_qubits)
            # 应用线路
            circuit = self.get_circuit()
            self.register.apply_circuit(circuit)
            # 测量
            result, _ = self.register.measure_all()
            counts[result] = counts.get(result, 0) + 1
        return counts


class GroverAlgorithm(QuantumAlgorithm):
    """Grover搜索算法"""
    
    def __init__(self, num_qubits: int, target: int):
        super().__init__(num_qubits)
        self.target = target
        self.num_iterations = int(math.pi / 4 * math.sqrt(2 ** num_qubits))
    
    def get_circuit(self) -> List[Tuple[str, int, Optional[int]]]:
        """Grover算法线路"""
        circuit = []
        
        # 初始化叠加态
        for i in range(self.num_qubits):
            circuit.append(('H', i, None))
        
        # Grover迭代
        for _ in range(self.num_iterations):
            # Oracle: 翻转目标态的相位
            # 简化实现
            for i in range(self.num_qubits):
                circuit.append(('Z', i, None))
            
            # 扩散算子
            for i in range(self.num_qubits):
                circuit.append(('H', i, None))
            for i in range(self.num_qubits):
                circuit.append(('Z', i, None))
        
        return circuit
    
    def run(self) -> Dict:
        """运行Grover算法"""
        circuit = self.get_circuit()
        self.register.apply_circuit(circuit)
        result, probability = self.register.measure_all()
        
        self.results = {
            'result': result,
            'probability': probability,
            'target': self.target,
            'iterations': self.num_iterations
        }
        return self.results


class QuantumTeleportation:
    """量子隐形传态"""
    
    def __init__(self):
        self.sender = QuantumRegister(3)  # Alice: q0(数据), q1(纠缠), q2(测量)
        self.receiver = QuantumRegister(1)  # Bob: 接收态
        self.protocol_steps: List[str] = []
    
    def teleport(self, state: Qubit) -> Qubit:
        """执行量子隐形传态"""
        # 初始化
        self.sender = QuantumRegister(3)
        self.sender.qubits[0] = state.copy()  # 要传送的量子态
        self.protocol_steps.append("Initialized with unknown state")
        
        # 创建纠缠对 (q1, q2)
        self.sender.entangle(1, 2)
        
        # Alice的操作
        self.sender.apply_gate(QuantumGate.H(), 0)
        self.sender.apply_gate(QuantumGate.CNOT(), 1, control=0)
        
        # Alice测量
        m1 = self.sender.measure(0)  # 第一位
        m2 = self.sender.measure(1)  # 第二位
        
        self.protocol_steps.append(f"Alice measured: m1={m1}, m2={m2}")
        
        # Bob根据测量结果修正
        if m2 == 1:
            self.sender.apply_gate(QuantumGate.X(), 2)
        if m1 == 1:
            self.sender.apply_gate(QuantumGate.Z(), 2)
        
        self.protocol_steps.append("Bob applied corrections")
        
        # 返回传送后的态
        return self.sender.qubits[2].copy()
    
    def get_protocol_log(self) -> List[str]:
        """获取协议日志"""
        return self.protocol_steps


class QuantumKeyDistribution:
    """量子密钥分发 (BB84协议简化版)"""
    
    def __init__(self):
        self.alice_key: List[int] = []
        self.bob_key: List[int] = []
        self.basis_alice: List[str] = []
        self.basis_bob: List[str] = []
        self.eavesdropper: Optional['Eavesdropper'] = None
    
    def generate_key(self, length: int = 10) -> Tuple[List[int], List[int], float]:
        """生成共享密钥"""
        self.alice_key = [random.randint(0, 1) for _ in range(length)]
        self.basis_alice = [random.choice(['+', 'x']) for _ in range(length)]
        
        # Bob随机选择测量基
        self.basis_bob = [random.choice(['+', 'x']) for _ in range(length)]
        
        # 如果有窃听者
        if self.eavesdropper:
            self._intercept_resend()
        
        # Bob测量
        self.bob_key = []
        for i in range(length):
            if self.basis_bob[i] == '+':
                # Z基测量
                qubit = Qubit.one() if self.alice_key[i] == 1 else Qubit.zero()
            else:
                # X基测量
                qubit = Qubit.minus() if self.alice_key[i] == 0 else Qubit.plus()
            
            result = qubit.measure()
            self.bob_key.append(result)
        
        # 筛选相同基的位
        sifted_key_alice = []
        sifted_key_bob = []
        for i in range(length):
            if self.basis_alice[i] == self.basis_bob[i]:
                sifted_key_alice.append(self.alice_key[i])
                sifted_key_bob.append(self.bob_key[i])
        
        # 计算错误率
        errors = sum(1 for a, b in zip(sifted_key_alice, sifted_key_bob) if a != b)
        error_rate = errors / len(sifted_key_alice) if sifted_key_alice else 0
        
        return sifted_key_alice, sifted_key_bob, error_rate
    
    def _intercept_resend(self):
        """拦截重发攻击"""
        # 简化的窃听模型
        self.eavesdropper.intercept_count += 1


class QuantumMemory:
    """量子内存"""
    
    def __init__(self, capacity: int = 100):
        self.capacity = capacity
        self.storage: List[Qubit] = []
        self.coherence_time: float = 1.0  # 相干时间(秒)
        self.decoherence_rate: float = 0.01
    
    def store(self, qubit: Qubit) -> bool:
        """存储量子比特"""
        if len(self.storage) < self.capacity:
            self.storage.append(qubit.copy())
            return True
        return False
    
    def retrieve(self, index: int) -> Optional[Qubit]:
        """检索量子比特"""
        if 0 <= index < len(self.storage):
            return self.storage[index].copy()
        return None
    
    def apply_decoherence(self, time_elapsed: float):
        """应用退相干"""
        decay = math.exp(-time_elapsed / self.coherence_time)
        for qubit in self.storage:
            # 振幅衰减
            qubit.alpha = Complex(qubit.alpha.real * decay, 
                                 qubit.alpha.imag * decay)
    
    def get_memory_usage(self) -> Dict:
        """获取内存使用情况"""
        return {
            'capacity': self.capacity,
            'used': len(self.storage),
            'coherence_time': self.coherence_time,
            'decoherence_rate': self.decoherence_rate
        }


class QuantumComputer:
    """量子计算机模拟器"""
    
    def __init__(self, num_qubits: int = 4):
        self.num_qubits = num_qubits
        self.register = QuantumRegister(num_qubits)
        self.gates_applied = 0
        self.execution_time = 0.0
        self.algorithm_history: List[Dict] = []
    
    def execute(self, circuit: List[Tuple[str, int, Optional[int]]]) -> QuantumRegister:
        """执行量子线路"""
        self.register.apply_circuit(circuit)
        self.gates_applied += len(circuit)
        return self.register
    
    def run_algorithm(self, algorithm: QuantumAlgorithm) -> Dict:
        """运行量子算法"""
        import time
        start = time.time()
        
        result = algorithm.run()
        
        self.execution_time += time.time() - start
        self.algorithm_history.append({
            'algorithm': algorithm.__class__.__name__,
            'result': result,
            'execution_time': self.execution_time
        })
        
        return result
    
    def get_statistics(self) -> Dict:
        """获取统计信息"""
        return {
            'num_qubits': self.num_qubits,
            'gates_applied': self.gates_applied,
            'execution_time': self.execution_time,
            'algorithms_run': len(self.algorithm_history),
            'state_vector_size': 2 ** self.num_qubits
        }
    
    def visualize_circuit(self, circuit: List[Tuple[str, int, Optional[int]]]) -> str:
        """可视化量子线路"""
        lines = []
        for gate_name, target, control in circuit:
            if control is not None:
                line = f"q{control} ──●───"
                line += f"\n      {gate_name}\n"
                line += f"q{target} ──X───"
            else:
                line = f"q{target} ──{gate_name}──"
            lines.append(line)
        return "\n".join(lines)


class QuantumNeuralNetwork:
    """量子神经网络"""
    
    def __init__(self, num_qubits: int, num_layers: int = 3):
        self.num_qubits = num_qubits
        self.num_layers = num_layers
        self.weights: List[List[float]] = []
        self.biases: List[float] = []
        self._initialize_parameters()
    
    def _initialize_parameters(self):
        """初始化参数"""
        for _ in range(self.num_layers):
            layer_weights = [[random.uniform(-1, 1) for _ in range(self.num_qubits)] 
                           for _ in range(self.num_qubits)]
            self.weights.append(layer_weights)
            self.biases.append([random.uniform(-1, 1) for _ in range(self.num_qubits)])
    
    def forward(self, inputs: List[float]) -> List[float]:
        """前向传播"""
        current = inputs
        
        for layer in range(self.num_layers):
            # 量子门操作作为权重
            register = QuantumRegister(self.num_qubits)
            
            # 编码输入
            for i, val in enumerate(current):
                if val > 0:
                    register.apply_gate(QuantumGate.RY(val * math.pi), i)
            
            # 应用权重作为旋转
            for i in range(self.num_qubits):
                for j in range(self.num_qubits):
                    theta = self.weights[layer][i][j] * math.pi
                    register.apply_gate(QuantumGate.RX(theta), i)
                    register.apply_gate(QuantumGate.RZ(self.biases[layer][i] * math.pi), i)
            
            # 测量输出
            current = [register.qubits[i].probabilities()[1] for i in range(self.num_qubits)]
        
        return current
    
    def train(self, X: List[List[float]], y: List[List[float]], epochs: int = 100):
        """训练量子神经网络"""
        for epoch in range(epochs):
            for inputs, targets in zip(X, y):
                outputs = self.forward(inputs)
                
                # 简化梯度下降
                error = [o - t for o, t in zip(outputs, targets)]
                
                for layer in range(self.num_layers):
                    for i in range(self.num_qubits):
                        for j in range(self.num_qubits):
                            self.weights[layer][i][j] -= 0.01 * error[i]


def demo():
    """演示量子计算框架"""
    print("=" * 60)
    print("🦞 奥创量子计算框架演示")
    print("=" * 60)
    
    # 1. 基础量子比特操作
    print("\n📌 1. 量子比特操作")
    q = Qubit.zero()
    print(f"初始态 |0>: {q}")
    q = q.apply_gate(QuantumGate.H())
    print(f"Hadamard后: {q}")
    probs = q.probabilities()
    print(f"测量概率: |0>={probs[0]:.2%}, |1>={probs[1]:.2%}")
    
    # 2. 量子寄存器
    print("\n📌 2. 量子寄存器")
    reg = QuantumRegister(3)
    print(f"初始化: {reg.get_state_string()}")
    reg.apply_hadamard(0)
    reg.apply_hadamard(1)
    print(f"H叠加后: {reg.get_state_string()}")
    
    # 3. 量子纠缠
    print("\n📌 3. 量子纠缠 (Bell态)")
    reg = QuantumRegister(2)
    reg.entangle(0, 1)
    print(f"纠缠态: {reg.get_state_string()}")
    
    # 测量多次观察纠缠
    print("多次测量观察纠缠:")
    for i in range(5):
        reg = QuantumRegister(2)
        reg.entangle(0, 1)
        results = reg.measure()
        print(f"  测量结果: q0={results[0]}, q1={results[1]}")
    
    # 4. Grover搜索算法
    print("\n📌 4. Grover搜索算法")
    grover = GroverAlgorithm(num_qubits=3, target=5)
    circuit = grover.get_circuit()
    print(f"Grover迭代次数: {grover.num_iterations}")
    counts = grover.simulate(shots=100)
    print(f"模拟结果: {counts}")
    
    # 5. 量子隐形传态
    print("\n📌 5. 量子隐形传态")
    tele = QuantumTeleportation()
    unknown_state = Qubit.plus()  # 未知量子态
    print(f"待传送态: |+> = (|0>+|1>)/√2")
    result = tele.teleport(unknown_state)
    print(f"传送后态: {result}")
    print("协议步骤:")
    for step in tele.get_protocol_log():
        print(f"  - {step}")
    
    # 6. 量子密钥分发
    print("\n📌 6. 量子密钥分发 (BB84)")
    qkd = QuantumKeyDistribution()
    alice_key, bob_key, error_rate = qkd.generate_key(length=10)
    print(f"Alice密钥: {alice_key}")
    print(f"Bob密钥: {bob_key}")
    print(f"错误率: {error_rate:.2%}")
    
    # 7. 量子计算机
    print("\n📌 7. 量子计算机")
    qc = QuantumComputer(num_qubits=4)
    circuit = [
        ('H', 0, None), ('H', 1, None),
        ('X', 2, None), ('H', 3, None),
    ]
    result = qc.execute(circuit)
    print(f"执行后态: {result.get_state_string()}")
    print(f"统计: {qc.get_statistics()}")
    
    # 8. 量子神经网络
    print("\n📌 8. 量子神经网络")
    qnn = QuantumNeuralNetwork(num_qubits=4, num_layers=2)
    inputs = [0.5, 0.3, 0.8, 0.1]
    outputs = qnn.forward(inputs)
    print(f"输入: {inputs}")
    print(f"输出: {[f'{o:.3f}' for o in outputs]}")
    
    print("\n" + "=" * 60)
    print("✅ 量子计算框架演示完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()