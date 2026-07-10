/* ===================================================================
   AVA — интеграция инвест-показателей в Tilda Store (ava.estate/ready-objects)
   Куда вставить: Настройки сайта → Ещё → «HTML-код для вставки внутри BODY»
   (или отдельный блок T123 в футере). Один раз на весь сайт.

   Что делает (только ДОБАВЛЯЕТ, ничего не ломает — каталог и фильтры ваши):
   • В каталоге: в каждую карточку товара .js-product добавляет строку из
     3 метрик (в работе / доход в мес / ROI) + мини-график, между ценой и кнопкой.
   • На странице объекта (/ready-objects/<slug>): под ценой добавляет
     инвест-блок (KPI + помесячный график с цифрами + накопленная доходность).

   Данные берутся из data.json (обновляется автоматически из Guesty).
   Соответствие «слаг товара → id в данных» — в SLUG_MAP ниже (дополняйте).
   =================================================================== */
(function () {
  'use strict';

  var DATA_URL = 'https://avaestate.github.io/ava-rental/b2b/data.json';

  // Первое слово слага товара (ava.estate/ready-objects/AURORA-villa-2-bedroom → "aurora")
  // → id виллы в data.json. Совпадающие уже прописаны; допишите переименованные
  // (nest / asteria / daphnis / veya / lua / nova → cocolane2/cocolane3/cocolane4/bunny/…).
  var SLUG_MAP = {
    aurora: 'aurora', radharani: 'radharani', axis: 'axis',
    katai: 'katai', white: 'whitelotus'
    // nest:'', asteria:'', daphnis:'', veya:'', lua:'', nova:''  // ← сопоставьте с данными
  };

  /* ---------- стили (namespace .ava-*, совпадают с тёмными карточками ava.estate) ---------- */
  var CSS =
  '.ava-inv{font-family:Manrope,system-ui,sans-serif;margin:20px 0 4px}' +
  '.ava-inv .strip{display:grid;grid-template-columns:1fr 1fr 1fr;border-top:1px solid #3f4748;border-bottom:1px solid #3f4748}' +
  '.ava-inv .m{padding:13px 12px 14px}' +
  '.ava-inv .m + .m{border-left:1px solid #3f4748}' +
  '.ava-inv .m .l{font-size:10px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:#75878b}' +
  '.ava-inv .m .v{font-size:19px;font-weight:800;margin-top:6px;letter-spacing:-.3px;color:#f0e7df;font-variant-numeric:tabular-nums}' +
  '.ava-inv .m .v .u{font-size:12px;color:#f0e7df;font-weight:700}' +
  '.ava-inv .m .v small{font-size:11px;color:#f0e7df;font-weight:700;opacity:.85}' +
  '.ava-inv .sparkpanel{background:#3F4A4C;border-radius:10px;padding:12px 14px 10px;margin-top:14px}' +
  '.ava-inv .sparkpanel svg{width:100%;height:44px;margin-top:6px;display:block;overflow:visible}' +
  '.ava-inv .trend{font-size:12px;font-weight:800;color:#90e480;white-space:nowrap;text-align:right}' +
  '.ava-detail{font-family:Manrope,system-ui,sans-serif;margin:20px 0}' +
  '.ava-detail .invest{background:#2b3838;color:#f2ebe1;border-radius:24px;padding:22px 20px 24px}' +
  '.ava-detail .itop{display:flex;align-items:center;justify-content:space-between}' +
  '.ava-detail .kicker{font-size:12.5px;font-weight:800;letter-spacing:1.3px;text-transform:uppercase;color:#cdd4d0}' +
  '.ava-detail .live{display:flex;align-items:center;gap:6px;font-size:11px;font-weight:700;color:#a9b2ad}' +
  '.ava-detail .dot{width:8px;height:8px;border-radius:50%;background:#7fa06f;display:inline-block}' +
  '.ava-detail .kpis{display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px;margin-top:18px}' +
  '.ava-detail .kpi{background:#333f3e;border-radius:16px;padding:14px 11px}' +
  '.ava-detail .kpi .lab{font-size:10.5px;font-weight:700;color:#939d98;text-transform:uppercase;line-height:1.25;min-height:26px}' +
  '.ava-detail .kpi .num{font-size:22px;font-weight:800;margin-top:7px;letter-spacing:-.5px;font-variant-numeric:tabular-nums}' +
  '.ava-detail .kpi .num .u{font-size:13px;font-weight:700;color:#c6a878}' +
  '.ava-detail .kpi .num small{font-size:12px;font-weight:700;color:#c9d1cc}' +
  '.ava-detail .subrow{display:flex;justify-content:space-between;gap:8px;margin-top:14px;font-size:12.5px;color:#aab3ae}' +
  '.ava-detail .subrow b{color:#e6ded2;font-weight:700}' +
  '.ava-detail .ctitle{font-size:12.5px;font-weight:700;color:#c3ccc6;margin:20px 0 12px;display:flex;justify-content:space-between}' +
  '.ava-detail .ctitle .hi{color:#d9c09a}' +
  '.ava-detail .invest svg{display:block;width:100%}' +
  '.ava-detail .cum{background:#333f3e;border-radius:16px;padding:16px;margin-top:20px}' +
  '.ava-detail .cum .r1{display:flex;justify-content:space-between;align-items:baseline}' +
  '.ava-detail .cum .big{font-size:22px;font-weight:800;letter-spacing:-.4px}' +
  '.ava-detail .cum .lab2{font-size:11px;color:#9aa39f;font-weight:600;margin-bottom:3px}' +
  '.ava-detail .cum .pct{font-size:13px;font-weight:800;color:#7fa06f}' +
  '.ava-detail .barw{height:9px;border-radius:6px;background:#28312f;margin-top:12px;overflow:hidden}' +
  '.ava-detail .barf{height:100%;border-radius:6px;background:linear-gradient(90deg,#c6a878,#d9c09a)}' +
  '.ava-detail .cum .cap{font-size:11px;color:#8f9994;margin-top:9px;line-height:1.45}' +
  '.ava-detail .note{font-size:10.5px;color:#8f9994;margin-top:13px;line-height:1.5;text-align:center}';

  function injectCSS() {
    if (document.getElementById('ava-inv-css')) return;
    var s = document.createElement('style'); s.id = 'ava-inv-css'; s.textContent = CSS;
    document.head.appendChild(s);
  }

  /* ---------- helpers + графики ---------- */
  function money(n){ return Math.round(n).toLocaleString('en-US'); }
  function kfmt(n){ return n>=1e6 ? (n/1e6).toFixed(n>=1e7?0:2)+'M' : (n>=1000 ? Math.round(n/1000)+'k' : Math.round(n)); }
  function sparkSVG(series){
    var v=series.slice(),W=200,H=30,PAD=4,n=v.length,mx=Math.max.apply(0,v.concat([1])),mn=Math.min.apply(0,v);
    var xs=function(i){return PAD+i*((W-2*PAD)/(n-1));},ys=function(x){return H-4-((x-mn)/((mx-mn)||1))*(H-9);};
    var d='M'+PAD+' '+ys(v[0]).toFixed(1),i;
    for(i=1;i<n;i++) d+=' L'+xs(i).toFixed(1)+' '+ys(v[i]).toFixed(1);
    var area=d+' L'+(W-PAD)+' '+H+' L'+PAD+' '+H+' Z';
    return '<defs><linearGradient id="avaSg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#abc4c7" stop-opacity=".35"/><stop offset="1" stop-color="#abc4c7" stop-opacity="0"/></linearGradient></defs>'+
      '<path d="'+area+'" fill="url(#avaSg)"/><path d="'+d+'" fill="none" stroke="#abc4c7" stroke-width="1" vector-effect="non-scaling-stroke"/>'+
      '<circle cx="'+(W-PAD)+'" cy="'+ys(v[n-1]).toFixed(1)+'" r="0.1" fill="none" stroke="#dcebec" stroke-width="4.6" stroke-linecap="round" vector-effect="non-scaling-stroke"/>';
  }
  function barsSVG(series,labels){
    var vals=series.slice(),W=400,H=168,n=vals.length,gap=7,bw=(W-gap*(n-1))/n,floor=H-24,top=22,mx=Math.max.apply(0,vals.concat([1])),s='';
    s+='<line x1="0" y1="'+floor+'" x2="'+W+'" y2="'+floor+'" stroke="#4a5553"/>';
    vals.forEach(function(val,i){
      var h=val>0?Math.max(3,(val/mx)*(floor-top)):0,x=i*(bw+gap),y=floor-h,hot=val>=mx*0.85;
      if(h>0){
        s+='<rect x="'+x.toFixed(1)+'" y="'+y.toFixed(1)+'" width="'+bw.toFixed(1)+'" height="'+h.toFixed(1)+'" rx="3" fill="'+(hot?'#d9c09a':'#c6a878')+'" opacity="'+(hot?1:.85)+'"/>';
        s+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(y-5).toFixed(1)+'" fill="#e6ded2" font-size="9" font-weight="700" text-anchor="middle" font-family="Manrope">'+kfmt(val)+'</text>';
      }
      s+='<text x="'+(x+bw/2).toFixed(1)+'" y="'+(H-8)+'" fill="#8b948f" font-size="9" text-anchor="middle" font-family="Manrope">'+(labels[i]||'')+'</text>';
    });
    return s;
  }

  /* ---------- данные ---------- */
  var byId = {};
  function idFromSlug(slug){ var f=(slug||'').split('-')[0]; return (SLUG_MAP[f]!==undefined)?SLUG_MAP[f]:f; }

  /* ---------- каталог: строка метрик в карточку ---------- */
  function stripHTML(v){
    return '<div class="strip">'+
      '<div class="m"><div class="l">In operation</div><div class="v">'+v.months+' <small>mo</small></div></div>'+
      '<div class="m"><div class="l">Net / month</div><div class="v"><span class="u">฿</span>'+kfmt(v.net)+'</div></div>'+
      '<div class="m"><div class="l">ROI / year</div><div class="v">'+v.yld+'<span class="u">%</span></div></div>'+
      '</div>'+
      '<div class="sparkpanel"><div class="trend">▲ ฿'+(v.cum/1e6).toFixed(2)+'M earned</div>'+
      '<svg viewBox="0 0 200 30" preserveAspectRatio="none">'+sparkSVG(v.series)+'</svg></div>';
  }
  function decorateCards(){
    var cards=document.querySelectorAll('.js-product.t-store__card');
    for(var i=0;i<cards.length;i++){
      var card=cards[i];
      if(card.getAttribute('data-ava-done'))continue;
      var url=card.getAttribute('data-product-url')||'';
      var slug=(url.split('/ready-objects/')[1]||'').replace(/-+$/,'');
      var v=byId[idFromSlug(slug)];
      var anchor=card.querySelector('.js-store-price-wrapper');
      if(!anchor)continue;
      card.setAttribute('data-ava-done','1');   // помечаем даже если данных нет — не дёргаемся повторно
      if(!v)continue;
      var box=document.createElement('div'); box.className='ava-inv'; box.innerHTML=stripHTML(v);
      anchor.parentNode.insertBefore(box,anchor.nextSibling);
    }
  }

  /* ---------- страница объекта: инвест-блок под ценой ---------- */
  function detailHTML(v){
    var rec=Math.round(v.cum/v.price*100), payback=Math.max(1,Math.round(100/v.yld));
    return '<div class="invest">'+
      '<div class="itop"><div class="kicker">Investment performance</div>'+
        '<div class="live"><span class="dot"></span> Live · updated daily</div></div>'+
      '<div class="kpis">'+
        '<div class="kpi"><div class="lab">In operation</div><div class="num">'+v.months+' <small>mo</small></div></div>'+
        '<div class="kpi"><div class="lab">Net profit / mo</div><div class="num"><span class="u">฿</span>'+money(v.net)+'</div></div>'+
        '<div class="kpi"><div class="lab">ROI / year</div><div class="num">'+v.yld+'<span class="u">%</span></div></div>'+
      '</div>'+
      '<div class="subrow"><div>Occupancy <b>'+v.occ+'%</b></div><div>ADR <b>฿'+money(v.adr)+'</b></div><div>Since <b>'+v.since+'</b></div></div>'+
      '<div class="ctitle">Net monthly profit, ฿ <span class="hi">last 12 months</span></div>'+
      '<svg viewBox="0 0 400 168" preserveAspectRatio="none">'+barsSVG(v.series,v.labels)+'</svg>'+
      '<div class="cum"><div class="r1"><div><div class="lab2">Earned since launch</div><div class="big">฿'+money(v.cum)+'</div></div>'+
        '<div class="pct">'+rec+'% of price back</div></div>'+
        '<div class="barw"><div class="barf" style="width:'+Math.min(100,rec)+'%"></div></div>'+
        '<div class="cap">Full payback in ≈ '+payback+' years, then pure income — and the villa itself stays yours.</div></div>'+
      '<div class="note">Figures from actual booking data (Guesty), refreshed daily.</div>'+
      '</div>';
  }
  function decorateProductPage(){
    var m=location.pathname.match(/\/ready-objects\/([^\/]+)/);
    if(!m || document.getElementById('ava-detail-blk'))return;
    var slug=m[1].replace(/-+$/,''); var v=byId[idFromSlug(slug)]; if(!v)return;
    var anchor=document.querySelector('.t760__price-wrapper, .js-store-single-product-info .js-store-price-wrapper, .js-store-price-wrapper');
    if(!anchor)return;
    var box=document.createElement('div'); box.id='ava-detail-blk'; box.className='ava-detail'; box.innerHTML=detailHTML(v);
    anchor.parentNode.insertBefore(box,anchor.nextSibling);
  }

  /* ---------- запуск: Tilda рендерит карточки асинхронно → опрос + наблюдатель ---------- */
  function run(){ try{ decorateCards(); decorateProductPage(); }catch(e){} }
  function boot(){
    injectCSS();
    fetch(DATA_URL,{cache:'no-store'}).then(function(r){return r.json();}).then(function(j){
      (j.villas||[]).forEach(function(v){ byId[v.id]=v; });
      run();
      var n=0, iv=setInterval(function(){ run(); if(++n>40)clearInterval(iv); },500);
      if(window.MutationObserver){ new MutationObserver(run).observe(document.body,{childList:true,subtree:true}); }
    }).catch(function(){});
  }
  if(document.readyState!=='loading')boot(); else document.addEventListener('DOMContentLoaded',boot);
})();
