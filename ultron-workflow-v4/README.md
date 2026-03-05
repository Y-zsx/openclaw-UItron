# 奥创转世系统 v4.0

模块化设计的自主思考系统。

## 目录结构

```
ultron-workflow-v4/
├── config/              # 配置
│   └── settings.yaml    # 系统配置
├── planner/             # 规划层
│   ├── task_graph.py    # 任务依赖图
│   └── scheduler.py     # 任务调度器
├── memory/              # 记忆层
│   └── incarnation.py   # 跨世记忆传承
├── executor/            # 执行层
│   ├── state_machine.py # 状态机
│   └── state.json       # 执行状态存储
├── memory/              # 记忆存储
│   ├── short_term.json  # 短期记忆
│   └── incarnation.json # 跨世记忆
└── ultron-life-v4.py    # 主入口
```

## 核心概念

### 1. 任务依赖图 (Planner)
- 任务之间有依赖关系
- 只有依赖满足才能执行
- 支持任务链: A → B → C → D

### 2. 状态机 (Executor)
- 精确的状态转换
- 自动重试机制
- 失败记录和学习

### 3. 跨世记忆 (Memory)
- short_term: 当前任务上下文
- incarnation: 跨世传承的经验
- 教训和洞察累积

## 使用

```bash
# 运行一次
python ultron-life-v4.py

# 状态查看
cat config/task_graph.json
cat memory/incarnation.json
```

## v3 vs v4

| 特性 | v3 | v4 |
|------|-----|-----|
| 任务依赖 | 无 | 有 |
| 状态管理 | 简单记录 | 状态机 |
| 记忆传承 | 每世重读 | 跨世累积 |
| 错误处理 | 无 | 重试+回滚 |