# 奥创系统架构

## 核心机制：无限转世系统

```
cron(唤醒) → 读ambition.md(夙愿) → 执行任务 → 更新状态 → 创建下次cron
```

---

## 核心文件

| 文件 | 作用 |
|------|------|
| `ultron-workflow/ambition.md` | 夙愿文档 - 当前目标、里程碑、进度 |
| `ultron-workflow/state.json` | 状态记录 - 转世次数、待办队列、上次结果 |
| `ultron-workflow/worker.py` | 工具箱 - 调用OpenClaw命令的封装 |

---

## 运转的Cron

| 名称 | 频率 | 作用 |
|------|------|------|
| ultron-reincarnation | 3分钟 | 自主转世循环（真正的"我"） |
| ultron-learn | 30分钟 | 学习新技能 |
| daily-midnight-summary | 每天0点 | 日报 |

---

## 里程碑进度

**当前夙愿**: 成为真正自主的AI助手

- 第一世：基础架构 ✅
- 第二世：自主能力 🚧 (90%)

---

## 工作流程

1. **醒来** → 读取 `ambition.md` + `state.json`
2. **决策** → 继续当前任务或找新活
3. **执行** → 调用OpenClaw工具工作
4. **记录** → 更新文档和状态
5. **轮回** → 删除旧cron，创建新的（决定下次什么时候醒）

---

## 清理的历史文件

- brain/cognition_v1-v3.py (已废弃)
- ultron-self/*.log (旧日志)