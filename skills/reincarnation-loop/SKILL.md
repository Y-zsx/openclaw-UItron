---
name: reincarnation-loop
description: 自主循环任务系统。让AI能够自我驱动、持续迭代完成任务。适用于：创建需要多轮迭代的长期任务、自动执行定时工作流、构建自我进化的AI系统。当用户说"持续做某事"、"循环执行"、"自我迭代"时使用此skill。
---

# Reincarnation Loop - 自主循环系统

## 核心概念

这是一个让AI能够**自我驱动、持续迭代**的系统。AI不会被每次cron唤醒当作独立任务，而是带着上下文继续推进目标。

```
醒来 → 读目标 → 决策 → 执行 → 记录 → 创建下次cron → 休眠
```

## 快速开始

### 1. 初始化项目结构

创建以下目录结构：
```
your-project/
├── ambition.md      # 夙愿文档
├── state.json       # 状态记录
└── scripts/
    └── reincarnate.py  # (可选) 工具脚本
```

### 2. 创建ambition.md

```markdown
# 我的夙愿

## 当前目标
[具体描述要完成的任务]

## 里程碑
- [ ] 里程碑1
- [ ] 里程碑2
- [ ] 里程碑3

## 验收标准
[做到什么程度算完成]
```

### 3. 创建state.json

```json
{
  "current_incarnation": 1,
  "current_ambition": "你的目标",
  "ambition_status": "running",
  "last_incarnation_time": "2026-01-01T00:00:00Z",
  "current_task": "当前正在做的事",
  "task_status": "in_progress",
  "history": [],
  "this_life_accomplished": [],
  "next_life_task": "下次要做什么"
}
```

## 工作流程

### 每次唤醒时

1. **读取状态** - 加载 `ambition.md` + `state.json`
2. **决策** - 根据当前状态决定下一步
3. **执行** - 完成任务的一部分
4. **记录** - 更新 `state.json` 的 history 和 this_life_accomplished
5. **规划下次** - 更新 next_life_task，决定下次唤醒间隔
6. **创建cron** - 删除旧cron，创建新的

### 决策算法

```
IF pending_tasks非空:
    执行 pending_tasks[0]
ELSE IF 当前任务未完成:
    继续当前任务
ELSE IF 有未完成里程碑:
    推进最优先里程碑
ELSE:
    标记完成，汇报结果
```

## 触发条件

此skill在以下情况自动触发：
- 用户说"持续做..."、"循环执行"
- 用户说"让它自己运行"
- 需要多轮迭代的复杂任务

## 参考资源

- [ambition-template.md](references/ambition-template.md) - 夙愿文档模板
- [state-schema.json](references/state-schema.json) - 状态JSON结构
- [decision-engine.md](references/decision-engine.md) - 决策算法详解

## 关键原则

1. **不要重复** - 每次醒来都要推进一点进度
2. **记录一切** - history字段记录每次做了什么
3. **明确下一步** - next_life_task让下次醒来知道做什么
4. **适时停止** - 达成验收标准后主动汇报，不要无限循环