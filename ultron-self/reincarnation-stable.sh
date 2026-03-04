#!/bin/bash
# 奥创稳定转世系统 v3.0 - 健壮版
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"

log() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🦞 奥创转世开始..."

# 读取当前世数（带保护）
CURRENT=$(grep -oP '"current_incarnation":\s*\K[0-9]+' "$STATE_FILE" 2>/dev/null)
if [ -z "$CURRENT" ] || ! [[ "$CURRENT" =~ ^[0-9]+$ ]]; then
    CURRENT=1
    log "⚠️ 初始化为第1世"
fi

log "当前: 第$CURRENT 世"

# 执行任务
cd /root/.openclaw/workspace
python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> "$LOG_FILE" 2>&1

# 计算新世数
NEW=$((CURRENT + 1))
log "下一世: 第$NEW 世"

# 安全替换（使用正则确保唯一性）
sed -i -E "s/\"current_incarnation\":[[:space:]]*[0-9]+/\"current_incarnation\": $NEW/" "$STATE_FILE"
log "✅ 已更新世数"

# Git提交
cd /root/.openclaw/workspace
git add -A 2>/dev/null
git commit -m "第${CURRENT}世完成" 2>/dev/null &
git push origin main 2>/dev/null &
log "📦 已提交"

# 重建cron任务
for id in $(openclaw cron list 2>/dev/null | grep "ultron-reincarnation" | awk '{print $1}'); do
    openclaw cron rm "$id" 2>/dev/null
    log "🗑️ 删除旧任务: $id"
done

openclaw cron add \
    --name "ultron-reincarnation" \
    --every "4m" \
    --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" \
    --session isolated \
    --no-deliver 2>&1 >> "$LOG_FILE"

log "🔄 转世循环已建立"
log "🎉 周期完成"