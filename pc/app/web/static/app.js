/* ABM 价格记录页面逻辑：拉取 /api/* 渲染，无第三方依赖。 */
"use strict";

const $ = (s) => document.querySelector(s);
const el = (tag, cls, text) => {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== undefined) n.textContent = text;
  return n;
};
const emptyRow = (colspan, text) => {
  const tr = el("tr");
  const td = el("td", "empty", text);
  td.colSpan = colspan;
  tr.append(td);
  return tr;
};
const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString() : "-");
const fmtPrice = (p) => (p == null ? "-" : Number(p).toLocaleString());

async function j(url, opt) {
  const r = await fetch(url, opt);
  if (!r.ok) throw new Error((await r.text()) || r.status);
  return r.json();
}

async function refreshOverview() {
  const o = await j("/health");
  $("#stat-records").textContent = o.records;
  $("#stat-bullets").textContent = o.bullets;
  $("#stat-devices").textContent = o.devices;
}

let currentBullet = null;
let currentWindow = "7d";

async function refreshLatest() {
  const [data, daily] = await Promise.all([j("/api/latest"), j("/api/daily")]);
  const names = Object.keys(data).sort();
  const tb = $("#latest-table tbody");
  tb.innerHTML = "";
  if (!names.length) {
    tb.append(emptyRow(6, "暂无记录 — 等待手机端采集上报"));
    return;
  }
  for (const name of names) {
    const it = data[name];
    const d = daily[name] || {};
    const tr = el("tr");
    tr.style.cursor = "pointer";
    tr.onclick = () => selectBullet(name);
    tr.append(el("td", null, name));
    tr.append(el("td", "price", fmtPrice(it.price)));
    tr.append(el("td", "price up", fmtPrice(d.high)));
    tr.append(el("td", "price down", fmtPrice(d.low)));
    const cls = it.delta == null ? "flat" : it.delta > 0 ? "up" : it.delta < 0 ? "down" : "flat";
    const txt = it.delta == null ? "-" : `${it.delta > 0 ? "+" : ""}${it.delta} (${it.delta_pct}%)`;
    tr.append(el("td", cls, txt));
    tr.append(el("td", null, fmtTime(it.captured_at)));
    tb.append(tr);
  }
  fillBulletSelect(names);
  if (!currentBullet || !names.includes(currentBullet)) currentBullet = names[0];
  $("#trend-bullet").value = currentBullet;
}

function fillBulletSelect(names) {
  const sel = $("#trend-bullet");
  sel.innerHTML = "";
  for (const n of names) {
    const op = el("option");
    op.value = n; op.textContent = n;
    sel.append(op);
  }
}

function selectBullet(name) {
  currentBullet = name;
  $("#trend-bullet").value = name;
  refreshTrend();
  refreshRecords();
}

async function refreshTrend() {
  if (!currentBullet) return;
  const pts = await j(`/api/trend?bullet=${encodeURIComponent(currentBullet)}&window=${currentWindow}`);
  const cv = $("#trend-canvas");
  const ctx = cv.getContext("2d");
  const empty = $("#trend-empty");
  const W = cv.width, H = cv.height;
  ctx.clearRect(0, 0, W, H);
  if (!pts.length) { empty.style.display = "block"; return; }
  empty.style.display = "none";
  const pad = { l: 64, r: 16, t: 16, b: 28 };
  const prices = pts.map((p) => p.price);
  const min = Math.min(...prices), max = Math.max(...prices);
  const span = max - min || 1;
  const x = (i) => pad.l + (i * (W - pad.l - pad.r)) / Math.max(pts.length - 1, 1);
  const y = (v) => pad.t + (H - pad.t - pad.b) * (1 - (v - min) / span);
  // 网格与 Y 轴刻度
  ctx.strokeStyle = "#332c47"; ctx.fillStyle = "#9a92b4"; ctx.font = "11px sans-serif";
  for (let g = 0; g <= 4; g++) {
    const gy = pad.t + (g * (H - pad.t - pad.b)) / 4;
    ctx.beginPath(); ctx.moveTo(pad.l, gy); ctx.lineTo(W - pad.r, gy); ctx.stroke();
    const val = Math.round(max - (g * span) / 4);
    ctx.fillText(val.toLocaleString(), 4, gy + 4);
  }
  // 折线
  ctx.strokeStyle = "#2bae8c"; ctx.lineWidth = 2;
  ctx.beginPath();
  pts.forEach((p, i) => (i ? ctx.lineTo(x(i), y(p.price)) : ctx.moveTo(x(i), y(p.price))));
  ctx.stroke();
  // 首末时间标签
  ctx.fillText(new Date(pts[0].t * 1000).toLocaleString(), pad.l, H - 6);
  ctx.fillText(new Date(pts[pts.length - 1].t * 1000).toLocaleString(), W - pad.r - 150, H - 6);
}

async function refreshRecords() {
  const q = currentBullet ? `bullet=${encodeURIComponent(currentBullet)}` : "";
  const d = await j(`/api/records?${q}&limit=200`);
  $("#rec-total").textContent = d.total;
  const tb = $("#records-table tbody");
  tb.innerHTML = "";
  if (!d.rows.length) {
    tb.append(emptyRow(5, "暂无明细"));
    return;
  }
  for (const r of d.rows) {
    const tr = el("tr");
    tr.append(el("td", null, fmtTime(r.captured_at)));
    tr.append(el("td", null, r.bullet_name));
    tr.append(el("td", "price", fmtPrice(r.price)));
    tr.append(el("td", null, r.device_id ? r.device_id.slice(0, 8) : "-"));
    const td = el("td");
    if (r.snapshot_url) {
      const a = el("a", "snap", "查看");
      a.href = r.snapshot_url; a.target = "_blank";
      td.append(a);
    } else td.textContent = "-";
    tr.append(td);
    tb.append(tr);
  }
}

async function refreshBullets() {
  const list = await j("/api/bullets");
  const tb = $("#bullets-table tbody");
  tb.innerHTML = "";
  if (!list.length) {
    tb.append(emptyRow(3, "清单为空 — 手机端上报的记录会自动加入，也可手动添加"));
    return;
  }
  for (const b of list) {
    const tr = el("tr");
    tr.append(el("td", null, b.name));
    const tdA = el("td");
    const btn = el("button", "mini", b.active ? "启用中" : "已停用");
    btn.style.background = b.active ? "#2bae8c" : "#4a4263";
    btn.onclick = async () => {
      await j(`/api/bullets/${encodeURIComponent(b.name)}/active?active=${b.active ? 0 : 1}`, { method: "PATCH" });
      refreshBullets();
    };
    tdA.append(btn);
    const tdD = el("td");
    const del = el("button", "danger mini", "删除");
    del.onclick = async () => {
      if (confirm(`删除清单项 ${b.name}？（历史记录保留）`)) {
        await j(`/api/bullets/${encodeURIComponent(b.name)}`, { method: "DELETE" });
        refreshBullets(); refreshLatest();
      }
    };
    tdD.append(del);
    tr.append(tdA, tdD);
    tb.append(tr);
  }
}

async function refreshReports() {
  const kind = $("#report-kind").value;
  const list = await j(`/api/reports?kind=${encodeURIComponent(kind)}&limit=30`);
  const box = $("#report-list");
  box.innerHTML = "";
  if (!list.length) {
    box.textContent = "暂无财报（可点上方按钮立即生成；每个整点/每天20:00也会自动生成）";
    $("#report-content").textContent = "-";
    return;
  }
  for (const r of list) {
    const a = document.createElement("a");
    a.className = "report-item";
    a.href = "#";
    a.textContent = r.title + "  ·  " + (r.created_at || "");
    a.onclick = (e) => { e.preventDefault(); showReport(r); };
    box.append(a, document.createElement("div"));
  }
  showReport(list[0]);
}

function showReport(r) {
  $("#report-content").textContent = r.content || "(无内容)";
}

async function genReport(kind) {
  try {
    const res = await j(`/api/reports/generate?kind=${kind}`, { method: "POST" });
    if (!res.ok) { alert("生成失败：" + res.reason); return; }
  } catch (e) { alert("生成失败：" + e.message); }
  refreshReports();
}

function renderWifiDevices(items, box) {
  box.innerHTML = "";
  if (!items || !items.length) { box.textContent = "未发现无线设备（确认手机已开启「无线调试」且与电脑同网）"; box.className = "muted"; return; }
  box.className = "";
  for (const d of items) {
    const row = document.createElement("div");
    const label = document.createElement("span");
    label.textContent = `${d.name ? d.name + " · " : ""}${d.host}:${d.port}${d.tls ? " (TLS)" : ""}`;
    const b = document.createElement("button");
    b.className = "mini"; b.textContent = "连接";
    b.onclick = () => wifiConnect(d.host, d.port, null, null);
    row.append(label, " ", b);
    box.append(row);
  }
}

async function wifiScan() {
  try {
    const res = await j("/api/wifi/scan");
    renderWifiDevices(res.devices || [], $("#wifi-scan-list"));
  } catch (e) { $("#wifi-scan-list").textContent = "扫描失败：" + e.message; }
}

async function wifiStatus() {
  try {
    const res = await j("/api/wifi/status");
    const s = $("#wifi-status");
    if (!res.ok) { s.textContent = "获取失败：" + res.reason; return; }
    s.innerHTML = "";
    s.append(document.createTextNode(`无线[${(res.wireless || []).join(", ") || "无"}]  USB[${(res.usb || []).join(", ") || "无"}]`));
    for (const w of (res.wireless || [])) {
      const b = document.createElement("button");
      b.className = "mini"; b.textContent = "断开 " + w;
      b.onclick = async () => {
        try { await j("/api/wifi/disconnect", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ addr: w }) }); }
        catch (e) { alert(e.message); }
        wifiStatus();
      };
      s.append(" ", b);
    }
  } catch (e) { $("#wifi-status").textContent = "状态失败：" + e.message; }
}

async function wifiConnect(host, port, pairPort, pairCode) {
  const box = $("#wifi-result");
  if (!host || !port) { box.textContent = "请填手机 IP 与连接端口"; return; }
  try {
    const res = await j("/api/wifi/connect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ host, port, pair_port: pairPort || null, pair_code: pairCode || null }),
    });
    box.textContent = res.ok
      ? "已连接：" + ((res.devices || []).join(", ") || "(未显示设备?)") + (res.output ? "｜" + res.output : "")
      : "失败：" + (res.reason || res.output || "");
    wifiStatus(); wifiScan();
  } catch (e) { box.textContent = "连接失败：" + e.message; }
}

function initEvents() {
  $("#btn-refresh").onclick = () => Promise.all([refreshOverview(), refreshLatest(), refreshBullets()]).catch(alert);
  $("#trend-bullet").onchange = (e) => selectBullet(e.target.value);
  $("#trend-windows").querySelectorAll("button").forEach((b) => {
    b.onclick = () => {
      currentWindow = b.dataset.w;
      document.querySelectorAll("#trend-windows button").forEach((x) => x.classList.toggle("on", x === b));
      refreshTrend();
    };
  });
  document.querySelector('#trend-windows button[data-w="7d"]').classList.add("on");
  $("#btn-add-bullet").onclick = async () => {
    const name = $("#bullet-new").value.trim();
    if (!name) return;
    await j("/api/bullets", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ name }),
    });
    $("#bullet-new").value = "";
    refreshBullets();
  };
  $("#btn-gen-daily").onclick = () => genReport("daily");
  $("#btn-gen-hourly").onclick = () => genReport("hourly");
  $("#btn-refresh-reports").onclick = () => refreshReports();
  $("#report-kind").onchange = () => refreshReports();
  $("#btn-wifi-scan").onclick = () => wifiScan();
  $("#btn-wifi-status").onclick = () => wifiStatus();
  $("#btn-wifi-connect").onclick = () => wifiConnect(
    $("#wifi-host").value.trim(),
    parseInt($("#wifi-port").value, 10) || 0,
    parseInt($("#wifi-pair-port").value, 10) || null,
    $("#wifi-pair-code").value.trim() || null
  );
}

async function boot() {
  initEvents();
  await Promise.all([refreshOverview(), refreshLatest(), refreshBullets()]);
  await refreshTrend();
  refreshRecords();
  refreshReports();
  setInterval(() => { refreshOverview(); refreshLatest(); refreshReports(); }, 15000);
}
boot().catch((e) => alert("加载失败：" + e.message));
