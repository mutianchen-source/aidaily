#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 资讯日报 · 数据生成脚本（v3 · 大模型智能整理版）

流程：
  1. 从 10 个权威媒体 RSS 抓取全网新闻素材（标题/链接/摘要/来源）；
  2. 交给 DeepSeek 大模型：筛选 AI 相关、分到 6 大板块、提炼一句话摘要；
  3. 生成 data/news.json，供 index.html 前端加载。

运行方式：
  python3 generate.py
定时运行（每天 08:00）：
  由 launchd 配置触发（见 com.user.aidaily.refresh.plist）。
"""

import json
import re
import ssl
import html
import os
import email.utils
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone


def _ssl_context():
    """构造可用的 SSL 上下文：优先系统证书，最后回退未验证（兼容 macOS / Linux）。"""
    candidates = [
        "/etc/ssl/cert.pem",                      # macOS
        "/etc/ssl/certs/ca-certificates.crt",     # Ubuntu / Debian
        "/etc/pki/tls/certs/ca-bundle.crt",       # CentOS / RHEL
    ]
    for cafile in candidates:
        if os.path.exists(cafile):
            try:
                return ssl.create_default_context(cafile=cafile)
            except Exception:
                continue
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl._create_unverified_context()


try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone.utc

BASE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(BASE, "data", "news.json")
OUT_JS = os.path.join(BASE, "data", "news.js")
CONFIG_PATH = os.path.join(BASE, "config.json")

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"

# 权威 RSS 源（可自行增删）
FEEDS = [
    {"name": "极客公园", "url": "https://www.geekpark.net/rss"},
    {"name": "IT之家", "url": "https://www.ithome.com/rss/"},
    {"name": "游戏陀螺", "url": "https://www.youxituoluo.com/feed"},
    {"name": "36氪快讯", "url": "https://rsshub.rssforever.com/36kr/newsflashes"},
    {"name": "爱范儿", "url": "https://www.ifanr.com/feed"},
    {"name": "雷科技", "url": "https://www.leiphone.com/feed"},
    {"name": "少数派", "url": "https://sspai.com/feed"},
    {"name": "掘金", "url": "https://juejin.cn/rss"},
]

CATEGORIES = ["硬件与芯片", "模型与产品", "游戏AI", "机器人具身智能", "行业政策", "资本与市场"]

# 关键词兜底分类规则（大模型漏掉某板块时，用这个从素材里补足）
CATEGORY_RULES = [
    ("游戏AI", ["游戏", "电竞", "Game", "NPC", "版号", "主机", "手游", "游戏机", "米哈游", "任天堂", "PlayStation", "Xbox", "Steam", "伽马数据", "电竞"]),
    ("机器人具身智能", ["机器人", "具身智能", "人形", "仿生", "无人", "自动驾驶", "物理 AI", "机械臂", "Figure", "Optimus", "宇树", "智元"]),
    ("行业政策", ["政策", "监管", "法规", "治理", "标准", "合规", "公约", "网信", "工信", "条例", "立法", "版权", "反垄断", "数据安全", "伦理", "算力网", "行动计划"]),
    ("硬件与芯片", ["芯片", "GPU", "英伟达", "NVIDIA", "算力", "处理器", "制程", "CPU", "半导体", "服务器", "存储", "HBM", "封装", "晶圆", "光刻", "内存", "硬盘", "AMD", "英特尔", "台积电", "骁龙", "天玑", "麒麟", "显卡", "量子"]),
    ("模型与产品", ["大模型", "模型", "GPT", "Claude", "Gemini", "文心", "豆包", "通义", "Kimi", "DeepSeek", "Agent", "智能体", "AI 助手", "AI助手", "开源模型", "LLM", "AIGC", "ChatGPT", "Copilot", "Sora", "语音助手", "面壁", "智谱", "GLM", "MiniCPM"]),
    ("资本与市场", ["融资", "估值", "上市", "财报", "股价", "收购", "并购", "IPO", "投资", "亿美元", "亿元", "市值", "股东", "基金", "债券", "营收", "净利"]),
]

MAX_PER_CATEGORY = 18
BATCH_SIZE = 200

SYSTEM_PROMPT = (
    "你是 AI 资讯日报主编。用户会给你一组新闻素材，每行一条，格式：序号. 标题 | 来源。\n"
    "你的任务：\n"
    "1. 只保留与「人工智能/AI、大模型、芯片、半导体、算力、机器人、具身智能、游戏科技、"
    "AI 政策监管、AI 融资/资本市场」相关的新闻；无关的（普通汽车、地产、消费、社会新闻等）直接丢弃。\n"
    "2. 把保留的新闻分到 6 个板块之一：硬件与芯片 / 模型与产品 / 游戏AI / 机器人具身智能 / 行业政策 / 资本与市场。\n"
    "3. 为每条写两个字段：summary（40 字以内的一句话，用于列表卡片）和 detail（2-3 句、120 字以内的展开说明，用于详情页，不要罗列全文）。\n"
    "4. 尽量保证 6 个板块都有内容，每个板块保留 3~6 条。\n"
    "5. 交叉验证：多个来源常会报道同一事件，但标题措辞不同（例如「苹果发布新款 Mac mini」可能被极客公园写成「Mac mini M6 发布」、爱范儿写成「新款 Mac mini 发布价格大涨」、少数派写成「Apple 发布新款 Mac mini」）。请识别这类同主题的多源报道：保留其中最完整的一条，必须把 hot 设为 true，并在 detail 末尾补一句「该事件获多个来源交叉报道」；仅单一来源的普通新闻 hot 设为 false。\n"
    "只输出一个 JSON 数组，每个元素格式：{\"category\":\"板块名\",\"id\":序号,\"summary\":\"一句话\",\"detail\":\"展开说明\",\"hot\":true或false}。\n"
    "不要输出任何解释、前后缀或 markdown 代码块。"
)


def load_config():
    env_key = os.environ.get("DEEPSEEK_API_KEY")
    if env_key:
        return {
            "api_key": env_key,
            "base_url": os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.environ.get("DEEPSEEK_MODEL", "deepseek-chat"),
        }
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=12, context=_ssl_context()) as r:
        return r.read().decode("utf-8", errors="ignore")


def clean(text):
    if not text:
        return ""
    text = re.sub(r"<script[\s\S]*?</script>", " ", text)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def truncate(text, limit=140):
    if not text:
        return ""
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def classify(text):
    blob = (text or "").lower()
    for cat, kws in CATEGORY_RULES:
        if any(k.lower() in blob for k in kws):
            return cat
    return None


def parse_pubdate(raw):
    """解析 RSS/Atom 的发布时间，返回 naive datetime 或 None。"""
    if not raw:
        return None
    try:
        dt = email.utils.parsedate_to_datetime(raw)
        if dt:
            return dt.replace(tzinfo=None)
    except (TypeError, ValueError):
        pass
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})[T\s]?(\d{2})?:?(\d{2})?", raw)
    if m:
        try:
            hh = int(m.group(4) or 0)
            mm = int(m.group(5) or 0)
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), hh, mm)
        except ValueError:
            pass
    return None


def parse_feed(xml_text):
    items = []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return items
    nodes = root.findall(".//item") or root.findall(".//{http://www.w3.org/2005/Atom}entry")
    for node in nodes:
        title = clean(node.findtext("title") or node.findtext("{http://www.w3.org/2005/Atom}title"))
        link = node.findtext("link") or node.findtext("{http://www.w3.org/2005/Atom}link")
        desc = clean(node.findtext("description") or node.findtext("{http://www.w3.org/2005/Atom}summary"))
        date = (node.findtext("pubDate")
                or node.findtext("{http://www.w3.org/2005/Atom}updated")
                or node.findtext("{http://www.w3.org/2005/Atom}published"))
        if not title:
            continue
        items.append({"title": title, "link": link, "summary": desc, "date": date})
    return items


def chat(messages, max_tokens=4000):
    cfg = load_config()
    body = {
        "model": cfg["model"],
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0,
    }
    req = urllib.request.Request(
        cfg["base_url"].rstrip("/") + "/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + cfg["api_key"], "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120, context=_ssl_context()) as r:
        data = json.loads(r.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"]


def parse_json_array(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start = text.find("[")
    end = text.rfind("]")
    if start != -1 and end != -1:
        text = text[start:end + 1]
    return json.loads(text)


def run():
    now = datetime.now(TZ)
    now_naive = now.replace(tzinfo=None)
    today = now.strftime("%Y-%m-%d")
    today_mmdd = now.strftime("%m-%d")

    # 1) 抓取 RSS 素材
    seen = set()
    items = []
    for feed in FEEDS:
        try:
            entries = parse_feed(fetch(feed["url"]))
        except Exception as e:
            print("[RSS] {} 抓取失败: {}".format(feed["name"], e))
            continue
        added = 0
        stale = 0
        for it in entries:
            key = it["title"].strip()
            if not key or key in seen:
                continue
            # 过滤"汇总式"标题（用分号/竖线塞多条新闻的，如"XX；YY；ZZ"）
            if "；" in key or "｜" in key:
                continue
            # 过滤旧新闻（发布时间超过 2 天的丢弃）
            pub = parse_pubdate(it.get("date"))
            if pub and (now_naive - pub).days > 2:
                stale += 1
                continue
            seen.add(key)
            items.append({"title": key, "link": it["link"], "summary": it["summary"], "source": feed["name"]})
            added += 1
        print("[RSS] {} -> {} 条（去重后 {}，过滤旧闻 {}）".format(feed["name"], len(entries), added, stale))

    if not items:
        print("没有抓到任何素材。")
        return None

    # 2) 交给 DeepSeek 智能筛选 + 分类 + 摘要
    picked = {}
    for i in range(0, len(items), BATCH_SIZE):
        batch = items[i:i + BATCH_SIZE]
        lines = ["{}. {} | {}".format(i + idx + 1, it["title"], it["source"])
                 for idx, it in enumerate(batch)]
        user = "\n".join(lines)
        print("[LLM] 处理素材 {} - {} 条...".format(i + 1, i + len(batch)))
        try:
            content = chat([
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user},
            ])
            result = parse_json_array(content)
        except Exception as e:
            print("[LLM] 处理失败: {}".format(e))
            continue
        for r in result:
            try:
                rid = int(r.get("id"))
                cat = r.get("category")
                if cat not in CATEGORIES:
                    continue
                picked[rid] = {
                    "category": cat,
                    "summary": truncate(r.get("summary", ""), 120),
                    "detail": truncate(r.get("detail", ""), 160),
                    "hot": bool(r.get("hot", False)),
                }
            except (TypeError, ValueError):
                continue
        print("[LLM] 本轮保留 {} 条".format(len(result)))

    # 3) 组装最终数据（大模型结果为主，关键词规则兜底）
    bucket = {}
    used = set()
    for rid, info in picked.items():
        it = items[rid - 1]
        bucket.setdefault(info["category"], []).append({
            "category": info["category"],
            "title": it["title"],
            "summary": info["summary"] or truncate(it["summary"], 80),
            "detail": info.get("detail") or truncate(it["summary"], 160),
            "source": it["source"],
            "date": today_mmdd,
            "url": it["link"] or "",
            "hot": info.get("hot", False),
        })
        used.add(rid)

    # 某板块不足时，用关键词分类的素材补齐（只补关键词命中、疑似 AI 相关的）
    for rid, it in enumerate(items, 1):
        if rid in used:
            continue
        cat = classify(it["title"] + " " + it["summary"])
        if not cat or cat not in CATEGORIES:
            continue
        if len(bucket.get(cat, [])) >= MAX_PER_CATEGORY:
            continue
        bucket.setdefault(cat, []).append({
            "category": cat,
            "title": it["title"],
            "summary": truncate(it["summary"], 80),
            "detail": truncate(it["summary"], 160),
            "source": it["source"],
            "date": today_mmdd,
            "url": it["link"] or "",
            "hot": False,
        })
        used.add(rid)

    # 每板块内：多源交叉验证（hot）的排前面，再截断
    final = []
    for cat in CATEGORIES:
        cat_items = bucket.get(cat, [])
        cat_items.sort(key=lambda n: 0 if n.get("hot") else 1)
        for n in cat_items[:MAX_PER_CATEGORY]:
            final.append(n)

    data = {
        "date": today,
        "updatedAt": now.strftime("%Y-%m-%d %H:%M"),
        "news": final,
    }

    from collections import Counter
    dist = Counter(n["category"] for n in final)
    print("\n已生成 {} 共 {} 条".format(today, len(final)))
    for c in CATEGORIES:
        print("  {}: {}".format(c, dist.get(c, 0)))

    return data


def write_outputs(data):
    """把数据写到 news.json / news.js。"""
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    with open(OUT_JS, "w", encoding="utf-8") as f:
        f.write("window.__NEWS__ = " + json.dumps(data, ensure_ascii=False) + ";\n")


def ask(question, news):
    """聊天助手：基于当天新闻回答用户问题（key 只在后端，不暴露前端）。"""
    lines = ["【{}】{}：{}".format(n.get("category", ""), n.get("title", ""), n.get("summary", "")) for n in news]
    system = (
        "你是「智识资讯」的智能助手。以下是当天收录的新闻：\n"
        + "\n".join(lines)
        + "\n\n请基于以上新闻回答用户问题，用中文，简洁明了；若问题与新闻无关可一般性回答。"
    )
    return chat([
        {"role": "system", "content": system},
        {"role": "user", "content": question},
    ], max_tokens=900)


def main():
    data = run()
    if data:
        write_outputs(data)


if __name__ == "__main__":
    main()
