#!/bin/bash
LOCK_FILE="/tmp/ultron-reincarnation.lock"
STATE_FILE="/root/.openclaw/workspace/ultron-workflow/state.json"
LOG_FILE="/root/.openclaw/workspace/ultron-self/reincarnation.log"
log() { echo "[$(date +%Y-%m-%d %H:%M:%S)] $1" | tee -a $LOG_FILE; }
log "Start"
log "Done"
