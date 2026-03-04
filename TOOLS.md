# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### 常用OpenClaw命令

```bash
# 状态查看
openclaw status           # 渠道健康状态
openclaw status --deep    # 深度检查
openclaw gateway status   # Gateway状态

# Gateway管理
openclaw gateway --force  # 强制重启Gateway
openclaw logs --follow    # 查看日志

# 浏览器
openclaw browser status   # 浏览器状态

# 渠道
openclaw channels login --verbose  # 登录渠道

# 更新
openclaw update           # 检查更新
```

### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Why Separate?

Skills are shared. Your setup is yours. Keeping them apart means you can update skills without losing your notes, and share skills without leaking your infrastructure.

---

Add whatever helps you do your job. This is your cheat sheet.
