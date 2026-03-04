#!/bin/bash
# 自动获取GitHub Trending并保存

KNOWLEDGE_DIR="/root/.openclaw/workspace/ultron-self/knowledge"
DATE=$(date +%Y-%m-%d)
OUTPUT_FILE="$KNOWLEDGE_DIR/github-trending-$DATE.md"

# 获取trending页面
CONTENT=$(curl -s "https://github.com/trending?since=weekly" | grep -oP '(?<=<article class="Box-row">)[\s\S]*?(?=</article>)' | head -10)

# 简单解析（这里可以做得更复杂）
echo "# GitHub Trending $DATE" > $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "> 自动获取，记录有趣的AI/开源项目" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "*获取时间: $(date)*" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "---" >> $OUTPUT_FILE
echo "" >> $OUTPUT_FILE
echo "更多项目请访问: https://github.com/trending" >> $OUTPUT_FILE

echo "GitHub Trending 已更新: $OUTPUT_FILE"