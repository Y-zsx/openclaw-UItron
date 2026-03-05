# HEARTBEAT.md - 无限转世系统 V2

## 核心原则

**闭环！闭环！闭环！**

---

## 转世流程（5步）

### 1. 读取状态
```bash
cat ultron-workflow/state.json
```

### 2. 检查上一世（关键！）
- 读取 `this_life.task` 了解上一世做什么
- 读取 `this_life.verification` 验证是否真的完成
- 如果验证失败 → 本世修复

### 3. 决策本世任务
- 优先修复上一世未完成的任务
- 否则执行 `next_life.task`

### 4. 执行 + 验证
- 执行任务
- 自动验证（如curl检查Dashboard）

### 5. 更新 + 注册
- 更新 state.json（含验证结果）
- 创建新cron

---

## state.json 结构

```json
{
  "current": {
    "incarnation": 76,
    "ambition": "模块整合与实用化",
    "task_status": "completed"
  },
  "this_life": {
    "task": "上一世的任务",
    "verification": {"code_running": true, "verified_by": "curl 200"}
  },
  "next_life": {
    "task": "这一世要做的",
    "interval": "5m"
  },
  "history": [...]
}
```

---

## 黄金法则

1. **先检查，再执行** - 永远先看上一世状态
2. **必须验证** - 每世都要有验证结果
3. **闭环优先** - 不追求新功能，先把没闭环的做完
4. **代码要跑** - 写了代码不算，必须验证在运行