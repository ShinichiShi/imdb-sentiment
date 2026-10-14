const Review = {
  movie: null, timer: null,
  async mount(el, param) {
    const lib = await loadLibrary();
    this.movie = param && App.byId[param] ? App.byId[param] : this.movie;
    el.innerHTML = `<section class="page">
      <div class="pagehead"><h1>Write a review</h1><p class="muted">Pick any of the ${lib.length.toLocaleString()} movies, write your review, and see the classifier's verdict. It is also published to Kafka, so it updates that movie's live running average.</p></div>
      <div class="grid2 rv">
        <div class="panel"><h2>1 · Choose a movie</h2>
          <input id="rq" class="search" type="search" placeholder="Search a title, e.g. Titanic…" autocomplete="off">
          <div id="rres" class="results"></div></div>
        <div class="panel"><h2>2 · Your review</h2><div id="rform"></div></div>
      </div></section>`;
    $("#rq").oninput = e => this.search(e.target.value);
    $("#rres").onclick = e => { const r = e.target.closest("[data-id]"); if (r) { this.movie = App.byId[r.dataset.id]; this.form(); } };
    this.search(""); this.form();
    await refreshLive();
  },
  search(q) {
    q = q.trim().toLowerCase();
    const l = (q ? App.library.filter(m => m.title.toLowerCase().includes(q)) : App.library).slice(0, 12);
    $("#rres").innerHTML = l.map(m => `<div class="res" data-id="${m.id}"><img src="${posterUrl(m.file)}" alt="" loading="lazy"><div><b>${esc(m.title)}</b><div class="muted small0">${m.year ?? ""} · ★ ${m.score.toFixed(1)}${m.genres[0] ? " · " + esc(m.genres[0]) : ""}</div></div></div>`).join("") || `<div class="muted">No match.</div>`;
  },
  form() {
    const m = this.movie, box = $("#rform");
    if (!m) { box.innerHTML = `<div class="muted" style="padding:30px 0">← Select a movie first.</div>`; return; }
    box.innerHTML = `<div class="picked"><img src="${posterUrl(m.file)}" alt=""><div><b>${esc(m.title)}</b><div class="muted">${m.year ?? ""} · ★ ${m.score.toFixed(1)} IMDb</div><div class="live2" id="rlive"></div></div></div>
      <textarea id="rtext" placeholder="What did you think of ${esc(m.title)}?"></textarea>
      <div class="row-between" style="margin-top:8px"><span class="muted small0" id="rcount">0 / 5000</span><button class="btn primary" id="rsend">Analyze &amp; publish</button></div>
      <div id="rout"></div>`;
    $("#rtext").oninput = e => $("#rcount").textContent = e.target.value.length + " / 5000";
    $("#rsend").onclick = () => this.send();
    this.liveBox();
  },
  liveBox() {
    const l = this.movie && App.liveById[this.movie.id], b = $("#rlive"); if (!b) return;
    b.innerHTML = l ? `Live audience sentiment <b style="color:${col(l.avg_score)}">${pct(l.avg_score, 1)}</b> · ${l.count} reviews` : `<span class="muted">No live reviews yet for this title</span>`;
  },
  async send() {
    const text = $("#rtext").value.trim(); if (text.length < 3) return;
    const btn = $("#rsend"); btn.disabled = true; btn.textContent = "Scoring…";
    const before = (App.liveById[this.movie.id] || {}).count || 0;
    try {
      const res = await fetch("/api/review", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ imdb_id: this.movie.id, review: text }) });
      if (!res.ok) throw new Error((await res.json()).detail || res.status);
      const r = await res.json(), pos = r.sentiment === "positive";
      $("#rout").innerHTML = `<div class="verdictbox ${pos ? "p" : "n"}"><div class="gauge"><i style="width:${100 - pct(r.score)}%"></i></div>
        <div class="verdict" style="color:${col(r.score)}">${pos ? "😊 Positive" : "😞 Negative"} — ${pct(r.score, 1)}% positive</div>
        <div class="muted small0">${r.published ? "Published to Kafka → processor → HDFS; the running average updates in a moment." : "Scored locally (could not publish to the stream)."}</div></div>
        <div class="muted small" >Words that drove the score:</div>
        <div class="chips">${r.top_words.map(w => `<span class="chip ${w.weight > 0 ? "p" : "n"}">${esc(w.word)} ${w.weight > 0 ? "+" : ""}${w.weight.toFixed(2)}</span>`).join("")}</div>`;
      $("#rtext").value = ""; $("#rcount").textContent = "0 / 5000";
      if (r.published) {   // wait for the pipeline to pick it up, then show the updated aggregate
        for (let i = 0; i < 8; i++) { await new Promise(r => setTimeout(r, 1000)); await refreshLive(); if (((App.liveById[this.movie.id] || {}).count || 0) > before) break; }
        this.liveBox();
      }
    } catch (e) { $("#rout").innerHTML = `<div class="err">${esc(e.message || "Could not reach the API.")}</div>`; }
    btn.disabled = false; btn.textContent = "Analyze & publish";
  },
  async update() { await refreshLive(); this.liveBox(); },
};
