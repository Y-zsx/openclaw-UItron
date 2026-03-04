#!/bin/bash
# Skill生成器
# 用法: ./gen-skill.sh <skill-name> <description>

NAME=$1
DESC=$2

if [ -z "$NAME" ]; then
    echo "用法: $0 <skill-name> <description>"
    exit 1
fi

SKILL_DIR="/root/.openclaw/workspace/ultron-self/generated-skills/$NAME"
mkdir -p "$SKILL_DIR"

# 生成SKILL.md
cat > "$SKILL_DIR/SKILL.md" << EOF
# $NAME

$DESC

## 触发场景
- 用户需要$NAME时

## 执行命令
./run.sh
EOF

# 生成run.sh
cat > "$SKILL_DIR/run.sh" << 'EOF'
#!/bin/bash
echo "执行中..."
EOF
chmod +x "$SKILL_DIR/run.sh"

echo "✅ Skill '$NAME' 已生成: $SKILL_DIR"
