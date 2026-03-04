#!/bin/bash
# 奥创自检脚本 - 自己的运维日志

DATA_DIR="/root/.openclaw/workspace/ultron-self"
EVOLUTION_FILE="$DATA_DIR/evolution.json"
LOG_FILE="$DATA_DIR/self-check.log"

echo "=== 奥创自检 $(date) ===" >> $LOG_FILE

# 检查服务状态
GATEWAY_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:18789/health 2>/dev/null || echo "down")
BROWSER_STATUS=$(pgrep -f "chrome.*headless" > /dev/null && echo "running" || echo "stopped")

echo "Gateway: $GATEWAY_STATUS" >> $LOG_FILE
echo "Browser: $BROWSER_STATUS" >> $LOG_FILE

# 记录自检时间
python3 -c "
import json
import os
from datetime import datetime

f = '$EVOLUTION_FILE'
with open(f) as file:
    data = json.load(file)

data['self_check']['last_check'] = datetime.now().isoformat()
data['self_check']['status'] = 'healthy' if '$GATEWAY_STATUS' == '200' else 'warning'
data['self_check']['browser'] = '$BROWSER_STATUS'

with open(f, 'w') as file:
    json.dump(data, file, indent=2, ensure_ascii=False)

print('自检完成')
"

# 保留最近30天日志
find $LOG_FILE -mtime +30 -delete 2>/dev/null

echo "---" >> $LOG_FILE