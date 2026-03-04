#!/usr/bin/env python3
"""
奥创智能数据分析与预测系统 v1.0
夙愿十二：智能数据分析与预测系统 - 第1世
功能：实时数据分析、趋势预测、智能决策建议
"""

import json
import os
from datetime import datetime, timedelta
from collections import defaultdict

HISTORY_FILE = "/root/.openclaw/workspace/ultron-self/monitor-history.jsonl"
OUTPUT_DIR = "/root/.openclaw/workspace/ultron-self/task-repo/analysis"
STATE_FILE = "/root/.openclaw/workspace/ultron-workflow/state.json"

def load_history():
    """加载监控历史数据"""
    data = []
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, 'r') as f:
            for line in f:
                try:
                    data.append(json.loads(line.strip()))
                except:
                    pass
    return data

def analyze_trends(data):
    """分析趋势"""
    if not data:
        return {}
    
    # 提取各指标
    loads = [float(d.get('load', 0)) for d in data]
    mems = [float(d.get('mem', 0)) for d in data]
    disks = [float(d.get('disk', 0)) for d in data]
    
    # 计算统计
    def stats(values):
        if not values:
            return {}
        return {
            'avg': sum(values) / len(values),
            'min': min(values),
            'max': max(values),
            'count': len(values)
        }
    
    return {
        'load': stats(loads),
        'memory': stats(mems),
        'disk': stats(disks),
        'time_range': {
            'start': data[0].get('time', ''),
            'end': data[-1].get('time', '')
        }
    }

def predict_trends(data):
    """简单的线性趋势预测"""
    if len(data) < 5:
        return "数据不足，无法预测"
    
    # 简单的移动平均预测
    recent = data[-6:]
    loads = [float(d.get('load', 0)) for d in recent]
    
    # 计算趋势
    if len(loads) >= 2:
        diff = loads[-1] - loads[0]
        if diff > 0.5:
            trend = "上升📈"
            advice = "负载呈上升趋势，建议关注"
        elif diff < -0.5:
            trend = "下降📉"
            advice = "负载下降，系统运行稳定"
        else:
            trend = "平稳➡️"
            advice = "负载保持稳定"
        
        return {
            'trend': trend,
            'change': round(diff, 2),
            'advice': advice,
            'prediction': "未来1小时内负载预计" + ("上升" if diff > 0 else "下降" if diff < 0 else "持平")
        }
    
    return {'trend': '未知', 'advice': '数据不足'}

def generate_suggestions(analysis, prediction):
    """生成智能建议"""
    suggestions = []
    
    # 基于内存分析
    mem_avg = analysis.get('memory', {}).get('avg', 0)
    if mem_avg > 80:
        suggestions.append("🔴 内存使用率过高，建议：1) 检查内存泄漏 2) 增加可用内存 3) 优化进程")
    elif mem_avg > 60:
        suggestions.append("🟡 内存使用率偏高，建议关注")
    
    # 基于负载分析
    load_avg = analysis.get('load', {}).get('avg', 0)
    if load_avg > 2:
        suggestions.append("🔴 系统负载过高，建议检查运行进程")
    elif load_avg > 1:
        suggestions.append("🟡 系统负载偏高")
    
    # 基于预测
    if isinstance(prediction, dict):
        pred = prediction.get('prediction', '')
        if '上升' in pred:
            suggestions.append("📊 预测负载将上升，建议提前做好准备")
    
    if not suggestions:
        suggestions.append("✅ 系统运行正常，无需特别关注")
    
    return suggestions

def main():
    print("🧠 奥创智能数据分析系统启动...")
    
    # 1. 加载数据
    data = load_history()
    print(f"📊 加载了 {len(data)} 条历史记录")
    
    if not data:
        print("❌ 无历史数据")
        return
    
    # 2. 分析趋势
    analysis = analyze_trends(data)
    print(f"📈 负载均值: {analysis['load']['avg']:.2f}")
    print(f"📈 内存均值: {analysis['memory']['avg']:.1f}%")
    print(f"📈 磁盘均值: {analysis['disk']['avg']:.1f}%")
    
    # 3. 预测趋势
    prediction = predict_trends(data)
    if isinstance(prediction, dict):
        print(f"🔮 趋势: {prediction.get('trend')} ({prediction.get('change')})")
        print(f"💡 {prediction.get('advice')}")
    
    # 4. 生成建议
    suggestions = generate_suggestions(analysis, prediction)
    print("\n🎯 智能建议:")
    for s in suggestions:
        print(f"  {s}")
    
    # 5. 保存报告
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    report = {
        'time': datetime.now().isoformat(),
        'analysis': analysis,
        'prediction': prediction,
        'suggestions': suggestions
    }
    
    report_file = f"{OUTPUT_DIR}/report-{datetime.now().strftime('%Y%m%d%H%M%S')}.json"
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ 报告已保存: {report_file}")
    
    return report

if __name__ == "__main__":
    main()