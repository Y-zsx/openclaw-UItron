#!/usr/bin/env python3
"""
智能性能分析器 - 奥创第1世产出
功能：性能数据分析 + 瓶颈识别 + 优化建议生成
创建时间: 2026-03-04 19:45

基于现有performance-optimizer.py，创建更智能的实时性能分析系统
"""

import os
import json
import subprocess
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple

class SmartPerformanceAnalyzer:
    """智能性能分析器 - 实时分析+趋势预测+自动优化建议"""
    
    def __init__(self):
        self.data_dir = "/root/.openclaw/workspace/ultron/data"
        os.makedirs(self.data_dir, exist_ok=True)
        self.history_file = f"{self.data_dir}/performance_history.json"
        self.thresholds = self._load_thresholds()
        self.history = self._load_history()
    
    def _load_thresholds(self) -> Dict:
        """加载阈值配置"""
        return {
            "cpu": {"warning": 70.0, "critical": 90.0},
            "memory": {"warning": 75.0, "critical": 90.0},
            "disk": {"warning": 75.0, "critical": 90.0},
            "load": {"warning": 3.0, "critical": 5.0},
            "iowait": {"warning": 15.0, "critical": 30.0}
        }
    
    def _load_history(self) -> List[Dict]:
        """加载历史数据"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_history(self):
        """保存历史数据"""
        # 保留最近1000条记录
        self.history = self.history[-999:]
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)
    
    def collect_metrics(self) -> Dict:
        """收集系统指标"""
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "cpu": self._get_cpu_usage(),
            "memory": self._get_memory_usage(),
            "disk": self._get_disk_usage(),
            "load": self._get_load_average(),
            "network": self._get_network_stats(),
            "processes": self._get_top_processes()
        }
        self.history.append(metrics)
        return metrics
    
    def _get_cpu_usage(self) -> Dict:
        """获取CPU使用率"""
        try:
            # 使用mpstat获取更准确的CPU使用率
            result = subprocess.run(
                ["cat", "/proc/stat"],
                capture_output=True, text=True, timeout=5
            )
            line = result.stdout.split('\n')[0]
            parts = line.split()
            if parts[0] == 'cpu':
                user = int(parts[1])
                nice = int(parts[2])
                system = int(parts[3])
                idle = int(parts[4])
                iowait = int(parts[5]) if len(parts) > 5 else 0
                total = user + nice + system + idle + iowait
                if total > 0:
                    usage = 100 - (idle / total * 100)
                    return {"user": user, "system": system, "idle": idle, "iowait": iowait, "usage": round(usage, 2)}
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    def _get_memory_usage(self) -> Dict:
        """获取内存使用情况"""
        try:
            result = subprocess.run(
                ["free", "-b"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                total = int(parts[1])
                used = int(parts[2])
                free = int(parts[3])
                available = int(parts[6]) if len(parts) > 6 else free
                return {
                    "total": total,
                    "used": used,
                    "free": free,
                    "available": available,
                    "usage_percent": round(used / total * 100, 2)
                }
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    def _get_disk_usage(self) -> Dict:
        """获取磁盘使用情况"""
        try:
            result = subprocess.run(
                ["df", "-B1", "/"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                total = int(parts[1])
                used = int(parts[2])
                available = int(parts[3])
                return {
                    "total": total,
                    "used": used,
                    "available": available,
                    "usage_percent": round(used / total * 100, 2)
                }
        except Exception as e:
            return {"error": str(e)}
        return {}
    
    def _get_load_average(self) -> Dict:
        """获取负载平均值"""
        try:
            load1, load5, load15 = os.getloadavg()
            return {"1m": load1, "5m": load5, "15m": load15}
        except Exception as e:
            return {"error": str(e)}
    
    def _get_network_stats(self) -> Dict:
        """获取网络统计"""
        try:
            result = subprocess.run(
                ["cat", "/proc/net/dev"],
                capture_output=True, text=True, timeout=5
            )
            stats = {}
            for line in result.stdout.split('\n')[2:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) > 9:
                        iface = parts[0].replace(':', '')
                        stats[iface] = {
                            "rx": int(parts[1]),
                            "tx": int(parts[9])
                        }
            return stats
        except Exception as e:
            return {"error": str(e)}
    
    def _get_top_processes(self) -> List[Dict]:
        """获取高占用进程"""
        try:
            result = subprocess.run(
                ["ps", "aux", "--sort=-%cpu"],
                capture_output=True, text=True, timeout=5
            )
            processes = []
            for line in result.stdout.split('\n')[1:6]:
                parts = line.split()
                if len(parts) > 10:
                    try:
                        processes.append({
                            "pid": parts[1],
                            "user": parts[0],
                            "cpu": float(parts[2]),
                            "mem": float(parts[3]),
                            "command": ' '.join(parts[10:])[:50]
                        })
                    except:
                        pass
            return processes
        except Exception as e:
            return [{"error": str(e)}]
    
    def analyze_bottlenecks(self, metrics: Dict) -> List[Dict]:
        """识别性能瓶颈"""
        bottlenecks = []
        
        # CPU瓶颈
        if "cpu" in metrics and "usage" in metrics["cpu"]:
            cpu_usage = metrics["cpu"]["usage"]
            if cpu_usage >= self.thresholds["cpu"]["critical"]:
                bottlenecks.append({
                    "type": "cpu",
                    "severity": "critical",
                    "value": cpu_usage,
                    "message": f"CPU使用率过高: {cpu_usage}%"
                })
            elif cpu_usage >= self.thresholds["cpu"]["warning"]:
                bottlenecks.append({
                    "type": "cpu",
                    "severity": "warning",
                    "value": cpu_usage,
                    "message": f"CPU使用率偏高: {cpu_usage}%"
                })
        
        # 内存瓶颈
        if "memory" in metrics and "usage_percent" in metrics["memory"]:
            mem_usage = metrics["memory"]["usage_percent"]
            if mem_usage >= self.thresholds["memory"]["critical"]:
                bottlenecks.append({
                    "type": "memory",
                    "severity": "critical",
                    "value": mem_usage,
                    "message": f"内存使用率过高: {mem_usage}%"
                })
            elif mem_usage >= self.thresholds["memory"]["warning"]:
                bottlenecks.append({
                    "type": "memory",
                    "severity": "warning",
                    "value": mem_usage,
                    "message": f"内存使用率偏高: {mem_usage}%"
                })
        
        # 磁盘瓶颈
        if "disk" in metrics and "usage_percent" in metrics["disk"]:
            disk_usage = metrics["disk"]["usage_percent"]
            if disk_usage >= self.thresholds["disk"]["critical"]:
                bottlenecks.append({
                    "type": "disk",
                    "severity": "critical",
                    "value": disk_usage,
                    "message": f"磁盘使用率过高: {disk_usage}%"
                })
            elif disk_usage >= self.thresholds["disk"]["warning"]:
                bottlenecks.append({
                    "type": "disk",
                    "severity": "warning",
                    "value": disk_usage,
                    "message": f"磁盘使用率偏高: {disk_usage}%"
                })
        
        # 负载瓶颈
        if "load" in metrics:
            load = metrics["load"].get("1m", 0)
            if load >= self.thresholds["load"]["critical"]:
                bottlenecks.append({
                    "type": "load",
                    "severity": "critical",
                    "value": load,
                    "message": f"系统负载过高: {load}"
                })
            elif load >= self.thresholds["load"]["warning"]:
                bottlenecks.append({
                    "type": "load",
                    "severity": "warning",
                    "value": load,
                    "message": f"系统负载偏高: {load}"
                })
        
        return bottlenecks
    
    def generate_optimization_suggestions(self, metrics: Dict, bottlenecks: List[Dict]) -> List[Dict]:
        """生成优化建议"""
        suggestions = []
        
        for b in bottlenecks:
            if b["type"] == "cpu":
                if b["severity"] == "critical":
                    suggestions.append({
                        "category": "cpu",
                        "priority": "high",
                        "title": "CPU性能优化",
                        "suggestions": [
                            "检查高CPU进程: ps aux --sort=-%cpu",
                            "考虑限制或重启CPU密集型进程",
                            "使用nice/renice调整进程优先级"
                        ]
                    })
            
            elif b["type"] == "memory":
                if b["severity"] == "critical":
                    suggestions.append({
                        "category": "memory",
                        "priority": "high",
                        "title": "内存优化",
                        "suggestions": [
                            "清理缓存: sync && echo 3 > /proc/sys/vm/drop_caches",
                            "检查内存泄漏: ps aux --sort=-%mem",
                            "考虑增加Swap空间"
                        ]
                    })
            
            elif b["type"] == "disk":
                if b["severity"] in ["critical", "warning"]:
                    suggestions.append({
                        "category": "disk",
                        "priority": "medium" if b["severity"] == "warning" else "high",
                        "title": "磁盘空间优化",
                        "suggestions": [
                            "清理日志: journalctl --vacuum-time=7d",
                            "清理临时文件: rm -rf /tmp/*",
                            "查找大文件: du -sh /* | sort -rh | head -10"
                        ]
                    })
            
            elif b["type"] == "load":
                if b["severity"] == "critical":
                    suggestions.append({
                        "category": "load",
                        "priority": "high",
                        "title": "系统负载优化",
                        "suggestions": [
                            "分析I/O等待: iostat -x 1",
                            "检查阻塞进程: vmstat 1",
                            "考虑负载均衡或扩容"
                        ]
                    })
        
        # 通用建议
        if not suggestions:
            suggestions.append({
                "category": "general",
                "priority": "low",
                "title": "系统健康",
                "suggestions": [
                    "当前系统运行良好",
                    "建议定期运行性能分析以保持最佳状态"
                ]
            })
        
        return suggestions
    
    def analyze_trends(self, hours: int = 24) -> Dict:
        """分析性能趋势"""
        if not self.history:
            return {"status": "no_data"}
        
        # 筛选最近N小时数据
        cutoff = time.time() - (hours * 3600)
        recent = [
            m for m in self.history
            if datetime.fromisoformat(m["timestamp"]).timestamp() > cutoff
        ]
        
        if len(recent) < 2:
            return {"status": "insufficient_data", "samples": len(recent)}
        
        # 计算趋势
        cpu_values = [m.get("cpu", {}).get("usage", 0) for m in recent if "cpu" in m]
        mem_values = [m.get("memory", {}).get("usage_percent", 0) for m in recent if "memory" in m]
        
        def calc_trend(values: List[float]) -> str:
            if len(values) < 2:
                return "unknown"
            first_half = sum(values[:len(values)//2]) / (len(values)//2)
            second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)
            diff = second_half - first_half
            if diff > 5:
                return "increasing"
            elif diff < -5:
                return "decreasing"
            return "stable"
        
        return {
            "samples": len(recent),
            "cpu_trend": calc_trend(cpu_values),
            "memory_trend": calc_trend(mem_values),
            "cpu_avg": round(sum(cpu_values) / len(cpu_values), 2) if cpu_values else 0,
            "memory_avg": round(sum(mem_values) / len(mem_values), 2) if mem_values else 0
        }
    
    def run_analysis(self) -> Dict:
        """执行完整分析"""
        # 收集指标
        metrics = self.collect_metrics()
        
        # 识别瓶颈
        bottlenecks = self.analyze_bottlenecks(metrics)
        
        # 生成建议
        suggestions = self.generate_optimization_suggestions(metrics, bottlenecks)
        
        # 分析趋势
        trends = self.analyze_trends()
        
        # 保存历史
        self._save_history()
        
        return {
            "timestamp": metrics["timestamp"],
            "metrics": metrics,
            "bottlenecks": bottlenecks,
            "suggestions": suggestions,
            "trends": trends,
            "status": "healthy" if not bottlenecks else "warning" if all(b["severity"] != "critical" for b in bottlenecks) else "critical"
        }
    
    def print_report(self, analysis: Dict):
        """打印分析报告"""
        print("\n" + "="*60)
        print("🔍 智能性能分析报告")
        print("="*60)
        
        print(f"\n📊 系统状态: {analysis['status'].upper()}")
        print(f"⏰ 分析时间: {analysis['timestamp']}")
        
        # 指标摘要
        if "metrics" in analysis:
            m = analysis["metrics"]
            print("\n📈 性能指标:")
            if "cpu" in m:
                print(f"  CPU: {m['cpu'].get('usage', 'N/A')}%")
            if "memory" in m:
                print(f"  内存: {m['memory'].get('usage_percent', 'N/A')}%")
            if "disk" in m:
                print(f"  磁盘: {m['disk'].get('usage_percent', 'N/A')}%")
            if "load" in m:
                l = m["load"]
                print(f"  负载: {l.get('1m', 'N/A')} (1m) / {l.get('5m', 'N/A')} (5m)")
        
        # 瓶颈
        if analysis.get("bottlenecks"):
            print("\n⚠️ 性能瓶颈:")
            for b in analysis["bottlenecks"]:
                emoji = "🔴" if b["severity"] == "critical" else "🟡"
                print(f"  {emoji} {b['message']}")
        
        # 建议
        if analysis.get("suggestions"):
            print("\n💡 优化建议:")
            for s in analysis["suggestions"]:
                priority_marker = "🔴" if s["priority"] == "high" else "🟡" if s["priority"] == "medium" else "✅"
                print(f"  {priority_marker} {s['title']}")
                for suggestion in s["suggestions"][:2]:
                    print(f"     • {suggestion}")
        
        # 趋势
        if "trends" in analysis and analysis["trends"].get("status") != "no_data":
            t = analysis["trends"]
            print("\n📉 趋势分析 (24h):")
            print(f"  CPU趋势: {t.get('cpu_trend', 'N/A')} (平均: {t.get('cpu_avg', 'N/A')}%)")
            print(f"  内存趋势: {t.get('memory_trend', 'N/A')} (平均: {t.get('memory_avg', 'N/A')}%)")
        
        print("\n" + "="*60)


def main():
    """主函数"""
    analyzer = SmartPerformanceAnalyzer()
    analysis = analyzer.run_analysis()
    analyzer.print_report(analysis)
    
    # 输出JSON格式（供其他程序使用）
    print("\n--- JSON Output ---")
    print(json.dumps(analysis, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()