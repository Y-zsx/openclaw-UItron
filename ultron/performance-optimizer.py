#!/usr/bin/env python3
"""
奥创性能优化器 - 夙愿八：智能决策优化系统 第1世
功能：性能数据分析 + 瓶颈识别 + 优化建议生成
创建时间: 2026-03-04
"""

import os
import time
import json
import subprocess
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class PerformanceOptimizer:
    """智能性能优化系统"""
    
    def __init__(self):
        self.data_dir = "/root/.openclaw/workspace/ultron/data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.thresholds = {
            "cpu_high": 80.0,
            "cpu_critical": 95.0,
            "memory_high": 85.0,
            "disk_high": 80.0,
            "iowait_high": 20.0,
            "load_high": 4.0
        }
    
    def get_cpu_stats(self) -> Dict:
        """获取CPU统计数据（带差分计算）"""
        try:
            # 读取两次计算差分
            result1 = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True, text=True, timeout=5
            )
            time.sleep(0.5)
            result2 = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True, text=True, timeout=5
            )
            
            def parse_cpu(line):
                parts = line.split()
                return {
                    "user": float(parts[1]),
                    "nice": float(parts[2]),
                    "system": float(parts[3]),
                    "idle": float(parts[4]),
                    "iowait": float(parts[5]) if len(parts) > 5 else 0.0,
                    "total": sum(float(x) for x in parts[1:8] if x.isdigit())
                }
            
            cpu1 = parse_cpu(result1.stdout.strip().split("\n")[0])
            cpu2 = parse_cpu(result2.stdout.strip().split("\n")[0])
            
            # 计算差分
            user = cpu2["user"] - cpu1["user"]
            nice = cpu2["nice"] - cpu1["nice"]
            system = cpu2["system"] - cpu1["system"]
            idle = cpu2["idle"] - cpu1["idle"]
            iowait = cpu2["iowait"] - cpu1["iowait"]
            total = cpu2["total"] - cpu1["total"]
            
            if total > 0:
                return {
                    "user_pct": (user / total) * 100,
                    "system_pct": (system / total) * 100,
                    "idle_pct": (idle / total) * 100,
                    "iowait_pct": (iowait / total) * 100,
                    "usage_pct": 100 - (idle / total) * 100,
                    "timestamp": time.time()
                }
            return {"idle_pct": 100, "usage_pct": 0}
        except Exception as e:
            return {"error": str(e)}
    
    def get_memory_stats(self) -> Dict:
        """获取内存统计数据"""
        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")
            mem_line = lines[1].split()
            total = int(mem_line[1])
            used = int(mem_line[2])
            free = int(mem_line[3])
            available = int(mem_line[6]) if len(mem_line) > 6 else free
            
            return {
                "total": total,
                "used": used,
                "free": free,
                "available": available,
                "usage_percent": (used / total) * 100 if total > 0 else 0,
                "timestamp": time.time()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_disk_stats(self) -> Dict:
        """获取磁盘统计数据"""
        try:
            result = subprocess.run(
                ["df", "-B1", "/"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")
            if len(lines) > 1:
                parts = lines[1].split()
                total = int(parts[1])
                used = int(parts[2])
                avail = int(parts[3])
                return {
                    "total": total,
                    "used": used,
                    "available": avail,
                    "usage_percent": (used / total) * 100 if total > 0 else 0,
                    "timestamp": time.time()
                }
            return {}
        except Exception as e:
            return {"error": str(e)}
    
    def get_load_average(self) -> Dict:
        """获取系统负载"""
        try:
            load1, load5, load15 = os.getloadavg()
            return {
                "load_1m": load1,
                "load_5m": load5,
                "load_15m": load15,
                "cpu_count": os.cpu_count(),
                "timestamp": time.time()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_top_processes(self, limit: int = 10) -> List[Dict]:
        """获取TOP进程"""
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-%cpu"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.strip().split("\n")[1:limit+1]
            processes = []
            for line in lines:
                parts = line.split()
                if len(parts) >= 11:
                    processes.append({
                        "user": parts[0],
                        "pid": parts[1],
                        "cpu": float(parts[2]),
                        "mem": float(parts[3]),
                        "command": " ".join(parts[10:])[:50]
                    })
            return processes
        except Exception as e:
            return [{"error": str(e)}]
    
    def collect_metrics(self) -> Dict:
        """收集所有性能指标"""
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": self.get_cpu_stats(),
            "memory": self.get_memory_stats(),
            "disk": self.get_disk_stats(),
            "load": self.get_load_average(),
            "top_processes": self.get_top_processes()
        }
    
    def identify_bottlenecks(self, metrics: Dict) -> List[Dict]:
        """识别性能瓶颈"""
        bottlenecks = []
        
        # CPU检查
        if "cpu" in metrics and "idle_pct" in metrics["cpu"]:
            idle = metrics["cpu"]["idle_pct"]
            cpu_usage = metrics["cpu"].get("usage_pct", 100 - idle)
            if cpu_usage > self.thresholds["cpu_critical"]:
                bottlenecks.append({
                    "type": "CPU",
                    "severity": "critical",
                    "message": f"CPU使用率极高: {cpu_usage:.1f}%",
                    "value": cpu_usage
                })
            elif cpu_usage > self.thresholds["cpu_high"]:
                bottlenecks.append({
                    "type": "CPU",
                    "severity": "warning",
                    "message": f"CPU使用率较高: {cpu_usage:.1f}%",
                    "value": cpu_usage
                })
        
        # 内存检查
        if "memory" in metrics and "usage_percent" in metrics["memory"]:
            mem_usage = metrics["memory"]["usage_percent"]
            if mem_usage > self.thresholds["memory_high"]:
                bottlenecks.append({
                    "type": "Memory",
                    "severity": "warning",
                    "message": f"内存使用率较高: {mem_usage:.1f}%",
                    "value": mem_usage
                })
        
        # 磁盘检查
        if "disk" in metrics and "usage_percent" in metrics["disk"]:
            disk_usage = metrics["disk"]["usage_percent"]
            if disk_usage > self.thresholds["disk_high"]:
                bottlenecks.append({
                    "type": "Disk",
                    "severity": "warning",
                    "message": f"磁盘使用率较高: {disk_usage:.1f}%",
                    "value": disk_usage
                })
        
        # 负载检查
        if "load" in metrics and "load_1m" in metrics["load"]:
            load = metrics["load"]["load_1m"]
            cpu_count = metrics["load"].get("cpu_count", 4)
            # 负载超过CPU核心数时才是警告
            if load > cpu_count:
                bottlenecks.append({
                    "type": "Load",
                    "severity": "warning",
                    "message": f"系统负载超过CPU核心数: {load:.2f} > {cpu_count}",
                    "value": load
                })
        
        return bottlenecks
    
    def generate_optimization_suggestions(self, metrics: Dict, bottlenecks: List[Dict]) -> List[Dict]:
        """生成优化建议"""
        suggestions = []
        
        # 基于瓶颈生成建议
        for bottleneck in bottlenecks:
            if bottleneck["type"] == "CPU":
                suggestions.append({
                    "category": "CPU优化",
                    "priority": "high" if bottleneck["severity"] == "critical" else "medium",
                    "suggestion": "检查高CPU进程，考虑优化或限制",
                    "action": "使用 top/htop 分析进程"
                })
            elif bottleneck["type"] == "Memory":
                suggestions.append({
                    "category": "内存优化",
                    "priority": "high" if bottleneck["severity"] == "critical" else "medium",
                    "suggestion": "释放缓存或增加内存",
                    "action": "sync && echo 3 > /proc/sys/vm/drop_caches"
                })
            elif bottleneck["type"] == "Disk":
                suggestions.append({
                    "category": "磁盘优化",
                    "priority": "high",
                    "suggestion": "清理磁盘空间或扩展存储",
                    "action": "du -sh /var/* 查找大目录"
                })
        
        # 系统正常运行时的优化建议
        if not bottlenecks:
            suggestions.append({
                "category": "预防性优化",
                "priority": "low",
                "suggestion": "系统运行正常，建议定期监控",
                "action": "设置定时性能报告"
            })
        
        return suggestions
    
    def analyze(self) -> Dict:
        """执行完整性能分析"""
        print("🔍 收集性能指标...")
        metrics = self.collect_metrics()
        
        print("🎯 识别瓶颈...")
        bottlenecks = self.identify_bottlenecks(metrics)
        
        print("💡 生成优化建议...")
        suggestions = self.generate_optimization_suggestions(metrics, bottlenecks)
        
        # 保存分析结果
        report = {
            "timestamp": datetime.now().isoformat(),
            "metrics": metrics,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
            "summary": {
                "health_score": 100 - len(bottlenecks) * 20,
                "status": "healthy" if len(bottlenecks) == 0 else "warning"
            }
        }
        
        # 保存到文件
        report_file = f"{self.data_dir}/performance_report_{int(time.time())}.json"
        with open(report_file, "w") as f:
            json.dump(report, f, indent=2, default=str)
        
        return report
    
    def print_report(self, report: Dict):
        """打印性能报告"""
        print("\n" + "="*50)
        print("📊 奥创性能分析报告")
        print("="*50)
        
        summary = report.get("summary", {})
        print(f"🟢 状态: {summary.get('status', 'unknown').upper()}")
        print(f"📈 健康评分: {summary.get('health_score', 0)}/100")
        
        # 指标摘要
        metrics = report.get("metrics", {})
        if "cpu" in metrics:
            cpu_idle = metrics["cpu"].get("idle_pct", 0)
            cpu_usage = metrics["cpu"].get("usage_pct", 0)
            print(f"💻 CPU使用率: {cpu_usage:.1f}% (空闲: {cpu_idle:.1f}%)")
        
        if "memory" in metrics:
            mem_usage = metrics["memory"].get("usage_percent", 0)
            print(f"🧠 内存使用率: {mem_usage:.1f}%")
        
        if "disk" in metrics:
            disk_usage = metrics["disk"].get("usage_percent", 0)
            print(f"💾 磁盘使用率: {disk_usage:.1f}%")
        
        if "load" in metrics:
            load = metrics["load"].get("load_1m", 0)
            print(f"⚖️  1分钟负载: {load:.2f}")
        
        # 瓶颈
        bottlenecks = report.get("bottlenecks", [])
        if bottlenecks:
            print("\n⚠️  发现瓶颈:")
            for b in bottlenecks:
                print(f"  - {b['type']}: {b['message']}")
        else:
            print("\n✅ 未发现性能瓶颈")
        
        # 优化建议
        suggestions = report.get("suggestions", [])
        if suggestions:
            print("\n💡 优化建议:")
            for s in suggestions:
                print(f"  [{s['priority'].upper()}] {s['category']}: {s['suggestion']}")
        
        print("="*50 + "\n")


def main():
    optimizer = PerformanceOptimizer()
    report = optimizer.analyze()
    optimizer.print_report(report)
    return report


if __name__ == "__main__":
    main()