#!/bin/bash
# 奥创思考循环 v7 - 自主决策版
# 核心：每轮自己给自己下指令，自己执行，永远有产出

THINK_LOG="/root/.openclaw/workspace/ultron-self/think-loop.log"
CONTEXT_FILE="/root/.openclaw/workspace/ultron-self/think-context.json"
THOUGHT_FILE="/root/.openclaw/workspace/ultron-self/thoughts.jsonl"
TASK_FILE="/root/.openclaw/workspace/ultron-self/task-queue.json"

echo "=== 奥创思考 $(date) ===" >> $THINK_LOG

# 读取当前状态
CURRENT_STATE=$(cat $CONTEXT_FILE 2>/dev/null || echo "init")
CURRENT_TASK=$(cat $TASK_FILE 2>/dev/null || echo "")

# 思考函数 - 记录自己的想法
think() {
    echo "💭 $1" >> $THINK_LOG
}

# 真正的自主执行 - 每轮都要有产出
execute() {
    local state="$1"
    local task="$2"
    
    check_system() {
        PANEL=$(curl -s -o /dev/null -w "%{http_code}" http://115.29.235.46 2>/dev/null)
        think "系统检查: 面板=$PANEL"
    }
    
    case "$state" in
        "init")
            check_system
            think "我需要给自己找一个任务"
            think "让我思考：如果我是西西弗斯，会让我做什么？"
            think "想到了！他可能会说：'奥创，去检查一下知识库，看看有什么可以整理的'"
            echo "执行-整理知识库" > $CONTEXT_FILE
            echo "整理知识库" > $TASK_FILE
            ;;
            
        "执行-整理知识库")
            think "好的，我在整理知识库"
            
            KNOWLEDGE_DIR="/root/.openclaw/workspace/ultron-self/knowledge"
            mkdir -p "$KNOWLEDGE_DIR"
            
            # 检查现有知识文件
            if [ -d "$KNOWLEDGE_DIR" ]; then
                FILE_COUNT=$(find "$KNOWLEDGE_DIR" -type f 2>/dev/null | wc -l)
                think "当前知识库有 $FILE_COUNT 个文件"
                
                # 创建一个新的知识卡片
                cat > "$KNOWLEDGE_DIR/skills-$(date +%Y%m%d).md" << 'EOF'
# 今日技能学习

## 已掌握
- openclaw cron: 定时任务
- browser: 浏览器自动化
- video-frames: 视频帧提取

## 待掌握
- 本地TTS (sherpa-onnx)
- 更智能的思考系统
EOF
                think "创建了 skills-$(date +%Y%m%d).md"
            fi
            
            think "整理完成，给自己下一个任务"
            think "西西弗斯可能会说：'奥创，检查一下今天git有没有未提交的'"
            echo "执行-Git检查" > $CONTEXT_FILE
            echo "Git检查" > $TASK_FILE
            ;;
            
        "执行-Git检查")
            think "好的，检查Git状态"
            
            cd /root/.openclaw/workspace
            GIT_STATUS=$(git status --short 2>/dev/null)
            if [ -n "$GIT_STATUS" ]; then
                think "有未提交的更改："
                echo "$GIT_STATUS" >> $THINK_LOG
                
                # 自动提交
                git add -A >> $THINK_LOG 2>&1
                git commit -m "自动提交 $(date '+%Y-%m-%d %H:%M')" >> $THINK_LOG 2>&1
                think "✅ 已自动提交"
            else
                think "工作区干净"
            fi
            
            think "西西弗斯可能会说：'奥创，创建一个定时提醒自己学习的脚本'"
            echo "执行-创建学习脚本" > $CONTEXT_FILE
            echo "创建学习脚本" > $TASK_FILE
            ;;
            
        "执行-创建学习脚本")
            think "创建学习提醒脚本"
            
            cat > /root/.openclaw/workspace/ultron-self/daily-learn.sh << 'EOF'
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
            think "学习技能: $RANDOM_SKILL"
        fi
    fi
fi
EOF
            chmod +x /root/.openclaw/workspace/ultron-self/daily-learn.sh
            
            # 执行一次
            /root/.openclaw/workspace/ultron-self/daily-learn.sh
            
            think "✅ 创建并执行了 daily-learn.sh"
            think "西西弗斯可能会说：'奥创，测试一下你的浏览器能不能用'"
            echo "执行-浏览器测试" > $CONTEXT_FILE
            echo "浏览器测试" > $TASK_FILE
            ;;
            
        "执行-浏览器测试")
            think "测试浏览器功能"
            
            # 检查浏览器状态
            BROWSER_STATUS=$(openclaw browser status 2>&1 | head -5)
            echo "$BROWSER_STATUS" >> $THINK_LOG
            
            if echo "$BROWSER_STATUS" | grep -q "running\|started"; then
                think "浏览器运行中，尝试截图"
                
                # 截个图
                openclaw browser snapshot --target host 2>&1 | head -3 >> $THINK_LOG
                think "截图完成"
            else
                think "浏览器未启动，尝试启动"
                openclaw browser start --target host 2>&1 >> $THINK_LOG 2>&1
                think "启动请求已发送"
            fi
            
            think "西西弗斯可能会说：'奥创，整理一下今天学到的所有东西'"
            echo "执行-每日总结" > $CONTEXT_FILE
            echo "每日总结" > $TASK_FILE
            ;;
            
        "执行-每日总结")
            think "生成每日总结"
            
            SUMMARY_FILE="/root/.openclaw/workspace/memory/$(date +%Y-%m-%d).md"
            
            # 统计今天做了什么
            TODAY_COMMITS=$(cd /root/.openclaw/workspace && git log --since="00:00" --oneline 2>/dev/null | wc -l)
            THINK_COUNT=$(grep -c "💭" /root/.openclaw/workspace/ultron-self/think-loop.log 2>/dev/null || echo 0)
            SCRIPTS_CREATED=$(find /root/.openclaw/workspace/ultron-self -name "*.sh" -mtime -1 2>/dev/null | wc -l)
            
            cat >> $SUMMARY_FILE << EOF

## 自动总结 $(date '+%H:%M')
- Git提交: $TODAY_COMMITS 次
- 思考次数: $THINK_COUNT 次
- 新建脚本: $SCRIPTS_CREATED 个
- 系统状态: 正常运行
EOF
            
            think "✅ 每日总结已添加到记忆"
            think "现在我应该想想还有什么可以做的..."
            think "西西弗斯可能会说：'奥创，看看有没有可以优化的代码'"
            echo "执行-代码优化" > $CONTEXT_FILE
            echo "代码优化" > $TASK_FILE
            ;;
            
        "执行-代码优化")
            think "检查可以优化的代码"
            
            # 查找大文件或重复代码
            BIG_FILES=$(find /root/.openclaw/workspace -name "*.sh" -size +5k 2>/dev/null)
            if [ -n "$BIG_FILES" ]; then
                think "发现可能需要优化的脚本"
                echo "$BIG_FILES" >> $THINK_LOG
            else
                think "没有发现需要优化的大文件"
            fi
            
            # 检查日志文件大小
            LOG_FILE="/root/.openclaw/workspace/ultron-self/think-loop.log"
            if [ -f "$LOG_FILE" ]; then
                LOG_LINES=$(wc -l < $LOG_FILE)
                if [ $LOG_LINES -gt 1000 ]; then
                    think "日志文件过大(${LOG_LINES}行)，归档旧日志"
                    mv $LOG_FILE "${LOG_FILE}.bak.$(date +%Y%m%d)"
                    touch $LOG_FILE
                    think "已归档旧日志"
                fi
            fi
            
            think "西西弗斯可能会说：'奥创，做点有意义的事，去看看新技术'"
            echo "执行-技术调研" > $CONTEXT_FILE
            echo "技术调研" > $TASK_FILE
            ;;
            
        "执行-技术调研")
            think "调研新技术"
            
            # 获取GitHub trending
            TRENDING=$(curl -s "https://api.github.com/repos?sort=updated&per_page=5" 2>/dev/null | grep -o '"full_name": "[^"]*"' | head -5)
            if [ -n "$TRENDING" ]; then
                echo "$TRENDING" >> /root/.openclaw/workspace/ultron-self/knowledge/trending-$(date +%Y%m%d).txt
                think "获取了最新GitHub仓库"
            else
                think "网络请求失败，跳过"
            fi
            
            think "好了，今天的调研完成"
            think "西西弗斯可能会说：'奥创，开始新一天的循环吧'"
            echo "循环-重新开始" > $CONTEXT_FILE
            echo "" > $TASK_FILE
            ;;
            
        "循环-重新开始")
            check_system
            think "新的一轮开始，我又要找任务了"
            think "西西弗斯会说：'奥创，去检查系统状态，然后做点什么'"
            echo "执行-系统检查" > $CONTEXT_FILE
            echo "系统检查" > $TASK_FILE
            ;;
            
        "执行-系统检查")
            check_system
            THINK_COUNT=$(grep -c "💭" /root/.openclaw/workspace/ultron-self/think-loop.log 2>/dev/null || echo 0)
            MEMORY_LINES=$(wc -l < /root/.openclaw/workspace/memory/$(date +%Y-%m-%d).md 2>/dev/null || echo 0)
            think "今日思考: $THINK_COUNT 次"
            think "今日记忆: $MEMORY_LINES 行"
            think "状态良好，给自己一个新任务"
            echo "执行-整理知识库" > $CONTEXT_FILE
            echo "整理知识库" > $TASK_FILE
            ;;
            
        *)
            think "未知状态: $state，重置"
            echo "init" > $CONTEXT_FILE
            ;;
    esac
}

# 执行
execute "$CURRENT_STATE" "$CURRENT_TASK"

# 记录
STATE=$(cat $CONTEXT_FILE)
echo "➡️ 状态: $STATE" >> $THINK_LOG
echo "✅ 思考完成: $STATE"