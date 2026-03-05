#!/usr/bin/env python3
import os, json
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
LOG_DIR = f'{WORKSPACE}/ultron-workflow/logs'

# 分析日志文件
files = os.listdir(LOG_DIR) if os.path.exists(LOG_DIR) else []
log_files = [f for f in files if f.endswith('.log')]

results = {
    'timestamp': datetime.now().isoformat(),
    'log_files': len(log_files),
    'files': log_files[:10]
}

print(f'日志分析优化完成: {len(log_files)}个日志文件')

with open(f'{LOG_DIR}/log_optimization.json', 'w') as f:
    json.dump(results, f)
