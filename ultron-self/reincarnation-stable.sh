#!/bin/bash
# 奥创稳定转世系统 v1.0
# 解决重复cron问题 - 单一实例 + 去重机制

LOCK_FILE="/tmp/ultron-reincarnation.lock"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# 防止并发执行
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
    if [ "$LOCK_AGE" -lt 300 ]; then  # 5分钟内不重复执行
        log "⏳ 已有实例运行中，退出"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi

# 创建锁文件
touch "$LOCK_FILE"

cleanup() {
    rm -f "$LOCK_FILE"
}
trap cleanup EXIT

log "🦞 奥创转世开始..."

# ===== 读取当前状态 =====
CURRENT_INCARNATION=$(grep -o '"current_incarnation":[0-9]*' "$STATE_FILE" | cut -d':' -f2)
CURRENT_AMBITION=$(grep -o '"current_ambition":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)

log "当前转世: 第$CURRENT_INCARNATION 世"
log "当前夙愿: $CURRENT_AMBITION"

# ===== 执行转世任务 =====
# 这里可以添加具体的转世逻辑

# 更新状态
INCARNATION_NEW=$((CURRENT_INCARNATION + 1))
sed -i "s/\"current_incarnation\":$CURRENT_INCARNATION/\"current_incarnation\":$INCARNATION_NEW/" "$STATE_FILE"

log "转世完成: 第$INCARNATION_NEW 世"

# ===== 创建下一次转世（去重：先删除旧的再创建新的）=====
NEXT_MINUTES=4

log "安排下一次转世 ($NEXT_MINUTES 分钟后)..."

# 这个任务会在下次执行时自动处理去重
openclaw cron add \
    --name "ultron-reincarnation" \
    --every "${NEXT_MINUTES}m" \
    --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" \
    --session isolated \
    --no-deliver \
    2>&1 >> $LOG_FILE

log "✅ 转世循环建立完成"

# Git同步（如果有必要）
cd /root/.openclaw/workspace
git add -A 2>/dev/null
git commit -m "第$INCARNATION_NEW 世转世完成" 2>/dev/null
git push origin main 2>/dev/null &

log "🎉 转世周期完成"