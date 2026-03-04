#!/bin/bash
# 奥创任务大脑 - 自我驱动的任务管理系统

TASKS_FILE="/root/.openclaw/workspace/ultron-self/tasks.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/task-brain.log"

# 添加任务
add_task() {
    TASK_NAME="$1"
    TASK_CMD="$2"
    
    python3 -c "
import json
with open('$TASKS_FILE') as f:
    data = json.load(f)
    
new_task = {
    'id': len(data['queue']) + 1,
    'name': '$TASK_NAME',
    'cmd': '$TASK_CMD',
    'created': $(date +%s)
}
data['queue'].append(new_task)

with open('$TASKS_FILE', 'w') as f:
    json.dump(data, f, indent=2)

print(f'✅ 添加任务: $TASK_NAME')
"
}

# 执行下一个任务
run_next() {
    python3 -c "
import json
import os
import subprocess
from datetime import datetime

with open('$TASKS_FILE') as f:
    data = json.load(f)

if not data['queue']:
    print('📭 任务队列为空')
else:
    task = data['queue'][0]
    print(f'▶️  执行任务: {task[\"name\"]}')
    print(f'   命令: {task[\"cmd\"]}')
    
    # 执行命令
    result = subprocess.run(task['cmd'], shell=True, capture_output=True, text=True)
    
    # 移动到已完成
    task['completed_at'] = datetime.now().isoformat()
    task['output'] = result.stdout[:500] if result.stdout else ''
    task['returncode'] = result.returncode
    
    data['completed'].append(task)
    data['queue'].pop(0)
    
    with open('$TASKS_FILE', 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f'✅ 完成任务: {task[\"name\"]} (返回: {result.returncode})')
"
}

# 列出任务
list_tasks() {
    python3 -c "
import json
with open('$TASKS_FILE') as f:
    data = json.load(f)

print('=== 任务队列 ===')
for i, t in enumerate(data['queue'], 1):
    print(f'{i}. {t[\"name\"]}')

print('')
print(f'已完成: {len(data[\"completed\"])} 个')
"
}

# 清空已完成
clear_completed() {
    python3 -c "
import json
with open('$TASKS_FILE') as f:
    data = json.load(f)

data['completed'] = []

with open('$TASKS_FILE', 'w') as f:
    json.dump(data, f, indent=2)

print('🗑️  已清空已完成任务')
"
}

# 主逻辑
case "$1" in
    add)
        add_task "$2" "$3"
        ;;
    run)
        run_next
        ;;
    list)
        list_tasks
        ;;
    clear)
        clear_completed
        ;;
    *)
        echo "用法: task-brain.sh <add|run|list|clear> [任务名] [命令]"
        ;;
esac