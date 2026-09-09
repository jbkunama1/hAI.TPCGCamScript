/* hAI.TPCGCamScript - gemeinsames Live-Skript fuer alle Themes */
const REFRESH_MS = 30000;

function updateImages() {
  const ts = Date.now();
  document.querySelectorAll("img[data-src]").forEach(function (img) {
    const url = img.dataset.src + "?t=" + ts;
    const tmp = new Image();
    tmp.onload = function () { img.src = url; };
    tmp.src = url;
  });
  const now = new Date().toLocaleTimeString("de-DE");
  const status = document.getElementById("status");
  if (status) {
    status.textContent = "✅ Letzter Refresh: " + now + " (automatisch alle " + (REFRESH_MS / 1000) + " s)";
    fetchWorkerStatus(status);
  }
}

async function fetchWorkerStatus(statusEl) {
  try {
    const r = await fetch("/output/status.json?t=" + Date.now());
    if (!r.ok) return;
    const s = await r.json();
    if (s && s.last_run) statusEl.textContent += " | ⚙️ Worker zuletzt aktiv: " + s.last_run;
  } catch (e) { /* status.json ist optional */ }
}

/* Links aus der SQLite-DB (im Admin-Bereich gepflegt), optional mit Bild */
async function loadLinks() {
  try {
    const r = await fetch("/api/links");
    if (!r.ok) return;
    const d = await r.json();
    const bar = document.querySelector(".action-bar");
    if (!bar) return;
    (d.links || []).forEach(function (l) {
      const a = document.createElement("a");
      a.className = "btn btn-link";
      a.href = l.url;
      a.target = "_blank";
      a.rel = "noopener";
      if (l.image) {
        const im = document.createElement("img");
        im.src = l.image;
        im.alt = "";
        a.appendChild(im);
      }
      a.appendChild(document.createTextNode((l.icon ? l.icon + " " : "") + l.title));
      bar.appendChild(a);
    });
  } catch (e) { /* Links optional */ }
}

updateImages();
setInterval(updateImages, REFRESH_MS);
loadLinks();
