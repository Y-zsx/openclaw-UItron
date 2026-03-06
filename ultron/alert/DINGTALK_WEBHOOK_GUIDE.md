# DingTalk 机器人 Webhook 配置指南

## 快速配置 (3步)

### 1. 创建自定义机器人
1. 打开钉钉群 → 设置 → 智能群助手
2. 添加机器人 → 自定义
3. 填写名称: `奥创告警`
4. 安全设置: 选择 "加签" (推荐) 或 "自定义关键词"
5. 复制 Webhook 地址

### 2. 配置加签 (推荐)
如果选择加签，需计算签名:
```python
import time
import hmac
import hashlib
import base64
import urllib.parse

timestamp = str(round(time.time() * 1000))
secret = '你的机器人密钥(以SEC开头的)'

secret_enc = secret.encode('utf-8')
string_to_sign = '{}\n{}'.format(timestamp, secret)
string_to_sign_enc = string_to_sign.encode('utf-8')
hmac_code = hmac.new(secret_enc, string_to_sign_enc, digestmod=hashlib.sha256).digest()
sign = urllib.parse.quote_plus(base64.b64encode(hmac_code))

webhook = f"https://oapi.dingtalk.com/robot/send?access_token=你的token&timestamp={timestamp}&sign={sign}"
```

### 3. 更新配置文件
```bash
# 编辑告警配置
vim /root/.openclaw/workspace/ultron/alert/config.yaml

# 修改 webhook_url 为你的真实地址
webhook_url: "https://oapi.dingtalk.com/robot/send?access_token=xxx"
```

## 测试
配置完成后，告警服务会自动发送测试消息。

## 当前状态
- 告警服务端口: 18215
- 配置文件: /root/.openclaw/workspace/ultron/alert/config.yaml
- 状态查询: curl http://localhost:18215/status