#!/usr/bin/env python3
"""
定时指标收集调度器 V2
集成到Cron定时任务中，支持：
- 定时指标收集
- 历史数据存储
- 阈值告警触发
- 与Dashboard集成
"""
import os, sys, json, subprocess, sqlite3, time
from datetime import datetime, timedelta
from pathlib import Path

WORKSPACE = '/root/.openclaw/workspace'
LOG_FILE = f'{WORKSPACE}/ultron-workflow/logs/metrics_scheduler.log'
METRICS_DB = f'{WORKSPACE}/ultron-workflow/logs/metrics_history.db'
METRICS_FILE = f'{WORKSPACE}/ultron-workflow/logs/latest_metrics.json'
ALERT_API_URL = 'http://localhost:18170'

def log(msg):
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    with open(LOG_FILE, 'a') as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)

def init_db():
    """初始化指标数据库"""
    conn = sqlite3.connect(METRICS_DB)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS metrics_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        load_1m REAL,
        load_5m REAL,
        load_15m REAL,
        memory_percent REAL,
        disk_percent REAL,
        gateway_processes INTEGER,
        services_healthy INTEGER,
        services_total INTEGER,
        network_sent_mb REAL,
        network_recv_mb REAL
    )''')
    conn.commit()
    conn.close()

def get_system_metrics():
    """获取系统指标"""
    metrics = {
        'timestamp': datetime.now().isoformat(),
        'load': {},
        'memory': {},
        'disk': {},
        'services': {},
        'network': {}
    }
    
    # 1. 系统负载
    try:
        with open('/proc/loadavg') as f:
            load = f.read().split()[:3]
            metrics['load'] = {
                '1m': float(load[0]),
                '5m': float(load[1]),
                '15m': float(load[2])
            }
    except:
        pass
    
    # 2. 内存
    try:
        with open('/proc/meminfo') as f:
            mem = {}
            for line in f:
                if 'MemTotal' in line:
                    mem['total'] = int(line.split()[1]) // 1024
                elif 'MemAvailable' in line:
                    mem['available'] = int(line.split()[1]) // 1024
            if mem:
                mem['used'] = mem['total'] - mem['available']
                mem['percent'] = round(mem['used'] / mem['total'] * 100, 1)
                metrics['memory'] = mem
    except:
        pass
    
    # 3. 磁盘
    try:
        result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True, timeout=5)
        parts = result.stdout.split('\n')[-1].split()
        metrics['disk'] = {
            'total': parts[1],
            'used': parts[2],
            'percent': parts[4].replace('%', '')
        }
    except:
        pass
    
    # 4. Gateway进程
    try:
        result = subprocess.run(['pgrep', '-f', 'openclaw'], capture_output=True, timeout=5)
        metrics['gateway_processes'] = len(result.stdout.split()) if result.stdout else 0
    except:
        pass
    
    # 5. 核心服务检查
    services = {
        'gateway': 'http://localhost:18789/',
        'status_panel': 'http://localhost:8889/',
        'health_api': 'http://localhost:8890/health',
        'dashboard': 'http://localhost:18103/',
        'metrics_api': 'http://localhost:8888/metrics'
    }
    
    healthy_services = []
    for name, url in services.items():
        try:
            result = subprocess.run(
                ['curl', '-s', '-o', '/dev/null', '-w', '%{http_code}', '-m', '3', url],
                capture_output=True, timeout=5, text=True
            )
            code = result.stdout.strip()
            if code == '200':
                healthy_services.append(name)
                metrics['services'][name] = 'healthy'
            else:
                metrics['services'][name] = f'unhealthy({code})'
        except Exception as e:
            metrics['services'][name] = f'error({e})'
    
    metrics['healthy_count'] = len(healthy_services)
    metrics['total_services'] = len(services)
    
    return metrics

def save_to_db(metrics):
    """保存指标到数据库"""
    try:
        conn = sqlite3.connect(METRICS_DB)
        c = conn.cursor()
        c.execute('''INSERT INTO metrics_history 
            (timestamp, load_1m, load_5m, load_15m, memory_percent, disk_percent, 
             gateway_processes, services_healthy, services_total)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (metrics['timestamp'],
             metrics['load'].get('1m'),
             metrics['load'].get('5m'),
             metrics['load'].get('15m'),
             metrics['memory'].get('percent'),
             metrics['disk'].get('percent'),
             metrics.get('gateway_processes'),
             metrics.get('healthy_count'),
             metrics.get('total_services')))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        log(f'数据库保存失败: {e}')
        return False

def check_thresholds_and_alert(metrics):
    """检查阈值并发送告警"""
    alerts = []
    
    # CPU负载阈值
    load_1m = metrics['load'].get('1m', 0)
    if load_1m > 5.0:
        alerts.append({
            'rule_id': 'high_load',
            'level': 'warning' if load_1m < 8.0 else 'error',
            'message': f'系统负载过高: {load_1m}',
            'value': load_1m,
            'threshold': 5.0
        })
    
    # 内存阈值
    mem_percent = metrics['memory'].get('percent', 0)
    if mem_percent > 80:
        alerts.append({
            'rule_id': 'high_memory',
            'level': 'warning' if mem_percent < 90 else 'error',
            'message': f'内存使用率过高: {mem_percent}%',
            'value': mem_percent,
            'threshold': 80
        })
    
    # 服务健康检查
    if metrics.get('healthy_count', 0) < metrics.get('total_services', 0):
        alerts.append({
            'rule_id': 'service_down',
            'level': 'error',
            'message': f'服务健康检查失败: {metrics.get("healthy_count")}/{metrics.get("total_services")}',
            'value': metrics.get('healthy_count'),
            'threshold': metrics.get('total_services')
        })
    
    # 发送告警到API
    for alert in alerts:
        try:
            import requests
            alert_data = {
                'rule_id': f'metrics_{alert["rule_id"]}',
                'rule_name': f'指标监控: {alert["rule_id"]}',
                'service_name': 'metrics-monitor',
                'level': alert['level'],
                'message': alert['message'],
                'value': alert['value'],
                'threshold': alert['threshold'],
                'labels': {'check_type': 'metrics'},
                'annotations': {'checked_at': metrics['timestamp']}
            }
            resp = requests.post(f'{ALERT_API_URL}/alerts', json=alert_data, timeout=5)
            if resp.status_code == 200:
                log(f'已发送告警: {alert["rule_id"]}')
        except Exception as e:
            log(f'告警发送失败: {e}')
    
    return alerts

def save_latest_metrics(metrics):
    """保存最新指标到JSON文件供Dashboard使用"""
    with open(METRICS_FILE, 'w') as f:
        json.dump(metrics, f, indent=2)

def cleanup_old_records():
    """清理7天前的历史数据"""
    try:
        conn = sqlite3.connect(METRICS_DB)
        c = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=7)).isoformat()
        c.execute('DELETE FROM metrics_history WHERE timestamp < ?', (cutoff,))
        deleted = c.rowcount
        conn.commit()
        conn.close()
        if deleted > 0:
            log(f'已清理{deleted}条历史记录')
    except Exception as e:
        log(f'清理失败: {e}')

def collect_metrics():
    """收集并处理指标"""
    log('开始收集指标...')
    
    # 初始化数据库
    init_db()
    
    # 获取指标
    metrics = get_system_metrics()
    
    # 保存到数据库
    if save_to_db(metrics):
        log('指标已保存到数据库')
    
    # 保存最新指标
    save_latest_metrics(metrics)
    
    # 检查阈值并告警
    alerts = check_thresholds_and_alert(metrics)
    
    # 清理旧数据
    cleanup_old_records()
    
    # 记录日志
    load = metrics['load'].get('1m', 0)
    mem = metrics['memory'].get('percent', 0)
    services = metrics.get('healthy_count', 0)
    total = metrics.get('total_services', 0)
    
    log(f'指标收集完成: 负载{load}, 内存{mem}%, 服务{services}/{total}')
    
    return metrics

if __name__ == '__main__':
    collect_metrics()