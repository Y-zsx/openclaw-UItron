#!/usr/bin/env python3
"""
Secure Channel REST API - 安全通道HTTP接口
基于 KeyManager + SecureChannelManager 实现端到端加密
"""

from flask import Flask, request, jsonify
from secure_channel import KeyManager, SecureChannelManager, Encryptor, EncryptionType, SecureChannel, EncryptedMessage
import argparse
import uuid

app = Flask(__name__)
key_manager = None
channel_manager = None
encryptor = None

def init_managers():
    global key_manager, channel_manager, encryptor
    
    storage_path = "/root/.openclaw/workspace/ultron/agents/data"
    
    key_manager = KeyManager(storage_path=storage_path)
    encryptor = Encryptor(key_manager)
    channel_manager = SecureChannelManager(key_manager, encryptor)
    
    return channel_manager

@app.route('/health', methods=['GET'])
def health():
    """健康检查"""
    return jsonify({
        "status": "healthy",
        "service": "secure-channel-api",
        "port": port
    })

@app.route('/api/key/generate', methods=['POST'])
def generate_key():
    """生成密钥"""
    data = request.get_json() or {}
    agent_id = data.get('agent_id', 'default')
    key = key_manager.generate_session_key(agent_id, 'system')
    return jsonify({"agent_id": agent_id, "session_key": key[:16] + "..."})

@app.route('/api/key/<agent_id>', methods=['GET'])
def get_key(agent_id):
    """获取密钥"""
    key = key_manager.get_session_key(agent_id, 'system')
    if not key:
        return jsonify({"error": "Key not found"}), 404
    return jsonify({"agent_id": agent_id, "session_key": key[:16] + "..."})

@app.route('/api/channels', methods=['POST'])
def create_channel():
    """创建安全通道"""
    data = request.get_json()
    
    agent_a = data.get('agent_a')
    agent_b = data.get('agent_b')
    encryption = data.get('encryption', 'e2e')
    
    if not agent_a or not agent_b:
        return jsonify({"error": "agent_a and agent_b required"}), 400
    
    enc_type = EncryptionType.E2E if encryption == 'e2e' else EncryptionType.TLS
    
    channel = channel_manager.create_channel(agent_a, agent_b, enc_type)
    
    return jsonify({
        "channel_id": channel.channel_id,
        "agent_a": channel.agent_a,
        "agent_b": channel.agent_b,
        "encryption": channel.encryption.value,
        "status": channel.status.value,
        "created_at": channel.created_at.isoformat()
    })

@app.route('/api/channels', methods=['GET'])
def list_channels():
    """列出所有通道"""
    channels = []
    for ch in channel_manager.channels.values():
        channels.append({
            "channel_id": ch.channel_id,
            "agent_a": ch.agent_a,
            "agent_b": ch.agent_b,
            "encryption": ch.encryption.value,
            "status": ch.status.value,
            "message_count": ch.message_count,
            "created_at": ch.created_at.isoformat()
        })
    return jsonify({"channels": channels, "count": len(channels)})

@app.route('/api/channels/<channel_id>', methods=['GET'])
def get_channel(channel_id):
    """获取通道详情"""
    channel = channel_manager.channels.get(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    
    return jsonify({
        "channel_id": channel.channel_id,
        "agent_a": channel.agent_a,
        "agent_b": channel.agent_b,
        "encryption": channel.encryption.value,
        "status": channel.status.value,
        "message_count": channel.message_count,
        "bytes_transferred": channel.bytes_transferred,
        "created_at": channel.created_at.isoformat(),
        "last_activity": channel.last_activity.isoformat()
    })

@app.route('/api/channels/<channel_id>', methods=['DELETE'])
def close_channel(channel_id):
    """关闭通道"""
    with channel_manager._lock:
        if channel_id in channel_manager.channels:
            del channel_manager.channels[channel_id]
            return jsonify({"success": True, "channel_id": channel_id})
    return jsonify({"error": "Channel not found"}), 404

@app.route('/api/channels/<channel_id>/messages', methods=['POST'])
def send_message(channel_id):
    """发送加密消息"""
    data = request.get_json()
    
    sender = data.get('sender')
    recipient = data.get('recipient')
    message = data.get('message')
    
    if not all([sender, recipient, message]):
        return jsonify({"error": "sender, recipient, message required"}), 400
    
    channel = channel_manager.channels.get(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    
    # 加密消息
    encrypted = encryptor.encrypt(
        message,
        channel.session_key,
        sender
    )
    
    # 创建加密消息对象
    enc_msg = EncryptedMessage(
        id=str(uuid.uuid4()),
        channel_id=channel_id,
        sender=sender,
        recipient=recipient,
        encrypted_content=encrypted['content'],
        iv=encrypted['iv'],
        auth_tag=encrypted.get('tag', '')
    )
    
    # 更新通道统计
    channel.message_count += 1
    channel.bytes_transferred += len(message)
    channel.last_activity = datetime.now()
    
    return jsonify({
        "message_id": enc_msg.id,
        "channel_id": enc_msg.channel_id,
        "sender": enc_msg.sender,
        "recipient": enc_msg.recipient,
        "encrypted_preview": enc_msg.encrypted_content[:32] + "...",
        "timestamp": enc_msg.timestamp.isoformat()
    })

@app.route('/api/channels/<channel_id>/messages/decrypt', methods=['POST'])
def decrypt_message(channel_id):
    """解密消息"""
    data = request.get_json()
    
    encrypted_content = data.get('encrypted_content')
    iv = data.get('iv')
    sender = data.get('sender')
    
    if not all([encrypted_content, iv, sender]):
        return jsonify({"error": "encrypted_content, iv, sender required"}), 400
    
    channel = channel_manager.channels.get(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    
    try:
        decrypted = encryptor.decrypt(
            encrypted_content,
            iv,
            channel.session_key,
            sender
        )
        return jsonify({
            "decrypted": decrypted,
            "sender": sender
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    """获取统计信息"""
    return jsonify({
        "channels": len(channel_manager.channels),
        "total_messages": sum(ch.message_count for ch in channel_manager.channels.values()),
        "total_bytes": sum(ch.bytes_transferred for ch in channel_manager.channels.values())
    })


# 需要datetime
from datetime import datetime

def main():
    global port
    parser = argparse.ArgumentParser(description='Secure Channel API')
    parser.add_argument('--port', type=int, default=8091, help='API port')
    args = parser.parse_args()
    port = args.port
    
    init_managers()
    
    print(f"\n🔐 Secure Channel API: http://0.0.0.0:{port}")
    print("   Endpoints:")
    print("   - GET  /health                      健康检查")
    print("   - POST /api/key/generate            生成密钥")
    print("   - GET  /api/key/<agent_id>          获取密钥")
    print("   - POST /api/channels                创建通道")
    print("   - GET  /api/channels                列出通道")
    print("   - GET  /api/channels/<id>           通道详情")
    print("   - DELETE /api/channels/<id>         关闭通道")
    print("   - POST /api/channels/<id>/messages  发送加密消息")
    print("   - POST /api/channels/<id>/messages/decrypt  解密消息")
    print("   - GET  /api/stats                   统计信息")
    
    app.run(host='0.0.0.0', port=port, debug=False)


if __name__ == '__main__':
    main()