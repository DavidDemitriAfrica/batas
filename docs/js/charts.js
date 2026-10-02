/* The charts below the story. Each render function redraws from scratch, so
   resizing or switching theme simply calls it again. */
(function () {
  "use strict";
  const B = window.B;
  const C = (B.charts = {});
  let D;
  const {fmt, pct, pct1, dec, ord} = B;
  const CONG = [1, 2, 3, 4, 5, 6, 7, "gap", 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
  const tipOff = sel => sel.on("pointerleave", B.hideTip);

  function yGrid(svg, y, x0, x1, ticks, f = fmt) {
    svg.append("g").selectAll("line").data(ticks).join("line").attr("x1", x0).attr("x2", x1)
      .attr("y1", d => Math.round(y(d)) + 0.5).attr("y2", d => Math.round(y(d)) + 0.5).attr("stroke", B.tok("--grid"));
    svg.append("g").selectAll("text").data(ticks).join("text").attr("x", x0 - 8).attr("y", d => y(d) + 4)
      .attr("text-anchor", "end").attr("font-size", 10.5).attr("fill", B.tok("--ink-3"))
      .style("font-variant-numeric", "tabular-nums").text(f);
  }

  /* ---------------- waves: small multiples ---------------- */
  const FASHION = {
    new_schools: {fam: 0, cap: "Peaks in the 14th Congress, when annexes were split into new high schools."},
    school_names: {fam: 0, cap: "Usually renamed after a person. Common before 1972 and again from 1987 to 1992."},
    colleges: {fam: 0, cap: "Up sharply in the 17th Congress, which made tuition at these schools free in 2017."},
    beds: {fam: 1, cap: "290 laws in the 8th Congress, and many more again after 2016."},
    new_hospitals: {fam: 1, cap: "Mostly emergency and municipal hospitals, before 1972."},
    national_roads: {fam: 3, cap: "Making a road national moves its upkeep to the national budget."},
    franchises: {fam: 5, cap: "Once given to power plants and phone lines too. Now mostly broadcasters and telecoms."},
    holidays: {fam: 4, cap: "Usually a town's founding anniversary, made a special non-working day."},
    courts: {fam: 4, cap: "New trial court branches, added a few Congresses at a time."},
    barangays: {fam: 2, cap: "Drops after the 1959 Barrio Charter let provincial boards create barrios."},
    cityhood: {fam: 2, cap: "Towns turned into cities, mostly from 1995 to 2007."},
    renamed_places: {fam: 2, cap: "The same charter let provincial boards rename barrios."},
  };
  C.multiples = function () {
    const wrap = B.$("#multiples"); wrap.replaceChildren();
    const cols = B.famColors();
    D.fashions.kinds.forEach(k => {
      const meta = FASHION[k.key] || {fam: 0, cap: ""};
      const box = B.el("div", {class: "mini"});
      const h = B.el("h4", {}, B.el("i", {style: `background:${cols[meta.fam]}`}), document.createTextNode(k.label));
      const ch = B.el("div", {class: "chart"});
      box.append(h, B.el("div", {class: "cap", text: meta.cap}), ch);
      wrap.append(box);
      const W = ch.clientWidth || 240, H = 104, m = {t: 16, r: 2, b: 16, l: 2};
      const x = d3.scaleBand().domain(CONG).range([m.l, W - m.r]).paddingInner(0.22);
      const max = d3.max(Object.values(k.counts)) || 1;
      const y = d3.scaleLinear().domain([0, max]).range([H - m.b, m.t]);
      const svg = B.svgIn(ch, W, H);
      svg.append("text").attr("x", m.l).attr("y", 10).attr("font-size", 9.5).attr("fill", B.tok("--ink-3")).text("max " + fmt(max));
      CONG.forEach(c => {
        if (c === "gap") return;
        const v = k.counts[c] || 0, bx = x(c), bw = x.bandwidth();
        svg.append("rect").attr("x", bx - 1).attr("y", m.t).attr("width", bw + 2).attr("height", H - m.b - m.t).attr("fill", "transparent")
          .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(v)} laws`}, {text: k.label}, {cls: "tm", text: `${ord(c)} Congress, ${B.CONG_YEARS[c]}`}]))
          .call(tipOff);
        if (v) svg.append("path").attr("d", B.roundedTop(bx, y(v), bw, y(0) - y(v), Math.min(3, bw / 2))).attr("fill", cols[meta.fam]).attr("pointer-events", "none");
      });
      svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(0) + 0.5).attr("y2", y(0) + 0.5).attr("stroke", B.tok("--axis"));
      [[1, "1946", "start"], [7, "1972", "end"], [8, "1987", "start"], [20, "2026", "end"]].forEach(([c, t, a]) => {
        svg.append("text").attr("x", a === "start" ? x(c) : x(c) + x.bandwidth()).attr("y", H - 3).attr("text-anchor", a)
          .attr("font-size", 9).attr("fill", B.tok("--ink-3")).text(t);
      });
    });
  };

  /* ---------------- bills: the 8th Congress waffle ---------------- */
  let waffleShown = false;
  C.waffle = function () {
    const el = B.$("#waffle");
    const panel = B.$("#wafflepanel");
    const e8 = D.bills.eighth;
    const local = e8.filed.filed_local || 0, nat = e8.filed.filed_national || 0, priv = e8.filed.filed_private || 0;
    const lit = Math.min(local, e8.laws.local || 0);
    const total = local + nat + priv;
    const W = el.clientWidth || 900;
    const maxH = W < 620 ? 620 : 560;
    let s = Math.sqrt(W * maxH / total);
    s = Math.max(2, Math.min(6, s));
    const cols = Math.floor(W / s), rowsN = Math.ceil(total / cols);
    const H = Math.ceil(rowsN * s);
    const {ctx} = B.canvasIn(el, W, H);
    const gap = s >= 3.5 ? 1 : 0.5, cell = s - gap;
    const glow = B.tok("--glow", panel), f6 = B.tok("--f6", panel), f5 = B.tok("--f5", panel);
    const groups = [
      {n: lit, color: glow, alpha: 1, label: `Local laws the 8th Congress passed: ${fmt(lit)}`},
      {n: local - lit, color: glow, alpha: 0.2, label: `Other local bills: ${fmt(local - lit)}`},
      {n: priv, color: f5, alpha: 0.6, label: `Private bills: ${fmt(priv)}`},
      {n: nat, color: f6, alpha: 0.75, label: `National bills: ${fmt(nat)}`},
    ];
    const lg = B.$("#wafflelegend"); lg.replaceChildren();
    groups.forEach(g => lg.append(B.el("span", {}, B.el("span", {class: "sw", style: `background:${g.color};opacity:${Math.max(0.35, g.alpha)}`}), document.createTextNode(g.label))));
    // Squares run local, private, national. The bright ones are spread evenly through the
    // local squares, one in every local/lit, since the record does not say which bills passed.
    const kind = new Uint8Array(total);
    for (let i = 0; i < total; i++) kind[i] = i < local ? 1 : (i < local + priv ? 2 : 3);
    const stepLit = local / Math.max(1, lit);
    for (let j = 0; j < lit; j++) {
      const i = Math.min(local - 1, Math.floor(j * stepLit + B.hash(j + 11) * stepLit));
      kind[i] = 0;
    }
    const paint = upto => {
      ctx.clearRect(0, 0, W, H);
      const last = Math.min(total, (upto + 1) * cols);
      [1, 2, 3, 0].forEach(k => {
        const g = groups[k];
        ctx.fillStyle = g.color; ctx.globalAlpha = g.alpha;
        ctx.beginPath();
        for (let i = 0; i < last; i++) if (kind[i] === k) ctx.rect((i % cols) * s, Math.floor(i / cols) * s, cell, cell);
        ctx.fill();
        if (k === 0) {  // a soft glow on the laws that passed
          ctx.save(); ctx.globalAlpha = 0.5; ctx.shadowColor = g.color; ctx.shadowBlur = 6; ctx.fill(); ctx.restore();
        }
      });
      ctx.globalAlpha = 1;
    };
    if (waffleShown || B.reduced) { paint(rowsN); return; }
    B.whenVisible(el, () => {
      waffleShown = true;
      const t0 = performance.now(), dur = 1600;
      const tick = now => {
        const t = Math.min(1, (now - t0) / dur);
        paint(Math.floor(d3.easeCubicOut(t) * rowsN));
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, "-80px");
    paint(-1);
  };

  let wishI = 0;
  C.wish = function () {
    const ex = D.bills.examples_8th, el = B.$("#wish");
    const next = () => {
      el.style.opacity = 0;
      setTimeout(() => {
        let t = ex[wishI % ex.length];
        const again = t.search(/\S(?=an act\b)/i);
        if (again > 20) t = t.slice(0, again + 1);
        el.textContent = t.replace(/(Therefor|Thereof)\S*.*$/, "$1").replace(/\s+\S*$/, t.length >= 219 ? "..." : "$&");
        el.style.opacity = 1; wishI++;
      }, B.reduced ? 0 : 260);
    };
    next();
    B.$("#wishnext").addEventListener("click", next);
  };

  /* ---------------- bills filed and enacted ---------------- */
  let billScope = "local";
  C.bills = function () {
    const el = B.$("#billchart");
    const W = el.clientWidth || 520, small = W < 520, H = small ? 250 : 290, m = {t: 16, r: 6, b: 38, l: 46};
    const cs = Object.keys(D.bills.funnel).map(Number).sort((a, b) => a - b);
    const x = d3.scaleBand().domain(cs).range([m.l, W - m.r]).paddingInner(0.28);
    const linked = c => c >= 13 && c <= 19;
    const vals = cs.map(c => ({c, filed: D.bills.funnel[c]["filed_" + billScope] || 0,
      enacted: linked(c) ? (D.bills.funnel[c]["enacted_" + billScope] || 0) : 0}));
    const y = d3.scaleLinear().domain([0, d3.max(vals, v => v.filed)]).nice().range([H - m.b, m.t]);
    const svg = B.svgIn(el, W, H);
    yGrid(svg, y, m.l, W - m.r, y.ticks(5));
    const bw = Math.min(30, x.bandwidth());
    const colF = billScope === "local" ? B.tok("--seq3") : B.tok("--f6");
    const colE = billScope === "local" ? B.tok("--accent") : B.tok("--ink");
    vals.forEach(v => {
      const bx = x(v.c) + (x.bandwidth() - bw) / 2;
      svg.append("path").attr("d", B.roundedTop(bx, y(v.filed), bw, y(0) - y(v.filed), 4)).attr("fill", colF).attr("opacity", billScope === "local" ? 0.9 : 0.8)
        .on("pointermove", e => B.showTip(e, [
          {cls: "tv", text: `${fmt(v.filed)} ${billScope} bills filed`},
          {text: linked(v.c) ? `${fmt(v.enacted)} became law (${pct1(v.enacted / Math.max(1, v.filed))})` : "The House record does not link these bills to laws"},
          {cls: "tm", text: `${ord(v.c)} Congress, ${B.CONG_YEARS[v.c]}`},
        ])).call(tipOff);
      if (v.enacted) svg.append("rect").attr("x", bx).attr("y", y(v.enacted)).attr("width", bw)
        .attr("height", Math.max(1.5, y(0) - y(v.enacted))).attr("fill", colE).attr("pointer-events", "none");
      if (!small || v.c % 2 === 0) svg.append("text").attr("x", x(v.c) + x.bandwidth() / 2).attr("y", H - m.b + 15).attr("text-anchor", "middle")
        .attr("font-size", 10.5).attr("fill", B.tok("--ink-2")).text(ord(v.c));
      if (!small && [8, 12, 16, 20].includes(v.c)) svg.append("text").attr("x", x(v.c) + x.bandwidth() / 2).attr("y", H - m.b + 28)
        .attr("text-anchor", "middle").attr("font-size", 9).attr("fill", B.tok("--ink-3")).text(B.CONG_YEARS[v.c].slice(0, 4));
    });
    svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(0) + 0.5).attr("y2", y(0) + 0.5).attr("stroke", B.tok("--axis"));
    const win = vals.filter(v => linked(v.c));
    const f = d3.sum(win, v => v.filed), en = d3.sum(win, v => v.enacted);
    const other = billScope === "local" ? "national" : "local";
    const fo = d3.sum(win, v => D.bills.funnel[v.c]["filed_" + other] || 0), eo = d3.sum(win, v => D.bills.funnel[v.c]["enacted_" + other] || 0);
    B.$("#billnote").textContent = `From the 13th to the 19th Congress, ${pct1(en / f)} of ${billScope} House bills became law, ` +
      `compared with ${pct1(eo / fo)} of ${other} bills. The 20th Congress is still in session.`;
    B.table(B.$("#billtable"), ["Congress", "Local filed", "Local enacted", "National filed", "National enacted"],
      cs.map(c => { const d = D.bills.funnel[c]; return [`${ord(c)} (${B.CONG_YEARS[c]})`, d.filed_local || 0, linked(c) ? (d.enacted_local || 0) : "", d.filed_national || 0, linked(c) ? (d.enacted_national || 0) : ""]; }));
  };
  function bindSeg(attr, set, redraw) {
    B.$$(`[data-${attr}]`).forEach(b => b.addEventListener("click", () => {
      set(b.dataset[attr.replace(/-./g, s => s[1].toUpperCase())]);
      B.$$(`[data-${attr}]`).forEach(o => o.setAttribute("aria-pressed", String(o === b)));
      redraw();
    }));
  }

  let dayCong = "18";
  C.days = function () {
    const el = B.$("#daychart");
    const W = el.clientWidth || 520, H = 230, m = {t: 18, r: 8, b: 26, l: 42};
    const days = new Map((D.bills.daily[dayCong] || []).map(d => [d[0], d[1]]));
    const start = {"17": "2016-06-30", "18": "2019-07-01", "19": "2022-06-30"}[dayCong];
    const d0 = Date.parse(start + "T00:00:00Z");
    const series = d3.range(60).map(i => { const iso = new Date(d0 + i * 864e5).toISOString().slice(0, 10); return {i, iso, n: days.get(iso) || 0}; });
    const x = d3.scaleBand().domain(series.map(s => s.i)).range([m.l, W - m.r]).paddingInner(0.18);
    const y = d3.scaleLinear().domain([0, d3.max(series, s => s.n) || 1]).nice().range([H - m.b, m.t]);
    const svg = B.svgIn(el, W, H);
    yGrid(svg, y, m.l, W - m.r, y.ticks(4));
    series.forEach(s => {
      const bx = x(s.i), bw = x.bandwidth();
      svg.append("rect").attr("x", bx).attr("y", m.t).attr("width", bw).attr("height", H - m.b - m.t).attr("fill", "transparent")
        .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(s.n)} bills filed`}, {cls: "tm", text: B.dateText(s.iso)}])).call(tipOff);
      if (s.n) svg.append("path").attr("d", B.roundedTop(bx, y(s.n), bw, y(0) - y(s.n), Math.min(3, bw / 2))).attr("fill", B.tok("--f0")).attr("pointer-events", "none");
    });
    const top = series.reduce((a, b) => (b.n > a.n ? b : a), series[0]);
    if (top.n) svg.append("text").attr("x", x(top.i) + x.bandwidth() + 7).attr("y", y(top.n) + 10).attr("font-size", 11.5)
      .attr("fill", B.tok("--ink")).text(`${fmt(top.n)} bills on ${B.dateText(top.iso)}`);
    [[0, "start"], [29, "middle"], [59, "end"]].forEach(([i, a]) => svg.append("text")
      .attr("x", a === "start" ? x(i) : a === "end" ? x(i) + x.bandwidth() : x(i) + x.bandwidth() / 2).attr("y", H - 8).attr("text-anchor", a)
      .attr("font-size", 10).attr("fill", B.tok("--ink-3")).text(`Day ${i + 1}`));
    svg.append("line").attr("x1", m.l).attr("x2", W - m.r).attr("y1", y(0) + 0.5).attr("y2", y(0) + 0.5).attr("stroke", B.tok("--axis"));
  };

  /* ---------------- effort: laws weighed by Senate time ---------------- */
  C.effort = function () {
    const E = D.effort, S = E.scopes;
    const scopes = [["local", "Local", "--accent"], ["private", "Private", "--f5"], ["national", "National", "--f6"]];
    const rows = [["laws", "Laws", "laws"], ["floor_days", "Days on the Senate floor", "floor days"],
      ["debate_days", "Days of debate", "days of debate"], ["certified", "Laws certified urgent", "certified laws"]];
    const el = B.$("#effortchart");
    // on small screens the labels sit above the bars
    const W = el.clientWidth || 900, small = W < 640, rowH = small ? 50 : 40, m = {t: 6, r: 8, b: 8, l: small ? 0 : 230};
    const H = m.t + rowH * rows.length + m.b + 30;
    const barY = small ? 18 : 5;
    const svg = B.svgIn(el, W, H);
    const x = d3.scaleLinear().domain([0, 1]).range([m.l, W - m.r]);
    const onDark = c => d3.hsl(c).l < 0.55;
    rows.forEach(([key, lab, unit], i) => {
      const tot = d3.sum(scopes, s => S[s[0]][key]);
      const cy = m.t + i * rowH;
      svg.append("text").attr("x", small ? 0 : m.l - 12).attr("y", small ? cy + 12 : cy + 18).attr("text-anchor", small ? "start" : "end")
        .attr("font-size", small ? 10.5 : 11.5).attr("fill", i === 0 ? B.tok("--ink") : B.tok("--ink-2"))
        .attr("font-weight", i === 0 ? 600 : 400).text(`${lab} (${fmt(tot)})`);
      let acc = 0;
      scopes.forEach(([s, name, col], j) => {
        const v = S[s][key];
        const x0 = x(acc / tot), x1 = x((acc + v) / tot);
        acc += v;
        const w = Math.max(0, x1 - x0 - 2), c = B.tok(col);
        svg.append("path").attr("d", j === scopes.length - 1 ? B.roundedRight(x0, cy + barY, w, 22, 4) : `M${x0},${cy + barY}h${w}v22h${-w}Z`).attr("fill", c)
          .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(v)} ${unit} · ${pct(v / tot)}`}, {key: c, text: `${name} laws`}, {cls: "tm", text: lab}]))
          .call(tipOff);
        if (w > 34) svg.append("text").attr("x", x0 + 7).attr("y", cy + barY + 15).attr("font-size", 10.5).attr("pointer-events", "none")
          .attr("fill", onDark(c) ? "#ffffff" : "#16140f").text(pct(v / tot));
      });
    });
    let lx = small ? 0 : m.l;
    const ly = m.t + rowH * rows.length + 16;
    scopes.forEach(([, name, col]) => {
      const g = svg.append("g");
      g.append("rect").attr("x", lx).attr("y", ly - 9).attr("width", 10).attr("height", 10).attr("rx", 3).attr("fill", B.tok(col));
      const t = g.append("text").attr("x", lx + 15).attr("y", ly).attr("font-size", 10.5).attr("fill", B.tok("--ink-2")).text(name);
      lx += t.node().getComputedTextLength() + 34;
    });
  };
  C.effortList = function () {
    const ul = B.$("#effortlist"); ul.replaceChildren();
    const byRa = new Map(D.laws.rows.map(r => [r[0], r]));
    D.effort.top.forEach(t => {
      const row = byRa.get(t.ra);
      const li = B.el("li");
      li.append(B.el("span", {class: "meta", text: `${t.year} · RA ${t.ra} · ${t.debate_days} days of debate, ${t.floor_days} on the floor${t.certified ? " · certified urgent" : ""}`}),
        B.el("a", {href: row ? B.lawUrl(row) : "https://lawphil.net/statutes/repacts/repacts.html", target: "_blank", rel: "noopener",
          text: B.shorten(t.title, 140)}));
      ul.append(li);
    });
  };

  /* ---------------- hospitals ---------------- */
  let bedPeriod = "2016";
  C.bedSummary = function () {
    const rec = D.hospitals.beds.filter(b => b.year >= 2016);
    const leg = d3.sum(rec, b => b.to), acc = d3.sum(rec, b => b.accredited);
    const box = B.$("#bedsummary"); box.replaceChildren();
    const mk = (n, l, frac, color) => {
      const bar = B.el("div", {class: "bar"}, B.el("i", {style: `background:${color}`}));
      const side = B.el("div", {class: "side"}, B.el("span", {class: "n", text: fmt(n)}), B.el("span", {class: "l", text: l}), bar);
      box.append(side);
      const go = () => { bar.firstChild.style.width = (frac * 100).toFixed(1) + "%"; };
      if (B.reduced) go(); else B.whenVisible(side, () => setTimeout(go, 150), "-60px");
    };
    mk(leg, `beds set by laws passed since 2016 for ${rec.length} hospitals`, 1, B.tok("--f1"));
    mk(acc, `beds PhilHealth accredits at those hospitals, ${pct(acc / leg)} of that number`, acc / leg, B.tok("--ink-2"));
  };
  C.beds = function () {
    const el = B.$("#bedchart");
    const list = D.hospitals.beds.filter(b => bedPeriod === "all" || b.year >= 2016)
      .sort((a, b) => (b.to - b.accredited) - (a.to - a.accredited) || b.to - a.to);
    const W = el.clientWidth || 900, small = W < 640;
    const rowH = small ? 22 : 24, m = {t: 26, r: 18, b: 10, l: small ? 132 : 330};
    const H = m.t + rowH * list.length + m.b;
    const x = d3.scaleLinear().domain([0, d3.max(list, b => Math.max(b.to, b.accredited))]).nice().range([m.l, W - m.r]);
    const svg = B.svgIn(el, W, H);
    const ticks = x.ticks(small ? 4 : 7);
    svg.append("g").selectAll("line").data(ticks).join("line").attr("x1", d => Math.round(x(d)) + 0.5).attr("x2", d => Math.round(x(d)) + 0.5)
      .attr("y1", m.t - 6).attr("y2", H - m.b).attr("stroke", B.tok("--grid"));
    svg.append("g").selectAll("text").data(ticks).join("text").attr("x", d => x(d)).attr("y", m.t - 12).attr("text-anchor", "middle")
      .attr("font-size", 10).attr("fill", B.tok("--ink-3")).text(d => fmt(d));
    svg.append("text").attr("x", m.l - 12).attr("y", m.t - 12).attr("text-anchor", "end").attr("font-size", 10).attr("fill", B.tok("--ink-3")).text("beds");
    const orange = B.tok("--f1"), ink = B.tok("--ink"), card = B.tok("--card");
    list.forEach((b, i) => {
      const cy = m.t + i * rowH + rowH / 2;
      const g = svg.append("g");
      g.append("rect").attr("x", 0).attr("y", cy - rowH / 2).attr("width", W).attr("height", rowH).attr("fill", "transparent");
      const nm = b.name.replace(/\s*\([^)]*\)\s*$/, "");
      g.append("text").attr("x", m.l - 12).attr("y", cy + 4).attr("text-anchor", "end").attr("font-size", small ? 10 : 11.5)
        .attr("fill", B.tok("--ink-2")).text(B.shorten(nm, small ? 22 : 50));
      const below = b.accredited < b.to;
      g.append("line").attr("x1", x(b.accredited)).attr("x2", x(b.to)).attr("y1", cy).attr("y2", cy)
        .attr("stroke", below ? orange : B.tok("--ink-3")).attr("stroke-width", 3).attr("stroke-opacity", 0.35).attr("stroke-linecap", "round");
      if (below) {
        g.append("circle").attr("cx", x(b.accredited)).attr("cy", cy).attr("r", 5).attr("fill", card).attr("stroke", ink).attr("stroke-width", 2);
        g.append("circle").attr("cx", x(b.to)).attr("cy", cy).attr("r", 5.5).attr("fill", orange).attr("stroke", card).attr("stroke-width", 2);
      } else {
        // the law's figure is met: draw the accredited ring over the dot so both stay visible
        g.append("circle").attr("cx", x(b.to)).attr("cy", cy).attr("r", 3.5).attr("fill", orange);
        g.append("circle").attr("cx", x(b.accredited)).attr("cy", cy).attr("r", 6.5).attr("fill", "none").attr("stroke", ink).attr("stroke-width", 2);
      }
      g.on("pointermove", e => B.showTip(e, [
        {cls: "tv", text: `${fmt(b.to)} beds by law · ${fmt(b.accredited)} accredited`},
        {cls: "tt", text: b.name},
        {cls: "tm", text: `RA ${b.ra} (${b.year})${b.from ? `, from ${fmt(b.from)} beds` : ""}${b.province ? " · " + b.province : ""}`},
        {text: `PhilHealth: ${b.philhealth_name}, ${b.level}`},
      ])).call(tipOff);
    });
    B.table(B.$("#bedtable"), ["Hospital", "Law", "Year", "Beds by law", "Beds accredited", "Province"],
      list.map(b => [b.name, {href: `https://lawphil.net/statutes/repacts/ra${b.year}/ra_${b.ra}_${b.year}.html`, text: `RA ${b.ra}`}, String(b.year), b.to, b.accredited, b.province]));
  };

  /* ---------------- schools ---------------- */
  C.schools = function () {
    const lv = D.schools.levels;
    const actions = [["all", "All of these laws"], ["establish", "Establish or create a school"], ["separate", "Make an annex independent"], ["convert", "Convert a school"]];
    const levels = [["named", "Found by name in the right town", "--f0"], ["barangay", "A school at the same level in that barangay", "--f2"],
      ["annex", "Still listed as an annex", "--f3"], ["not_found", "Not found", "--f1"], ["no_town", "Town or name not identified", "--f6"]];
    const group = {all: ["establish", "create", "separate", "convert"], establish: ["establish", "create"], separate: ["separate"], convert: ["convert"]};
    const get = (a, k) => d3.sum(group[a], x => (lv[`${x}|${k}`] || 0) + (k === "no_town" ? (lv[`${x}|no_name`] || 0) : 0));
    const el = B.$("#schoolchart");
    // on small screens the labels sit above the bars
    const W = el.clientWidth || 900, small = W < 640, rowH = small ? 50 : 40, m = {t: 6, r: 8, b: 8, l: small ? 0 : 230};
    const H = m.t + rowH * actions.length + m.b + (small ? 70 : 40);
    const barY = small ? 18 : 5;
    const svg = B.svgIn(el, W, H);
    const x = d3.scaleLinear().domain([0, 1]).range([m.l, W - m.r]);
    const onDark = c => d3.hsl(c).l < 0.55;
    actions.forEach(([a, lab], i) => {
      const tot = d3.sum(levels, l => get(a, l[0]));
      const cy = m.t + i * rowH;
      svg.append("text").attr("x", small ? 0 : m.l - 12).attr("y", small ? cy + 12 : cy + 18).attr("text-anchor", small ? "start" : "end")
        .attr("font-size", small ? 10.5 : 11.5).attr("fill", a === "all" ? B.tok("--ink") : B.tok("--ink-2"))
        .attr("font-weight", a === "all" ? 600 : 400).text(`${lab} (${fmt(tot)})`);
      let acc = 0;
      const vis = levels.filter(l => get(a, l[0]) > 0);
      vis.forEach(([k, name, col], j) => {
        const v = get(a, k);
        const x0 = x(acc / tot), x1 = x((acc + v) / tot);
        acc += v;
        const w = Math.max(0, x1 - x0 - 2);
        const c = B.tok(col);
        const last = j === vis.length - 1;
        svg.append("path").attr("d", last ? B.roundedRight(x0, cy + barY, w, 22, 4) : `M${x0},${cy + barY}h${w}v22h${-w}Z`).attr("fill", c)
          .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(v)} laws · ${pct(v / tot)}`}, {key: c, text: name}, {cls: "tm", text: lab}]))
          .call(tipOff);
        if (w > 40) svg.append("text").attr("x", x0 + 7).attr("y", cy + barY + 15).attr("font-size", 10.5).attr("pointer-events", "none")
          .attr("fill", onDark(c) ? "#ffffff" : "#16140f").text(pct(v / tot));
      });
    });
    let lx = small ? 0 : m.l, ly = m.t + rowH * actions.length + 16;
    levels.forEach(([k, name, col]) => {
      const g = svg.append("g");
      g.append("rect").attr("x", lx).attr("y", ly - 9).attr("width", 10).attr("height", 10).attr("rx", 3).attr("fill", B.tok(col));
      const t = g.append("text").attr("x", lx + 15).attr("y", ly).attr("font-size", 10.5).attr("fill", B.tok("--ink-2")).text(name);
      lx += t.node().getComputedTextLength() + 34;
      if (lx > W - 150) { lx = small ? 0 : m.l; ly += 18; }
    });
    B.table(B.$("#schooltable"), ["Law", "Year", "School named in the law", "Title"],
      D.schools.not_found.map(s => [{href: `https://lawphil.net/statutes/repacts/ra${s.year}/ra_${s.ra}_${s.year}.html`, text: `RA ${s.ra}`}, String(s.year), s.target || "", s.title]));
  };

  /* ---------------- authors ---------------- */
  C.family = function () {
    const A = D.authors;
    const el = B.$("#famchart");
    const W = el.clientWidth || 440, H = 170, m = {t: 18, r: 40, b: 34, l: 104};
    const rows = [["Family seats", A.family, "--f4"], ["Other seats", A.other, "--ink-3"]];
    const x = d3.scaleLinear().domain([0, Math.max(2, d3.max(rows, r => r[1].hi))]).nice().range([m.l, W - m.r]);
    const svg = B.svgIn(el, W, H);
    svg.append("g").selectAll("line").data(x.ticks(4)).join("line").attr("x1", d => x(d) + 0.5).attr("x2", d => x(d) + 0.5)
      .attr("y1", m.t).attr("y2", H - m.b).attr("stroke", B.tok("--grid"));
    svg.append("g").selectAll("text").data(x.ticks(4)).join("text").attr("x", d => x(d)).attr("y", H - m.b + 15)
      .attr("text-anchor", "middle").attr("font-size", 10).attr("fill", B.tok("--ink-3")).text(d => d);
    rows.forEach(([lab, s, col], i) => {
      const cy = m.t + 26 + i * 50, c = B.tok(col);
      svg.append("text").attr("x", m.l - 12).attr("y", cy + 4).attr("text-anchor", "end").attr("font-size", 11.5).attr("fill", B.tok("--ink-2")).text(lab);
      svg.append("line").attr("x1", x(s.lo)).attr("x2", x(s.hi)).attr("y1", cy).attr("y2", cy).attr("stroke", c).attr("stroke-width", 2.5).attr("stroke-linecap", "round");
      svg.append("circle").attr("cx", x(s.mean)).attr("cy", cy).attr("r", 7).attr("fill", c).attr("stroke", B.tok("--card")).attr("stroke-width", 2)
        .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${dec(s.mean)} local laws per term`}, {text: `${lab}: ${fmt(s.n)} terms`},
          {cls: "tm", text: `95% interval ${dec(s.lo)} to ${dec(s.hi)} · median ${s.median} · ${pct(s.zero_share)} passed none`}])).call(tipOff);
      svg.append("text").attr("x", x(s.hi) + 9).attr("y", cy + 4).attr("font-size", 12).attr("font-weight", 600).attr("fill", B.tok("--ink")).text(dec(s.mean));
    });
    svg.append("text").attr("x", m.l).attr("y", H - 3).attr("font-size", 9.5).attr("fill", B.tok("--ink-3")).text("local laws per term");

    const el2 = B.$("#famcong");
    const W2 = el2.clientWidth || 440, H2 = 206, m2 = {t: 14, r: 12, b: 36, l: 34};
    const cs = Object.keys(A.by_congress).map(Number);
    const x2 = d3.scalePoint().domain(cs).range([m2.l + 16, W2 - m2.r - 16]);
    const mx = d3.max(cs, c => Math.max(A.by_congress[c].family.mean, A.by_congress[c].other.mean));
    const y2 = d3.scaleLinear().domain([0, mx]).nice().range([H2 - m2.b, m2.t]);
    const svg2 = B.svgIn(el2, W2, H2);
    yGrid(svg2, y2, m2.l, W2 - m2.r, y2.ticks(4), d => d);
    cs.forEach(c => {
      const b = A.by_congress[c], cx = x2(c);
      svg2.append("line").attr("x1", cx).attr("x2", cx).attr("y1", y2(b.family.mean)).attr("y2", y2(b.other.mean)).attr("stroke", B.tok("--axis")).attr("stroke-width", 2);
      [["family", "--f4", -4], ["other", "--ink-3", 4]].forEach(([k, col, dx]) => {
        svg2.append("circle").attr("cx", cx + dx).attr("cy", y2(b[k].mean)).attr("r", 5.5).attr("fill", B.tok(col)).attr("stroke", B.tok("--card")).attr("stroke-width", 2)
          .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${dec(b[k].mean)} local laws per term`},
            {key: B.tok(col), text: k === "family" ? "Family seats" : "Other seats"},
            {cls: "tm", text: `${ord(c)} Congress · ${fmt(b[k].n)} terms · family share ${pct(b.family_share)}`}])).call(tipOff);
      });
      svg2.append("text").attr("x", cx).attr("y", H2 - m2.b + 16).attr("text-anchor", "middle").attr("font-size", 10.5).attr("fill", B.tok("--ink-2")).text(ord(c));
      svg2.append("text").attr("x", cx).attr("y", H2 - m2.b + 29).attr("text-anchor", "middle").attr("font-size", 9).attr("fill", B.tok("--ink-3")).text(B.CONG_YEARS[c].slice(0, 4));
    });
  };
  C.topAuthors = function () {
    const el = B.$("#topauthors");
    const list = D.authors.top.slice(0, 15);
    const W = el.clientWidth || 900, small = W < 640, rowH = 26, m = {t: 4, r: 40, b: 6, l: small ? 150 : 320};
    const H = m.t + rowH * list.length + m.b;
    const x = d3.scaleLinear().domain([0, d3.max(list, a => a.laws)]).range([m.l, W - m.r]);
    const svg = B.svgIn(el, W, H);
    list.forEach((a, i) => {
      const cy = m.t + i * rowH;
      svg.append("text").attr("x", m.l - 12).attr("y", cy + 16).attr("text-anchor", "end").attr("font-size", small ? 10 : 11.5)
        .attr("fill", B.tok("--ink")).text(small ? a.name : `${a.name}, ${a.province}`);
      svg.append("path").attr("d", B.roundedRight(m.l, cy + 5, x(a.laws) - m.l, 15, 4)).attr("fill", B.tok("--f0"))
        .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(a.laws)} local laws`}, {cls: "tt", text: a.name},
          {cls: "tm", text: `${a.province} · ${a.congresses.map(ord).join(", ")} Congress · mostly ${a.top_category.toLowerCase()}`}])).call(tipOff);
      svg.append("text").attr("x", x(a.laws) + 7).attr("y", cy + 16.5).attr("font-size", 11).attr("fill", B.tok("--ink-2")).text(a.laws);
    });
  };

  /* ---------------- calendar ---------------- */
  C.calendar = function () {
    const el = B.$("#calchart");
    const panel = el.closest(".panel");
    const W = el.clientWidth || 900, small = W < 640;
    const years = d3.range(1946, 2027).filter(y => y <= 1972 || y >= 1987);
    const labelW = small ? 34 : 44, cellH = small ? 3.6 : 5.2, gapRow = 16, top = 20;
    const H = Math.ceil(top + cellH * years.length + gapRow + 6);
    const {cv, ctx} = B.canvasIn(el, W, H);
    cv.setAttribute("role", "img");
    cv.setAttribute("aria-label", "Heat map of laws approved on each day of the year, 1946 to 2026. Before 1972 most laws are approved in June.");
    const cw = (W - labelW - 2) / 366;
    const days = D.calendar.days;
    const ramp = [2, 3, 4, 5, 6, 7].map(i => B.tok("--seq" + i, panel));
    const col = d3.scaleThreshold().domain([2, 5, 12, 30, 80]).range(ramp);
    const yOf = y => top + years.indexOf(y) * cellH + (y >= 1987 ? gapRow : 0);
    ctx.font = `10px ${B.tok("--mono")}`; ctx.fillStyle = B.tok("--ink-3", panel); ctx.textAlign = "center";
    const mStarts = [1, 32, 60, 91, 121, 152, 182, 213, 244, 274, 305, 335];
    mStarts.forEach((d, i) => ctx.fillText(B.MONTHS[i].slice(0, small ? 1 : 3), labelW + (d + 14) * cw, top - 7));
    ctx.textAlign = "right";
    [1950, 1960, 1970, 1990, 2000, 2010, 2020].forEach(y => ctx.fillText(String(y), labelW - 6, yOf(y) + cellH));
    ctx.fillStyle = B.tok("--nodata", panel);
    years.forEach(y => ctx.fillRect(labelW, yOf(y), cw * 366, cellH - 0.7));
    years.forEach(y => (days[y] || []).forEach(([doy, n]) => {
      ctx.fillStyle = col(n);
      ctx.fillRect(labelW + (doy - 1) * cw, yOf(y), Math.max(1.2, cw), cellH - 0.7);
    }));
    ctx.fillStyle = B.tok("--ink-3", panel); ctx.textAlign = "left";
    ctx.fillText("1973 to 1986: no Republic Acts", labelW, yOf(1972) + cellH + gapRow * 0.72);
    cv.addEventListener("pointermove", e => {
      const b = cv.getBoundingClientRect();
      const mx = (e.clientX - b.left) * (W / b.width), my = (e.clientY - b.top) * (H / b.height);
      const doy = Math.floor((mx - labelW) / cw) + 1;
      const y = years.find(yy => my >= yOf(yy) && my < yOf(yy) + cellH);
      if (!y || doy < 1 || doy > 366) { B.hideTip(); return; }
      const hit = (days[y] || []).find(d => d[0] === doy);
      const dt = new Date(Date.UTC(y, 0, doy));
      B.showTip(e, [{cls: "tv", text: `${hit ? fmt(hit[1]) : 0} law${hit && hit[1] === 1 ? "" : "s"}`}, {cls: "tm", text: `${B.MONTHS[dt.getUTCMonth()]} ${dt.getUTCDate()}, ${y}`}]);
    });
    cv.addEventListener("pointerleave", B.hideTip);
    const lg = B.$("#callegend"); lg.replaceChildren();
    const labs = ["1", "2 to 4", "5 to 11", "12 to 29", "30 to 79", "80 or more"];
    ramp.forEach((c, i) => lg.append(B.el("span", {}, B.el("span", {class: "sw", style: `background:${c}`}), document.createTextNode(labs[i] + (i === 0 ? " law" : " laws")))));
  };

  C.lapsed = function () {
    const el = B.$("#lapsechart");
    const order = ["Roxas", "Quirino", "Magsaysay", "Garcia", "Macapagal", "Marcos Sr.", "Aquino", "Ramos", "Estrada", "Arroyo", "Aquino III", "Duterte", "Marcos Jr."];
    const L = D.calendar.lapsed;
    const list = order.filter(p => L[p]).map(p => ({p, ...L[p], share: L[p].lapsed / L[p].total}));
    const W = el.clientWidth || 440, rowH = 23, m = {t: 4, r: 48, b: 8, l: 88};
    const H = m.t + rowH * list.length + m.b;
    const x = d3.scaleLinear().domain([0, d3.max(list, d => d.share)]).range([m.l, W - m.r]);
    const svg = B.svgIn(el, W, H);
    list.forEach((d, i) => {
      const cy = m.t + i * rowH;
      svg.append("text").attr("x", m.l - 10).attr("y", cy + 15).attr("text-anchor", "end").attr("font-size", 11).attr("fill", B.tok("--ink-2")).text(d.p);
      svg.append("rect").attr("x", 0).attr("y", cy).attr("width", W).attr("height", rowH).attr("fill", "transparent")
        .on("pointermove", e => B.showTip(e, [{cls: "tv", text: `${fmt(d.lapsed)} of ${fmt(d.total)} laws lapsed`},
          {text: `${d.p} · ${fmt(d.local)} of the lapsed laws were local`}])).call(tipOff);
      if (d.lapsed) svg.append("path").attr("d", B.roundedRight(m.l, cy + 5, Math.max(2, x(d.share) - m.l), 13, 4))
        .attr("fill", d.p === "Ramos" ? B.tok("--accent") : B.tok("--f6")).attr("pointer-events", "none");
      svg.append("text").attr("x", Math.max(m.l, x(d.share)) + 7).attr("y", cy + 15).attr("font-size", 10.5).attr("fill", B.tok("--ink-2"))
        .attr("pointer-events", "none").text(d.lapsed ? (d.share < 0.005 ? "under 1%" : pct(d.share)) : "none");
    });
    if (L.Ramos) B.$("#lapsenote").textContent = `${fmt(L.Ramos.lapsed)} laws, ${pct(L.Ramos.lapsed / L.Ramos.total)} of those passed under Fidel Ramos, took effect without his signature. Most were local.`;
  };
  C.citizens = function () {
    const ul = B.$("#citlist"); ul.replaceChildren();
    const byRa = new Map(D.laws.rows.map(r => [r[0], r]));
    D.odd.citizenship.slice().reverse().slice(0, 30).forEach(c => {
      const li = B.el("li");
      const row = byRa.get(c.ra);
      li.append(B.el("span", {class: "meta", text: `${c.year} · RA ${c.ra}`}),
        B.el("a", {href: row ? B.lawUrl(row) : "https://lawphil.net/statutes/repacts/repacts.html", target: "_blank", rel: "noopener",
          text: c.name.replace(/[.,]\s*(with all|and for other).*$/i, "")}));
      ul.append(li);
    });
  };

  C.init = function (data) {
    D = data;
    bindSeg("billscope", v => { billScope = v; }, C.bills);
    bindSeg("day", v => { dayCong = v; }, C.days);
    bindSeg("beds", v => { bedPeriod = v; }, C.beds);
    C.wish();
    C.citizens();
    if (D.effort) C.effortList();
    const all = [C.multiples, C.waffle, C.bills, C.days, ...(D.effort ? [C.effort] : []), C.bedSummary, C.beds, C.schools, C.family, C.topAuthors, C.calendar, C.lapsed];
    all.forEach(f => { try { f(); } catch (e) { console.error(e); } });
    const again = () => all.forEach(f => { try { f(); } catch (e) { console.error(e); } });
    B.onResize(again);
    B.onTheme(again);
  };
})();
