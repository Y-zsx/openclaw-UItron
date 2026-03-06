#!/usr/bin/env python3
"""
智能告警路由服务
根据告警级别、类型、时间等因素自动路由到合适的通知渠道
端口: 18222
"""

import json
import os
from datetime import datetime, time
from flask import Flask, jsonify, request
from collections import defaultdict

app = Flask(__name__)

CONFIG_FILE = "/root/.openclaw/workspace/ultron/data/alert_routing.json"
ROUTING_LOG = "/root/.openclaw/workspace/ultron/data/routing_history.jsonl"

# 默认路由规则
DEFAULT_RULES = {
    "rules": [
        {
            "id": "rule_critical",
            "name": "严重告警路由",
            "condition": {
                "level": "critical"
            },
            "channels": ["dingtalk", "email", "console"],
            "priority": 100,
            "enabled": True
        },
        {
            "id": "rule_warning",
            "name": "警告告警路由",
            "condition": {
                "level": "warning"
            },
            "channels": ["dingtalk", "console"],
            "priority": 50,
            "enabled": True
        },
        {
            "id": "rule_info",
            "name": "信息告警路由",
            "condition": {
                "level": "info"
            },
            "channels": ["console"],
            "priority": 10,
            "enabled": True
        },
        {
            "id": "rule_offhours",
            "name": "非工作时间路由",
            "condition": {
                "time_range": {"start": "22:00", "end": "08:00"}
            },
            "channels": ["email"],
            "priority": 80,
            "enabled": True
        },
        {
            "id": "rule_service_api",
            "name": "API服务告警",
            "condition": {
                "service_type": "api"
            },
            "channels": ["dingtalk", "webhook"],
            "priority": 60,
            "enabled": True
        },
        {
            "id": "rule_service_db",
            "name": "数据库告警",
            "condition": {
                "service_type": "database"
            },
            "channels": ["dingtalk", "email"],
            "priority": 70,
            "enabled": True
        }
    ],
    "default_channels": ["console"],
    "off_hours": {
        "start": "22:00",
        "end": "08:00",
        "enabled": True,
        "channels": ["email"]
    }
}

def load_config():
    """加载路由配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return DEFAULT_RULES.copy()

def save_config(config):
    """保存路由配置"""
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def log_routing(alert, channels):
    """记录路由日志"""
    os.makedirs(os.path.dirname(ROUTING_LOG), exist_ok=True)
    with open(ROUTING_LOG, 'a') as f:
        f.write(json.dumps({
            "timestamp": datetime.now().isoformat(),
            "alert": alert,
            "channels": channels
        }) + "\n")

def check_time_range(time_range, current_time=None):
    """检查时间是否在范围内"""
    if not time_range:
        return False
    
    current_time = current_time or datetime.now().time()
    
    # 使用 datetime.strptime 解析时间
    start_str = time_range.get('start', '00:00')
    end_str = time_range.get('end', '23:59')
    
    start = datetime.strptime(start_str, '%H:%M').time()
    end = datetime.strptime(end_str, '%H:%M').time()
    
    if start <= end:
        return start <= current_time <= end
    else:  # 跨天
        return current_time >= start or current_time <= end

def match_condition(condition, alert):
    """检查告警是否匹配条件"""
    if not condition:
        return True
    
    # 级别匹配
    if 'level' in condition:
        if alert.get('level') != condition['level']:
            return False
    
    # 服务类型匹配
    if 'service_type' in condition:
        if alert.get('service_type') != condition['service_type']:
            return False
    
    # 服务名称匹配
    if 'service' in condition:
        if alert.get('service') != condition['service']:
            return False
    
    # 指标匹配
    if 'metric' in condition:
        if alert.get('metric') != condition['metric']:
            return False
    
    # 阈值匹配
    if 'threshold' in condition:
        value = alert.get('value', 0)
        threshold = condition['threshold']
        operator = condition.get('operator', '>=')
        
        if operator == '>=' and value < threshold:
            return False
        elif operator == '<=' and value > threshold:
            return False
        elif operator == '==' and value != threshold:
            return False
    
    # 时间范围匹配
    if 'time_range' in condition:
        if not check_time_range(condition['time_range']):
            return False
    
    return True

def route_alert(alert):
    """根据规则路由告警"""
    config = load_config()
    matched_channels = set()
    matched_rules = []
    
    # 按优先级排序规则
    rules = sorted(config.get('rules', []), key=lambda x: x.get('priority', 0), reverse=True)
    
    for rule in rules:
        if not rule.get('enabled', True):
            continue
        
        if match_condition(rule.get('condition', {}), alert):
            for channel in rule.get('channels', []):
                matched_channels.add(channel)
            matched_rules.append({
                "rule_id": rule.get('id'),
                "name": rule.get('name'),
                "channels": rule.get('channels', [])
            })
    
    # 如果没有匹配任何规则，使用默认渠道
    if not matched_channels:
        matched_channels = set(config.get('default_channels', ['console']))
        matched_rules.append({
            "rule_id": "default",
            "name": "默认规则",
            "channels": list(matched_channels)
        })
    
    # 检查非工作时间
    current_time = datetime.now().time()
    off_hours = config.get('off_hours', {})
    if off_hours.get('enabled') and check_time_range({
        'start': off_hours.get('start', '22:00'),
        'end': off_hours.get('end', '08:00')
    }, current_time):
        off_hours_channels = set(off_hours.get('channels', ['email']))
        # 合并渠道，优先使用off_hours配置
        matched_channels = matched_channels.union(off_hours_channels)
    
    return {
        "channels": list(matched_channels),
        "rules": matched_rules
    }

@app.route('/api/route', methods=['POST'])
def route():
    """路由告警"""
    alert = request.get_json()
    
    if not alert:
        return jsonify({"status": "error", "message": "No alert data"}), 400
    
    result = route_alert(alert)
    
    # 记录日志
    log_routing(alert, result['channels'])
    
    return jsonify({
        "status": "ok",
        "alert": alert,
        "routing": result,
        "timestamp": datetime.now().isoformat()
    })

@app.route('/api/route/preview', methods=['POST'])
def route_preview():
    """预览路由结果（不实际发送）"""
    alert = request.get_json()
    
    if not alert:
        return jsonify({"status": "error", "message": "No alert data"}), 400
    
    result = route_alert(alert)
    
    return jsonify({
        "status": "ok",
        "alert": alert,
        "routing": result,
        "preview": True
    })

@app.route('/api/rules', methods=['GET'])
def list_rules():
    """列出所有路由规则"""
    config = load_config()
    return jsonify({
        "status": "ok",
        "rules": config.get('rules', [])
    })

@app.route('/api/rules', methods=['POST'])
def add_rule():
    """添加路由规则"""
    config = load_config()
    rule = request.get_json()
    
    if not rule or 'id' not in rule:
        return jsonify({"status": "error", "message": "Rule must have an ID"}), 400
    
    # 检查是否已存在
    for i, existing in enumerate(config.get('rules', [])):
        if existing.get('id') == rule['id']:
            config['rules'][i] = rule
            break
    else:
        config['rules'].append(rule)
    
    save_config(config)
    
    return jsonify({
        "status": "ok",
        "rule": rule
    })

@app.route('/api/rules/<rule_id>', methods=['PUT', 'POST'])
def update_rule(rule_id):
    """更新路由规则"""
    config = load_config()
    data = request.get_json()
    
    for i, rule in enumerate(config.get('rules', [])):
        if rule.get('id') == rule_id:
            config['rules'][i].update(data)
            save_config(config)
            return jsonify({
                "status": "ok",
                "rule": config['rules'][i]
            })
    
    return jsonify({"status": "error", "message": f"Rule {rule_id} not found"}), 404

@app.route('/api/rules/<rule_id>', methods=['DELETE'])
def delete_rule(rule_id):
    """删除路由规则"""
    config = load_config()
    
    original_count = len(config.get('rules', []))
    config['rules'] = [r for r in config.get('rules', []) if r.get('id') != rule_id]
    
    if len(config['rules']) < original_count:
        save_config(config)
        return jsonify({"status": "ok", "message": f"Rule {rule_id} deleted"})
    
    return jsonify({"status": "error", "message": f"Rule {rule_id} not found"}), 404

@app.route('/api/rules/<rule_id>/toggle', methods=['POST'])
def toggle_rule(rule_id):
    """启用/禁用规则"""
    config = load_config()
    
    for i, rule in enumerate(config.get('rules', [])):
        if rule.get('id') == rule_id:
            config['rules'][i]['enabled'] = not rule.get('enabled', True)
            save_config(config)
            return jsonify({
                "status": "ok",
                "rule_id": rule_id,
                "enabled": config['rules'][i]['enabled']
            })
    
    return jsonify({"status": "error", "message": f"Rule {rule_id} not found"}), 404

@app.route('/api/config', methods=['GET'])
def get_config():
    """获取路由配置"""
    config = load_config()
    # 隐藏敏感信息
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/api/config', methods=['PUT', 'POST'])
def update_config():
    """更新路由配置"""
    config = load_config()
    data = request.get_json()
    
    config.update(data)
    save_config(config)
    
    return jsonify({
        "status": "ok",
        "config": config
    })

@app.route('/api/history', methods=['GET'])
def get_history():
    """获取路由历史"""
    limit = request.args.get('limit', 20, type=int)
    
    if not os.path.exists(ROUTING_LOG):
        return jsonify({"status": "ok", "history": []})
    
    history = []
    with open(ROUTING_LOG, 'r') as f:
        for line in reversed(f.readlines()):
            if len(history) >= limit:
                break
            try:
                history.append(json.loads(line))
            except:
                pass
    
    return jsonify({
        "status": "ok",
        "history": history
    })

@app.route('/health', methods=['GET'])
def health():
    return jsonify({
        "status": "healthy",
        "service": "smart-alert-router",
        "port": 18222
    })

if __name__ == '__main__':
    print("启动智能告警路由服务...")
    print(f"端口: 18222")
    print(f"配置文件: {CONFIG_FILE}")
    app.run(host='0.0.0.0', port=18222, debug=False)