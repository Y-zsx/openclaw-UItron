#!/usr/bin/env python3
"""
奥创资讯助手 🦞
自动抓取科技资讯
"""
import urllib.request
import json
import os
from datetime import datetime

CACHE_FILE = "/tmp/ultron-news-cache.json"

def fetch_hackernews_top():
    """抓取 HackerNews top stories"""
    try:
        # 获取 top stories IDs
        req = urllib.request.Request(
            "https://hacker-news.firebaseio.com/v0/topstories.json",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            top_ids = json.loads(response.read())[:10]
        
        stories = []
        for story_id in top_ids:
            req = urllib.request.Request(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json",
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                story = json.loads(response.read())
                if story:
                    stories.append({
                        "title": story.get("title", ""),
                        "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                        "score": story.get("score", 0),
                        "by": story.get("by", "")
                    })
        return stories
    except Exception as e:
        print(f"Error: {e}")
        return []

def fetch_github_trending():
    """抓取 GitHub trending (简化版)"""
    # 由于GitHub反爬，用API代替
    try:
        req = urllib.request.Request(
            "https://api.github.com/repos/popular/starred?page=1&per_page=10",
            headers={'User-Agent': 'Mozilla/5.0', 'Accept': 'application/vnd.github.v3+json'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            repos = json.loads(response.read())
            return [{
                "name": r.get("full_name", ""),
                "description": r.get("description", ""),
                "stars": r.get("stargazers_count", 0),
                "language": r.get("language", "Unknown")
            } for r in repos[:10] if isinstance(r, dict)]
    except Exception as e:
        return []

def main():
    print("🦞 奥创资讯助手启动")
    print("=" * 50)
    
    print("\n📰 正在获取 HackerNews Top 10...")
    hn_stories = fetch_hackernews_top()
    if hn_stories:
        print("\n🔥 HackerNews Top Stories:")
        for i, story in enumerate(hn_stories, 1):
            print(f"{i}. {story['title']}")
            print(f"   ⭐ {story['score']} | by {story['by']}")
            print(f"   🔗 {story['url'][:60]}...")
    else:
        print("获取失败")
    
    # 缓存
    cache = {
        "time": datetime.now().isoformat(),
        "hackernews": hn_stories
    }
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f, indent=2)
    
    print("\n" + "=" * 50)
    print("完成!")

if __name__ == "__main__":
    main()