#!/usr/bin/env python3
"""
增强版日志分析自动化工具
功能：自动分析日志、异常检测、趋势预测、自动告警
"""
import json
import os
import re
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from collections import defaultdict
import threading

WORKSPACE = "/root/.openclaw/workspace"
LOGS_DIR = f"{WORKSPACE}/logs"
DB_PATH = f"{WORKSPACE}/ultron/enhanced_logs.db"
ANALYSIS_REPORT = f"{WORKSPACE}/ultron/data/log_analysis_report.json"

class EnhancedLogAnalyzer:
    def __init__(self):
        self.db_path = DB_PATH
        self.log_patterns = {
            'error': re.compile(r'\b(ERROR|error|Error|FATAL|fatal)\b'),
            'warning': re.compile(r'\b(WARN|warn|Warning|warning)\b'),
            'exception': re.compile(r'\b(Exception|EXCEPTION|Traceback|traceback)\b'),
            'timeout': re.compile(r'\b(timeout|Timeout|TIMEOUT)\b'),
            'connection': re.compile(r'\b(connection|Connection|connect|Connect)\b.*(failed|error|refused|Failed|Error|refused)'),
        }
        self._ensure_db()
        self._ensure_data_dir()
    
    def _ensure_data_dir(self):
        os.makedirs(f"{WORKSPACE}/ultron/data", exist_ok=True)
    
    def _ensure_db(self):
        """确保数据库存在"""
        os.makedirs(os.path.dirname(self.db_path.replace(".db", "")), exist_ok=True)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 日志条目表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_entries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_file TEXT NOT NULL,
                timestamp TEXT,
                level TEXT,
                message TEXT,
                source TEXT,
                line_number INTEGER,
                analyzed_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 分析报告表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS analysis_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                total_logs INTEGER,
                error_count INTEGER,
                warning_count INTEGER,
                exception_count INTEGER,
                timeout_count INTEGER,
                top_errors TEXT,
                trend TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 告警表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                severity TEXT NOT NULL,
                message TEXT NOT NULL,
                source TEXT,
                resolved INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                resolved_at TEXT
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def scan_log_files(self):
        """扫描日志文件"""
        log_files = []
        
        # 扫描多个日志目录
        for log_dir in [LOGS_DIR, f"{WORKSPACE}/.openclaw/logs", "/var/log"]:
            if os.path.exists(log_dir):
                for root, dirs, files in os.walk(log_dir):
                    for f in files:
                        if f.endswith('.log') or f.endswith('.txt'):
                            full_path = os.path.join(root, f)
                            try:
                                size = os.path.getsize(full_path)
                                if size > 0 and size < 50*1024*1024:  # < 50MB
                                    log_files.append(full_path)
                            except:
                                pass
        
        return log_files[:20]  # 最多分析20个文件
    
    def analyze_log_file(self, filepath):
        """分析单个日志文件"""
        results = {
            'total_lines': 0,
            'errors': [],
            'warnings': [],
            'exceptions': [],
            'timeouts': [],
            'connections': [],
        }
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    results['total_lines'] += 1
                    
                    if self.log_patterns['error'].search(line):
                        results['errors'].append({
                            'line': line_num,
                            'content': line.strip()[:200]
                        })
                    
                    if self.log_patterns['warning'].search(line):
                        results['warnings'].append({
                            'line': line_num,
                            'content': line.strip()[:200]
                        })
                    
                    if self.log_patterns['exception'].search(line):
                        results['exceptions'].append({
                            'line': line_num,
                            'content': line.strip()[:200]
                        })
                    
                    if self.log_patterns['timeout'].search(line):
                        results['timeouts'].append({
                            'line': line_num,
                            'content': line.strip()[:200]
                        })
                    
                    if self.log_patterns['connection'].search(line):
                        results['connections'].append({
                            'line': line_num,
                            'content': line.strip()[:200]
                        })
                    
                    # 只分析前10000行
                    if line_num >= 10000:
                        break
        
        except Exception as e:
            results['error'] = str(e)
        
        return results
    
    def detect_anomalies(self, results):
        """检测异常模式"""
        anomalies = []
        
        # 错误数量异常
        if len(results['errors']) > 10:
            anomalies.append({
                'type': 'high_error_rate',
                'severity': 'warning',
                'message': f"发现 {len(results['errors'])} 个错误日志",
                'count': len(results['errors'])
            })
        
        # 异常过多
        if len(results['exceptions']) > 5:
            anomalies.append({
                'type': 'high_exception_rate',
                'severity': 'error',
                'message': f"发现 {len(results['exceptions'])} 个异常",
                'count': len(results['exceptions'])
            })
        
        # 超时问题
        if len(results['timeouts']) > 3:
            anomalies.append({
                'type': 'timeout_issues',
                'severity': 'warning',
                'message': f"发现 {len(results['timeouts'])} 个超时",
                'count': len(results['timeouts'])
            })
        
        # 连接问题
        if len(results['connections']) > 2:
            anomalies.append({
                'type': 'connection_issues',
                'severity': 'warning',
                'message': f"发现 {len(results['connections'])} 个连接失败",
                'count': len(results['connections'])
            })
        
        return anomalies
    
    def generate_report(self):
        """生成分析报告"""
        print("🔍 开始增强日志分析...")
        
        log_files = self.scan_log_files()
        print(f"📁 发现 {len(log_files)} 个日志文件")
        
        all_results = {}
        total_errors = 0
        total_warnings = 0
        total_exceptions = 0
        total_timeouts = 0
        
        for filepath in log_files:
            filename = os.path.basename(filepath)
            print(f"  分析: {filename}")
            results = self.analyze_log_file(filepath)
            all_results[filename] = results
            
            total_errors += len(results['errors'])
            total_warnings += len(results['warnings'])
            total_exceptions += len(results['exceptions'])
            total_timeouts += len(results['timeouts'])
        
        # 检测异常
        all_anomalies = []
        for filename, results in all_results.items():
            anomalies = self.detect_anomalies(results)
            for a in anomalies:
                a['source'] = filename
            all_anomalies.extend(anomalies)
        
        # 保存报告
        report = {
            'analyzed_at': datetime.now().isoformat(),
            'files_count': len(log_files),
            'summary': {
                'total_errors': total_errors,
                'total_warnings': total_warnings,
                'total_exceptions': total_exceptions,
                'total_timeouts': total_timeouts,
            },
            'anomalies': all_anomalies,
            'files': {}
        }
        
        # 只保存有问题或关键的文件
        for filename, results in all_results.items():
            if results['errors'] or results['exceptions']:
                report['files'][filename] = {
                    'errors': results['errors'][:5],
                    'warnings': results['warnings'][:3],
                    'exceptions': results['exceptions'][:5],
                }
        
        # 保存到文件
        with open(ANALYSIS_REPORT, 'w') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        
        # 保存到数据库
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        top_errors = json.dumps([
            a['message'] for a in all_anomalies[:5]
        ])
        
        cursor.execute('''
            INSERT INTO analysis_reports 
            (report_date, total_logs, error_count, warning_count, exception_count, timeout_count, top_errors)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().strftime('%Y-%m-%d'),
            len(log_files),
            total_errors,
            total_warnings,
            total_exceptions,
            total_timeouts,
            top_errors
        ))
        
        # 保存告警
        for anomaly in all_anomalies:
            cursor.execute('''
                INSERT INTO alerts (alert_type, severity, message, source)
                VALUES (?, ?, ?, ?)
            ''', (anomaly['type'], anomaly['severity'], anomaly['message'], anomaly.get('source')))
        
        conn.commit()
        conn.close()
        
        print(f"\n✅ 分析完成!")
        print(f"   错误: {total_errors}, 警告: {total_warnings}, 异常: {total_exceptions}, 超时: {total_timeouts}")
        
        if all_anomalies:
            print(f"\n⚠️  发现 {len(all_anomalies)} 个异常:")
            for a in all_anomalies[:5]:
                print(f"   [{a['severity'].upper()}] {a['message']}")
        else:
            print(f"\n✅ 没有发现异常!")
        
        return report

def main():
    analyzer = EnhancedLogAnalyzer()
    report = analyzer.generate_report()
    
    # 输出摘要
    print(f"\n📊 报告已保存: {ANALYSIS_REPORT}")

if __name__ == "__main__":
    main()