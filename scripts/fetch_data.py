#!/usr/bin/env python3
"""抓取每日 A 股收盘数据 → data/raw/YYYY-MM-DD.json
数据源：AkShare（东方财富 / 新浪备用），带重试和多源回退。
用法:
  python scripts/fetch_data.py             # 全量抓取
  python scripts/fetch_data.py --lhb-only  # 仅补抓龙虎榜并合并
"""
import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import akshare as ak

BASE = Path(__file__).resolve().parent.parent
RAW_DIR = BASE / "data" / "raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)
TODAY = datetime.now().strftime("%Y-%m-%d")
DATE_EM = datetime.now().strftime("%Y%m%d")   # 东财接口需要 YYYYMMDD


def safe(name, fn, retries=3, delay=3):
    """带重试的抓取包装"""
    for attempt in range(1, retries + 1):
        try:
            return fn()
        except Exception as e:
            print(f"[warn] {name} 第 {attempt}/{retries} 次失败: {e}")
            if attempt < retries:
                time.sleep(delay)
    return None


def fetch_indices():
    """沪深重要指数：优先东财，失败回退新浪"""
    try:
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
    except Exception as e:
        print(f"[info] 东财指数失败({e})，改用新浪备用源…")
        df = ak.stock_zh_index_spot_sina()
        targets = {
            "sh000001": "上证指数", "sz399001": "深证成指",
            "sz399006": "创业板指", "sh000688": "科创50", "sh000300": "沪深300",
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
                })
        return {"indices": out, "turnover_yi": None}


def fetch_market_stats():
    """涨跌家数、涨停/跌停（乐咕乐股·赚钱效应）——列名容错"""
    df = ak.stock_market_activity_legu()
    if df is None or df.empty:
        raise ValueError("返回为空")
    r = df.iloc[0]

    def get_num(*names):
        for n in names:
            if n in r.index:
                try:
                    return int(r[n])
                except Exception:
                    pass
        return None

    return {
        "advancers": get_num("上涨", "上涨家数"),
        "decliners": get_num("下跌", "下跌家数"),
        "flat": get_num("平盘", "平盘家数"),
        "limit_up": get_num("涨停", "涨停家数"),
        "limit_down": get_num("跌停", "跌停家数"),
    }


def fetch_hot_sectors():
    """行业资金流 TOP5（东财，失败返回空列表）"""
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
    """涨停股池 → 涨停梯队（日期用 YYYYMMDD）"""
    df = ak.stock_zt_pool_em(date=DATE_EM)
    top, ladders = [], {}
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
        "max_board": max_board,
        "ladders": {k: v for k, v in sorted(
            ladders.items(), key=lambda kv: int(kv[0].replace("板", "")), reverse=True)},
    }


def fetch_zt_pool_zbgc():
    """炸板股池（日期用 YYYYMMDD）"""
    df = ak.stock_zt_pool_zbgc_em(date=DATE_EM)
    return {
        "count": len(df),
        "top": [{"name": str(r["名称"]), "code": str(r["代码"])}
                for _, r in df.head(5).iterrows()],
    }


def fetch_lhb():
    """龙虎榜详情（东财，18:00 后披露）"""
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


def is_trading_day(date_str):
    """用新浪交易日历判断是否为 A 股交易日"""
    try:
        df = ak.tool_trade_date_hist_sina()
        days = {str(d) for d in df["trade_date"].astype(str)}
        return date_str in days
    except Exception as e:
        print(f"[warn] 交易日历获取失败，按交易日处理: {e}")
        return True


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
    if not is_trading_day(TODAY):
        print(f"{TODAY} 非 A 股交易日，跳过抓取。")
        return 0

    print(f"开始抓取 {TODAY} 数据…")
    indices_data = safe("指数", fetch_indices)
    stats = safe("涨跌统计", fetch_market_stats)
    sectors = safe("板块资金流", fetch_hot_sectors)
    zt = safe("涨停梯队", fetch_limit_up)
    zbgc = safe("炸板", fetch_zt_pool_zbgc)
    lhb = safe("龙虎榜", fetch_lhb)

    if not indices_data or not indices_data.get("indices"):
        print("指数抓取失败（可能网络被屏蔽），今日不写入。")
        return 1

    broken_rate = None
    if stats and zbgc and stats.get("limit_up") is not None:
        denom = stats["limit_up"] + zbgc.get("count", 0)
        if denom > 0:
            broken_rate = round(zbgc["count"] / denom * 100, 1)

    payload = {
        "date": TODAY,
        "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S+08:00"),
        "indices": indices_data["indices"],
        "turnover_yi": indices_data.get("turnover_yi"),
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