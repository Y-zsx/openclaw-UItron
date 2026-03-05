#!/usr/bin/env python3
"""
智能告警分析引擎 - Intelligent Alert Analyzer
功能：
1. 告警趋势分析
2. 异常模式识别  
3. 预测性告警
4. 根因分析建议
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

class AlertAnalyzer:
    def __init__(self, data_dir="/root/.openclaw/workspace/ultron/data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.alerts_file = self.data_dir / "alert_history.json"
        self.analysis_file = self.data_dir / "alert_analysis.json"
        self._load_alerts()
    
    def _load_alerts(self):
        """加载告警历史"""
        if self.alerts_file.exists():
            with open(self.alerts_file, 'r') as f:
                data = json.load(f)
                self.alerts = data.get('alerts', [])
        else:
            self.alerts = []
    
    def _save_analysis(self, analysis):
        """保存分析结果"""
        with open(self.analysis_file, 'w') as f:
            json.dump(analysis, f, indent=2, ensure_ascii=False)
    
    def analyze_trends(self, hours=24):
        """分析告警趋势"""
        now = datetime.now()
        cutoff = now - timedelta(hours=hours)
        
        recent_alerts = [
            a for a in self.alerts 
            if datetime.fromisoformat(a.get('timestamp', '2020-01-01')) > cutoff
        ]
        
        # 按小时统计
        hourly_stats = defaultdict(int)
        type_stats = defaultdict(int)
        severity_stats = defaultdict(int)
        
        for alert in recent_alerts:
            ts = datetime.fromisoformat(alert.get('timestamp', '2020-01-01'))
            hour_key = ts.strftime('%Y-%m-%d %H:00')
            hourly_stats[hour_key] += 1
            
            alert_type = alert.get('type', 'unknown')
            severity = alert.get('severity', 'info')
            
            type_stats[alert_type] += 1
            severity_stats[severity] += 1
        
        return {
            'total': len(recent_alerts),
            'hourly': dict(hourly_stats),
            'by_type': dict(type_stats),
            'by_severity': dict(severity_stats)
        }
    
    def detect_patterns(self):
        """检测告警模式"""
        patterns = []
        
        # 频繁告警检测
        type_counts = defaultdict(int)
        for alert in self.alerts[-100:]:  # 最近100条
            type_counts[alert.get('type', 'unknown')] += 1
        
        for alert_type, count in type_counts.items():
            if count >= 5:
                patterns.append({
                    'type': 'frequent',
                    'alert_type': alert_type,
                    'count': count,
                    'message': f'{alert_type}类型告警频繁出现{count}次'
                })
        
        # 时间模式检测
        hour_counts = defaultdict(int)
        for alert in self.alerts[-200:]:
            ts = datetime.fromisoformat(alert.get('timestamp', '2020-01-01'))
            hour_counts[ts.hour] += 1
        
        # 找出高峰时段
        peak_hours = sorted(hour_counts.items(), key=lambda x: -x[1])[:3]
        if peak_hours and peak_hours[0][1] > 3:
            patterns.append({
                'type': 'time_pattern',
                'peak_hours': [h for h, c in peak_hours],
                'message': f'告警高峰时段: {", ".join(str(h[0]) for h in peak_hours)}点'
            })
        
        # 连续失败检测
        recent = self.alerts[-10:]
        if len(recent) >= 5:
            error_count = sum(1 for a in recent if a.get('severity') in ['error', 'critical'])
            if error_count >= 3:
                patterns.append({
                    'type': 'consecutive_errors',
                    'count': error_count,
                    'message': f'检测到连续{error_count}个错误告警'
                })
        
        return patterns
    
    def predict_future(self, hours=6):
        """预测未来告警"""
        if len(self.alerts) < 10:
            return {'prediction': '数据不足', 'risk_level': 'unknown'}
        
        # 基于历史模式预测
        recent_24h = [
            a for a in self.alerts 
            if datetime.fromisoformat(a.get('timestamp', '2020-01-01')) > 
               datetime.now() - timedelta(hours=24)
        ]
        
        avg_per_hour = len(recent_24h) / 24
        predicted_count = int(avg_per_hour * hours)
        
        # 风险评估
        severity_map = {'info': 1, 'warning': 2, 'error': 3, 'critical': 4}
        recent_severity = [
            severity_map.get(a.get('severity', 'info'), 1) 
            for a in recent_24h[-10:]
        ]
        avg_severity = sum(recent_severity) / len(recent_severity) if recent_severity else 1
        
        if avg_severity >= 3:
            risk_level = 'high'
        elif avg_severity >= 2:
            risk_level = 'medium'
        else:
            risk_level = 'low'
        
        return {
            'predicted_alerts': predicted_count,
            'risk_level': risk_level,
            'avg_hourly_rate': round(avg_per_hour, 2),
            'avg_severity': round(avg_severity, 2)
        }
    
    def suggest_root_cause(self, alert_type):
        """根因分析建议"""
        suggestions = {
            'disk': [
                '检查大文件日志',
                '清理临时文件',
                '扩展磁盘空间',
                '检查日志轮转配置'
            ],
            'memory': [
                '检查内存泄漏进程',
                '增加Swap空间',
                '优化应用内存使用',
                '重启占用内存大的服务'
            ],
            'cpu': [
                '检查异常进程',
                '分析CPU密集型任务',
                '考虑升级CPU资源',
                '优化应用负载'
            ],
            'network': [
                '检查网络连接状态',
                '查看防火墙规则',
                '分析网络流量异常',
                '检查DNS解析'
            ],
            'service': [
                '检查服务日志',
                '验证服务配置',
                '检查依赖服务状态',
                '尝试重启服务'
            ]
        }
        return suggestions.get(alert_type, ['需要更多数据进行分析'])
    
    def generate_report(self):
        """生成完整分析报告"""
        trends = self.analyze_trends(24)
        patterns = self.detect_patterns()
        prediction = self.predict_future(6)
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_alerts_24h': trends['total'],
                'most_common_type': max(trends['by_type'].items(), key=lambda x: x[1])[0] if trends['by_type'] else 'N/A',
                'risk_level': prediction['risk_level']
            },
            'trends': trends,
            'patterns': patterns,
            'prediction': prediction,
            'recommendations': []
        }
        
        # 生成建议
        if prediction['risk_level'] == 'high':
            report['recommendations'].append('⚠️ 高风险: 建议立即检查系统状态')
        
        if patterns:
            for p in patterns:
                if p['type'] == 'frequent':
                    alert_type = p['alert_type']
                    report['recommendations'].append(
                        f'建议检查{alert_type}相关问题，根因: {", ".join(self.suggest_root_cause(alert_type)[:2])}'
                    )
        
        self._save_analysis(report)
        return report

def main():
    analyzer = AlertAnalyzer()
    report = analyzer.generate_report()
    
    print("📊 智能告警分析报告")
    print("=" * 50)
    print(f"生成时间: {report['generated_at']}")
    print(f"\n📈 概览:")
    print(f"  - 24小时告警数: {report['summary']['total_alerts_24h']}")
    print(f"  - 最常见类型: {report['summary']['most_common_type']}")
    print(f"  - 风险等级: {report['summary']['risk_level']}")
    
    print(f"\n🔮 预测 (未来6小时):")
    p = report['prediction']
    print(f"  - 预计告警数: {p['predicted_alerts']}")
    print(f"  - 风险级别: {p['risk_level']}")
    print(f"  - 平均每小时: {p['avg_hourly_rate']}")
    
    if report['patterns']:
        print(f"\n🔍 检测到的模式:")
        for pat in report['patterns']:
            print(f"  - {pat['message']}")
    
    if report['recommendations']:
        print(f"\n💡 建议:")
        for rec in report['recommendations']:
            print(f"  - {rec}")
    
    return report

if __name__ == '__main__':
    main()