#!/bin/bash
# 奥创AI监控系统 - v1
# 每5分钟收集系统状态

LOG_FILE="/root/.openclaw/workspace/ultron-self/monitor-history.jsonl"
TIMESTAMP=$(date -Iseconds)

# 收集指标
PANEL=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)
GATEWAY=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/health 2>/dev/null)
LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
MEM=$(free | awk '/^Mem:/ {printf "%.1f", $3/$2 * 100}')
DISK=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')

# 写入日志
echo "{\"time\":\"$TIMESTAMP\",\"panel\":\"$PANEL\",\"gateway\":\"$GATEWAY\",\"load\":\"$LOAD\",\"mem\":\"$MEM\",\"disk\":\"$DISK\"}" >> $LOG_FILE

# 简单告警
[ "$PANEL" != "200" ] && echo "[ALERT] Panel down: $PANEL"
[ "$(echo "$MEM > 90" | bc 2>/dev/null || echo 0)" -eq 1 ] && echo "[ALERT] Memory high: $MEM%"
[ "$DISK" -gt 90 ] && echo "[ALERT] Disk full: $DISK%"
