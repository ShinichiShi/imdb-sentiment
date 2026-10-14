const Dashboard = {
  selected: null, paused: false,
  async mount(el) {
    await loadLibrary();
    el.innerHTML = `<section class="page">
      <div class="pagehead row-between"><div><h1>Live dashboard</h1><p class="muted">Running average sentiment per title, straight from the Kafka → HDFS pipeline.</p></div>
        <div class="controls"><span>Stream rate</span><input type="range" id="rate" min="1" max="30" value="3"><span id="rateLbl" style="min-width:48px">3 /s</span>
          <button id="pause">Pause</button><button id="reset" title="Clear dashboard aggregates (HDFS data is kept)">Reset stats</button></div></div>
      <div class="kpis" id="kpis"></div>
      <div class="panel"><h2>Pipeline</h2><div class="flow" id="flow"></div><div class="err" id="hdfsErr"></div></div>
      <div class="grid2">
        <div class="panel"><h2>Running average per title <span class="muted nc">— click a row</span></h2><div id="movies" class="board"></div>
          <div class="muted small">Score = mean P(positive) over all reviews so far · centre line = neutral (50)</div></div>
        <div class="panel"><h2 id="chartTitle">Sentiment over time</h2><div id="chart"></div>
          <h2 style="margin-top:14px">Latest reviews</h2><div class="feed" id="feed"></div></div></div>
      <div class="panel"><h2>HDFS — recent part files</h2><table id="files"></table>
        <div style="margin-top:8px"><a id="nnui" target="_blank" rel="noopener">NameNode web UI ↗</a></div></div></section>`;
    $("#rate").oninput = e => $("#rateLbl").textContent = e.target.value + " /s";
    $("#rate").onchange = e => post("/api/control", { rate: +e.target.value });
    $("#pause").onclick = () => post("/api/control", { paused: !this.paused }).then(() => this.update());
    $("#reset").onclick = async () => { await post("/api/reset", {}); this.update(); };
    $("#movies").onclick = e => { const r = e.target.closest(".row"); if (r) { this.selected = r.dataset.t; this.draw(); this.detail(); } };
    await this.update();
  },
  async update() { await refreshLive(); this.draw(); await this.detail(); },
  draw() {
    const s = App.summary, p = App.pipeline, d = x => `<span class="dot ${x ? "on" : "off"}"></span>`;
    const kpi = (v, l) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    $("#kpis").innerHTML = kpi(s.total.toLocaleString(), "reviews scored") + kpi(pct(s.avg_score, 1), "overall avg sentiment (0–100)") +
      kpi(pct(s.pos_pct) + "%", "classified positive") + kpi(s.per_min, "reviews in last minute") +
      kpi(s.live_accuracy == null ? "–" : pct(s.live_accuracy, 1) + "%", "live accuracy vs true labels");
    this.paused = p.producer.paused; $("#pause").textContent = this.paused ? "Resume" : "Pause";
    if (document.activeElement !== $("#rate")) { $("#rate").value = p.producer.rate; $("#rateLbl").textContent = p.producer.rate + " /s"; }
    $("#flow").innerHTML = [
      ["Producer", d(p.producer.alive && !this.paused), `${p.producer.sent.toLocaleString()} sent · ${this.paused ? "paused" : p.producer.rate + "/s"}`],
      ["Kafka", d(true), `topic <code>${p.kafka.topic}</code><br>${esc(p.kafka.mode)} · lag ${p.kafka.lag}`],
      ["Stream processor", d(p.processor.alive), `${p.processor.consumed.toLocaleString()} consumed<br>TF-IDF + LogReg · ${p.processor.buffered} buffered`],
      ["HDFS", d(p.hdfs.ok && !p.hdfs.error), `${esc(p.hdfs.mode)}<br>${p.hdfs.records.toLocaleString()} records · ${p.hdfs.raw.files || 0} raw + ${p.hdfs.scored.files || 0} scored files · ${bytes((p.hdfs.raw.bytes || 0) + (p.hdfs.scored.bytes || 0))}`],
      ["Dashboard", d(true), "running averages per title"]]
      .map((n, i) => (i ? `<div class="arrow">➜</div>` : "") + `<div class="node"><b>${n[1]}${n[0]}</b><div class="s">${n[2]}</div></div>`).join("");
    $("#hdfsErr").textContent = p.hdfs.error ? "HDFS write error (retrying): " + p.hdfs.error : "";
    $("#files").innerHTML = `<tr><th>path</th><th>size</th></tr>` + p.hdfs.recent_files.map(f => `<tr><td title="${esc(f.path)}">${esc(f.path.replace("/imdb/stream/", "…/"))}</td><td>${bytes(f.size)}</td></tr>`).join("");
    $("#nnui").href = p.hdfs.ui;
    const ms = App.live; if (!this.selected && ms.length) this.selected = ms[0].title;
    $("#movies").innerHTML = ms.map(m => {
      const arrow = Math.abs(m.trend) < 0.01 ? "" : m.trend > 0 ? `<span class="up" title="last 20 reviews above average">▲</span>` : `<span class="down" title="last 20 reviews below average">▼</span>`;
      return `<div class="row ${m.title === this.selected ? "sel" : ""}" data-t="${esc(m.title)}">
        <img class="th" src="${posterUrl(m.poster)}" alt="" loading="lazy">
        <div class="t">${esc(m.title)} <small>${m.year ?? ""}</small></div>
        <div class="bar"><i style="width:${pct(m.avg_score)}%;background:${col(m.avg_score)}"></i></div>
        <div class="num"><b>${pct(m.avg_score, 1)}</b></div><div class="num muted">${m.count}</div><div>${arrow}</div></div>`;
    }).join("") || `<div class="muted">Waiting for the first reviews…</div>`;
  },
  async detail() {
    if (!this.selected) return;
    const t = encodeURIComponent(this.selected);
    const [h, rec] = await Promise.all([get(`/api/movies/history?title=${t}`), get(`/api/recent?limit=12&title=${t}`)]);
    $("#chartTitle").textContent = `Running average — ${this.selected}`;
    $("#chart").innerHTML = lineChart(h);
    $("#feed").innerHTML = rec.map(r => reviewItem(r, false)).join("") || `<div class="muted">No reviews yet.</div>`;
  },
};
