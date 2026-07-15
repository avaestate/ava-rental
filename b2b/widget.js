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
    en: { months: "In operation", net: "Net / month", yld: "ROI / year", earned: "earned",
      tip: "Cumulative net income earned by this villa since it started operating. The chart shows monthly net income for the last 12 months — hover the trend to see the villa's earning momentum." },
    ru: { months: "В работе", net: "Чистыми / мес", yld: "ROI / год", earned: "earned",
      tip: "Накопленный чистый доход виллы с начала работы. График — чистый доход по месяцам за последние 12 месяцев: видно динамику заработка." }
  };
  function fmtK(n) { return n >= 1000 ? Math.round(n / 1000) + "K" : String(n); }
  function fmtM(n) { return "฿" + (n / 1000000).toFixed(2).replace(/\.?0+$/, "") + "M"; }

  function css() {
    if (document.getElementById("ava-stats-css")) return;
    var s = document.createElement("style");
    s.id = "ava-stats-css";
    s.textContent = "" +
      ".ava-stats-box{font-family:'Manrope',-apple-system,'Helvetica Neue',Arial,sans-serif;border-radius:10px;padding:10px;display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between;max-width:1200px;margin:0 auto;box-sizing:border-box}" +
      ".ava-stats-box.dark{background:#293638;color:#F0E7DF}" +
      ".ava-stats-box.light{background:#F7F2EC;color:#2C3638;border:1px solid #e4dccd}" +
      ".ava-stats-kpis{display:flex;gap:10px;flex-wrap:wrap}" +
      ".ava-stats-kpi{border-radius:8px;padding:16px 20px;min-width:150px;box-sizing:border-box}" +
      ".dark .ava-stats-kpi{background:#3F4A4C}" +
      ".light .ava-stats-kpi{background:rgba(44,54,56,.06)}" +
      ".ava-stats-kpi span{display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#75878B;font-weight:600;margin-bottom:10px}" +
      ".light .ava-stats-kpi span{color:#75878B}" +
      ".ava-stats-kpi b{display:block;font-size:18px;font-weight:700;letter-spacing:-.01em;line-height:1}" +
      ".ava-stats-kpi b small{font-size:13px;font-weight:600;opacity:.8;margin-left:3px}" +
      ".ava-stats-chart{flex:1;min-width:280px;max-width:560px;box-sizing:border-box;padding:10px 40px}" +
      ".ava-stats-chart svg{display:block;width:100%;height:64px;overflow:visible}" +
      ".ava-stats-badge{display:block;color:#8BE28B;font-size:14px;font-weight:700;letter-spacing:.01em;margin-bottom:8px;position:relative}" +
      ".ava-stats-help{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;margin-left:6px;border-radius:50%;border:1.2px solid #75878B;color:#75878B;font-size:11px;font-weight:700;cursor:pointer;vertical-align:1px;user-select:none}" +
      ".ava-stats-tip{display:none;position:absolute;left:0;top:24px;z-index:9;max-width:290px;background:#1E2829;color:#DDE4E1;font-size:12px;font-weight:500;line-height:1.5;letter-spacing:0;padding:10px 12px;border-radius:8px;box-shadow:0 6px 20px rgba(0,0,0,.35)}" +
      ".ava-stats-tip.open{display:block}" +
      "@media(max-width:640px){.ava-stats-box{gap:10px;padding:10px}.ava-stats-kpis{gap:10px}.ava-stats-kpi{min-width:104px;padding:12px 14px}.ava-stats-chart{padding:10px 16px}}";
    document.head.appendChild(s);
  }

  var GRAD_N = 0;
  function chartSVG(series, theme) {
    var w = 520, h = 86, max = Math.max.apply(null, series.concat([1]));
    var stepX = w / (series.length - 1);
    var pts = series.map(function (v, i) { return [i * stepX, h - 8 - (v / max) * (h - 20)]; });
    var line = pts.map(function (p, i) { return (i ? "L" : "M") + p[0].toFixed(1) + "," + p[1].toFixed(1); }).join(" ");
    var area = line + " L" + w + "," + h + " L0," + h + " Z";
    var stroke = theme === "light" ? "#2C3638" : "#C9D2CE";
    var gid = "ava-stats-grad-" + (++GRAD_N);
    var last = pts[pts.length - 1];
    return '<svg viewBox="0 0 ' + w + " " + h + '" preserveAspectRatio="none">' +
      '<defs><linearGradient id="' + gid + '" x1="0" y1="0" x2="0" y2="1">' +
        '<stop offset="0%" stop-color="' + stroke + '" stop-opacity=".28"/>' +
        '<stop offset="100%" stop-color="' + stroke + '" stop-opacity="0"/>' +
      "</linearGradient></defs>" +
      '<path d="' + area + '" fill="url(#' + gid + ')"/>' +
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
          '<div class="ava-stats-badge">▲ ' + fmtM(v.cum) + " " + t.earned +
            '<span class="ava-stats-help" role="button" tabindex="0" aria-label="What is this chart?">?</span>' +
            '<span class="ava-stats-tip">' + t.tip + "</span>" +
          "</div>" +
          chartSVG(v.series, theme) +
        "</div>" +
      "</div>";
    var help = el.querySelector(".ava-stats-help");
    var tip = el.querySelector(".ava-stats-tip");
    if (help && tip) {
      help.addEventListener("click", function (e) { e.stopPropagation(); tip.classList.toggle("open"); });
      document.addEventListener("click", function () { tip.classList.remove("open"); });
    }
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
