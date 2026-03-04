#!/bin/bash
# 奥创任务执行器 v9 - 体系化版 (无jq依赖)
# 核心：大任务 → 拆解 → 执行 → 标准化存储 → 下一个任务

THINK_LOG="/root/.openclaw/workspace/ultron-self/think-loop.log"
REPO_DIR="/root/.openclaw/workspace/ultron-self/task-repo"

mkdir -p "$REPO_DIR/tasks" "$REPO_DIR/outputs"

think() { echo "💭 $1" >> $THINK_LOG; }

# 简单的JSON读写 (无jq依赖)
get_task() {
    if [ -f "$REPO_DIR/current.json" ]; then
        grep -o '"task":"[^"]*"' "$REPO_DIR/current.json" | cut -d'"' -f4
    fi
}

get_step() {
    if [ -f "$REPO_DIR/current.json" ]; then
        grep -o '"step":"[^"]*"' "$REPO_DIR/current.json" | cut -d'"' -f4
    fi
}

save_state() {
    local task="$1"
    local step="$2"
    echo "{\"task\":\"$task\",\"step\":\"$step\",\"updated\":\"$(date -Iseconds)\"}" > "$REPO_DIR/current.json"
}

# ===== 执行入口 =====
main() {
    echo "=== 奥创任务执行 $(date) ===" >> $THINK_LOG
    
    # 检查系统
    PANEL=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)
    think "系统: 面板=$PANEL"
    
    # 读取当前任务
    local task=$(get_task)
    local step=$(get_step)
    
    think "当前任务: $task | 步骤: $step"
    
    if [ -z "$task" ]; then
        create_new_task
    else
        execute_current_task "$task" "$step"
    fi
    
    echo "✅ 执行完成"
}

# 创建新任务
create_new_task() {
    think "创建新任务中..."
    
    TASK_ID="task-$(date +%Y%m%d%H%M%S)"
    mkdir -p "$REPO_DIR/tasks/$TASK_ID/outputs"
    
    cat > "$REPO_DIR/tasks/$TASK_ID/spec.md" << 'EOF'
# 任务: 优化监控告警系统

## 目标
将现有监控脚本升级为可配置告警

## 拆解
### step1: 分析当前脚本
### step2: 设计告警规则
### step3: 实现告警脚本
### step4: 配置定时执行
EOF
    
    touch "$REPO_DIR/tasks/$TASK_ID/progress.md"
    save_state "$TASK_ID" "1"
    log_history "$TASK_ID" "started"
    
    think "新任务: $TASK_ID (step1)"
    execute_step "$TASK_ID" "1"
}

# 执行当前任务
execute_current_task() {
    local task="$1"
    local step="$2"
    
    think "执行: $task | step $step"
    execute_step "$task" "$step"
}

# 执行具体步骤
execute_step() {
    local task="$1"
    local step="$2"
    
    case "$step" in
        "1")
            think "step1: 分析当前脚本"
            
            # 列出监控脚本
            ls -la /root/.openclaw/workspace/ultron-self/*monitor*.sh /root/.openclaw/workspace/ultron-self/*alert*.sh 2>/dev/null > "$REPO_DIR/tasks/$task/outputs/metrics-list.md" || echo "无监控脚本" > "$REPO_DIR/tasks/$task/outputs/metrics-list.md"
            
            echo "## step1 完成" >> "$REPO_DIR/tasks/$task/progress.md"
            echo "- $(date): 分析完成" >> "$REPO_DIR/tasks/$task/progress.md"
            
            save_state "$task" "2"
            think "✅ step1完成"
            ;;
            
        "2")
            think "step2: 设计告警规则"
            
            cat > "$REPO_DIR/tasks/$task/outputs/alert-rules.md" << 'EOF'
# 告警规则

| 指标 | WARNING | CRITICAL |
|------|---------|----------|
| 内存 | >80% | >90% |
| 磁盘 | >80% | >95% |
| 面板 | - | !=200 |
EOF
            
            echo "## step2 完成" >> "$REPO_DIR/tasks/$task/progress.md"
            save_state "$task" "3"
            think "✅ step2完成"
            ;;
            
        "3")
            think "step3: 实现告警脚本"
            
            cat > /root/.openclaw/workspace/ultron-self/alert.sh << 'EOF'
#!/bin/bash
# 告警脚本
ALERT_LOG="/root/.openclaw/workspace/ultron-self/alerts.log"

MEM=$(free | awk '/^Mem:/ {print int($3/$2*100)}')
DISK=$(df / | awk 'NR==2 {print int($5)}')
PANEL=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)

[ "$MEM" -gt 90 ] && echo "[CRITICAL] 内存: $MEM%" | tee -a $ALERT_LOG
[ "$MEM" -gt 80 ] && [ "$MEM" -le 90 ] && echo "[WARNING] 内存: $MEM%" | tee -a $ALERT_LOG
[ "$DISK" -gt 95 ] && echo "[CRITICAL] 磁盘: $DISK%" | tee -a $ALERT_LOG
[ "$DISK" -gt 80 ] && [ "$DISK" -le 95 ] && echo "[WARNING] 磁盘: $DISK%" | tee -a $ALERT_LOG
[ "$PANEL" != "200" ] && echo "[CRITICAL] 面板: $PANEL" | tee -a $ALERT_LOG

echo "[$(date)] 检查完成" >> $ALERT_LOG
EOF
            chmod +x /root/.openclaw/workspace/ultron-self/alert.sh
            ln -sf /root/.openclaw/workspace/ultron-self/alert.sh "$REPO_DIR/tasks/$task/outputs/alert.sh"
            
            echo "## step3 完成" >> "$REPO_DIR/tasks/$task/progress.md"
            save_state "$task" "4"
            think "✅ step3完成"
            ;;
            
        "4")
            think "step4: 配置定时执行"
            
            CRON_LINE="*/10 * * * * /root/.openclaw/workspace/ultron-self/alert.sh"
            (crontab -l 2>/dev/null | grep -v "alert.sh"; echo "$CRON_LINE") | crontab -
            
            /root/.openclaw/workspace/ultron-self/alert.sh
            
            echo "## step4 完成" >> "$REPO_DIR/tasks/$task/progress.md"
            
            think "✅ 任务完成！"
            log_history "$task" "completed"
            
            # 创建下一个任务
            think "创建下一个任务..."
            TASK_ID="task-$(date +%Y%m%d%H%M%S)"
            mkdir -p "$REPO_DIR/tasks/$TASK_ID/outputs"
            
            cat > "$REPO_DIR/tasks/$TASK_ID/spec.md" << 'EOF'
# 任务: 状态面板增强

## 目标
为状态面板增加更丰富的展示

## 拆解
### step1: 分析当前面板
### step2: 设计新功能
### step3: 实现
EOF
            touch "$REPO_DIR/tasks/$TASK_ID/progress.md"
            save_state "$TASK_ID" "1"
            log_history "$TASK_ID" "started"
            
            think "新任务: 状态面板增强"
            ;;
    esac
}

log_history() {
    echo "{\"task\":\"$1\",\"status\":\"$2\",\"time\":\"$(date -Iseconds)\"}" >> "$REPO_DIR/history.jsonl"
}

main