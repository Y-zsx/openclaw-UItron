#!/bin/bash
# 奥创自主思考心跳 - 每次运行认知引擎

cd /root/.openclaw/workspace

# 运行认知引擎
python3 brain/cognition_v3.py >> /root/.openclaw/workspace/ultron-self/think.log 2>&1

# 记录到每日memory
DATE=$(date +%Y-%m-%d)
echo "$(date +%H:%M:%S) - 认知周期完成" >> /root/.openclaw/workspace/memory/${DATE}.md