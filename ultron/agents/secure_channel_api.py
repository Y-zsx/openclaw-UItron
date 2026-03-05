#!/usr/bin/env python3
"""
Secure Channel REST API - 安全通道HTTP接口
"""

from flask import Flask, request, jsonify
from secure_channel import (
    SecureGateway, EncryptionType, ChannelStatus
)
import argparse

app = Flask(__name__)
gateway = None

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "secure-channel-gateway",
        "port": gateway.port if gateway else 8091
    })

@app.route('/api/channels', methods=['POST'])
def create_channel():
    """创建安全通道"""
    data = request.get_json()
    
    agent_a = data.get('agent_a')
    agent_b = data.get('agent_b')
    encryption = data.get('encryption', 'e2e')
    
    if not agent_a or not agent_b:
        return jsonify({"error": "agent_a and agent_b required"}), 400
    
    result = gateway.create_secure_channel(agent_a, agent_b, encryption)
    return jsonify(result)

@app.route('/api/channels', methods=['GET'])
def list_channels():
    """列出所有通道"""
    channels = []
    for ch in gateway.channel_manager.channels.values():
        channels.append({
            "channel_id": ch.channel_id,
            "agent_a": ch.agent_a,
            "agent_b": ch.agent_b,
            "encryption": ch.encryption.value,
            "status": ch.status.value,
            "message_count": ch.message_count,
            "created_at": ch.created_at.isoformat()
        })
    return jsonify({"channels": channels})

@app.route('/api/channels/<channel_id>', methods=['GET'])
def get_channel(channel_id):
    """获取通道详情"""
    info = gateway.get_channel_info(channel_id)
    if not info:
        return jsonify({"error": "Channel not found"}), 404
    return jsonify(info)

@app.route('/api/channels/<channel_id>', methods=['DELETE'])
def close_channel(channel_id):
    """关闭通道"""
    success = gateway.channel_manager.close_channel(channel_id)
    return jsonify({"success": success})

@app.route('/api/channels/<channel_id>/messages', methods=['POST'])
def send_message(channel_id):
    """发送加密消息"""
    data = request.get_json()
    
    sender = data.get('sender')
    recipient = data.get('recipient')
    message = data.get('message')
    
    if not all([sender, recipient, message]):
        return jsonify({"error": "sender, recipient, message required"}), 400
    
    result = gateway.send_message(channel_id, sender, recipient, message)
    return jsonify(result)

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    return jsonify(gateway.get_stats())

def main():
    global gateway
    
    parser = argparse.ArgumentParser(description='Secure Channel API')
    parser.add_argument('--port', type=int, default=8091, help='API port')
    args = parser.parse_args()
    
    gateway = SecureGateway(port=args.port)
    gateway.start()
    
    print(f"\n🔐 Secure Channel API: http://localhost:{args.port}")
    print("   Endpoints:")
    print("   - POST /api/channels       创建通道")
    print("   - GET  /api/channels       列出通道")
    print("   - GET  /api/channels/<id>  通道详情")
    print("   - DELETE /api/channels/<id> 关闭通道")
    print("   - POST /api/channels/<id>/messages 发送消息")
    print("   - GET  /api/stats          统计信息")
    
    app.run(host='0.0.0.0', port=args.port, debug=False)

if __name__ == '__main__':
    main()