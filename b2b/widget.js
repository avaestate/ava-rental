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
    en: { months: "months on market", net: "avg net / month", yld: "annual yield", earned: "earned since", title: "" },
    ru: { months: "месяцев в работе", net: "чистыми / месяц", yld: "годовая доходность", earned: "заработано с", title: "" }
  };
  function fmtK(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n); }
  function fmtM(n) { return "฿" + (n / 1000000).toFixed(2).replace(/\.?0+$/, "") + "M"; }

  function css() {
    if (document.getElementById("ava-stats-css")) return;
    var s = document.createElement("style");
    s.id = "ava-stats-css";
    s.textContent = "" +
      ".ava-stats-box{font-family:'Manrope',-apple-system,'Helvetica Neue',Arial,sans-serif;border-radius:16px;padding:22px 26px;display:flex;flex-wrap:wrap;gap:26px;align-items:center;justify-content:space-between;max-width:1200px;margin:0 auto;box-sizing:border-box}" +
      ".ava-stats-box.dark{background:#1F2B29;color:#F0E7DF}" +
      ".ava-stats-box.light{background:#F7F2EC;color:#2C3638;border:1px solid #e4dccd}" +
      ".ava-stats-kpis{display:flex;gap:34px;flex-wrap:wrap}" +
      ".ava-stats-kpi b{display:block;font-size:26px;font-weight:800;letter-spacing:-.01em;line-height:1.1}" +
      ".ava-stats-kpi span{display:block;font-size:11px;letter-spacing:.08em;text-transform:uppercase;opacity:.65;margin-top:4px;font-weight:600}" +
      ".ava-stats-chart{flex:1;min-width:260px;max-width:520px;position:relative}" +
      ".ava-stats-chart svg{display:block;width:100%;height:86px}" +
      ".ava-stats-badge{position:absolute;top:-6px;right:0;background:#2FBF71;color:#fff;font-size:11px;font-weight:800;padding:4px 10px;border-radius:20px;letter-spacing:.02em}" +
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
          '<div class="ava-stats-kpi"><b>' + v.months + ' mo</b><span>' + t.months + "</span></div>" +
          '<div class="ava-stats-kpi"><b>฿' + fmtK(v.net) + '</b><span>' + t.net + "</span></div>" +
          '<div class="ava-stats-kpi"><b>' + v.yld + '%</b><span>' + t.yld + "</span></div>" +
        "</div>" +
        '<div class="ava-stats-chart">' +
          '<div class="ava-stats-badge">▲ ' + fmtM(v.cum) + " " + t.earned + " " + v.since + "</div>" +
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
