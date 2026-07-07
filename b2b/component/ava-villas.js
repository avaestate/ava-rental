/* ============================================================
   AVA Investment Villas — component (vanilla JS, без зависимостей)
   Рендер-функции возвращают HTML-строку из объекта виллы.
   Ничего не навязывает по разметке страницы — встраивается в
   вашу систему карточек товаров Tilda.

   Использование:
     const villas = await AVAVillas.load('/b2b/data.json');   // или ваш путь
     el.innerHTML = AVAVillas.card(villas[0]);                 // карточка в каталог
     el.innerHTML = AVAVillas.detail(villas[0]);               // блок на странице объекта

   Поля объекта виллы — см. README / data.json.
   ============================================================ */
window.AVAVillas = (function () {
  const money = n => Math.round(n).toLocaleString('en-US');
  // короткий формат денег: 1 234 567 -> "1.2M", 96 000 -> "96k"
  const kfmt = n => n >= 1e6 ? (n / 1e6).toFixed(n >= 1e7 ? 0 : 2) + 'M'
                  : (n >= 1000 ? Math.round(n / 1000) + 'k' : Math.round(n));

  /* мини-спарклайн (для карточки) из массива series[] */
  function sparkSVG(series) {
    const v = series.slice(), W = 200, H = 30, n = v.length,
          mx = Math.max(...v, 1), mn = Math.min(...v);
    const xs = i => i * (W / (n - 1)), ys = val => H - 3 - ((val - mn) / ((mx - mn) || 1)) * (H - 7);
    let d = `M0 ${ys(v[0]).toFixed(1)}`;
    for (let i = 1; i < n; i++) d += ` L${xs(i).toFixed(1)} ${ys(v[i]).toFixed(1)}`;
    const area = d + ` L${W} ${H} L0 ${H} Z`;
    return `<defs><linearGradient id="avaSg" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#c6a878" stop-opacity=".5"/>
      <stop offset="1" stop-color="#c6a878" stop-opacity="0"/></linearGradient></defs>
      <path d="${area}" fill="url(#avaSg)"/>
      <path d="${d}" fill="none" stroke="#d9c09a" stroke-width="2"/>
      <circle cx="${W}" cy="${ys(v[n - 1]).toFixed(1)}" r="2.6" fill="#e2c592"/>`;
  }

  /* столбчатый график помесячного дохода с подписью значения над каждым столбиком */
  function barsSVG(series, labels) {
    const vals = series.slice(), W = 400, H = 168, n = vals.length,
          gap = 7, bw = (W - gap * (n - 1)) / n, floor = H - 24, top = 22, mx = Math.max(...vals, 1);
    let s = `<line x1="0" y1="${floor}" x2="${W}" y2="${floor}" stroke="#4a5553"/>`;
    vals.forEach((val, i) => {
      const h = val > 0 ? Math.max(3, (val / mx) * (floor - top)) : 0,
            x = i * (bw + gap), y = floor - h, hot = val >= mx * 0.85;
      if (h > 0) {
        s += `<rect x="${x.toFixed(1)}" y="${y.toFixed(1)}" width="${bw.toFixed(1)}" height="${h.toFixed(1)}" rx="3" fill="${hot ? '#d9c09a' : '#c6a878'}" opacity="${hot ? 1 : .85}"/>`;
        s += `<text x="${(x + bw / 2).toFixed(1)}" y="${(y - 5).toFixed(1)}" fill="#e6ded2" font-size="9" font-weight="700" text-anchor="middle" font-family="Manrope">${kfmt(val)}</text>`;
      }
      s += `<text x="${(x + bw / 2).toFixed(1)}" y="${H - 8}" fill="#8b948f" font-size="9" text-anchor="middle" font-family="Manrope">${labels[i] || ''}</text>`;
    });
    return s;
  }

  /* КАРТОЧКА (в каталог товаров). Верните строку в innerHTML контейнера с классом .ava-card
     ИЛИ оберните сами: `<div class="ava-card">${AVAVillas.card(v)}</div>` */
  function card(v) {
    return `
      <div class="photo"><img src="${v.hero}" alt="" loading="lazy"><div class="pill">FOR SALE</div></div>
      <div class="cname">${v.name.replace('AVA ', '')} — ${v.bd} BR</div>
      <div class="csub">${v.city} · fully furnished, rental-ready.</div>
      <div class="cprice">${money(v.price)} <span>฿</span></div>
      <div class="strip">
        <div class="m"><div class="l">In operation</div><div class="v">${v.months} <small>mo</small></div></div>
        <div class="m"><div class="l">Net / month</div><div class="v"><span class="u">฿</span>${kfmt(v.net)}</div></div>
        <div class="m"><div class="l">ROI / year</div><div class="v">${v.yld}<span class="u">%</span></div></div>
      </div>
      <div class="sparkrow"><svg viewBox="0 0 200 30" preserveAspectRatio="none">${sparkSVG(v.series)}</svg>
        <div class="trend">▲ ฿${(v.cum / 1e6).toFixed(2)}M earned</div></div>`;
  }

  /* ИНВЕСТ-БЛОК для страницы объекта. Вставляется ПОД ваше описание+цену.
     Оберните в `<div class="ava-detail">${AVAVillas.detail(v)}</div>` */
  function detail(v) {
    const recovered = Math.round(v.cum / v.price * 100);
    const payback = Math.max(1, Math.round(100 / v.yld));
    return `
      <div class="invest">
        <div class="itop"><div class="kicker">Investment performance</div>
          <div class="live"><span class="dot"></span> Live · updated daily</div></div>
        <div class="kpis">
          <div class="kpi"><div class="lab">In operation</div><div class="num">${v.months} <small>mo</small></div></div>
          <div class="kpi"><div class="lab">Net profit / mo</div><div class="num"><span class="u">฿</span>${money(v.net)}</div></div>
          <div class="kpi"><div class="lab">ROI / year</div><div class="num">${v.yld}<span class="u">%</span></div></div>
        </div>
        <div class="subrow"><div>Occupancy <b>${v.occ}%</b></div><div>ADR <b>฿${money(v.adr)}</b></div><div>Since <b>${v.since}</b></div></div>
        <div class="ctitle">Net monthly profit, ฿ <span class="hi">last 12 months</span></div>
        <svg viewBox="0 0 400 168" preserveAspectRatio="none">${barsSVG(v.series, v.labels)}</svg>
        <div class="cum">
          <div class="r1"><div><div class="lab2">Earned since launch</div><div class="big">฿${money(v.cum)}</div></div>
            <div class="pct">${recovered}% of price back</div></div>
          <div class="barw"><div class="barf" style="width:${Math.min(100, recovered)}%"></div></div>
          <div class="cap">Full payback in ≈ ${payback} years, then pure income — and the villa itself stays yours.</div>
        </div>
        <button class="cta">Request full report <span class="arr">→</span></button>
        <div class="note">Figures from actual booking data (Guesty), refreshed daily.</div>
      </div>`;
  }

  /* загрузка данных: возвращает массив villas[] */
  async function load(url) {
    const r = await fetch(url, { cache: 'no-store' });
    const j = await r.json();
    return (j && j.villas) ? j.villas : [];
  }

  return { card, detail, sparkSVG, barsSVG, load, kfmt, money };
})();
