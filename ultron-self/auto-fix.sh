#!/bin/bash
# 自动修复脚本 - 第二世: 自动修复机制
# 功能: 检测并修复常见问题

LOG_FILE="/root/.openclaw/workspace/ultron-self/auto-fix.log"
ALERT_LOG="/root/.openclaw/workspace/ultron-self/alerts.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# 检查并修复常见问题
check_and_fix() {
    local fixed=0
    
    # 1. 检查磁盘空间，清理日志
    disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 80 ]; then
        log "⚠️ 磁盘使用率: ${disk_usage}%, 清理日志..."
        # 清理旧日志
        find /root/.openclaw/workspace/ultron-self -name "*.log" -type f -mtime +3 -delete 2>/dev/null
        find /root/.openclaw/workspace/memory -name "*.md" -type f -mtime +7 -delete 2>/dev/null
        log "✅ 磁盘清理完成"
        fixed=$((fixed + 1))
    fi
    
    # 2. 检查 Gateway 状态
    if ! pgrep -x "openclaw" > /dev/null 2>&1; then
        log "⚠️ Gateway 未运行，尝试启动..."
        openclaw gateway start
        sleep 3
        if pgrep -x "openclaw" > /dev/null 2>&1; then
            log "✅ Gateway 已重启"
            fixed=$((fixed + 1))
        else
            log "❌ Gateway 重启失败"
        fi
    fi
    
    # 3. 检查 Chrome 进程
    chrome_count=$(pgrep -f "chrome" | wc -l)
    if [ "$chrome_count" -lt 1 ]; then
        log "⚠️ Chrome headless 未运行，启动..."
        openclaw browser start
        sleep 2
        log "✅ Chrome headless 已启动"
        fixed=$((fixed + 1))
    fi
    
    # 4. 检查内存使用
    mem_usage=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    if [ "$mem_usage" -gt 85 ]; then
        log "⚠️ 内存使用率: ${mem_usage}%, 尝试释放..."
        sync
        echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
        log "✅ 内存释放完成"
        fixed=$((fixed + 1))
    fi
    
    # 5. 检查状态面板
    panel_status=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8889/ 2>/dev/null)
    if [ "$panel_status" != "200" ]; then
        log "⚠️ 状态面板异常，尝试重启..."
        pkill -f "ultron-status.py" 2>/dev/null
        nohup python3 /root/.openclaw/workspace/ultron-status.py > /dev/null 2>&1 &
        sleep 2
        log "✅ 状态面板重启完成"
        fixed=$((fixed + 1))
    fi
    
    return $fixed
}

# 主流程
log "========== 自动修复开始 =========="

check_and_fix
fixes=$?

log "完成 $fixes 项修复"
log "========== 自动修复结束 =========="

# 记录到告警日志
echo "[$(date)] auto-fix: 完成 $fixes 项修复" >> "$ALERT_LOG"

exit 0