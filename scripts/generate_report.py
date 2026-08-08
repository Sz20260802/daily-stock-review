#!/usr/bin/env python3
"""根据 raw 数据生成复盘 JSON → data/reviews/{date}.json，并更新 latest.json / index.json
可选功能：
  - DEEPSEEK_API_KEY 环境变量存在时，自动调用 DeepSeek 生成"今日小结"
  - REVIEW_PROMPT    环境变量可覆盖默认分析 Prompt（自定义个人思维模式，换行用 \n）
用法:
  python scripts/generate_report.py           # 生成/覆盖当日复盘
  python scripts/generate_report.py --merge   # 合并模式：保留已有主题/事件，只更新 market
"""
import argparse
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

DEFAULT_PROMPT = """你是一名有 10 年经验的 A 股复盘分析师，风格克制、客观、数据驱动。
以下是 {date} 的 A 股收盘数据（JSON）：
{data}

请严格按以下框架输出一段 120~180 字的当日复盘（一段话，不要列点，不要提"根据AI分析"）：
1. 指数与量能：三大指数表现、成交额是放量还是缩量（无前值则只描述现状）；
2. 情绪温度：涨停家数、炸板率高低、最高连板说明市场情绪处于冰点/修复/亢奋哪一档；
3. 资金主线：从板块资金流入和涨停梯队归纳当日最强方向；
4. 风险信号：跌停、高炸板率、指数背离、高位股分歧等值得警惕的迹象；
5. 明日关注：给 1~2 个基于数据可推演的验证点，不凭空预测。

硬性要求：
- 只基于上面给定数据说话，数据里没有的一律不写，不确定就写"数据不足"；
- 区分"事实"与"推断"，推断句必须用"或/可能"等词；
- 禁止编造任何数字、个股、消息；
- 语气专业、不夸大、不喊单，结尾不喊口号。"""


def build_prompt(market: dict) -> str:
    prompt = os.environ.get("REVIEW_PROMPT", "").strip().replace("\\n", "\n")
    if not prompt:
        prompt = DEFAULT_PROMPT
    return prompt.format(date=TODAY, data=json.dumps(market, ensure_ascii=False))


def llm_summary(market: dict, api_key: str) -> str:
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": build_prompt(market)}],
        "temperature": 0.4,   # 复盘要稳，温度调低减少发散
        "max_tokens": 400,
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.deepseek.com/chat/completions",
        data=body,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] LLM 总结失败: {e}")
        return ""


def build_market(raw: dict) -> dict:
    return {
        "generated_at": raw.get("fetched_at", ""),
        "indices": raw.get("indices", []),
        "stats": raw.get("stats", {}),
        "turnover_yi": raw.get("turnover_yi"),
        "broken_rate": raw.get("broken_rate"),
        "hot_sectors": raw.get("hot_sectors", []),
        "limit_up_ladder": raw.get("limit_up_ladder", {}),
        "broken_board": raw.get("broken_board", {}),
        "lhb": raw.get("lhb", {}),
        "summary": "",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--merge", action="store_true",
                        help="合并模式：保留已有主题/事件等内容，只更新 market")
    args = parser.parse_args()

    raw_path = RAW_DIR / f"{TODAY}.json"
    if not raw_path.exists():
        print("今日原始数据不存在（非交易日或抓取跳过），退出。")
        return 0
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if not raw.get("indices"):
        print("今日指数为空，退出。")
        return 0

    out_path = REVIEW_DIR / f"{TODAY}.json"
    prev = {}
    if args.merge and out_path.exists():
        prev = json.loads(out_path.read_text(encoding="utf-8"))
        print("合并模式：保留已有主题/事件/关联/洞察。")

    market = build_market(raw)
    # 已有小结则保留，避免重复调用 LLM
    if prev.get("market", {}).get("summary"):
        market["summary"] = prev["market"]["summary"]

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if api_key and not market["summary"]:
        market["summary"] = llm_summary(market, api_key)

    review = {
        "meta": {
            "date": TODAY,
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "github-actions",
        },
        "market": market,
        "themes": prev.get("themes", []),
        "calendar_events": prev.get("calendar_events", []),
        "correlations": prev.get("correlations", []),
        "insights": prev.get("insights", []),
    }

    out_path.write_text(json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")
    (REVIEW_DIR / "latest.json").write_text(
        json.dumps(review, ensure_ascii=False, indent=2), encoding="utf-8")

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

    print(f"已生成复盘 {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
