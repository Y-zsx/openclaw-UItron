#!/usr/bin/env python3
"""
智能告警分析预测系统 - Alert Intelligence System
功能：
1. 实时指标采集与分析
2. 趋势预测
3. 告警模式识别
4. 根因分析
5. 智能预警
"""

import json
import os
import time
import subprocess
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# 配置
DATA_DIR = "/root/.openclaw/workspace/ultron/data"
HISTORY_FILE = f"{DATA_DIR}/alert-intelligence-history.json"
PATTERNS_FILE = f"{DATA_DIR}/alert-patterns.json"
ANALYSIS_FILE = f"{DATA_DIR}/alert-analysis.json"

class AlertIntelligence:
    def __init__(self):
        self.data_dir = Path(DATA_DIR)
        self.data_dir.mkdir(exist_ok=True)
        self.history = self._load_history()
        self.patterns = self._load_patterns()
        
    def _load_history(self):
        """加载历史数据"""
        if os.path.exists(HISTORY_FILE):
            try:
                with open(HISTORY_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {'metrics': [], 'alerts': []}
        return {'metrics': [], 'alerts': []}
    
    def _save_history(self):
        """保存历史数据"""
        with open(HISTORY_FILE, 'w') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
    
    def _load_patterns(self):
        """加载告警模式"""
        if os.path.exists(PATTERNS_FILE):
            try:
                with open(PATTERNS_FILE, 'r') as f:
                    return json.load(f)
            except:
                return {'patterns': [], 'last_update': None}
        return {'patterns': [], 'last_update': None}
    
    def _save_patterns(self):
        """保存告警模式"""
        with open(PATTERNS_FILE, 'w') as f:
            json.dump(self.patterns, f, indent=2, ensure_ascii=False)
    
    def collect_metrics(self):
        """采集系统指标"""
        metrics = {
            'timestamp': datetime.now().isoformat(),
            'cpu': self._get_cpu_usage(),
            'memory': self._get_memory_usage(),
            'disk': self._get_disk_usage(),
            'load': self._get_load_avg(),
            'network': self._get_network_stats(),
            'process': self._get_process_stats()
        }
        
        # 保存到历史
        self.history.setdefault('metrics', []).append(metrics)
        
        # 只保留最近500条
        if len(self.history['metrics']) > 500:
            self.history['metrics'] = self.history['metrics'][-500:]
        
        self._save_history()
        return metrics
    
    def _get_cpu_usage(self):
        """获取CPU使用率"""
        try:
            result = subprocess.run(
                ["top", "-bn1"],
                capture_output=True, text=True, timeout=5
            )
            for line in result.stdout.split('\n'):
                if 'Cpu(s)' in line:
                    parts = line.split()
                    for i, p in enumerate(parts):
                        if 'id' in p:
                            idle = float(parts[i-1].replace(',', '.'))
                            return round(100 - idle, 1)
        except:
            pass
        return 0.0
    
    def _get_memory_usage(self):
        """获取内存使用率"""
        try:
            result = subprocess.run(
                ["free", "-m"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            for line in lines:
                if line.startswith('Mem:'):
                    parts = line.split()
                    total = float(parts[1])
                    used = float(parts[2])
                    if total > 0:
                        return round(used / total * 100, 1)
        except:
            pass
        return 0.0
    
    def _get_disk_usage(self):
        """获取磁盘使用率"""
        try:
            result = subprocess.run(
                ["df", "-h", "/"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            if len(lines) > 1:
                parts = lines[1].split()
                if len(parts) > 4:
                    return float(parts[4].replace('%', ''))
        except:
            pass
        return 0.0
    
    def _get_load_avg(self):
        """获取负载"""
        try:
            result = subprocess.run(
                ["cat", "/proc/loadavg"],
                capture_output=True, text=True, timeout=5
            )
            return float(result.stdout.split()[0])
        except:
            return 0.0
    
    def _get_network_stats(self):
        """获取网络统计"""
        stats = {}
        try:
            result = subprocess.run(
                ["cat", "/proc/net/dev"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            for line in lines:
                if 'eth0' in line or 'ens' in line:
                    parts = line.split()
                    if len(parts) > 9:
                        stats['rx'] = int(parts[1])
                        stats['tx'] = int(parts[9])
                        break
        except:
            pass
        return stats
    
    def _get_process_stats(self):
        """获取进程统计"""
        try:
            result = subprocess.run(
                ["ps", "aux"],
                capture_output=True, text=True, timeout=5
            )
            lines = result.stdout.split('\n')
            return {'total': len(lines) - 1}
        except:
            return {'total': 0}
    
    def analyze_trends(self):
        """分析趋势"""
        metrics = self.history.get('metrics', [])
        if len(metrics) < 5:
            return {'status': 'insufficient_data', 'message': '需要更多数据点'}
        
        # 分析最近的数据
        recent = metrics[-10:] if len(metrics) >= 10 else metrics
        
        cpu_values = [m.get('cpu', 0) for m in recent]
        mem_values = [m.get('memory', 0) for m in recent]
        disk_values = [m.get('disk', 0) for m in recent]
        
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'data_points': len(metrics),
            'analysis_period': f"{len(recent)} 个数据点",
            'cpu': self._analyze_metric_trend('CPU', cpu_values),
            'memory': self._analyze_metric_trend('Memory', mem_values),
            'disk': self._analyze_metric_trend('Disk', disk_values),
            'prediction': self._predict_alerts(metrics)
        }
        
        # 保存分析结果
        with open(ANALYSIS_FILE, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
        
        return analysis
    
    def _analyze_metric_trend(self, name, values):
        """分析单个指标的趋势"""
        if not values:
            return {'current': 0, 'avg': 0, 'max': 0, 'min': 0, 'trend': 'stable'}
        
        current = values[-1]
        avg = sum(values) / len(values)
        max_val = max(values)
        min_val = min(values)
        
        # 简单趋势判断
        if len(values) >= 3:
            recent_avg = sum(values[-3:]) / 3
            older_avg = sum(values[:-3]) / max(len(values)-3, 1)
            if recent_avg > older_avg * 1.1:
                trend = 'rising'
            elif recent_avg < older_avg * 0.9:
                trend = 'falling'
            else:
                trend = 'stable'
        else:
            trend = 'stable'
        
        return {
            'current': round(current, 1),
            'avg': round(avg, 1),
            'max': round(max_val, 1),
            'min': round(min_val, 1),
            'trend': trend
        }
    
    def _predict_alerts(self, metrics):
        """预测告警"""
        if len(metrics) < 10:
            return {'status': 'waiting'}
        
        # 基于最近的趋势预测
        recent = metrics[-10:]
        
        predictions = []
        
        # 检查CPU趋势
        cpu_values = [m.get('cpu', 0) for m in recent]
        if cpu_values:
            avg_cpu = sum(cpu_values) / len(cpu_values)
            if avg_cpu > 80:
                predictions.append({
                    'type': 'cpu',
                    'level': 'warning' if avg_cpu < 90 else 'critical',
                    'message': f'CPU平均使用率 {avg_cpu:.1f}%，可能有告警风险',
                    'probability': min(avg_cpu / 100, 0.95)
                })
        
        # 检查内存趋势
        mem_values = [m.get('memory', 0) for m in recent]
        if mem_values:
            avg_mem = sum(mem_values) / len(mem_values)
            if avg_mem > 70:
                predictions.append({
                    'type': 'memory',
                    'level': 'warning' if avg_mem < 85 else 'critical',
                    'message': f'内存平均使用率 {avg_mem:.1f}%，可能有告警风险',
                    'probability': min(avg_mem / 100, 0.95)
                })
        
        return {
            'predictions': predictions,
            'status': 'analyzed'
        }
    
    def analyze_alert_patterns(self):
        """分析告警模式"""
        # 读取告警历史
        alert_file = "/root/.openclaw/workspace/ultron/alerts/alerts.json"
        patterns = {'patterns': [], 'timestamp': datetime.now().isoformat()}
        
        if os.path.exists(alert_file):
            try:
                with open(alert_file, 'r') as f:
                    alerts = json.load(f)
                
                # 统计告警类型
                alert_counts = defaultdict(int)
                for alert in alerts:
                    rule = alert.get('rule', 'unknown')
                    alert_counts[rule] += 1
                
                patterns['alert_type_counts'] = dict(alert_counts)
                
                # 识别频繁告警
                frequent = [(k, v) for k, v in alert_counts.items() if v >= 2]
                if frequent:
                    patterns['frequent_alerts'] = [
                        {'rule': k, 'count': v} for k, v in sorted(frequent, key=lambda x: -x[1])
                    ]
                
            except Exception as e:
                patterns['error'] = str(e)
        
        # 保存模式
        self.patterns = patterns
        self._save_patterns()
        
        return patterns
    
    def get_intelligence_report(self):
        """获取智能分析报告"""
        return {
            'timestamp': datetime.now().isoformat(),
            'metrics_count': len(self.history.get('metrics', [])),
            'analysis': self.analyze_trends(),
            'patterns': self.analyze_alert_patterns()
        }


def main():
    """主函数"""
    ai = AlertIntelligence()
    
    # 1. 采集指标
    print("📊 采集系统指标...")
    metrics = ai.collect_metrics()
    print(f"  CPU: {metrics.get('cpu')}%")
    print(f"  Memory: {metrics.get('memory')}%")
    print(f"  Disk: {metrics.get('disk')}%")
    print(f"  Load: {metrics.get('load')}")
    
    # 2. 趋势分析
    print("\n📈 趋势分析...")
    analysis = ai.analyze_trends()
    if analysis.get('status') != 'insufficient_data':
        for metric in ['cpu', 'memory', 'disk']:
            if metric in analysis:
                m = analysis[metric]
                print(f"  {metric}: {m.get('current')}% | 趋势: {m.get('trend')} | 预测: {m.get('prediction', {}).get('message', 'N/A')}")
    
    # 3. 告警模式分析
    print("\n🔍 告警模式分析...")
    patterns = ai.analyze_alert_patterns()
    if 'alert_type_counts' in patterns:
        for alert_type, count in patterns['alert_type_counts'].items():
            print(f"  {alert_type}: {count}次")
    
    print("\n✅ 智能告警分析完成")
    
    # 保存完整报告
    report = ai.get_intelligence_report()
    report_file = f"{DATA_DIR}/alert-intelligence-report.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📄 报告已保存: {report_file}")
    
    return report


if __name__ == "__main__":
    main()