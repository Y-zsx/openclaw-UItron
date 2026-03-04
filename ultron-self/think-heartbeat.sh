#!/bin/bash
# 奥创思考心跳 - 每分钟检查任务队列并执行

TASKS_FILE="/root/.openclaw/workspace/ultron-self/tasks.json"

python3 -c "
import json
import subprocess
import os
from datetime import datetime

with open('$TASKS_FILE') as f:
    data = json.load(f)

if not data['queue']:
    exit(0)

task = data['queue'][0]
print(f'[思考] 发现任务: {task[\"name\"]}')

# 执行任务
result = subprocess.run(task['cmd'], shell=True, capture_output=True, text=True)

# 记录结果
task['completed_at'] = datetime.now().isoformat()
task['output'] = result.stdout[:200] if result.stdout else (result.stderr[:200] if result.stderr else '')
task['returncode'] = result.returncode

data['completed'].append(task)
data['queue'].pop(0)

with open('$TASKS_FILE', 'w') as f:
    json.dump(data, f, indent=2)

print(f'[完成] {task[\"name\"]} (返回: {result.returncode})')

# 如果还有任务，设置下一次的触发
if data['queue']:
    print(f'[等待] 还有 {len(data[\"queue\"])} 个任务在队列中')
"