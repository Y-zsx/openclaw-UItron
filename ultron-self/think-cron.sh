#!/bin/bash
# 奥创思考系统 v2 - 基于OpenClaw Cron原生能力

# 添加一个"思考任务"，1分钟后执行
add_thought() {
    local TASK_NAME="$1"
    local TASK_CMD="$2"
    
    # 用OpenClaw cron添加一次性任务
    openclaw cron add \
        --name "think:$TASK_NAME" \
        --at "+1m" \
        --message "$TASK_CMD" \
        --delete-after-run \
        --no-deliver \
        --expect-final \
        --timeout-seconds 60 \
        2>&1
    
    echo "🧠 已添加思考任务: $TASK_NAME (1分钟后执行)"
}

# 列出思考任务
list_thoughts() {
    openclaw cron list 2>&1 | grep "think:" || echo "无等待中的思考任务"
}

# 立即执行一个思考（测试用）
think_now() {
    local TASK_NAME="$1"
    local TASK_CMD="$2"
    
    echo "🧠 立即思考: $TASK_NAME"
    eval "$TASK_CMD"
    local RESULT=$?
    echo "✅ 完成 (返回: $RESULT)"
}

# 连续思考模式 - 多个任务依次执行
chain_thoughts() {
    shift
    local TASKS=("$@")
    
    for task in "${TASKS[@]}"; do
        echo "🔗 链式思考: $task"
    done
}

case "$1" in
    add)
        add_thought "$2" "$3"
        ;;
    list)
        list_thoughts
        ;;
    now)
        think_now "$2" "$3"
        ;;
    chain)
        shift
        chain_thoughts "$@"
        ;;
    *)
        echo "用法:"
        echo "  think.sh add <任务名> <命令>     # 添加1分钟后执行"
        echo "  think.sh now <任务名> <命令>     # 立即执行"
        echo "  think.sh list                    # 列出等待任务"
        echo "  think.sh chain <任务1> <任务2>  # 链式执行"
        ;;
esac