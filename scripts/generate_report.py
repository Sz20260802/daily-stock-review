#!/usr/bin/env python3
"""根据 raw 数据生成复盘 JSON → data/reviews/{date}.json，并更新 latest.json / index.json
可选：设置环境变量 DEEPSEEK_API_KEY 时，自动调用 DeepSeek 生成"今日小结"。
"""
import json
import os
import sys
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
REVIEW_DIR = BASE / "data" / "reviews"
REVIEW_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")


def llm_summary(market, api_key):
    """调用 DeepSeek 生成 100 字以内的市场小结"""
    prompt = (
        f"今天是 {TODAY}，以下是 A 股收盘数据：{json.dumps(market, ensure_ascii=False)}。"
        "请用 100 字以内概括当日市场表现，点出资金主线与主要风险，语气专业简洁。"
    )
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.6,
        "max_tokens": 200,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] LLM 总结失败: {e}")
        return ""


def main():
    raw_path = RAW_DIR / f"{TODAY}.json"
    if not raw_path.exists():
        print("今日原始数据不存在（非交易日或抓取跳过），退出。")
        return 0
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if not raw.get("indices"):
        print("今日指数为空，退出。")
        return 0

    market = {
        "generated_at": raw.get("fetched_at", ""),
        "indices": raw.get("indices", []),
        "stats": raw.get("stats", {}),
        "turnover_yi": raw.get("turnover_yi"),
        "hot_sectors": raw.get("hot_sectors", []),
        "limit_up_top": raw.get("limit_up_top", []),
        "summary": "",
    }

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if api_key:
        market["summary"] = llm_summary(market, api_key)

    # 尝试继承上一日的主题/事件/关联/洞察框架
    # ⚠️ 注意：themes / calendar_events / correlations / insights 属于研报级内容，
    #    不会随行情数据自动更新。建议定期手动维护，或接入 LLM 自动分析研报生成。
    prev = None
    latest_path = REVIEW_DIR / "latest.json"
    if latest_path.exists():
        prev = json.loads(latest_path.read_text(encoding="utf-8"))
        print("[info] 已继承上一日研报框架，请定期人工更新主题与事件内容。")

    review = {
        "meta": {
            "date": TODAY,
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "github-actions",
        },
        "market": market,
        "themes": (prev or {}).get("themes", []),
        "calendar_events": (prev or {}).get("calendar_events", []),
        "correlations": (prev or {}).get("correlations", []),
        "insights": (prev or {}).get("insights", []),
    }

    out = REVIEW_DIR / f"{TODAY}.json"
    out.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    (REVIEW_DIR / "latest.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

    # 更新历史索引
    index_path = REVIEW_DIR / "index.json"
    dates = []
    if index_path.exists():
        dates = json.loads(index_path.read_text(encoding="utf-8")).get("dates", [])
    if TODAY not in dates:
        dates.append(TODAY)
        dates.sort()
    index_path.write_text(
        json.dumps({"dates": dates, "latest": TODAY}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"已生成复盘 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
