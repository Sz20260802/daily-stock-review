const REVIEWS_BASE = "data/reviews/";

async function loadJSON(url) {
  // 加时间戳避免 CDN/浏览器缓存旧数据
  const sep = url.includes("?") ? "&" : "?";
  const nocacheUrl = `${url}${sep}_t=${Date.now()}`;
  const resp = await fetch(nocacheUrl);
  if (!resp.ok) throw new Error(`HTTP ${resp.status}: ${url}`);
  return resp.json();
}

function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, c => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  }[c]));
}

/* ---------- 雷达图（SVG） ---------- */
function radarSVG(scores) {
  const size = 170, cx = 85, cy = 85, R = 58;
  const labels = ["供需", "估值", "阶段"];
  const vals = [scores.supply_demand ?? 0, scores.valuation ?? 0, scores.stage ?? 0];
  const angles = [-90, 30, 150].map(a => a * Math.PI / 180);
  let s = `<svg viewBox="0 0 ${size} ${size}" style="max-width:200px">`;
  [0.25, 0.5, 0.75, 1].forEach(lv => {
    const pts = angles.map(a => `${cx + R * lv * Math.cos(a)},${cy + R * lv * Math.sin(a)}`).join(" ");
    s += `<polygon points="${pts}" fill="none" stroke="#e5e7eb" stroke-width="1"/>`;
  });
  angles.forEach(a => {
    s += `<line x1="${cx}" y1="${cy}" x2="${cx + R * Math.cos(a)}" y2="${cy + R * Math.sin(a)}" stroke="#e5e7eb" stroke-width="1"/>`;
  });
  const pts = angles.map((a, i) => `${cx + R * vals[i] / 10 * Math.cos(a)},${cy + R * vals[i] / 10 * Math.sin(a)}`).join(" ");
  s += `<polygon points="${pts}" fill="rgba(59,130,246,.25)" stroke="#2563eb" stroke-width="2"/>`;
  angles.forEach((a, i) => {
    const vx = cx + (R + 8) * Math.cos(a), vy = cy + (R + 8) * Math.sin(a);
    const lx = cx + (R + 22) * Math.cos(a), ly = cy + (R + 22) * Math.sin(a);
    s += `<circle cx="${vx}" cy="${vy}" r="3.5" fill="#2563eb"/>`;
    s += `<text x="${vx}" y="${vy}" text-anchor="middle" dominant-baseline="middle" font-size="11" font-weight="700">${vals[i]}</text>`;
    s += `<text x="${lx}" y="${ly}" text-anchor="middle" dominant-baseline="middle" font-size="12" fill="#475569">${labels[i]}</text>`;
  });
  return s + "</svg>";
}

/* ---------- 置信度徽章 ---------- */
function confClass(c) {
  if (!c) return "conf-中置信";
  if (c.includes("高置信")) return "conf-高置信";
  if (c.includes("中高")) return "conf-中高置信";
  if (c.includes("低")) return "conf-低置信";
  return "conf-中置信";
}

/* ---------- 渲染：市场总览 ---------- */
function renderMarket(market) {
  if (!market || !market.indices) {
    return `<div class="notice">本日暂无市场数据（自动任务运行后生成）</div>`;
  }
  const isDemo = market.sample ? `<span class="badge-demo">演示数据</span>` : "";
  let html = `<div class="index-grid">`;
  market.indices.forEach(idx => {
    const cls = idx.change_pct >= 0 ? "up" : "down";
    const sign = idx.change_pct >= 0 ? "+" : "";
    html += `<div class="index-card"><div class="name">${esc(idx.name)}</div>
      <div class="value">${idx.value?.toLocaleString?.() ?? idx.value}</div>
      <span class="${cls}">${sign}${idx.change_pct}%</span></div>`;
  });
  html += `</div>`;
  const st = market.stats || {};
  html += `<div class="stats-row">
    <span class="chip">涨停 ${st.limit_up ?? "-"}</span>
    <span class="chip">跌停 ${st.limit_down ?? "-"}</span>
    <span class="chip">上涨 ${st.advancers ?? "-"} 家</span>
    <span class="chip">下跌 ${st.decliners ?? "-"} 家</span>
    <span class="chip">平盘 ${st.flat ?? "-"}</span>
    ${st.turnover_yi ? `<span class="chip">两市成交 ${st.turnover_yi} 亿</span>` : ""}
    ${market.broken_rate != null ? `<span class="chip">炸板率 ${market.broken_rate}%</span>` : ""}
  </div>`;
  if (market.hot_sectors?.length) {
    html += `<div class="stats-row"><b style="font-size:14px">热门板块：</b>`;
    market.hot_sectors.forEach(sec => {
      const cls = sec.change_pct >= 0 ? "up" : "down";
      html += `<span class="chip">${esc(sec.name)} <span class="${cls}">${sec.change_pct > 0 ? "+" : ""}${sec.change_pct}%</span></span>`;
    });
    html += `</div>`;
  }
  if (market.summary) {
    html += `<div class="thesis" style="margin-top:14px"><span class="label">📝 今日小结（AI）</span>${esc(market.summary)}</div>`;
  }
  return `<div>${html}<div class="meta" style="margin-top:8px">${isDemo} 生成时间：${esc(market.generated_at || "")}</div></div>`;
}

/* ---------- 渲染：涨停梯队 / 龙虎榜 ---------- */
function renderLadder(market) {
  if (!market) return `<div class="notice">暂无数据</div>`;
  const ladder = market.limit_up_ladder || {};
  const zbgc = market.broken_board || {};
  const lhb = market.lhb || {};
  let html = `<div class="stats-row">`;
  if (ladder.max_board) html += `<span class="chip">最高板：${ladder.max_board} 板</span>`;
  if (zbgc.count != null) html += `<span class="chip">炸板：${zbgc.count} 家</span>`;
  html += `</div>`;

  if (ladder.ladders && Object.keys(ladder.ladders).length) {
    html += `<div class="sub-block"><span class="block-title">🎢 连板梯队</span>`;
    for (const [k, v] of Object.entries(ladder.ladders)) {
      html += `<div style="margin:6px 0"><span class="tag" style="background:#1e3a8a;color:#fff">${esc(k)}</span> ${v.map(esc).join("、")}</div>`;
    }
    html += `</div>`;
  }

  if (ladder.top10?.length) {
    html += `<div class="sub-block"><span class="block-title">🔥 涨停 TOP10</span><div class="inst-chips">`;
    ladder.top10.forEach(s => {
      html += `<span class="inst-chip">${esc(s.name)} <span class="rid">${s.consecutive}板</span></span>`;
    });
    html += `</div></div>`;
  }

  if (lhb.top10?.length) {
    html += `<div class="sub-block"><span class="block-title">🐉 龙虎榜 TOP10</span>`;
    html += `<table class="evidence"><thead><tr><th>名称</th><th>涨跌幅</th><th>净买额(亿)</th><th>上榜原因</th></tr></thead><tbody>`;
    lhb.top10.forEach(r => {
      const cls = r.close_pct >= 0 ? "up" : "down";
      html += `<tr><td>${esc(r.name)}</td><td class="${cls}">${r.close_pct > 0 ? "+" : ""}${r.close_pct}%</td><td>${r.net_buy_yi}</td><td>${esc(r.reason || "")}</td></tr>`;
    });
    html += `</tbody></table></div>`;
  } else {
    html += `<div class="notice" style="padding:16px">龙虎榜通常 18:00 后披露，当日晚间会自动补抓。</div>`;
  }
  return html;
}

/* ---------- 渲染：主题卡片 ---------- */
function renderTheme(t, idx) {
  const radar = t.radar_scores || {};
  const inst = t.institutions || {};
  const evRows = (t.evidence_table || []).map(r => `
    <tr><td>${esc(r.indicator)}</td><td>${esc(r.value)}</td>
    <td>${esc(r.source_type)}</td><td class="src">${esc(r.source_id || "")}</td></tr>`).join("");

  let html = `<article class="theme-card">
    <div class="theme-head">
      <div class="theme-index">#${t.header?.index ?? idx + 1}</div>
      <div class="theme-title">${esc(t.header?.title || t.title || "")}</div>
      <span class="conf-badge ${confClass(t.header?.confidence)}">${esc(t.header?.confidence || "")}</span>
    </div>
    <div class="tags">${(t.tags || []).map(x => `<span class="tag">${esc(x)}</span>`).join("")}</div>
    <div class="theme-body">
      <div class="radar-box">
        <div class="radar-title">供需 / 估值 / 阶段 评分</div>
        ${radarSVG(radar)}
        <div class="radar-total">总分 ${radar.total || "-"} ｜ 平均 ${radar.average || "-"}</div>
      </div>
      <div>
        <div class="thesis"><span class="label">🎯 核心观点</span>${esc(t.core_thesis || "")}</div>
        ${inst.count ? `<div class="sub-block"><span class="block-title">🏛 机构覆盖（${inst.count} 家）</span>
          <div class="inst-chips">${(inst.list || []).map(i =>
            `<span class="inst-chip">${esc(i.name)} <span class="rid">${esc(i.report_id || "")}</span></span>`).join("")}
          </div></div>` : ""}
        ${evRows ? `<div class="sub-block"><span class="block-title">📊 关键证据</span>
          <table class="evidence"><thead><tr><th>指标</th><th>数值</th><th>来源</th><th>编号</th></tr></thead>
          <tbody>${evRows}</tbody></table></div>` : ""}
        ${t.logic_chain ? `<div class="sub-block"><span class="block-title">🧩 逻辑链条</span>
          <div class="logic">${esc(t.logic_chain)}</div></div>` : ""}
        ${t.risk_note ? `<div class="risk-box">⚠️ 风险提示：${esc(t.risk_note)}</div>` : ""}
        ${t.falsifiability_threshold ? `<div class="falsify-box">🔍 可证伪阈值：${esc(t.falsifiability_threshold)}</div>` : ""}
        ${t.related_events?.length ? `<div class="related-events">📅 关联事件：${t.related_events.map(esc).join("；")}</div>` : ""}
      </div>
    </div>
  </article>`;
  return html;
}

/* ---------- 渲染：事件日历 ---------- */
function renderCalendar(events) {
  if (!events?.length) return `<div class="notice">暂无事件数据</div>`;
  return `<div class="timeline">` + events.map(ev => `
    <div class="tl-item">
      <div class="tl-date">📅 ${esc(ev.date)}</div>
      <div class="tl-name">${esc(ev.event_name)}</div>
      <div class="tl-desc">影响：${esc(ev.impact || "")}</div>
      ${ev.related_theme_ids?.length ? `<div class="tl-desc">关联主题：${ev.related_theme_ids.map(x => `#${x}`).join("、")}</div>` : ""}
      ${ev.data_verification_point ? `<div class="tl-verify">✔ 验证点：${esc(ev.data_verification_point)}</div>` : ""}
    </div>`).join("") + `</div>`;
}

/* ---------- 渲染：关联图谱 ---------- */
function renderCorrelations(corrs) {
  if (!corrs?.length) return `<div class="notice">暂无关联数据</div>`;
  return `<div class="corr-grid">` + corrs.map(c => `
    <div class="corr-card">
      <div class="corr-pair">
        <span class="corr-node">${esc(c.from)}</span>
        <span class="corr-arrow">→</span>
        <span class="corr-node">${esc(c.to)}</span>
        <span class="corr-rel">${esc(c.relation)}</span>
      </div>
      <div class="corr-ev">${esc(c.evidence || "")}</div>
    </div>`).join("") + `</div>`;
}

/* ---------- 渲染：关键洞察 ---------- */
function renderInsights(items) {
  if (!items?.length) return `<div class="notice">暂无洞察数据</div>`;
  return items.map((it, i) => `
    <div class="insight-item"><div class="insight-num">${i + 1}</div>
    <div>${esc(typeof it === "string" ? it : (it.title + (it.detail ? " —— " + it.detail : "")))}</div></div>`).join("");
}

/* ---------- 主渲染 ---------- */
async function renderReview(date) {
  const url = date === "latest" ? `${REVIEWS_BASE}latest.json` : `${REVIEWS_BASE}${date}.json`;
  try {
    const data = await loadJSON(url);
    document.getElementById("header-meta").textContent =
      `复盘日期：${data.meta?.date} ｜ 生成时间：${data.meta?.generated_at || "-"} ｜ 来源：${data.meta?.source || "-"}`;
    document.getElementById("market-content").innerHTML = renderMarket(data.market);
    document.getElementById("ladder-content").innerHTML = renderLadder(data.market);
    document.getElementById("themes-content").innerHTML =
      (data.themes || []).map((t, i) => renderTheme(t, i)).join("") || `<div class="notice">暂无主题数据</div>`;
    document.getElementById("calendar-content").innerHTML = renderCalendar(data.calendar_events);
    document.getElementById("correlations-content").innerHTML = renderCorrelations(data.correlations);
    document.getElementById("insights-content").innerHTML = renderInsights(data.insights);
    document.getElementById("loading").hidden = true;
  } catch (e) {
    document.getElementById("loading").hidden = true;
    document.getElementById("error").hidden = false;
    document.getElementById("error").textContent = `加载失败（${e.message}）。该日期可能尚未生成复盘，或文件不存在。`;
  }
}

/* ---------- 历史日期下拉 ---------- */
async function initDatePicker() {
  try {
    const idx = await loadJSON(`${REVIEWS_BASE}index.json`);
    const dates = idx.dates || [];
    const sel = document.getElementById("date-select");
    sel.innerHTML = "";
    dates.forEach(d => {
      const opt = document.createElement("option");
      opt.value = d; opt.textContent = d;
      if (d === idx.latest) opt.selected = true;
      sel.appendChild(opt);
    });
    if (idx.latest) sel.value = idx.latest;
  } catch (e) {
    console.warn("index.json 不可用，仅展示最新：", e);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  await initDatePicker();
  const sel = document.getElementById("date-select");
  renderReview(sel.value || "latest");
  sel.addEventListener("change", () => renderReview(sel.value || "latest"));
  document.getElementById("btn-latest").addEventListener("click", async () => {
    await initDatePicker();
    renderReview(sel.value || "latest");
  });
});
