/* Boot: load the data, fill in every number the text quotes, start the story
   and the charts. */
(function () {
  "use strict";
  const B = window.B;
  const {fmt, pct, pct1, dec} = B;
  const WORDS = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

  function numbers(D) {
    const s = D.stats, rows = D.laws.rows, cats = D.laws.categories;
    const fc = s.family_counts;
    B.bind("n_laws", fmt(s.n_laws));
    B.bind("national", fmt(s.national));
    B.bind("private", fmt(s.private));
    B.bind("local", fmt(s.local));
    B.bind("placed", fmt(s.placed));
    B.bind("placed_town", fmt(s.placed_town));
    B.bind("education", fmt(fc[0]));
    // busiest year
    const byYear = d3.rollups(rows.filter(r => r[1]), v => v.length, r => +r[1].slice(0, 4)).sort((a, b) => b[1] - a[1]);
    D.story = {top_year: {year: byYear[0][0], n: byYear[0][1]}};
    B.bind("top_year", String(byYear[0][0]));
    B.bind("top_year_n", fmt(byYear[0][1]));
    // the towns that the most local laws name
    const naming = new Map();
    rows.forEach(r => { if (r[3] <= 4) r[8].forEach(t => naming.set(t, (naming.get(t) || 0) + 1)); });
    const tops = Array.from(naming.entries()).sort((a, b) => b[1] - a[1]);
    if (tops.length) {
      const nm = t => B.townName(D.laws.towns[t][1]);
      const [t1, n1] = tops[0], [t2, n2] = tops[1] || [null, -1];
      B.bind("top_towns", n1 === n2 ? `${nm(t1)} and ${nm(t2)} have the most, with ${fmt(n1)} each.` : `${nm(t1)} has the most, with ${fmt(n1)}.`);
    }
    // local share by Congress
    const share = c => {
      const rs = rows.filter(r => r[2] === c);
      return rs.filter(r => cats[r[4]].scope === "local").length / Math.max(1, rs.length);
    };
    B.bind("c8_n", fmt(rows.filter(r => r[2] === 8).length));
    B.bind("c8_local", pct(share(8)));
    B.bind("c14_local", pct(share(14)));
    const bd = D.calendar.big_days[0];
    B.bind("big_day", B.dateText(bd[0]));
    B.bind("big_day_n", fmt(bd[1]));
    // bills
    const e8 = D.bills.eighth;
    const filed8 = (e8.filed.filed_local || 0) + (e8.filed.filed_national || 0) + (e8.filed.filed_private || 0);
    B.bind("n_bills", fmt(D.bills.n_bills));
    B.bind("c8_bills", fmt(filed8));
    B.bind("c8_bills_local_share", pct(e8.filed.filed_local / filed8));
    B.bind("c8_local_laws", fmt(e8.laws.local || 0));
    B.bind("c8_pass_max", String(Math.ceil((e8.laws.local || 0) / e8.filed.filed_local * 100)));
    // local bills filed per year: the 1988 peak and the most in any year after it
    const perYear = new Map();
    (D.bills.monthly || []).forEach(([m, d]) => { const y = +m.slice(0, 4); if (y >= 1987) perYear.set(y, (perYear.get(y) || 0) + (d.local || 0)); });
    const yrs = Array.from(perYear.entries()).sort((a, b) => b[1] - a[1]);
    if (yrs.length) {
      const [py, pn] = yrs[0];
      B.bind("peak_year", String(py));
      B.bind("peak_local", fmt(pn));
      B.bind("peak_after", fmt(d3.max(Array.from(perYear.entries()).filter(([y]) => y > py), d => d[1]) || 0));
    }
    B.bind("c8_one_in", fmt(Math.round(e8.filed.filed_local / Math.max(1, e8.laws.local || 0))));
    // hospitals
    const rec = D.hospitals.beds.filter(b => b.year >= 2016), old = rec.filter(b => b.year <= 2022);
    B.bind("h_n", fmt(rec.length));
    B.bind("h_below", fmt(rec.filter(b => b.accredited < b.to).length));
    B.bind("h_old", fmt(old.length));
    B.bind("h_oldbelow", fmt(old.filter(b => b.accredited < b.to).length));
    // schools
    const lv = D.schools.levels, n = D.schools.n_window;
    const sum = k => d3.sum(Object.entries(lv).filter(([key]) => key.endsWith("|" + k)), d => d[1]);
    B.bind("s_n", fmt(n));
    B.bind("s_named", pct(sum("named") / n));
    B.bind("s_nf", pct(sum("not_found") / n));
    B.bind("s_recent", fmt(D.schools.recent));
    B.bind("s_pre", pct(D.schools.recent_preexisting / D.schools.recent));
    B.bind("s_est_pre", fmt(D.schools.recent_establish_preexisting || 0));
    B.bind("s_est_n", fmt(D.schools.recent_establish || 0));
    const pc = D.schools.per_congress;
    B.bind("sep13", fmt((pc[13] || {}).separate || 0));
    B.bind("sep14", fmt((pc[14] || {}).separate || 0));
    // authors
    const A = D.authors;
    B.bind("a_laws", fmt(A.n_laws_with_author));
    B.bind("a_laws_district", fmt(A.n_laws_district_author || 0));
    B.bind("a_famshare", pct(A.n_family / A.n_terms));
    B.bind("a_fam", dec(A.family.mean));
    B.bind("a_oth", dec(A.other.mean));
    const cmp = Object.values(A.by_congress).map(b => b.family.mean - b.other.mean);
    const more = cmp.filter(d => d > 0.1).length, less = cmp.filter(d => d < -0.1).length, same = cmp.length - more - less;
    const bits = [more && ["more", more], same && ["about the same", same], less && ["fewer", less]].filter(Boolean)
      .map(([w, k], i) => `${w} in ${WORDS[k] || k}${i === 0 ? (k === 1 ? " Congress" : " Congresses") : ""}`);
    B.bind("a_pattern", "family seats averaged " + (bits.length > 1 ? bits.slice(0, -1).join(", ") + ", and " + bits[bits.length - 1] : bits[0]));
    // effort: Senate floor days, days of debate and urgent certifications, 13th to 19th Congress
    const E = D.effort;
    if (E) {
      const S = E.scopes, tot = k => d3.sum(Object.values(S), s => s[k]);
      const laws = tot("laws"), floor = tot("floor_days"), debate = tot("debate_days");
      B.bind("e_n", fmt(E.n));
      B.bind("e_linked", fmt(E.linked));
      B.bind("e_loc_laws", pct(S.local.laws / laws));
      B.bind("e_loc_floor", pct(S.local.floor_days / floor));
      B.bind("e_loc_debate", pct(S.local.debate_days / debate));
      B.bind("e_nat_laws", pct(S.national.laws / laws));
      B.bind("e_nat_floor", pct(S.national.floor_days / floor));
      B.bind("e_nat_debate", pct(S.national.debate_days / debate));
      B.bind("e_batch", fmt(S.local.batch));
      B.bind("e_loc_linked", fmt(S.local.linked));
      // the median counts the law itself; the text gives the others passed that day
      B.bind("e_tr_loc", fmt(S.local.third_with_median - 1));
      B.bind("e_tr_nat", fmt(S.national.third_with_median - 1));
      B.bind("e_bigday", B.dateText(E.biggest_third_day[0]));
      B.bind("e_bigday_n", fmt(E.biggest_third_day[1]));
      const cert = tot("certified");
      B.bind("e_cert", fmt(cert));
      B.bind("e_cert_nat", fmt(S.national.certified));
      const ys = E.certified_local.map(c => c.year);
      B.bind("e_cert_local_n", WORDS[ys.length] || fmt(ys.length));
      B.bind("e_cert_local_years", `${d3.min(ys)} to ${d3.max(ys)}`);
      B.bind("e_cert_share", pct(cert / laws));
      B.bind("e_cert_floor", pct(E.certified_floor_days / floor));
      B.bind("e_cert_debate", pct(E.certified_debate_days / debate));
      const cs = E.certified_sources;
      B.bind("e_pllo_both", fmt(cs.both || 0));
      B.bind("e_pllo_n", fmt((cs.both || 0) + (cs.PLLO || 0)));
      B.bind("e_pllo_only", fmt(cs.PLLO || 0));
    }
    // calendar
    const dated = rows.filter(r => r[1]);
    const pre = dated.filter(r => +r[1].slice(0, 4) <= 1972), post = dated.filter(r => +r[1].slice(0, 4) >= 1987);
    const june = rs => rs.filter(r => r[1].slice(5, 7) === "06").length / rs.length;
    B.bind("june_pre", pct(june(pre)));
    B.bind("june_post", pct(june(post)));
    // sources and validation
    if (s.sources) {
      B.bind("n_chanrobles", fmt(s.sources.chanrobles || 0));
      B.bind("n_house", fmt(s.sources["house record"] || 0));
    }
    if (s.missing) B.bind("n_missing", WORDS[s.missing.length] ? WORDS[s.missing.length][0].toUpperCase() + WORDS[s.missing.length].slice(1) : fmt(s.missing.length));
    const v = D.validation;
    if (v) {
      B.bind("v_n", fmt(v.first.n)); B.bind("v_cat", pct1(v.first.category)); B.bind("v_scope", pct1(v.first.scope));
      if (v.second) { B.bind("v2_n", fmt(v.second.n)); B.bind("v2_cat", pct1(v.second.category)); B.bind("v2_scope", pct1(v.second.scope)); }
    }
  }

  const files = ["laws", "provinces", "bills", "calendar", "hospitals", "schools", "authors", "fashions", "odd", "stats", "validation", "effort"];
  Promise.all([...files.map(f => fetch(`data/${f}.json`).then(r => (r.ok ? r.json() : null))), fetch("provinces.topojson").then(r => r.json())])
    .then(res => {
      const D = {};
      files.forEach((f, i) => { D[f] = res[i]; });
      D.topo = res[files.length];
      numbers(D);
      try { B.story.init(D); } catch (e) { console.error(e); }
      try { B.explore.init(D); } catch (e) { console.error(e); }
      try { B.charts.init(D); } catch (e) { console.error(e); }
    })
    .catch(err => {
      console.error(err);
      const p = B.el("p", {class: "dek", text: "The data files could not be loaded. If you opened this page from disk, serve the docs folder over HTTP instead."});
      B.$(".herocard").append(p);
    });
})();
