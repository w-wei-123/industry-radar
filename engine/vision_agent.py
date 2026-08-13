#!/usr/bin/env python3
"""
视觉分析引擎 · GLM-4.6V-Flash 免费视觉模型
用途：
  1. 识别 K 线图截图 → 形态/趋势/支撑压力
  2. 识别财报截图 → 提取关键数字
  3. 识别龙虎榜截图 → 汇总买卖席位
  4. 集成进 13 Agent 流水线作为"视觉分析师"

用法:
  python vision_agent.py <图片路径或URL> [提示词]

示例:
  python vision_agent.py kline.png "识别这张K线图的技术形态和趋势"
  python vision_agent.py https://image.sinajs.cn/newchart/daily/n/sh000001.gif "上证指数日K，描述走势"
"""
import sys
import io
import os
import base64
import json
import urllib.request
from urllib.parse import urlparse

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# ---------- 读取 API Key ----------
def load_api_key():
    """从 .env 或环境变量读取 ZHIPU_API_KEY"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '.env')
    if os.path.exists(env_path):
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('ZHIPU_API_KEY='):
                    return line.split('=', 1)[1].strip()
    return os.environ.get('ZHIPU_API_KEY', '')

API_KEY = load_api_key()
API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MODEL = "glm-4v-flash"  # 免费视觉模型（实测可用）

def is_url(s):
    return urlparse(s).scheme in ('http', 'https')

def load_image_as_base64(source):
    """支持本地文件或 URL，返回 data URI"""
    if is_url(source):
        req = urllib.request.Request(source, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = resp.read()
    else:
        with open(source, 'rb') as f:
            data = f.read()

    # 自动判断 mime
    ext = os.path.splitext(source if not is_url(source) else source.split('?')[0])[1].lower()
    mime_map = {'.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.webp': 'image/webp', '.bmp': 'image/bmp'}
    mime = mime_map.get(ext, 'image/jpeg')

    if len(data) > 10 * 1024 * 1024:
        print("⚠️ 图片超过 10MB，GLM 会拒绝。建议压缩后重试。")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"

def analyze_image(source, prompt):
    if not API_KEY:
        print("❌ 未找到 ZHIPU_API_KEY。请在 D:/develop/industry-radar/.env 中配置。")
        sys.exit(1)

    image_data = load_image_as_base64(source)
    payload = {
        "model": MODEL,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": image_data}},
                {"type": "text", "text": prompt}
            ]
        }],
        "temperature": 0.3
    }

    req = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode(),
        headers={
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {API_KEY}'
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
            content = result['choices'][0]['message']['content']
            return content
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        err_map = {
            401: "API Key 无效——请检查 .env 里的 key 是否完整、有无空格",
            429: "请求太频繁（免费版限 1 并发）——稍等几秒重试",
            400: "模型名或参数有误",
            404: "接口地址错误",
        }
        print(f"❌ HTTP {e.code}: {err_map.get(e.code, '未知错误')}")
        print(f"   响应: {body[:200]}")
        sys.exit(1)

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    source = sys.argv[1]
    prompt = sys.argv[2] if len(sys.argv) > 2 else "请详细描述这张图片的内容，如果是K线图请分析技术形态"

    print(f"🖼️  分析图片: {source}")
    print(f"🤖 模型: {MODEL}")
    print(f"📝 提示词: {prompt}\n")

    result = analyze_image(source, prompt)
    print("=" * 50)
    print(result)
    print("=" * 50)

if __name__ == '__main__':
    main()
