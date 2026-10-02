/* The explorer: every local law at the town it names, a per-person view by
   province, and a town search. */
(function () {
  "use strict";
  const B = window.B;
  const X = (B.explore = {});
  const GOLDEN = Math.PI * (3 - Math.sqrt(5));
  const ERA_POP = {all: [1960, 1970, 1980, 1990, 2000, 2010, 2020], pre: [1960, 1970], post: [1990, 2000, 2010, 2020]};

  let D, rows, towns, geo, provIdx;
  let view = "dots", fam = "all", era = "all", selTown = null, selProv = null;
  let W = 0, H = 0, proj, path, svgSel, cv, ctx, dpr = 1;
  let townLaws, drawn, centers, quad, lawsByProv;

  const isLocal = r => r[3] <= 4;
  const inEra = r => era === "all" || (era === "pre" ? r[2] >= 1 && r[2] <= 7 : r[2] >= 8);
  const inFam = r => fam === "all" || r[3] === +fam;
  const keep = r => isLocal(r) && inEra(r) && inFam(r);

  function prep() {
    rows = D.laws.rows; towns = D.laws.towns;
    geo = topojson.feature(D.topo, D.topo.objects[Object.keys(D.topo.objects)[0]]);
    provIdx = new Map(D.laws.provinces.map((p, i) => [p, i]));
    // every law that names a town, listed under each town it names
    townLaws = new Map();
    lawsByProv = new Map();
    rows.forEach((r, k) => {
      if (!isLocal(r)) return;
      r[8].forEach(t => { if (!townLaws.has(t)) townLaws.set(t, []); townLaws.get(t).push(k); });
      r[7].forEach(p => { if (!lawsByProv.has(p)) lawsByProv.set(p, []); lawsByProv.get(p).push(k); });
    });
  }

  /* ---------- geometry ---------- */
  function layout() {
    const box = B.$("#mapbox");
    W = Math.round(box.clientWidth || 700);
    H = Math.round(Math.min(W * 1.32, Math.max(560, window.innerHeight * 0.86), 900));
    box.style.height = H + "px";
    proj = d3.geoMercator().fitExtent([[10, 10], [W - 10, H - 10]], geo);
    path = d3.geoPath(proj);
    dpr = Math.min(2, window.devicePixelRatio || 1);
    cv = B.$("#mapcanvas");
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr);
    ctx = cv.getContext("2d");
    const svg = B.$("#mapsvg");
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svgSel = d3.select(svg);
    svgSel.selectAll("*").remove();
    svgSel.append("rect").attr("width", W).attr("height", H).attr("fill", "transparent");
    svgSel.append("g").attr("class", "provs").selectAll("path").data(geo.features).join("path")
      .attr("d", path).attr("stroke-width", 0.6).attr("vector-effect", "non-scaling-stroke");
    svgSel.append("g").attr("class", "sel");
    svgSel.on("pointermove", onMove).on("pointerleave", () => { B.hideTip(); }).on("click", onClick);
  }

  /* ---------- dots ---------- */
  function computeDots() {
    const size = W < 520 ? 1.5 : 1.9, c = size * 0.66;
    const seen = new Map();
    drawn = [];
    const order = rows.map((r, k) => k).filter(k => keep(rows[k])).sort((a, b) => (rows[a][1] || "").localeCompare(rows[b][1] || "") || a - b);
    for (const k of order) {
      const r = rows[k];
      const tl = r[8].filter(t => towns[t][3] != null);
      const h = B.hash(r[0]);
      if (tl.length) {
        const t = tl[Math.floor(h * tl.length) % tl.length];
        const p = proj([towns[t][3], towns[t][4]]);
        const n = seen.get(t) || 0;
        seen.set(t, n + 1);
        const rr = c * Math.sqrt(n + 0.5), a = n * GOLDEN;
        drawn.push([p[0] + rr * Math.cos(a), p[1] + rr * Math.sin(a), r[3], k]);
      } else if (r[7].length) {
        const f = geo.features.find(g => g.properties.province === D.laws.provinces[r[7][Math.floor(h * r[7].length) % r[7].length]]);
        if (!f) continue;
        const [[x0, y0], [x1, y1]] = path.bounds(f);
        let pt = null;
        for (let j = 0; j < 60 && !pt; j++) {
          const px = x0 + B.hash(r[0] * 31 + j * 7.1) * (x1 - x0), py = y0 + B.hash(r[0] * 17 + j * 3.3) * (y1 - y0);
          if (d3.geoContains(f, proj.invert([px, py]))) pt = [px, py];
        }
        pt = pt || proj(d3.geoCentroid(f));
        drawn.push([pt[0], pt[1], r[3], k]);
      }
    }
    // town centres for hover, sized by the number of dots drawn there
    centers = Array.from(seen.entries()).map(([t, n]) => {
      const p = proj([towns[t][3], towns[t][4]]);
      return {t, n, x: p[0], y: p[1], r: c * Math.sqrt(n) + 2};
    });
    quad = d3.quadtree().x(d => d.x).y(d => d.y).addAll(centers);
    return size;
  }
  function drawDots() {
    const size = computeDots();
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    if (view !== "dots") return;
    const dark = B.isDark();
    const cols = B.famColors(), glow = B.tok("--glow");
    ctx.globalCompositeOperation = dark ? "lighter" : "source-over";
    const byCol = new Map();
    for (const d of drawn) {
      const c = fam === "all" ? glow : cols[d[2]];
      if (!byCol.has(c)) byCol.set(c, []);
      byCol.get(c).push(d);
    }
    for (const [c, list] of byCol) {
      ctx.fillStyle = c;
      ctx.globalAlpha = dark ? 0.72 : 0.7;
      ctx.beginPath();
      for (const d of list) ctx.rect(d[0] - size / 2, d[1] - size / 2, size, size);
      ctx.fill();
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
    if (selTown != null) {
      const c = centers.find(c => c.t === selTown);
      if (c) {
        ctx.strokeStyle = B.tok("--accent"); ctx.lineWidth = 1.6;
        ctx.beginPath(); ctx.arc(c.x, c.y, c.r + 5, 0, Math.PI * 2); ctx.stroke();
      }
    }
  }

  /* ---------- per-person view ---------- */
  function provValues() {
    const out = {};
    D.provinces.provinces.forEach(p => {
      let n = 0;
      for (const [k, v] of Object.entries(p.counts)) {
        const [c, f] = k.split("|").map(Number);
        if (fam !== "all" && f !== +fam) continue;
        if (era === "pre" && !(c >= 1 && c <= 7)) continue;
        if (era === "post" && !(c >= 8)) continue;
        n += v;
      }
      const pops = ERA_POP[era].map(y => p.pop[y]).filter(v => v > 0);
      const pop = pops.length ? d3.mean(pops) : null;
      out[p.name] = {n, pop, rate: pop ? n / pop * 1e5 : null};
    });
    return out;
  }
  let scale = null, vals = null;
  function paintProvinces() {
    vals = provValues();
    const steps = [2, 3, 4, 5, 6, 7].map(i => B.tok("--seq" + i));
    const arr = Object.values(vals).map(v => v.rate).filter(v => v != null && v > 0).sort(d3.ascending);
    scale = d3.scaleQuantile().domain(arr).range(steps);
    svgSel.select("g.provs").selectAll("path")
      .attr("fill", d => {
        if (view !== "rate") return "transparent";
        const v = vals[d.properties.province];
        return v && v.rate > 0 ? scale(v.rate) : B.tok("--nodata");
      })
      .attr("stroke", view === "rate" ? B.tok("--card") : B.tok("--line-2"))
      .style("cursor", "pointer");
    const sel = svgSel.select("g.sel");
    sel.selectAll("*").remove();
    if (selProv) {
      const f = geo.features.find(g => g.properties.province === selProv);
      if (f) sel.append("path").attr("d", path(f)).attr("fill", "none").attr("stroke", B.tok("--ink")).attr("stroke-width", 1.6).attr("pointer-events", "none");
    }
    legend(steps);
  }
  function legend(steps) {
    const lg = B.$("#maplegend"); lg.replaceChildren();
    const note = B.$("#mapnote");
    if (view === "dots") {
      const c = fam === "all" ? B.tok("--glow") : B.famColors()[+fam];
      lg.append(B.el("span", {}, B.el("span", {class: "dot", style: `background:${c};width:7px;height:7px`}), document.createTextNode("One local law, at the town it names")));
      const n = rows.filter(keep).length;
      note.textContent = `${B.fmt(drawn.length)} of ${B.fmt(n)} local laws are on the map. We couldn't match a place for the rest. Laws that name only a province are placed at a random point inside it.`;
      return;
    }
    const qs = scale.quantiles();
    const dom = scale.domain();
    const edges = [dom[0], ...qs, dom[dom.length - 1]];
    const f = v => v < 10 ? v.toFixed(1) : Math.round(v);
    steps.forEach((c, i) => lg.append(B.el("span", {}, B.el("span", {class: "sw", style: `background:${c}`}), document.createTextNode(`${f(edges[i])} to ${f(edges[i + 1])}`))));
    note.textContent = "Local laws per 100,000 people, using the average census population over the period. Batanes and other small provinces rank high mainly because they have so few people.";
  }

  /* ---------- hover and select ---------- */
  function nearTown(mx, my) {
    if (view !== "dots" || !quad) return null;
    let best = null, bd = Infinity;
    quad.visit((node, x0, y0, x1, y1) => {
      if (!node.length) {
        let d = node;
        do {
          const c = d.data, dist = Math.hypot(c.x - mx, c.y - my);
          if (dist < c.r + 4 && dist < bd) { bd = dist; best = c; }
        } while ((d = d.next));
      }
      return x0 > mx + 30 || x1 < mx - 30 || y0 > my + 30 || y1 < my - 30;
    });
    return best;
  }
  function pointer(e) {
    const b = B.$("#mapsvg").getBoundingClientRect();
    return [(e.clientX - b.left) * (W / b.width), (e.clientY - b.top) * (H / b.height)];
  }
  function provAt(e) {
    const t = e.target;
    return t && t.__data__ && t.__data__.properties ? t.__data__.properties.province : null;
  }
  function onMove(e) {
    const [mx, my] = pointer(e);
    const c = nearTown(mx, my);
    if (c) {
      const ks = (townLaws.get(c.t) || []).filter(k => keep(rows[k]));
      const kinds = d3.rollups(ks, v => v.length, k => rows[k][4]).sort((a, b) => b[1] - a[1]).slice(0, 3);
      B.showTip(e, [
        {cls: "tv", text: `${B.townName(towns[c.t][1])}, ${towns[c.t][2]}`},
        {text: `${B.fmt(ks.length)} local law${ks.length === 1 ? " names" : "s name"} this town`},
        ...kinds.map(([cat, n]) => ({key: B.famColors()[D.laws.categories[cat].family], text: `${D.laws.categories[cat].label}: ${n}`})),
        {cls: "tm", text: "Select to list them"},
      ]);
      B.$("#mapsvg").style.cursor = "pointer";
      return;
    }
    const p = provAt(e);
    if (!p) { B.hideTip(); return; }
    const v = (vals || provValues())[p] || {};
    B.showTip(e, [
      {cls: "tv", text: p},
      {text: `${B.fmt(Math.round(v.n || 0))} local laws${v.rate != null ? ` · ${B.dec(v.rate)} per 100,000 people` : ""}`},
      {cls: "tm", text: "Select to see its laws"},
    ]);
  }
  function onClick(e) {
    const [mx, my] = pointer(e);
    const c = nearTown(mx, my);
    if (c) { pickTown(c.t); return; }
    const p = provAt(e);
    if (p) pickProv(p);
  }

  /* ---------- panel ---------- */
  function lawItem(k) {
    const r = rows[k];
    const li = B.el("li");
    const meta = B.el("span", {class: "meta"}, B.el("i", {style: `background:${B.famColors()[r[3]]}`}),
      document.createTextNode(`RA ${r[0]} · ${B.dateText(r[1])}`));
    const a = B.el("a", {href: B.lawUrl(r), target: "_blank", rel: "noopener", text: r[5]});
    li.append(meta, a);
    return li;
  }
  function kindBars(ks) {
    const box = B.el("div", {class: "bars"});
    const kinds = d3.rollups(ks, v => v.length, k => rows[k][4]).sort((a, b) => b[1] - a[1]).slice(0, 6);
    const max = kinds.length ? kinds[0][1] : 1;
    kinds.forEach(([cat, n]) => {
      const c = B.famColors()[D.laws.categories[cat].family];
      box.append(B.el("div", {class: "b"}, B.el("span", {text: D.laws.categories[cat].label}), B.el("span", {class: "v", text: B.fmt(n)}),
        B.el("div", {class: "track"}, B.el("div", {class: "fill", style: `width:${(n / max) * 100}%;background:${c}`}))));
    });
    return box;
  }
  function pickTown(t) {
    selTown = t; selProv = null;
    drawDots(); paintProvinces();
    const ks = (townLaws.get(t) || []).filter(k => keep(rows[k])).sort((a, b) => rows[b][0] - rows[a][0]);
    const all = (townLaws.get(t) || []).length;
    const panel = B.$("#placepanel"); panel.replaceChildren(backButton());
    panel.append(B.el("p", {class: "eyebrow small", text: towns[t][2]}), B.el("h3", {text: B.townName(towns[t][1])}),
      B.el("p", {class: "bignum", text: B.fmt(ks.length)}),
      B.el("p", {class: "muted", text: `local law${ks.length === 1 ? " names" : "s name"} this town` + (ks.length !== all ? ` (${B.fmt(all)} of every kind and period)` : "")}),
      kindBars(ks));
    const ul = B.el("ul", {class: "lawlist"});
    ks.forEach(k => ul.append(lawItem(k)));
    panel.append(ul);
    B.$("#townsearch").value = B.townName(towns[t][1]);
  }
  function pickProv(p) {
    selProv = p; selTown = null;
    drawDots(); paintProvinces();
    const pi = provIdx.get(p);
    const ks = (lawsByProv.get(pi) || []).filter(k => keep(rows[k])).sort((a, b) => rows[b][0] - rows[a][0]);
    const v = (vals || provValues())[p] || {};
    const panel = B.$("#placepanel"); panel.replaceChildren(backButton());
    panel.append(B.el("p", {class: "eyebrow small", text: "Province"}), B.el("h3", {text: p}),
      B.el("p", {class: "bignum", text: B.fmt(ks.length)}),
      B.el("p", {class: "muted", text: `local laws${v.rate != null ? `, ${B.dec(v.rate)} per 100,000 people` : ""}`}),
      kindBars(ks));
    const tcount = d3.rollups(ks.flatMap(k => rows[k][8]).filter(t => towns[t][2] === p), v => v.length, t => t)
      .sort((a, b) => b[1] - a[1]).slice(0, 6);
    if (tcount.length) {
      const r = B.el("div", {class: "rank"}, B.el("h4", {text: "Most named towns"}));
      tcount.forEach(([t, n], i) => {
        const row = B.el("div", {class: "row", tabindex: "0"}, B.el("span", {class: "i", text: String(i + 1)}),
          B.el("span", {class: "nm", text: B.townName(towns[t][1])}), B.el("span", {class: "v", text: B.fmt(n)}));
        row.addEventListener("click", () => pickTown(t));
        row.addEventListener("keydown", e => { if (e.key === "Enter") pickTown(t); });
        r.append(row);
      });
      panel.append(r);
    }
    panel.append(B.el("p", {class: "eyebrow small", style: "margin-top:16px", text: "Latest laws"}));
    const ul = B.el("ul", {class: "lawlist"});
    ks.slice(0, 60).forEach(k => ul.append(lawItem(k)));
    panel.append(ul);
  }
  function backButton() {
    const b = B.el("button", {type: "button", class: "ghostbtn", style: "margin-bottom:14px", text: "\u2190 All towns"});
    b.addEventListener("click", () => { selTown = null; selProv = null; B.$("#townsearch").value = ""; drawDots(); paintProvinces(); defaultPanel(); });
    return b;
  }
  function defaultPanel() {
    const panel = B.$("#placepanel");
    if (selTown != null) return pickTown(selTown);
    if (selProv) return pickProv(selProv);
    panel.replaceChildren(
      B.el("p", {class: "eyebrow small", text: "Select a town or a province"}),
      B.el("h3", {text: view === "dots" ? "Towns" : "Per person"}),
      B.el("p", {class: "muted", text: view === "dots"
        ? "Hover over or tap a town to see its laws, and click it to list them. The largest clusters are mostly provincial and regional centres."
        : "Provinces are shaded by local laws per 100,000 people. Click one to see its laws."}),
      B.el("div", {id: "rankings"}));
    const box = B.$("#rankings");
    if (view === "dots") {
      const counts = Array.from(townLaws.entries()).map(([t, ks]) => [t, ks.filter(k => keep(rows[k])).length])
        .filter(d => d[1] > 0).sort((a, b) => b[1] - a[1]).slice(0, 12);
      const r = B.el("div", {class: "rank"}, B.el("h4", {text: "Most named towns"}));
      counts.forEach(([t, n], i) => {
        const row = B.el("div", {class: "row", tabindex: "0"}, B.el("span", {class: "i", text: String(i + 1)}),
          B.el("span", {class: "nm", text: `${B.townName(towns[t][1])}, ${towns[t][2]}`}), B.el("span", {class: "v", text: B.fmt(n)}));
        row.addEventListener("click", () => pickTown(t));
        row.addEventListener("keydown", e => { if (e.key === "Enter") pickTown(t); });
        r.append(row);
      });
      box.append(r);
    } else {
      const v = vals || provValues();
      const ranked = Object.entries(v).filter(([, x]) => x.rate != null).sort((a, b) => b[1].rate - a[1].rate);
      const mk = (title, list, idx) => {
        const r = B.el("div", {class: "rank"}, B.el("h4", {text: title}));
        list.forEach(([name, x], i) => {
          const row = B.el("div", {class: "row", tabindex: "0"}, B.el("span", {class: "i", text: String(idx(i))}),
            B.el("span", {class: "nm", text: name}), B.el("span", {class: "v", text: B.dec(x.rate)}));
          row.addEventListener("click", () => pickProv(name));
          row.addEventListener("keydown", e => { if (e.key === "Enter") pickProv(name); });
          r.append(row);
        });
        return r;
      };
      box.append(mk("Most per person", ranked.slice(0, 8), i => i + 1), mk("Fewest per person", ranked.slice(-8).reverse(), i => ranked.length - i));
    }
  }
  function table() {
    const v = provValues();
    const ranked = Object.entries(v).sort((a, b) => (b[1].rate || 0) - (a[1].rate || 0));
    B.table(B.$("#maptable"), ["Province", "Local laws", "Population (average)", "Per 100,000 people"],
      ranked.map(([n, x]) => [n, Math.round(x.n), x.pop ? Math.round(x.pop) : "", x.rate == null ? "" : B.dec(x.rate)]));
  }

  /* ---------- controls ---------- */
  function chips() {
    const box = B.$("#famchips"); box.replaceChildren();
    const opts = [["all", "All local laws", B.tok("--glow")], ...D.laws.families.slice(0, 5).map((f, i) => [String(i), f.label, B.famColors()[i]])];
    opts.forEach(([k, lab, c]) => {
      const b = B.el("button", {type: "button", "aria-pressed": String(fam === k)}, B.el("i", {style: `background:${c}`}), document.createTextNode(lab));
      b.addEventListener("click", () => { fam = k; chips(); redraw(); });
      box.append(b);
    });
    const eras = [["all", "1946 to 2026"], ["pre", "Before 1972"], ["post", "Since 1987"]];
    const sel = B.el("div", {class: "seg", role: "group", "aria-label": "Period", style: "margin:0 0 0 auto"});
    eras.forEach(([k, lab]) => {
      const b = B.el("button", {type: "button", "aria-pressed": String(era === k), text: lab});
      b.addEventListener("click", () => { era = k; chips(); redraw(); });
      sel.append(b);
    });
    box.append(sel);
  }
  function redraw() {
    drawDots(); paintProvinces(); defaultPanel(); table();
  }
  function search() {
    const input = B.$("#townsearch"), box = B.$("#townsuggest");
    const list = towns.map((t, i) => ({i, name: B.townName(t[1]), prov: t[2], key: B.fold(B.townName(t[1]).replace(/ City$/, "")),
      n: (townLaws.get(i) || []).length}));
    let items = [], on = -1;
    const show = l => {
      box.replaceChildren(); items = l; on = -1;
      l.forEach(t => {
        const b = B.el("button", {type: "button", role: "option"}, document.createTextNode(`${t.name}`), B.el("span", {text: `${t.prov} · ${B.fmt(t.n)}`}));
        b.addEventListener("click", () => { box.style.display = "none"; input.setAttribute("aria-expanded", "false"); pickTown(t.i); });
        box.append(b);
      });
      box.style.display = l.length ? "block" : "none";
      input.setAttribute("aria-expanded", String(!!l.length));
    };
    input.addEventListener("input", () => {
      const q = B.fold(input.value);
      if (q.length < 2) { show([]); return; }
      const starts = list.filter(t => t.key.startsWith(q)), has = list.filter(t => !t.key.startsWith(q) && t.key.includes(q));
      show([...starts.sort((a, b) => b.n - a.n), ...has.sort((a, b) => b.n - a.n)].slice(0, 12));
    });
    input.addEventListener("keydown", e => {
      const bs = box.querySelectorAll("button");
      if (e.key === "ArrowDown") { on = Math.min(bs.length - 1, on + 1); e.preventDefault(); }
      else if (e.key === "ArrowUp") { on = Math.max(0, on - 1); e.preventDefault(); }
      else if (e.key === "Enter") {
        const t = items[on >= 0 ? on : 0];
        if (t) { box.style.display = "none"; input.setAttribute("aria-expanded", "false"); pickTown(t.i); }
        e.preventDefault(); return;
      }
      else if (e.key === "Escape") { box.style.display = "none"; input.setAttribute("aria-expanded", "false"); return; }
      bs.forEach((b, i) => b.classList.toggle("on", i === on));
    });
    document.addEventListener("click", e => { if (!e.target.closest(".searchbox")) box.style.display = "none"; });
  }

  X.init = function (data) {
    D = data;
    prep();
    layout();
    chips();
    B.$$("[data-mapview]").forEach(b => b.addEventListener("click", () => {
      view = b.dataset.mapview;
      B.$$("[data-mapview]").forEach(o => o.setAttribute("aria-pressed", String(o === b)));
      redraw();
    }));
    search();
    redraw();
    B.onResize(() => { layout(); redraw(); });
    B.onTheme(() => { chips(); redraw(); });
  };
})();
