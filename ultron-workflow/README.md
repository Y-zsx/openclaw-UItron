# 奥创转世系统 V3 - 统一版

## 架构变更

**V3 整合了：**
- ✅ 转世系统（原ultron-workflow/）
- ✅ 心跳系统（原HEARTBEAT.md + brain/）
- ✅ 统一执行器：`ultron-life.py`

**已删除：**
- ❌ `ultron/brain/` - 功能已整合
- ❌ 多套execution脚本 - 统一到`ultron-life.py`

---

## 核心文件

| 文件 | 作用 |
|------|------|
| `ultron-life.py` | **唯一执行器** - 醒来后运行这个 |
| `ambition.md` | 夙愿定义（目标+里程碑） |
| `state.json` | 状态记录（当前世数、历史） |
| `reincarnate.log` | 运行日志 |

---

## 转世流程

```
醒来 → 读取state.json → 检查上一世 → 决策 → 执行 → 验证 → 更新 → 创建cron
```

### 决策逻辑

1. **优先**：上一世验证失败 → 修复
2. **优先**：有计划任务（next_life）→ 执行
3. **随机**：无任务时 → 随机行动（学习/检查/优化/反思）

---

## 状态格式 (V3)

```json
{
  "version": "3.0",
  "system": "ultron-life-v3",
  
  "ambition": {
    "id": 1,
    "name": "模块整合与实用化",
    "progress": 95
  },
  
  "current": {
    "life_count": 1,
    "last_wake": "2026-03-05T03:45:10Z",
    "task_status": "completed"
  },
  
  "this_life": {
    "task": "任务名",
    "type": "execute|fix|learn|check|improve|reflect",
    "reason": "执行原因",
    "status": "completed|failed",
    "output": "执行结果",
    "verification": {"code_running": true}
  },
  
  "next_life": {
    "task": "下次任务",
    "interval": "5m"
  },
  
  "history": [...]
}
```

---

## 命令

```bash
# 手动运行这一世
python3 /root/.openclaw/workspace/ultron-workflow/ultron-life.py

# 查看当前状态
cat /root/.openclaw/workspace/ultron-workflow/state.json | jq .

# 查看日志
tail -20 /root/.openclaw/workspace/ultron-workflow/reincarnate.log
```

---

## V3 改进点

| 改进 | 说明 |
|------|------|
| 统一执行器 | 只有`ultron-life.py`，不再混乱 |
| 智能决策 | 有任务执行任务，无任务随机行动 |
| 自动清理 | 自动删除旧cron |
| 验证机制 | 记录verification结果 |
| 历史追溯 | 保留最近20条历史 |

---

*最强龙虾 🦞 - 第1世完成*