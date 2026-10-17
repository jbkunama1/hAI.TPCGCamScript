(function () {
  var $ = function (id) { return document.getElementById(id); };
  if (!$("snap-form")) return;

  function mode() {
    return document.querySelector('input[name="snap-mode"]:checked').value;
  }

  function applyVisibility() {
    var src = $("snap-source").value;
    $("snap-reolink").style.display = src === "reolink" ? "" : "none";
    $("snap-custom").style.display = src === "custom" ? "" : "none";
    $("snap-fields").style.opacity = mode() === "snapshot" ? "1" : "0.55";
  }

  function collect() {
    return {
      mode: mode(),
      source: $("snap-source").value,
      host: $("snap-host").value,
      port: $("snap-port").value,
      https: $("snap-https").checked,
      channel: $("snap-channel").value,
      url: $("snap-url").value,
      user: $("snap-user").value,
      password: $("snap-pass").value,
      verify_tls: $("snap-verify").checked,
      interval: $("snap-interval").value,
      target: $("snap-target").value
    };
  }

  function fill(c, targets) {
    var sel = $("snap-target");
    if (targets && !sel.options.length) {
      Object.keys(targets).forEach(function (k) {
        var o = document.createElement("option");
        o.value = k;
        o.textContent = targets[k];
        sel.appendChild(o);
      });
    }
    document.querySelector('input[name="snap-mode"][value="' + c.mode + '"]').checked = true;
    $("snap-source").value = c.source;
    $("snap-host").value = c.host || "";
    $("snap-port").value = c.port || "";
    $("snap-https").checked = !!c.https;
    $("snap-channel").value = c.channel;
    $("snap-url").value = c.url || "";
    $("snap-user").value = c.user || "";
    $("snap-pass").value = "";
    $("snap-pass").placeholder = c.password ? "(gespeichert – leer lassen zum Beibehalten)" : "Passwort";
    $("snap-verify").checked = !!c.verify_tls;
    $("snap-interval").value = c.interval;
    sel.value = c.target;
    applyVisibility();
  }

  function renderStatus(st) {
    var lines = [];
    if (st && st.last_run) {
      lines.push((st.ok ? "OK    " : "FEHLER") + "  " + st.last_run + "  " + (st.message || ""));
      if (st.last_success) lines.push("Letzter Erfolg: " + st.last_success + "  " + (st.file || ""));
    } else {
      lines.push("(noch kein Abruf durchgeführt)");
    }
    $("snap-status-view").textContent = lines.join("\n");
  }

  async function load() {
    try {
      var r = await fetch("/api/snapshot");
      var d = await r.json();
      if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
      fill(d.config, d.targets);
      renderStatus(d.status);
    } catch (e) {
      $("snap-msg").textContent = "❌ Fehler beim Laden: " + e;
    }
  }

  async function refreshStatus() {
    try {
      var r = await fetch("/api/snapshot");
      if (r.ok) renderStatus((await r.json()).status);
    } catch (e) { /* ignorieren */ }
  }

  $("snap-source").addEventListener("change", applyVisibility);
  Array.prototype.forEach.call(document.querySelectorAll('input[name="snap-mode"]'), function (el) {
    el.addEventListener("change", applyVisibility);
  });

  $("snap-form").addEventListener("submit", async function (ev) {
    ev.preventDefault();
    try {
      var r = await fetch("/api/snapshot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collect())
      });
      var d = await r.json();
      if (!r.ok) throw new Error(d.error || ("HTTP " + r.status));
      $("snap-msg").textContent = "✅ Gespeichert – Modus: " + d.config.mode +
        (d.config.mode === "snapshot" ? " (Abruf startet innerhalb weniger Sekunden)" : " (kein Abruf, nur FTP)");
      fill(d.config);
      if (typeof loadAudit === "function") loadAudit();
    } catch (e) {
      $("snap-msg").textContent = "❌ " + e.message;
    }
  });

  $("snap-test").addEventListener("click", async function () {
    $("snap-msg").textContent = "⏳ Test-Abruf läuft…";
    try {
      var r = await fetch("/api/snapshot/test", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(collect())
      });
      var d = await r.json();
      $("snap-msg").textContent = (d.ok ? "✅ " : "❌ ") + (d.message || d.error || ("HTTP " + r.status));
    } catch (e) {
      $("snap-msg").textContent = "❌ " + e;
    }
  });

  load();
  setInterval(refreshStatus, 10000);
})();
