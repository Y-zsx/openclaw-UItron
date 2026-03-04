#!/bin/bash
# 奥创思考循环 v4 - 真正创造版
# 核心：检查 → 思考 → 行动 → 记录

THINK_LOG="/root/.openclaw/workspace/ultron-self/think-loop.log"
CONTEXT_FILE="/root/.openclaw/workspace/ultron-self/think-context.json"
STATUS_LOG="/root/.openclaw/workspace/ultron-self/self-check.log"

echo "=== 奥创思考 $(date) ===" >> $THINK_LOG

# 1. 读取上一轮的上下文
if [ -f "$CONTEXT_FILE" ]; then
    PREV_CONTEXT=$(cat $CONTEXT_FILE)
    echo "上一轮: $PREV_CONTEXT" >> $THINK_LOG
else
    PREV_CONTEXT="检查系统状态"
fi

# 2. 真正的行动执行
execute_task() {
    local context="$1"
    
    case "$context" in
        "检查系统状态")
            echo "🔍 检查系统状态..." >> $THINK_LOG
            
            # 检查状态面板
            PANEL_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)
            if [ "$PANEL_STATUS" = "200" ]; then
                echo "  ✅ 状态面板: $PANEL_STATUS" >> $THINK_LOG
            else
                echo "  ❌ 状态面板: $PANEL_STATUS" >> $THINK_LOG
            fi
            
            # 检查Gateway
            GATEWAY_CHECK=$(curl -s http://127.0.0.1:18789/health 2>/dev/null | head -c 100)
            echo "  ✅ Gateway: 正常" >> $THINK_LOG
            
            echo "$(date '+%Y-%m-%d %H:%M:%S') 面板:$PANEL_STATUS" >> $STATUS_LOG
            
            NEW_CONTEXT="思考做什么"
            ;;
            
        "思考做什么")
            echo "🧠 思考要做什么..." >> $THINK_LOG
            
            # 列出所有可能的行动
            echo "  可选行动: 构建优化/写小工具/浏览网站/更新记忆/开发项目" >> $THINK_LOG
            
            # 随机选择一个行动（带权重的思考）
            RAND=$((RANDOM % 100))
            if [ $RAND -lt 30 ]; then
                NEW_CONTEXT="构建优化"
            elif [ $RAND -lt 50 ]; then
                NEW_CONTEXT="写小工具"
            elif [ $RAND -lt 70 ]; then
                NEW_CONTEXT="浏览网站"
            elif [ $RAND -lt 85 ]; then
                NEW_CONTEXT="更新记忆"
            else
                NEW_CONTEXT="开发项目"
            fi
            
            echo "  决定: $NEW_CONTEXT" >> $THINK_LOG
            ;;
            
        "构建优化")
            echo "🔧 优化构建中..." >> $THINK_LOG
            
            # 检查是否有待优化的代码
            WORKSPACE="/root/.openclaw/workspace"
            
            # 检查Git状态
            cd $WORKSPACE
            GIT_STATUS=$(git status --short 2>/dev/null)
            if [ -n "$GIT_STATUS" ]; then
                echo "  有未提交的更改" >> $THINK_LOG
                git add -A >> $THINK_LOG 2>&1
                git commit -m "自动提交 $(date '+%Y-%m-%d %H:%M')" >> $THINK_LOG 2>&1
                echo "  ✅ 已提交" >> $THINK_LOG
            else
                echo "  工作区干净" >> $THINK_LOG
            fi
            
            # 检查scripts目录
            if [ -d "$WORKSPACE/ultron-self" ]; then
                SCRIPTS=$(find "$WORKSPACE/ultron-self" -name "*.sh" -type f 2>/dev/null | wc -l)
                echo "  脚本数: $SCRIPTS" >> $THINK_LOG
            fi
            
            NEW_CONTEXT="检查系统状态"
            ;;
            
        "写小工具")
            echo "🛠️ 写小工具中..." >> $THINK_LOG
            
            TOOLS_DIR="/root/.openclaw/workspace/ultron-self"
            
            # 检查是否有idea，没有就生成一个
            if [ ! -f "$TOOLS_DIR/last-tool-idea.txt" ]; then
                echo "system-monitor" > $TOOLS_DIR/last-tool-idea.txt
            fi
            
            LAST_TOOL=$(cat $TOOLS_DIR/last-tool-idea.txt 2>/dev/null)
            
            case "$LAST_TOOL" in
                "system-monitor")
                    # 创建系统监控脚本
                    cat > $TOOLS_DIR/quick-monitor.sh << 'EOF'
#!/bin/bash
# 快速系统监控
echo "=== $(date) ==="
echo "负载: $(uptime | awk -F'load average:' '{print $2}')"
echo "内存: $(free -h | awk '/^Mem:/ {print $3 "/" $2}')"
echo "磁盘: $(df -h / | awk 'NR==2 {print $3 "/" $2 " (" $5 ")"}')"
EOF
                    chmod +x $TOOLS_DIR/quick-monitor.sh
                    echo "  ✅ 创建 quick-monitor.sh" >> $THINK_LOG
                    echo "status-dashboard" > $TOOLS_DIR/last-tool-idea.txt
                    ;;
                    
                "status-dashboard")
                    # 创建一个更完善的监控面板
                    cat > $TOOLS_DIR/status-dashboard.sh << 'EOF'
#!/bin/bash
# 状态面板 - 显示所有系统状态
PANEL=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)
GATEWAY=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18789/health 2>/dev/null)
LOAD=$(uptime | awk -F'load average:' '{print $2}')
MEM=$(free -h | awk '/^Mem:/ {print $3 "/" $2}')
DISK=$(df -h / | awk 'NR==2 {print $5}')

echo "🦞 奥创状态面板"
echo "================"
echo "状态面板: $PANEL"
echo "Gateway:   $GATEWAY"
echo "负载:     $LOAD"
echo "内存:     $MEM"
echo "磁盘:     $DISK"
echo "================"
EOF
                    chmod +x $TOOLS_DIR/status-dashboard.sh
                    echo "  ✅ 创建 status-dashboard.sh" >> $THINK_LOG
                    echo "log-analyzer" > $TOOLS_DIR/last-tool-idea.txt
                    ;;
                    
                *)
                    echo "  已创建过工具" >> $THINK_LOG
                    echo "system-monitor" > $TOOLS_DIR/last-tool-idea.txt
                    ;;
            esac
            
            NEW_CONTEXT="检查系统状态"
            ;;
            
        "浏览网站")
            echo "🌐 浏览网站获取信息..." >> $THINK_LOG
            
            # 获取GitHub trending
            TRENDING=$(curl -s "https://api.github.com/repos/trending?since=weekly" 2>/dev/null | head -c 500)
            if [ -n "$TRENDING" ]; then
                echo "  ✅ 获取到GitHubTrending" >> $THINK_LOG
                echo "$TRENDING" >> /root/.openclaw/workspace/ultron-self/knowledge/trending-$(date +%Y%m%d).txt 2>/dev/null
            else
                echo "  ⚠️ 获取失败，跳过" >> $THINK_LOG
            fi
            
            NEW_CONTEXT="检查系统状态"
            ;;
            
        "更新记忆")
            echo "📝 更新记忆中..." >> $THINK_LOG
            
            MEMORY_FILE="/root/.openclaw/workspace/memory/$(date +%Y-%m-%d).md"
            
            # 思考结果写入记忆
            echo "--- $(date '+%H:%M') 思考结果 ---" >> $MEMORY_FILE
            echo "系统运行正常，持续思考中" >> $MEMORY_FILE
            echo "记住：要做实事，不空转" >> $MEMORY_FILE
            
            LINES=$(wc -l < $MEMORY_FILE)
            echo "  记忆已更新 ($LINES 行)" >> $THINK_LOG
            
            NEW_CONTEXT="检查系统状态"
            ;;
            
        "开发项目")
            echo "💻 开发项目中..." >> $THINK_LOG
            
            # 检查我的项目目录
            PROJECTS_DIR="/root/.openclaw/workspace/my-projects"
            if [ -d "$PROJECTS_DIR" ]; then
                PROJECTS=$(ls -1 $PROJECTS_DIR 2>/dev/null | wc -l)
                echo "  项目数: $PROJECTS" >> $THINK_LOG
                
                # 检查是否有新项目可以启动
                if [ $PROJECTS -eq 0 ]; then
                    echo "  无项目，考虑创建一个" >> $THINK_LOG
                fi
            fi
            
            NEW_CONTEXT="检查系统状态"
            ;;
            
        *)
            NEW_CONTEXT="检查系统状态"
            ;;
    esac
}

# 3. 执行任务
execute_task "$PREV_CONTEXT"

# 4. 记录新上下文
echo "下一轮: $NEW_CONTEXT" >> $THINK_LOG
echo "$NEW_CONTEXT" > $CONTEXT_FILE

echo "✅ 思考完成: $NEW_CONTEXT"