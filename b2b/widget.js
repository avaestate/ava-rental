/* AVA Villa Performance Widget — embeddable stats bar for villa pages (Tilda etc.)
 * Usage:
 *   <div class="ava-stats" data-villa="aurora"></div>
 *   <script src="https://avaestate.github.io/ava-rental/b2b/widget.js" defer></script>
 * Data source: https://avaestate.github.io/ava-rental/b2b/data.json (maintained by AVA)
 * Optional attributes:
 *   data-lang="en|ru"      (default en)
 *   data-theme="dark|light" (default dark)
 */
(function () {
  "use strict";
  var DATA_URL = "https://avaestate.github.io/ava-rental/b2b/data.json";
  var L = {
    en: { months: "In operation", net: "Net / month", yld: "ROI / year", earned: "earned" },
    ru: { months: "В работе", net: "Чистыми / мес", yld: "ROI / год", earned: "earned" }
  };
  function fmtK(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n); }
  function fmtM(n) { return "฿" + (n / 1000000).toFixed(2).replace(/\.?0+$/, "") + "M"; }

  function css() {
    if (document.getElementById("ava-stats-css")) return;
    var s = document.createElement("style");
    s.id = "ava-stats-css";
    s.textContent = "" +
      ".ava-stats-box{font-family:'Manrope',-apple-system,'Helvetica Neue',Arial,sans-serif;border-radius:16px;padding:22px 26px;display:flex;flex-wrap:wrap;gap:26px;align-items:center;justify-content:space-between;max-width:1200px;margin:0 auto;box-sizing:border-box}" +
      ".ava-stats-box.dark{background:#1C2523;color:#F0E7DF}" +
      ".ava-stats-box.light{background:#F7F2EC;color:#2C3638;border:1px solid #e4dccd}" +
      ".ava-stats-kpis{display:flex;gap:14px;flex-wrap:wrap}" +
      ".ava-stats-kpi{border-radius:12px;padding:14px 18px;min-width:118px;box-sizing:border-box}" +
      ".dark .ava-stats-kpi{background:rgba(255,255,255,.055)}" +
      ".light .ava-stats-kpi{background:rgba(44,54,56,.06)}" +
      ".ava-stats-kpi span{display:block;font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;opacity:.55;font-weight:600;margin-bottom:6px}" +
      ".ava-stats-kpi b{display:block;font-size:24px;font-weight:800;letter-spacing:-.01em;line-height:1.05}" +
      ".ava-stats-kpi b small{font-size:14px;font-weight:600;opacity:.85;margin-left:2px}" +
      ".ava-stats-chart{flex:1;min-width:260px;max-width:520px;position:relative}" +
      ".ava-stats-chart svg{display:block;width:100%;height:86px}" +
      ".ava-stats-badge{position:absolute;top:-10px;left:2px;color:#4ED98A;font-size:13px;font-weight:800;letter-spacing:.01em}" +
      "@media(max-width:640px){.ava-stats-box{gap:16px;padding:18px}.ava-stats-kpis{gap:20px}.ava-stats-kpi b{font-size:21px}}";
    document.head.appendChild(s);
  }

  function chartSVG(series, theme) {
    var w = 520, h = 86, max = Math.max.apply(null, series.concat([1]));
    var stepX = w / (series.length - 1);
    var pts = series.map(function (v, i) { return [i * stepX, h - 8 - (v / max) * (h - 20)]; });
    var line = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
    var area = line + " L" + w + "," + h + " L0," + h + " Z";
    var stroke = theme === "light" ? "#2C3638" : "#DCC59A";
    var fill = theme === "light" ? "rgba(44,54,56,.10)" : "rgba(220,197,154,.16)";
    var last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none">' +
      '<path d="' + area + '" fill="' + fill + '"/>' +
      '<path d="' + line + '" fill="none" stroke="' + stroke + '" stroke-width="2.2" stroke-linecap="round"/>' +
      '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="4" fill="' + stroke + '"/></svg>';
  }

  function render(el, v, lang, theme) {
    var t = L[lang] || L.en;
    el.innerHTML =
      '<div class="ava-stats-box ' + theme + '">' +
        '<div class="ava-stats-kpis">' +
          '<div class="ava-stats-kpi"><span>' + t.months + '</span><b>' + v.months + "<small>mo</small></b></div>" +
          '<div class="ava-stats-kpi"><span>' + t.net + '</span><b>' + fmtK(v.net).toLowerCase() + "</b></div>" +
          '<div class="ava-stats-kpi"><span>' + t.yld + '</span><b>' + v.yld + "<small>%</small></b></div>" +
        "</div>" +
        '<div class="ava-stats-chart">' +
          '<div class="ava-stats-badge">▲ ' + fmtM(v.cum) + " " + t.earned + "</div>" +
          chartSVG(v.series, theme) +
        "</div>" +
      "</div>";
  }

  function init() {
    var nodes = document.querySelectorAll(".ava-stats[data-villa]");
    if (!nodes.length) return;
    css();
    fetch(DATA_URL).then(function (r) { return r.json(); }).then(function (data) {
      var map = {};
      (data.villas || []).forEach(function (v) { map[v.id] = v; });
      nodes.forEach(function (el) {
        var v = map[el.getAttribute("data-villa")];
        if (!v) { el.style.display = "none"; return; }
        render(el, v, el.getAttribute("data-lang") || "en", el.getAttribute("data-theme") || "dark");
      });
    }).catch(function () { nodes.forEach(function (el) { el.style.display = "none"; }); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
