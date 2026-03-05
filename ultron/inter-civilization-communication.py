#!/usr/bin/env python3
"""
文明间通信系统 - Inter-Civilization Communication
夙愿二十八第2世：跨宇宙协作
实现不同文明之间的跨维度通信、翻译与协作
"""

import json
import time
import random
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from enum import Enum
from collections import defaultdict


class CivilizationType(Enum):
    """文明类型"""
    PRIMITIVE = "primitive"         # 原始文明
    AGRICULTURAL = "agricultural"   # 农业文明
    INDUSTRIAL = "industrial"       # 工业文明
    INFORMATION = "information"     # 信息文明
    POST_BIOLOGICAL = "post_biological"  # 后生物文明
    QUANTUM = "quantum"             # 量子文明
    COSMIC = "cosmic"               # 宇宙文明
    TRANSCENDENT = "transcendent"   # 超验文明


class CommunicationProtocol(Enum):
    """通信协议"""
    PRIMITIVE_SIGNALS = "primitive_signals"
    ELECTROMAGNETIC = "electromagnetic"
    QUANTUM_ENTANGLEMENT = "quantum_entanglement"
    DIMENSIONAL_WAVE = "dimensional_wave"
    CONSCIOUSNESS_LINK = "consciousness_link"
    UNIVERSAL_MATH = "universal_math"


class MessagePriority(Enum):
    """消息优先级"""
    LOW = 1
    NORMAL = 5
    HIGH = 8
    URGENT = 10
    CRITICAL = 15


class MessageStatus(Enum):
    """消息状态"""
    PENDING = "pending"
    TRANSMITTING = "transmitting"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


@dataclass
class Civilization:
    """文明"""
    civilization_id: str
    name: str
    civ_type: CivilizationType
    universe: str
    dimension: int
    communication_protocols: Set[CommunicationProtocol]
    resources: Dict[str, float] = field(default_factory=dict)
    contacts: List[str] = field(default_factory=list)
    message_count: int = 0
    trust_level: float = 0.5
    discovered_at: float = field(default_factory=time.time)
    last_contact: float = field(default_factory=time.time)


@dataclass
class Message:
    """跨文明消息"""
    message_id: str
    sender_id: str
    receiver_id: str
    content: Any
    priority: MessagePriority
    protocol: CommunicationProtocol
    status: MessageStatus
    timestamp: float = field(default_factory=time.time)
    delivered_at: Optional[float] = None
    read_at: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class UniversalTranslator:
    """通用翻译器 - 跨文明语言翻译"""
    
    def __init__(self):
        self.language_models: Dict[str, Dict] = {}
        self.translation_cache: Dict[str, str] = {}
        self.learning_rate = 0.1
        self._init_base_languages()
    
    def _init_base_languages(self):
        """初始化基础语言模型"""
        self.language_models = {
            "universal_math": {
                "type": "mathematical",
                "vocabulary": ["0", "1", "+", "-", "×", "÷", "=", "∞", "π", "e"],
                "complexity": 1.0
            },
            "quantum_state": {
                "type": "quantum",
                "vocabulary": ["Ψ", "⟩", "⟨", "|", "0", "1", "+", "-"],
                "complexity": 0.8
            },
            "consciousness_wave": {
                "type": "consciousness",
                "vocabulary": ["◇", "◈", "△", "▽", "○", "●"],
                "complexity": 0.9
            },
            "dimensional_code": {
                "type": "dimensional",
                "vocabulary": ["①", "②", "③", "④", "⑤", "⑥", "⑦", "⑧"],
                "complexity": 0.95
            },
            "electromagnetic": {
                "type": "signal",
                "vocabulary": ["·", "−", "≡", "∼", "≋"],
                "complexity": 0.6
            }
        }
    
    def translate(self, message: str, from_lang: str, to_lang: str) -> str:
        """翻译消息"""
        cache_key = f"{from_lang}:{to_lang}:{hashlib.md5(message.encode()).hexdigest()}"
        
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key]
        
        if from_lang == to_lang:
            return message
        
        if from_lang == "universal_math" or to_lang == "universal_math":
            translated = self._math_based_translation(message, from_lang, to_lang)
        else:
            translated = self._neural_translation(message, from_lang, to_lang)
        
        self.translation_cache[cache_key] = translated
        return translated
    
    def _math_based_translation(self, message: str, from_lang: str, to_lang: str) -> str:
        """基于数学的翻译"""
        if to_lang == "universal_math":
            return self._encode_to_math(message)
        elif from_lang == "universal_math":
            return self._decode_from_math(message)
        return message
    
    def _encode_to_math(self, message: str) -> str:
        """编码为数学语言"""
        encoded = []
        for char in message:
            code = ord(char)
            encoded.append(f"∫{code}∂")
        return "".join(encoded)
    
    def _decode_from_math(self, message: str) -> str:
        """从数学语言解码"""
        decoded = []
        parts = message.split("∫")
        for part in parts:
            if "∂" in part:
                num = part.replace("∂", "")
                if num.isdigit():
                    decoded.append(chr(int(num)))
        return "".join(decoded)
    
    def _neural_translation(self, message: str, from_lang: str, to_lang: str) -> str:
        """神经翻译"""
        from_model = self.language_models.get(from_lang, {})
        to_model = self.language_models.get(to_lang, {})
        
        if not from_model or not to_model:
            return message
        
        complexity_factor = to_model.get("complexity", 0.5)
        return f"[{to_lang}] {message} [/]" if complexity_factor > 0.5 else message


class CivilizationNetwork:
    """文明网络 - 管理已知文明"""
    
    def __init__(self):
        self.civilizations: Dict[str, Civilization] = {}
        self.contacts: Dict[str, List[str]] = defaultdict(list)
        self.lock = threading.RLock()
        self.civ_counter = 0
        self._init_known_civilizations()
    
    def _init_known_civilizations(self):
        """初始化已知文明"""
        known_civs = [
            {
                "name": "地球文明",
                "civ_type": CivilizationType.INFORMATION,
                "universe": "prime-0",
                "dimension": 4,
                "protocols": {CommunicationProtocol.ELECTROMAGNETIC}
            },
            {
                "name": "半人马座α文明",
                "civ_type": CivilizationType.POST_BIOLOGICAL,
                "universe": "prime-0",
                "dimension": 5,
                "protocols": {CommunicationProtocol.QUANTUM_ENTANGLEMENT, CommunicationProtocol.ELECTROMAGNETIC}
            },
            {
                "name": "仙女座星际联邦",
                "civ_type": CivilizationType.COSMIC,
                "universe": "mirror-0",
                "dimension": 6,
                "protocols": {CommunicationProtocol.DIMENSIONAL_WAVE, CommunicationProtocol.QUANTUM_ENTANGLEMENT}
            }
        ]
        
        for civ_data in known_civs:
            self.register_civilization(**civ_data)
    
    def register_civilization(self, name: str, civ_type: CivilizationType,
                              universe: str, dimension: int,
                              protocols: Set[CommunicationProtocol]) -> str:
        """注册新文明"""
        with self.lock:
            self.civ_counter += 1
            civ_id = f"civ-{self.civ_counter}"
            
            civ = Civilization(
                civilization_id=civ_id,
                name=name,
                civ_type=civ_type,
                universe=universe,
                dimension=dimension,
                communication_protocols=protocols
            )
            
            self.civilizations[civ_id] = civ
            return civ_id
    
    def discover_civilization(self, civ_id: str) -> bool:
        """发现文明"""
        with self.lock:
            if civ_id not in self.civilizations:
                return False
            
            civ = self.civilizations[civ_id]
            civ.last_contact = time.time()
            return True
    
    def establish_contact(self, civ1_id: str, civ2_id: str) -> bool:
        """建立文明间联系"""
        with self.lock:
            if civ1_id not in self.civilizations or civ2_id not in self.civilizations:
                return False
            
            civ1 = self.civilizations[civ1_id]
            civ2 = self.civilizations[civ2_id]
            
            if civ2_id not in civ1.contacts:
                civ1.contacts.append(civ2_id)
            if civ1_id not in civ2.contacts:
                civ2.contacts.append(civ1_id)
            
            self.contacts[civ1_id].append(civ2_id)
            self.contacts[civ2_id].append(civ1_id)
            
            civ1.last_contact = time.time()
            civ2.last_contact = time.time()
            
            return True
    
    def get_civilization(self, civ_id: str) -> Optional[ Civilization]:
        """获取文明信息"""
        return self.civilizations.get(civ_id)
    
    def get_civilizations_by_universe(self, universe: str) -> List[Civilization]:
        """获取指定宇宙的文明"""
        return [c for c in self.civilizations.values() if c.universe == universe]
    
    def calculate_trust(self, civ1_id: str, civ2_id: str) -> float:
        """计算文明间信任度"""
        if civ1_id not in self.civilizations or civ2_id not in self.civilizations:
            return 0.0
        
        civ1 = self.civilizations[civ1_id]
        civ2 = self.civilizations[civ2_id]
        
        contact_history = len(set(civ1.contacts) & set(civ2.contacts))
        base_trust = 0.5
        
        if civ1.universe == civ2.universe:
            base_trust += 0.1
        if abs(civ1.dimension - civ2.dimension) <= 1:
            base_trust += 0.1
        
        trust = min(1.0, base_trust + contact_history * 0.05)
        return trust


class MessageRouter:
    """消息路由器 - 跨文明消息传递"""
    
    def __init__(self, network: CivilizationNetwork, translator: UniversalTranslator):
        self.network = network
        self.translator = translator
        self.messages: Dict[str, Message] = {}
        self.message_queues: Dict[str, List[str]] = defaultdict(list)
        self.message_counter = 0
        self.lock = threading.RLock()
    
    def send_message(self, sender_id: str, receiver_id: str, content: Any,
                     priority: MessagePriority = MessagePriority.NORMAL,
                     protocol: CommunicationProtocol = CommunicationProtocol.UNIVERSAL_MATH) -> str:
        """发送跨文明消息"""
        with self.lock:
            sender = self.network.get_civilization(sender_id)
            receiver = self.network.get_civilization(receiver_id)
            
            if not sender or not receiver:
                return ""
            
            self.message_counter += 1
            message_id = f"msg-{self.message_counter}"
            
            sender_protocols = sender.communication_protocols
            if protocol not in sender_protocols:
                available = list(sender_protocols)[0] if sender_protocols else CommunicationProtocol.UNIVERSAL_MATH
                protocol = available
            
            message = Message(
                message_id=message_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                content=content,
                priority=priority,
                protocol=protocol,
                status=MessageStatus.PENDING
            )
            
            self.messages[message_id] = message
            self.message_queues[receiver_id].append(message_id)
            
            sender.message_count += 1
            
            return message_id
    
    def route_message(self, message_id: str) -> bool:
        """路由消息"""
        with self.lock:
            if message_id not in self.messages:
                return False
            
            message = self.messages[message_id]
            
            if message.status != MessageStatus.PENDING:
                return False
            
            message.status = MessageStatus.TRANSMITTING
            
            sender = self.network.get_civilization(message.sender_id)
            receiver = self.network.get_civilization(message.receiver_id)
            
            if sender and receiver:
                delay = random.uniform(0.1, 1.0)
                time.sleep(min(delay, 0.01))
                
                message.status = MessageStatus.DELIVERED
                message.delivered_at = time.time()
                
                return True
            
            message.status = MessageStatus.FAILED
            return False
    
    def deliver_message(self, message_id: str) -> bool:
        """投递消息"""
        with self.lock:
            if message_id not in self.messages:
                return False
            
            message = self.messages[message_id]
            
            if message.status == MessageStatus.DELIVERED:
                message.status = MessageStatus.READ
                message.read_at = time.time()
                return True
            
            return False
    
    def get_pending_messages(self, receiver_id: str) -> List[Message]:
        """获取待处理消息"""
        pending = []
        queue = self.message_queues.get(receiver_id, [])
        
        for msg_id in queue:
            if msg_id in self.messages:
                msg = self.messages[msg_id]
                if msg.status in [MessageStatus.PENDING, MessageStatus.TRANSMITTING]:
                    pending.append(msg)
        
        return pending
    
    def get_message_history(self, civ_id: str) -> List[Message]:
        """获取消息历史"""
        return [m for m in self.messages.values() 
                if m.sender_id == civ_id or m.receiver_id == civ_id]


class DiplomaticChannel:
    """外交频道 - 高级文明间协作"""
    
    def __init__(self, network: CivilizationNetwork, router: MessageRouter):
        self.network = network
        self.router = router
        self.agreements: Dict[str, Dict] = {}
        self.agreement_counter = 0
        self.lock = threading.Lock()
    
    def propose_alliance(self, civ1_id: str, civ2_id: str, terms: Dict) -> str:
        """提议结盟"""
        with self.lock:
            self.agreement_counter += 1
            agreement_id = f"alliance-{self.agreement_counter}"
            
            trust = self.network.calculate_trust(civ1_id, civ2_id)
            
            self.agreements[agreement_id] = {
                "agreement_id": agreement_id,
                "type": "alliance",
                "parties": [civ1_id, civ2_id],
                "terms": terms,
                "trust_required": 0.7,
                "current_trust": trust,
                "status": "proposed",
                "created_at": time.time()
            }
            
            return agreement_id
    
    def sign_agreement(self, agreement_id: str) -> bool:
        """签署协议"""
        with self.lock:
            if agreement_id not in self.agreements:
                return False
            
            agreement = self.agreements[agreement_id]
            
            if agreement["current_trust"] >= agreement["trust_required"]:
                agreement["status"] = "active"
                agreement["signed_at"] = time.time()
                return True
            
            return False
    
    def break_agreement(self, agreement_id: str) -> bool:
        """解除协议"""
        with self.lock:
            if agreement_id in self.agreements:
                self.agreements[agreement_id]["status"] = "broken"
                self.agreements[agreement_id]["broken_at"] = time.time()
                return True
            return False


def demo():
    """演示文明间通信系统"""
    print("=" * 60)
    print("文明间通信系统 - Inter-Civilization Communication Demo")
    print("=" * 60)
    
    network = CivilizationNetwork()
    translator = UniversalTranslator()
    router = MessageRouter(network, translator)
    diplomatic = DiplomaticChannel(network, router)
    
    print("\n[1] 已发现文明:")
    for civ_id, civ in network.civilizations.items():
        print(f"  {civ.name} ({civ.civ_type.value}) - 维度: {civ.dimension}")
    
    print("\n[2] 建立文明间联系...")
    civ_ids = list(network.civilizations.keys())
    if len(civ_ids) >= 2:
        network.establish_contact(civ_ids[0], civ_ids[1])
        network.establish_contact(civ_ids[1], civ_ids[2])
        print(f"  已建立 {civ_ids[0]} <-> {civ_ids[1]}")
        print(f"  已建立 {civ_ids[1]} <-> {civ_ids[2]}")
    
    print("\n[3] 发送跨文明消息...")
    msg1 = router.send_message(
        sender_id=civ_ids[0],
        receiver_id=civ_ids[1],
        content="和平与合作",
        priority=MessagePriority.HIGH,
        protocol=CommunicationProtocol.QUANTUM_ENTANGLEMENT
    )
    print(f"  消息ID: {msg1}")
    
    msg2 = router.send_message(
        sender_id=civ_ids[1],
        receiver_id=civ_ids[2],
        content="资源共享提议",
        priority=MessagePriority.NORMAL,
        protocol=CommunicationProtocol.DIMENSIONAL_WAVE
    )
    print(f"  消息ID: {msg2}")
    
    print("\n[4] 路由消息...")
    if msg1:
        result = router.route_message(msg1)
        print(f"  消息1: {'投递成功' if result else '投递失败'}")
    if msg2:
        result = router.route_message(msg2)
        print(f"  消息2: {'投递成功' if result else '投递失败'}")
    
    print("\n[5] 消息翻译...")
    math_message = translator._encode_to_math("Hello Universe")
    print(f"  原文: Hello Universe")
    print(f"  数学编码: {math_message}")
    decoded = translator._decode_from_math(math_message)
    print(f"  解码: {decoded}")
    
    print("\n[6] 外交协议...")
    if len(civ_ids) >= 3:
        alliance = diplomatic.propose_alliance(
            civ_ids[0], 
            civ_ids[1],
            {"resource_sharing": True, "defense_pact": True}
        )
        print(f"  提议结盟ID: {alliance}")
        
        trust = network.calculate_trust(civ_ids[0], civ_ids[1])
        print(f"  当前信任度: {trust:.2f}")
        
        signed = diplomatic.sign_agreement(alliance)
        print(f"  签署状态: {'成功' if signed else '需要更高信任度'}")
    
    print("\n[7] 文明间信任计算...")
    for i in range(len(civ_ids)):
        for j in range(i+1, len(civ_ids)):
            trust = network.calculate_trust(civ_ids[i], civ_ids[j])
            civ1 = network.civilizations[civ_ids[i]]
            civ2 = network.civilizations[civ_ids[j]]
            print(f"  {civ1.name} <-> {civ2.name}: {trust:.2f}")
    
    print("\n[8] 消息状态...")
    for msg_id, msg in router.messages.items():
        print(f"  {msg_id}: {msg.sender_id} -> {msg.receiver_id} [{msg.status.value}]")
    
    print("\n" + "=" * 60)
    print("文明间通信系统 - 运行完成")
    print("=" * 60)


if __name__ == "__main__":
    demo()