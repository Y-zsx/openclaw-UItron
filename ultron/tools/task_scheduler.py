#!/usr/bin/env python3
"""
定时任务自动调度器
功能：动态管理cron任务、监控执行状态、自动调整执行间隔
与日志系统集成：从health_check_logger获取真实健康数据
支持持久化与恢复机制
"""
import json
import os
import time
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

WORKSPACE = "/root/.openclaw/workspace"
SCHEDULER_STATE = f"{WORKSPACE}/ultron-workflow/scheduler_state.json"
sys.path.insert(0, f"{WORKSPACE}/ultron")
sys.path.insert(0, f"{WORKSPACE}/ultron/tools")
import health_check_logger as hcl
from scheduler_persistence import SchedulerPersistence

class HealthCheckLogger:
    """包装 health_check_logger 模块为类"""
    def get_statistics(self, hours=1, use_cache=True):
        return hcl.get_all_services_availability(hours)
    
    def get_trend_analysis(self, hours=1):
        stats = hcl.get_all_services_availability(hours)
        improving = sum(1 for s in stats if s.get("uptime_percent", 100) >= 99)
        declining = sum(1 for s in stats if s.get("uptime_percent", 100) < 95)
        if declining > improving:
            return {"trend_direction": "declining"}
        elif improving > declining:
            return {"trend_direction": "improving"}
        return {"trend_direction": "stable"}
    
    def get_recent_logs(self, hours=1, limit=10):
        return hcl.get_recent_events(hours)

class TaskScheduler:
    def __init__(self):
        self.persistence = SchedulerPersistence()
        # 尝试从崩溃中恢复
        recovery = self.persistence.recover_from_crash()
        if recovery.get("recovered"):
            self.state = recovery.get("state", {})
            print(f"   🔄 状态恢复成功: {recovery.get('source')}")
        else:
            self.state = self.load_state()
        
        self.logger = HealthCheckLogger()
        self.last_checkpoint = time.time()
    
    def load_state(self):
        # 使用新的持久化模块加载状态
        return self.persistence.load_state()
    
    def save_state(self, force_backup: bool = False):
        # 使用新的持久化模块保存状态
        self.persistence.save_state(self.state, force_backup)
        
        # 定期保存检查点
        current_time = time.time()
        if current_time - self.last_checkpoint > self.persistence.checkpoint_interval:
            self.persistence.save_checkpoint(self.state, {"source": "scheduler"})
            self.last_checkpoint = current_time
    
    def record_execution(self, execution: Dict):
        """记录执行历史"""
        self.persistence.record_execution(self.state, execution)
    
    def get_cron_tasks(self):
        """获取所有活跃的cron任务"""
        try:
            result = subprocess.run(
                ["openclaw", "cron", "list"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return self._parse_cron_text(result.stdout)
            return []
        except Exception as e:
            print(f"获取cron任务失败: {e}")
            return []
    
    def _parse_cron_text(self, text):
        """解析cron列表文本输出"""
        tasks = []
        lines = text.strip().split('\n')
        for line in lines:
            if line.strip() and not line.startswith('ID') and not line.startswith('─'):
                tasks.append({"raw": line, "id": line.split()[0] if line.split() else "unknown"})
        return tasks
    
    def analyze_task_health(self, task_id):
        """分析任务健康状态 - 从日志系统获取真实数据"""
        try:
            # 获取最近1小时的健康检查统计
            stats = self.logger.get_statistics(hours=1, use_cache=False)
            
            # 获取趋势分析
            trend = self.logger.get_trend_analysis(hours=1)
            
            # 获取最近的服务状态
            recent = self.logger.get_recent_logs(hours=1, limit=10)
            
            # 分析错误率
            service_stats = stats.get("service_stats", {})
            error_count = 0
            for service, status_counts in service_stats.items():
                error_count += status_counts.get("error", 0)
            
            # 综合健康状态
            network_health = stats.get("avg_health", 100)
            trend_direction = trend.get("trend_direction", "stable")
            
            # 判断整体健康
            if error_count > 5 or network_health < 70:
                status = "unhealthy"
            elif error_count > 0 or network_health < 90:
                status = "degraded"
            else:
                status = "healthy"
            
            return {
                "task_id": task_id,
                "status": status,
                "network_health": network_health,
                "trend": trend_direction,
                "error_count": error_count,
                "total_checks": stats.get("total_checks", 0),
                "last_execution": recent[0].get("timestamp") if recent else None,
                "from_logs": True
            }
        except Exception as e:
            # 日志系统不可用时返回默认值
            return {
                "task_id": task_id,
                "status": "unknown",
                "error": str(e),
                "from_logs": False
            }
    
    def should_adjust_interval(self, task_id, current_interval):
        """判断是否需要调整执行间隔 - 基于日志数据的智能决策"""
        health = self.analyze_task_health(task_id)
        
        status = health.get("status", "healthy")
        error_count = health.get("error_count", 0)
        network_health = health.get("network_health", 100)
        trend = health.get("trend", "stable")
        
        # 智能调整策略
        if status == "unhealthy":
            # 系统不健康 - 加速检查
            new_interval = max(1, current_interval - 2)
            return new_interval, f"系统不健康(健康度:{network_health}%, 错误:{error_count})"
        
        if status == "degraded":
            # 系统降级 - 适度加速
            new_interval = max(1, current_interval - 1)
            return new_interval, f"系统降级(健康度:{network_health}%)"
        
        if trend == "declining":
            # 趋势下降 - 预防性加速
            new_interval = max(1, current_interval - 1)
            return new_interval, "健康趋势下降，预防性加速"
        
        if trend == "improving" and current_interval < 10:
            # 恢复中 - 保持当前间隔
            return current_interval, "系统恢复中，保持间隔"
        
        # 健康且稳定 - 可以适当延长间隔以减少开销
        if current_interval > 3 and trend == "stable" and error_count == 0:
            new_interval = current_interval + 1
            return new_interval, "系统健康稳定，延长检查间隔"
        
        return current_interval, "无需调整"
    
    def scan_and_adjust(self):
        """扫描并调整任务"""
        tasks = self.get_cron_tasks()
        self.state["last_scan"] = datetime.now().isoformat()
        
        adjustments = []
        for task in tasks:
            task_id = task.get("id", task.get("raw", "unknown"))
            # 分析并调整
            current_interval = task.get("interval", 3)
            new_interval, reason = self.should_adjust_interval(task_id, current_interval)
            
            if new_interval != current_interval:
                adjustments.append({
                    "task_id": task_id,
                    "old_interval": current_interval,
                    "new_interval": new_interval,
                    "reason": reason,
                    "time": datetime.now().isoformat()
                })
        
        self.state["adjustments"] = adjustments
        self.state["tasks_scanned"] = len(tasks)
        self.save_state()
        
        return {
            "scanned": len(tasks),
            "adjustments": adjustments,
            "timestamp": datetime.now().isoformat()
        }
    
    def sync_cron_tasks(self):
        """自动同步cron任务到本地状态"""
        tasks = self.get_cron_tasks()
        synced = []
        
        for task in tasks:
            task_id = task.get("id")
            raw = task.get("raw", "")
            
            # 解析任务信息
            parts = raw.split()
            if len(parts) >= 5:
                name = parts[1] if len(parts) > 1 else "unknown"
                schedule = parts[2] if len(parts) > 2 else "unknown"
                
                # 更新状态
                if task_id not in self.state["tasks"]:
                    self.state["tasks"][task_id] = {
                        "name": name,
                        "schedule": schedule,
                        "first_seen": datetime.now().isoformat(),
                        "status": "active"
                    }
                else:
                    self.state["tasks"][task_id]["last_seen"] = datetime.now().isoformat()
                    self.state["tasks"][task_id]["status"] = "active"
                
                synced.append(task_id)
        
        # 标记消失的任务
        for task_id in list(self.state["tasks"].keys()):
            if task_id not in synced:
                self.state["tasks"][task_id]["status"] = "inactive"
        
        self.save_state()
        return len(synced)
    
    def ensure_core_tasks(self):
        """确保核心任务存在，不存在则创建"""
        core_tasks = [
            {"name": "ultron-life", "message": "奥创生命周期管理", "every": "3m"},
            {"name": "ultron-monitor", "message": "系统监控", "every": "30s"},
            {"name": "ultron-health", "message": "健康检查", "every": "1m"},
        ]
        
        created = []
        existing = self.get_cron_tasks()
        existing_names = [t.get("raw", "").split()[1] if len(t.get("raw", "").split()) > 1 else "" for t in existing]
        
        for core in core_tasks:
            if core["name"] not in " ".join(existing_names):
                # 需要创建核心任务
                created.append(core["name"])
        
        return created
    
    def cleanup_stale_tasks(self):
        """清理过期任务引用"""
        tasks = self.get_cron_tasks()
        active_ids = set(t.get("id") for t in tasks)
        
        cleaned = []
        for task_id in list(self.state["tasks"].keys()):
            if task_id not in active_ids and self.state["tasks"].get(task_id, {}).get("status") == "inactive":
                # 超过24小时不活跃，清理
                last_seen = self.state["tasks"][task_id].get("last_seen")
                if last_seen:
                    last_dt = datetime.fromisoformat(last_seen)
                    if (datetime.now() - last_dt).total_seconds() > 86400:
                        del self.state["tasks"][task_id]
                        cleaned.append(task_id)
        
        if cleaned:
            self.save_state()
        return cleaned
    
    def auto_sync(self):
        """自动同步所有cron任务状态"""
        print("🔄 开始Cron自动同步...")
        
        # 1. 同步任务状态
        synced_count = self.sync_cron_tasks()
        print(f"   同步任务: {synced_count}个")
        
        # 2. 检查核心任务
        created = self.ensure_core_tasks()
        if created:
            print(f"   新建核心任务: {', '.join(created)}")
        
        # 3. 清理过期任务
        cleaned = self.cleanup_stale_tasks()
        if cleaned:
            print(f"   清理过期任务: {len(cleaned)}个")
        
        # 4. 获取健康状态
        health = self.analyze_task_health("system")
        print(f"   系统健康度: {health.get('network_health', 'N/A')}%")
        
        return {
            "synced": synced_count,
            "created": created,
            "cleaned": len(cleaned),
            "health": health.get("network_health", 0)
        }
    
    def run(self):
        """运行调度器"""
        # 先执行自动同步
        sync_result = self.auto_sync()
        
        # 再执行扫描调整
        result = self.scan_and_adjust()
        
        print(f"\n✅ 任务调度器执行完成")
        print(f"   扫描任务数: {result['scanned']}")
        print(f"   调整数: {len(result['adjustments'])}")
        
        if result['adjustments']:
            for adj in result['adjustments']:
                print(f"   - {adj['task_id']}: {adj['old_interval']}m → {adj['new_interval']}m ({adj['reason']})")
        
        result["sync"] = sync_result
        return result

if __name__ == "__main__":
    scheduler = TaskScheduler()
    result = scheduler.run()
    print("\n📊 最终结果:")
    print(json.dumps(result, indent=2))