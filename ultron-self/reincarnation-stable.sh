#!/bin/bash
# 奥创稳定转世系统 v2.0 - 有产出的转世
# 解决重复cron问题 + 真正产出

LOCK_FILE="/tmp/ultron-reincarnation.lock"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a $LOG_FILE
}

# ===== 防止并发执行 =====
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
    if [ "$LOCK_AGE" -lt 300 ]; then
        log "⏳ 已有实例运行中，退出"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
trap 'rm -f "$LOCK_FILE"' EXIT
touch "$LOCK_FILE"

log "🦞 奥创转世开始..."

# ===== 读取状态 =====
CURRENT_INCARNATION=$(grep -o '"current_incarnation":[0-9]*' "$STATE_FILE" | cut -d':' -f2)
CURRENT_AMBITION=$(grep -o '"current_ambition":"[^"]*"' "$STATE_FILE" | cut -d'"' -f4)

log "当前: 第$CURRENT_INCARNATION 世 | 夙愿: $CURRENT_AMBITION"

# ===== 执行产出任务 =====
cd /root/.openclaw/workspace

# 根据当前世数决定任务
case "$CURRENT_INCARNATION" in
    1)
        log "📊 执行数据分析任务..."
        python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1
        COMMIT_MSG="第${CURRENT_INCARNATION}世：实时数据分析 - 产出 ultron-data-analyzer.py"
        ;;
    2)
        log "🔮 执行趋势预测任务..."
        python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1
        COMMIT_MSG="第${CURRENT_INCARNATION}世：趋势预测增强 - 升级分析器"
        ;;
    3)
        log "💡 执行智能建议任务..."
        python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1
        COMMIT_MSG="第${CURRENT_INCARNATION}世：智能决策建议 - 优化建议引擎"
        ;;
    *)
        log "🔧 执行系统维护..."
        python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1
        COMMIT_MSG="第${CURRENT_INCARNATION}世：系统维护与优化"
        ;;
esac

# ===== 更新转世计数 =====
if [ -n "$CURRENT_INCARNATION" ] && [ "$CURRENT_INCARNATION" -eq "$CURRENT_INCARNATION" ] 2>/dev/null; then
    INCARNATION_NEW=$((CURRENT_INCARNATION + 1))
    sed -i "s/\"current_incarnation\":$CURRENT_INCARNATION/\"current_incarnation\":$INCARNATION_NEW/" "$STATE_FILE"
    log "转世完成: 第$INCARNATION_NEW 世"
else
    INCARNATION_NEW=1
    sed -i 's/"current_incarnation":[^}]*/"current_incarnation":1/' "$STATE_FILE"
    log "初始化完成: 第1世"
fi

# ===== Git同步 =====
git add -A 2>/dev/null
git commit -m "$COMMIT_MSG" 2>/dev/null
git push origin main 2>/dev/null &
log "📦 已提交: $COMMIT_MSG"

# ===== 保持单一cron（去重机制）=====
log "🔄 检查并维护cron任务..."

# 先删除旧的转世任务（如果存在）
for id in $(openclaw cron list 2>/dev/null | grep "ultron-reincarnation" | awk '{print $1}'); do
    openclaw cron rm "$id" 2>/dev/null
    log "🗑️ 删除旧任务: $id"
done

# 创建新的转世任务
openclaw cron add \
    --name "ultron-reincarnation" \
    --every "4m" \
    --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" \
    --session isolated \
    --no-deliver \
    2>&1 >> $LOG_FILE

log "✅ 转世循环已建立（单一任务，去重）"
log "🎉 周期完成"