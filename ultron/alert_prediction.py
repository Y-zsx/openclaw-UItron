#!/usr/bin/env python3
"""
告警预测与预防性分析服务
基于历史数据预测未来告警并提供预防建议
端口: 18225
"""

import json
import os
import sqlite3
import math
from datetime import datetime, timedelta
from collections import defaultdict
from flask import Flask, jsonify, request

app = Flask(__name__)

DB_FILE = "/root/.openclaw/workspace/ultron/data/alerts.db"

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def calculate_trend(values):
    """计算趋势（简单线性回归）"""
    if len(values) < 2:
        return 0
    
    n = len(values)
    x = list(range(n))
    y = values
    
    # 计算斜率
    x_mean = sum(x) / n
    y_mean = sum(y) / n
    
    numerator = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n))
    denominator = sum((x[i] - x_mean) ** 2 for i in range(n))
    
    if denominator == 0:
        return 0
    
    slope = numerator / denominator
    return slope

def predict_next(values, periods=1):
    """预测下一个值"""
    if len(values) < 2:
        return values[-1] if values else 0
    
    # 使用指数移动平均
    alpha = 0.3
    predicted = values[-1]
    for _ in range(periods):
        predicted = alpha * predicted + (1 - alpha) * sum(values) / len(values)
    
    return max(0, predicted)

def analyze_patterns():
    """分析告警模式"""
    conn = get_db()
    c = conn.cursor()
    
    # 获取过去7天的数据
    start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    c.execute("SELECT timestamp, level, service, metric FROM alerts WHERE timestamp >= ?", (start,))
    
    alerts = c.fetchall()
    conn.close()
    
    # 按小时统计
    hourly = defaultdict(int)
    # 按天统计
    daily = defaultdict(int)
    # 按服务统计
    by_service = defaultdict(int)
    # 按级别统计
    by_level = defaultdict(int)
    
    for alert in alerts:
        ts = alert['timestamp']
        if ts:
            try:
                dt = datetime.strptime(ts, '%Y-%m-%d %H:%M:%S')
                hourly[dt.hour] += 1
                daily[dt.strftime('%Y-%m-%d')] += 1
            except:
                pass
        
        if alert['service']:
            by_service[alert['service']] += 1
        if alert['level']:
            by_level[alert['level']] += 1
    
    return {
        "hourly": dict(hourly),
        "daily": dict(daily),
        "by_service": dict(by_service),
        "by_level": dict(by_level)
    }

def generate_predictions():
    """生成预测"""
    conn = get_db()
    c = conn.cursor()
    
    predictions = []
    
    # 分析最近30天的告警
    start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    # 按天统计
    c.execute("""SELECT DATE(timestamp) as date, COUNT(*) as cnt 
        FROM alerts WHERE timestamp >= ? GROUP BY DATE(timestamp) ORDER BY date""", (start,))
    daily_counts = [row[1] for row in c.fetchall()]
    
    if daily_counts:
        # 预测明日告警数量
        predicted_tomorrow = predict_next(daily_counts)
        trend = calculate_trend(daily_counts[-7:])  # 最近7天趋势
        
        predictions.append({
            "metric": "daily_alerts",
            "current": daily_counts[-1] if daily_counts else 0,
            "predicted": round(predicted_tomorrow, 1),
            "trend": "increasing" if trend > 0.1 else "decreasing" if trend < -0.1 else "stable",
            "trend_value": round(trend, 2)
        })
    
    # 按服务统计并预测
    c.execute("""SELECT service, COUNT(*) as cnt 
        FROM alerts WHERE timestamp >= ? AND service IS NOT NULL 
        GROUP BY service ORDER BY cnt DESC LIMIT 5""", (start,))
    
    service_predictions = []
    for row in c.fetchall():
        service = row[0]
        count = row[1]
        
        # 获取该服务的历史数据
        c.execute("""SELECT DATE(timestamp) as date, COUNT(*) as cnt 
            FROM alerts WHERE timestamp >= ? AND service = ?
            GROUP BY DATE(timestamp) ORDER BY date""", (start, service))
        
        service_daily = [r[1] for r in c.fetchall()]
        
        if service_daily:
            predicted = predict_next(service_daily)
            trend = calculate_trend(service_daily[-7:])
            
            service_predictions.append({
                "service": service,
                "current": count,
                "predicted_7d": round(predicted * 7, 1),
                "trend": "increasing" if trend > 0.1 else "decreasing" if trend < -0.1 else "stable"
            })
    
    conn.close()
    
    return {
        "overall": predictions,
        "by_service": service_predictions
    }

def generate_preventive_suggestions():
    """生成预防建议"""
    conn = get_db()
    c = conn.cursor()
    
    suggestions = []
    
    # 分析高频告警服务
    start = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
    c.execute("""SELECT service, COUNT(*) as cnt 
        FROM alerts WHERE timestamp >= ? AND service IS NOT NULL 
        GROUP BY service HAVING cnt > 5 ORDER BY cnt DESC""", (start,))
    
    for row in c.fetchall():
        service = row[0]
        count = row[1]
        
        suggestions.append({
            "type": "service",
            "priority": "high" if count > 20 else "medium",
            "target": service,
            "issue": f"过去7天产生 {count} 条告警",
            "suggestion": f"建议检查{service}服务的配置和运行状态，考虑增加监控指标或优化服务性能"
        })
    
    # 分析失败率高的任务
    c.execute("""SELECT status, COUNT(*) as cnt 
        FROM alerts WHERE timestamp >= ? 
        GROUP BY status""", (start,))
    
    status_counts = {row[0]: row[1] for row in c.fetchall()}
    total = sum(status_counts.values())
    
    if total > 0:
        error_rate = (status_counts.get('error', 0) + status_counts.get('failed', 0)) / total * 100
        
        if error_rate > 10:
            suggestions.append({
                "type": "failure",
                "priority": "critical",
                "target": "系统",
                "issue": f"失败率 {error_rate:.1f}%",
                "suggestion": "失败率较高，建议检查错误日志并增加重试机制"
            })
        elif error_rate > 5:
            suggestions.append({
                "type": "failure", 
                "priority": "medium",
                "target": "系统",
                "issue": f"失败率 {error_rate:.1f}%",
                "suggestion": "失败率略有上升，建议关注"
            })
    
    # 分析响应时间
    c.execute("""SELECT AVG(value) as avg_val, MAX(value) as max_val 
        FROM alerts WHERE metric = 'response_time' AND timestamp >= ?""", (start,))
    row = c.fetchone()
    
    if row and row[0]:
        avg_response = row[0]
        max_response = row[1] or 0
        
        if avg_response > 1000:
            suggestions.append({
                "type": "performance",
                "priority": "high",
                "target": "API响应",
                "issue": f"平均响应时间 {avg_response:.0f}ms",
                "suggestion": "响应时间较长，建议启用缓存或优化数据库查询"
            })
        
        if max_response > 5000:
            suggestions.append({
                "type": "performance",
                "priority": "medium",
                "target": "API响应",
                "issue": f"最大响应时间 {max_response:.0f}ms",
                "suggestion": "存在响应超时风险，建议增加超时配置和重试机制"
            })
    
    conn.close()
    
    return suggestions

@app.route('/api/predict', methods=['GET'])
def predict():
    """获取预测数据"""
    predictions = generate_predictions()
    
    return jsonify({
        "status": "ok",
        "predictions": predictions,
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/patterns', methods=['GET'])
def patterns():
    """获取告警模式分析"""
    patterns = analyze_patterns()
    
    return jsonify({
        "status": "ok",
        "patterns": patterns,
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/suggestions', methods=['GET'])
def suggestions():
    """获取预防建议"""
    suggestions = generate_preventive_suggestions()
    
    return jsonify({
        "status": "ok",
        "suggestions": suggestions,
        "count": len(suggestions),
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/analysis', methods=['GET'])
def full_analysis():
    """完整分析（预测+模式+建议）"""
    predictions = generate_predictions()
    patterns = analyze_patterns()
    suggestions = generate_preventive_suggestions()
    
    # 计算风险评分
    risk_score = 0
    
    for pred in predictions.get('overall', []):
        if pred.get('trend') == 'increasing':
            risk_score += 20
    
    for sugg in suggestions:
        if sugg.get('priority') == 'critical':
            risk_score += 30
        elif sugg.get('priority') == 'high':
            risk_score += 15
    
    risk_level = "low" if risk_score < 30 else "medium" if risk_score < 60 else "high"
    
    return jsonify({
        "status": "ok",
        "analysis": {
            "predictions": predictions,
            "patterns": patterns,
            "suggestions": suggestions,
            "risk_assessment": {
                "score": min(100, risk_score),
                "level": risk_level
            }
        },
        "generated_at": datetime.now().isoformat()
    })

@app.route('/api/forecast', methods=['GET'])
def forecast():
    """预测指定指标的未来值"""
    metric = request.args.get('metric', 'alerts')
    periods = request.args.get('periods', 7, type=int)
    
    conn = get_db()
    c = conn.cursor()
    
    start = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    
    if metric == 'alerts':
        c.execute("""SELECT DATE(timestamp) as date, COUNT(*) as cnt 
            FROM alerts GROUP BY DATE(timestamp) ORDER BY date""")
        values = [row[1] for row in c.fetchall()]
    else:
        c.execute("""SELECT DATE(timestamp) as date, AVG(value) as avg_val 
            FROM alerts WHERE metric = ? AND timestamp >= ?
            GROUP BY DATE(timestamp) ORDER BY date""", (metric, start))
        values = [row[1] for row in c.fetchall() if row[1]]
    
    conn.close()
    
    if not values:
        return jsonify({
            "status": "ok",
            "metric": metric,
            "forecast": [],
            "message": "No historical data available"
        })
    
    # 生成预测
    forecast_values = []
    current_values = values.copy()
    
    for i in range(periods):
        predicted = predict_next(current_values, i + 1)
        current_values.append(predicted)
        
        forecast_date = (datetime.now() + timedelta(days=i+1)).strftime('%Y-%m-%d')
        forecast_values.append({
            "date": forecast_date,
            "predicted": round(predicted, 1)
        })
    
    return jsonify({
        "status": "ok",
        "metric": metric,
        "current": values[-1] if values else 0,
        "forecast": forecast_values,
        "periods": periods
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "alert-prediction",
        "port": 18225
    })

if __name__ == '__main__':
    print("启动告警预测与预防性分析服务...")
    print(f"端口: 18225")
    app.run(host='0.0.0.0', port=18225, debug=False)