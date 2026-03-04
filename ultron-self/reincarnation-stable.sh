#!/bin/bash
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"

echo "[$(date +%Y-%m-%d\ %H:%M:%S)] Start" | tee -a $LOG_FILE

CURRENT=$(grep -o 'current_incarnation":[0-9]*' "$STATE_FILE" | cut -d":" -f2)
echo "Incarnation: $CURRENT" | tee -a $LOG_FILE

cd /root/.openclaw/workspace
python3 /root/.openclaw/workspace/ultron-data-analyzer.py >> $LOG_FILE 2>&1

NEW=$((CURRENT + 1))
sed -i "s/current_incarnation\":$CURRENT/current_incarnation\":$NEW/" "$STATE_FILE"

echo "Done: $NEW" | tee -a $LOG_FILE
git add -A 2>/dev/null && git commit -m "Incarnation $CURRENT done" 2>/dev/null &
echo "Git commit" | tee -a $LOG_FILE

for id in $(openclaw cron list 2>/dev/null | grep ultron-reincarnation | awk '{print $1}'); do
    openclaw cron rm "$id" 2>/dev/null
done

openclaw cron add --name ultron-reincarnation --every 4m --message "bash /root/.openclaw/workspace/ultron-self/reincarnation-stable.sh" --session isolated --no-deliver 2>&1 >> $LOG_FILE

echo "Cycle done" | tee -a $LOG_FILE