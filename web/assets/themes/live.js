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

/* ---- Live-Config aus /api/live-config (Admin > Seiten-Anpassung) ---- */

function camKey(img) {
  const src = img.dataset.src || "";
  if (src.indexOf("/tennis/") !== -1) return "tennis";
  if (src.indexOf("webcam2_") !== -1) return "padel2";
  if (src.indexOf("/padel/") !== -1) return "padel1";
  return null;
}

function setText(el, value) {
  if (el && value) { el.textContent = value; }
}

function setCaption(cam, value) {
  if (!value) { return; }
  const p = cam.querySelector("p");
  if (!p) { return; }
  const italic = p.querySelector("i");
  (italic || p).textContent = value;
}

function applyConfig(cfg) {
  const body = document.body;

  if (cfg.columns === "1") { body.classList.add("cfg-cols-1"); }
  if (cfg.columns === "2") { body.classList.add("cfg-cols-2"); }
  body.classList.add("cfg-img-" + (cfg.image_size || "large"));

  const texts = cfg.texts || {};
  setText(document.querySelector(".ueberschrift-container h1"), texts.title);
  setText(document.querySelector(".ueberschrift-container h2"), texts.subtitle);
  setText(document.querySelector(".action-bar p"), texts.intro);

  document.querySelectorAll(".cam").forEach(function (cam) {
    const img = cam.querySelector("img[data-src]");
    if (!img) { return; }
    const key = camKey(img);
    const isPadel = (key === "padel1" || key === "padel2");

    if (cfg.cams === "tennis" && isPadel) { cam.classList.add("cfg-hidden"); }
    if (cfg.cams === "padel" && key === "tennis") { cam.classList.add("cfg-hidden"); }

    const h3 = cam.querySelector("h3");
    if (key === "tennis") {
      setText(h3, texts.tennis_title);
      setCaption(cam, texts.tennis_caption);
    } else if (key === "padel1") {
      setText(h3, texts.padel1_title);
      setCaption(cam, texts.padel1_caption);
    } else if (key === "padel2") {
      setText(h3, texts.padel2_title);
      setCaption(cam, texts.padel2_caption);
    }
  });
}

async function loadConfig() {
  try {
    const r = await fetch("/api/live-config");
    if (!r.ok) return;
    applyConfig(await r.json());
  } catch (e) { /* Config optional – Theme-Standard bleibt */ }
}

loadConfig();
updateImages();
setInterval(updateImages, REFRESH_MS);
loadLinks();
