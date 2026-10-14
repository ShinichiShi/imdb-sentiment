const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
const pct = (x, d = 0) => x == null ? "–" : (x * 100).toFixed(d);
const bytes = n => n < 1024 ? n + " B" : n < 1048576 ? (n / 1024).toFixed(1) + " KB" : (n / 1048576).toFixed(1) + " MB";
const col = s => s >= 0.5 ? "var(--pos)" : "var(--neg)";
const get = async u => { const r = await fetch(u); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); };
const post = (u, b) => fetch(u, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) }).then(r => r.json());
const posterUrl = f => `/posters/${f}`;
const kfmt = n => n >= 1e6 ? (n / 1e6).toFixed(1) + "M" : n >= 1e3 ? Math.round(n / 1e3) + "K" : n;

// shared client state
const App = { library: [], byId: {}, live: [], liveById: {}, summary: null, pipeline: null };

async function loadLibrary() {
  if (!App.library.length) {
    App.library = await get("/static/library.json");
    App.library.forEach(m => App.byId[m.id] = m);
  }
  return App.library;
}

async function refreshLive() {
  const [live, summary, pipeline] = await Promise.all([get("/api/movies"), get("/api/summary"), get("/api/pipeline")]);
  App.live = live; App.summary = summary; App.pipeline = pipeline;
  App.liveById = Object.fromEntries(live.map(m => [m.imdb_id, m]));
  const on = pipeline.processor.alive && pipeline.producer.alive && !pipeline.producer.paused;
  $("#livePill").classList.toggle("on", on);
  $("#liveTxt").textContent = pipeline.producer.paused ? "stream paused" : on ? `live · ${summary.total.toLocaleString()} reviews` : "stream offline";
}

/* ---- reusable fragments ---- */
function ring(score) {   // circular live-sentiment badge
  const p = Math.round(score * 100);
  return `<span class="ring" style="--p:${p};--c:${score >= .5 ? "var(--pos)" : "var(--neg)"}"><i>${p}</i></span>`;
}

function posterCard(m) {   // m = library entry
  const live = App.liveById[m.id];
  return `<article class="card" data-id="${m.id}" tabindex="0">
    <div class="pimg"><img loading="lazy" src="${posterUrl(m.file)}" alt="${esc(m.title)} poster" onerror="this.parentNode.classList.add('nopic')">
      <span class="imdb">★ ${m.score.toFixed(1)}</span>${live ? ring(live.avg_score) : ""}</div>
    <div class="ct">${esc(m.title)}</div><div class="cs">${m.year ?? ""}${m.genres[0] ? " · " + esc(m.genres[0]) : ""}</div></article>`;
}

function lineChart(data, h = 190) {
  if (data.length < 2) return `<div class="muted" style="padding:30px 0">Collecting data…</div>`;
  const W = 560, H = h, L = 34, R = 10, T = 10, B = 22;
  const ys = data.map(d => d.avg), lo = Math.max(0, Math.min(...ys, .5) - .05), hi = Math.min(1, Math.max(...ys, .5) + .05);
  const x = i => L + (W - L - R) * i / (data.length - 1), y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const path = data.map((d, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(d.avg).toFixed(1)}`).join("");
  const last = data[data.length - 1];
  const ticks = [lo, (lo + hi) / 2, hi].map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 4}" y="${y(v) + 4}" text-anchor="end">${pct(v)}</text>`).join("");
  const neutral = lo < .5 && hi > .5 ? `<line x1="${L}" x2="${W - R}" y1="${y(.5)}" y2="${y(.5)}" stroke="var(--muted)" stroke-dasharray="4 3"/>` : "";
  return `<svg viewBox="0 0 ${W} ${H}" width="100%" role="img" aria-label="Running average sentiment">${ticks}${neutral}
    <path d="${path}" fill="none" stroke="${col(last.avg)}" stroke-width="2.4"/>
    <circle cx="${x(data.length - 1)}" cy="${y(last.avg)}" r="4" fill="${col(last.avg)}"/>
    <text x="${W - R}" y="${y(last.avg) - 9}" text-anchor="end" style="fill:var(--text)">${pct(last.avg, 1)}</text>
    <text x="${L}" y="${H - 5}">review #1</text><text x="${W - R}" y="${H - 5}" text-anchor="end">#${last.n}</text></svg>`;
}

function reviewItem(r, showTitle) {
  return `<div class="item ${r.label ? "p" : "n"}"><div class="m"><span>${showTitle ? `<b>${esc(r.title)}</b> · ` : ""}${r.true_label === -1 ? "✍ user review · " : ""}${r.label ? "positive" : "negative"}</span><span>${pct(r.score)}%</span></div><p>${esc(r.text)}</p></div>`;
}

/* ---- movie detail modal ---- */
let modalTimer = null;
async function openMovie(id) {
  await loadLibrary();
  const m = App.byId[id]; if (!m) return;
  $("#modal").hidden = false; document.body.classList.add("noscroll");
  const draw = async () => {
    const live = App.liveById[id];
    let body = "";
    if (live) {
      const [h, rec] = await Promise.all([get(`/api/movies/history?title=${encodeURIComponent(m.title)}`), get(`/api/recent?limit=6&title=${encodeURIComponent(m.title)}`)]);
      const gap = live.avg_score * 10 - m.score;
      body = `<div class="two">
          <div class="stat"><div class="v" style="color:${col(live.avg_score)}">${pct(live.avg_score, 1)}</div><div class="l">live audience sentiment</div></div>
          <div class="stat"><div class="v">${pct(live.pos_pct)}%</div><div class="l">positive · ${live.count} reviews</div></div>
          <div class="stat"><div class="v">${m.score.toFixed(1)}</div><div class="l">IMDb rating</div></div>
          <div class="stat"><div class="v ${gap >= 0 ? "up" : "down"}">${gap >= 0 ? "+" : ""}${gap.toFixed(1)}</div><div class="l">live (÷10) vs IMDb</div></div></div>
        <h4>Running average sentiment</h4>${lineChart(h, 150)}
        <h4>Latest reviews</h4><div class="feed short">${rec.map(r => reviewItem(r, false)).join("") || '<div class="muted">No reviews yet.</div>'}</div>`;
    } else {
      body = `<div class="notlive">No live reviews for this title yet. Be the first — write a review and it will start its running sentiment score.</div>`;
    }
    $("#sheet").innerHTML = `<button class="x" id="mx" aria-label="Close">✕</button>
      <div class="mhead"><img src="${posterUrl(m.file)}" alt="${esc(m.title)} poster">
        <div><h2>${esc(m.title)}</h2><div class="muted">${m.year ?? "–"}${m.runtime ? " · " + m.runtime + " min" : ""}</div>
          <div class="tags">${m.genres.map(g => `<span>${esc(g)}</span>`).join("")}</div>
          <div class="imdbbig">★ ${m.score.toFixed(1)}<small>/10 · ${kfmt(m.votes)} votes</small></div>
          <div class="mact"><a class="btn primary" href="#/review/${m.id}">✍ Write a review</a> <a class="muted" target="_blank" rel="noopener" href="https://www.imdb.com/title/${m.id}/">IMDb page ↗</a></div></div></div>${body}`;
    $("#mx").onclick = closeMovie;
  };
  await draw();
  clearInterval(modalTimer); modalTimer = setInterval(() => !$("#modal").hidden && App.liveById[id] && draw().catch(() => {}), 3000);
}
function closeMovie() { $("#modal").hidden = true; document.body.classList.remove("noscroll"); clearInterval(modalTimer); }
document.addEventListener("keydown", e => e.key === "Escape" && closeMovie());
document.addEventListener("click", e => {
  if (e.target.id === "modal") return closeMovie();
  const c = e.target.closest(".card[data-id]"); if (c) openMovie(c.dataset.id);
});
document.addEventListener("keydown", e => { if (e.key === "Enter" && e.target.matches?.(".card[data-id]")) openMovie(e.target.dataset.id); });
