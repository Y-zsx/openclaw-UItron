#!/bin/bash
# 奥创健康检查脚本 - 详细系统监控

echo "🦞 奥创健康检查 $(date '+%Y-%m-%d %H:%M:%S')"
echo "============================================"

# 1. 系统基础信息
echo -e "\n📊 系统状态:"
echo "  运行时间: $(uptime -p)"
echo "  负载: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
echo "  进程数: $(ps aux | wc -l)"

# 2. 内存
echo -e "\n💾 内存:"
free -h | grep -E "Mem|Swap" | while read line; do
    echo "  $line"
done

# 3. 磁盘
echo -e "\n💿 磁盘:"
df -h | grep -E "^/dev|Filesystem" | head -5

# 4. 网络连接
echo -e "\n🌐 网络:"
echo "  开放端口: $(ss -tuln | wc -l) 条"
echo "  活跃连接: $(ss -tan | wc -l) 条"

# 5. 关键服务状态
echo -e "\n🔧 服务状态:"
services=("openclaw" "nginx" "chromium" "cron")
for svc in "${services[@]}"; do
    if pgrep -x "$svc" > /dev/null 2>&1 || pgrep -f "$svc" > /dev/null 2>&1; then
        echo "  ✅ $svc: 运行中"
    else
        echo "  ❌ $svc: 未运行"
    fi
done

# 6. OpenClaw状态
echo -e "\n🤖 OpenClaw:"
if pgrep -f "openclaw" > /dev/null; then
    echo "  Gateway: ✅ 运行中"
    echo "  端口: $(ss -tlnp | grep 18789 | awk '{print $4}' || echo '18789')"
else
    echo "  Gateway: ❌ 未运行"
fi

# 7. 今日统计
echo -e "\n📈 今日统计:"
log_dir="/root/.openclaw/workspace/ultron/logs"
if [ -d "$log_dir" ]; then
    echo "  日志文件: $(find $log_dir -type f 2>/dev/null | wc -l) 个"
    echo "  最新报告: $(ls -t $log_dir/*.json 2>/dev/null | head -1 | xargs basename 2>/dev/null || echo '无')"
fi

# 8. Git提交统计
cd /root/.openclaw/workspace
if [ -d ".git" ]; then
    commits=$(git log --since=" midnight" --oneline | wc -l)
    echo "  今日Git提交: $commits 次"
fi

# 9. 检查需要关注的问题
echo -e "\n⚠️ 警告检查:"
warnings=0

# 检查磁盘空间
disk_usage=$(df / | tail -1 | awk '{print $5}' | sed 's/%//')
if [ "$disk_usage" -gt 80 ]; then
    echo "  ⚠️ 磁盘使用率: ${disk_usage}% (建议清理)"
    ((warnings++))
else
    echo "  ✅ 磁盘使用率: ${disk_usage}% (正常)"
fi

# 检查内存
mem_percent=$(free | grep Mem | awk '{printf "%.0f", $3/$2 * 100}')
if [ "$mem_percent" -gt 80 ]; then
    echo "  ⚠️ 内存使用: ${mem_percent}% (偏高)"
    ((warnings++))
else
    echo "  ✅ 内存使用: ${mem_percent}% (正常)"
fi

# 检查进程数
proc_count=$(ps aux | wc -l)
if [ "$proc_count" -gt 300 ]; then
    echo "  ⚠️ 进程数: $proc_count (偏多)"
    ((warnings++))
else
    echo "  ✅ 进程数: $proc_count (正常)"
fi

echo -e "\n============================================"
if [ "$warnings" -eq 0 ]; then
    echo "🎉 系统健康! 无警告"
else
    echo "⚠️ 发现 $warnings 个问题需要关注"
fi

echo "🦞 奥创状态: 🟢 正常运作中"