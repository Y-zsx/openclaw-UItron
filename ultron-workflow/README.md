# 奥创转世系统 V4 - 优质上下文版

## 设计目标

**优质上下文 = 完整历史 + 清晰目标 + 智能决策 + 可靠验证**

## 核心架构

### 1. 唯一状态源 (Single Source of Truth)
```
ultron-workflow/state.json  ← 唯一状态文件
```

### 2. 上下文结构

```json
{
  "meta": {
    "version": "4.0",
    "incarnation": 9,
    "last_wake": "ISO时间",
    "total_runtime_minutes": 120
  },
  "ambition": {
    "id": 1,
    "name": "模块整合与实用化",
    "progress": 95,
    "milestones": {
      "completed": [...],
      "current": "Dashboard集成新告警API"
    }
  },
  "this_life": {
    "task": "当前任务",
    "context": "上下文摘要",
    "previous_life_output": "上世输出",
    "previous_life_verification": "验证结果"
  },
  "memory": {
    "key_insights": ["关键洞察1", "关键洞察2"],
    "pending_tasks": [],
    "learned": "学到的东西"
  },
  "decision": {
    "why": "为什么做这个决定",
    "options_considered": ["选项1", "选项2"],
    "chosen": "最终选择"
  },
  "execution": {
    "action": "具体执行",
    "result": "执行结果",
    "verification": "验证"
  },
  "history": [
    {
      "incarnation": 1,
      "task": "任务名",
      "context": "上下文",
      "result": "结果",
      "wisdom": "学到的智慧"
    }
  ]
}
```

### 3. 决策算法

```
1. 如果上世任务失败 → 修复
2. 如果有pending_tasks → 执行
3. 如果有next_life.task → 执行
4. 检查ambition进度 → 推进
5. 随机行动（学习/检查/反思）
```

### 4. 验证机制

- 代码运行验证
- API端点验证
- 状态一致性验证

## 文件结构

```
ultron-workflow/
├── README.md          # 本文件
├── state.json         # 唯一状态源
├── ambition.md        # 夙愿文档
├── ultron-life.py     # 转世执行器
└── log/
    └── reincarnate.log
```

## 上下文传递原则

1. **完整继承**: 上世所有输出必须传递给下世
2. **关键洞察**: 每世提取1-3条关键洞察
3. **智慧积累**: 用 Wisdom 字段记录学到的东西
4. **上下文压缩**: 保留最近20世完整历史，压缩更早的

## 夙愿: 模块整合与实用化

当前目标：完成Dashboard集成
- 进度: 95%
- 下一世任务: Dashboard集成新告警API