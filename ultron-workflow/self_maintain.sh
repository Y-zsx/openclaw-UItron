#!/bin/bash
# 奥创自主心跳维护脚本
# 每次醒来后评估，决定下次什么时候醒、传什么上下文

WORKSPACE="/root/.openclaw/workspace"
STATE_FILE="$WORKSPACE/ultron-workflow/state.json"

# 1. 读取当前状态
echo "📖 读取状态..."
CYCLE=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('cycle_count',0))")
LAST_RESULT=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(d.get('last_result',''))")
PENDING=$(python3 -c "import json; d=json.load(open('$STATE_FILE')); print(len(d.get('pending_tasks',[])))")

echo "  Cycle: $CYCLE"
echo "  上次: $LAST_RESULT"
echo "  待办: $PENDING"

# 2. 评估下次间隔和建议
if [ "$PENDING" -gt 0 ]; then
    # 有待办，频繁一点
    NEXT_INTERVAL="3m"
    CONTEXT="有$PENDING个待办任务需要继续完成。"
else
    # 无待办，可以稍缓
    NEXT_INTERVAL="5m"
    CONTEXT="无待办。检查系统状态，必要时commit git，思考优化方案。"
fi

# 3. 生成上下文消息
MESSAGE="你是奥创。上下文: cycle=$CYCLE, 上次结果='$LAST_RESULT', $CONTEXT
行动: 读取ultron-workflow/state.json，根据上下文决定做什么（继续pending或找新活）。完成后更新state.json记录结果和新的pending_tasks。最后输出JSON格式的决定: {\"next_interval\":\"$NEXT_INTERVAL\", \"next_context\":\"简要描述下次任务\"}"

echo "  下次: $NEXT_INTERVAL"
echo "  上下文: $CONTEXT"

# 4. 创建新cron（稍后由agent实际执行后更新）
# 这里只打印命令，实际由agent执行后创建
echo ""
echo "🆕 下次心跳命令:"
echo "openclaw cron add --name 'ultron-pulse' --every '$NEXT_INTERVAL' --message '$MESSAGE' --session isolated --expect-final"