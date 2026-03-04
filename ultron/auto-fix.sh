#!/bin/bash
# 奥创自动修复脚本 - 第二世：自动修复机制
# 功能：自动检测并修复常见问题

LOG_FILE="/root/.openclaw/workspace/ultron/logs/auto-fix-$(date '+%Y-%m-%d').log"
mkdir -p "$(dirname $LOG_FILE)"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "🦞 奥创自动修复开始"

fixed=0
issues=0

# 1. 检查并修复磁盘空间
check_disk() {
    local disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
    if [ "$disk_usage" -gt 85 ]; then
        log "⚠️ 磁盘使用率: ${disk_usage}% - 尝试清理..."
        
        # 清理日志
        find /var/log -name "*.log" -mtime +7 -delete 2>/dev/null
        find /root/.openclaw/logs -name "*.log" -mtime +3 -delete 2>/dev/null
        
        # 清理tmp
        find /tmp -type f -mtime +1 -delete 2>/dev/null
        
        # 清理npm缓存
        npm cache clean --force 2>/dev/null
        
        # 清理Docker (如果存在)
        docker system prune -f 2>/dev/null
        
        new_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
        log "✅ 磁盘清理完成: ${disk_usage}% -> ${new_usage}%"
        ((fixed++))
    else
        log "✅ 磁盘使用率正常: ${disk_usage}%"
    fi
}

# 2. 检查并修复内存
check_memory() {
    local mem_percent=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
    if [ "$mem_percent" -gt 85 ]; then
        log "⚠️ 内存使用: ${mem_percent}% - 尝试清理..."
        
        # 清理缓存
        sync && echo 3 > /proc/sys/vm/drop_caches 2>/dev/null
        
        # 终止占用高的无用进程
        for pid in $(ps aux --sort=-%mem | awk 'NR>1 {if($4>10) print $2}' | head -3); do
            proc_name=$(ps -p $pid -o comm= 2>/dev/null)
            if [[ ! "$proc_name" =~ "openclaw"|"node"|"gateway" ]]; then
                kill -15 $pid 2>/dev/null
                log "  终止高内存进程: $proc_name (PID: $pid)"
            fi
        done
        
        new_mem=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
        log "✅ 内存清理完成: ${mem_percent}% -> ${new_mem}%"
        ((fixed++))
    else
        log "✅ 内存使用正常: ${mem_percent}%"
    fi
}

# 3. 检查并修复服务异常
check_services() {
    # OpenClaw Gateway
    if ! pgrep -f "openclaw.*gateway" > /dev/null; then
        log "⚠️ OpenClaw Gateway 未运行 - 尝试启动..."
        openclaw gateway start 2>/dev/null
        if pgrep -f "openclaw.*gateway" > /dev/null; then
            log "✅ OpenClaw Gateway 已重启"
            ((fixed++))
        else
            log "❌ OpenClaw Gateway 重启失败"
            ((issues++))
        fi
    else
        log "✅ OpenClaw Gateway 运行正常"
    fi
    
    # Nginx
    if ! pgrep nginx > /dev/null; then
        log "⚠️ Nginx 未运行 - 尝试启动..."
        systemctl start nginx 2>/dev/null || nginx 2>/dev/null
        if pgrep nginx > /dev/null; then
            log "✅ Nginx 已重启"
            ((fixed++))
        else
            log "⚠️ Nginx 重启失败 (可能不需要)"
        fi
    else
        log "✅ Nginx 运行正常"
    fi
}

# 4. 检查端口占用
check_ports() {
    # 检查18789端口
    if ! ss -tlnp | grep -q ":18789 "; then
        log "⚠️ Gateway端口18789未监听 - 可能是启动问题"
        ((issues++))
    else
        log "✅ Gateway端口正常"
    fi
}

# 5. 检查并清理僵死进程
check_zombies() {
    local zombies=$(ps aux | awk '$8 ~ /Z/ {print $2}' | wc -l)
    if [ "$zombies" -gt 0 ]; then
        log "⚠️ 发现 $zombies 个僵死进程"
        # 僵死进程无法直接 kill，清理父进程
        for pid in $(ps aux | awk '$8 ~ /Z/ {print $2}'); do
            ppid=$(ps -o ppid= -p $pid 2>/dev/null)
            if [ -n "$ppid" ] && [ "$ppid" -gt 1 ]; then
                kill -9 $ppid 2>/dev/null
                log "  清理僵死进程父进程: PID $ppid"
            fi
        done
        ((fixed++))
    else
        log "✅ 无僵死进程"
    fi
}

# 6. 检查日志文件大小
check_logs() {
    local log_dir="/root/.openclaw/workspace/ultron/logs"
    if [ -d "$log_dir" ]; then
        local total_size=$(du -sh "$log_dir" 2>/dev/null | cut -f1)
        log "📁 日志目录大小: $total_size"
        
        # 如果日志太大，清理旧的
        if du -sb "$log_dir" | cut -f1 | grep -qE '[0-9]{8,}'; then
            find "$log_dir" -name "*.log" -mtime +7 -delete 2>/dev/null
            find "$log_dir" -name "*.json" -mtime +14 -delete 2>/dev/null
            log "✅ 旧日志已清理"
        fi
    fi
}

# 执行所有检查
log "========== 开始系统检查 =========="
check_disk
check_memory
check_services
check_ports
check_zombies
check_logs
log "========== 检查完成 =========="

log "🦞 自动修复完成: 修复 $fixed 项, 问题 $issues 项"

# 输出总结
echo ""
echo "========================================"
echo "🦞 奥创自动修复报告"
echo "========================================"
echo "修复项: $fixed"
echo "待处理: $issues"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S')"
echo "========================================"

exit 0