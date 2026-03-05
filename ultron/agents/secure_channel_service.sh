#!/bin/bash
# Secure Channel Gateway 启动脚本

AGENT_DIR="/root/.openclaw/workspace/ultron/agents"
PID_FILE="/tmp/secure_channel.pid"

start() {
    echo "Starting Secure Channel Gateway..."
    cd $AGENT_DIR
    nohup python3 secure_channel_api.py --port 8091 > /tmp/secure_channel.log 2>&1 &
    echo $! > $PID_FILE
    echo "Started (PID: $(cat $PID_FILE))"
}

stop() {
    if [ -f $PID_FILE ]; then
        kill $(cat $PID_FILE) 2>/dev/null
        rm $PID_FILE
        echo "Stopped"
    else
        echo "Not running"
    fi
}

status() {
    if [ -f $PID_FILE ] && kill -0 $(cat $PID_FILE) 2>/dev/null; then
        echo "Running (PID: $(cat $PID_FILE))"
        curl -s http://localhost:8091/health 2>/dev/null | python3 -m json.tool
    else
        echo "Not running"
    fi
}

case "$1" in
    start) start ;;
    stop) stop ;;
    status) status ;;
    restart) stop; start ;;
    *) echo "Usage: $0 {start|stop|status|restart}" ;;
esac