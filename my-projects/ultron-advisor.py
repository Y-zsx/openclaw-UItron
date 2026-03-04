#!/usr/bin/env python3
"""
奥创智能顾问 - 系统优化建议生成器
分析系统状态，提供优化建议
"""
import json
import subprocess
import os
from datetime import datetime

def get_system_metrics():
    """获取系统指标"""
    metrics = {}
    
    # CPU负载
    try:
        with open('/proc/loadavg') as f:
            load = f.read().split()[:3]
            metrics['load'] = [float(x) for x in load]
    except:
        metrics['load'] = [0, 0, 0]
    
    # 内存使用
    try:
        result = subprocess.run(['free', '-m'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            mem = lines[1].split()
            metrics['memory'] = {
                'total': int(mem[1]),
                'used': int(mem[2]),
                'free': int(mem[3])
            }
    except:
        metrics['memory'] = {'total': 0, 'used': 0, 'free': 0}
    
    # 磁盘使用
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
        lines = result.stdout.strip().split('\n')
        if len(lines) > 1:
            disk = lines[1].split()
            metrics['disk'] = {
                'total': disk[1],
                'used': disk[2],
                'avail': disk[3],
                'percent': disk[4]
            }
    except:
        metrics['disk'] = {}
    
    # 运行时间
    try:
        result = subprocess.run(['uptime', '-p'], capture_output=True, text=True)
        metrics['uptime'] = result.stdout.strip()
    except:
        metrics['uptime'] = 'unknown'
    
    return metrics

def analyze_and_suggest(metrics):
    """分析指标并生成建议"""
    suggestions = []
    
    # CPU负载分析
    load = metrics.get('load', [0, 0, 0])
    if load[0] > 2.0:
        suggestions.append({
            'type': 'cpu',
            'level': 'warning',
            'message': f'CPU负载较高 (15分钟平均: {load[2]:.2f})，建议检查运行中的进程'
        })
    elif load[0] < 0.5:
        suggestions.append({
            'type': 'cpu',
            'level': 'good',
            'message': 'CPU负载正常，系统运行流畅'
        })
    
    # 内存分析
    mem = metrics.get('memory', {})
    if mem:
        usage_pct = (mem['used'] / mem['total'] * 100) if mem['total'] > 0 else 0
        if usage_pct > 85:
            suggestions.append({
                'type': 'memory',
                'level': 'warning',
                'message': f'内存使用率较高 ({usage_pct:.1f}%)，考虑释放内存'
            })
        elif usage_pct < 50:
            suggestions.append({
                'type': 'memory',
                'level': 'good',
                'message': f'内存充足，使用率 {usage_pct:.1f}%'
            })
    
    # 磁盘分析
    disk = metrics.get('disk', {})
    if disk:
        pct = disk.get('percent', '0%').replace('%', '')
        try:
            pct = int(pct)
            if pct > 85:
                suggestions.append({
                    'type': 'disk',
                    'level': 'warning',
                    'message': f'磁盘使用率较高 ({pct}%)，建议清理日志或缓存'
                })
            else:
                suggestions.append({
                    'type': 'disk',
                    'level': 'good',
                    'message': f'磁盘空间充足，使用率 {pct}%'
                })
        except:
            pass
    
    return suggestions

def main():
    print("=" * 50)
    print("  奥创智能顾问 🦞 - 系统分析")
    print("=" * 50)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # 获取指标
    metrics = get_system_metrics()
    
    print("📊 系统状态:")
    print(f"  运行时间: {metrics.get('uptime', 'N/A')}")
    print(f"  CPU负载: {metrics.get('load', [0,0,0])}")
    if metrics.get('memory'):
        mem = metrics['memory']
        print(f"  内存: {mem['used']}MB / {mem['total']}MB")
    if metrics.get('disk'):
        d = metrics['disk']
        print(f"  磁盘: {d['used']} / {d['total']} (可用 {d['avail']})")
    
    print()
    print("💡 优化建议:")
    suggestions = analyze_and_suggest(metrics)
    
    if suggestions:
        for s in suggestions:
            emoji = '✅' if s['level'] == 'good' else '⚠️'
            print(f"  {emoji} {s['message']}")
    else:
        print("  ✅ 系统运行正常，无特殊建议")
    
    print()
    print("=" * 50)
    
    # 返回JSON格式供程序使用
    return {
        'timestamp': datetime.now().isoformat(),
        'metrics': metrics,
        'suggestions': suggestions
    }

if __name__ == '__main__':
    result = main()
    # 可选：保存到日志
    log_file = '/root/.openclaw/workspace/ultron/logs/advisor.log'
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    with open(log_file, 'a') as f:
        f.write(json.dumps(result) + '\n')