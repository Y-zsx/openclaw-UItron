#!/usr/bin/env python3
"""
调度任务执行日志分析器
分析任务执行日志，提供统计和告警
"""
import os, json
from datetime import datetime, timedelta
from collections import defaultdict

WORKSPACE = '/root/.openclaw/workspace'
LOG_DIR = f'{WORKSPACE}/ultron-workflow/logs'
ANALYSIS_FILE = f'{LOG_DIR}/task_analysis.json'

def analyze_log_file(filepath):
    """分析单个日志文件"""
    if not os.path.exists(filepath):
        return None
    
    stats = {
        'total_lines': 0,
        'errors': 0,
        'warnings': 0,
        'info': 0,
        'last_entry': None,
        'first_entry': None
    }
    
    try:
        with open(filepath) as f:
            lines = f.readlines()
            stats['total_lines'] = len(lines)
            
            for line in lines[-100:]:  # 只读最后100行
                line = line.lower()
                if 'error' in line:
                    stats['errors'] += 1
                elif 'warning' in line:
                    stats['warnings'] += 1
                elif 'info' in line or 'ok' in line or 'complete' in line:
                    stats['info'] += 1
                
                # 提取时间戳
                if '2026-' in line:
                    try:
                        ts = line.split('2026-')[1][:19]
                        ts = '2026-' + ts
                        if not stats['first_entry']:
                            stats['first_entry'] = ts
                        stats['last_entry'] = ts
                    except:
                        pass
        
        return stats
    except Exception as e:
        return {'error': str(e)}

def analyze_all_logs():
    """分析所有日志"""
    log_files = [
        ('task_scheduler.log', '调度器'),
        ('cron_health_trigger.log', '健康检查'),
        ('metrics_collector.log', '指标收集'),
        ('health_api.log', 'API服务'),
        ('health_scheduler.log', '健康调度'),
        ('cron_sync.log', 'Cron同步')
    ]
    
    results = {
        'timestamp': datetime.now().isoformat(),
        'logs': {}
    }
    
    for filename, name in log_files:
        filepath = f'{LOG_DIR}/{filename}'
        stats = analyze_log_file(filepath)
        if stats:
            results['logs'][name] = stats
    
    # 计算汇总统计
    total_errors = sum(l.get('errors', 0) for l in results['logs'].values())
    total_warnings = sum(l.get('warnings', 0) for l in results['logs'].values())
    
    results['summary'] = {
        'total_errors': total_errors,
        'total_warnings': total_warnings,
        'healthy': total_errors == 0,
        'logs_analyzed': len(results['logs'])
    }
    
    return results

def save_analysis(results):
    """保存分析结果"""
    with open(ANALYSIS_FILE, 'w') as f:
        json.dump(results, f, indent=2)

if __name__ == '__main__':
    results = analyze_all_logs()
    save_analysis(results)
    
    # 打印摘要
    print(f"日志分析完成:")
    print(f"  分析日志数: {results['summary']['logs_analyzed']}")
    print(f"  总错误数: {results['summary']['total_errors']}")
    print(f"  总警告数: {results['summary']['total_warnings']}")
    print(f"  健康状态: {results['summary']['healthy']}")
    
    for name, stats in results['logs'].items():
        if 'error' not in stats:
            print(f"  - {name}: {stats.get('total_lines', 0)}行, {stats.get('errors', 0)}错误")
