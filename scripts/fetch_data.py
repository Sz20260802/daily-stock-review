#!/usr/bin/env python3
"""抓取每日 A 股收盘数据 → data/raw/YYYY-MM-DD.json
数据源：AkShare（东方财富）。每个接口单独容错，单点失败不影响整体。
"""
import json
import sys
from datetime import datetime
from pathlib import Path

import akshare as ak

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")


def safe(name, fn):
    try:
        result = fn()
        if result is None or (hasattr(result, "empty") and result.empty):
            print(f"[warn] {name} 返回空数据（可能休市或接口变更）")
            return None
        return result
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
                "amount_yi": float(r["成交额"]) / 1e8,  # 元 → 亿
            })
    # 两市总成交额 = 上证 + 深证 + 北交所（如有）
    turnover = sum(x["amount_yi"] for x in out if x["code"] in ("000001", "399001"))
    # 尝试补充北交所成交额（若指数列表中包含）
    bjse = next((x for x in out if x["code"] == "899050"), None)
    if bjse:
        turnover += bjse["amount_yi"]
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
    """涨停股池（含连板数）"""
    df = ak.stock_zt_pool_em(date=TODAY)
    if df is None or df.empty:
        return []
    out = []
    for _, r in df.head(10).iterrows():
        out.append({
            "name": str(r.get("名称", "")), "code": str(r.get("代码", "")),
            "change_pct": float(r.get("涨跌幅", 0)),
            "consecutive": int(r.get("连板数", 0)),
        })
    return out


def main():
    print(f"开始抓取 {TODAY} 数据…")
    indices_data = safe("指数", fetch_indices)
    stats = safe("涨跌统计", fetch_market_stats)
    sectors = safe("板块资金流", fetch_hot_sectors)
    zt = safe("涨停池", fetch_limit_up)

    if not indices_data or not indices_data["indices"]:
        print("今日指数为空（可能休市），跳过写入。")
        return 0

    payload = {
        "date": TODAY,
        "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "indices": indices_data["indices"],
        "turnover_yi": indices_data["turnover_yi"],
        "stats": stats or {},
        "hot_sectors": sectors or [],
        "limit_up_top": zt or [],
    }
    out = RAW_DIR / f"{TODAY}.json"
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"已写入 {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
