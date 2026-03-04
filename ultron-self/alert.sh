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
