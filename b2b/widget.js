/* AVA Villa Performance Widget — embeddable stats panel for villa pages (Tilda etc.)
 * Layout per Figma frame 1410-1072 (Frame 1339, 1040×285).
 * Usage:
 *   <div class="ava-stats" data-villa="aurora"></div>
 *   <script src="https://avaestate.github.io/ava-rental/b2b/widget.js" defer></script>
 * Data source: https://avaestate.github.io/ava-rental/b2b/data.json (maintained by AVA)
 * Optional attributes:
 *   data-lang="en|ru"      (default en)
 */
(function () {
  "use strict";
  var DATA_URL = "https://avaestate.github.io/ava-rental/b2b/data.json";
  var L = {
    en: {
      months: "In operation", net: "Net / month", yld: "ROI / year",
      earned: "Earned since launch", back: "% of price back",
      payback: function (y) { return "Full payback in ≈ " + y + " years, then pure income – and the villa itself stays yours."; },
      occ: "Occupancy", adr: "ADR", since: "Since",
      live: "Live · updated daily",
      chart: "Net monthly profit,<br>last 12 months",
      mo: "mo"
    },
    ru: {
      months: "В работе", net: "Чистыми / мес", yld: "ROI / год",
      earned: "Заработано с запуска", back: "% цены возвращено",
      payback: function (y) { return "Полная окупаемость ≈ " + y + " лет, дальше — чистый доход, а вилла остаётся вашей."; },
      occ: "Загрузка", adr: "Ставка / ночь", since: "Старт",
      live: "Live · обновляется ежедневно",
      chart: "Чистая прибыль по месяцам,<br>последние 12 мес",
      mo: "мес"
    }
  };

  function fmtK(n) { return n >= 1000 ? Math.round(n / 1000) + "k" : String(n); }
  function fmtNum(n) { return String(Math.round(n)).replace(/\B(?=(\d{3})+(?!\d))/g, " "); }
  function fmtUSD(thb, fx) { return fx ? "≈ $" + fmtNum(thb / fx) : ""; }

  function css() {
    if (document.getElementById("ava-stats-css")) return;
    var s = document.createElement("style");
    s.id = "ava-stats-css";
    s.textContent = "" +
      ".ava-stats-box{font-family:'Manrope',-apple-system,'Helvetica Neue',Arial,sans-serif;background:#293638;color:#FFFFFF;border-radius:10px;padding:10px;display:flex;gap:40px;max-width:1040px;margin:0 auto;box-sizing:border-box}" +
      ".ava-stats-box *{box-sizing:border-box}" +
      ".ava-stats-left{flex:0 0 460px;display:flex;flex-direction:column;gap:10px}" +
      ".ava-stats-kpis{display:flex;gap:10px}" +
      ".ava-stats-kpi{flex:1;background:#3F4A4C;border-radius:8px;padding:16px 20px}" +
      ".ava-stats-kpi span{display:block;font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:#75878B;font-weight:600;margin-bottom:10px;white-space:nowrap}" +
      ".ava-stats-kpi b{display:block;font-size:18px;font-weight:700;line-height:1;white-space:nowrap}" +
      ".ava-stats-kpi b small{font-size:13px;font-weight:600;opacity:.75;margin-left:3px}" +
      ".ava-stats-usd{display:block;font-size:11px;font-weight:600;color:#8FA3A8;margin-top:5px;white-space:nowrap}" +
      ".ava-stats-earned{background:#3F4A4C;border-radius:8px;padding:16px 20px;flex:1;display:flex;flex-direction:column;justify-content:space-between;gap:8px}" +
      ".ava-stats-earned .row{display:flex;justify-content:space-between;align-items:baseline;gap:10px}" +
      ".ava-stats-earned .lbl{font-size:13px;color:#C3CDCA;font-weight:500}" +
      ".ava-stats-earned .back{font-size:13px;color:#8BE28B;font-weight:600;white-space:nowrap}" +
      ".ava-stats-earned .val{font-size:24px;font-weight:700;line-height:1.1}" +
      ".ava-stats-bar{height:4px;border-radius:2px;background:rgba(255,255,255,.14);overflow:hidden}" +
      ".ava-stats-bar i{display:block;height:100%;border-radius:2px;background:#C9D2CE}" +
      ".ava-stats-earned .cap{font-size:12px;line-height:1.5;color:#75878B}" +
      ".ava-stats-right{flex:1;min-width:0;display:flex;flex-direction:column;padding:10px 10px 6px 0}" +
      ".ava-stats-meta{display:flex;align-items:flex-start;gap:56px;border-bottom:1px solid rgba(255,255,255,.09);padding-bottom:14px}" +
      ".ava-stats-meta .m span{display:block;font-size:12px;color:#75878B;font-weight:500;margin-bottom:4px;white-space:nowrap}" +
      ".ava-stats-meta .m b{font-size:14px;font-weight:600;white-space:nowrap}" +
      ".ava-stats-live{margin-left:auto;font-size:12px;color:#8BE28B;font-weight:500;white-space:nowrap}" +
      ".ava-stats-live i{display:inline-block;width:6px;height:6px;border-radius:50%;background:#8BE28B;margin-right:6px;vertical-align:1px}" +
      ".ava-stats-ct{font-size:13px;line-height:1.4;color:#D2C6BC;margin:16px 0 8px;font-weight:500}" +
      ".ava-stats-bars{flex:1;display:flex;align-items:flex-end;gap:8px;min-height:96px;border-bottom:1px solid rgba(255,255,255,.09)}" +
      ".ava-stats-col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;min-width:0}" +
      ".ava-stats-col .v{font-size:11px;color:#E4EAE7;font-weight:600;margin-bottom:4px;white-space:nowrap}" +
      ".ava-stats-col .b{width:100%;border-radius:3px 3px 0 0;background:rgba(201,210,206,.38)}" +
      ".ava-stats-col .b.max{background:#C9D2CE}" +
      ".ava-stats-months{display:flex;gap:8px;margin-top:6px}" +
      ".ava-stats-months .m{flex:1;text-align:center;font-size:11px;color:#75878B;font-weight:500;min-width:0}" +
      ".ava-stats{container-type:inline-size}" +
      "@container(max-width:920px){.ava-stats-box{flex-direction:column;gap:16px}.ava-stats-left{flex:none;width:100%}.ava-stats-right{padding:0 10px 6px}}" +
      "@container(max-width:640px){.ava-stats-kpis{flex-wrap:wrap}.ava-stats-kpi{flex:1 1 calc(33% - 10px);min-width:96px;padding:12px 12px}.ava-stats-kpi b{font-size:16px}.ava-stats-meta{flex-wrap:wrap;gap:14px 20px}.ava-stats-live{margin-left:0;width:100%;order:9}.ava-stats-bars{gap:4px}.ava-stats-col .v{font-size:9px;margin-bottom:2px}.ava-stats-col .m{font-size:9px}.ava-stats-earned .val{font-size:20px}}" +
      "@media(max-width:920px){.ava-stats-box{flex-direction:column;gap:16px}.ava-stats-left{flex:none;width:100%}.ava-stats-right{padding:0 10px 6px}}" +
      "@media(max-width:640px){.ava-stats-kpis{flex-wrap:wrap}.ava-stats-kpi{flex:1 1 calc(33% - 10px);min-width:96px;padding:12px 12px}.ava-stats-kpi b{font-size:16px}.ava-stats-meta{flex-wrap:wrap;gap:14px 20px}.ava-stats-live{margin-left:0;width:100%;order:9}.ava-stats-bars{gap:4px}.ava-stats-col .v{font-size:9px}.ava-stats-col .m{font-size:9px}.ava-stats-earned .val{font-size:20px}}";
    document.head.appendChild(s);
  }

  function bars(series) {
    var max = Math.max.apply(null, series.concat([1]));
    var MAXH = 96; // px, tallest bar
    return series.map(function (v) {
      var h = v > 0 ? Math.max(3, Math.round(v / max * MAXH)) : 0;
      return '<div class="ava-stats-col">' +
        (v > 0 ? '<div class="v">' + fmtK(v) + "</div>" : "") +
        (v > 0 ? '<div class="b' + (v === max ? " max" : "") + '" style="height:' + h + 'px"></div>' : "") +
      "</div>";
    }).join("");
  }
  function months(labels) {
    return (labels || []).map(function (l) { return '<div class="m">' + (l || "") + "</div>"; }).join("");
  }

  function render(el, v, lang, fx) {
    var t = L[lang] || L.en;
    var pct = v.price ? Math.max(1, Math.round(v.cum / v.price * 100)) : null;
    var payback = v.price && v.net ? Math.round(v.price / (v.net * 12)) : null;
    el.innerHTML =
      '<div class="ava-stats-box">' +
        '<div class="ava-stats-left">' +
          '<div class="ava-stats-kpis">' +
            '<div class="ava-stats-kpi"><span>' + t.months + '</span><b>' + v.months + "<small>" + t.mo + "</small></b></div>" +
            '<div class="ava-stats-kpi"><span>' + t.net + '</span><b>' + fmtNum(v.net) + "<small>THB</small></b>" +
              (fx ? '<span class="ava-stats-usd">' + fmtUSD(v.net, fx) + "</span>" : "") + "</div>" +
            '<div class="ava-stats-kpi"><span>' + t.yld + '</span><b>' + v.yld + "<small>%</small></b></div>" +
          "</div>" +
          '<div class="ava-stats-earned">' +
            '<div class="row"><span class="lbl">' + t.earned + "</span>" +
              (pct !== null ? '<span class="back">' + pct + t.back + "</span>" : "") + "</div>" +
            '<div class="val">' + fmtNum(v.cum) + ' <small style="font-size:14px;font-weight:600;opacity:.75">THB</small>' +
              (fx ? ' <span style="font-size:13px;font-weight:600;color:#8FA3A8">' + fmtUSD(v.cum, fx) + "</span>" : "") + "</div>" +
            (pct !== null ? '<div class="ava-stats-bar"><i style="width:' + Math.min(100, pct) + '%"></i></div>' : "") +
            (payback !== null ? '<div class="cap">' + t.payback(payback) + "</div>" : "") +
          "</div>" +
        "</div>" +
        '<div class="ava-stats-right">' +
          '<div class="ava-stats-meta">' +
            '<div class="m"><span>' + t.occ + "</span><b>" + v.occ + "%</b></div>" +
            '<div class="m"><span>' + t.adr + "</span><b>" + fmtNum(v.adr) + ' <small style="font-size:11px;font-weight:600;opacity:.75">THB</small></b></div>' +
            '<div class="m"><span>' + t.since + "</span><b>" + (v.since || "") + "</b></div>" +
            '<div class="ava-stats-live"><i></i>' + t.live + "</div>" +
          "</div>" +
          '<div class="ava-stats-ct">' + t.chart + "</div>" +
          '<div class="ava-stats-bars">' + bars(v.series || []) + "</div>" +
          '<div class="ava-stats-months">' + months(v.labels || []) + "</div>" +
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
        render(el, v, el.getAttribute("data-lang") || "en", data.fx);
      });
    }).catch(function () { nodes.forEach(function (el) { el.style.display = "none"; }); });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
