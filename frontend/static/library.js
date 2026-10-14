const Library = {
  q: "", genre: "All", sort: "votes", liveOnly: false, shown: 0, list: [], BATCH: 48,
  async mount(el) {
    const lib = await loadLibrary();
    const cnt = {}; lib.forEach(m => m.genres.forEach(g => cnt[g] = (cnt[g] || 0) + 1));
    const genres = ["All", ...Object.entries(cnt).sort((a, b) => b[1] - a[1]).slice(0, 14).map(e => e[0])];
    el.innerHTML = `<section class="page"><div class="pagehead"><h1>Movie library</h1><p class="muted">${lib.length.toLocaleString()} posters with IMDb ratings. Titles in the live stream carry a sentiment ring — click any poster for details.</p></div>
      <div class="filters">
        <input id="lq" type="search" placeholder="Search title…" value="${esc(this.q)}">
        <select id="ls"><option value="votes">Most popular</option><option value="score">IMDb rating</option><option value="year">Newest</option><option value="live">Live sentiment</option></select>
        <label class="tog"><input type="checkbox" id="ll"> Live stream only</label><span class="muted" id="lc"></span></div>
      <div class="chips2" id="lg">${genres.map(g => `<button class="${g === this.genre ? "on" : ""}" data-g="${g}">${g}</button>`).join("")}</div>
      <div class="grid" id="lgrid"></div><div id="lsent" style="height:40px"></div></section>`;
    $("#ls").value = this.sort; $("#ll").checked = this.liveOnly;
    $("#lq").oninput = e => { this.q = e.target.value; this.apply(); };
    $("#ls").onchange = e => { this.sort = e.target.value; this.apply(); };
    $("#ll").onchange = e => { this.liveOnly = e.target.checked; this.apply(); };
    $("#lg").onclick = e => { const b = e.target.closest("button"); if (!b) return; this.genre = b.dataset.g; $$("#lg button").forEach(x => x.classList.toggle("on", x === b)); this.apply(); };
    this.io = new IntersectionObserver(es => es[0].isIntersecting && this.more(), { rootMargin: "600px" });
    this.io.observe($("#lsent"));
    await refreshLive(); this.apply();
  },
  apply() {
    const q = this.q.trim().toLowerCase();
    let l = App.library.filter(m => (this.genre === "All" || m.genres.includes(this.genre)) && (!q || m.title.toLowerCase().includes(q)) && (!this.liveOnly || App.liveById[m.id]));
    const key = { votes: m => -m.votes, score: m => -m.score, year: m => -(m.year || 0), live: m => -(App.liveById[m.id]?.avg_score ?? -1) }[this.sort];
    this.list = l.sort((a, b) => key(a) - key(b));
    this.shown = 0; $("#lgrid").innerHTML = ""; $("#lc").textContent = `${this.list.length.toLocaleString()} movies`;
    this.more();
  },
  more() {
    if (this.shown >= this.list.length) return;
    $("#lgrid").insertAdjacentHTML("beforeend", this.list.slice(this.shown, this.shown + this.BATCH).map(posterCard).join(""));
    this.shown += this.BATCH;
  },
  async update(el) { await refreshLive(); refreshRings(el); },
  unmount() { this.io && this.io.disconnect(); },
};
