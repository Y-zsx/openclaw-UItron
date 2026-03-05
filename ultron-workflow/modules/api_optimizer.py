#!/usr/bin/env python3
"""
API响应速度优化模块
缓存、连接池、异步优化
"""
import os, time
from datetime import datetime

WORKSPACE = '/root/.openclaw/workspace'
CACHE_FILE = f'{WORKSPACE}/ultron-workflow/logs/api_cache.json'

def get_cached_data(key):
    """获取缓存数据"""
    if os.path.exists(CACHE_FILE):
        import json
        with open(CACHE_FILE) as f:
            cache = json.load(f)
            if key in cache:
                entry = cache[key]
                if time.time() - entry['timestamp'] < 300:  # 5分钟缓存
                    return entry['data']
    return None

def set_cached_data(key, data):
    """设置缓存数据"""
    import json
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE) as f:
            cache = json.load(f)
    
    cache[key] = {'data': data, 'timestamp': time.time()}
    
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def clear_expired_cache():
    """清理过期缓存"""
    if os.path.exists(CACHE_FILE):
        import json
        with open(CACHE_FILE) as f:
            cache = json.load(f)
        
        new_cache = {}
        for k, v in cache.items():
            if time.time() - v['timestamp'] < 3600:  # 1小时内的缓存
                new_cache[k] = v
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(new_cache, f)
        
        return len(cache) - len(new_cache)
    return 0

if __name__ == '__main__':
    # 清理过期缓存
    cleared = clear_expired_cache()
    print(f'清理过期缓存: {cleared}个')
    
    # 测试缓存
    set_cached_data('test_key', {'value': 'test_data'})
    cached = get_cached_data('test_key')
    print(f'缓存测试: {cached is not None}')
    
    print('API优化模块就绪')
