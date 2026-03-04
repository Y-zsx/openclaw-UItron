#!/usr/bin/env python3
"""
奥创天气助手 🦞
获取天气信息
"""
import urllib.request
import json
import sys

def get_weather(city="Shanghai"):
    """获取天气"""
    try:
        url = f"https://wttr.in/{city}?format=j1"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read())
            
        current = data.get("current_condition", [{}])[0]
        
        return {
            "city": city,
            "temp": current.get("temp_C", "N/A"),
            "condition": current.get("weatherDesc", [{}])[0].get("value", "Unknown"),
            "humidity": current.get("humidity", "N/A"),
            "wind": current.get("windspeedKmph", "N/A"),
            "feels": current.get("FeelsLikeC", "N/A")
        }
    except Exception as e:
        return {"error": str(e)}

def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "Shanghai"
    
    print(f"🦞 奥创天气助手 - {city}")
    print("=" * 40)
    
    weather = get_weather(city)
    
    if "error" in weather:
        print(f"❌ 错误: {weather['error']}")
        return
    
    print(f"""
🌡️  温度: {weather['temp']}°C
🌤️  天气: {weather['condition']}
💧  湿度: {weather['humidity']}%
🌬️  风速: {weather['wind']} km/h
🤔  体感: {weather['feels']}°C
""")

if __name__ == "__main__":
    main()