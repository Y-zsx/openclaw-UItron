#!/usr/bin/env python3
"""
增强版健康报告生成器
整合日志系统，提供更详细的趋势分析和历史对比
"""
import json
import sqlite3
import os
from pathlib import Path
from datetime import datetime, timedelta

DB_PATH = Path("/root/.openclaw/workspace/ultron/data/health_check_logs.db")
REPORTS_DIR = Path("/root/.openclaw/workspace/ultron/reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def get_availability(hours=24):
    """获取可用性统计"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT 
            service_name,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency,
            MIN(latency_ms) as min_latency,
            MAX(latency_ms) as max_latency
        FROM health_checks
        WHERE timestamp >= ?
        GROUP BY service_name
    ''', (since,))
    
    results = []
    for row in cursor.fetchall():
        service, total, healthy, avg_lat, min_lat, max_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        results.append({
            "service": service,
            "total_checks": total,
            "healthy_checks": healthy,
            "uptime_percent": round(uptime, 2),
            "avg_latency_ms": round(avg_lat, 2) if avg_lat else 0,
            "min_latency_ms": round(min_lat, 2) if min_lat else 0,
            "max_latency_ms": round(max_lat, 2) if max_lat else 0
        })
    
    conn.close()
    return results

def get_trend(service_name, hours=24):
    """获取趋势数据"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    # 按小时聚合
    cursor.execute('''
        SELECT 
            strftime('%Y-%m-%d %H:00', timestamp) as hour,
            COUNT(*) as total,
            SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy,
            AVG(latency_ms) as avg_latency
        FROM health_checks
        WHERE service_name = ? AND timestamp >= ?
        GROUP BY hour
        ORDER BY hour
    ''', (service_name, since))
    
    trend = []
    for row in cursor.fetchall():
        hour, total, healthy, avg_lat = row
        uptime = (healthy / total * 100) if total > 0 else 0
        trend.append({
            "hour": hour,
            "uptime_percent": round(uptime, 2),
            "latency_ms": round(avg_lat, 2) if avg_lat else 0
        })
    
    conn.close()
    return trend

def get_failures(hours=24, limit=20):
    """获取最近失败记录"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    since = (datetime.now() - timedelta(hours=hours)).isoformat()
    
    cursor.execute('''
        SELECT timestamp, service_name, port_status, http_status, latency_ms, details
        FROM health_checks
        WHERE status = 'unhealthy' AND timestamp >= ?
        ORDER BY timestamp DESC
        LIMIT ?
    ''', (since, limit))
    
    failures = []
    for row in cursor.fetchall():
        failures.append({
            "timestamp": row[0],
            "service": row[1],
            "port_status": bool(row[2]),
            "http_status": row[3],
            "latency_ms": row[4],
            "details": json.loads(row[5]) if row[5] else {}
        })
    
    conn.close()
    return failures

def compare_with_yesterday():
    """与昨天对比"""
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    yesterday_start = (now - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    yesterday_end = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    
    # 今天的可用性
    cursor.execute('''
        SELECT service_name, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy
        FROM health_checks
        WHERE timestamp >= ?
        GROUP BY service_name
    ''', (today_start,))
    
    today = {}
    for row in cursor.fetchall():
        service, total, healthy = row[0], row[1], row[2]
        today[service] = (healthy / total * 100) if total > 0 else 0
    
    # 昨天的可用性
    cursor.execute('''
        SELECT service_name, 
               COUNT(*) as total,
               SUM(CASE WHEN status = 'healthy' THEN 1 ELSE 0 END) as healthy
        FROM health_checks
        WHERE timestamp >= ? AND timestamp < ?
        GROUP BY service_name
    ''', (yesterday_start, yesterday_end))
    
    yesterday = {}
    for row in cursor.fetchall():
        service, total, healthy = row[0], row[1], row[2]
        yesterday[service] = (healthy / total * 100) if total > 0 else 0
    
    conn.close()
    
    # 计算变化
    comparison = []
    all_services = set(today.keys()) | set(yesterday.keys())
    for service in all_services:
        today_pct = today.get(service, 0)
        yesterday_pct = yesterday.get(service, 0)
        change = today_pct - yesterday_pct
        
        trend = "→"
        if change > 5:
            trend = "↑"
        elif change < -5:
            trend = "↓"
        
        comparison.append({
            "service": service,
            "today": round(today_pct, 1),
            "yesterday": round(yesterday_pct, 1),
            "change": round(change, 1),
            "trend": trend
        })
    
    return comparison

def generate_enhanced_report(hours=24):
    """生成增强版报告"""
    availability = get_availability(hours)
    failures = get_failures(hours)
    comparison = compare_with_yesterday()
    
    # 计算健康分数
    total = len(availability)
    healthy = sum(1 for a in availability if a["uptime_percent"] >= 99)
    degraded = sum(1 for a in availability if 95 <= a["uptime_percent"] < 99)
    unhealthy = sum(1 for a in availability if a["uptime_percent"] < 95)
    health_score = (healthy / total * 100) if total > 0 else 0
    
    # 趋势分析
    trends = {}
    for svc in availability:
        service_name = svc["service"]
        trend_data = get_trend(service_name, hours)
        if len(trend_data) >= 2:
            first = trend_data[0]["uptime_percent"]
            last = trend_data[-1]["uptime_percent"]
            trends[service_name] = "improving" if last > first else "degrading" if last < first else "stable"
        else:
            trends[service_name] = "unknown"
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "period_hours": hours,
        "health_score": round(health_score, 2),
        "status": "healthy" if health_score >= 95 else "degraded" if health_score >= 80 else "unhealthy",
        "summary": {
            "total_services": total,
            "healthy": healthy,
            "degraded": degraded,
            "unhealthy": unhealthy
        },
        "services": availability,
        "trends": trends,
        "recent_failures": failures,
        "yesterday_comparison": comparison,
        "recommendation": get_recommendation(health_score, unhealthy, failures)
    }
    
    return report

def get_recommendation(health_score, unhealthy_count, failures):
    """获取建议"""
    if health_score >= 95:
        return "All systems operational. Continue regular monitoring."
    elif health_score >= 80:
        return f"Attention needed: {unhealthy_count} service(s) degraded. Review failure logs."
    else:
        return f"CRITICAL: {unhealthy_count} service(s) unhealthy. Immediate action required!"

def save_report_json(report):
    """保存JSON格式报告"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"enhanced_health_{timestamp}.json"
    filepath = REPORTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    return str(filepath)

def save_report_markdown(report):
    """保存Markdown格式报告"""
    timestamp = datetime.now().strftime('%Y%m%d %H:%M')
    report_date = datetime.now().strftime('%Y年%m月%d日')
    
    md = f"""# 📊 健康检查报告 - {report_date}

**生成时间**: {timestamp}
**检查周期**: 过去 {report['period_hours']} 小时
**健康分数**: {report['health_score']}% ({report['status']})

---

## 📈 整体状态

| 指标 | 数值 |
|------|------|
| 总服务数 | {report['summary']['total_services']} |
| 健康 | ✅ {report['summary']['healthy']} |
| 降级 | ⚠️ {report['summary']['degraded']} |
| 不健康 | ❌ {report['summary']['unhealthy']} |

---

## 🔧 服务详情

| 服务 | 可用率 | 平均延迟 | 状态 |
|------|--------|----------|------|
"""
    
    for svc in report['services']:
        status_icon = "✅" if svc['uptime_percent'] >= 99 else "⚠️" if svc['uptime_percent'] >= 95 else "❌"
        trend = report['trends'].get(svc['service'], 'unknown')
        trend_icon = "↗" if trend == "improving" else "↘" if trend == "degrading" else "→"
        md += f"| {svc['service']} | {svc['uptime_percent']}% | {svc['avg_latency_ms']}ms | {status_icon} {trend_icon} |\n"
    
    if report['recent_failures']:
        md += f"""
---

## 🚨 最近失败 ({len(report['recent_failures'])}次)

| 时间 | 服务 | 延迟 |
|------|------|------|
"""
        for f in report['recent_failures'][:10]:
            md += f"| {f['timestamp'][:16]} | {f['service']} | {f['latency_ms']}ms |\n"
    
    if report['yesterday_comparison']:
        md += f"""
---

## 📅 昨日对比

| 服务 | 今日 | 昨日 | 变化 | 趋势 |
|------|------|------|------|------|
"""
        for c in report['yesterday_comparison']:
            md += f"| {c['service']} | {c['today']}% | {c['yesterday']}% | {c['change']:+.1f}% | {c['trend']} |\n"
    
    md += f"""
---

## 💡 建议

{report['recommendation']}

---

*🤖 奥创健康检查系统*
"""
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"health_report_{timestamp}.md"
    filepath = REPORTS_DIR / filename
    
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(md)
    
    return str(filepath)

def main():
    print("=" * 60)
    print("📊 增强版健康报告生成器")
    print("=" * 60)
    
    # 生成报告
    report = generate_enhanced_report(24)
    
    # 保存报告
    json_path = save_report_json(report)
    md_path = save_report_markdown(report)
    
    print(f"\n✅ 报告已保存:")
    print(f"   - JSON: {json_path}")
    print(f"   - Markdown: {md_path}")
    
    print(f"\n📊 健康分数: {report['health_score']}% ({report['status']})")
    print(f"   - 健康: {report['summary']['healthy']} 服务")
    print(f"   - 降级: {report['summary']['degraded']} 服务")
    print(f"   - 不健康: {report['summary']['unhealthy']} 服务")
    
    print(f"\n💡 {report['recommendation']}")
    
    return 0

if __name__ == "__main__":
    import sys
    sys.exit(main())