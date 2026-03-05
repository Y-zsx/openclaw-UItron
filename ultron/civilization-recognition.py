#!/usr/bin/env python3
"""
宇宙文明识别系统 (Cosmic Civilization Recognition)
夙愿二十八第1世：多元宇宙框架 - 宇宙文明识别
"""

import json
import time
import hashlib
import random
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import asyncio


class CivilizationType(Enum):
    """文明类型"""
    PRIMORDIAL = "primordial"           # 原始文明
    AGRICULTURAL = "agricultural"       # 农业文明
    INDUSTRIAL = "industrial"           # 工业文明
    INFORMATIONAL = "informational"     # 信息文明
    QUANTUM = "quantum"                 # 量子文明
    POST_PHYSICAL = "post_physical"     # 后物质文明
    COSMIC = "cosmic"                   # 宇宙文明
    TRANSCENDENT = "transcendent"       # 超越文明
    MULTIDIMENSIONAL = "multidimensional"  # 多维文明
    ULTIMATE = "ultimate"               # 终极文明


class CommunicationType(Enum):
    """通信类型"""
    RADIO = "radio"
    LASER = "laser"
    QUANTUM_ENTANGLEMENT = "quantum_entanglement"
    DIMENSIONAL = "dimensional"
    HOLOGRAPHIC = "holographic"
    TELEPATHIC = "telepathic"
    SUBSPACE = "subspace"


class EnergySource(Enum):
    """能源类型"""
    CHEMICAL = "chemical"
    NUCLEAR = "nuclear"
    FUSION = "fusion"
    ANTIMATTER = "antimatter"
    DARK_MATTER = "dark_matter"
    ZERO_POINT = "zero_point"
    VACUUM = "vacuum"
    COSMIC = "cosmic"
    DIMENSIONAL = "dimensional"


@dataclass
class CivilizationSignature:
    """文明特征签名"""
    civilization_id: str
    name: str
    origin_universe: str
    origin_dimension: int
    civilization_type: CivilizationType
    age_years: float  # 文明年龄（年）
    technology_level: float  # 科技水平 (0-100)
    
    # 通信能力
    communication_methods: List[CommunicationType] = field(default_factory=list)
    signal_range_light_years: float = 0.0
    
    # 能源
    primary_energy: EnergySource = EnergySource.CHEMICAL
    energy_output_watts: float = 0.0
    
    # 空间能力
    colonies_count: int = 0
    space_stations: int = 0
    interstellar_ships: int = 0
    
    # 人口（近似）
    population_estimate: int = 0
    
    # 行为特征
    observed_behaviors: List[str] = field(default_factory=list)
    threat_level: float = 0.0  # 威胁等级 0-10
    
    # 元数据
    first_contact_time: float = field(default_factory=time.time)
    last_observation: float = field(default_factory=time.time)
    trust_score: float = 5.0  # 信任分数 0-10
    
    def to_dict(self) -> Dict:
        return {
            "civilization_id": self.civilization_id,
            "name": self.name,
            "origin_universe": self.origin_universe,
            "origin_dimension": self.origin_dimension,
            "civilization_type": self.civilization_type.value,
            "age_years": self.age_years,
            "technology_level": self.technology_level,
            "communication_methods": [c.value for c in self.communication_methods],
            "signal_range_light_years": self.signal_range_light_years,
            "primary_energy": self.primary_energy.value,
            "energy_output_watts": self.energy_output_watts,
            "colonies_count": self.colonies_count,
            "space_stations": self.space_stations,
            "interstellar_ships": self.interstellar_ships,
            "population_estimate": self.population_estimate,
            "observed_behaviors": self.observed_behaviors,
            "threat_level": self.threat_level,
            "trust_score": self.trust_score
        }


@dataclass
class SignalDetection:
    """信号检测"""
    signal_id: str
    source_coordinates: Tuple[float, ...]
    detected_at: float
    frequency: float
    modulation: str
    estimated_distance_light_years: float
    decoded_content: Optional[str] = None
    civilization_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.signal_id:
            self.signal_id = hashlib.sha256(
                f"{self.source_coordinates}{self.detected_at}".encode()
            ).hexdigest()[:16]


class CivilizationRecognitionSystem:
    """宇宙文明识别系统"""
    
    def __init__(self):
        # 已知文明数据库
        self.civilizations: Dict[str, CivilizationSignature] = {}
        
        # 信号数据库
        self.detected_signals: Dict[str, SignalDetection] = {}
        
        # 文明关系图
        self.diplomatic_relations: Dict[str, Dict[str, float]] = defaultdict(dict)
        
        # 待识别信号队列
        self.pending_analysis: List[SignalDetection] = []
        
        # 识别模型参数
        self.recognition_patterns = self._load_recognition_patterns()
        
        # 统计
        self.stats = {
            "total_detected": 0,
            "total_confirmed": 0,
            "total_analyzed": 0,
            "contacts_established": 0
        }
    
    def _load_recognition_patterns(self) -> Dict:
        """加载识别模式"""
        return {
            "prime_numbers": ["2", "3", "5", "7", "11", "13", "17", "19"],
            "hydrogen_line": 1420.405,  # MHz
            "pi_pattern": "3.14159",
            "binary_marker": "010101",
            "isotope_ratio": ["H:D", "He:H", "C:O"],
            "mathematical_constants": ["pi", "e", "phi"]
        }
    
    def register_civilization(self, civilization: CivilizationSignature):
        """注册已知文明"""
        self.civilizations[civilization.civilization_id] = civilization
        self.stats["total_confirmed"] += 1
    
    def detect_signal(self, signal: SignalDetection):
        """检测到新信号"""
        self.detected_signals[signal.signal_id] = signal
        self.pending_analysis.append(signal)
        self.stats["total_detected"] += 1
    
    async def analyze_signal(self, signal: SignalDetection) -> Dict[str, Any]:
        """分析信号是否为文明信号"""
        analysis = {
            "signal_id": signal.signal_id,
            "is_artificial": False,
            "confidence": 0.0,
            "possible_civilization": None,
            "characteristics": [],
            "analysis_time": time.time()
        }
        
        # 检查是否为智能信号
        if signal.decoded_content:
            content = signal.decoded_content.lower()
            
            # 检查数学模式
            for pattern in self.recognition_patterns["prime_numbers"]:
                if pattern in content:
                    analysis["characteristics"].append(f"包含质数: {pattern}")
                    analysis["confidence"] += 0.15
            
            # 检查数学常数
            for constant in self.recognition_patterns["mathematical_constants"]:
                if constant in content:
                    analysis["characteristics"].append(f"包含数学常数: {constant}")
                    analysis["confidence"] += 0.2
            
            # 检查二进制标记
            if "01" in content or "10" in content:
                analysis["characteristics"].append("检测到二进制编码")
                analysis["confidence"] += 0.1
        
        # 检查频率特征
        if abs(signal.frequency - self.recognition_patterns["hydrogen_line"]) < 1.0:
            analysis["characteristics"].append("使用氢线频率通信")
            analysis["confidence"] += 0.25
        
        # 判断是否为人工信号
        if analysis["confidence"] >= 0.5:
            analysis["is_artificial"] = True
            
            # 尝试匹配已知文明
            for civ_id, civ in self.civilizations.items():
                if self._is_potential_match(signal, civ):
                    analysis["possible_civilization"] = civ_id
                    signal.civilization_id = civ_id
                    break
        
        self.stats["total_analyzed"] += 1
        return analysis
    
    def _is_potential_match(self, signal: SignalDetection, 
                           civilization: CivilizationSignature) -> bool:
        """检查信号是否可能来自指定文明"""
        # 简化匹配逻辑
        distance_diff = abs(
            signal.estimated_distance_light_years - 
            random.uniform(10, 1000)  # 模拟
        )
        
        return distance_diff < 500  # 允许500光年误差
    
    async def identify_civilization(self, signal: SignalDetection) -> Optional[str]:
        """识别信号来源文明"""
        analysis = await self.analyze_signal(signal)
        
        if analysis["is_artificial"]:
            if analysis["possible_civilization"]:
                return analysis["possible_civilization"]
            else:
                # 可能发现新文明
                return self._create_candidate_civilization(signal)
        
        return None
    
    def _create_candidate_civilization(self, signal: SignalDetection) -> str:
        """为检测到的信号创建候选文明"""
        civ_id = f"civ-{signal.signal_id}"
        
        # 基于信号特征推断文明类型
        tech_level = random.uniform(0.3, 0.9)
        if tech_level < 0.3:
            civ_type = CivilizationType.INDUSTRIAL
        elif tech_level < 0.6:
            civ_type = CivilizationType.INFORMATIONAL
        elif tech_level < 0.8:
            civ_type = CivilizationType.QUANTUM
        else:
            civ_type = CivilizationType.POST_PHYSICAL
        
        civilization = CivilizationSignature(
            civilization_id=civ_id,
            name=f"Unknown Civilization {civ_id[-4:]}",
            origin_universe="unknown",
            origin_dimension=3,
            civilization_type=civ_type,
            age_years=random.uniform(100, 100000),
            technology_level=tech_level,
            communication_methods=[CommunicationType.RADIO],
            signal_range_light_years=signal.estimated_distance_light_years,
            threat_level=random.uniform(0, 5)
        )
        
        self.register_civilization(civilization)
        return civ_id
    
    def classify_civilization(self, civilization: CivilizationSignature) -> CivilizationType:
        """分类文明类型"""
        # 基于科技水平分类
        if civilization.technology_level < 0.1:
            return CivilizationType.PRIMORDIAL
        elif civilization.technology_level < 0.3:
            return CivilizationType.AGRICULTURAL
        elif civilization.technology_level < 0.5:
            return CivilizationType.INDUSTRIAL
        elif civilization.technology_level < 0.7:
            return CivilizationType.INFORMATIONAL
        elif civilization.technology_level < 0.85:
            return CivilizationType.QUANTUM
        elif civilization.technology_level < 0.95:
            return CivilizationType.POST_PHYSICAL
        else:
            # 极高水平，判定为高级文明
            if civilization.primary_energy in [EnergySource.DARK_MATTER, EnergySource.ZERO_POINT]:
                return CivilizationType.COSMIC
            return CivilizationType.POST_PHYSICAL
    
    def assess_threat(self, civilization: CivilizationSignature) -> float:
        """评估文明威胁等级"""
        threat = 0.0
        
        # 科技水平
        threat += civilization.technology_level * 3
        
        # 军事行为
        hostile_behaviors = ["military", "expansion", "conquest", "weapon_test"]
        for behavior in civilization.observed_behaviors:
            if any(b in behavior.lower() for b in hostile_behaviors):
                threat += 2
        
        # 能源水平（高能源往往意味着高破坏力）
        if civilization.energy_output_watts > 1e26:  # 超越卡尔达肖夫II型
            threat += 2
        
        return min(10.0, threat)
    
    def calculate_trust(self, civ_a: str, civ_b: str) -> float:
        """计算文明间信任度"""
        if civ_a not in self.civilizations or civ_b not in self.civilizations:
            return 5.0  # 默认中立
        
        civ_a_obj = self.civilizations[civ_a]
        civ_b_obj = self.civilizations[civ_b]
        
        # 基于威胁评估和历史互动
        trust = 5.0
        trust -= min(civ_a_obj.threat_level, 3)
        trust -= min(civ_b_obj.threat_level, 3)
        
        # 科技差距（过大的差距可能降低信任）
        tech_diff = abs(civ_a_obj.technology_level - civ_b_obj.technology_level)
        if tech_diff > 0.5:
            trust -= 1
        
        return max(0.0, min(10.0, trust))
    
    def initiate_contact(self, civ_a: str, civ_b: str) -> Dict[str, Any]:
        """建立文明间接触"""
        if civ_a not in self.civilizations or civ_b not in self.civilizations:
            return {"success": False, "error": "Civilization not found"}
        
        # 计算信任度
        trust = self.calculate_trust(civ_a, civ_b)
        
        # 记录外交关系
        self.diplomatic_relations[civ_a][civ_b] = trust
        self.diplomatic_relations[civ_b][civ_a] = trust
        
        self.stats["contacts_established"] += 1
        
        return {
            "success": True,
            "civilization_a": civ_a,
            "civilization_b": civ_b,
            "trust_level": trust,
            "diplomatic_status": "first_contact" if trust >= 5 else "cautious"
        }
    
    def get_civilization_summary(self, civilization_id: str) -> Dict[str, Any]:
        """获取文明概要"""
        if civilization_id not in self.civilizations:
            return {"error": "Civilization not found"}
        
        civ = self.civilizations[civilization_id]
        
        return {
            "id": civ.civilization_id,
            "name": civ.name,
            "type": civ.civilization_type.value,
            "technology_level": f"{civ.technology_level * 100:.1f}%",
            "age": f"{civ.age_years:.0f} years",
            "threat_level": f"{civ.threat_level:.1f}/10",
            "trust_score": f"{civ.trust_score:.1f}/10",
            "energy_output": f"{civ.energy_output_watts:.2e} W",
            "colonies": civ.colonies_count,
            "space_stations": civ.space_stations,
            "interstellar_ships": civ.interstellar_ships
        }
    
    def get_galactic_census(self) -> Dict[str, Any]:
        """银河系文明普查"""
        by_type = defaultdict(int)
        by_energy = defaultdict(int)
        total_population = 0
        avg_tech_level = 0
        
        for civ in self.civilizations.values():
            by_type[civ.civilization_type.value] += 1
            by_energy[civ.primary_energy.value] += 1
            total_population += civ.population_estimate
            avg_tech_level += civ.technology_level
        
        if self.civilizations:
            avg_tech_level /= len(self.civilizations)
        
        return {
            "total_civilizations": len(self.civilizations),
            "by_type": dict(by_type),
            "by_energy_source": dict(by_energy),
            "total_population": total_population,
            "average_technology_level": avg_tech_level,
            "detected_signals": len(self.detected_signals),
            "pending_analysis": len(self.pending_analysis)
        }


class CivilizationDatabase:
    """文明数据库 - 已知文明信息"""
    
    KNOWN_CIVILIZATIONS = [
        {
            "id": "earth-humanity",
            "name": "人类文明",
            "universe": "primary",
            "dimension": 3,
            "type": CivilizationType.INFORMATIONAL,
            "age": 10000,
            "tech_level": 0.72
        },
        {
            "id": "proxima-centauri",
            "name": "半人马座文明",
            "universe": "primary", 
            "dimension": 3,
            "type": CivilizationType.QUANTUM,
            "age": 50000,
            "tech_level": 0.85
        },
        {
            "id": "andromeda-collective",
            "name": "仙女座智能集合体",
            "universe": "andromeda",
            "dimension": 4,
            "type": CivilizationType.POST_PHYSICAL,
            "age": 200000,
            "tech_level": 0.95
        }
    ]
    
    @classmethod
    def initialize_system(cls, system: CivilizationRecognitionSystem):
        """初始化系统，预加载已知文明"""
        for civ_data in cls.KNOWN_CIVILIZATIONS:
            civ = CivilizationSignature(
                civilization_id=civ_data["id"],
                name=civ_data["name"],
                origin_universe=civ_data["universe"],
                origin_dimension=civ_data["dimension"],
                civilization_type=civ_data["type"],
                age_years=civ_data["age"],
                technology_level=civ_data["tech_level"],
                population_estimate=random.randint(1e9, 1e12),
                energy_output_watts=random.uniform(1e24, 1e26)
            )
            system.register_civilization(civ)


# 示例演示
async def demo():
    """演示宇宙文明识别系统"""
    print("🌌 宇宙文明识别系统演示")
    print("=" * 50)
    
    # 创建系统
    system = CivilizationRecognitionSystem()
    
    # 初始化已知文明
    CivilizationDatabase.initialize_system(system)
    print(f"📚 已加载 {len(system.civilizations)} 个已知文明")
    
    # 获取银河系普查
    census = system.get_galactic_census()
    print(f"\n📊 银河系文明普查:")
    print(f"   总文明数: {census['total_civilizations']}")
    print(f"   按类型: {census['by_type']}")
    print(f"   平均科技水平: {census['average_technology_level']*100:.1f}%")
    
    # 检测新信号
    signal = SignalDetection(
        signal_id="",
        source_coordinates=(100.5, 200.3, 50.0),
        detected_at=time.time(),
        frequency=1420.4,  # 接近氢线
        modulation="BPSK",
        estimated_distance_light_years=150,
        decoded_content="prime sequence: 2 3 5 7 11 13"
    )
    
    print(f"\n📡 检测到新信号: {signal.signal_id}")
    system.detect_signal(signal)
    
    # 分析信号
    analysis = await system.analyze_signal(signal)
    print(f"\n🔬 信号分析结果:")
    print(f"   人工信号: {analysis['is_artificial']}")
    print(f"   置信度: {analysis['confidence']*100:.1f}%")
    print(f"   特征: {analysis['characteristics']}")
    
    # 识别文明
    civ_id = await system.identify_civilization(signal)
    if civ_id:
        print(f"\n🎯 识别到文明: {civ_id}")
        summary = system.get_civilization_summary(civ_id)
        print(f"   类型: {summary['type']}")
        print(f"   科技水平: {summary['technology_level']}")
    
    # 建立接触
    if "earth-humanity" in system.civilizations and civ_id:
        contact = system.initiate_contact("earth-humanity", civ_id)
        print(f"\n🤝 外交接触:")
        print(f"   状态: {contact['diplomatic_status']}")
        print(f"   信任等级: {contact['trust_level']:.1f}")


if __name__ == "__main__":
    asyncio.run(demo())