# Skill框架设计

## 结构
```
skill-name/
├── SKILL.md        # Skill定义
├── run.sh          # 执行脚本
└── assets/         # 资源文件
```

## SKILL.md 格式
```markdown
# 技能名
## 描述
## 触发场景
## 执行命令
```

## 生成流程
1. 输入skill名和描述
2. 生成目录结构
3. 写入SKILL.md模板
4. 生成run.sh脚本
