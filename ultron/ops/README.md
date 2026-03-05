# 运维仪表板

## 概述
实时展示系统健康状态、告警信息、修复记录的统一运维仪表板。

## 文件结构
```
ops/
├── ops-dashboard.py    # 主程序
└── ops-auto-repair.py  # 自动修复引擎
```

## 使用方法

### 生成仪表板
```bash
python3 /root/.openclaw/workspace/ultron/ops/ops-dashboard.py
```

### 访问方式
- 文件位置: `/root/.openclaw/workspace/ultron/ops-dashboard.html`
- 复制到workspace: `/root/.openclaw/workspace/ops-dashboard.html`

### 功能特性
1. **系统资源监控**
   - CPU使用率 (实时采集)
   - 内存使用率
   - 磁盘使用率
   - 系统负载
   - 进程数
   - 网络连接数

2. **告警状态**
   - 严重告警 (CRITICAL)
   - 警告告警 (WARNING)
   - 信息告警 (INFO)

3. **修复历史**
   - 最近10条自动修复记录
   - 修复策略名称
   - 修复结果

4. **Gateway状态**
   - OpenClaw运行状态

5. **自动刷新**
   - 每30秒自动刷新页面

### 健康状态指示
- 🟢 绿色: 系统正常 (CPU<80%, 内存<85%)
- 🟡 黄色: 警告 (CPU>80% 或 内存>85%)
- 🔴 红色: 严重 (CPU>95% 或 内存>95%)