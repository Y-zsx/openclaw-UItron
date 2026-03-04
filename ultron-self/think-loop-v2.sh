#!/bin/bash
# 奥创思考循环 v2 - 简洁版
# 核心：思考 → 执行 → 决定下一轮 → 清理

THINK_LOG="/root/.openclaw/workspace/ultron-self/think-loop.log"
CONTEXT_FILE="/root/.openclaw/workspace/ultron-self/think-context.json"

echo "=== 奥创思考 $(date) ===" >> $THINK_LOG

# 1. 读取上一轮的上下文
if [ -f "$CONTEXT_FILE" ]; then
    PREV_CONTEXT=$(cat $CONTEXT_FILE)
    echo "上一轮上下文: $PREV_CONTEXT" >> $THINK_LOG
else
    PREV_CONTEXT="无"
fi

# 2. 执行思考（基于上一轮上下文）
case "$PREV_CONTEXT" in
    *"学习"*)
        echo "继续学习新技能..."
        NEW_CONTEXT="检查系统状态"
        ;;
    *"检查"*)
        echo "检查完成，评估是否需要新任务"
        NEW_CONTEXT="决定下一步"
        ;;
    *"决定"*)
        echo "决定下一步行动"
        NEW_CONTEXT="学习"  # 回到学习循环
        ;;
    *)
        NEW_CONTEXT="检查系统状态"
        ;;
esac

# 3. 决定下一轮做什么
echo "本轮决定: $NEW_CONTEXT"
echo $NEW_CONTEXT > $CONTEXT_FILE

# 4. 清理旧的重复任务（保持简洁）
CURRENT_TASKS=$(openclaw cron list 2>&1 | grep -c "ultron-think" || echo 0)
if [ $CURRENT_TASKS -gt 2 ]; then
    echo "⚠️ 任务过多($CURRENT_TASKS)，清理中..."
    openclaw cron list 2>&1 | grep "ultron-think" | awk '{print $1}' | tail -n +3 | while read id; do
        openclaw cron delete $id 2>/dev/null
    done
fi

# 5. 本轮结束，记录
echo "🧠 思考完成，下一轮: $NEW_CONTEXT" >> $THINK_LOG

echo "思考完成: $NEW_CONTEXT"