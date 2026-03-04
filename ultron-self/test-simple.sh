#!/bin/bash
LOCK_FILE="/tmp/ultron-reincarnation.lock"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"

log() { 
    echo "[$(date +%Y-%m-%d\ %H:%M:%S)] $1" | tee -a $LOG_FILE
}

if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(($(date +%s) - $(stat -c %Y "$LOCK_FILE" 2>/dev/null || echo 0)))
    if [ "$LOCK_AGE" -lt 300 ]; then
        log "SKIP"
        exit 0
    fi
    rm -f "$LOCK_FILE"
fi
trap "rm -f $LOCK_FILE" EXIT
touch "$LOCK_FILE"

log "Start"

CURRENT=$(grep -o "current_incarnation":[0-9]*" "$STATE_FILE" | cut -d":" -f2)
if [ -z "$CURRENT" ]; then CURRENT=1; fi
log "Incarnation: $CURRENT"

cd /root/.openclaw/workspace
python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1

NEW=$((CURRENT + 1))
sed -i "s/current_incarnation":$CURRENT/current_incarnation":$NEW/" "$STATE_FILE"
log "Done: $NEW"

git add -A 2>/dev/null && git commit -m "Incarnation $CURRENT done" 2>/dev/null &
log "Git commit"

for id in $(openclaw cron list 2>/dev/null | grep ultron-reincarnation | awk "{print $1}"); do
    openclaw cron rm "$id" 2>/dev/null
done

openclaw cron add --name ultron-reincarnation --every 4m --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" --session isolated --no-deliver 2>&1 >> $LOG_FILE

log "Cycle done"
