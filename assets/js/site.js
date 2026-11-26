/* Paradise.mx — site behaviour. Vanilla JS, no dependencies. */
(function () {
  "use strict";
  var CFG = window.PARADISE_CONFIG || {};
  var ROOT = document.documentElement.getAttribute("data-root") || "./";
  var MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
  var MONTHS_LONG = ["January","February","March","April","May","June","July","August","September","October","November","December"];
  var $ = function (s, el) { return (el || document).querySelector(s); };
  var $$ = function (s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); };
  var store = {
    get: function (k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    set: function (k, v) { try { window.localStorage.setItem(k, v); } catch (e) {} }
  };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return {"&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;"}[c]; }); }
  function qs() { var o = {}; (location.search || "").replace(/^\?/, "").split("&").forEach(function (p) { if (!p) return; var kv = p.split("="); o[decodeURIComponent(kv[0])] = decodeURIComponent((kv[1] || "").replace(/\+/g, " ")); }); return o; }

  /* ---------- Navigation ---------- */
  var mb = $(".menu-btn"), nav = $("#nav");
  if (mb && nav) mb.addEventListener("click", function () {
    var open = nav.classList.toggle("open");
    mb.setAttribute("aria-expanded", open ? "true" : "false");
  });

  /* ---------- Cookie notice ---------- */
  var ck = $("#cookie");
  if (ck && !store.get("pmx-cookie")) {
    ck.classList.add("show");
    $$("[data-cookie]", ck).forEach(function (b) {
      b.addEventListener("click", function () { store.set("pmx-cookie", b.getAttribute("data-cookie")); ck.classList.remove("show"); });
    });
  }

  /* ---------- Paradise score (mirrors scripts/build.py) ---------- */
  var PD = null;
  var pdEl = document.getElementById("pdata");
  if (pdEl) { try { PD = JSON.parse(pdEl.textContent); } catch (e) { PD = null; } }
  function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
  function beachy(d) { return d.type === "beach" || d.type === "island" || d.type === "lagoon"; }
  function monthData(d, m) {
    var z = PD.c.zones[d.zone], n = (PD.n && PD.n[d.slug]) || null;
    var hi = n && n.hi ? n.hi[m] : z.hi[m];
    var rain = n && n.rain ? n.rain[m] : z.rain[m];
    var sea = z.sea[m];
    var sarg = PD.c.sargassum.levels[m] * (d.sargassum || 0);
    var hur = PD.c.hurricane[z.basin][m];
    var ev = (d.events || []).filter(function (id) { var e = PD.c.events[id]; return e && e.months.indexOf(m + 1) > -1; });
    return { hi: hi, rain: rain, sea: sea, sarg: sarg, hur: hur, ev: ev };
  }
  function score(d, m) {
    var x = monthData(d, m), b = beachy(d);
    var air = b ? 100 - 6 * Math.max(0, 27 - x.hi) - 7 * Math.max(0, x.hi - 31)
                : 100 - 6 * Math.max(0, 21 - x.hi) - 7 * Math.max(0, x.hi - 27);
    air = clamp(air, 0, 100);
    var rain = clamp(100 - 4.5 * x.rain, 0, 100);
    var sea = x.sea == null ? 70 : (x.sea >= 27 ? 100 : clamp(100 - (27 - x.sea) * 9, 0, 100));
    var base = b ? air * 0.38 + rain * 0.34 + sea * 0.28 : air * 0.5 + rain * 0.5;
    var pen = 6 * x.sarg + (b ? 4 : 2) * x.hur;
    var bonus = Math.min(8, 4 * x.ev.length);
    return clamp(Math.round(base - pen + bonus), 0, 100);
  }
  function sargWord(v) { return v >= 2.2 ? "High sargassum risk" : v >= 1.2 ? "Some sargassum risk" : ""; }
  function hurWord(v) { return v >= 3 ? "Peak storm season" : v >= 2 ? "Storm season" : ""; }
  function scoreColor(s) {
    if (s >= 85) return ["#0E4D5C", "#fff"]; if (s >= 75) return ["#19B5A6", "#04302B"];
    if (s >= 65) return ["#9FE0D7", "#0E4D5C"]; if (s >= 55) return ["#FFE3A3", "#5A3B00"];
    return ["#F6D3DC", "#7A1C3A"];
  }
  window.ParadiseScore = { score: score, monthData: monthData };

  function art(slug) { return ROOT + "assets/img/postcards/" + slug + ".svg"; }
  function destUrl(slug) { return ROOT + "destinations/" + slug + "/"; }

  /* ---------- Home: Paradise Finder ---------- */
  var finder = $("#finder");
  if (finder && PD) {
    var now = new Date().getMonth();
    var qm = parseInt(qs().month, 10);
    var start = !isNaN(qm) && qm >= 1 && qm <= 12 ? qm - 1 : now;
    var r = $('input[name="fm"][value="' + start + '"]', finder); if (r) r.checked = true;
    // month strength bars
    $$(".month", finder).forEach(function (lab) {
      var m = parseInt($("input", lab).value, 10);
      var best = PD.d.filter(beachy).map(function (d) { return score(d, m); }).sort(function (a, b) { return b - a; }).slice(0, 5);
      var avg = best.reduce(function (a, b) { return a + b; }, 0) / best.length;
      var i = $("i", lab); if (i) { i.style.background = scoreColor(avg)[0]; }
    });
    var list = $("#rank"), countEl = $("#rank-count"), planA = $("#finder-plan");
    function renderFinder() {
      var m = parseInt(($('input[name="fm"]:checked', finder) || {}).value || now, 10);
      var kind = ($('input[name="fk"]:checked', finder) || {}).value || "beach";
      var regions = $$('input[name="fr"]:checked', finder).map(function (i) { return i.value; });
      var pool = PD.d.filter(function (d) {
        if (kind === "beach" && !beachy(d)) return false;
        if (kind === "culture" && beachy(d)) return false;
        if (regions.length && regions.indexOf(d.region) < 0) return false;
        return true;
      }).map(function (d) { return { d: d, s: score(d, m), x: monthData(d, m) }; })
        .sort(function (a, b) { return b.s - a.s; });
      // Diversity: at most two picks per climate zone, so one coast can't fill the whole list.
      var top = [], perZone = {}, rest = [];
      pool.forEach(function (o) {
        var z = o.d.zone; perZone[z] = (perZone[z] || 0) + 1;
        if (perZone[z] <= 2 && top.length < 8) top.push(o); else rest.push(o);
      });
      for (var ri = 0; top.length < 8 && ri < rest.length; ri++) top.push(rest[ri]);
      top.sort(function (a, b) { return b.s - a.s; });
      // FLIP: record old positions
      var old = {};
      $$("li", list).forEach(function (li) { old[li.getAttribute("data-slug")] = li.getBoundingClientRect().top; });
      list.innerHTML = top.map(function (o, i) {
        var d = o.d, x = o.x, warn = [sargWord(x.sarg), hurWord(x.hur)].filter(Boolean);
        var evs = x.ev.map(function (id) { return PD.c.events[id].name; });
        return '<li data-slug="' + d.slug + '">' +
          '<span class="n">' + (i + 1) + '</span>' +
          '<a class="pc" href="' + destUrl(d.slug) + '" tabindex="-1" aria-hidden="true"><img src="' + art(d.slug) + '" alt="" width="64" height="48" loading="lazy"></a>' +
          '<div class="t"><h3><a href="' + destUrl(d.slug) + '">' + esc(d.name) + '</a></h3><div class="where">' + esc(d.state) + ' · fly into ' + esc(d.airport) + '</div></div>' +
          '<div class="facts"><span>High <b>' + x.hi + '°C</b></span>' + (x.sea != null ? '<span>Water <b>' + x.sea + '°C</b></span>' : '') +
          '<span>Rainy days <b>' + x.rain + '</b></span>' +
          (warn.length ? '<span class="tag-sarg">' + esc(warn.join(", ")) + '</span>' : '') +
          (evs.length ? '<span>' + esc(evs[0]) + '</span>' : '') + '</div>' +
          '<div class="score" aria-label="Paradise score ' + o.s + ' out of 100"><span class="bar"><i style="width:' + o.s + '%"></i></span><b>' + o.s + '</b></div>' +
          '</li>';
      }).join("") || '<li class="empty">No destinations match. Clear a region filter.</li>';
      // FLIP animate
      if (!window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
        $$("li", list).forEach(function (li) {
          var s = li.getAttribute("data-slug"), t = li.getBoundingClientRect().top;
          if (old[s] != null) {
            var dy = old[s] - t; if (!dy) return;
            li.style.transform = "translateY(" + dy + "px)"; li.style.transition = "none";
            requestAnimationFrame(function () { requestAnimationFrame(function () { li.style.transition = "transform .45s cubic-bezier(.2,.7,.2,1)"; li.style.transform = ""; }); });
          } else { li.animate && li.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 300 }); }
        });
      }
      if (countEl) countEl.textContent = "Ranked " + pool.length + " destinations for " + MONTHS_LONG[m] + ".";
      if (planA && top[0]) planA.href = ROOT + "plan/?dest=" + encodeURIComponent(top[0].d.slug) + "&month=" + (m + 1);
      store.set("pmx-month", String(m));
    }
    finder.addEventListener("change", renderFinder);
    renderFinder();
  }

  /* ---------- Destinations explorer ---------- */
  var ex = $("#explorer");
  if (ex && PD) {
    var exM = $("#ex-month"), exR = $("#ex-region"), exV = $("#ex-vibe"), exB = $("#ex-budget"), exQ = $("#ex-q"), exOut = $("#ex-out"), exN = $("#ex-count");
    var sm = store.get("pmx-month"); exM.value = sm != null ? sm : String(new Date().getMonth());
    var p = qs(); if (p.region) exR.value = p.region; if (p.vibe) exV.value = p.vibe;
    function renderEx() {
      var m = parseInt(exM.value, 10), q = (exQ.value || "").toLowerCase().trim();
      var rows = PD.d.filter(function (d) {
        if (exR.value && d.region !== exR.value) return false;
        if (exV.value && d.vibes.indexOf(exV.value) < 0) return false;
        if (exB.value && d.budget > parseInt(exB.value, 10)) return false;
        if (q && (d.name + " " + d.state + " " + d.vibes.join(" ")).toLowerCase().indexOf(q) < 0) return false;
        return true;
      }).map(function (d) { return { d: d, s: score(d, m) }; }).sort(function (a, b) { return b.s - a.s; });
      exN.textContent = rows.length + " destination" + (rows.length === 1 ? "" : "s") + ", sorted by Paradise score for " + MONTHS_LONG[m] + ".";
      exOut.innerHTML = rows.map(function (o) {
        var d = o.d, c = scoreColor(o.s);
        return '<a class="card" href="' + destUrl(d.slug) + '"><div class="art"><img src="' + art(d.slug) + '" alt="" loading="lazy" width="400" height="300"></div>' +
          '<h3>' + esc(d.name) + '</h3><p>' + esc(d.tagline) + '</p>' +
          '<div class="meta"><span style="background:' + c[0] + ';color:' + c[1] + ';padding:1px 8px;border-radius:999px">' + o.s + '</span><span>' + esc(d.region) + '</span><span>' + "$$$$".slice(0, d.budget) + '</span></div></a>';
      }).join("") || '<p class="empty">Nothing matches those filters yet. Try another region or budget.</p>';
    }
    [exM, exR, exV, exB].forEach(function (el) { el.addEventListener("change", renderEx); });
    exQ.addEventListener("input", renderEx);
    renderEx();
  }

  /* ---------- Best-time matrix: mark current month ---------- */
  var mx = $("#matrix");
  if (mx) { var cm = new Date().getMonth(); $$('[data-m="' + cm + '"]', mx).forEach(function (c) { c.style.outline = "2px solid #C2255C"; }); }

  /* ---------- Compare tool ---------- */
  var cmp = $("#compare");
  if (cmp && PD) {
    var sels = $$("select", cmp), out = $("#compare-out");
    var opts = '<option value="">Choose a destination</option>' + PD.d.map(function (d) { return '<option value="' + d.slug + '">' + esc(d.name) + '</option>'; }).join("");
    sels.forEach(function (s, i) { s.innerHTML = opts; s.value = ["cancun", "los-cabos", "puerto-vallarta"][i] || ""; s.addEventListener("change", renderCmp); });
    function renderCmp() {
      var picks = sels.map(function (s) { return PD.d.filter(function (d) { return d.slug === s.value; })[0]; }).filter(Boolean);
      if (!picks.length) { out.innerHTML = '<p class="empty">Pick at least one destination.</p>'; return; }
      var h = '<div class="table-scroll"><table class="clim"><thead><tr><th>Month</th>' + picks.map(function (d) { return '<th>' + esc(d.name) + '</th>'; }).join("") + '</tr></thead><tbody>';
      for (var m = 0; m < 12; m++) {
        var sc = picks.map(function (d) { return score(d, m); }), mxs = Math.max.apply(null, sc);
        h += '<tr><td>' + MONTHS_LONG[m] + '</td>' + picks.map(function (d, i) {
          var x = monthData(d, m), c = scoreColor(sc[i]);
          return '<td><span style="background:' + c[0] + ';color:' + c[1] + ';padding:2px 8px;border-radius:999px;font-weight:800' + (sc[i] === mxs && picks.length > 1 ? ';box-shadow:0 0 0 2px #C2255C' : '') + '">' + sc[i] + '</span><br><small>' + x.hi + '°C' + (x.sea != null ? ' · sea ' + x.sea + '°' : '') + ' · ' + x.rain + ' wet days</small></td>';
        }).join("") + '</tr>';
      }
      out.innerHTML = h + '</tbody></table></div>';
    }
    renderCmp();
  }

  /* ---------- Sargassum outlook tool ---------- */
  var sg = $("#sarg-tool");
  if (sg && PD) {
    var sgm = $("#sg-month"); sgm.value = String(new Date().getMonth());
    function renderSg() {
      var m = parseInt(sgm.value, 10);
      var car = PD.d.filter(function (d) { return d.sargassum > 0 && beachy(d); }).map(function (d) { return { d: d, v: PD.c.sargassum.levels[m] * d.sargassum }; }).sort(function (a, b) { return a.v - b.v; });
      var alt = PD.d.filter(function (d) { return beachy(d) && d.sargassum === 0; }).map(function (d) { return { d: d, s: score(d, m) }; }).sort(function (a, b) { return b.s - a.s; }).slice(0, 6);
      var lvl = ["None", "Low", "Moderate", "High"][PD.c.sargassum.levels[m]];
      $("#sg-out").innerHTML = '<p class="lede">Typical Caribbean season level in ' + MONTHS_LONG[m] + ': <b>' + lvl + '</b>. Real conditions change week to week; check a live monitor before you go.</p>' +
        '<div class="grid-2"><div><h3>Caribbean beaches, least to most exposed</h3><ol class="news">' + car.map(function (o) {
          var w = o.v >= 2.2 ? "High" : o.v >= 1.2 ? "Moderate" : o.v > 0.3 ? "Low" : "Very low";
          return '<li><a href="' + destUrl(o.d.slug) + '">' + esc(o.d.name) + '</a><div class="src">Expected exposure: ' + w + '</div></li>';
        }).join("") + '</ol></div><div><h3>Seaweed-free alternatives this month</h3><ol class="news">' + alt.map(function (o) {
          return '<li><a href="' + destUrl(o.d.slug) + '">' + esc(o.d.name) + '</a><div class="src">' + esc(o.d.region) + ' · Paradise score ' + o.s + '</div></li>';
        }).join("") + '</ol></div></div>';
    }
    sgm.addEventListener("change", renderSg); renderSg();
  }

  /* ---------- FX (snapshot first, then live) ---------- */
  var FX = null;
  function loadFx(cb) {
    if (FX) return cb(FX);
    fetch(ROOT + "data/fx.json", { cache: "no-store" }).then(function (r) { return r.json(); }).then(function (j) { FX = j; cb(FX); })
      .catch(function () { cb(null); });
    fetch("https://open.er-api.com/v6/latest/USD").then(function (r) { return r.json(); }).then(function (j) {
      if (j && j.rates && j.rates.MXN) { FX = { base: "USD", date: j.time_last_update_utc, rates: { MXN: j.rates.MXN, CAD: j.rates.CAD, EUR: j.rates.EUR, GBP: j.rates.GBP }, live: true }; cb(FX); }
    }).catch(function () {});
  }
  function perMXN(cur, fx) { var r = fx.rates; if (cur === "USD") return r.MXN; return r.MXN / r[cur]; }
  $$("[data-fx]").forEach(function (el) {
    loadFx(function (fx) { if (!fx) return; var cur = el.getAttribute("data-fx"); el.textContent = perMXN(cur, fx).toFixed(2); });
  });
  var conv = $("#fx-tool");
  if (conv) {
    var amt = $("#fx-amt"), from = $("#fx-from"), to = $("#fx-to"), res = $("#fx-res"), stamp = $("#fx-stamp");
    function doConv() {
      loadFx(function (fx) {
        if (!fx) { res.textContent = "Rates are unavailable right now. Try again in a minute."; return; }
        var a = parseFloat(amt.value) || 0, mxn = from.value === "MXN" ? a : a * perMXN(from.value, fx);
        var outv = to.value === "MXN" ? mxn : mxn / perMXN(to.value, fx);
        res.textContent = a.toLocaleString(undefined, { maximumFractionDigits: 2 }) + " " + from.value + " = " + outv.toLocaleString(undefined, { maximumFractionDigits: 2 }) + " " + to.value;
        if (stamp) stamp.textContent = (fx.live ? "Live rate" : "Rate snapshot") + " · " + (fx.date || "");
      });
    }
    [amt, from, to].forEach(function (e) { e.addEventListener("input", doConv); e.addEventListener("change", doConv); });
    doConv();
  }

  /* ---------- Live weather (Open-Meteo, no key) ---------- */
  var WX = {0:"Clear",1:"Mostly clear",2:"Partly cloudy",3:"Cloudy",45:"Fog",48:"Fog",51:"Drizzle",53:"Drizzle",55:"Drizzle",61:"Rain",63:"Rain",65:"Heavy rain",66:"Freezing rain",67:"Freezing rain",71:"Snow",73:"Snow",75:"Snow",80:"Showers",81:"Showers",82:"Heavy showers",95:"Thunderstorms",96:"Thunderstorms",99:"Thunderstorms"};
  var strip = $("#live-strip");
  if (strip) {
    var cells = $$("[data-lat]", strip);
    var lats = cells.map(function (c) { return c.getAttribute("data-lat"); }).join(","), lons = cells.map(function (c) { return c.getAttribute("data-lon"); }).join(",");
    fetch("https://api.open-meteo.com/v1/forecast?latitude=" + lats + "&longitude=" + lons + "&current=temperature_2m,weather_code&timezone=auto")
      .then(function (r) { return r.json(); }).then(function (j) {
        var arr = Array.isArray(j) ? j : [j];
        arr.forEach(function (o, i) { var c = cells[i]; if (!c || !o.current) return; $(".v", c).innerHTML = Math.round(o.current.temperature_2m) + '°C <small>' + (WX[o.current.weather_code] || "") + '</small>'; });
      }).catch(function () {});
  }
  var dw = $("#dest-weather");
  if (dw) {
    var la = dw.getAttribute("data-lat"), lo = dw.getAttribute("data-lon");
    fetch("https://api.open-meteo.com/v1/forecast?latitude=" + la + "&longitude=" + lo + "&current=temperature_2m,apparent_temperature,weather_code,wind_speed_10m,relative_humidity_2m&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max&timezone=auto&forecast_days=7")
      .then(function (r) { return r.json(); }).then(function (j) {
        var c = j.current, d = j.daily; if (!c) return;
        $("#dw-now").innerHTML = '<span style="font-size:2.4rem;font-weight:800">' + Math.round(c.temperature_2m) + '°C</span><span>' + (WX[c.weather_code] || "") + '</span><span class="small">Feels like ' + Math.round(c.apparent_temperature) + '°C · humidity ' + c.relative_humidity_2m + '% · wind ' + Math.round(c.wind_speed_10m) + ' km/h</span>';
        $("#dw-days").innerHTML = d.time.map(function (t, i) {
          var dt = new Date(t + "T12:00:00");
          return '<div><span>' + dt.toLocaleDateString(undefined, { weekday: "short" }) + '</span><b>' + Math.round(d.temperature_2m_max[i]) + '°</b><span class="small">' + Math.round(d.temperature_2m_min[i]) + '° · ' + (d.precipitation_probability_max[i] == null ? "–" : d.precipitation_probability_max[i] + "%") + '</span></div>';
        }).join("");
      }).catch(function () { $("#dw-now").textContent = "Live weather is unavailable right now."; });
    if (dw.getAttribute("data-sea") === "1") {
      fetch("https://marine-api.open-meteo.com/v1/marine?latitude=" + la + "&longitude=" + lo + "&current=wave_height,sea_surface_temperature&timezone=auto")
        .then(function (r) { return r.json(); }).then(function (j) {
          var c = j.current; if (!c) return; var bits = [];
          if (c.sea_surface_temperature != null) bits.push("Sea " + Math.round(c.sea_surface_temperature) + "°C");
          if (c.wave_height != null) bits.push("waves " + c.wave_height.toFixed(1) + " m");
          if (bits.length) $("#dw-sea").textContent = bits.join(" · ");
        }).catch(function () {});
    }
  }

  /* ---------- YouTube facade ---------- */
  $$(".yt").forEach(function (box) {
    function play() {
      var id = box.getAttribute("data-id");
      box.innerHTML = '<iframe src="https://www.youtube-nocookie.com/embed/' + id + '?autoplay=1&rel=0" title="' + esc(box.getAttribute("data-title") || "Video") + '" allow="accelerometer; autoplay; encrypted-media; gyroscope; picture-in-picture" allowfullscreen loading="lazy"></iframe>';
    }
    box.addEventListener("click", play);
    var b = $("button", box); if (b) b.addEventListener("keydown", function (e) { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); play(); } });
  });

  /* ---------- Ads: in-content units only when slot IDs exist ---------- */
  if (CFG.adSlots && CFG.adSlots.inContent) {
    $$("[data-ad]").forEach(function (w) {
      w.innerHTML = '<ins class="adsbygoogle" style="display:block" data-ad-client="' + CFG.adClient + '" data-ad-slot="' + CFG.adSlots.inContent + '" data-ad-format="auto" data-full-width-responsive="true"></ins>';
      try { (window.adsbygoogle = window.adsbygoogle || []).push({}); } catch (e) {}
    });
  }

  /* ---------- Forms (FormSubmit AJAX; inbox assembled at submit time) ---------- */
  var params = qs();
  function prefill(form) {
    $$("[data-prefill]", form).forEach(function (el) {
      var k = el.getAttribute("data-prefill"), v = params[k];
      if (k === "month" && !v) { var sm2 = store.get("pmx-month"); if (sm2 != null) v = String(parseInt(sm2, 10) + 1); }
      if (v == null || v === "") return;
      if (el.type === "radio" || el.type === "checkbox") { if (el.value === v) el.checked = true; return; }
      var before = el.value;
      el.value = v;
      if (el.tagName === "SELECT" && el.selectedIndex === -1) {
        var n = parseInt(v, 10);
        if (k === "month" && n >= 1 && n <= 12) el.value = MONTHS_LONG[n - 1];
        if (k === "budget" && !isNaN(n)) el.value = n < 1000 ? "Under US$1,000" : n < 2500 ? "US$1,000-2,500" : n < 5000 ? "US$2,500-5,000" : n < 10000 ? "US$5,000-10,000" : "US$10,000+";
        if (k === "dest") { var d0 = PD && PD.d.filter(function (x) { return x.slug === v; })[0]; if (d0) el.value = d0.name; }
        if (el.selectedIndex === -1) el.value = before;
      }
    });
  }
  function validate(scope) {
    var ok = true, first = null;
    $$("[required]", scope).forEach(function (el) {
      if (el.closest(".step") && !el.closest(".step").classList.contains("on") && scope.classList && scope.classList.contains("step")) return;
      var f = el.closest(".field") || el.parentNode, bad = false;
      if (el.type === "checkbox") bad = !el.checked;
      else if (el.type === "radio") bad = !$$('input[name="' + el.name + '"]', scope).some(function (r) { return r.checked; });
      else bad = !el.value.trim() || (el.type === "email" && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(el.value.trim()));
      var msg = f.querySelector(".err");
      if (bad) {
        ok = false; first = first || el; f.setAttribute("aria-invalid", "true");
        if (!msg) { msg = document.createElement("div"); msg.className = "err"; f.appendChild(msg); }
        msg.textContent = el.getAttribute("data-msg") || (el.type === "email" ? "Enter a valid email address." : "This field is required.");
      } else { f.removeAttribute("aria-invalid"); if (msg) msg.remove(); }
    });
    if (first) first.focus();
    return ok;
  }
  function collect(form) {
    var data = {};
    $$("input, select, textarea", form).forEach(function (el) {
      if (!el.name || el.name.charAt(0) === "_" && el.name !== "_honey") return;
      if ((el.type === "checkbox" || el.type === "radio") && !el.checked) return;
      if (el.type === "checkbox" && data[el.name]) data[el.name] += ", " + el.value;
      else data[el.name] = el.value;
    });
    return data;
  }
  function subjectFrom(tpl, data) { return tpl.replace(/\{(\w+)\}/g, function (_, k) { return data[k] || "-"; }); }
  $$("form[data-form]").forEach(function (form) {
    prefill(form);
    // wizard
    var steps = $$(".step", form), bars = $$(".progress i", form), cur = 0;
    function show(i) {
      steps.forEach(function (s, j) { s.classList.toggle("on", j === i); });
      bars.forEach(function (b, j) { b.classList.toggle("on", j <= i); });
      var back = $("[data-back]", form), next = $("[data-next]", form), sub = $("[type=submit]", form);
      if (back) back.style.visibility = i === 0 ? "hidden" : "visible";
      if (next) next.style.display = i === steps.length - 1 ? "none" : "";
      if (sub) sub.style.display = i === steps.length - 1 ? "" : "none";
      var c = $("[data-stepnum]", form); if (c) c.textContent = "Step " + (i + 1) + " of " + steps.length;
    }
    if (steps.length) {
      show(0);
      var nx = $("[data-next]", form), bk = $("[data-back]", form);
      if (nx) nx.addEventListener("click", function () { if (validate(steps[cur])) { cur = Math.min(cur + 1, steps.length - 1); show(cur); var h = $("h2,h3,legend", steps[cur]); if (h) { h.setAttribute("tabindex", "-1"); h.focus(); } } });
      if (bk) bk.addEventListener("click", function () { cur = Math.max(cur - 1, 0); show(cur); });
    }
    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (!validate(form)) return;
      var hp = $('input[name="_honey"]', form); if (hp && hp.value) return;
      var data = collect(form); delete data._honey;
      var kind = form.getAttribute("data-form");
      data._subject = subjectFrom(form.getAttribute("data-subject") || ("Paradise.mx - " + kind), data);
      data._template = "table";
      data.form_type = kind;
      data.page = location.pathname;
      data.submitted_at = new Date().toISOString();
      ["utm_source", "utm_medium", "utm_campaign"].forEach(function (k) { if (params[k]) data[k] = params[k]; });
      var btn = $("[type=submit]", form), label = btn ? btn.textContent : "";
      if (btn) { btn.disabled = true; btn.textContent = "Sending…"; }
      var box = $(".form-status", form) || form;
      fetch(CFG.endpoint(), { method: "POST", headers: { "Content-Type": "application/json", "Accept": "application/json" }, body: JSON.stringify(data) })
        .then(function (r) { return r.json().catch(function () { return {}; }).then(function (j) { if (!r.ok || String(j.success) === "false") throw new Error(j.message || "send failed"); return j; }); })
        .then(function () {
          var okMsg = form.getAttribute("data-ok") || "Thanks — your message is in. We reply within 48 hours.";
          form.innerHTML = '<div class="form-ok" role="status" tabindex="-1"><h3>Sent.</h3><p class="mb0">' + esc(okMsg) + '</p></div>';
          var st = $(".form-ok", form); if (st) st.focus();
        })
        .catch(function () {
          if (btn) { btn.disabled = false; btn.textContent = label; }
          var bad = $(".form-bad", form);
          if (!bad) { bad = document.createElement("div"); bad.className = "form-bad"; bad.setAttribute("role", "alert"); (btn ? btn.parentNode : form).appendChild(bad); }
          bad.textContent = "Your message didn't go through. Check your connection and press the button again.";
        });
    });
  });

  /* ---------- Trip cost estimator ---------- */
  var tc = $("#cost-tool");
  if (tc && PD) {
    var B = { lodging: [45, 120, 280, 650], food: [20, 45, 90, 180], local: [8, 15, 30, 60], act: [15, 35, 70, 140], ai: [0, 170, 260, 480] };
    var mult = [0, 0.8, 1, 1.2, 1.45];
    var dsel = $("#tc-dest"); dsel.innerHTML = PD.d.map(function (d) { return '<option value="' + d.slug + '">' + esc(d.name) + '</option>'; }).join("");
    if (params.dest) dsel.value = params.dest;
    function calc() {
      var d = PD.d.filter(function (x) { return x.slug === dsel.value; })[0] || PD.d[0];
      var nights = Math.max(1, parseInt($("#tc-nights").value, 10) || 1), ppl = Math.max(1, parseInt($("#tc-people").value, 10) || 1);
      var st = parseInt($("#tc-style").value, 10), ai = $("#tc-ai").checked && st > 0, fl = parseFloat($("#tc-flight").value) || 0;
      var rooms = Math.ceil(ppl / 2), k = mult[d.budget];
      var lodging = ai ? 0 : B.lodging[st] * k * rooms * nights;
      var food = ai ? 0 : B.food[st] * k * ppl * nights;
      var allinc = ai ? B.ai[st] * k * ppl * nights : 0;
      var local = B.local[st] * k * ppl * nights * (ai ? 0.5 : 1);
      var act = B.act[st] * k * ppl * Math.ceil(nights * 0.6);
      var flights = fl * ppl;
      var tax = d.state === "Quintana Roo" ? 16 * ppl : 0;
      var total = lodging + food + allinc + local + act + flights + tax;
      var rows = [["Flights", flights], ["Accommodation", lodging], ["All-inclusive stay", allinc], ["Food and drinks", food], ["Local transport", local], ["Tours and activities", act], ["Quintana Roo Visitax (approx.)", tax]].filter(function (r) { return r[1] > 0; });
      var fmt = function (v) { return "US$" + Math.round(v).toLocaleString(); };
      $("#tc-out").innerHTML = '<table class="clim"><tbody>' + rows.map(function (r) { return '<tr><td>' + r[0] + '</td><td style="text-align:right">' + fmt(r[1]) + '</td></tr>'; }).join("") +
        '<tr><td><b>Estimated total</b></td><td style="text-align:right"><b style="font-size:1.4rem">' + fmt(total) + '</b></td></tr>' +
        '<tr><td>Per person</td><td style="text-align:right">' + fmt(total / ppl) + '</td></tr></tbody></table><p class="small mt4" id="tc-mxn"></p>' +
        '<a class="btn btn-primary mt4" href="' + ROOT + 'plan/?dest=' + d.slug + '&budget=' + Math.round(total / ppl) + '">Get a real quote for ' + esc(d.name) + '</a>';
      loadFx(function (fx) { var e = $("#tc-mxn"); if (fx && e) e.textContent = "About MX$" + Math.round(total * fx.rates.MXN).toLocaleString() + " at " + fx.rates.MXN.toFixed(2) + " pesos per US dollar."; });
    }
    $$("input,select", tc).forEach(function (el) { el.addEventListener("input", calc); el.addEventListener("change", calc); });
    calc();
  }

  /* ---------- Packing list ---------- */
  var pk = $("#pack-tool");
  if (pk) {
    var L = {
      base: ["Passport (valid for your whole stay)", "Printed or saved booking confirmations", "Credit card with no foreign-transaction fee", "Some pesos in small notes for tips, taxis and markets", "Phone, charger and a small power bank", "Travel insurance details", "Prescription medicines in original packaging", "Reef-safe mineral sunscreen", "Sunglasses and a hat", "Refillable water bottle"],
      beach: ["Two swimsuits", "Rash guard (sun and jellyfish protection)", "Water shoes for rocky entries", "Light cover-up", "Dry bag for boat days", "Snorkel mask that fits you"],
      cenotes: ["Biodegradable or no sunscreen (many cenotes require you to shower first)", "Quick-dry towel", "Waterproof phone pouch", "Cash for entry fees"],
      city: ["Comfortable walking shoes", "A light jacket for cool evenings at altitude", "Small daypack", "Modest outfit for churches"],
      adventure: ["Closed-toe hiking shoes", "Insect repellent with DEET or picaridin", "Headlamp", "Quick-dry layers"],
      wedding: ["Formal outfit in breathable fabric", "Flat shoes for sand", "Steamer or wrinkle spray", "Copies of documents for the ceremony"],
      rain: ["Packable rain jacket", "Quick-dry clothes", "Zip bags for electronics"],
      kids: ["Kids' swim vests", "Children's sunscreen and after-sun", "Snacks for transfers", "Each child's passport and birth certificate (hotels now verify guardianship at check-in)", "Signed consent letter from any parent who isn't travelling"]
    };
    function renderPk() {
      var types = $$('input[name="pk-type"]:checked', pk).map(function (i) { return i.value; });
      var m = parseInt($("#pk-month").value, 10), kids = $("#pk-kids").checked;
      var items = L.base.slice();
      types.forEach(function (t) { items = items.concat(L[t] || []); });
      if (m >= 5 && m <= 9) items = items.concat(L.rain);
      if (kids) items = items.concat(L.kids);
      $("#pk-out").innerHTML = '<ul class="tick">' + items.map(function (t, i) { return '<li><label><input type="checkbox" id="pk' + i + '"> ' + esc(t) + '</label></li>'; }).join("") + '</ul>';
    }
    $$("input,select", pk).forEach(function (el) { el.addEventListener("change", renderPk); });
    $("#pk-month").value = String(new Date().getMonth());
    renderPk();
    var pp = $("#pk-print"); if (pp) pp.addEventListener("click", function () { window.print(); });
  }

  /* ---------- Donations ---------- */
  var don = $("#support-form");
  if (don) {
    var custom = $("#don-custom"), amtF = $("#don-amount");
    function syncAmt() {
      var t = $('input[name="tier"]:checked', don);
      if (t && t.value !== "custom") { amtF.value = t.getAttribute("data-amt"); custom.parentNode.style.display = "none"; }
      else { custom.parentNode.style.display = ""; amtF.value = custom.value; }
    }
    don.addEventListener("change", syncAmt); custom.addEventListener("input", syncAmt); syncAmt();
    var payBox = $("#pay-direct");
    if (payBox && CFG.pay && (CFG.pay.oneTime || CFG.pay.monthly)) {
      payBox.hidden = false;
      if (CFG.pay.oneTime) $("#pay-once").href = CFG.pay.oneTime; else $("#pay-once").remove();
      if (CFG.pay.monthly) $("#pay-month").href = CFG.pay.monthly; else $("#pay-month").remove();
    }
  }

  /* ---------- Year ---------- */
  $$("[data-year]").forEach(function (e) { e.textContent = new Date().getFullYear(); });
})();
