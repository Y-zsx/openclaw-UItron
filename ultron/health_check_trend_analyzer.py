#!/usr/bin/env python3
"""
健康检查历史趋势分析器
功能：提供历史趋势分析、健康度预测、异常检测、可视化数据
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = "/root/.openclaw/workspace/ultron/logs/health_check_log.db"


class HealthCheckTrendAnalyzer:
    """健康检查历史趋势分析器"""
    
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
    
    def _query(self, sql: str, params: tuple = ()) -> List[Dict]:
        """执行查询并返回结果"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results
    
    def _query_one(self, sql: str, params: tuple = ()) -> Optional[Dict]:
        """执行查询并返回单条结果"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(sql, params)
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_time_series(self, hours: int = 24, interval: str = "auto") -> Dict:
        """获取时间序列数据
        
        Args:
            hours: 时间范围（小时）
            interval: 数据间隔 (auto/5m/15m/1h)
        """
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 自动选择间隔
        if interval == "auto":
            if hours <= 6:
                interval = "5m"
            elif hours <= 24:
                interval = "15m"
            else:
                interval = "1h"
        
        # 根据间隔聚合数据
        if interval == "5m":
            group_by = "strftime('%Y-%m-%d %H:%M:', timestamp) || (CAST(strftime('%M', timestamp) / 5 AS INTEGER) * 5) || '00'"
        elif interval == "15m":
            group_by = "strftime('%Y-%m-%d %H:', timestamp) || (CAST(strftime('%M', timestamp) / 15 AS INTEGER) * 15) || ':00'"
        else:  # 1h
            group_by = "strftime('%Y-%m-%d %H:00:00', timestamp)"
        
        sql = f"""
            SELECT 
                {group_by} as time_bucket,
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health,
                AVG(healthy_services) as avg_healthy_services,
                SUM(CASE WHEN unhealthy_services > 0 THEN 1 ELSE 0 END) as failure_count,
                COUNT(*) as sample_count
            FROM health_check_logs 
            WHERE timestamp >= ?
            GROUP BY time_bucket
            ORDER BY time_bucket ASC
        """
        
        data = self._query(sql, (since,))
        
        return {
            "interval": interval,
            "period_hours": hours,
            "data_points": len(data),
            "series": data
        }
    
    def get_service_trends(self, hours: int = 24) -> Dict:
        """获取各服务的趋势分析"""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 各服务的健康趋势
        sql = """
            SELECT 
                service_name,
                COUNT(*) as total_checks,
                SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy_count,
                SUM(CASE WHEN status = 'unhealthy' THEN 1 ELSE 0 END) as unhealthy_count,
                AVG(response_time_ms) as avg_response_time,
                MIN(CASE WHEN status = 'healthy' THEN timestamp END) as first_check,
                MAX(CASE WHEN status = 'healthy' THEN timestamp END) as last_healthy
            FROM service_status_logs 
            WHERE timestamp >= ?
            GROUP BY service_name
            ORDER BY service_name
        """
        
        services = self._query(sql, (since,))
        
        # 计算各服务的可用率
        result = []
        for svc in services:
            total = svc.get('total_checks', 0) or 1
            healthy = svc.get('healthy_count', 0) or 0
            availability = (healthy / total) * 100
            
            # 趋势判断
            trend = "stable"
            if svc.get('unhealthy_count', 0) == 0:
                trend = "healthy"
            elif healthy == 0:
                trend = "critical"
            elif svc.get('unhealthy_count', 0) > total * 0.3:
                trend = "degrading"
            
            result.append({
                "service": svc['service_name'],
                "availability": round(availability, 2),
                "total_checks": total,
                "healthy_count": healthy,
                "unhealthy_count": svc.get('unhealthy_count', 0),
                "avg_response_time": round(svc.get('avg_response_time') or 0, 2),
                "trend": trend,
                "last_healthy": svc.get('last_healthy')
            })
        
        return {
            "period_hours": hours,
            "services": result,
            "total_services": len(result)
        }
    
    def get_weekly_trend(self) -> Dict:
        """获取周趋势分析（7天）"""
        since = (datetime.now() - timedelta(days=7)).isoformat()
        
        # 按天聚合
        sql = """
            SELECT 
                DATE(timestamp) as day,
                COUNT(*) as checks,
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health,
                SUM(CASE WHEN unhealthy_services > 0 THEN 1 ELSE 0 END) as failure_days
            FROM health_check_logs 
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY day
        """
        
        daily = self._query(sql, (since,))
        
        # 计算周统计
        if daily:
            avg_weekly_health = sum(d.get('avg_health', 0) or 0 for d in daily) / len(daily)
            total_checks = sum(d.get('checks', 0) for d in daily)
            total_failures = sum(d.get('failure_days', 0) for d in daily)
            uptime_percentage = ((len(daily) - total_failures) / len(daily)) * 100 if daily else 0
        else:
            avg_weekly_health = 0
            total_checks = 0
            total_failures = 0
            uptime_percentage = 0
        
        return {
            "period": "7 days",
            "daily_data": daily,
            "summary": {
                "avg_health": round(avg_weekly_health, 2),
                "total_checks": total_checks,
                "failure_days": total_failures,
                "uptime_percentage": round(uptime_percentage, 2)
            }
        }
    
    def get_monthly_trend(self) -> Dict:
        """获取月趋势分析（30天）"""
        since = (datetime.now() - timedelta(days=30)).isoformat()
        
        # 按天聚合
        sql = """
            SELECT 
                DATE(timestamp) as day,
                COUNT(*) as checks,
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health,
                SUM(CASE WHEN unhealthy_services > 0 THEN 1 ELSE 0 END) as failure_events
            FROM health_check_logs 
            WHERE timestamp >= ?
            GROUP BY DATE(timestamp)
            ORDER BY day
        """
        
        daily = self._query(sql, (since,))
        
        # 计算月统计
        if daily:
            avg_monthly_health = sum(d.get('avg_health', 0) or 0 for d in daily) / len(daily)
            total_checks = sum(d.get('checks', 0) for d in daily)
            total_failures = sum(d.get('failure_events', 0) for d in daily)
            uptime_percentage = ((len(daily) - total_failures) / len(daily)) * 100 if daily else 0
            
            # 找出最佳和最差天
            best_day = max(daily, key=lambda x: x.get('avg_health', 0))
            worst_day = min(daily, key=lambda x: x.get('avg_health', 100))
        else:
            avg_monthly_health = 0
            total_checks = 0
            total_failures = 0
            uptime_percentage = 0
            best_day = None
            worst_day = None
        
        return {
            "period": "30 days",
            "daily_data": daily,
            "summary": {
                "avg_health": round(avg_monthly_health, 2),
                "total_checks": total_checks,
                "failure_events": total_failures,
                "uptime_percentage": round(uptime_percentage, 2),
                "best_day": best_day.get('day') if best_day else None,
                "best_day_health": round(best_day.get('avg_health', 0), 2) if best_day else None,
                "worst_day": worst_day.get('day') if worst_day else None,
                "worst_day_health": round(worst_day.get('avg_health', 0), 2) if worst_day else None
            }
        }
    
    def detect_anomalies(self, hours: int = 24, threshold: float = 15.0) -> Dict:
        """异常检测
        
        Args:
            hours: 分析时间范围
            threshold: 异常阈值（偏离平均值的百分比）
        """
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        # 获取时间序列
        sql = """
            SELECT timestamp, network_health, healthy_services, unhealthy_services
            FROM health_check_logs 
            WHERE timestamp >= ?
            ORDER BY timestamp
        """
        
        data = self._query(sql, (since,))
        
        if len(data) < 5:
            return {"status": "insufficient_data", "message": f"需要至少5个数据点，当前{len(data)}个"}
        
        health_values = [d['network_health'] for d in data]
        avg_health = sum(health_values) / len(health_values)
        
        # 检测异常点
        anomalies = []
        for d in data:
            deviation = d['network_health'] - avg_health
            if abs(deviation) > threshold:
                anomalies.append({
                    "timestamp": d['timestamp'],
                    "health": d['network_health'],
                    "deviation": round(deviation, 2),
                    "healthy_services": d['healthy_services'],
                    "unhealthy_services": d['unhealthy_services'],
                    "severity": "critical" if abs(deviation) > 30 else "warning"
                })
        
        # 统计异常
        critical_count = sum(1 for a in anomalies if a['severity'] == 'critical')
        warning_count = sum(1 for a in anomalies if a['severity'] == 'warning')
        
        return {
            "status": "success",
            "period_hours": hours,
            "threshold": threshold,
            "avg_health": round(avg_health, 2),
            "total_anomalies": len(anomalies),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "anomalies": anomalies[-20:]  # 最多返回20个
        }
    
    def get_health_score(self) -> Dict:
        """综合健康评分（0-100）"""
        # 取最近1小时数据
        stats_1h = self._get_quick_stats(1)
        # 取最近24小时数据
        stats_24h = self._get_quick_stats(24)
        
        # 计算评分
        # 1. 当前健康度 (40%)
        current_health = stats_1h.get('avg_health', 100)
        
        # 2. 稳定性 (30%) - 基于24小时波动
        stability = 100 - min(stats_24h.get('volatility', 0), 100)
        
        # 3. 可用率 (30%) - 基于24小时
        availability = stats_24h.get('availability', 100)
        
        # 综合评分
        score = (current_health * 0.4) + (stability * 0.3) + (availability * 0.3)
        
        # 确定状态
        if score >= 90:
            status = "excellent"
        elif score >= 75:
            status = "good"
        elif score >= 60:
            status = "fair"
        else:
            status = "poor"
        
        return {
            "score": round(score, 1),
            "status": status,
            "components": {
                "current_health": round(current_health, 1),
                "stability": round(stability, 1),
                "availability": round(availability, 1)
            },
            "period_1h": stats_1h,
            "period_24h": stats_24h
        }
    
    def _get_quick_stats(self, hours: int) -> Dict:
        """快速统计（内部使用）"""
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        sql = """
            SELECT 
                AVG(network_health) as avg_health,
                MIN(network_health) as min_health,
                MAX(network_health) as max_health,
                COUNT(*) as samples
            FROM health_check_logs 
            WHERE timestamp >= ?
        """
        
        row = self._query_one(sql, (since,))
        
        if not row or row.get('samples', 0) == 0:
            return {"avg_health": 100, "min_health": 100, "max_health": 100, "samples": 0, "volatility": 0, "availability": 100}
        
        # 计算波动性
        avg_h = row.get('avg_health', 100) or 100
        min_h = row.get('min_health', 100) or 100
        max_h = row.get('max_health', 100) or 100
        volatility = max_h - min_h
        
        # 计算可用率（健康检查占比）
        sql2 = """
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN unhealthy_services = 0 THEN 1 ELSE 0 END) as healthy
            FROM health_check_logs 
            WHERE timestamp >= ?
        """
        row2 = self._query_one(sql2, (since,))
        
        if row2 and row2.get('total', 0) > 0:
            availability = (row2.get('healthy', 0) / row2.get('total', 1)) * 100
        else:
            availability = 100
        
        return {
            "avg_health": round(avg_h, 1),
            "min_health": round(min_h, 1),
            "max_health": round(max_h, 1),
            "samples": row.get('samples', 0),
            "volatility": round(volatility, 1),
            "availability": round(availability, 1)
        }
    
    def generate_report(self, period: str = "24h") -> Dict:
        """生成趋势分析报告
        
        Args:
            period: 报告周期 (1h/6h/24h/7d/30d)
        """
        # 解析周期
        hours_map = {"1h": 1, "6h": 6, "24h": 24, "7d": 168, "30d": 720}
        hours = hours_map.get(period, 24)
        
        # 收集各项数据
        time_series = self.get_time_series(hours=hours)
        service_trends = self.get_service_trends(hours=hours)
        
        if hours <= 24:
            anomalies = self.detect_anomalies(hours=hours)
        else:
            anomalies = {"status": "skipped", "message": "周期大于24小时跳过异常检测"}
        
        health_score = self.get_health_score()
        
        # 获取预测
        from health_check_logger import HealthCheckLogger
        logger = HealthCheckLogger(self.db_path)
        prediction = logger.predict_health(hours_ahead=1)
        
        return {
            "report_period": period,
            "generated_at": datetime.now().isoformat(),
            "health_score": health_score,
            "time_series": time_series,
            "service_trends": service_trends,
            "anomalies": anomalies,
            "prediction": prediction
        }
    
    def get_chart_data(self, hours: int = 24) -> Dict:
        """获取图表所需的数据（前端可视化）"""
        time_series = self.get_time_series(hours=hours, interval="auto")
        service_trends = self.get_service_trends(hours=hours)
        
        # 格式化时间序列为图表数据
        chart_data = {
            "labels": [d['time_bucket'] for d in time_series.get('series', [])],
            "health": [d['avg_health'] for d in time_series.get('series', [])],
            "min_health": [d['min_health'] for d in time_series.get('series', [])],
            "max_health": [d['max_health'] for d in time_series.get('series', [])],
            "failures": [d['failure_count'] for d in time_series.get('series', [])]
        }
        
        # 服务可用率数据
        service_data = {}
        for svc in service_trends.get('services', []):
            service_data[svc['service']] = {
                "availability": svc['availability'],
                "trend": svc['trend'],
                "avg_response_time": svc['avg_response_time']
            }
        
        return {
            "period_hours": hours,
            "chart": chart_data,
            "services": service_data,
            "timestamp": datetime.now().isoformat()
        }


def main():
    """测试入口"""
    analyzer = HealthCheckTrendAnalyzer(DB_PATH)
    
    print("=== 健康检查历史趋势分析 ===\n")
    
    # 1. 健康评分
    print("1. 综合健康评分:")
    score = analyzer.get_health_score()
    print(f"   评分: {score['score']} ({score['status']})")
    print(f"   当前健康: {score['components']['current_health']}")
    print(f"   稳定性: {score['components']['stability']}")
    print(f"   可用率: {score['components']['availability']}\n")
    
    # 2. 服务趋势
    print("2. 服务趋势 (24h):")
    trends = analyzer.get_service_trends(hours=24)
    for svc in trends['services']:
        print(f"   {svc['service']}: {svc['availability']}% ({svc['trend']})")
    print()
    
    # 3. 周趋势
    print("3. 周趋势 (7天):")
    weekly = analyzer.get_weekly_trend()
    print(f"   平均健康度: {weekly['summary']['avg_health']}%")
    print(f"   可用率: {weekly['summary']['uptime_percentage']}%")
    print()
    
    # 4. 异常检测
    print("4. 异常检测 (24h):")
    anomalies = analyzer.detect_anomalies(hours=24)
    print(f"   状态: {anomalies.get('status', 'unknown')}")
    if anomalies.get('total_anomalies', 0) > 0:
        print(f"   异常数: {anomalies['total_anomalies']} (严重: {anomalies['critical_count']}, 警告: {anomalies['warning_count']})")
    else:
        print("   无异常")
    print()
    
    # 5. 图表数据
    print("5. 图表数据样本:")
    chart = analyzer.get_chart_data(hours=6)
    print(f"   数据点: {len(chart['chart']['labels'])}")
    print(f"   服务数: {len(chart['services'])}")


if __name__ == "__main__":
    main()