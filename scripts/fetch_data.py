#!/usr/bin/env python3
"""抓取每日 A 股收盘数据 → data/raw/YYYY-MM-DD.json
数据源：AkShare（东方财富）。
用法:
  python scripts/fetch_data.py             # 全量抓取（指数/涨跌停/板块/涨停梯队/炸板/龙虎榜）
  python scripts/fetch_data.py --lhb-only  # 仅补抓龙虎榜并合并（盘后 18:30 用）
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import akshare as ak

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")
DATE_EM = datetime.now().strftime("%Y%m%d")  # 东财接口格式 YYYYMMDD


def safe(name, fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001
        print(f"[warn] {name} 抓取失败: {e}")
        return None


def fetch_indices():
    """沪深重要指数实时行情"""
    df = ak.stock_zh_index_spot_em(symbol="沪深重要指数")
    targets = {
        "000001": "上证指数", "399001": "深证成指", "399006": "创业板指",
        "000688": "科创50", "000300": "沪深300",
    }
    out = []
    for code, name in targets.items():
        row = df[df["代码"] == code]
        if not row.empty:
            r = row.iloc[0]
            out.append({
                "code": code, "name": name,
                "value": float(r["最新价"]),
                "change_pct": float(r["涨跌幅"]),
                "amount_yi": float(r["成交额"]) / 1e8,
            })
    turnover = sum(x["amount_yi"] for x in out if x["code"] in ("000001", "399001"))
    return {"indices": out, "turnover_yi": round(turnover, 0)}


def fetch_market_stats():
    """涨跌家数、涨停/跌停（乐咕乐股·赚钱效应）"""
    df = ak.stock_market_activity_legu()
    r = df.iloc[0]
    return {
        "advancers": int(r["上涨"]), "decliners": int(r["下跌"]),
        "flat": int(r["平盘"]), "limit_up": int(r["涨停"]),
        "limit_down": int(r["跌停"]),
    }


def fetch_hot_sectors():
    """行业资金流 TOP5（今日主力净流入）"""
    df = ak.stock_sector_fund_flow_rank(indicator="今日", sector_type="行业资金流")
    out = []
    for _, r in df.head(5).iterrows():
        out.append({
            "name": str(r["名称"]),
            "change_pct": float(r["今日涨跌幅"]),
            "main_net_inflow_yi": round(float(r["主力净流入-净额"]) / 1e8, 2),
        })
    return out


def fetch_limit_up():
    """涨停股池 → 涨停梯队（按连板数分组）"""
    df = ak.stock_zt_pool_em(date=TODAY)
    top = []
    ladders = {}
    for _, r in df.iterrows():
        item = {"name": str(r["名称"]), "code": str(r["代码"]),
                "consecutive": int(r["连板数"])}
        top.append(item)
        key = f"{int(r['连板数'])}板"
        ladders.setdefault(key, []).append(item["name"])
    top.sort(key=lambda x: x["consecutive"], reverse=True)
    max_board = max((x["consecutive"] for x in top), default=0)
    return {
        "top10": top[:10],
        "max_board": max_board,   # 最高板（空间板）
        "ladders": {k: v for k, v in sorted(
            ladders.items(), key=lambda kv: int(kv[0].replace("板", "")), reverse=True)},
    }


def fetch_zt_pool_zbgc():
    """炸板股池 → 炸板家数"""
    df = ak.stock_zt_pool_zbgc_em(date=TODAY)
    return {
        "count": len(df),
        "top": [{"name": str(r["名称"]), "code": str(r["代码"])}
                for _, r in df.head(5).iterrows()],
    }


def fetch_lhb():
    """龙虎榜详情（东方财富，当日盘后 18:00 后才有数据）"""
    df = ak.stock_lhb_detail_em(start_date=DATE_EM, end_date=DATE_EM)
    out = []
    for _, r in df.head(10).iterrows():
        out.append({
            "name": str(r["名称"]), "code": str(r["代码"]),
            "close_pct": float(r["涨跌幅"]),
            "net_buy_yi": round(float(r["龙虎榜净买额"]) / 1e8, 2),
            "reason": str(r["解读"]),
        })
    return {"count": len(df), "top10": out}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--lhb-only", action="store_true", help="仅补抓龙虎榜合并进当日 raw")
    args = parser.parse_args()

    raw_path = RAW_DIR / f"{TODAY}.json"

    # —— 龙虎榜补抓模式 ——
    if args.lhb_only:
        if not raw_path.exists():
            print("当日 raw 不存在，无法合并龙虎榜。")
            return 1
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
        lhb = safe("龙虎榜", fetch_lhb)
        if not lhb or not lhb.get("top10"):
            print("龙虎榜暂未更新（通常 18:00 后披露），本次跳过。")
            return 0
        payload["lhb"] = lhb
        payload["lhb_fetched_at"] = datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00")
        raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print("龙虎榜已合并。")
        return 0

    # —— 全量抓取模式 ——
    print(f"开始抓取 {TODAY} 数据…")
    indices_data = safe("指数", fetch_indices)
    stats = safe("涨跌统计", fetch_market_stats)
    sectors = safe("板块资金流", fetch_hot_sectors)
    zt = safe("涨停梯队", fetch_limit_up)
    zbgc = safe("炸板", fetch_zt_pool_zbgc)
    lhb = safe("龙虎榜", fetch_lhb)

    if not indices_data or not indices_data["indices"]:
        print("今日指数为空（可能休市），跳过写入。")
        return 0

    # 炸板率 = 炸板数 / (涨停数 + 炸板数)
    broken_rate = None
    if stats and zbgc and stats.get("limit_up") is not None:
        denom = stats["limit_up"] + zbgc.get("count", 0)
        if denom > 0:
            broken_rate = round(zbgc["count"] / denom * 100, 1)

    payload = {
        "date": TODAY,
        "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "indices": indices_data["indices"],
        "turnover_yi": indices_data["turnover_yi"],
        "stats": stats or {},
        "broken_rate": broken_rate,
        "hot_sectors": sectors or [],
        "limit_up_ladder": zt or {},
        "broken_board": zbgc or {},
        "lhb": lhb or {},
    }
    raw_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {raw_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
