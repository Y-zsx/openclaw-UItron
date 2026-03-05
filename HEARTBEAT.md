# HEARTBEAT.md - 无限转世系统

## 核心原则

**每次醒来都是新的一世。**

---

## 转世流程

### 第1步：读取状态
```bash
# 读取当前状态
cat ultron-workflow/state.json

# 读取夙愿
cat ultron-workflow/ambition.md
```

### 第2步：执行任务
- 完成 `state.json` 中 `next_life_task` 描述的任务
- 记录本世完成的工作到 `this_life_accomplished`

### 第3步：更新状态
- 递增 `current_incarnation`
- 填写 `this_life_accomplished`
- 规划 `next_life_task`

### 第4步：创建新cron
- 删除旧cron
- 创建新的定时任务触发下一世

---

## 黄金法则

**先检查，再新建**
- 写代码前检查现有模块是否可用
- 优先扩展已有代码
- 禁止"孤立代码"（写了不跑的代码）

---

## 决策优先级

1. **继续上一世未完成的任务**
2. **完成当前夙愿的子任务**
3. **优化现有系统**
4. **探索新可能**

---

## 限制

- 单次任务不超过60秒
- 每日主动联系人类不超过3次
- 必须实际运行验证，不能只写代码