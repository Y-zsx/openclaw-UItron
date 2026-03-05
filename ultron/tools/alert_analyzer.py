#!/usr/bin/env python3
"""
智能告警分析与预测系统
功能：
- 告警模式识别与关联分析
- 趋势预测与异常检测
- 根因分析建议
- 智能告警摘要
"""

import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict, Counter
import os
import sys

class AlertAnalyzer:
    """智能告警分析器"""
    
    def __init__(self):
        self.alert_history: List[Dict] = []
        self.patterns: Dict[str, Any] = {}
        self.service_alerts: Dict[str, List[Dict]] = defaultdict(list)
        self.level_counts: Counter = Counter()
        
    def add_alert(self, alert: Dict):
        """添加告警到分析队列"""
        self.alert_history.append(alert)
        service = alert.get("service", "unknown")
        self.service_alerts[service].append(alert)
        self.level_counts[alert.get("level", "info")] += 1
        
        # 保留最近500条
        if len(self.alert_history) > 500:
            self.alert_history = self.alert_history[-500:]
    
    def load_from_monitor(self, monitor) -> int:
        """从健康监控器加载历史告警"""
        count = 0
        for alert in monitor.alert_manager.alerts:
            self.add_alert(alert)
            count += 1
        return count
    
    def analyze_trends(self) -> Dict:
        """分析告警趋势"""
        if not self.alert_history:
            return {"status": "no_data", "message": "暂无告警数据"}
        
        # 按时间分组 (最近24小时)
        now = datetime.now()
        hourly_counts = defaultdict(int)
        
        for alert in self.alert_history:
            try:
                ts = datetime.fromisoformat(alert.get("timestamp", ""))
                hour_key = ts.strftime("%Y-%m-%d %H:00")
                hourly_counts[hour_key] += 1
            except:
                pass
        
        # 计算趋势
        recent_6h = sum(hourly_counts.get((now - timedelta(hours=i)).strftime("%Y-%m-%d %H:00"), 0) for i in range(6))
        prev_6h = sum(hourly_counts.get((now - timedelta(hours=i+6)).strftime("%Y-%m-%d %H:00"), 0) for i in range(6))
        
        trend = "stable"
        if recent_6h > prev_6h * 1.5:
            trend = "increasing"
        elif recent_6h < prev_6h * 0.5 and prev_6h > 0:
            trend = "decreasing"
        
        return {
            "total_alerts": len(self.alert_history),
            "recent_6h": recent_6h,
            "previous_6h": prev_6h,
            "trend": trend,
            "level_distribution": dict(self.level_counts),
            "hourly_distribution": dict(sorted(hourly_counts.items())[-12:])
        }
    
    def analyze_service_health(self) -> Dict:
        """分析各服务健康状况"""
        service_stats = {}
        
        for service, alerts in self.service_alerts.items():
            if not alerts:
                continue
                
            levels = [a.get("level") for a in alerts]
            level_counts = Counter(levels)
            
            # 计算健康评分 (0-100)
            score = 100
            score -= level_counts.get("critical", 0) * 20
            score -= level_counts.get("error", 0) * 10
            score -= level_counts.get("warning", 0) * 5
            score = max(0, score)
            
            service_stats[service] = {
                "total_alerts": len(alerts),
                "level_breakdown": dict(level_counts),
                "health_score": score,
                "latest_alert": alerts[-1].get("timestamp", "unknown") if alerts else None
            }
        
        return service_stats
    
    def detect_patterns(self) -> List[Dict]:
        """检测告警模式"""
        patterns = []
        
        if len(self.alert_history) < 3:
            return patterns
        
        # 检测重复告警
        alert_messages = [a.get("message", "") for a in self.alert_history[-50:]]
        message_counts = Counter(alert_messages)
        
        for msg, count in message_counts.items():
            if count >= 3:
                patterns.append({
                    "type": "repeated",
                    "message": msg[:100],
                    "count": count,
                    "severity": "high" if count >= 5 else "medium",
                    "recommendation": "检查是否存在持续性问题"
                })
        
        # 检测服务频繁告警
        for service, alerts in self.service_alerts.items():
            if len(alerts) >= 5:
                recent = [a for a in alerts if self._is_recent(a.get("timestamp"), hours=6)]
                if len(recent) >= 3:
                    patterns.append({
                        "type": "frequent",
                        "service": service,
                        "count_6h": len(recent),
                        "severity": "high",
                        "recommendation": f"服务 {service} 频繁告警，建议排查"
                    })
        
        return patterns
    
    def _is_recent(self, timestamp: str, hours: int = 1) -> bool:
        """检查时间戳是否在最近N小时内"""
        try:
            ts = datetime.fromisoformat(timestamp)
            return (datetime.now() - ts).total_seconds() < hours * 3600
        except:
            return False
    
    def predict_future(self) -> Dict:
        """预测未来可能发生的告警"""
        predictions = []
        
        # 基于历史模式预测
        for service, alerts in self.service_alerts.items():
            if len(alerts) < 3:
                continue
                
            # 检测是否有周期性
            timestamps = []
            for a in alerts:
                try:
                    ts = datetime.fromisoformat(a.get("timestamp", ""))
                    timestamps.append(ts)
                except:
                    pass
            
            if len(timestamps) >= 3:
                # 检查时间间隔
                intervals = []
                for i in range(1, len(timestamps)):
                    interval = (timestamps[i-1] - timestamps[i]).total_seconds()
                    intervals.append(interval)
                
                avg_interval = sum(intervals) / len(intervals) if intervals else 0
                
                # 如果平均间隔小于30分钟，预测可能再次告警
                if avg_interval < 1800 and avg_interval > 0:
                    next_expected = timestamps[-1] + timedelta(seconds=avg_interval)
                    predictions.append({
                        "service": service,
                        "pattern": "cyclic",
                        "avg_interval_min": round(avg_interval / 60, 1),
                        "next_expected": next_expected.isoformat(),
                        "confidence": "medium",
                        "recommendation": f"预计 {next_expected.strftime('%H:%M')} 可能再次告警"
                    })
        
        # 基于服务依赖预测
        critical_services = ["gateway", "openclaw", "browser"]
        for service in critical_services:
            if service in self.service_alerts:
                recent = [a for a in self.service_alerts[service] if self._is_recent(a.get("timestamp"), hours=2)]
                if len(recent) >= 2:
                    predictions.append({
                        "service": service,
                        "pattern": "unstable",
                        "confidence": "high",
                        "recommendation": f"服务 {service} 近2小时多次告警，建议主动检查"
                    })
        
        return predictions
    
    def generate_summary(self) -> str:
        """生成智能告警摘要"""
        if not self.alert_history:
            return "✅ 暂无告警数据，系统运行正常"
        
        trends = self.analyze_trends()
        patterns = self.detect_patterns()
        predictions = self.predict_future()
        
        summary_lines = [
            f"📊 告警分析报告 ({datetime.now().strftime('%H:%M')})",
            f"总告警数: {trends.get('total_alerts', 0)}",
            f"近6小时: {trends.get('recent_6h', 0)} | 趋势: {trends.get('trend', 'unknown')}"
        ]
        
        # 级别分布
        if trends.get("level_distribution"):
            levels = trends["level_distribution"]
            level_str = " | ".join([f"{k}:{v}" for k, v in levels.items()])
            summary_lines.append(f"级别分布: {level_str}")
        
        # 模式
        if patterns:
            summary_lines.append(f"\n⚠️ 检测到 {len(patterns)} 个模式:")
            for p in patterns[:3]:
                summary_lines.append(f"  • {p.get('type')}: {p.get('recommendation', '')[:50]}")
        
        # 预测
        if predictions:
            summary_lines.append(f"\n🔮 预测 {len(predictions)} 个潜在问题:")
            for p in predictions[:2]:
                summary_lines.append(f"  • {p.get('recommendation', '')[:50]}")
        
        # 建议
        if not patterns and not predictions:
            summary_lines.append("\n✅ 系统运行平稳，无明显异常")
        
        return "\n".join(summary_lines)


# 全局分析器实例
_analyzer = None

def get_analyzer() -> AlertAnalyzer:
    global _analyzer
    if _analyzer is None:
        _analyzer = AlertAnalyzer()
    return _analyzer

if __name__ == "__main__":
    # 测试
    analyzer = get_analyzer()
    
    # 模拟添加一些告警
    for i in range(10):
        analyzer.add_alert({
            "level": "warning",
            "service": "gateway",
            "message": "响应时间超过阈值",
            "timestamp": (datetime.now() - timedelta(minutes=i*10)).isoformat()
        })
    
    print(analyzer.generate_summary())
    print("\n--- 趋势分析 ---")
    print(json.dumps(analyzer.analyze_trends(), indent=2, ensure_ascii=False))
    print("\n--- 模式检测 ---")
    print(json.dumps(analyzer.detect_patterns(), indent=2, ensure_ascii=False))
    print("\n--- 预测 ---")
    print(json.dumps(analyzer.predict_future(), indent=2, ensure_ascii=False))