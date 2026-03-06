#!/usr/bin/env python3
"""
调度任务执行日志分析器
分析 scheduler_daemon.log 中的任务执行记录，提供统计和趋势分析
"""

import json
import re
import os
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

LOG_FILE = "/root/.openclaw/workspace/ultron-workflow/logs/scheduler_daemon.log"
STATS_FILE = "/root/.openclaw/workspace/ultron-workflow/logs/scheduler_stats.json"

class SchedulerLogAnalyzer:
    def __init__(self, log_file=LOG_FILE):
        self.log_file = log_file
        self.task_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*执行任务:\s*(\w+)'
        )
        self.complete_pattern = re.compile(
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d+)\s*-\s*完成: returncode=(\d+)'
        )
        
    def parse_log(self, lines=None):
        """解析日志文件，提取任务执行记录"""
        if lines is None:
            if not os.path.exists(self.log_file):
                return []
            with open(self.log_file, 'r') as f:
                lines = f.readlines()
        
        executions = []
        pending_task = None
        pending_start = None
        
        for line in lines:
            task_match = self.task_pattern.search(line)
            if task_match:
                pending_start = datetime.fromisoformat(task_match.group(1))
                pending_task = task_match.group(2)
                
            complete_match = self.complete_pattern.search(line)
            if complete_match and pending_task:
                end_time = datetime.fromisoformat(complete_match.group(1))
                return_code = int(complete_match.group(2))
                duration = (end_time - pending_start).total_seconds()
                
                executions.append({
                    'task': pending_task,
                    'start_time': pending_start.isoformat(),
                    'end_time': end_time.isoformat(),
                    'duration': round(duration, 3),
                    'return_code': return_code,
                    'success': return_code == 0
                })
                pending_task = None
                pending_start = None
                
        return executions
    
    def analyze(self, executions=None):
        """分析执行记录，生成统计报告"""
        if executions is None:
            executions = self.parse_log()
            
        if not executions:
            return {
                'summary': 'No executions found',
                'total_runs': 0,
                'success_rate': 0
            }
        
        # 任务级别统计
        task_stats = defaultdict(lambda: {'total': 0, 'success': 0, 'failures': 0, 'durations': []})
        
        for ex in executions:
            task = ex['task']
            task_stats[task]['total'] += 1
            if ex['success']:
                task_stats[task]['success'] += 1
            else:
                task_stats[task]['failures'] += 1
            task_stats[task]['durations'].append(ex['duration'])
        
        # 计算每个任务的平均执行时间
        for task in task_stats:
            durations = task_stats[task]['durations']
            task_stats[task]['avg_duration'] = round(sum(durations) / len(durations), 3)
            task_stats[task]['min_duration'] = round(min(durations), 3)
            task_stats[task]['max_duration'] = round(max(durations), 3)
            task_stats[task]['success_rate'] = round(
                task_stats[task]['success'] / task_stats[task]['total'] * 100, 2
            )
            del task_stats[task]['durations']  # 删除详细 durations
        
        # 总体统计
        total_runs = len(executions)
        total_success = sum(1 for ex in executions if ex['success'])
        success_rate = round(total_success / total_runs * 100, 2) if total_runs > 0 else 0
        avg_duration = round(sum(ex['duration'] for ex in executions) / total_runs, 3)
        
        # 最近1小时统计
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent = [ex for ex in executions 
                  if datetime.fromisoformat(ex['start_time']) > one_hour_ago]
        recent_success = sum(1 for ex in recent if ex['success'])
        recent_rate = round(recent_success / len(recent) * 100, 2) if recent else 0
        
        return {
            'summary': {
                'total_runs': total_runs,
                'success': total_success,
                'failures': total_runs - total_success,
                'success_rate': success_rate,
                'avg_duration': avg_duration,
                'last_hour': {
                    'runs': len(recent),
                    'success': recent_success,
                    'success_rate': recent_rate
                }
            },
            'task_stats': dict(task_stats),
            'latest_runs': executions[-10:] if len(executions) > 10 else executions,
            'analyzed_at': datetime.now().isoformat()
        }
    
    def get_task_trends(self, hours=6):
        """获取任务执行时间趋势（按小时）"""
        executions = self.parse_log()
        if not executions:
            return []
        
        cutoff = datetime.now() - timedelta(hours=hours)
        recent = [ex for ex in executions 
                  if datetime.fromisoformat(ex['start_time']) > cutoff]
        
        # 按小时分组
        hourly = defaultdict(lambda: {'total': 0, 'success': 0, 'duration_sum': 0})
        
        for ex in recent:
            hour = datetime.fromisoformat(ex['start_time']).strftime('%Y-%m-%d %H:00')
            hourly[hour]['total'] += 1
            if ex['success']:
                hourly[hour]['success'] += 1
            hourly[hour]['duration_sum'] += ex['duration']
        
        trends = []
        for hour in sorted(hourly.keys()):
            stats = hourly[hour]
            trends.append({
                'hour': hour,
                'total': stats['total'],
                'success': stats['success'],
                'success_rate': round(stats['success'] / stats['total'] * 100, 2),
                'avg_duration': round(stats['duration_sum'] / stats['total'], 3)
            })
        
        return trends
    
    def save_stats(self):
        """保存统计结果到文件"""
        stats = self.analyze()
        with open(STATS_FILE, 'w') as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)
        return stats


if __name__ == "__main__":
    import sys
    
    analyzer = SchedulerLogAnalyzer()
    
    if len(sys.argv) > 1:
        if sys.argv[1] == "--trends":
            trends = analyzer.get_task_trends(int(sys.argv[2]) if len(sys.argv) > 2 else 6)
            print(json.dumps(trends, indent=2))
        elif sys.argv[1] == "--save":
            stats = analyzer.save_stats()
            print(json.dumps(stats, indent=2, ensure_ascii=False))
        else:
            print("Usage: scheduler_log_analyzer.py [--trends hours] [--save]")
    else:
        stats = analyzer.analyze()
        print(json.dumps(stats, indent=2, ensure_ascii=False))