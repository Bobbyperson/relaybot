"use strict";

const API = ""; // same origin; set to "https://host:2586" if the site is hosted elsewhere
const PAGE_SIZE = 25;

const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) =>
  ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

async function api(path) {
  const res = await fetch(API + path);
  if (!res.ok) throw new Error(`${path} -> ${res.status}`);
  return res.json();
}

function setEngine(ok) {
  $("engine-dot").classList.toggle("stale", !ok);
  $("engine-text").textContent = ok ? "Connected // Live" : "Connection lost";
}

function hms(sec) {
  sec = Math.max(0, Math.floor(sec));
  const h = String(Math.floor(sec / 3600)).padStart(2, "0");
  const m = String(Math.floor((sec % 3600) / 60)).padStart(2, "0");
  const s = String(sec % 60).padStart(2, "0");
  return `${h}:${m}:${s}`;
}

function stamp(ts) {
  const d = new Date(ts * 1000);
  return d.toLocaleString(undefined, {
    month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
  });
}

function dur(s) { return `${Number(s).toFixed(1)}s`; }

function statRows(el, rows, valueFn, cls) {
  if (!rows.length) {
    el.innerHTML = '<div class="empty-state" style="padding:0.75rem 0;">No data</div>';
    return;
  }
  el.innerHTML = rows.map((r, i) => `
    <div class="stat-row">
      <span class="idx">${i + 1}</span>
      <span class="nm">${esc(r.name)}</span>
      <span class="vl ${cls || ""}">${valueFn(r)}</span>
    </div>`).join("");
}

/* ============================ TERMINAL ============================ */

let cycleEnd = 0, cycleCode = "";

async function loadTerminal() {
  const [latest, status, online, streaks, heat, insights] = await Promise.all([
    api("/api/recent_duels?limit=1&window=all"),
    api("/api/cycle_status"),
    api("/api/online_players"),
    api("/api/streaks?window=7d"),
    api("/api/heatmap?window=7d"),
    api("/api/live_insights?window=cycle&limit=5&min_duels=1"),
  ]);

  const d = latest.results[0];
  $("latest-duel").innerHTML = d ? `
    <div class="side victor">
      <div class="who">${esc(d.winner_name)}</div>
      <div class="meta">${d.winner_acc.toFixed(1)}% acc &middot; ${d.winner_hp} hp left</div>
    </div>
    <div class="vs">DEFEATED</div>
    <div class="side victim">
      <div class="who">${esc(d.loser_name)}</div>
      <div class="meta">${d.loser_acc.toFixed(1)}% acc</div>
    </div>
    <div class="side" style="text-align:right;flex:0 0 auto;">
      <div class="who" style="font-size:0.95rem;color:var(--accent-blue);">${dur(d.duration)}</div>
      <div class="meta">${stamp(d.ts)}</div>
    </div>`
    : '<div class="empty-state" style="padding:0.5rem 0;">Awaiting new duel&hellip;</div>';

  cycleEnd = status.end;
  cycleCode = status.cycle;
  $("cycle-label").textContent = `Cycle ${status.cycle}`;

  $("online-players").innerHTML = online.results.length
    ? online.results.map((p) => `
        <div class="stat-row">
          <span class="nm">${esc(p.name || p.uid)}</span>
          <span class="vl">${p.handicap !== 1 ? Math.round(p.handicap * 100) + "%" : "&mdash;"}</span>
        </div>`).join("")
    : '<div class="empty-state" style="padding:0.75rem 0;">Nobody online</div>';

  const max = Math.max(1, ...heat.counts);
  $("heatmap").innerHTML = heat.counts.map((c, h) =>
    `<div class="bar" style="height:${(c / max) * 100}%;opacity:${c ? 0.25 + (c / max) * 0.75 : 0.08}" title="${String(h).padStart(2, "0")}:00 UTC — ${c} duels"></div>`
  ).join("");

  statRows($("hot-streaks"), streaks.hot, (r) => `W${r.streak}`, "hot");
  statRows($("cold-streaks"), streaks.cold, (r) => `L${Math.abs(r.streak)}`, "cold");
  statRows($("top-eliminators"), insights.top_eliminators, (r) => r.wins);
  statRows($("most-eliminated"), insights.most_eliminated, (r) => r.losses);
}

setInterval(() => {
  if (cycleEnd) {
    const left = hms(cycleEnd - Date.now() / 1000);
    $("cycle-countdown").textContent = left;
    const rk = $("rk-reset");
    if (rk) rk.textContent = left;
  }
}, 1000);

/* =========================== LEADERBOARD =========================== */

let lbRows = [], lbPage = 0;

async function loadLeaderboard() {
  $("lb-loading").classList.add("visible");
  $("lb-empty").style.display = "none";
  const q = new URLSearchParams({
    window: $("lb-window").value,
    sort: $("lb-sort").value,
    search: $("lb-search").value.trim(),
  });
  const data = await api("/api/leaderboard?" + q);
  lbRows = data.results;
  lbPage = 0;
  $("lb-loading").classList.remove("visible");
  renderLeaderboard();
}

function renderLeaderboard() {
  const slice = lbRows.slice(lbPage * PAGE_SIZE, (lbPage + 1) * PAGE_SIZE);
  $("lb-empty").style.display = lbRows.length ? "none" : "block";
  $("lb-body").innerHTML = slice.map((r) => `
    <tr>
      <td class="rank">${r.rank}</td>
      <td>${esc(r.name)}</td>
      <td class="num">${r.wins}</td>
      <td class="num">${r.losses}</td>
      <td class="num">${r.winrate}%</td>
      <td class="num">${r.acc}%</td>
      <td class="num" style="color:${r.streak > 0 ? "var(--accent-green)" : r.streak < 0 ? "var(--accent-red)" : "var(--text-muted)"}">
        ${r.streak > 0 ? "W" + r.streak : r.streak < 0 ? "L" + Math.abs(r.streak) : "&mdash;"}
      </td>
    </tr>`).join("");
  pager($("lb-pages"), lbPage, Math.ceil(lbRows.length / PAGE_SIZE), (p) => { lbPage = p; renderLeaderboard(); });
}

function pager(el, page, total, go) {
  if (total <= 1) { el.innerHTML = ""; return; }
  el.innerHTML = `
    <button ${page === 0 ? "disabled" : ""} data-go="${page - 1}">PREV</button>
    <span class="page-display">PAGE_INDEX: ${String(page + 1).padStart(2, "0")} / ${String(total).padStart(2, "0")}</span>
    <button ${page >= total - 1 ? "disabled" : ""} data-go="${page + 1}">NEXT</button>`;
  el.querySelectorAll("button[data-go]").forEach((b) =>
    b.addEventListener("click", () => go(Number(b.dataset.go))));
}

/* ============================== RANKS ============================== */

async function loadCycles() {
  const data = await api("/api/cycles");
  $("rk-cycle").innerHTML = data.results.map((c) => `<option value="${esc(c)}">${esc(c)}</option>`).join("");
}

async function loadRanks() {
  $("rk-loading").classList.add("visible");
  const cycle = $("rk-cycle").value;
  const data = await api("/api/top_players?limit=50&cycle=" + encodeURIComponent(cycle));
  $("rk-loading").classList.remove("visible");
  $("rk-empty").style.display = data.results.length ? "none" : "block";
  $("rk-body").innerHTML = data.results.map((r) => `
    <tr>
      <td class="rank">${r.rank}</td>
      <td>${esc(r.name)}</td>
      <td class="num">${r.wins}</td>
      <td class="num">${r.losses}</td>
      <td class="num">${r.winrate}%</td>
      <td class="num">${r.acc}%</td>
    </tr>`).join("");
}

/* ============================= RECORDS ============================= */

let rcRows = [], rcPage = 0;

async function loadRecords() {
  $("rc-loading").classList.add("visible");
  const data = await api("/api/recent_duels?limit=200&window=" + $("rc-window").value);
  rcRows = data.results;
  rcPage = 0;
  $("rc-loading").classList.remove("visible");
  renderRecords();
}

function renderRecords() {
  const slice = rcRows.slice(rcPage * PAGE_SIZE, (rcPage + 1) * PAGE_SIZE);
  $("rc-empty").style.display = rcRows.length ? "none" : "block";
  $("rc-body").innerHTML = slice.map((d) => `
    <tr>
      <td class="uid">${d.id}</td>
      <td class="uid">${stamp(d.ts)}</td>
      <td class="victor">${esc(d.winner_name)}</td>
      <td class="uid">${esc(d.winner_uid)}</td>
      <td class="num">${d.winner_acc.toFixed(1)}</td>
      <td>${esc(d.loser_name)}</td>
      <td class="uid">${esc(d.loser_uid)}</td>
      <td class="num">${d.loser_acc.toFixed(1)}</td>
      <td class="num">${dur(d.duration)}</td>
    </tr>`).join("");
  pager($("rc-pages"), rcPage, Math.ceil(rcRows.length / PAGE_SIZE), (p) => { rcPage = p; renderRecords(); });
}

/* ============================== VERSUS ============================== */

async function loadVersus() {
  const a = $("vs-a").value.trim(), b = $("vs-b").value.trim();
  if (!a || !b) return;
  const data = await api(`/api/versus?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`);
  $("vs-score").style.display = "flex";
  $("vs-wrap").style.display = data.total ? "block" : "none";
  $("vs-empty").style.display = data.total ? "none" : "block";
  if (!data.total) $("vs-empty").textContent = "No duels between these two players.";
  $("vs-a-name").textContent = a;
  $("vs-b-name").textContent = b;
  $("vs-a-count").textContent = data.a_wins;
  $("vs-b-count").textContent = data.b_wins;
  $("vs-body").innerHTML = data.duels.map((d) => `
    <tr>
      <td class="uid">${stamp(d.ts)}</td>
      <td class="victor">${esc(d.winner_name)}</td>
      <td class="num">${d.winner_acc.toFixed(1)}</td>
      <td>${esc(d.loser_name)}</td>
      <td class="num">${d.loser_acc.toFixed(1)}</td>
      <td class="num">${dur(d.duration)}</td>
    </tr>`).join("");
}

async function fillNames() {
  const data = await api("/api/player_search?q=&limit=25").catch(() => ({ results: [] }));
  $("vs-names").innerHTML = data.results.map((p) => `<option value="${esc(p.name)}">`).join("");
}

/* =============================== SHELL =============================== */

const SUBTITLES = {
  terminal: "Live combat feed",
  leaderboard: "Duel standings",
  ranks: "Cycle rankings // weekly reset",
  records: "Filtered combat log",
  versus: "Head to head",
};

const LOADERS = {
  terminal: loadTerminal,
  leaderboard: loadLeaderboard,
  ranks: loadRanks,
  records: loadRecords,
  versus: async () => { await fillNames(); },
};

let current = "terminal";

async function show(view) {
  current = view;
  document.querySelectorAll(".site-nav button").forEach((b) =>
    b.classList.toggle("active", b.dataset.view === view));
  document.querySelectorAll(".view").forEach((s) =>
    s.classList.toggle("active", s.id === "view-" + view));
  $("page-subtitle").textContent = SUBTITLES[view];
  try {
    await LOADERS[view]();
    setEngine(true);
  } catch (e) {
    console.error(e);
    setEngine(false);
  }
}

function debounce(fn, ms) {
  let t;
  return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

document.querySelectorAll(".site-nav button").forEach((b) =>
  b.addEventListener("click", () => show(b.dataset.view)));

$("lb-window").addEventListener("change", loadLeaderboard);
$("lb-sort").addEventListener("change", loadLeaderboard);
$("lb-search").addEventListener("input", debounce(loadLeaderboard, 250));
$("rk-cycle").addEventListener("change", loadRanks);
$("rc-window").addEventListener("change", loadRecords);
$("vs-a").addEventListener("input", debounce(loadVersus, 400));
$("vs-b").addEventListener("input", debounce(loadVersus, 400));

// Refresh the terminal periodically; other views reload on interaction.
setInterval(() => { if (current === "terminal") show("terminal"); }, 15000);

(async () => {
  await loadCycles().catch(() => {});
  await show("terminal");
})();
