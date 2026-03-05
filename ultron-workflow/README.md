# 奥创转世系统

## 核心文件

| 文件 | 作用 |
|------|------|
| `state.json` | 唯一状态来源（当前世数、任务、验证） |
| `reincarnate-v2.py` | 转世执行器（闭环流程） |
| `README.md` | 本文件 |

## 转世流程

```
醒来 → 读取state.json → 检查上一世验证 → 决策 → 执行 → 验证 → 更新 → 创建cron
```

## 命令

```bash
# 手动运行转世
python3 ultron-workflow/reincarnate-v2.py

# 查看当前状态
cat ultron-workflow/state.json | jq .
```

## 验证机制

每世任务完成后自动验证，确保：
- 代码真的在运行
- 功能真的可用
- 验证结果写入state.json