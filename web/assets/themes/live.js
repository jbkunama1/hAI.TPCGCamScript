/* Gemeinsames Skript aller Themes:
   - updateImages(): periodischer Bild-Refresh mit Cache-Buster
   - /api/live-config: Spalten, Bildgroesse, Cam-Filter, Texte
   - /api/links: optionale Link-Leiste ueber der Statuszeile */
(function () {
  "use strict";

  var REFRESH_MS = 30000;

  window.updateImages = function () {
    var now = Date.now();
    document.querySelectorAll("img[data-src]").forEach(function (img) {
      img.src = img.getAttribute("data-src") + "?t=" + now;
    });
    var status = document.getElementById("status");
    if (status) {
      status.textContent = "✅ Bilder aktualisiert: " + new Date().toLocaleTimeString("de-DE");
    }
  };

  // Cam anhand des Bildpfads erkennen
  function camKey(img) {
    var src = img.getAttribute("data-src") || "";
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
    var p = cam.querySelector("p");
    if (!p) { return; }
    var italic = p.querySelector("i");
    (italic || p).textContent = value;
  }

  function applyConfig(cfg) {
    var body = document.body;

    if (cfg.columns === "1") { body.classList.add("cfg-cols-1"); }
    if (cfg.columns === "2") { body.classList.add("cfg-cols-2"); }
    body.classList.add("cfg-img-" + (cfg.image_size || "large"));

    var texts = cfg.texts || {};
    setText(document.querySelector(".ueberschrift-container h1"), texts.title);
    setText(document.querySelector(".ueberschrift-container h2"), texts.subtitle);
    setText(document.querySelector(".action-bar p"), texts.intro);

    document.querySelectorAll(".cam").forEach(function (cam) {
      var img = cam.querySelector("img[data-src]");
      if (!img) { return; }
      var key = camKey(img);
      var isPadel = (key === "padel1" || key === "padel2");

      if (cfg.cams === "tennis" && isPadel) { cam.classList.add("cfg-hidden"); }
      if (cfg.cams === "padel" && key === "tennis") { cam.classList.add("cfg-hidden"); }

      var h3 = cam.querySelector("h3");
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

  function loadConfig() {
    fetch("/api/live-config")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (cfg) { if (cfg) { applyConfig(cfg); } })
      .catch(function () { /* Config optional – Theme-Standard bleibt */ });
  }

  function loadLinks() {
    fetch("/api/links")
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (d) {
        if (!d || !d.links || !d.links.length) { return; }
        var bar = document.createElement("div");
        bar.className = "links-bar";
        d.links.forEach(function (l) {
          var a = document.createElement("a");
          a.href = l.url;
          a.target = "_blank";
          a.rel = "noopener";
          a.textContent = (l.icon ? l.icon + " " : "") + l.title;
          bar.appendChild(a);
        });
        var status = document.getElementById("status");
        if (status && status.parentNode) {
          status.parentNode.insertBefore(bar, status);
        }
      })
      .catch(function () { /* Links optional */ });
  }

  document.addEventListener("DOMContentLoaded", function () {
    loadConfig();
    loadLinks();
    window.updateImages();
    setInterval(window.updateImages, REFRESH_MS);
  });
})();
