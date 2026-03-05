#!/usr/bin/env python3
"""
告警分析CLI工具
用法: python3 alert_analysis_cli.py [command]
"""

import argparse
import json
import sys
import os
import requests
from datetime import datetime

API_BASE = "http://localhost:8098"

def cmd_summary():
    """获取告警摘要"""
    r = requests.get(f"{API_BASE}/analysis/summary")
    print(r.json().get("summary", "无数据"))

def cmd_trends():
    """趋势分析"""
    r = requests.get(f"{API_BASE}/analysis/trends")
    data = r.json()
    print(f"📈 趋势分析")
    print(f"  总告警: {data.get('total_alerts', 0)}")
    print(f"  近6小时: {data.get('recent_6h', 0)}")
    print(f"  趋势: {data.get('trend', 'unknown')}")
    print(f"  级别分布: {data.get('level_distribution', {})}")

def cmd_patterns():
    """模式检测"""
    r = requests.get(f"{API_BASE}/analysis/patterns")
    patterns = r.json()
    print(f"🔍 检测到 {len(patterns)} 个模式")
    for p in patterns:
        print(f"  • [{p.get('severity', '')}] {p.get('type', '')}: {p.get('recommendation', '')[:60]}")

def cmd_predict():
    """预测"""
    r = requests.get(f"{API_BASE}/analysis/predict")
    preds = r.json()
    print(f"🔮 {len(preds)} 个预测")
    for p in preds:
        print(f"  • {p.get('recommendation', '')[:60]}")

def cmd_services():
    """服务健康"""
    r = requests.get(f"{API_BASE}/analysis/services")
    services = r.json()
    print(f"🏥 服务健康状况 ({len(services)} 个服务)")
    for svc, stats in services.items():
        score = stats.get('health_score', 100)
        emoji = "✅" if score > 80 else "⚠️" if score > 50 else "🔴"
        print(f"  {emoji} {svc}: 分数 {score} | 告警 {stats.get('total_alerts', 0)}")

def cmd_all():
    """完整报告"""
    print("="*50)
    print("     📊 智能告警分析报告")
    print(f"     时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("="*50)
    cmd_summary()
    print()
    cmd_trends()
    print()
    cmd_patterns()
    print()
    cmd_predict()
    print()
    cmd_services()
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description="智能告警分析工具")
    parser.add_argument("cmd", nargs="?", default="all", 
                       choices=["all", "summary", "trends", "patterns", "predict", "services"],
                       help="命令")
    
    args = parser.parse_args()
    
    cmds = {
        "all": cmd_all,
        "summary": cmd_summary,
        "trends": cmd_trends,
        "patterns": cmd_patterns,
        "predict": cmd_predict,
        "services": cmd_services
    }
    
    try:
        cmds[args.cmd]()
    except Exception as e:
        print(f"错误: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()