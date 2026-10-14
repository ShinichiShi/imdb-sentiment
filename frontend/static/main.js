/* light / dark theme (initial value is set by the inline script in index.html) */
function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#themeBtn").textContent = t === "light" ? "🌙" : "☀️";
  try { localStorage.setItem("theme", t); } catch (e) {}
}
$("#themeBtn").onclick = () => applyTheme(document.documentElement.dataset.theme === "light" ? "dark" : "light");
$("#themeBtn").textContent = document.documentElement.dataset.theme === "light" ? "🌙" : "☀️";

const ROUTES = { home: Home, library: Library, dashboard: Dashboard, analysis: Analysis, review: Review };
let current = null, timer = null, token = 0;

async function route() {
  const parts = (location.hash.replace(/^#\/?/, "") || "home").split("/"), name = parts[0], param = parts[1];
  const view = ROUTES[name] || Home, key = ROUTES[name] ? name : "home";
  if (current && current.unmount) current.unmount();
  closeMovie(); clearInterval(timer);
  $$("#links a").forEach(a => a.classList.toggle("on", a.dataset.r === key));
  const my = ++token, el = $("#view"); current = view;
  el.className = "view fade"; el.innerHTML = `<div class="loading">Loading…</div>`; window.scrollTo(0, 0);
  try { await view.mount(el, param); } catch (e) { console.error(e); if (my === token) el.innerHTML = `<div class="loading">Could not reach the API. Is the backend running?</div>`; return; }
  if (my !== token) return;
  timer = setInterval(() => view.update && view.update(el).catch(console.error), 2500);
}
window.addEventListener("hashchange", route);
route();
