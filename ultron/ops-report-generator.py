#!/usr/bin/env python3
"""
智能运维助手 - 自动化报告生成器
第38世: 自动化报告生成

功能:
- 定时生成系统运行报告
- 支持日报/周报/月报
- 包含指标摘要、告警统计、健康评分
- 支持多格式输出 (console/file/html)
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path

# 添加当前目录到路径，以便导入同级模块
_ops_dir = os.path.dirname(os.path.abspath(__file__))
if _ops_dir not in sys.path:
    sys.path.insert(0, _ops_dir)

# 尝试导入采集器和告警引擎
try:
    from ops_collector import MetricCollector
    COLLECTOR_AVAILABLE = True
except ImportError:
    COLLECTOR_AVAILABLE = False
    print("⚠️ ops_collector 不可用，使用基础采集")

try:
    from ops_alert_engine import AlertEngine, AlertLevel
    ALERT_ENGINE_AVAILABLE = True
except ImportError:
    ALERT_ENGINE_AVAILABLE = False
    print("⚠️ ops_alert_engine 不可用，使用基础告警")


class MetricsStore:
    """指标数据存储（基于文件）"""
    
    def __init__(self, store_dir: str = "/root/.openclaw/workspace/ultron/data"):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.metrics_file = self.store_dir / "metrics_history.json"
    
    def save_metric(self, metric: Dict[str, Any]):
        """保存单条指标"""
        metrics = self.load_all()
        metrics.append({
            "timestamp": metric.get("timestamp", datetime.now().isoformat()),
            "data": metric
        })
        
        # 只保留最近7天的数据 (10080条)
        if len(metrics) > 10080:
            metrics = metrics[-10080:]
        
        with open(self.metrics_file, 'w') as f:
            json.dump(metrics, f, indent=2, default=str)
    
    def load_all(self) -> List[Dict[str, Any]]:
        """加载所有历史指标"""
        if not self.metrics_file.exists():
            return []
        
        try:
            with open(self.metrics_file, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def load_recent(self, hours: int = 24) -> List[Dict[str, Any]]:
        """加载最近N小时的指标"""
        all_metrics = self.load_all()
        cutoff = datetime.now() - timedelta(hours=hours)
        
        result = []
        for m in all_metrics:
            try:
                ts = datetime.fromisoformat(m.get("timestamp", ""))
                if ts >= cutoff:
                    result.append(m)
            except:
                continue
        
        return result
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """计算统计信息"""
        metrics = self.load_recent(hours)
        
        if not metrics:
            return {}
        
        # 提取CPU和内存数据
        cpu_values = []
        memory_values = []
        
        for m in metrics:
            data = m.get("data", {})
            if "cpu" in data and "usage_percent" in data["cpu"]:
                cpu_values.append(data["cpu"]["usage_percent"])
            if "memory" in data and "percent" in data["memory"]:
                memory_values.append(data["memory"]["percent"])
        
        def calc_stats(values: List[float]) -> Dict[str, float]:
            if not values:
                return {}
            return {
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "count": len(values)
            }
        
        return {
            "cpu": calc_stats(cpu_values),
            "memory": calc_stats(memory_values),
            "sample_count": len(metrics),
            "hours": hours
        }


class HealthScorer:
    """健康评分器"""
    
    def __init__(self):
        self.weights = {
            "cpu": 0.25,
            "memory": 0.25,
            "disk": 0.20,
            "network": 0.15,
            "services": 0.15
        }
    
    def score_metric(self, category: str, value: float) -> float:
        """单项评分 (0-100)"""
        # 越低越好
        if category in ["cpu", "memory", "disk"]:
            return max(0, 100 - value)
        return 100
    
    def overall_score(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        """计算综合健康分"""
        scores = {}
        
        # CPU评分
        cpu = metrics.get("cpu", {}).get("usage_percent", 0)
        scores["cpu"] = self.score_metric("cpu", cpu)
        
        # 内存评分
        memory = metrics.get("memory", {}).get("percent", 0)
        scores["memory"] = self.score_metric("memory", memory)
        
        # 磁盘评分
        disk = metrics.get("disk", {}).get("disks", [{}])[0].get("percent", 0)
        scores["disk"] = self.score_metric("disk", disk)
        
        # 网络评分 (基于错误率)
        network = metrics.get("network", {})
        errors = network.get("errin", 0) + network.get("errout", 0)
        scores["network"] = max(0, 100 - min(errors / 100, 100))
        
        # 服务评分
        services = metrics.get("services", {})
        running = sum(1 for v in services.values() if v == "running")
        total = len(services)
        scores["services"] = (running / total * 100) if total > 0 else 100
        
        # 综合评分
        overall = sum(
            scores.get(k, 0) * self.weights.get(k, 0) 
            for k in self.weights.keys()
        )
        
        return {
            "overall": round(overall, 1),
            "details": {k: round(v, 1) for k, v in scores.items()},
            "grade": self._get_grade(overall)
        }
    
    def _get_grade(self, score: float) -> str:
        """评分等级"""
        if score >= 90:
            return "A (优秀)"
        elif score >= 80:
            return "B (良好)"
        elif score >= 70:
            return "C (一般)"
        elif score >= 60:
            return "D (警告)"
        else:
            return "F (危急)"


class ReportGenerator:
    """报告生成器"""
    
    def __init__(self):
        self.collector = MetricCollector() if COLLECTOR_AVAILABLE else None
        self.alert_engine = AlertEngine() if ALERT_ENGINE_AVAILABLE else None
        self.metrics_store = MetricsStore()
        self.health_scorer = HealthScorer()
        
        self.report_dir = Path("/root/.openclaw/workspace/ultron/reports")
        self.report_dir.mkdir(parents=True, exist_ok=True)
    
    def collect_current_metrics(self) -> Dict[str, Any]:
        """采集当前指标"""
        if self.collector:
            return self.collector.collect_all()
        
        # 基础采集
        import psutil
        return {
            "timestamp": datetime.now().isoformat(),
            "cpu": {"usage_percent": psutil.cpu_percent(interval=1)},
            "memory": {"percent": psutil.virtual_memory().percent},
            "disk": {"disks": [{"percent": psutil.disk_usage('/').percent}]},
            "network": psutil.net_io_counters()._asdict()
        }
    
    def generate_daily_report(self) -> Dict[str, Any]:
        """生成日报"""
        # 采集当前数据
        current_metrics = self.collect_current_metrics()
        
        # 获取历史统计
        stats = self.metrics_store.get_statistics(hours=24)
        
        # 健康评分
        health = self.health_scorer.overall_score(current_metrics)
        
        # 告警统计
        alert_count = 0
        if self.alert_engine:
            alerts = self.alert_engine.check(current_metrics)
            alert_count = len(alerts)
        
        report = {
            "type": "daily",
            "generated_at": datetime.now().isoformat(),
            "period": {
                "start": (datetime.now() - timedelta(hours=24)).isoformat(),
                "end": datetime.now().isoformat()
            },
            "current_status": {
                "cpu_percent": current_metrics.get("cpu", {}).get("usage_percent", 0),
                "memory_percent": current_metrics.get("memory", {}).get("percent", 0),
                "disk_percent": current_metrics.get("disk", {}).get("disks", [{}])[0].get("percent", 0)
            },
            "statistics_24h": stats,
            "health_score": health,
            "alerts_24h": alert_count
        }
        
        return report
    
    def format_console_report(self, report: Dict[str, Any]) -> str:
        """格式化控制台报告"""
        lines = []
        lines.append("=" * 60)
        lines.append("📊 智能运维助手 - 系统运行报告")
        lines.append("=" * 60)
        
        # 基本信息
        lines.append(f"\n📅 报告时间: {report['generated_at']}")
        lines.append(f"📆 报告类型: {report['type'].upper()}")
        lines.append(f"⏰ 统计周期: {report['period']['start']} ~ {report['period']['end']}")
        
        # 当前状态
        lines.append("\n" + "-" * 40)
        lines.append("🔴 当前状态")
        lines.append("-" * 40)
        current = report['current_status']
        lines.append(f"  CPU:    {current['cpu_percent']:.1f}%")
        lines.append(f"  内存:   {current['memory_percent']:.1f}%")
        lines.append(f"  磁盘:   {current['disk_percent']:.1f}%")
        
        # 24小时统计
        stats = report.get('statistics_24h', {})
        if stats.get('cpu'):
            lines.append("\n" + "-" * 40)
            lines.append("📈 24小时统计")
            lines.append("-" * 40)
            cpu = stats.get('cpu', {})
            mem = stats.get('memory', {})
            lines.append(f"  CPU:    最低{cpu.get('min', 0):.1f}% / 最高{cpu.get('max', 0):.1f}% / 平均{cpu.get('avg', 0):.1f}%")
            lines.append(f"  内存:   最低{mem.get('min', 0):.1f}% / 最高{mem.get('max', 0):.1f}% / 平均{mem.get('avg', 0):.1f}%")
            lines.append(f"  采样:   {stats.get('sample_count', 0)} 次")
        
        # 健康评分
        health = report.get('health_score', {})
        lines.append("\n" + "-" * 40)
        lines.append("💚 健康评分")
        lines.append("-" * 40)
        lines.append(f"  综合:   {health.get('overall', 0)} 分 - {health.get('grade', 'N/A')}")
        details = health.get('details', {})
        lines.append(f"  CPU:    {details.get('cpu', 0)} 分")
        lines.append(f"  内存:   {details.get('memory', 0)} 分")
        lines.append(f"  磁盘:   {details.get('disk', 0)} 分")
        lines.append(f"  网络:   {details.get('network', 0)} 分")
        lines.append(f"  服务:   {details.get('services', 0)} 分")
        
        # 告警统计
        lines.append("\n" + "-" * 40)
        lines.append("🚨 告警统计")
        lines.append("-" * 40)
        lines.append(f"  24小时内告警: {report.get('alerts_24h', 0)} 次")
        
        lines.append("\n" + "=" * 60)
        
        return "\n".join(lines)
    
    def format_html_report(self, report: Dict[str, Any]) -> str:
        """生成HTML报告"""
        health = report.get('health_score', {})
        current = report['current_status']
        stats = report.get('statistics_24h', {})
        
        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>系统运行报告 - {report['generated_at'][:10]}</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
               max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .card {{ background: white; border-radius: 10px; padding: 20px; margin-bottom: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; text-align: center; }}
        h2 {{ color: #666; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .metric {{ display: flex; justify-content: space-between; padding: 10px 0; border-bottom: 1px solid #eee; }}
        .metric-value {{ font-weight: bold; color: #2196F3; }}
        .score {{ font-size: 48px; text-align: center; color: #4CAF50; }}
        .grade {{ font-size: 24px; text-align: center; color: #666; }}
        .status-ok {{ color: #4CAF50; }}
        .status-warn {{ color: #FF9800; }}
        .status-error {{ color: #F44336; }}
        .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 20px; }}
    </style>
</head>
<body>
    <h1>📊 系统运行报告</h1>
    
    <div class="card">
        <h2>基本信息</h2>
        <div class="metric"><span>报告时间</span><span class="metric-value">{report['generated_at'][:19]}</span></div>
        <div class="metric"><span>报告类型</span><span class="metric-value">{report['type'].upper()}</span></div>
        <div class="metric"><span>统计周期</span><span class="metric-value">24小时</span></div>
    </div>
    
    <div class="card">
        <h2>当前状态</h2>
        <div class="metric"><span>CPU 使用率</span><span class="metric-value">{current['cpu_percent']:.1f}%</span></div>
        <div class="metric"><span>内存使用率</span><span class="metric-value">{current['memory_percent']:.1f}%</span></div>
        <div class="metric"><span>磁盘使用率</span><span class="metric-value">{current['disk_percent']:.1f}%</span></div>
    </div>
    
    <div class="card">
        <h2>健康评分</h2>
        <div class="score">{health.get('overall', 0)}</div>
        <div class="grade">{health.get('grade', 'N/A')}</div>
    </div>
    
    <div class="card">
        <h2>24小时统计</h2>
"""
        
        if stats.get('cpu'):
            cpu = stats.get('cpu', {})
            mem = stats.get('memory', {})
            html += f"""
        <div class="metric"><span>CPU 平均</span><span class="metric-value">{cpu.get('avg', 0):.1f}%</span></div>
        <div class="metric"><span>CPU 峰值</span><span class="metric-value">{cpu.get('max', 0):.1f}%</span></div>
        <div class="metric"><span>内存平均</span><span class="metric-value">{mem.get('avg', 0):.1f}%</span></div>
        <div class="metric"><span>内存峰值</span><span class="metric-value">{mem.get('max', 0):.1f}%</span></div>
        <div class="metric"><span>采样次数</span><span class="metric-value">{stats.get('sample_count', 0)}</span></div>
"""
        
        html += f"""
    </div>
    
    <div class="card">
        <h2>告警统计</h2>
        <div class="metric"><span>24小时内告警</span><span class="metric-value">{report.get('alerts_24h', 0)} 次</span></div>
    </div>
    
    <div class="footer">
        Generated by 奥创智能运维助手 | {datetime.now().isoformat()}
    </div>
</body>
</html>"""
        
        return html
    
    def save_report(self, report: Dict[str, Any], format: str = "all") -> List[str]:
        """保存报告"""
        saved = []
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存JSON
        if format in ["json", "all"]:
            json_path = self.report_dir / f"report_{timestamp}.json"
            with open(json_path, 'w') as f:
                json.dump(report, f, indent=2, default=str)
            saved.append(str(json_path))
        
        # 保存HTML
        if format in ["html", "all"]:
            html_path = self.report_dir / f"report_{timestamp}.html"
            html_content = self.format_html_report(report)
            with open(html_path, 'w') as f:
                f.write(html_content)
            saved.append(str(html_path))
        
        return saved
    
    def run(self, save: bool = True, output: str = "console"):
        """运行报告生成"""
        # 采集当前指标并保存
        metrics = self.collect_current_metrics()
        self.metrics_store.save_metric(metrics)
        
        # 生成报告
        report = self.generate_daily_report()
        
        # 输出
        if output == "console" or output == "all":
            print(self.format_console_report(report))
        
        if output == "html" or output == "all":
            html = self.format_html_report(report)
            print(f"\n📄 HTML报告已生成")
        
        # 保存
        if save:
            saved = self.save_report(report, output if output != "all" else "json")
            print(f"\n💾 报告已保存: {saved}")
        
        return report


def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="智能运维报告生成器")
    parser.add_argument("--output", choices=["console", "html", "json", "all"], default="console", help="输出格式")
    parser.add_argument("--no-save", action="store_true", help="不保存报告")
    parser.add_argument("--stats", action="store_true", help="仅显示统计信息")
    
    args = parser.parse_args()
    
    generator = ReportGenerator()
    
    if args.stats:
        # 只显示统计
        stats = generator.metrics_store.get_statistics(hours=24)
        print("📊 24小时统计:")
        print(json.dumps(stats, indent=2, default=str))
    else:
        # 完整报告
        generator.run(save=not args.no_save, output=args.output)


if __name__ == "__main__":
    main()