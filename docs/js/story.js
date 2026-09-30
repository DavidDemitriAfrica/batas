/* The story: every Republic Act is one particle. Scrolling through the steps
   moves the same 12,000 particles between layouts: a timeline, blocks by
   kind, a map, columns by Congress, and towers by signing day.
   Rendering is WebGL (positions and colours are interpolated on the GPU),
   with a plain canvas fallback that draws each layout without animation. */
(function () {
  "use strict";
  const B = window.B;
  const S = (B.story = {});
  const GOLDEN = Math.PI * (3 - Math.sqrt(5));
  const LOCAL = f => f <= 4;
  const STACK_ORDER = [0, 1, 2, 3, 4, 5, 6]; // local families at the base, national on top

  let D, N, law;
  let stage, cv, svg, legendEl, descEl;
  let W = 0, H = 0, dpr = 1;
  let gl = null, prog = null, bufs = {}, ctx2d = null;
  let sx, sy, ex, ey, sc, ec, delay;       // particle state
  let sizeS = 2, sizeE = 2, stagger = 0.35, T = 1, dur = 1400, t0 = 0, raf = 0;
  let step = -1, layout = null, geo = null, provFeatures = null, quad = null, hot = -1;
  let colors = null;

  /* ---------------- data ---------------- */
  function prep() {
    const rows = D.laws.rows;
    N = rows.length;
    law = rows.map((r, i) => {
      const t = r[1] ? Date.UTC(+r[1].slice(0, 4), +r[1].slice(5, 7) - 1, +r[1].slice(8, 10)) : null;
      return {i, ra: r[0], iso: r[1], t, year: r[1] ? +r[1].slice(0, 4) : null, cong: r[2], fam: r[3],
        cat: r[4], title: r[5], provs: r[7], towns: r[8], h: B.hash(r[0])};
    });
    geo = topojson.feature(D.topo, D.topo.objects[Object.keys(D.topo.objects)[0]]);
    provFeatures = new Map(geo.features.map(f => [f.properties.province, f]));
  }

  /* ---------------- frames ---------------- */
  const mobile = () => W < 760;
  function frame(kind) {
    if (mobile()) {
      if (kind === "hero") return {x0: 12, x1: W - 12, y0: H * 0.62, y1: H - 22};
      return {x0: 14, x1: W - 14, y0: 106, y1: H * 0.57};
    }
    if (kind === "hero") return {x0: 40, x1: W - 40, y0: H * 0.6, y1: H - 44};
    const left = Math.min(Math.max(470, W * 0.38), W * 0.46);
    return {x0: left, x1: W - 48, y0: 92, y1: H - 62};
  }

  /* ---------------- colours ---------------- */
  function readColors() {
    const fam = B.famColors().map(B.rgb);
    const dark = B.isDark();
    colors = {
      fam, dark,
      glow: B.rgb(B.tok("--glow")),
      lit: B.rgb(B.tok("--ink-2")),
      base: dark ? 0.9 : 0.92,
      nat: dark ? 0.62 : 0.75,
      dim: dark ? 0.12 : 0.12,
      mono: dark ? 0.62 : 0.62,
    };
  }
  // mode: {kind: "family"} | {kind: "focus", fams: Set} | {kind: "mono"} | {kind: "monoFocus", fam}
  function paint(mode, visible) {
    const out = new Float32Array(N * 4);
    const C = colors;
    for (let i = 0; i < N; i++) {
      const f = law[i].fam;
      let rgb = C.fam[f], a = f === 6 ? C.nat : C.base;
      if (mode.kind === "focus") {
        if (mode.fams.has(f)) { if (f === 6) { rgb = C.lit; a = 0.95; } }
        else a = C.dim;
      } else if (mode.kind === "mono") {
        rgb = C.glow; a = C.mono;
      } else if (mode.kind === "monoFocus") {
        if (f === mode.fam) { a = C.base; } else { rgb = C.glow; a = C.dim * 1.3; }
      }
      if (visible && !visible[i]) a = 0;
      out[i * 4] = rgb[0]; out[i * 4 + 1] = rgb[1]; out[i * 4 + 2] = rgb[2]; out[i * 4 + 3] = a;
    }
    return out;
  }

  /* ---------------- layouts ---------------- */
  function fitStep(maxN, bandW, height, fill = 0.9, sMax = 4.2) {
    let s = sMax, k = 1;
    for (; s > 0.55; s -= 0.05) {
      k = Math.max(1, Math.floor(bandW * fill / s));
      if (Math.ceil(maxN / k) * s <= height) break;
    }
    return {s, k};
  }
  function stackedBands(bands, groupOf, f, reserveBottom = 0, reserveTop = 0) {
    // bands: array of keys (null = gap); groupOf(i) -> key
    const x = new Float32Array(N), y = new Float32Array(N), vis = new Uint8Array(N);
    const by = new Map();
    for (let i = 0; i < N; i++) {
      const g = groupOf(i);
      if (g == null) continue;
      if (!by.has(g)) by.set(g, []);
      by.get(g).push(i);
    }
    const bw = (f.x1 - f.x0) / bands.length;
    const maxN = d3.max(Array.from(by.values()), v => v.length) || 1;
    const {s, k} = fitStep(maxN, bw, f.y1 - f.y0 - reserveBottom - reserveTop);
    const base = f.y1 - reserveBottom;
    bands.forEach((g, bi) => {
      const list = by.get(g);
      if (!list) return;
      list.sort((a, b) => (STACK_ORDER[law[a].fam] - STACK_ORDER[law[b].fam]) || ((law[a].t || 0) - (law[b].t || 0)) || (a - b));
      const x0 = f.x0 + bi * bw + (bw - k * s) / 2;
      list.forEach((i, j) => {
        x[i] = x0 + (j % k) * s + s / 2;
        y[i] = base - Math.floor(j / k) * s - s / 2;
        vis[i] = 1;
      });
    });
    return {x, y, vis, s, k, bw, by, base};
  }

  function layoutYears(kind) {
    const f = frame(kind);
    const years = d3.range(1946, 2027);
    const L = stackedBands(years, i => law[i].year, f);
    L.size = Math.max(0.9, L.s * 0.84);
    L.overlay = g => {
      const yx = y => f.x0 + (y - 1946) * L.bw + L.bw / 2;
      const ticks = mobile() ? [1950, 1970, 1990, 2010] : [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020];
      ticks.forEach(t => {
        g.append("text").attr("class", "lab-mono").attr("x", yx(t)).attr("y", f.y1 + 16).attr("text-anchor", "middle").text(t);
      });
      const gx0 = yx(1973) - L.bw / 2, gx1 = yx(1986) + L.bw / 2;
      const gy = f.y1 - Math.min(90, (f.y1 - f.y0) * 0.35);
      if (!mobile()) {  // the gap is too narrow on a phone; the step text explains it
        g.append("text").attr("class", "lab").attr("x", (gx0 + gx1) / 2).attr("y", gy).attr("text-anchor", "middle").text("No Congress");
        g.append("text").attr("class", "lab-mono").attr("x", (gx0 + gx1) / 2).attr("y", gy + 15).attr("text-anchor", "middle").text("1972 to 1987");
      }
      if (kind !== "hero") {
        const top = D.story.top_year;
        const list = L.by.get(top.year) || [];
        const rows = Math.ceil(list.length / L.k);
        const px = yx(top.year), py = L.base - rows * L.s - 10;
        g.append("text").attr("class", "lab-strong").attr("x", px).attr("y", py).attr("text-anchor", "middle").text(B.fmt(top.n));
        g.append("text").attr("class", "lab-mono").attr("x", px).attr("y", py - 15).attr("text-anchor", "middle").text(top.year);
      }
    };
    L.legend = "family";
    return L;
  }

  function layoutFamilies() {
    const f = frame("main");
    const n = 7, gap = mobile() ? 6 : 16, labelH = mobile() ? 30 : 40, topH = 22;
    const gw = (f.x1 - f.x0 - gap * (n - 1)) / n;
    const x = new Float32Array(N), y = new Float32Array(N), vis = new Uint8Array(N);
    const groups = d3.range(n).map(() => []);
    law.forEach(l => groups[l.fam].push(l.i));
    const maxN = d3.max(groups, g => g.length);
    const {s, k} = fitStep(maxN, gw, f.y1 - f.y0 - labelH - topH, 0.98, 4.4);
    const base = f.y1 - labelH;
    groups.forEach((list, gi) => {
      list.sort((a, b) => ((law[a].t || 0) - (law[b].t || 0)) || (a - b));
      const gx = f.x0 + gi * (gw + gap) + (gw - k * s) / 2;
      list.forEach((i, j) => {
        x[i] = gx + (j % k) * s + s / 2;
        y[i] = base - Math.floor(j / k) * s - s / 2;
        vis[i] = 1;
      });
    });
    const L = {x, y, vis, s, size: Math.max(1, s * 0.8)};
    L.overlay = g => {
      groups.forEach((list, gi) => {
        const cx = f.x0 + gi * (gw + gap) + gw / 2;
        const rows = Math.ceil(list.length / k);
        g.append("text").attr("class", "lab-strong").attr("x", cx).attr("y", base - rows * s - 8).attr("text-anchor", "middle")
          .text(B.fmt(list.length));
        const name = mobile() ? B.SHORT_FAM[gi] : D.laws.families[gi].label;
        wrapSvg(g, name, cx, base + 16, gw + (mobile() ? 4 : 10), mobile() ? 10.5 : 12);
      });
    };
    L.legend = "none";
    return L;
  }
  function wrapSvg(g, text, cx, y, maxW, fs) {
    const t = g.append("text").attr("class", "lab").attr("x", cx).attr("y", y).attr("text-anchor", "middle").style("font-size", fs + "px");
    const words = text.split(" ");
    let line = [], tspan = t.append("tspan").attr("x", cx).attr("dy", 0), ln = 0;
    for (const w of words) {
      line.push(w);
      tspan.text(line.join(" "));
      if (tspan.node().getComputedTextLength() > maxW && line.length > 1) {
        line.pop(); tspan.text(line.join(" "));
        line = [w]; ln++;
        tspan = t.append("tspan").attr("x", cx).attr("dy", fs * 1.2).text(w);
      }
    }
  }

  let mapCache = null;
  function layoutMap() {
    const f = frame("main");
    const key = `${W}x${H}`;
    if (mapCache && mapCache.key === key) return mapCache.L;
    const proj = d3.geoMercator().fitExtent([[f.x0, f.y0], [f.x1, f.y1]], geo);
    const x = new Float32Array(N), y = new Float32Array(N), vis = new Uint8Array(N);
    const size = mobile() ? 1.35 : 1.75;
    const c = size * 0.66;
    const towns = D.laws.towns;
    const seen = new Map();
    const order = law.filter(l => LOCAL(l.fam)).sort((a, b) => ((a.t || 0) - (b.t || 0)) || (a.i - b.i));
    for (const l of order) {
      let px = null, py = null;
      const tl = l.towns.filter(t => towns[t][3] != null);
      if (tl.length) {
        const t = tl[Math.floor(l.h * tl.length) % tl.length];
        const p = proj([towns[t][3], towns[t][4]]);
        const n = seen.get(t) || 0;
        seen.set(t, n + 1);
        const r = c * Math.sqrt(n + 0.5), a = n * GOLDEN;
        px = p[0] + r * Math.cos(a); py = p[1] + r * Math.sin(a);
      } else if (l.provs.length) {
        const name = D.laws.provinces[l.provs[Math.floor(l.h * l.provs.length) % l.provs.length]];
        const pt = pointIn(provFeatures.get(name), proj, l.ra);
        if (pt) { px = pt[0]; py = pt[1]; }
      }
      if (px != null) { x[l.i] = px; y[l.i] = py; vis[l.i] = 1; }
    }
    const L = {x, y, vis, size, proj};
    // label the towns that the most local laws name (the same count the explorer shows)
    const naming = new Map();
    law.forEach(l => { if (LOCAL(l.fam)) l.towns.forEach(t => naming.set(t, (naming.get(t) || 0) + 1)); });
    // on a phone only the west coast has room for labels
    const top = Array.from(naming.entries()).filter(([t]) => towns[t][3] != null && seen.has(t) && (!mobile() || towns[t][3] < 123.2))
      .sort((a, b) => b[1] - a[1]).slice(0, mobile() ? 3 : 6);
    L.outlines = g => {
      g.append("g").selectAll("path").data(geo.features).join("path").attr("class", "outline").attr("d", d3.geoPath(proj));
    };
    L.overlay = g => {
      const path = d3.geoPath(proj);
      L.outlines(g);
      const [[lx0], [lx1]] = path.bounds(geo);
      const items = top.map(([t, n]) => {
        const p = proj([towns[t][3], towns[t][4]]);
        // towns west of about 123.2 E are labelled in the West Philippine Sea, the rest in the Pacific
        return {t, n, x: p[0], y: p[1], r: c * Math.sqrt(seen.get(t) || n) + 2, left: towns[t][3] < 123.2};
      });
      ["left", "right"].forEach(side => {
        const col = items.filter(d => (side === "left") === d.left).sort((a, b) => a.y - b.y);
        let last = -Infinity;
        col.forEach(d => { d.ly = Math.max(d.y, last + 17); last = d.ly; });
        col.forEach(d => {
          const t = g.append("text").attr("class", "lab").attr("y", d.ly + 4);
          t.text(`${B.townName(towns[d.t][1])} `).append("tspan").attr("class", "lab-strong").text(B.fmt(d.n));
          const w = t.node().getComputedTextLength();
          // in the sea beside the country, but never off the stage
          let tx = side === "left" ? lx0 - 12 : lx1 + 12;
          tx = side === "left" ? Math.max(f.x0 + w, tx) : Math.min(f.x1 - w, tx);
          t.attr("x", tx).attr("text-anchor", side === "left" ? "end" : "start");
          const sx0 = d.x + (side === "left" ? -d.r : d.r);
          g.insert("path", "text").attr("class", "leader").attr("d", `M${sx0},${d.y}L${tx + (side === "left" ? 6 : -6)},${d.ly}`);
        });
      });
    };
    L.legend = "mono";
    mapCache = {key, L};
    return L;
  }
  function pointIn(feature, proj, seed) {
    if (!feature) return null;
    const [[x0, y0], [x1, y1]] = d3.geoPath(proj).bounds(feature);
    for (let k = 0; k < 60; k++) {
      const px = x0 + B.hash(seed * 31 + k * 7.1) * (x1 - x0), py = y0 + B.hash(seed * 17 + k * 3.3) * (y1 - y0);
      if (d3.geoContains(feature, proj.invert([px, py]))) return [px, py];
    }
    return proj(d3.geoCentroid(feature));
  }

  function layoutCongress() {
    const f = frame("main");
    const bands = [1, 2, 3, 4, 5, 6, 7, null, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20];
    const L = stackedBands(bands, i => law[i].cong || null, f, mobile() ? 30 : 36, 20);
    L.size = Math.max(0.9, L.s * 0.8);
    L.overlay = g => {
      bands.forEach((c, bi) => {
        const cx = f.x0 + bi * L.bw + L.bw / 2;
        if (c == null) {
          g.append("text").attr("class", "lab-mono").attr("x", cx).attr("y", L.base - 40).attr("text-anchor", "middle")
            .attr("transform", `rotate(-90 ${cx} ${L.base - 40})`).text("no Congress");
          return;
        }
        const list = L.by.get(c) || [];
        const showOrd = !mobile() || [1, 4, 7, 8, 11, 14, 17, 20].includes(c);
        if (showOrd) g.append("text").attr("class", "lab-mono").attr("x", cx).attr("y", L.base + 15).attr("text-anchor", "middle").text(B.ord(c));
        if (!mobile() && [1, 8, 14, 20].includes(c)) g.append("text").attr("class", "lab-mono").attr("x", cx).attr("y", L.base + 29)
          .attr("text-anchor", "middle").style("opacity", 0.7).text(B.CONG_YEARS[c].slice(0, 4));
        if (!mobile() || [6, 8, 14].includes(c)) {
          const rows = Math.ceil(list.length / L.k);
          g.append("text").attr("class", [8, 14].includes(c) ? "lab-strong" : "lab").attr("x", cx).attr("y", L.base - rows * L.s - 7)
            .attr("text-anchor", "middle").style("font-size", mobile() ? "10px" : "11px").text(B.fmt(list.length));
        }
      });
    };
    L.legend = "family";
    return L;
  }

  function layoutDays() {
    const f = frame("main");
    const x = new Float32Array(N), y = new Float32Array(N), vis = new Uint8Array(N);
    const xs = d3.scaleUtc().domain([Date.UTC(1946, 0, 1), Date.UTC(2027, 0, 1)]).range([f.x0, f.x1]);
    const by = d3.group(law.filter(l => l.t != null), l => l.t);
    const maxN = d3.max(Array.from(by.values()), v => v.length);
    const sv = Math.min(3, (f.y1 - f.y0 - 34) / maxN);
    for (const [t, list] of by) {
      list.sort((a, b) => (STACK_ORDER[a.fam] - STACK_ORDER[b.fam]) || (a.i - b.i));
      const px = xs(t);
      list.forEach((l, j) => { x[l.i] = px; y[l.i] = f.y1 - j * sv - sv / 2; vis[l.i] = 1; });
    }
    const L = {x, y, vis, size: Math.max(1.1, Math.min(2.2, sv * 1.05))};
    L.overlay = g => {
      const ticks = mobile() ? [1950, 1970, 1990, 2010] : [1950, 1960, 1970, 1980, 1990, 2000, 2010, 2020];
      ticks.forEach(t => g.append("text").attr("class", "lab-mono").attr("x", xs(Date.UTC(t, 0, 1))).attr("y", f.y1 + 16)
        .attr("text-anchor", "middle").text(t));
      const top = D.calendar.big_days.slice(0, mobile() ? 1 : 2);
      top.forEach(([iso, n], j) => {
        const px = xs(Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)));
        const py = f.y1 - n * sv;
        const tx = px + (j === 0 ? 34 : -34), ty = py + (j === 0 ? -4 : 26);
        g.append("path").attr("class", "leader").attr("d", `M${px + (j === 0 ? 3 : -3)},${py + 2}L${tx},${ty}`);
        g.append("text").attr("class", j === 0 ? "lab-strong" : "lab").attr("x", tx + (j === 0 ? 5 : -5)).attr("y", ty + 4)
          .attr("text-anchor", j === 0 ? "start" : "end").text(`${B.dateText(iso)}: ${B.fmt(n)} laws`);
      });
    };
    L.legend = "family";
    return L;
  }

  /* ---------------- steps ---------------- */
  const STEPS = [
    {layout: () => layoutYears("hero"), mode: () => ({kind: "family"}), desc: "Every Republic Act from 1946 to 2026 as a dot, stacked by year."},
    {layout: () => layoutYears("main"), mode: () => ({kind: "family"}), desc: "Laws per year, with a gap from 1972 to 1987 when there was no Congress."},
    {layout: layoutFamilies, mode: () => ({kind: "focus", fams: new Set([6])}), desc: "The laws grouped by kind; national laws are highlighted."},
    {layout: layoutFamilies, mode: () => ({kind: "focus", fams: new Set([5])}), desc: "Franchises and other private laws are highlighted."},
    {layout: layoutFamilies, mode: () => ({kind: "focus", fams: new Set([0, 1, 2, 3, 4])}), desc: "The five families of local laws are highlighted."},
    {layout: layoutMap, mode: () => ({kind: "mono"}), desc: "Local laws placed on a map of the Philippines at the towns they name."},
    {layout: () => { const L = layoutMap(); return Object.assign({}, L, {overlay: L.outlines}); },
      mode: () => ({kind: "monoFocus", fam: 0}), desc: "The same map, with school and college laws highlighted."},
    {layout: layoutCongress, mode: () => ({kind: "family"}), desc: "Laws stacked by the Congress that passed them."},
    {layout: layoutDays, mode: () => ({kind: "family"}), desc: "Laws stacked by the day they were approved; a few days have hundreds."},
  ];

  function go(k, animate = true) {
    if (!law) return;
    k = Math.max(0, Math.min(STEPS.length - 1, k));
    if (k === step) return;
    captureCurrent();
    step = k;
    const st = STEPS[k];
    const L = st.layout();
    layout = L;
    for (let i = 0; i < N; i++) {
      // particles this layout does not show fade out where they are
      if (L.vis[i]) { ex[i] = L.x[i]; ey[i] = L.y[i]; } else { ex[i] = sx[i]; ey[i] = sy[i]; }
    }
    ec.set(paint(st.mode(), L.vis));
    sizeE = L.size;
    for (let i = 0; i < N; i++) delay[i] = law[i].h;
    stagger = k === 5 ? 0.45 : 0.35;
    dur = B.reduced || !animate ? 0 : (k === 5 ? 1900 : 1400);
    quad = null; hot = -1; B.hideTip();
    drawOverlay(L);
    drawLegend(st.mode(), L.legend);
    descEl.textContent = st.desc;
    start();
  }
  function currentSize() {
    const e = ease(Math.min(1, T));
    return sizeS + (sizeE - sizeS) * e;
  }
  function ease(t) { return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2; }
  function captureCurrent() {
    if (!sx) return;
    for (let i = 0; i < N; i++) {
      const tt = Math.min(1, Math.max(0, (T - delay[i] * stagger) / (1 - stagger)));
      const e = ease(tt);
      sx[i] = sx[i] + (ex[i] - sx[i]) * e;
      sy[i] = sy[i] + (ey[i] - sy[i]) * e;
      for (let c = 0; c < 4; c++) sc[i * 4 + c] = sc[i * 4 + c] + (ec[i * 4 + c] - sc[i * 4 + c]) * e;
    }
    sizeS = currentSize();
  }
  function start() {
    cancelAnimationFrame(raf);
    upload();
    t0 = performance.now();
    T = dur ? 0 : 1;
    const tick = now => {
      T = dur ? Math.min(1, (now - t0) / dur) : 1;
      draw();
      if (T < 1) raf = requestAnimationFrame(tick);
      else settle();
    };
    raf = requestAnimationFrame(tick);
  }
  function settle() {
    // the next transition starts from here
    sx.set(ex); sy.set(ey); sc.set(ec); sizeS = sizeE;
    upload();
    draw();
    const pts = [];
    for (let i = 0; i < N; i++) if (ec[i * 4 + 3] > 0.2) pts.push(i);
    quad = d3.quadtree().x(i => ex[i]).y(i => ey[i]).addAll(pts);
  }

  /* ---------------- WebGL ---------------- */
  const VS = `
    attribute vec2 a_s; attribute vec2 a_e; attribute vec4 a_cs; attribute vec4 a_ce; attribute float a_d;
    uniform vec2 u_res; uniform float u_t; uniform float u_ss; uniform float u_se; uniform float u_dpr; uniform float u_stag;
    varying vec4 v_c; varying float v_size;
    float ease(float t) { return t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0; }
    void main() {
      float t = clamp((u_t - a_d * u_stag) / (1.0 - u_stag), 0.0, 1.0);
      float e = ease(t);
      vec2 p = mix(a_s, a_e, e);
      vec2 c = p / u_res * 2.0 - 1.0;
      gl_Position = vec4(c.x, -c.y, 0.0, 1.0);
      v_size = mix(u_ss, u_se, e) * u_dpr;
      gl_PointSize = v_size;
      v_c = mix(a_cs, a_ce, e);
    }`;
  const FS = `
    precision mediump float;
    varying vec4 v_c; varying float v_size;
    void main() {
      float a = v_c.a;
      if (v_size > 3.2) {
        float d = length(gl_PointCoord - 0.5);
        a *= 1.0 - smoothstep(0.40, 0.5, d);
      }
      gl_FragColor = vec4(v_c.rgb * a, a);
    }`;
  function initGL() {
    try {
      gl = cv.getContext("webgl", {premultipliedAlpha: true, antialias: false, alpha: true});
    } catch (e) { gl = null; }
    if (!gl) { ctx2d = cv.getContext("2d"); return; }
    const sh = (type, src) => {
      const s = gl.createShader(type); gl.shaderSource(s, src); gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    prog = gl.createProgram();
    gl.attachShader(prog, sh(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, sh(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    gl.useProgram(prog);
    ["a_s", "a_e", "a_cs", "a_ce", "a_d"].forEach(n => { bufs[n] = gl.createBuffer(); });
  }
  function upload() {
    if (!gl) return;
    const put = (name, arr, size) => {
      const loc = gl.getAttribLocation(prog, name);
      gl.bindBuffer(gl.ARRAY_BUFFER, bufs[name]);
      gl.bufferData(gl.ARRAY_BUFFER, arr, gl.DYNAMIC_DRAW);
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, size, gl.FLOAT, false, 0, 0);
    };
    const s = new Float32Array(N * 2), e = new Float32Array(N * 2);
    for (let i = 0; i < N; i++) { s[i * 2] = sx[i]; s[i * 2 + 1] = sy[i]; e[i * 2] = ex[i]; e[i * 2 + 1] = ey[i]; }
    put("a_s", s, 2); put("a_e", e, 2); put("a_cs", sc, 4); put("a_ce", ec, 4); put("a_d", delay, 1);
  }
  function draw() {
    if (gl) {
      gl.viewport(0, 0, cv.width, cv.height);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT);
      gl.enable(gl.BLEND);
      if (colors.dark) gl.blendFunc(gl.ONE, gl.ONE); else gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      const u = n => gl.getUniformLocation(prog, n);
      gl.uniform2f(u("u_res"), W, H);
      gl.uniform1f(u("u_t"), T);
      gl.uniform1f(u("u_ss"), sizeS);
      gl.uniform1f(u("u_se"), sizeE);
      gl.uniform1f(u("u_dpr"), dpr);
      gl.uniform1f(u("u_stag"), stagger);
      gl.drawArrays(gl.POINTS, 0, N);
    } else if (ctx2d) {
      // fallback: the end state of each step, batched by colour
      ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx2d.clearRect(0, 0, W, H);
      const groups = new Map();
      for (let i = 0; i < N; i++) {
        const a = ec[i * 4 + 3];
        if (a <= 0) continue;
        const k = `${Math.round(ec[i * 4] * 255)},${Math.round(ec[i * 4 + 1] * 255)},${Math.round(ec[i * 4 + 2] * 255)},${a.toFixed(2)}`;
        if (!groups.has(k)) groups.set(k, []);
        groups.get(k).push(i);
      }
      const s = sizeE;
      for (const [k, list] of groups) {
        ctx2d.fillStyle = `rgba(${k})`;
        ctx2d.beginPath();
        for (const i of list) ctx2d.rect(ex[i] - s / 2, ey[i] - s / 2, s, s);
        ctx2d.fill();
      }
    }
  }

  /* ---------------- overlay and legend ---------------- */
  function drawOverlay(L) {
    const s = d3.select(svg);
    s.selectAll("g.layer").transition().duration(B.reduced ? 0 : 300).style("opacity", 0).remove();
    const g = s.append("g").attr("class", "layer").style("opacity", 0);
    if (L.overlay) L.overlay(g);
    g.transition().delay(B.reduced ? 0 : Math.min(900, dur * 0.6)).duration(B.reduced ? 0 : 500).style("opacity", 1);
  }
  function drawLegend(mode, kind) {
    legendEl.replaceChildren();
    if (kind === "none") { legendEl.style.opacity = 0; return; }
    legendEl.style.opacity = 1;
    if (kind === "mono") {
      const glow = B.tok("--glow");
      const sp = B.el("span", {}, B.el("i", {style: `background:${glow};box-shadow:0 0 8px ${glow}`}), document.createTextNode("One local law"));
      legendEl.append(sp);
      if (mode.kind === "monoFocus") {
        const c = B.famColors()[mode.fam];
        legendEl.append(B.el("span", {}, B.el("i", {style: `background:${c}`}), document.createTextNode(D.laws.families[mode.fam].label)));
      }
      return;
    }
    // on a phone the hero headline fills the top of the screen, so its legend waits for step 1
    if (mobile() && step === 0) { legendEl.style.opacity = 0; }
    const cols = B.famColors();
    D.laws.families.forEach((fm, i) => {
      const on = mode.kind !== "focus" || mode.fams.has(i);
      const sp = B.el("span", {style: `opacity:${on ? 1 : 0.35}`}, B.el("i", {style: `background:${cols[i]}`}),
        document.createTextNode(mobile() ? B.SHORT_FAM[i] : fm.label));
      legendEl.append(sp);
    });
  }

  /* ---------------- hover ---------------- */
  function onMove(e) {
    if (!quad || T < 1) return;
    const b = cv.getBoundingClientRect();
    const mx = e.clientX - b.left, my = e.clientY - b.top;
    const i = quad.find(mx, my, 9);
    if (i == null) { if (hot !== -1) { hot = -1; B.hideTip(); cv.style.cursor = "default"; } return; }
    hot = i;
    cv.style.cursor = "pointer";
    const l = law[i];
    const cat = D.laws.categories[l.cat];
    const place = l.towns.length ? B.townName(D.laws.towns[l.towns[0]][1]) + ", " + D.laws.towns[l.towns[0]][2]
      : (l.provs.length ? D.laws.provinces[l.provs[0]] : "");
    B.showTip(e, [
      {cls: "tv", text: `Republic Act No. ${l.ra}`},
      {cls: "tm", text: `${B.dateText(l.iso)}${l.cong ? " · " + B.ord(l.cong) + " Congress" : ""}`},
      {cls: "tt", text: B.shorten(l.title, 180)},
      {key: B.famColors()[l.fam], text: cat.label + (place && LOCAL(l.fam) ? ` · ${place}` : "")},
    ]);
  }

  /* ---------------- setup ---------------- */
  function size() {
    const r = stage.getBoundingClientRect();
    W = Math.round(r.width); H = Math.round(r.height);
    dpr = Math.min(2, window.devicePixelRatio || 1);
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    mapCache = null;
  }
  function resize() {
    const r = stage.getBoundingClientRect();
    if (Math.round(r.width) === W && Math.abs(Math.round(r.height) - H) < 120) return;
    size();
    if (step < 0) return;
    cancelAnimationFrame(raf);
    // jump to the new geometry without animating; hidden particles wait on the timeline
    const st = STEPS[step];
    const L = st.layout();
    const park = layoutYears("main");
    layout = L;
    for (let i = 0; i < N; i++) {
      const x = L.vis[i] ? L.x[i] : park.x[i], y = L.vis[i] ? L.y[i] : park.y[i];
      sx[i] = ex[i] = x; sy[i] = ey[i] = y;
    }
    const col = paint(st.mode(), L.vis);
    sc.set(col); ec.set(col);
    sizeS = sizeE = L.size; T = 1; dur = 0;
    d3.select(svg).selectAll("g.layer").remove();
    drawOverlay(L);
    upload(); settle();
  }
  function retheme() {
    if (!law) return;
    readColors();
    if (step < 0) return;
    const st = STEPS[step];
    const col = paint(st.mode(), layout.vis);
    ec.set(col); sc.set(col);
    upload(); draw();
    drawLegend(st.mode(), layout.legend);
  }

  S.init = function (data) {
    D = data;
    stage = B.$("#stage"); cv = B.$("#stagecanvas"); svg = B.$("#stagesvg");
    legendEl = B.$("#stagelegend"); descEl = B.$("#stagedesc");
    prep();
    size();
    readColors();
    try { initGL(); } catch (e) { console.error(e); gl = null; ctx2d = cv.getContext("2d"); }
    sx = new Float32Array(N); sy = new Float32Array(N); ex = new Float32Array(N); ey = new Float32Array(N);
    sc = new Float32Array(N * 4); ec = new Float32Array(N * 4); delay = new Float32Array(N);
    // start as falling rain above the skyline
    for (let i = 0; i < N; i++) {
      sx[i] = B.hash(i * 3.7) * W; sy[i] = -20 - B.hash(i * 1.3) * H * 0.9;
      ex[i] = sx[i]; ey[i] = sy[i];
    }
    step = -1;
    const first = layoutYears("hero");
    for (let i = 0; i < N; i++) if (first.vis[i]) { ex[i] = first.x[i]; ey[i] = first.y[i]; }
    // colours start transparent and fade in
    const col = paint({kind: "family"}, first.vis);
    for (let i = 0; i < N; i++) { sc[i * 4] = col[i * 4]; sc[i * 4 + 1] = col[i * 4 + 1]; sc[i * 4 + 2] = col[i * 4 + 2]; sc[i * 4 + 3] = 0; }
    // observe steps
    const stepsEls = B.$$(".step");
    const io = new IntersectionObserver(entries => {
      entries.forEach(en => { if (en.isIntersecting) go(+en.target.dataset.step); });
    }, {rootMargin: "-48% 0px -48% 0px"});
    stepsEls.forEach(el => io.observe(el));
    // entrance
    step = 0;
    layout = first;
    ec.set(col);
    sizeS = first.size; sizeE = first.size;
    for (let i = 0; i < N; i++) delay[i] = law[i].h;
    stagger = 0.6; dur = B.reduced ? 0 : 2400;
    drawOverlay(first);
    drawLegend({kind: "family"}, "family");
    descEl.textContent = STEPS[0].desc;
    start();
    // if the page loads scrolled down, jump to the right step
    const mid = window.innerHeight / 2;
    stepsEls.forEach(el => { const r = el.getBoundingClientRect(); if (r.top <= mid && r.bottom >= mid && +el.dataset.step !== 0) go(+el.dataset.step, false); });
    cv.addEventListener("pointermove", onMove);
    cv.addEventListener("pointerleave", () => { hot = -1; B.hideTip(); });
    cv.addEventListener("click", () => { if (hot >= 0) window.open(B.lawUrl(D.laws.rows[hot]), "_blank", "noopener"); });
    B.onResize(resize);
    B.onTheme(retheme);
  };
})();
