const Home = {
  async mount(el) {
    const lib = await loadLibrary();
    const pool = lib.slice(0, 150), rows = [0, 1, 2, 3].map(r => pool.filter((_, i) => i % 4 === r).slice(0, 30));
    const marquee = rows.map((row, i) => {
      const imgs = row.map(m => `<img src="${posterUrl(m.file)}" alt="" loading="lazy">`).join("");
      return `<div class="mrow ${i % 2 ? "rev" : ""}" style="--d:${80 + i * 12}s"><div class="track">${imgs}${imgs}</div></div>`;
    }).join("");
    const top = lib.filter(m => m.votes > 150000).sort((a, b) => b.score - a.score).slice(0, 24);
    el.innerHTML = `
    <section class="hero">
      <div class="marquee" aria-hidden="true">${marquee}</div><div class="shade"></div>
      <div class="hero-in">
        <div class="kicker">Big Data Analytics · Streaming NLP</div>
        <h1>Know how the audience feels —<br><span class="grad">while the credits still roll.</span></h1>
        <p>Movie reviews stream through <b>Kafka</b>, land on <b>HDFS</b>, and are scored by a <b>TF-IDF + logistic regression</b> model.
           A running sentiment score per title replaces days of manual reporting.</p>
        <div class="cta"><a class="btn primary" href="#/library">Browse the library</a><a class="btn" href="#/dashboard">Open live dashboard</a></div>
        <div class="strip" id="hstrip"></div>
      </div>
    </section>
    <section class="sec"><div class="sechead"><h2>Live in the stream</h2><span class="muted">Ring = live audience sentiment · ★ = IMDb rating · sorted by sentiment</span>
        <div class="arrows"><button data-dir="-1">‹</button><button data-dir="1">›</button></div></div>
      <div class="rail" id="railLive"></div></section>
    <section class="sec"><div class="sechead"><h2>Highest rated of all time</h2><span class="muted">from the poster archive</span>
        <div class="arrows"><button data-dir="-1">‹</button><button data-dir="1">›</button></div></div>
      <div class="rail">${top.map(posterCard).join("")}</div></section>
    <section class="sec"><div class="sechead"><h2>How it works</h2></div>
      <div class="steps">
        ${[["1", "Stream", "A producer replays IMDB reviews into a Kafka topic, keyed by movie title.", "Kafka"],
           ["2", "Store", "A stream processor writes raw and scored micro-batches to HDFS as part files.", "HDFS"],
           ["3", "Classify", "TF-IDF features feed a logistic regression: P(positive) for every review.", "scikit-learn"],
           ["4", "Aggregate", "A running average per title powers the dashboard in near real time.", "FastAPI"]]
          .map(s => `<div class="step"><span class="n">${s[0]}</span><h3>${s[1]}</h3><p>${s[2]}</p><em>${s[3]}</em></div>`).join("")}
      </div></section>`;
    $$(".arrows button", el).forEach(b => b.onclick = () => { const r = b.closest(".sec").querySelector(".rail"); r.scrollBy({ left: b.dataset.dir * r.clientWidth * .8, behavior: "smooth" }); });
    await this.update(el, true);
  },
  async update(el, first) {
    await refreshLive();
    const s = App.summary, m = App.pipeline.model;
    $("#hstrip").innerHTML = [[s.total.toLocaleString(), "reviews scored"], [App.live.length, "titles tracked live"],
      [s.avg_score == null ? "–" : pct(s.avg_score, 1), "avg sentiment (0–100)"], [m.accuracy ? pct(m.accuracy, 1) + "%" : "–", "model accuracy"]]
      .map(x => `<div><b>${x[0]}</b><span>${x[1]}</span></div>`).join("");
    if (first) {
      const ids = [...App.live].sort((a, b) => b.avg_score - a.avg_score).map(l => App.byId[l.imdb_id]).filter(Boolean);
      $("#railLive").innerHTML = ids.map(posterCard).join("") || `<div class="muted">Waiting for the stream…</div>`;
    }
    refreshRings(el);
  },
};

function refreshRings(root) {
  $$(".card[data-id]", root).forEach(c => {
    const live = App.liveById[c.dataset.id], box = $(".pimg", c), old = $(".ring", c);
    if (!live) return;
    if (old) { old.style.setProperty("--p", Math.round(live.avg_score * 100)); old.style.setProperty("--c", live.avg_score >= .5 ? "var(--pos)" : "var(--neg)"); $("i", old).textContent = Math.round(live.avg_score * 100); }
    else box.insertAdjacentHTML("beforeend", ring(live.avg_score));
  });
}
