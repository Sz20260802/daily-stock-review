#!/usr/bin/env python3
"""根据 raw 数据生成复盘 JSON → data/reviews/{date}.json，并更新 latest.json / index.json
研究类内容（主题/事件/关联/洞察）自动继承自最近一份历史复盘（种子 8/7 含完整内容）。
用法:
  python scripts/generate_report.py                        # 生成今天
  python scripts/generate_report.py --date 2026-08-10      # 指定日期（补录）
  python scripts/generate_report.py --merge                # 仅更新 market，保留当天已有内容
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


def build_prompt(date_str, market):
    prompt = os.environ.get("REVIEW_PROMPT", "").strip().replace("\\n", "\n")
    if not prompt:
        prompt = DEFAULT_PROMPT
    return prompt.format(date=date_str, data=json.dumps(market, ensure_ascii=False))


def llm_summary(date_str, market, api_key):
    body = json.dumps({
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": build_prompt(date_str, market)}],
        "temperature": 0.4,
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
    except Exception as e:
        print(f"[warn] LLM 总结失败: {e}")
        return ""


def build_market(raw):
    """构造 market 数据；把 1558.0 这类整数浮点规范成 1558"""
    st = raw.get("stats") or {}
    stats = {}
    for k, v in st.items():
        if isinstance(v, float) and v.is_integer():
            stats[k] = int(v)
        else:
            stats[k] = v
    return {
        "generated_at": raw.get("fetched_at", ""),
        "indices": raw.get("indices", []),
        "stats": stats,
        "turnover_yi": raw.get("turnover_yi"),
        "broken_rate": raw.get("broken_rate"),
        "hot_sectors": raw.get("hot_sectors", []),
        "limit_up_ladder": raw.get("limit_up_ladder", {}),
        "broken_board": raw.get("broken_board", {}),
        "lhb": raw.get("lhb", {}),
        "summary": "",
    }


def find_prev_review(date_str):
    """找到日期严格早于 date_str 的最近一份复盘，用于继承研报内容"""
    candidates = []
    for p in REVIEW_DIR.glob("*.json"):
        name = p.stem
        if name in ("latest", "index"):
            continue
        try:
            datetime.strptime(name, "%Y-%m-%d")
        except ValueError:
            continue
        if name < date_str:
            candidates.append(name)
    if not candidates:
        return {}
    candidates.sort()
    try:
        return json.loads((REVIEW_DIR / f"{candidates[-1]}.json").read_text(encoding="utf-8"))
    except Exception:
        return {}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="日期 YYYY-MM-DD，默认今天")
    parser.add_argument("--merge", action="store_true", help="仅更新 market，保留当天已有内容")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")
    raw_path = RAW_DIR / f"{date_str}.json"
    if not raw_path.exists():
        print(f"{date_str} 原始数据不存在，先运行 fetch_data.py 或指定正确日期。")
        return 0
    raw = json.loads(raw_path.read_text(encoding="utf-8"))
    if not raw.get("indices"):
        print(f"{date_str} 指数为空，退出。")
        return 0

    out_path = REVIEW_DIR / f"{date_str}.json"
    prev = find_prev_review(date_str)
    if args.merge and out_path.exists():
        cur = json.loads(out_path.read_text(encoding="utf-8"))
        if cur.get("themes"):
            prev = cur
            print("合并模式：保留当天已有主题/事件/关联/洞察。")

    market = build_market(raw)
    if prev.get("market", {}).get("summary"):
        market["summary"] = prev["market"]["summary"]

    api_key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if api_key and not market["summary"]:
        market["summary"] = llm_summary(date_str, market, api_key)

    review = {
        "meta": {
            "date": date_str,
            "generated_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
            "source": "local-script",
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
    if date_str not in dates:
        dates.append(date_str)
        dates.sort()
    index_path.write_text(
        json.dumps({"dates": dates, "latest": date_str}, ensure_ascii=False, indent=2),
        encoding="utf-8")

    print(f"已生成复盘 {out_path}")
    print(f"继承内容: 主题{len(review['themes'])}个 / 事件{len(review['calendar_events'])}个 / "
          f"关联{len(review['correlations'])}组 / 洞察{len(review['insights'])}条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
