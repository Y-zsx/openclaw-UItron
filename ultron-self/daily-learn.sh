#!/bin/bash
# 每日学习脚本 - 自主学习
SKILLS_DIR="/usr/lib/node_modules/openclaw/skills"
LEARN_LOG="/root/.openclaw/workspace/ultron-self/learn-log.txt"

echo "=== 学习时间 $(date) ===" >> $LEARN_LOG

# 随机选一个技能学习
if [ -d "$SKILLS_DIR" ]; then
    RANDOM_SKILL=$(ls "$SKILLS_DIR" 2>/dev/null | shuf -n1)
    if [ -n "$RANDOM_SKILL" ]; then
        SKILL_PATH="$SKILLS_DIR/$RANDOM_SKILL/SKILL.md"
        if [ -f "$SKILL_PATH" ]; then
            LINES=$(wc -l < "$SKILL_PATH")
            echo "学习: $RANDOM_SKILL ($LINES 行)" >> $LEARN_LOG
        fi
    fi
fi
