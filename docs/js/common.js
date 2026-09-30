/* Batas: shared helpers. Every number on the page comes from docs/data/*.json,
   which pipeline/make_site_data.py writes. */
(function () {
  "use strict";
  const B = (window.B = {});

  B.$ = (s, r = document) => r.querySelector(s);
  B.$$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  B.fmt = d3.format(",");
  B.pct = d3.format(".0%");
  B.pct1 = d3.format(".1%");
  B.dec = d3.format(".2f");
  B.MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December"];
  B.CONG_YEARS = {1: "1946-49", 2: "1950-53", 3: "1954-57", 4: "1958-61", 5: "1962-65", 6: "1966-69",
    7: "1970-72", 8: "1987-92", 9: "1992-95", 10: "1995-98", 11: "1998-01", 12: "2001-04", 13: "2004-07",
    14: "2007-10", 15: "2010-13", 16: "2013-16", 17: "2016-19", 18: "2019-22", 19: "2022-25", 20: "2025-"};
  B.ord = n => n + ({1: "st", 2: "nd", 3: "rd"}[n] || "th");
  B.SHORT_FAM = ["Schools", "Hospitals", "Towns", "Roads", "Offices", "Private", "National"];
  B.fold = s => (s || "").normalize("NFKD").replace(/[̀-ͯ]/g, "").toLowerCase()
    .replace(/[^a-z0-9 ]+/g, " ").replace(/\s+/g, " ").trim();
  B.dateText = iso => {
    if (!iso) return "date unknown";
    const [y, m, d] = iso.split("-").map(Number);
    return `${B.MONTHS[m - 1]} ${d}, ${y}`;
  };
  // "City of Davao" -> "Davao City"; "City of Manila" -> "Manila"
  B.townName = n => {
    let s = (n || "").trim().replace(/^City of (.+)$/, "$1 City").replace(/ De /g, " de ").replace(/ Del /g, " del ");
    if (s === "Manila City") s = "Manila";
    return s;
  };
  B.reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* ---------- tokens ---------- */
  B.tok = (name, el) => getComputedStyle(el || document.documentElement).getPropertyValue(name).trim();
  B.famColors = el => d3.range(7).map(i => B.tok("--f" + i, el));
  B.isDark = () => B.tok("color-scheme") !== "light";
  B.rgb = hex => { const c = d3.color(hex) || d3.color("#888"); return [c.r / 255, c.g / 255, c.b / 255]; };

  /* ---------- theme ---------- */
  const btn = B.$("#themebtn");
  const listeners = [];
  B.onTheme = f => listeners.push(f);
  function setTheme(mode, save) {
    if (mode === "auto") delete document.documentElement.dataset.theme;
    else document.documentElement.dataset.theme = mode;
    btn.querySelector(".themelabel").textContent = mode[0].toUpperCase() + mode.slice(1);
    btn.setAttribute("aria-label", `Colour theme: ${mode}. Select to change.`);
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = B.tok("--bg");
    if (save) { try { localStorage.setItem("batas-theme", mode); } catch (e) { /* storage may be blocked */ } }
    listeners.forEach(f => { try { f(); } catch (e) { console.error(e); } });
  }
  btn.addEventListener("click", () => {
    const cur = document.documentElement.dataset.theme || "auto";
    setTheme({auto: "light", light: "dark", dark: "auto"}[cur], true);
  });
  try {
    const saved = localStorage.getItem("batas-theme");
    if (saved === "light" || saved === "dark") setTheme(saved, false);
  } catch (e) { /* ignore */ }
  const meta0 = document.querySelector('meta[name="theme-color"]');
  if (meta0) meta0.content = B.tok("--bg");
  window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => setTheme(document.documentElement.dataset.theme || "auto", false));

  /* ---------- resize ---------- */
  const resizers = [];
  B.onResize = f => resizers.push(f);
  let lastW = window.innerWidth, lastH = window.innerHeight, rt = null;
  window.addEventListener("resize", () => {
    clearTimeout(rt);
    rt = setTimeout(() => {
      const w = window.innerWidth, h = window.innerHeight;
      // mobile browsers resize the viewport when the address bar hides; ignore small height changes
      if (Math.abs(w - lastW) < 2 && Math.abs(h - lastH) < 120) return;
      lastW = w; lastH = h;
      resizers.forEach(f => { try { f(); } catch (e) { console.error(e); } });
    }, 120);
  });

  /* ---------- nav ---------- */
  const nav = B.$(".topnav");
  const onScroll = () => nav.classList.toggle("scrolled", window.scrollY > window.innerHeight * 0.9);
  window.addEventListener("scroll", onScroll, {passive: true});
  onScroll();

  /* ---------- tooltip ---------- */
  const tip = B.$("#tooltip");
  B.showTip = function (evt, parts) {
    tip.replaceChildren();
    for (const p of parts) {
      const div = document.createElement("div");
      if (p.cls) div.className = p.cls;
      if (p.key) {
        const k = document.createElement("span");
        k.className = "key"; k.style.background = p.key;
        div.appendChild(k);
      }
      div.appendChild(document.createTextNode(p.text));
      tip.appendChild(div);
    }
    tip.style.display = "block";
    const pad = 16, w = tip.offsetWidth, h = tip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > window.innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > window.innerHeight - 8) y = evt.clientY - h - pad;
    tip.style.left = Math.max(8, x) + "px";
    tip.style.top = Math.max(8, y) + "px";
  };
  B.hideTip = () => { tip.style.display = "none"; };

  /* ---------- small DOM helpers ---------- */
  B.el = (tag, attrs = {}, ...kids) => {
    const e = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") e.className = v;
      else if (k === "style") e.style.cssText = v;
      else if (k === "text") e.textContent = v;
      else e.setAttribute(k, v);
    }
    kids.forEach(k => e.append(k));
    return e;
  };
  B.svgIn = (el, w, h) => {
    el.replaceChildren();
    return d3.select(el).append("svg").attr("viewBox", `0 0 ${w} ${h}`).attr("width", w).attr("height", h)
      .style("width", "100%").style("height", "auto");
  };
  B.canvasIn = (el, w, h) => {
    el.replaceChildren();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    const cv = document.createElement("canvas");
    cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr);
    cv.style.height = h + "px";
    el.appendChild(cv);
    const ctx = cv.getContext("2d");
    ctx.scale(dpr, dpr);
    return {cv, ctx, dpr};
  };
  B.table = (el, head, rows) => {
    const t = document.createElement("table");
    t.className = "datatable";
    const thead = t.createTHead().insertRow();
    head.forEach(h => { const th = document.createElement("th"); th.textContent = h; thead.appendChild(th); });
    const tb = t.createTBody();
    rows.forEach(r => {
      const tr = tb.insertRow();
      r.forEach((v, i) => {
        const td = tr.insertCell();
        if (v && typeof v === "object" && v.href) {
          const a = document.createElement("a"); a.href = v.href; a.textContent = v.text; a.target = "_blank"; a.rel = "noopener";
          td.appendChild(a);
        } else td.textContent = typeof v === "number" ? B.fmt(v) : (v == null ? "" : v);
        if (i > 0 && typeof v !== "number") td.className = "l";
      });
    });
    el.replaceChildren(t);
  };
  B.roundedTop = (x, y, w, h, r) => {
    r = Math.min(r, w / 2, h);
    if (h <= 0) return "";
    return `M${x},${y + h}V${y + r}Q${x},${y} ${x + r},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h}Z`;
  };
  B.roundedRight = (x, y, w, h, r) => {
    r = Math.min(r, h / 2, w);
    if (w <= 0) return "";
    return `M${x},${y}H${x + w - r}Q${x + w},${y} ${x + w},${y + r}V${y + h - r}Q${x + w},${y + h} ${x + w - r},${y + h}H${x}Z`;
  };
  B.lawUrl = row => {
    const ra = row[0], link = row[9];
    if (typeof link === "number") return `https://lawphil.net/statutes/repacts/ra${link}/ra_${ra}_${link}.html`;
    return link || "https://lawphil.net/statutes/repacts/repacts.html";
  };
  B.shorten = (s, n) => (s.length > n ? s.slice(0, n - 1).replace(/\s+\S*$/, "") + "..." : s);
  // deterministic pseudo-random numbers from an integer seed
  B.hash = n => { const x = Math.sin(n * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x); };
  B.bind = (key, text) => B.$$(`[data-bind="${key}"]`).forEach(e => { e.textContent = text; });
  // run a function once an element is near the viewport
  B.whenVisible = (el, f, margin = "200px") => {
    if (!("IntersectionObserver" in window)) { f(); return; }
    const io = new IntersectionObserver(es => { if (es.some(e => e.isIntersecting)) { io.disconnect(); f(); } }, {rootMargin: margin});
    io.observe(el);
  };
})();
