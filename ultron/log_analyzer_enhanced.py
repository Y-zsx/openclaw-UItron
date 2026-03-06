#!/usr/bin/env python3
"""
Enhanced Log Analyzer API
Provides advanced log analysis capabilities with pattern recognition,
error aggregation, and real-time log monitoring.
"""

import json
import os
import re
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading
import time

LOG_DIR = "/root/.openclaw/workspace/ultron/logs"
DB_PATH = "/root/.openclaw/workspace/ultron/log_analyzer.db"

# Log patterns - support both [LEVEL] and plain text formats
LOG_PATTERNS = {
    'error': re.compile(r'\[(ERROR|FATAL|CRITICAL)\]|\b(ERROR|error|ERROR:|FATAL|Fatal|fatal|CRITICAL|Critical)\b'),
    'warning': re.compile(r'\[(WARNING|WARN)\]|\b(WARNING|Warning|WARN|Warn|WARN:)\b'),
    'info': re.compile(r'\[(INFO)\]|\b(INFO|Info|INFO:)\b'),
    'debug': re.compile(r'\[(DEBUG)\]|\b(DEBUG|Debug|DEBUG:)\b'),
}

SEVERITY_LEVELS = {
    'FATAL': 5,
    'CRITICAL': 4,
    'ERROR': 3,
    'WARNING': 2,
    'INFO': 1,
    'DEBUG': 0,
}

def init_db():
    """Initialize the SQLite database for log analysis."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_file TEXT NOT NULL,
            log_level TEXT,
            timestamp TEXT,
            message TEXT,
            pattern_type TEXT,
            count INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS error_patterns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pattern TEXT NOT NULL,
            occurrences INTEGER DEFAULT 1,
            first_seen TIMESTAMP,
            last_seen TIMESTAMP,
            severity TEXT,
            source_files TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS log_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            log_file TEXT NOT NULL,
            total_lines INTEGER,
            error_count INTEGER,
            warning_count INTEGER,
            info_count INTEGER,
            debug_count INTEGER,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    return conn

def analyze_log_file(filepath):
    """Analyze a single log file and return statistics."""
    stats = {
        'total_lines': 0,
        'errors': 0,
        'warnings': 0,
        'infos': 0,
        'debugs': 0,
        'error_messages': [],
        'warning_messages': [],
        'patterns': [],
    }
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stats['total_lines'] += 1
                line = line.strip()
                
                if LOG_PATTERNS['error'].search(line):
                    stats['errors'] += 1
                    if len(stats['error_messages']) < 20:
                        stats['error_messages'].append(line[:200])
                elif LOG_PATTERNS['warning'].search(line):
                    stats['warnings'] += 1
                    if len(stats['warning_messages']) < 20:
                        stats['warning_messages'].append(line[:200])
                elif LOG_PATTERNS['info'].search(line):
                    stats['infos'] += 1
                elif LOG_PATTERNS['debug'].search(line):
                    stats['debugs'] += 1
                    
    except Exception as e:
        stats['error'] = str(e)
    
    return stats

def extract_error_patterns(error_messages):
    """Extract common error patterns from error messages."""
    patterns = []
    
    # Common pattern extractors
    pattern_rules = [
        (r'([a-zA-Z_]+Error|[a-zA-Z_]+Exception): (.+)', 'exception'),
        (r'Connection (refused|timeout|reset)', 'connection'),
        (r'Permission denied', 'permission'),
        (r'File not found: (.+)', 'file_not_found'),
        (r'Timeout.*(\d+)s', 'timeout'),
        (r'Memory.*(\d+)MB', 'memory'),
        (r'Port.*(\d+)', 'port'),
    ]
    
    for msg in error_messages:
        for pattern, ptype in pattern_rules:
            match = re.search(pattern, msg)
            if match:
                patterns.append({
                    'type': ptype,
                    'message': msg[:100],
                    'match': match.group(0)[:50]
                })
                break
    
    return patterns

def analyze_all_logs():
    """Analyze all log files in the logs directory."""
    results = {}
    all_errors = []
    
    log_files = [f for f in os.listdir(LOG_DIR) if f.endswith('.log') or f.endswith('.error.log')]
    log_files = sorted(log_files, key=lambda x: os.path.getsize(os.path.join(LOG_DIR, x)), reverse=True)[:15]
    
    for log_file in log_files:
        filepath = os.path.join(LOG_DIR, log_file)
        stats = analyze_log_file(filepath)
        results[log_file] = stats
        
        if stats.get('error_messages'):
            all_errors.extend([(log_file, msg) for msg in stats['error_messages']])
    
    # Extract patterns
    error_patterns = extract_error_patterns([e[1] for e in all_errors])
    
    return {
        'files': results,
        'total_errors': sum(s['errors'] for s in results.values()),
        'total_warnings': sum(s['warnings'] for s in results.values()),
        'error_patterns': error_patterns[:10],
        'timestamp': datetime.now().isoformat()
    }

def store_analysis(conn, analysis):
    """Store analysis results in database."""
    cursor = conn.cursor()
    
    for filename, stats in analysis['files'].items():
        cursor.execute('''
            INSERT INTO log_stats 
            (log_file, total_lines, error_count, warning_count, info_count, debug_count)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (filename, stats['total_lines'], stats['errors'], stats['warnings'], 
              stats['infos'], stats['debugs']))
        
        # Store error patterns
        for err_msg in stats.get('error_messages', [])[:10]:
            cursor.execute('''
                INSERT OR IGNORE INTO error_patterns (pattern, first_seen, last_seen, severity, source_files)
                VALUES (?, ?, ?, ?, ?)
            ''', (err_msg[:100], datetime.now().isoformat(), datetime.now().isoformat(), 'ERROR', filename))
            
            cursor.execute('''
                UPDATE error_patterns SET 
                    occurrences = occurrences + 1,
                    last_seen = ?
                WHERE pattern = ?
            ''', (datetime.now().isoformat(), err_msg[:100]))
    
    conn.commit()

# HTTP Handler
class LogAnalyzerHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        if path == '/api/analyze':
            # Run fresh analysis
            analysis = analyze_all_logs()
            self.send_json(analysis)
            
            # Store in DB
            try:
                conn = init_db()
                store_analysis(conn, analysis)
                conn.close()
            except:
                pass
                
        elif path == '/api/stats':
            # Get stored statistics
            conn = init_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT log_file, total_lines, error_count, warning_count, info_count, debug_count, analyzed_at
                FROM log_stats ORDER BY analyzed_at DESC LIMIT 20
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            stats = [{
                'log_file': r[0],
                'total_lines': r[1],
                'errors': r[2],
                'warnings': r[3],
                'infos': r[4],
                'debugs': r[5],
                'analyzed_at': r[6]
            } for r in rows]
            self.send_json({'stats': stats})
            
        elif path == '/api/patterns':
            # Get error patterns
            conn = init_db()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT pattern, occurrences, severity, source_files, last_seen
                FROM error_patterns ORDER BY occurrences DESC LIMIT 20
            ''')
            rows = cursor.fetchall()
            conn.close()
            
            patterns = [{
                'pattern': r[0][:80],
                'occurrences': r[1],
                'severity': r[2],
                'sources': r[3],
                'last_seen': r[4]
            } for r in rows]
            self.send_json({'patterns': patterns})
            
        elif path == '/api/summary':
            # Quick summary
            conn = init_db()
            cursor = conn.cursor()
            
            cursor.execute('SELECT COUNT(*) FROM log_stats')
            total_files = cursor.fetchone()[0]
            
            cursor.execute('SELECT SUM(error_count), SUM(warning_count) FROM log_stats')
            totals = cursor.fetchone()
            
            cursor.execute('SELECT COUNT(*) FROM error_patterns')
            unique_patterns = cursor.fetchone()[0]
            
            conn.close()
            
            self.send_json({
                'total_files_analyzed': total_files,
                'total_errors': totals[0] or 0,
                'total_warnings': totals[1] or 0,
                'unique_patterns': unique_patterns,
                'status': 'healthy' if (totals[0] or 0) < 100 else 'warning'
            })
            
        elif path == '/health':
            self.send_json({'status': 'ok', 'service': 'log-analyzer-enhanced'})
        else:
            self.send_json({'error': 'Not found'}, status=404)
    
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode())
    
    def log_message(self, format, *args):
        pass  # Suppress logging

def run_server(port=18270):
    """Run the log analyzer API server."""
    server = HTTPServer(('0.0.0.0', port), LogAnalyzerHandler)
    print(f"Log Analyzer Enhanced API running on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()