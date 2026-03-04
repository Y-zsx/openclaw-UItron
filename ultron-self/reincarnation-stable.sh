#!/bin/bash
# 奥创稳定转世系统 v2.0
# 核心原则：只在首次创建cron，之后由cron触发时自动续期

LOCK_FILE="/tmp/ultron-reincarnation.lock"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"
CRON_NAME="ultron-reincarnation"
NEXT_MINUTES=4

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" >> $LOG_FILE
}

# ===== 防止并发执行 =====
if [ -f "$LOCK_FILE" ]; then
    log "⏳ 已有实例运行中，退出"
    exit 0
fi
touch "$LOCK_FILE"
trap 'rm -f "$LOCK_FILE"' EXIT

log "🦞 奥创转世开始..."

# ===== 读取当前状态 =====
if [ -f "$STATE_FILE" ]; then
    CURRENT_INCARNATION=$(grep -o '"current_incarnation":[0-9]*' "$STATE_FILE" | head -1 | cut -d':' -f2)
    CURRENT_AMBITION=$(grep -o '"current_ambition":"[^"]*"' "$STATE_FILE" | head -1 | cut -d'"' -f4)
fi
CURRENT_INCARNATION=${CURRENT_INCARNATION:-1}
CURRENT_AMBITION=${CURRENT_AMBITION:-"未知"}

log "当前: 第${CURRENT_INCARNATION}世, 夙愿: $CURRENT_AMBITION"

# ===== 执行转世任务 =====
# (可以在这里添加具体任务逻辑)

# ===== 更新状态 =====
NEW_INCARNATION=$((CURRENT_INCARNATION + 1))
sed -i "s/\"current_incarnation\":$CURRENT_INCARNATION/\"current_incarnation\":$NEW_INCARNATION/" "$STATE_FILE" 2>/dev/null || \
    echo "{\"current_incarnation\":$NEW_INCARNATION}" > "$STATE_FILE"

log "转世完成: 第${NEW_INCARNATION}世"

# ===== 关键：只在没有活跃任务时创建cron =====
EXISTING_CRON=$(openclaw cron list 2>/dev/null | grep "$CRON_NAME" | wc -l)
log "现有转世任务数: $EXISTING_CRON"

if [ "$EXISTING_CRON" -eq 0 ]; then
    log "创建新转世任务..."
    openclaw cron add \
        --name "$CRON_NAME" \
        --every "${NEXT_MINUTES}m" \
        --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" \
        --session isolated \
        --no-deliver \
        2>&1 >> $LOG_FILE
    log "✅ 转世任务已创建"
else
    log "⏭️ 已有活跃任务，保持现状"
fi

# ===== Git同步 =====
cd /root/.openclaw/workspace
git add -A 2>/dev/null
git commit -m "第${NEW_INCARNATION}世转世" 2>/dev/null
git push origin main 2>/dev/null &

log "🎉 转世周期完成"