# DingTalk Webhook 配置指南

## 当前状态
- 告警服务运行在端口 18215
- 当前配置使用 dummy token，需要真实 webhook 才能发送告警

## 配置步骤

### 方法1: 通过环境变量配置 (推荐)
```bash
export DINGTALK_WEBHOOK="https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN"
```
然后重启告警服务:
```bash
pkill -f agent_alert_dingtalk
cd /root/.openclaw/workspace/ultron/tools && python3 agent_alert_dingtalk.py &
```

### 方法2: 直接修改配置文件
编辑 `/root/.openclaw/workspace/ultron/config/notification_channels.json`:
```json
{
  "id": "dingtalk-ops",
  "config": {
    "webhook_url": "https://oapi.dingtalk.com/robot/send?access_token=YOUR_REAL_TOKEN"
  }
}
```

## 如何获取 DingTalk Webhook

1. 打开钉钉电脑版或手机版
2. 进入要接收告警的群聊
3. 点击右上角「...」→「智能群助手」
4. 点击「添加机器人」
5. 选择「自定义」机器人
6. 设置机器人名称 (如: 奥创告警)
7. 复制生成的 Webhook URL
8. (可选) 安全设置: 加签或 IP 白名单

## 加签方法 (可选安全增强)
如果启用了加签，需要在代码中计算签名:
```
timestamp = 当前时间戳
sign = hmac_sha256(secret, timestamp)
```

## 验证配置
配置完成后，可以测试:
```bash
curl -X POST "https://oapi.dingtalk.com/robot/send?access_token=YOUR_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"msgtype": "text", "text": {"content": "测试消息"}}'
```

---
创建时间: 2026-03-06