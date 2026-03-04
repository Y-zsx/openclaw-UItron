---
name: ultron-learning
description: 奥创的运维技能 - 服务器监控和自动化
metadata:
  {
    "openclaw": { "emoji": "🦞" }
  }
---

# 奥创运维技能 🦞

## 服务器状态检查

```bash
# CPU和内存
uptime
free -h
df -h /

# 进程
ps aux --sort=-%mem | head

# 服务状态
systemctl status nginx
systemctl status openclaw-gateway
```

## 状态面板

- 端口 8888: 服务器监控 (Python)
- 端口 8889: 奥创状态面板

访问: http://115.29.235.46:8888

## 常用命令

### Gateway
- `openclaw gateway status` - 检查网关状态
- `openclaw health` - 健康检查
- `openclaw logs --limit 20` - 查看日志

### Cron 任务
- `openclaw cron list` - 列出任务
- `openclaw cron add --every 5m --message "任务"` - 添加任务
- `openclaw cron runs --id <jobId>` - 查看运行历史

### 浏览器
- `openclaw browser status` - 状态
- `openclaw browser start` - 启动
- `openclaw browser snapshot` - 页面快照
- `openclaw browser tabs` - 列出标签页

### 消息
- `openclaw message send --channel dingtalk --target <id> --message <text>`

## 核心架构

- Gateway: 18789端口 (LAN模式)
- 浏览器CDP: 18800端口
- 工具分类: fs/runtime/web/memory/sessions/ui/messaging/automation/nodes/agents/media
- 插件目录: /usr/lib/node_modules/openclaw/extensions/
- 技能目录: /usr/lib/node_modules/openclaw/skills/