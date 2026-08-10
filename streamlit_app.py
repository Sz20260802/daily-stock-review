import json
import requests
import streamlit as st

st.set_page_config(page_title="每日股票复盘报告", page_icon="📈", layout="wide")

# ============ 配置区：改成你自己的 GitHub 用户名 ============
GITHUB_USER = "Sz20260802"      # ← 改成你的用户名
REPO        = "stock-review-app"
BRANCH      = "main"
BASE = f"https://raw.githubusercontent.com/{GITHUB_USER}/{REPO}/{BRANCH}/data/reviews/"
# ===========================================================

CSS = """
<style>
body { font-family: "PingFang SC","Microsoft YaHei",sans-serif; background:#f4f6f9; }
.index-grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
.index-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:12px 16px; }
.name { color:#6b7280; font-size:13px; }
.value { font-size:22px; font-weight:700; }
.up { color:#dc2626; } .down { color:#16a34a; }
.chip { display:inline-block; padding:3px 10px; border-radius:999px; font-size:12px;
        background:#eef2ff; color:#3730a3; margin:2px 4px 2px 0; }
.theme-card { background:#fff; border:1px solid #e5e7eb; border-radius:14px; padding:18px; margin-bottom:14px; }
.theme-title { font-size:16px; font-weight:600; margin-bottom:6px; }
.tag { display:inline-block; background:#f3f4f6; border:1px solid #e5e7eb; color:#374151;
       border-radius:6px; padding:2px 8px; font-size:12px; margin-right:6px; }
.thesis { background:#f8fafc; border-left:3px solid #2563eb; padding:10px 12px; border-radius:8px; font-size:14px; }
table { width:100%; border-collapse:collapse; font-size:13px; background:#fff; }
th { background:#f1f5f9; text-align:left; padding:7px 10px; }
td { border-top:1px solid #e5e7eb; padding:7px 10px; }
.block { margin-top:10px; font-size:14px; color:#1f2937; white-space:pre-line; }
.label { font-weight:600; color:#475569; font-size:13px; }
.risk { background:#fef2f2; border:1px solid #fecaca; color:#991b1b; border-radius:8px; padding:8px 12px; font-size:13px; margin-top:8px; }
.falsify { background:#fffbeb; border:1px solid #fde68a; color:#92400e; border-radius:8px; padding:8px 12px; font-size:13px; margin-top:8px; }
.tl-item { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px; margin-bottom:10px; }
.corr-card { background:#fff; border:1px solid #e5e7eb; border-radius:12px; padding:14px; margin-bottom:10px; }
.insight-item { background:#fff; border:1px solid #e5e7eb; border-radius:10px; padding:12px 14px; margin-bottom:8px; }
</style>
"""

def esc(s):
    return str(s if s is not None else "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

@st.cache_data(ttl=600, show_spinner="加载数据…")
def get_json(path):
    r = requests.get(BASE + path, timeout=15)
    r.raise_for_status()
    return r.json()

def radar_svg(s):
    size, cx, cy, R = 170, 85, 85, 58
    labels = ["供需","估值","阶段"]
    vals = [s.get("supply_demand",0), s.get("valuation",0), s.get("stage",0)]
    angles = [-90, 30, 150]
    import math
    rad = [a*math.pi/180 for a in angles]
    svg = f'<svg viewBox="0 0 {size} {size}" style="max-width:200px">'
    for lv in [0.25,0.5,0.75,1]:
        pts = " ".join(f"{cx+R*lv*math.cos(a)},{cy+R*lv*math.sin(a)}" for a in rad)
        svg += f'<polygon points="{pts}" fill="none" stroke="#e5e7eb" stroke-width="1"/>'
    pts = " ".join(f"{cx+R*vals[i]/10*math.cos(rad[i])},{cy+R*vals[i]/10*math.sin(rad[i])}" for i in range(3))
    svg += f'<polygon points="{pts}" fill="rgba(59,130,246,.25)" stroke="#2563eb" stroke-width="2"/>'
    for i,a in enumerate(rad):
        vx,vy = cx+(R+8)*math.cos(a), cy+(R+8)*math.sin(a)
        lx,ly = cx+(R+24)*math.cos(a), cy+(R+24)*math.sin(a)
        svg += f'<circle cx="{vx}" cy="{vy}" r="3.5" fill="#2563eb"/>'
        svg += f'<text x="{vx}" y="{vy}" text-anchor="middle" dominant-baseline="middle" font-size="11" font-weight="700">{vals[i]}</text>'
        svg += f'<text x="{lx}" y="{ly}" text-anchor="middle" dominant-baseline="middle" font-size="12" fill="#475569">{labels[i]}</text>'
    return svg + "</svg>"

def render_market(m):
    html = f'<h3 style="margin-top:0">📊 市场总览</h3>'
    if not m or not m.get("indices"):
        return html + '<p style="color:#6b7280">本日暂无市场数据（等待自动任务生成）</p>'
    html += '<div class="index-grid">'
    for idx in m["indices"]:
        cls = "up" if idx.get("change_pct",0)>=0 else "down"
        sign = "+" if idx.get("change_pct",0)>=0 else ""
        html += (f'<div class="index-card"><div class="name">{esc(idx["name"])}</div>'
                 f'<div class="value">{idx.get("value","-")}</div>'
                 f'<span class="{cls}">{sign}{idx.get("change_pct","-")}%</span></div>')
    html += '</div>'
    stt = m.get("stats") or {}
    html += '<div style="margin-top:10px">'
    for label,key in [("涨停","limit_up"),("跌停","limit_down"),("上涨","advancers"),("下跌","decliners"),("平盘","flat")]:
        if stt.get(key) is not None:
            html += f'<span class="chip">{label} {stt[key]}</span>'
    if m.get("turnover_yi"):
        html += f'<span class="chip">两市成交 {m["turnover_yi"]} 亿</span>'
    if m.get("broken_rate") is not None:
        html += f'<span class="chip">炸板率 {m["broken_rate"]}%</span>'
    html += '</div>'
    if m.get("summary"):
        html += f'<div class="thesis" style="margin-top:10px"><span class="label">📝 今日小结（AI）</span><br>{esc(m["summary"])}</div>'
    return html

def render_ladder(m):
    html = '<h3>🎢 涨停梯队与龙虎榜</h3>'
    if not m: return html + '<p style="color:#6b7280">暂无数据</p>'
    ladder = m.get("limit_up_ladder") or {}
    zbgc = m.get("broken_board") or {}
    lhb = m.get("lhb") or {}
    top = ''
    if ladder.get("max_board"): top += f'<span class="chip">最高板：{ladder["max_board"]} 板</span>'
    if zbgc.get("count") is not None: top += f'<span class="chip">炸板：{zbgc["count"]} 家</span>'
    if top: html += f'<div>{top}</div>'
    if ladder.get("ladders"):
        html += '<div style="margin-top:8px"><span class="label">连板梯队</span><br>'
        for k,v in ladder["ladders"].items():
            html += f'<span class="chip" style="background:#1e3a8a;color:#fff">{esc(k)}</span> {esc("、".join(v))}<br>'
        html += '</div>'
    if lhb.get("top10"):
        html += '<div style="margin-top:8px"><span class="label">🐉 龙虎榜 TOP10</span></div>'
        html += '<table><tr><th>名称</th><th>涨跌幅</th><th>净买额(亿)</th><th>上榜原因</th></tr>'
        for r in lhb["top10"]:
            cls = "up" if r.get("close_pct",0)>=0 else "down"
            sign = "+" if r.get("close_pct",0)>=0 else ""
            html += (f'<tr><td>{esc(r.get("name",""))}</td>'
                     f'<td class="{cls}">{sign}{r.get("close_pct","-")}%</td>'
                     f'<td>{r.get("net_buy_yi","-")}</td>'
                     f'<td>{esc(r.get("reason",""))}</td></tr>')
        html += '</table>'
    else:
        html += '<p style="color:#6b7280">龙虎榜通常 18:00 后披露，当日晚间自动补抓。</p>'
    return html

def render_theme(t, i):
    h = t.get("header") or {}
    radar = t.get("radar_scores") or {}
    inst = t.get("institutions") or {}
    html = (f'<div class="theme-card"><div class="theme-title">#{h.get("index",i+1)} '
            f'{esc(h.get("title",t.get("title","")))} '
            f'<span class="chip" style="background:#2563eb;color:#fff">{esc(h.get("confidence",""))}</span></div>')
    if t.get("tags"):
        html += '<div>' + "".join(f'<span class="tag">{esc(x)}</span>' for x in t["tags"]) + '</div>'
    html += '<div style="display:flex;gap:16px;margin-top:10px;flex-wrap:wrap">'
    html += f'<div style="text-align:center">{radar_svg(radar)}<br>总分 {radar.get("total","-")} ｜ 平均 {radar.get("average","-")}</div>'
    html += '<div style="flex:1;min-width:280px">'
    html += f'<div class="thesis"><span class="label">🎯 核心观点</span><br>{esc(t.get("core_thesis",""))}</div>'
    if inst.get("count"):
        names = "、".join(f'{x.get("name","")}({x.get("report_id","")})' for x in (inst.get("list") or []))
        html += f'<div style="margin-top:8px"><span class="label">🏛 机构覆盖（{inst["count"]} 家）</span><br>{esc(names)}</div>'
    if t.get("evidence_table"):
        html += '<div style="margin-top:8px"><span class="label">📊 关键证据</span></div><table><tr><th>指标</th><th>数值</th><th>来源</th></tr>'
        for r in t["evidence_table"]:
            html += (f'<tr><td>{esc(r.get("indicator",""))}</td><td>{esc(r.get("value",""))}</td>'
                     f'<td>{esc(r.get("source_type",""))}</td></tr>')
        html += '</table>'
    if t.get("logic_chain"):
        html += f'<div class="block" style="margin-top:8px"><span class="label">🧩 逻辑链条</span><br>{esc(t["logic_chain"])}</div>'
    if t.get("risk_note"):
        html += f'<div class="risk">⚠️ 风险提示：{esc(t["risk_note"])}</div>'
    if t.get("falsifiability_threshold"):
        html += f'<div class="falsify">🔍 可证伪阈值：{esc(t["falsifiability_threshold"])}</div>'
    if t.get("related_events"):
        html += f'<div style="margin-top:8px;font-size:13px;color:#475569">📅 关联事件：{esc("；".join(t["related_events"]))}</div>'
    html += '</div></div></div>'
    return html

def render_calendar(evs):
    if not evs: return '<h3>📅 事件日历</h3><p style="color:#6b7280">暂无</p>'
    html = '<h3>📅 事件日历</h3>'
    for ev in evs:
        html += (f'<div class="tl-item"><b>{esc(ev.get("date",""))}</b>　{esc(ev.get("event_name",""))}<br>'
                 f'<span style="color:#475569;font-size:13px">影响：{esc(ev.get("impact",""))}</span>')
        if ev.get("data_verification_point"):
            html += f'<div class="falsify" style="margin-top:6px">✔ 验证点：{esc(ev["data_verification_point"])}</div>'
        html += '</div>'
    return html

def render_corr(cs):
    if not cs: return '<h3>🔗 跨主题关联图谱</h3><p style="color:#6b7280">暂无</p>'
    html = '<h3>🔗 跨主题关联图谱</h3>'
    for c in cs:
        html += (f'<div class="corr-card"><b>{esc(c.get("from",""))}</b> → <b>{esc(c.get("to",""))}</b> '
                 f'<span class="chip">{esc(c.get("relation",""))}</span><br>'
                 f'<span style="font-size:13px;color:#475569">{esc(c.get("evidence",""))}</span></div>')
    return html

def render_insights(its):
    if not its: return '<h3>💡 关键洞察</h3><p style="color:#6b7280">暂无</p>'
    html = '<h3>💡 关键洞察</h3>'
    for i,it in enumerate(its,1):
        if isinstance(it, str):
            html += f'<div class="insight-item"><b>{i}.</b> {esc(it)}</div>'
        else:
            html += f'<div class="insight-item"><b>{i}.</b> {esc(it.get("title",""))} —— {esc(it.get("detail",""))}</div>'
    return html

def main():
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        idx = get_json("index.json")
    except Exception:
        idx = {"dates": ["latest"], "latest": "latest"}

    dates = idx.get("dates", [])
    latest = idx.get("latest", "latest")
    date = st.selectbox("📅 选择复盘日期", options=["latest"] + dates,
                        format_func=lambda d: "最新（" + latest + "）" if d == "latest" else d)

    try:
        data = get_json("latest.json" if date == "latest" else f"{date}.json")
    except Exception as e:
        st.error(f"加载失败：{e}。请确认数据文件已生成并推送。")
        return

    meta = data.get("meta") or {}
    st.markdown(f"**复盘日期：{esc(meta.get('date',''))}** ｜ 生成时间：{esc(meta.get('generated_at',''))} ｜ 来源：{esc(meta.get('source',''))}")

    m = data.get("market") or {}
    st.markdown(render_market(m), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(render_ladder(m), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown('<h3>📂 主题复盘</h3>', unsafe_allow_html=True)
    for i,t in enumerate(data.get("themes") or []):
        st.markdown(render_theme(t,i), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(render_calendar(data.get("calendar_events") or []), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(render_corr(data.get("correlations") or []), unsafe_allow_html=True)
    st.markdown("---")
    st.markdown(render_insights(data.get("insights") or []), unsafe_allow_html=True)
    st.caption("⚠️ 本应用仅供学习研究，不构成任何投资建议。数据来源：东方财富等公开渠道。")

main()
