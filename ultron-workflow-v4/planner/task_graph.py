"""
任务依赖图 (Task Graph)
=========================
管理任务之间的依赖关系，确保按正确顺序执行。

数据模型:
- Node: 任务节点 (id, name, status, dependencies)
- Edge: 依赖边 (from -> to)

状态流转:
  pending -> ready -> running -> done / failed
"""

import json
from pathlib import Path
from typing import Optional
from datetime import datetime

class TaskNode:
    """任务节点"""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    
    def __init__(self, task_id: str, name: str, dependencies: list = None):
        self.id = task_id
        self.name = name
        self.dependencies = dependencies or []
        self.status = self.PENDING
        self.created_at = datetime.now().isoformat()
        self.started_at = None
        self.completed_at = None
        self.result = None
        self.retry_count = 0
        
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "dependencies": self.dependencies,
            "status": self.status,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "result": self.result,
            "retry_count": self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data):
        node = cls(data["id"], data["name"], data.get("dependencies", []))
        node.status = data.get("status", cls.PENDING)
        node.created_at = data.get("created_at", datetime.now().isoformat())
        node.started_at = data.get("started_at")
        node.completed_at = data.get("completed_at")
        node.result = data.get("result")
        node.retry_count = data.get("retry_count", 0)
        return node


class TaskGraph:
    """任务依赖图管理器"""
    
    def __init__(self, data_file: str):
        self.data_file = Path(data_file)
        self.nodes: dict[str, TaskNode] = {}
        self._load()
    
    def _load(self):
        """从文件加载图数据"""
        if self.data_file.exists():
            with open(self.data_file) as f:
                data = json.load(f)
                for node_data in data.get("nodes", []):
                    node = TaskNode.from_dict(node_data)
                    self.nodes[node.id] = node
    
    def _save(self):
        """保存图数据到文件"""
        data = {
            "updated_at": datetime.now().isoformat(),
            "nodes": [node.to_dict() for node in self.nodes.values()]
        }
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)
    
    def add_task(self, task_id: str, name: str, dependencies: list = None) -> TaskNode:
        """添加新任务"""
        node = TaskNode(task_id, name, dependencies)
        self.nodes[task_id] = node
        self._update_ready_status()
        self._save()
        return node
    
    def _update_ready_status(self):
        """更新所有任务的ready状态"""
        for node in self.nodes.values():
            if node.status == TaskNode.PENDING:
                if self._can_run(node):
                    node.status = TaskNode.READY
    
    def _can_run(self, node: TaskNode) -> bool:
        """检查任务是否可以执行（所有依赖都已完成）"""
        if not node.dependencies:
            return True
        for dep_id in node.dependencies:
            dep_node = self.nodes.get(dep_id)
            if not dep_node or dep_node.status != TaskNode.DONE:
                return False
        return True
    
    def get_next_task(self) -> Optional[TaskNode]:
        """获取下一个可执行的任务"""
        ready_nodes = [n for n in self.nodes.values() if n.status == TaskNode.READY]
        # 按创建时间排序，返回最早创建的
        ready_nodes.sort(key=lambda x: x.created_at)
        return ready_nodes[0] if ready_nodes else None
    
    def start_task(self, task_id: str) -> bool:
        """开始执行任务"""
        node = self.nodes.get(task_id)
        if node and node.status == TaskNode.READY:
            node.status = TaskNode.RUNNING
            node.started_at = datetime.now().isoformat()
            self._save()
            return True
        return False
    
    def complete_task(self, task_id: str, result: str = None, success: bool = True):
        """完成任务"""
        node = self.nodes.get(task_id)
        if node:
            node.status = TaskNode.DONE if success else TaskNode.FAILED
            node.completed_at = datetime.now().isoformat()
            node.result = result
            if not success:
                node.retry_count += 1
            # 触发依赖任务检查
            self._update_ready_status()
            self._save()
    
    def get_status(self) -> dict:
        """获取图状态"""
        return {
            "total": len(self.nodes),
            "pending": len([n for n in self.nodes.values() if n.status == TaskNode.PENDING]),
            "ready": len([n for n in self.nodes.values() if n.status == TaskNode.READY]),
            "running": len([n for n in self.nodes.values() if n.status == TaskNode.RUNNING]),
            "done": len([n for n in self.nodes.values() if n.status == TaskNode.DONE]),
            "failed": len([n for n in self.nodes.values() if n.status == TaskNode.FAILED])
        }


# ========== 预定义任务模板 ==========

TASK_TEMPLATES = {
    "system_health": {
        "id": "system_health",
        "name": "系统健康检查",
        "dependencies": []
    },
    "website_monitor": {
        "id": "website_monitor", 
        "name": "网站监控",
        "dependencies": ["system_health"]
    },
    "data_analysis": {
        "id": "data_analysis",
        "name": "数据分析",
        "dependencies": ["website_monitor"]
    },
    "generate_report": {
        "id": "generate_report",
        "name": "生成报告",
        "dependencies": ["data_analysis"]
    },
    "send_notification": {
        "id": "send_notification",
        "name": "发送通知",
        "dependencies": ["generate_report"]
    }
}


if __name__ == "__main__":
    # 测试
    graph = TaskGraph("/tmp/task_graph.json")
    
    # 添加任务链
    for task_id, task_info in TASK_TEMPLATES.items():
        graph.add_task(task_id, task_info["name"], task_info["dependencies"])
    
    print("图状态:", graph.get_status())
    print("下一个任务:", graph.get_next_task().name if graph.get_next_task() else "无")