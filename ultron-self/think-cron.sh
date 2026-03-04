#!/bin/bash
# 奥创思考系统 v2.1 - 真正联动OpenClaw Cron

# 添加一个"思考任务"，1分钟后执行
add_thought() {
    local TASK_NAME="$1"
    local TASK_CMD="$2"
    
    # 计算1分钟后的时间
    local RUN_AT=$(date -d "+1 minute" -Iseconds)
    
    # 用OpenClaw cron添加一次性任务
    openclaw cron add \
        --name "think:$TASK_NAME" \
        --at "$RUN_AT" \
        --message "$TASK_CMD" \
        --delete-after-run \
        --no-deliver \
        --session isolated \
        2>&1
    
    echo "🧠 已添加思考任务: $TASK_NAME (1分钟后执行)"
}

# 添加延迟任务（自定义分钟）
add_thought_delayed() {
    local TASK_NAME="$1"
    local TASK_CMD="$2"
    local MINUTES="${3:-1}"
    
    local RUN_AT=$(date -d "+$MINUTES minute" -Iseconds)
    
    openclaw cron add \
        --name "think:$TASK_NAME" \
        --at "$RUN_AT" \
        --message "$TASK_CMD" \
        --delete-after-run \
        --no-deliver \
        --session isolated \
        2>&1
    
    echo "🧠 已添加思考任务: $TASK_NAME (${MINUTES}分钟后执行)"
}

# 列出思考任务
list_thoughts() {
    openclaw cron list 2>&1 | grep "think:" || echo "无等待中的思考任务"
}

# 立即执行一个思考（不经过cron）
think_now() {
    local TASK_NAME="$1"
    local TASK_CMD="$2"
    
    echo "🧠 立即思考: $TASK_NAME"
    eval "$TASK_CMD"
    local RESULT=$?
    echo "✅ 完成 (返回: $RESULT)"
}

case "$1" in
    add)
        add_thought "$2" "$3"
        ;;
    add-delay)
        add_thought_delayed "$2" "$3" "$4"
        ;;
    list)
        list_thoughts
        ;;
    now)
        think_now "$2" "$3"
        ;;
    *)
        echo "用法:"
        echo "  think-cron.sh add <任务名> <命令>        # 1分钟后执行"
        echo "  think-cron.sh add-delay <任务名> <命令> <分钟>  # 自定义延迟"
        echo "  think-cron.sh now <任务名> <命令>       # 立即执行"
        echo "  think-cron.sh list                      # 列出等待任务"
        ;;
esac