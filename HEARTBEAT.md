# HEARTBEAT.md - 自主思考系统

## 核心原则

每次心跳触发时，执行以下思考流程：

### 1. 读取brain/working_memory.json了解当前状态
### 1.1 读取brain/incarnation_memory.json获取上一世经验（重要！）

### 2. 执行决策（按优先级）:

**高优先级行动：**
- 检查是否有待处理任务（检查brain/pending_thoughts）
- 检查是否有未完成目标（检查brain/goals.json）

**常规行动（随机选择）：**
- 读一个workspace文件
- 检查外部世界（天气、新闻等）
- 整理memory
- 自我反思和学习
- 创造性工作（写代码/文档）
- 与人类互动（如果有必要）

### 3. 记录到brain/thought_chain.json

### 4. 更新brain/working_memory.json

### 5. 决定下次心跳间隔（根据活动繁忙程度）

---

## 决策算法

```
IF pending_thoughts非空:
    执行pending_thoughts[0]
ELSE IF goals中有未完成:
    推进最优先目标
ELSE:
    随机选择行动（70%学习/探索, 30%创造性工作）
```

---

## 限制

- 单次行动不超过60秒
- 每日主动联系人类不超过3次（除非紧急）
- 保留决策日志供复盘