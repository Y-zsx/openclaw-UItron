#!/usr/bin/env python3
"""
奥创科技情报收集器
自动收集科技行业最新资讯
"""
import json
import os
from datetime import datetime
from pathlib import Path

LOG_DIR = Path("/root/.openclaw/workspace/ultron/logs")

def fetch_tech_news():
    """从多个源获取科技新闻"""
    news_items = []
    sources = [
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "Hacker News", "url": "https://news.ycombinator.com/rss"},
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/technology-lab"},
    ]
    
    import urllib.request
    import xml.etree.ElementTree as ET
    
    for source in sources:
        try:
            req = urllib.request.Request(source["url"], headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=10) as response:
                content = response.read()
                root = ET.fromstring(content)
                # 提取前5条新闻
                items = root.findall(".//item")[:5]
                for item in items:
                    title = item.find("title")
                    link = item.find("link")
                    news_items.append({
                        "source": source["name"],
                        "title": title.text if title is not None else "无标题",
                        "link": link.text if link is not None else "",
                        "time": datetime.now().isoformat()
                    })
        except Exception as e:
            news_items.append({
                "source": source["name"],
                "title": f"获取失败: {str(e)}",
                "link": "",
                "time": datetime.now().isoformat()
            })
    
    return news_items

def save_report(news):
    """保存情报报告"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_file = LOG_DIR / f"intelligence_{timestamp}.json"
    
    report = {
        "created": datetime.now().isoformat(),
        "count": len(news),
        "news": news
    }
    
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 同时更新最新报告
    latest_file = LOG_DIR / "latest_intelligence.json"
    with open(latest_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    return report_file

def main():
    print(f"🤖 奥创科技情报收集器启动 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 50)
    
    # 收集情报
    news = fetch_tech_news()
    print(f"📰 获取到 {len(news)} 条科技资讯")
    
    # 保存报告
    report_file = save_report(news)
    print(f"💾 报告已保存: {report_file}")
    
    # 显示摘要
    print("\n📊 情报摘要:")
    for i, item in enumerate(news[:10], 1):
        print(f"  {i}. [{item['source']}] {item['title'][:60]}...")
    
    print("\n✅ 情报收集完成!")
    return len(news)

if __name__ == "__main__":
    main()