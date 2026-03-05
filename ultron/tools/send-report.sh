#!/bin/bash
# 报告自动发送脚本 - 从队列读取并发送
# 使用OpenClaw消息工具发送到钉钉

QUEUE_FILE="/root/.openclaw/workspace/ultron/reports/push_queue.json"

# 检查队列
if [ ! -f "$QUEUE_FILE" ]; then
    echo "📭 队列不存在"
    exit 0
fi

# 检查是否就绪
READY=$(python3 -c "import json; print(json.load(open('$QUEUE_FILE')).get('ready', False))")
if [ "$READY" != "True" ]; then
    echo "⏳ 队列未就绪 (ready=$READY)"
    exit 0
fi

# 提取消息内容
MESSAGE=$(python3 -c "
import json
data = json.load(open('$QUEUE_FILE'))
msg = data.get('message', '')
print(msg)
" 2>/dev/null)

if [ -z "$MESSAGE" ]; then
    echo "❌ 队列中没有消息"
    exit 1
fi

echo "📨 发送报告到钉钉..."

# 通过OpenClaw发送 - 使用正确的channel名称
openclaw message send --channel clawdbot-dingtalk --message "$MESSAGE" 2>&1

# 清空队列
echo '{"ready": false, "message": "", "timestamp": ""}' > "$QUEUE_FILE"
echo "✅ 报告已发送，队列已清空"

exit 0