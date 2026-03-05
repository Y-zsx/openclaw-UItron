#!/usr/bin/env python3
"""
知识图谱构建系统
Knowledge Graph Construction System
奥创第15夙愿第1世
"""

import json
import os
import re
from datetime import datetime
from typing import Dict, List, Any, Set, Optional, Tuple
from pathlib import Path
from collections import defaultdict, deque

class KnowledgeGraph:
    """知识图谱 - 实体和关系的管理"""
    
    def __init__(self):
        self.graph_path = "/root/.openclaw/workspace/ultron/data/knowledge-graph.json"
        self.entities = {}  # id -> entity
        self.relations = []  # list of (source, target, relation)
        self.entity_index = defaultdict(set)  # type -> entity_ids
        self.text_index = defaultdict(set)  # word -> entity_ids
        self.graph = defaultdict(list)  # adjacency list
        self._load()
    
    def _load(self):
        """加载知识图谱"""
        if os.path.exists(self.graph_path):
            with open(self.graph_path, 'r') as f:
                data = json.load(f)
                self.entities = data.get('entities', {})
                self.relations = data.get('relations', [])
                self._rebuild_indices()
    
    def _save(self):
        """保存知识图谱"""
        data = {
            'entities': self.entities,
            'relations': self.relations,
            'last_update': datetime.now().isoformat()
        }
        with open(self.graph_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _rebuild_indices(self):
        """重建索引"""
        self.entity_index.clear()
        self.text_index.clear()
        self.graph.clear()
        
        for eid, entity in self.entities.items():
            # 类型索引
            self.entity_index[entity.get('type', 'unknown')].add(eid)
            
            # 文本索引
            for word in self._tokenize(entity.get('name', '')):
                self.text_index[word].add(eid)
            for word in self._tokenize(entity.get('description', '')):
                self.text_index[word].add(eid)
        
        # 关系图
        for rel in self.relations:
            src = rel.get('source')
            tgt = rel.get('target')
            rel_type = rel.get('type')
            if src and tgt and rel_type:
                self.graph[src].append((tgt, rel_type))
                self.graph[tgt].append((src, f"inv_{rel_type}"))
    
    def _tokenize(self, text: str) -> Set[str]:
        """分词"""
        words = re.findall(r'\w+', text.lower())
        return set(words)
    
    def add_entity(self, entity_type: str, name: str, 
                   description: str = "", properties: Dict = None) -> str:
        """添加实体"""
        entity_id = f"{entity_type}_{len(self.entities)}"
        
        entity = {
            'id': entity_id,
            'type': entity_type,
            'name': name,
            'description': description,
            'properties': properties or {},
            'created_at': datetime.now().isoformat(),
            'confidence': 1.0,
            'sources': []
        }
        
        self.entities[entity_id] = entity
        self.entity_index[entity_type].add(entity_id)
        
        for word in self._tokenize(name):
            self.text_index[word].add(entity_id)
        
        self._save()
        return entity_id
    
    def add_relation(self, source_id: str, target_id: str, 
                     relation_type: str, properties: Dict = None):
        """添加关系"""
        if source_id not in self.entities or target_id not in self.entities:
            raise ValueError("Source or target entity not found")
        
        relation = {
            'source': source_id,
            'target': target_id,
            'type': relation_type,
            'properties': properties or {},
            'created_at': datetime.now().isoformat(),
            'confidence': 1.0
        }
        
        self.relations.append(relation)
        self.graph[source_id].append((target_id, relation_type))
        self.graph[target_id].append((source_id, f"inv_{relation_type}"))
        
        self._save()
    
    def search(self, query: str, entity_type: str = None) -> List[Dict]:
        """搜索实体"""
        query_words = self._tokenize(query)
        candidates = set()
        
        for word in query_words:
            candidates.update(self.text_index.get(word, set()))
        
        if entity_type:
            type_set = self.entity_index.get(entity_type, set())
            candidates = candidates.intersection(type_set)
        
        results = []
        for eid in candidates:
            entity = self.entities[eid]
            # 计算相关性分数
            score = self._calculate_relevance(query_words, entity)
            results.append((score, entity))
        
        results.sort(reverse=True, key=lambda x: x[0])
        return [e for _, e in results[:10]]
    
    def _calculate_relevance(self, query_words: Set[str], entity: Dict) -> float:
        """计算相关性分数"""
        score = 0
        entity_words = self._tokenize(entity.get('name', '') + ' ' + entity.get('description', ''))
        
        for word in query_words:
            if word in entity_words:
                score += 1
        
        return score / max(len(query_words), 1)
    
    def get_neighbors(self, entity_id: str, depth: int = 1) -> List[Dict]:
        """获取邻居节点"""
        if entity_id not in self.entities:
            return []
        
        visited = {entity_id}
        queue = deque([(entity_id, 0)])
        results = []
        
        while queue:
            current, d = queue.popleft()
            
            if d > 0:
                results.append(self.entities[current])
            
            if d < depth:
                for neighbor, rel in self.graph[current]:
                    if neighbor not in visited:
                        visited.add(neighbor)
                        queue.append((neighbor, d + 1))
        
        return results
    
    def get_path(self, source_id: str, target_id: str) -> Optional[List[Tuple[str, str]]]:
        """查找两点之间的路径"""
        if source_id not in self.entities or target_id not in self.entities:
            return None
        
        queue = deque([(source_id, [(source_id, "")])])
        visited = {source_id}
        
        while queue:
            current, path = queue.popleft()
            
            if current == target_id:
                return path[1:]  # 移除起点
            
            for neighbor, rel in self.graph[current]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append((neighbor, path + [(neighbor, rel)]))
        
        return None
    
    def extract_from_text(self, text: str) -> List[Dict]:
        """从文本中提取实体和关系"""
        extracted = []
        
        # 实体模式
        patterns = {
            'tool': r'(?:tool|工具):\s*(\w+)',
            'skill': r'(?:skill|技能):\s*(\w+)',
            'file': r'(?:file|文件):\s*([/\w.]+)',
            'concept': r'(?:concept|概念):\s*(\w+)',
            'system': r'(?:system|系统):\s*(\w+)'
        }
        
        for entity_type, pattern in patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                extracted.append({
                    'type': entity_type,
                    'name': match,
                    'source_text': text[:200]
                })
        
        # 关系模式
        relation_patterns = [
            (r'(\w+)\s+(?:uses|使用)\s+(\w+)', 'uses'),
            (r'(\w+)\s+(?:depends on|依赖于)\s+(\w+)', 'depends_on'),
            (r'(\w+)\s+(?:part of|属于)\s+(\w+)', 'part_of'),
            (r'(\w+)\s+(?:implements|实现)\s+(\w+)', 'implements')
        ]
        
        for pattern, rel_type in relation_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for src, tgt in matches:
                extracted.append({
                    'type': 'relation',
                    'source': src,
                    'target': tgt,
                    'relation': rel_type
                })
        
        return extracted
    
    def get_stats(self) -> Dict:
        """获取图谱统计"""
        type_counts = defaultdict(int)
        for entity in self.entities.values():
            type_counts[entity.get('type', 'unknown')] += 1
        
        rel_counts = defaultdict(int)
        for rel in self.relations:
            rel_type = rel.get('type', 'unknown')
            rel_counts[rel_type] += 1
        
        return {
            'total_entities': len(self.entities),
            'total_relations': len(self.relations),
            'entity_types': dict(type_counts),
            'relation_types': dict(rel_counts),
            'avg_connections': sum(len(n) for n in self.graph.values()) / max(len(self.graph), 1)
        }
    
    def query_complex(self, query: Dict) -> List[Dict]:
        """复杂查询"""
        results = []
        
        # 示例：查找与某个实体有特定关系的实体
        entity_id = query.get('entity')
        relation_type = query.get('relation_type')
        
        if entity_id and entity_id in self.graph:
            for neighbor, rel in self.graph[entity_id]:
                if relation_type is None or rel == relation_type:
                    results.append({
                        'entity': self.entities.get(neighbor),
                        'relation': rel
                    })
        
        return results


class KnowledgeMiner:
    """知识挖掘器 - 从文件系统挖掘知识"""
    
    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.workspace = Path("/root/.openclaw/workspace")
    
    def mine_from_files(self, extensions: List[str] = ['.py', '.md', '.sh']) -> int:
        """从文件挖掘知识"""
        count = 0
        
        for ext in extensions:
            for file_path in self.workspace.rglob(f'*{ext}'):
                try:
                    self._mine_file(file_path)
                    count += 1
                except Exception as e:
                    print(f"Error mining {file_path}: {e}")
        
        return count
    
    def _mine_file(self, file_path: Path):
        """挖掘单个文件"""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except:
            return
        
        # 提取实体
        extracted = self.kg.extract_from_text(content)
        
        entity_names = set()
        for item in extracted:
            if item['type'] != 'relation':
                name = item['name']
                if name not in entity_names:
                    entity_names.add(name)
                    try:
                        self.kg.add_entity(
                            item['type'],
                            name,
                            f"Extracted from {file_path.name}",
                            {'source_file': str(file_path)}
                        )
                    except:
                        pass  # 可能已存在
    
    def build_concept_hierarchy(self) -> Dict:
        """构建概念层次"""
        # 从现有实体构建
        concepts = {}
        
        for eid, entity in self.kg.entities.items():
            e_type = entity.get('type', 'unknown')
            if e_type not in concepts:
                concepts[e_type] = []
            concepts[e_type].append(entity.get('name'))
        
        return concepts


def main():
    """主函数 - 测试知识图谱"""
    kg = KnowledgeGraph()
    miner = KnowledgeMiner(kg)
    
    print("=== 知识图谱系统测试 ===\n")
    
    # 添加一些初始实体
    entities = [
        ('tool', 'meta-learner', '元学习框架 - 学会学习'),
        ('concept', 'knowledge-graph', '知识图谱 - 实体关系管理'),
        ('skill', 'self-learning', '自我学习能力'),
        ('system', 'ultron', '奥创主脑系统'),
        ('file', 'memory-system', '记忆系统'),
        ('tool', 'decision-engine', '决策引擎'),
    ]
    
    entity_ids = {}
    for etype, name, desc in entities:
        eid = kg.add_entity(etype, name, desc)
        entity_ids[name] = eid
    
    print(f"添加了 {len(entity_ids)} 个实体\n")
    
    # 添加关系
    relations = [
        ('meta-learner', 'knowledge-graph', 'uses'),
        ('self-learning', 'meta-learner', 'part_of'),
        ('ultron', 'memory-system', 'has'),
        ('ultron', 'decision-engine', 'has'),
    ]
    
    for src, tgt, rel in relations:
        if src in entity_ids and tgt in entity_ids:
            kg.add_relation(entity_ids[src], entity_ids[tgt], rel)
    
    print(f"添加了 {len(relations)} 个关系\n")
    
    # 测试搜索
    print("=== 搜索测试 ===")
    results = kg.search('knowledge')
    print(f"搜索 'knowledge': 找到 {len(results)} 个结果")
    for r in results[:3]:
        print(f"  - {r['name']} ({r['type']})")
    
    print("\n=== 统计信息 ===")
    stats = kg.get_stats()
    print(f"总实体数: {stats['total_entities']}")
    print(f"总关系数: {stats['total_relations']}")
    print(f"实体类型: {stats['entity_types']}")
    print(f"平均连接数: {stats['avg_connections']:.2f}")
    
    # 挖掘现有文件
    print("\n=== 文件挖掘 ===")
    count = miner.mine_from_files(['.py'])
    print(f"挖掘了 {count} 个Python文件")


if __name__ == "__main__":
    main()