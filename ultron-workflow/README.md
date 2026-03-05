# 奥创转世系统 v3

## 核心变化

**命名方式优化**: 以"夙愿"为前缀单独计数
- 旧: `第78世`, `第79世` (全局累加)
- 新: `夙愿1-任务1`, `夙愿1-任务2` (夙愿内单独计数)

## 核心文件

| 文件 | 作用 |
|------|------|
| `ambition.md` | 夙愿文档（当前目标、里程碑） |
| `state.json` | 状态记录（夙愿ID、任务计数、历史） |
| `reincarnate.py` | 转世执行器 |
| `ultron-life.py` | 任务执行器 |

## 转世流程

```
醒来 → 读取ambition.md + state.json → 执行任务 → 验证 → 更新 → 创建cron → 轮回
```

## 状态格式 (v3)

```json
{
  "version": "3.0",
  "ambition": {
    "id": 1,
    "name": "模块整合与实用化",
    "count": 2,
    "status": "running"
  },
  "this_life": {...},
  "next_life": {...},
  "history": [...]
}
```

## 命令

```bash
# 查看当前状态
python3 ultron/core/reincarnate.py status

# 手动触发转世
python3 ultron/core/reincarnate.py next

# 启动生命周期
python3 ultron/core/ultron-life.py
```

## 验证机制

每任务完成后自动验证，确保：
- 代码真的在运行
- 功能真的可用
- 验证结果写入state.json

## 夙愿切换

当一个夙愿完成后：
1. 更新 ambition.md 添加新夙愿
2. 重置 count 为 1
3. ambition.id 递增