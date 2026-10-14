const Analysis = {
  async mount(el) {
    await loadLibrary();
    el.innerHTML = `<section class="page">
      <div class="pagehead"><h1>Analysis</h1><p class="muted">How good is the classifier, what does it look at, and does the live audience agree with IMDb?</p></div>
      <div class="kpis" id="mk"></div>
      <div class="grid2">
        <div class="panel"><h2>Live sentiment vs IMDb rating</h2><div id="scatter"></div><div class="muted small" id="corr"></div></div>
        <div class="panel"><h2>Confusion matrix · 10,000 held-out reviews</h2><div id="cm"></div><div class="muted small" id="algo" style="margin-top:10px"></div></div></div>
      <div class="panel"><h2>What the model learned — most influential words</h2><div class="words" id="words"></div>
        <div class="muted small">Largest logistic-regression coefficients over the 5,000 TF-IDF features.</div></div>
      <div class="panel"><h2>Try the classifier</h2>
        <textarea id="review" placeholder="Write a movie review...">An absolutely brilliant film. The acting was superb and the story kept me hooked, though the ending was a little rushed.</textarea>
        <div style="margin-top:8px"><button class="btn primary" id="analyze">Analyze sentiment</button></div><div id="result"></div></div></section>`;
    $("#analyze").onclick = () => this.analyze();
    $("#scatter").onclick = e => { const c = e.target.closest("[data-id]"); if (c) openMovie(c.dataset.id); };
    const w = await get("/api/model/words");
    const mx = Math.max(...w.positive.map(x => x.weight), ...w.negative.map(x => -x.weight));
    const col2 = (arr, cls) => `<div><h3 class="${cls}">${cls === "up" ? "Pushes positive" : "Pushes negative"}</h3>${arr.map(x => `<div class="wrow"><span>${esc(x.word)}</span><div class="bar"><i style="width:${Math.abs(x.weight) / mx * 100}%;background:var(--${cls === "up" ? "pos" : "neg"})"></i></div><b>${x.weight.toFixed(1)}</b></div>`).join("")}</div>`;
    $("#words").innerHTML = col2(w.positive, "up") + col2(w.negative, "down");
    await this.update();
  },
  async update() {
    await refreshLive();
    const m = App.pipeline.model; if (!m.accuracy) return;
    const kpi = (v, l) => `<div class="kpi"><div class="v">${v}</div><div class="l">${l}</div></div>`;
    $("#mk").innerHTML = kpi(pct(m.accuracy, 2) + "%", "accuracy") + kpi(m.f1.toFixed(4), "F1 score") + kpi(m.roc_auc.toFixed(4), "ROC-AUC") +
      kpi(m.train_size.toLocaleString(), "training reviews") + kpi(pct(App.summary.live_accuracy, 1) + "%", "live accuracy (stream)");
    const cm = m.confusion_matrix, mx = Math.max(...cm.flat());
    const c = (v, good) => `<div style="background:color-mix(in srgb, ${good ? "var(--pos)" : "var(--neg)"} ${Math.round(v / mx * 70)}%, var(--panel2))">${v}</div>`;
    $("#cm").innerHTML = `<div class="cm"><div class="h"></div><div class="h">pred neg</div><div class="h">pred pos</div><div class="h">true neg</div>${c(cm[0][0], 1)}${c(cm[0][1], 0)}<div class="h">true pos</div>${c(cm[1][0], 0)}${c(cm[1][1], 1)}</div>`;
    $("#algo").textContent = `${m.algorithm} · C=${m.best_params.C.toFixed(2)}, solver=${m.best_params.solver}`;
    this.scatter();
  },
  scatter() {
    const pts = App.live.filter(m => m.imdb_score), W = 560, H = 300, L = 40, R = 14, T = 12, B = 34;
    if (pts.length < 3) { $("#scatter").innerHTML = `<div class="muted">Waiting for data…</div>`; return; }
    const x = v => L + (W - L - R) * (v - 2) / 8, y = v => T + (H - T - B) * (1 - v);
    const xs = pts.map(p => p.imdb_score), ys = pts.map(p => p.avg_score), n = pts.length, mx = xs.reduce((a, b) => a + b) / n, my = ys.reduce((a, b) => a + b) / n;
    const r = xs.reduce((s, v, i) => s + (v - mx) * (ys[i] - my), 0) / Math.sqrt(xs.reduce((s, v) => s + (v - mx) ** 2, 0) * ys.reduce((s, v) => s + (v - my) ** 2, 0));
    const grid = [0, .25, .5, .75, 1].map(v => `<line x1="${L}" x2="${W - R}" y1="${y(v)}" y2="${y(v)}" stroke="var(--line)"/><text x="${L - 6}" y="${y(v) + 4}" text-anchor="end">${v * 100}</text>`).join("") +
      [2, 4, 6, 8, 10].map(v => `<text x="${x(v)}" y="${H - 16}" text-anchor="middle">${v}</text>`).join("");
    const diag = `<line x1="${x(2)}" y1="${y(.2)}" x2="${x(10)}" y2="${y(1)}" stroke="var(--muted)" stroke-dasharray="4 3"/>`;
    const dots = pts.map(p => `<g data-id="${p.imdb_id}" class="dotg"><circle cx="${x(p.imdb_score)}" cy="${y(p.avg_score)}" r="7" fill="${col(p.avg_score)}" fill-opacity=".85" stroke="var(--bg)"/><title>${esc(p.title)} — IMDb ${p.imdb_score}, live ${pct(p.avg_score, 1)} (${p.count} reviews)</title></g>`).join("");
    $("#scatter").innerHTML = `<svg viewBox="0 0 ${W} ${H}" width="100%">${grid}${diag}${dots}<text x="${(L + W) / 2}" y="${H - 2}" text-anchor="middle">IMDb rating</text><text x="${L + 8}" y="${T + 12}">live sentiment ↑</text></svg>`;
    $("#corr").textContent = `Pearson r = ${r.toFixed(2)} over ${n} titles. Each dot is a streamed movie (click for details); the dashed line is perfect agreement (IMDb×10 = sentiment).`;
  },
  async analyze() {
    const text = $("#review").value.trim(); if (!text) return;
    try {
      const r = await post("/api/predict", { review: text }), pos = r.sentiment === "positive";
      $("#result").innerHTML = `<div class="verdict" style="color:${pos ? "var(--pos)" : "var(--neg)"}">${pos ? "😊 Positive" : "😞 Negative"} — ${pct(r.score, 1)}% positive</div>
        <div class="muted small" style="margin-top:6px">Words that drove the score (TF-IDF × coefficient):</div>
        <div class="chips">${r.top_words.map(w => `<span class="chip ${w.weight > 0 ? "p" : "n"}">${esc(w.word)} ${w.weight > 0 ? "+" : ""}${w.weight.toFixed(2)}</span>`).join("")}</div>`;
    } catch { $("#result").innerHTML = `<div class="err">Could not reach the API.</div>`; }
  },
};
