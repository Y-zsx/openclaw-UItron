# DingTalk 发送问题

## 问题
无法找到用户的DingTalk staffId，导致消息发送失败。

## 错误信息
```
HTTP 400: {"code":"staffId.notExisted","message":"错误描述: staff 不存在"}
```

## 需要
- 用户的钉钉 senderStaffId (如 "manager9140")
- 或full senderId

## 解决方案
1. 用户需要提供正确的钉钉ID
2. 或者在配置文件中设置

## 配置记录
- notification_channels.json 中 user_id 为空
- 配置时间: 2026-03-08
- 状态: 未解决

## 尝试过的方法
1. 检查 openclaw.json 渠道配置 - 无 accounts 配置
2. 查找 session 数据中的 rawEvent - 无 sender 信息
3. 检查 delivery-queue - to 字段为 "heartbeat" 而非有效用户ID
4. 查看 DingTalk 插件源码 - 需要 selfUserId 配置

## 结论
系统需要用户的钉钉 userId 才能发送主动消息。当前无法主动发送消息给用户。

## 时间
2026-03-10 18:40