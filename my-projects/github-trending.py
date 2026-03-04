#!/usr/bin/env python3
"""
GitHub Trending 自动抓取工具
奥创自制 🦞
"""
import urllib.request
import urllib.parse
import re
import json
import sys
from html import unescape

URL = "https://github.com/trending?since={since}"

def fetch_trending(language="", since="daily"):
    """获取GitHub trending"""
    params = []
    if language:
        params.append(f"spoken_language_code={language}")
    if since:
        params.append(f"since={since}")
    
    url = URL.format(since=since)
    if params:
        url += "&" + "&".join(params)
    
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Linux; Ubuntu) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
    except Exception as e:
        return {"error": str(e)}
    
    # 解析repo
    repos = []
    # 简单的解析 - 寻找article标签
    article_pattern = r'<article[^>]*>(.*?)</article>'
    articles = re.findall(article_pattern, html, re.DOTALL)
    
    for article in articles[:10]:  # 取前10个
        # 提取repo名
        repo_match = re.search(r'href="([^"]+)"[^>]*>\s*([^<]+)</a>', article)
        if repo_match:
            repo = repo_match.group(1).strip()
            name = repo_match.group(2).strip()
            
            # 提取描述
            desc_match = re.search(r'<p[^>]*>([^<]+)</p>', article)
            desc = desc_match.group(1).strip() if desc_match else ""
            
            # 提取语言
            lang_match = re.search(r'<span[^>]*>([^<]+)</span>', article)
            lang = lang_match.group(1).strip() if lang_match else "Unknown"
            
            # 提取stars
            stars_match = re.search(r'(\d+[,]?\d*)\s+stars', article)
            stars = stars_match.group(1) if stars_match else "0"
            
            repos.append({
                "name": name,
                "repo": repo,
                "description": desc,
                "language": lang,
                "stars": stars
            })
    
    return {
        "url": url,
        "count": len(repos),
        "repos": repos
    }

if __name__ == "__main__":
    lang = sys.argv[1] if len(sys.argv) > 1 else ""
    since = sys.argv[2] if len(sys.argv) > 2 else "daily"
    
    result = fetch_trending(lang, since)
    print(json.dumps(result, ensure_ascii=False, indent=2))