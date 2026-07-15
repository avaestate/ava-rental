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
      ".ava-stats-box{font-family:'Manrope',-apple-system,'Helvetica Neue',Arial,sans-serif;border-radius:10px;padding:16px;display:flex;flex-wrap:wrap;gap:20px;align-items:center;justify-content:space-between;max-width:1200px;margin:0 auto;box-sizing:border-box}" +
      ".ava-stats-box.dark{background:#293638;color:#F0E7DF}" +
      ".ava-stats-box.light{background:#F7F2EC;color:#2C3638;border:1px solid #e4dccd}" +
      ".ava-stats-kpis{display:flex;gap:12px;flex-wrap:wrap}" +
      ".ava-stats-kpi{border-radius:8px;padding:16px 20px;min-width:150px;box-sizing:border-box}" +
      ".dark .ava-stats-kpi{background:#3F4A4C}" +
      ".light .ava-stats-kpi{background:rgba(44,54,56,.06)}" +
      ".ava-stats-kpi span{display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#75878B;font-weight:600;margin-bottom:10px}" +
      ".light .ava-stats-kpi span{color:#75878B}" +
      ".ava-stats-kpi b{display:block;font-size:18px;font-weight:700;letter-spacing:-.01em;line-height:1}" +
      ".ava-stats-kpi b small{font-size:13px;font-weight:600;opacity:.8;margin-left:3px}" +
      ".ava-stats-chart{flex:1;min-width:280px;max-width:560px;box-sizing:border-box;padding:10px 40px}" +
      ".ava-stats-chart svg{display:block;width:100%;height:64px;overflow:visible}" +
      ".ava-stats-badge{display:block;color:#8BE28B;font-size:14px;font-weight:700;letter-spacing:.01em;margin-bottom:8px}" +
      "@media(max-width:640px){.ava-stats-box{gap:14px;padding:14px}.ava-stats-kpis{gap:10px}.ava-stats-kpi{min-width:104px;padding:12px 14px}.ava-stats-chart{padding:10px 16px}}";
    document.head.appendChild(s);
  }

  function chartSVG(series, theme) {
    var w = 520, h = 86, max = Math.max.apply(null, series.concat([1]));
    var stepX = w / (series.length - 1);
    var pts = series.map(function (v, i) { return [i * stepX, h - 8 - (v / max) * (h - 20)]; });
    var line = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
    var area = line + " L" + w + "," + h + " L0," + h + " Z";
    var stroke = theme === "light" ? "#2C3638" : "#C9D2CE";
    var fill = theme === "light" ? "rgba(44,54,56,.10)" : "rgba(201,210,206,.12)";
    var last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none">' +
      '<path d="' + area + '" fill="' + fill + '"/>' +
      '<path d="' + line + '" fill="none" stroke="' + stroke + '" stroke-width="1.8" stroke-linecap="round"/>' +
      '<circle cx="' + last[0] + '" cy="' + last[1] + '" r="5" fill="' + stroke + '"/></svg>';
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
