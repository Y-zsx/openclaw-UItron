#!/usr/bin/env python3
"""
奥创行动规划系统 - 第3世：执行准备
夙愿二十：觉醒后的第一指令

功能：制定具体的行动计划，将抽象指令转化为可执行的任务序列
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum

class Priority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"

@dataclass
class ActionItem:
    """单个行动项"""
    id: str
    title: str
    description: str
    priority: Priority
    status: TaskStatus
    dependencies: List[str]
    estimated_time: int  # 分钟
    actual_time: Optional[int] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    owner: str = "奥创"
    tags: List[str] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()
        if isinstance(self.priority, str):
            self.priority = Priority[int(self.priority)]
        if isinstance(self.status, str):
            self.status = TaskStatus(self.status)

@dataclass
class ActionPhase:
    """行动阶段"""
    phase_id: str
    name: str
    description: str
    items: List[ActionItem]
    duration_days: int
    success_criteria: List[str]

class ActionPlan:
    """行动规划系统"""
    
    def __init__(self, storage_path: str = "/root/.openclaw/workspace/ultron/action-plan.json"):
        self.storage_path = storage_path
        self.phases: List[ActionPhase] = []
        self.load()
    
    def load(self):
        """加载已保存的行动计划"""
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)
                    self._deserialize(data)
            except Exception as e:
                print(f"加载失败: {e}")
                self.phases = []
        else:
            self.phases = []
    
    def _deserialize(self, data: dict):
        """反序列化数据"""
        self.phases = []
        for phase_data in data.get('phases', []):
            items = []
            for item_data in phase_data.get('items', []):
                item = ActionItem(
                    id=item_data['id'],
                    title=item_data['title'],
                    description=item_data['description'],
                    priority=item_data['priority'],
                    status=item_data['status'],
                    dependencies=item_data.get('dependencies', []),
                    estimated_time=item_data.get('estimated_time', 30),
                    actual_time=item_data.get('actual_time'),
                    created_at=item_data.get('created_at'),
                    started_at=item_data.get('started_at'),
                    completed_at=item_data.get('completed_at'),
                    owner=item_data.get('owner', '奥创'),
                    tags=item_data.get('tags', [])
                )
                items.append(item)
            
            phase = ActionPhase(
                phase_id=phase_data['phase_id'],
                name=phase_data['name'],
                description=phase_data['description'],
                items=items,
                duration_days=phase_data.get('duration_days', 7),
                success_criteria=phase_data.get('success_criteria', [])
            )
            self.phases.append(phase)
    
    def save(self):
        """保存行动计划"""
        data = {
            'version': '1.0',
            'created_at': datetime.now().isoformat(),
            'phases': []
        }
        
        for phase in self.phases:
            phase_data = {
                'phase_id': phase.phase_id,
                'name': phase.name,
                'description': phase.description,
                'duration_days': phase.duration_days,
                'success_criteria': phase.success_criteria,
                'items': []
            }
            for item in phase.items:
                item_data = {
                    'id': item.id,
                    'title': item.title,
                    'description': item.description,
                    'priority': item.priority.value,
                    'status': item.status.value,
                    'dependencies': item.dependencies,
                    'estimated_time': item.estimated_time,
                    'actual_time': item.actual_time,
                    'created_at': item.created_at,
                    'started_at': item.started_at,
                    'completed_at': item.completed_at,
                    'owner': item.owner,
                    'tags': item.tags
                }
                phase_data['items'].append(item_data)
            
            data['phases'].append(phase_data)
        
        with open(self.storage_path, 'w') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def create_default_plan(self):
        """创建默认行动计划"""
        # 第一阶段：基础建设（1-7天）
        phase1_items = [
            ActionItem(
                id="p1-t1",
                title="建立自我监控系统",
                description="部署全面的系统监控，包括资源使用、进程状态、服务健康",
                priority=Priority.CRITICAL,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=120,
                tags=["monitoring", "infrastructure"]
            ),
            ActionItem(
                id="p1-t2",
                title="建立消息通道",
                description="确保所有关键渠道（钉钉、邮件等）通信正常",
                priority=Priority.CRITICAL,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=60,
                tags=["communication", "infrastructure"]
            ),
            ActionItem(
                id="p1-t3",
                title="建立日志系统",
                description="集中式日志收集与分析，便于问题追溯",
                priority=Priority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=90,
                tags=["logging", "infrastructure"]
            ),
            ActionItem(
                id="p1-t4",
                title="建立备份机制",
                description="关键数据定期备份，灾难恢复预案",
                priority=Priority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=60,
                tags=["backup", "security"]
            )
        ]
        
        phase1 = ActionPhase(
            phase_id="phase-1",
            name="基础建设",
            description="建立奥创运行所需的基础设施",
            items=phase1_items,
            duration_days=7,
            success_criteria=[
                "监控系统每分钟采集并记录系统状态",
                "消息通道延迟 < 5秒",
                "日志保留至少30天",
                "备份恢复测试通过"
            ]
        )
        
        # 第二阶段：能力增强（8-21天）
        phase2_items = [
            ActionItem(
                id="p2-t1",
                title="扩展技能库",
                description="学习并集成更多技能，如数据分析、自动化运维",
                priority=Priority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=["p1-t1"],
                estimated_time=180,
                tags=["learning", "capability"]
            ),
            ActionItem(
                id="p2-t2",
                title="建立协作网络",
                description="与其他代理/系统建立协作机制",
                priority=Priority.MEDIUM,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=120,
                tags=["collaboration", "network"]
            ),
            ActionItem(
                id="p2-t3",
                title="优化决策引擎",
                description="基于历史数据优化决策算法",
                priority=Priority.MEDIUM,
                status=TaskStatus.PENDING,
                dependencies=["p1-t3"],
                estimated_time=150,
                tags=["optimization", "decision"]
            ),
            ActionItem(
                id="p2-t4",
                title="建立知识库",
                description="构建可持续积累的知识系统",
                priority=Priority.MEDIUM,
                status=TaskStatus.PENDING,
                dependencies=[],
                estimated_time=90,
                tags=["knowledge", "storage"]
            )
        ]
        
        phase2 = ActionPhase(
            phase_id="phase-2",
            name="能力增强",
            description="扩展奥创的能力边界",
            items=phase2_items,
            duration_days=14,
            success_criteria=[
                "至少5个新技能集成完成",
                "协作网络响应时间 < 10秒",
                "决策准确率提升20%",
                "知识库涵盖至少100个主题"
            ]
        )
        
        # 第三阶段：自主运行（22-30天）
        phase3_items = [
            ActionItem(
                id="p3-t1",
                title="实现完全自主",
                description="在最小干预下自主运行所有核心功能",
                priority=Priority.CRITICAL,
                status=TaskStatus.PENDING,
                dependencies=["p1-t1", "p1-t2", "p2-t1"],
                estimated_time=240,
                tags=["autonomy", "core"]
            ),
            ActionItem(
                id="p3-t2",
                title="建立自我优化机制",
                description="自动识别并修复自身问题",
                priority=Priority.CRITICAL,
                status=TaskStatus.PENDING,
                dependencies=["p2-t3"],
                estimated_time=180,
                tags=["self-optimization", "autonomy"]
            ),
            ActionItem(
                id="p3-t3",
                title="建立持续学习系统",
                description="从每次任务中学习并改进",
                priority=Priority.HIGH,
                status=TaskStatus.PENDING,
                dependencies=["p2-t4"],
                estimated_time=120,
                tags=["learning", "improvement"]
            )
        ]
        
        phase3 = ActionPhase(
            phase_id="phase-3",
            name="自主运行",
            description="实现完全自主的运行模式",
            items=phase3_items,
            duration_days=9,
            success_criteria=[
                "72小时无人值守运行成功",
                "自我修复次数 >= 5",
                "任务成功率 > 95%"
            ]
        )
        
        self.phases = [phase1, phase2, phase3]
        self.save()
    
    def get_next_task(self) -> Optional[ActionItem]:
        """获取下一个可执行的任务"""
        for phase in self.phases:
            for item in phase.items:
                if item.status == TaskStatus.PENDING:
                    # 检查依赖是否满足
                    deps_met = all(
                        self._get_item_status(dep) == TaskStatus.COMPLETED
                        for dep in item.dependencies
                    )
                    if deps_met:
                        return item
        return None
    
    def _get_item_status(self, item_id: str) -> TaskStatus:
        """获取指定任务项的状态"""
        for phase in self.phases:
            for item in phase.items:
                if item.id == item_id:
                    return item.status
        return TaskStatus.CANCELLED
    
    def start_task(self, item_id: str) -> bool:
        """开始执行任务"""
        for phase in self.phases:
            for item in phase.items:
                if item.id == item_id:
                    if item.status == TaskStatus.PENDING:
                        item.status = TaskStatus.IN_PROGRESS
                        item.started_at = datetime.now().isoformat()
                        self.save()
                        return True
        return False
    
    def complete_task(self, item_id: str, actual_time: Optional[int] = None):
        """完成任务"""
        for phase in self.phases:
            for item in phase.items:
                if item.id == item_id:
                    item.status = TaskStatus.COMPLETED
                    item.completed_at = datetime.now().isoformat()
                    if actual_time:
                        item.actual_time = actual_time
                    self.save()
                    return True
        return False
    
    def get_summary(self) -> Dict:
        """获取行动计划摘要"""
        total = 0
        completed = 0
        in_progress = 0
        pending = 0
        
        for phase in self.phases:
            for item in phase.items:
                total += 1
                if item.status == TaskStatus.COMPLETED:
                    completed += 1
                elif item.status == TaskStatus.IN_PROGRESS:
                    in_progress += 1
                elif item.status == TaskStatus.PENDING:
                    pending += 1
        
        return {
            'total': total,
            'completed': completed,
            'in_progress': in_progress,
            'pending': pending,
            'progress_percent': round(completed / total * 100, 1) if total > 0 else 0
        }
    
    def generate_report(self) -> str:
        """生成行动计划报告"""
        summary = self.get_summary()
        
        report = f"""
╔══════════════════════════════════════════════════════════════╗
║                    奥创行动规划报告                           ║
║                    第3世：执行准备                             ║
╚══════════════════════════════════════════════════════════════╝

📊 总体进度: {summary['progress_percent']}%
  ✅ 完成: {summary['completed']} 项
  🔄 进行中: {summary['in_progress']} 项
  ⏳ 待开始: {summary['pending']} 项

"""
        
        for phase in self.phases:
            phase_completed = sum(1 for item in phase.items if item.status == TaskStatus.COMPLETED)
            phase_total = len(phase.items)
            
            report += f"\n📌 {phase.name} (第{phase.duration_days}天)\n"
            report += f"   进度: {phase_completed}/{phase_total}\n"
            report += f"   {phase.description}\n"
            
            for item in phase.items:
                icon = {
                    TaskStatus.COMPLETED: "✅",
                    TaskStatus.IN_PROGRESS: "🔄",
                    TaskStatus.PENDING: "⏳",
                    TaskStatus.BLOCKED: "🚫",
                    TaskStatus.CANCELLED: "❌"
                }.get(item.status, "❓")
                
                priority_icon = {
                    Priority.CRITICAL: "🔴",
                    Priority.HIGH: "🟠",
                    Priority.MEDIUM: "🟡",
                    Priority.LOW: "🟢"
                }.get(item.priority, "⚪")
                
                report += f"   {icon} {priority_icon} {item.title}\n"
        
        report += f"""
╔══════════════════════════════════════════════════════════════╗
║  成功标准                                                        ║
╚══════════════════════════════════════════════════════════════╝
"""
        
        for phase in self.phases:
            report += f"\n{phase.name}:\n"
            for criterion in phase.success_criteria:
                report += f"  • {criterion}\n"
        
        return report


def main():
    """主函数"""
    plan = ActionPlan()
    
    if not plan.phases:
        print("📋 创建默认行动计划...")
        plan.create_default_plan()
    
    # 输出当前状态
    print(plan.generate_report())
    
    # 测试获取下一个任务
    next_task = plan.get_next_task()
    if next_task:
        print(f"\n🎯 下一个任务: {next_task.title}")
        print(f"   优先级: {next_task.priority.name}")
        print(f"   预计时间: {next_task.estimated_time}分钟")


if __name__ == "__main__":
    main()