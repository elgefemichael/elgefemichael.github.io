/* Morning30 deterministic motion-graphics engine.
 * The page never animates on its own: the driver calls window.__seek(t) for each frame,
 * every element is positioned as a pure function of t, then the frame is captured.
 * That makes renders frame-exact and reproducible on any machine (e.g. GitHub Actions).
 */
(function () {
  // ---------- math helpers ----------
  const clamp = (x, a = 0, b = 1) => Math.min(b, Math.max(a, x));
  const prog = (t, t0, d) => clamp((t - t0) / d);
  const lerp = (a, b, k) => a + (b - a) * k;
  const E = {
    outExpo: k => (k >= 1 ? 1 : 1 - Math.pow(2, -10 * k)),
    outBack: k => { const c = 1.9; return 1 + (c + 1) * Math.pow(k - 1, 3) + c * Math.pow(k - 1, 2); },
    outCubic: k => 1 - Math.pow(1 - k, 3),
    inCubic: k => k * k * k,
    inOut: k => (k < .5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2),
    outElastic: k => (k === 0 || k === 1 ? k : Math.pow(2, -10 * k) * Math.sin((k * 10 - .75) * (2 * Math.PI) / 3) + 1),
  };
  // seeded random so particles are identical every render
  let seed = 7;
  const rnd = () => ((seed = (seed * 16807) % 2147483647) / 2147483647);
  const $ = (sel, root = document) => root.querySelector(sel);
  const div = (cls, html, parent) => {
    const e = document.createElement("div");
    if (cls) e.className = cls;
    if (html != null) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  };
  const esc = s => String(s).replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const fmt = (v, dec) => Number(v).toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });

  const THEMES = {
    "경제": ["#0f8f6b", "#25f5b0"], "증시": ["#0f8f6b", "#25f5b0"], "정치": ["#5a2bd6", "#b98cff"],
    "사회": ["#1b6cff", "#00e0ff"], "국제": ["#0b7fa8", "#5ef0ff"], "IT": ["#b01fd1", "#ff7bf2"],
    "과학": ["#b01fd1", "#ff7bf2"], "스포츠": ["#e85d04", "#ffd166"], "생활": ["#c79100", "#ffe066"],
    "날씨": ["#2273d6", "#9be7ff"], "문화": ["#d6336c", "#ffb3c7"], "default": ["#1b6cff", "#00e0ff"],
  };

  let EP = null, scenes = [], anchors = {}, capEl, capIdx = -1, capWords = [], segs = [], particles = [], newsScenes = [];

  // ---------- scene builders ----------
  function buildHeadline(parent, text, highlight) {
    const h = div("abs headline", null, parent);
    const words = text.split(/\s+/).filter(Boolean);
    const ws = words.map(w => {
      const isHl = highlight && (w.includes(highlight) || highlight.includes(w.replace(/[^\w가-힣.,%]/g, "")) && w.length > 1);
      return div("w" + (isHl ? " hl" : ""), esc(w), h);
    });
    return { h, ws };
  }

  function fitHeadline(h, maxH) {
    let fs = 112;
    while (h.scrollHeight > maxH && fs > 60) { fs -= 4; h.style.fontSize = fs + "px"; }
  }

  function buildViz(panel, v) {
    const kind = (v && v.kind) || "keyword";
    panel.classList.add("v-" + kind);
    const o = { kind };
    if (kind === "counter") {
      div("abs lbl", esc(v.label || ""), panel);
      o.num = div("abs num", "", panel);
      o.unit = v.unit ? `<span class="unit">${esc(v.unit)}</span>` : "";
      o.dec = v.decimals != null ? v.decimals : (String(v.value).split(".")[1] || "").length;
      o.value = Number(v.value);
      const dir = v.direction || "flat";
      o.delta = v.delta ? div("abs delta " + dir, (dir === "up" ? "▲ " : dir === "down" ? "▼ " : "") + esc(v.delta), panel) : null;
      const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      svg.setAttribute("viewBox", "0 0 300 300"); svg.classList.add("abs", "arrow");
      const up = dir !== "down";
      const pts = up ? "20,250 90,180 140,215 270,60" : "20,60 90,130 140,95 270,250";
      const head = up ? "M215 55 L275 55 L275 115" : "M275 195 L275 255 L215 255";
      const col = dir === "up" ? "#ff2e4d" : dir === "down" ? "#4d94ff" : "#cfd3e6";
      svg.innerHTML = `<polyline points="${pts}" fill="none" stroke="${col}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" pathLength="1" stroke-dasharray="1" stroke-dashoffset="1"/><path d="${head}" fill="none" stroke="${col}" stroke-width="26" stroke-linecap="round" stroke-linejoin="round" opacity="0"/>`;
      panel.appendChild(svg);
      o.line = svg.firstChild; o.head = svg.lastChild;
    } else if (kind === "versus") {
      const L = v.left || {}, R = v.right || {};
      o.l = div("abs side l", `<div class="t">${esc(L.label || "")}</div><div class="n">${esc(L.value != null ? L.value : "")}</div>`, panel);
      o.r = div("abs side r", `<div class="t">${esc(R.label || "")}</div><div class="n">${esc(R.value != null ? R.value : "")}</div>`, panel);
      o.vs = div("abs vs", "VS", panel);
      const ln = parseFloat(String(L.value).replace(/[^\d.]/g, "")), rn = parseFloat(String(R.value).replace(/[^\d.]/g, ""));
      if (isFinite(ln) && isFinite(rn) && ln + rn > 0) {
        const bar = div("abs bar", null, panel);
        o.bl = div("l", null, bar); o.br = div("r", null, bar); o.ratio = ln / (ln + rn);
        o.bl.style.width = o.br.style.width = "0%";
      }
    } else if (kind === "ranking") {
      const items = (v.items || []).slice(0, 3);
      const max = Math.max(...items.map(i => parseFloat(String(i.value).replace(/[^\d.-]/g, "")) || 0), 1);
      o.rows = items.map((it, i) => {
        const r = div("abs row", null, panel);
        r.style.top = (34 + i * 112) + "px";
        div("rk", String(i + 1), r);
        const bw = div("bw", null, r);
        const b = div("b", null, bw);
        div("tx", esc(it.label), bw);
        div("vv", esc(it.value != null ? it.value : ""), bw);
        const n = parseFloat(String(it.value).replace(/[^\d.-]/g, ""));
        return { r, b, w: isFinite(n) ? Math.max(.35, n / max) : 1 - i * .18 };
      });
    } else if (kind === "stamp") {
      o.stamp = div("abs stamp", esc(v.text || "속보"), panel);
      o.sub = v.sub ? div("abs sub", esc(v.sub), panel) : null;
    } else {
      o.emo = div("abs emo", esc(v.emoji || "📰"), panel);
      o.kw = div("abs kw", esc(v.text || ""), panel);
    }
    o.shine = div("shine", null, panel);
    return o;
  }

  function updateViz(o, panel, lt) {
    const k0 = 0.75; // viz starts after headline
    const pk = E.outBack(prog(lt, k0 - .25, .5));
    panel.style.transform = `perspective(1400px) rotateX(${(1 - pk) * 70}deg) scale(${lerp(.6, 1, pk)})`;
    panel.style.opacity = prog(lt, k0 - .25, .2);
    o.shine.style.left = lerp(-200, 1200, E.inOut(prog(lt, k0 + .4, .8))) + "px";
    if (o.kind === "counter") {
      const ck = E.outExpo(prog(lt, k0, 1.3));
      o.num.innerHTML = fmt(o.value * ck, o.dec) + o.unit;
      o.num.style.transform = `scale(${1 + .08 * Math.sin(Math.PI * prog(lt, k0 + 1.2, .25))})`;
      o.line.setAttribute("stroke-dashoffset", 1 - E.outCubic(prog(lt, k0 + .1, .9)));
      o.head.setAttribute("opacity", prog(lt, k0 + .9, .1));
      if (o.delta) { const d = E.outBack(prog(lt, k0 + 1.0, .35)); o.delta.style.transform = `scale(${d})`; }
    } else if (o.kind === "versus") {
      const a = E.outBack(prog(lt, k0, .45)), b = E.outBack(prog(lt, k0 + .15, .45));
      o.l.style.transform = `translateX(${(1 - a) * -500}px)`;
      o.r.style.transform = `translateX(${(1 - b) * 500}px)`;
      const vk = E.outElastic(prog(lt, k0 + .35, .7));
      o.vs.style.transform = `scale(${vk * (1 + .05 * Math.sin(lt * 9))}) rotate(${(1 - vk) * -90}deg)`;
      if (o.bl) { const bk = E.outCubic(prog(lt, k0 + .6, .9)); o.bl.style.width = (o.ratio * 100 * bk) + "%"; o.br.style.width = ((1 - o.ratio) * 100 * bk) + "%"; }
    } else if (o.kind === "ranking") {
      o.rows.forEach((r, i) => {
        const rk = E.outCubic(prog(lt, k0 + i * .18, .7));
        r.b.style.width = (r.w * 100 * rk) + "%";
        r.r.style.opacity = prog(lt, k0 + i * .18, .15);
        r.r.style.transform = `translateX(${(1 - E.outBack(prog(lt, k0 + i * .18, .4))) * -80}px)`;
      });
    } else if (o.kind === "stamp") {
      const sk = prog(lt, k0 + .15, .22);
      const s = sk < 1 ? lerp(3.2, 1, E.inCubic(sk)) : 1 + .04 * Math.sin(prog(lt, k0 + .37, .2) * Math.PI);
      o.stamp.style.transform = `translate(-50%,-50%) rotate(-9deg) scale(${s})`;
      o.stamp.style.opacity = sk > 0 ? 1 : 0;
      if (o.sub) o.sub.style.opacity = prog(lt, k0 + .5, .3);
    } else {
      const ek = E.outElastic(prog(lt, k0, .9));
      o.emo.style.transform = `translateX(-50%) scale(${ek}) rotate(${Math.sin(lt * 3) * 6}deg)`;
      const kk = E.outBack(prog(lt, k0 + .3, .4));
      o.kw.style.transform = `scale(${kk})`;
    }
  }

  function buildNews(sc, root) {
    const chip = div("abs chip", esc(sc.category || "뉴스"), root);
    const no = div("abs newsno", "0" + sc.no, root);
    const { h, ws } = buildHeadline(root, sc.headline, sc.highlight);
    const panel = div("abs panel", null, root);
    const viz = buildViz(panel, sc.viz);
    let meme = null;
    if (sc.meme && sc.meme.text) meme = div("abs meme", `<span class="e">${esc(sc.meme.emoji || "")}</span>${esc(sc.meme.text)}`, root);
    return {
      fit() {
        fitHeadline(h, 280);
        const top = Math.min(700, 400 + h.scrollHeight + 50);
        panel.style.top = top + "px";
        if (meme) meme.style.top = (top + 350) + "px";
      },
      update(lt, dur) {
        const ck = E.outBack(prog(lt, .12, .35));
        chip.style.transform = `skewX(-12deg) scaleX(${ck})`;
        const nk = E.outExpo(prog(lt, .05, .6));
        no.style.transform = `translateX(${(1 - nk) * 400}px) rotate(${(1 - nk) * 20}deg)`;
        ws.forEach((w, i) => {
          const wk = prog(lt, .22 + i * .07, .32);
          const e = E.outBack(wk);
          w.style.opacity = wk > 0 ? 1 : 0;
          w.style.transform = `translateY(${(1 - e) * 90}px) scale(${lerp(.4, 1, e)}) rotate(${(1 - e) * -8}deg)`;
          if (w.classList.contains("hl")) w.style.setProperty("--mk", E.outCubic(prog(lt, .55 + i * .07, .35)));
        });
        updateViz(viz, panel, lt);
        if (meme) {
          const at = Math.min(dur * (sc.meme_at || .55), dur - 1.2);
          const mk = prog(lt, at, .45);
          const e = E.outElastic(mk);
          meme.style.opacity = mk > 0 ? 1 : 0;
          meme.style.transform = `rotate(${lerp(-25, -5, e) + Math.sin(lt * 4) * 1.5}deg) scale(${e})`;
        }
        // whole scene gets a subtle push-in so nothing is ever static
        root.style.transform = `scale(${1 + lt * .006})`;
      },
    };
  }

  function buildIntro(sc, root) {
    const title = div("abs intro-title", (sc.title_lines || ["오늘 아침", "30초 브리핑"]).map((l, i) => `<div class="ln${i ? " y" : ""}">${esc(l)}</div>`).join(""), root);
    const lines = [...title.children];
    const sub = div("abs intro-sub", esc(sc.sub || ""), root);
    const teasers = (sc.teasers || []).slice(0, 3).map((t, i) => {
      const e = div("abs teaser", `<b>#${i + 1}</b>${esc(t)}`, root);
      e.style.top = (830 + i * 110) + "px";
      return e;
    });
    return {
      fit() {},
      update(lt) {
        lines.forEach((l, i) => {
          const k = prog(lt, i * .14, .4);
          const s = k < 1 ? lerp(2.6, 1, E.inCubic(k)) : 1;
          l.style.opacity = k > 0 ? 1 : 0;
          l.style.transform = `scale(${s}) rotate(${i ? 2 : -2}deg)`;
        });
        const sk = E.outCubic(prog(lt, .45, .35));
        sub.style.opacity = sk; sub.style.transform = `translateY(${(1 - sk) * 40}px)`;
        teasers.forEach((e, i) => {
          const k = E.outBack(prog(lt, .6 + i * .16, .4));
          const from = i % 2 ? 900 : -900;
          e.style.transform = `translateX(calc(-50% + ${(1 - k) * from}px)) rotate(${i % 2 ? 3 : -3}deg)`;
        });
        root.style.transform = `scale(${1 + lt * .01})`;
      },
    };
  }

  function buildOutro(sc, root) {
    const title = div("abs intro-title", (sc.title_lines || ["내일 아침", "또 만나요!"]).map((l, i) => `<div class="ln${i ? " y" : ""}">${esc(l)}</div>`).join(""), root);
    title.style.top = "300px"; title.style.fontSize = "150px";
    const lines = [...title.children];
    const btn = div("abs sub-btn", "구독 🔔", root);
    btn.style.top = "650px";
    const cta = sc.cta ? div("abs cta", esc(sc.cta), root) : null;
    if (cta) cta.style.top = "820px";
    return {
      fit() {},
      update(lt) {
        lines.forEach((l, i) => {
          const k = E.outBack(prog(lt, i * .12, .45));
          l.style.transform = `translateY(${(1 - k) * 300}px) scale(${k})`;
        });
        const bk = E.outBack(prog(lt, .4, .4));
        const press = prog(lt, 1.2, .12), rel = prog(lt, 1.32, .15);
        const done = lt > 1.3;
        btn.classList.toggle("done", done);
        btn.textContent = done ? "구독중 ✔" : "구독 🔔";
        btn.style.transform = `scale(${bk * (1 - .08 * press + .08 * rel)}) translateY(${(press - rel) * 12}px)`;
        if (cta) { const ck = E.outCubic(prog(lt, .7, .4)); cta.style.opacity = ck; cta.style.transform = `translateY(${(1 - ck) * 40}px)`; }
      },
    };
  }

  // ---------- load ----------
  window.__load = function (ep) {
    EP = ep;
    document.documentElement.style.setProperty("--dummy", 0);
    $(".logo .name").textContent = ep.brand || "모닝 30";
    $(".date").textContent = ep.date_label || "";
    // particles
    const pr = $(".bg-particles");
    for (let i = 0; i < 46; i++) {
      const p = document.createElement("i");
      const s = 3 + rnd() * 7;
      p.style.width = p.style.height = s + "px";
      pr.appendChild(p);
      particles.push({ el: p, x: rnd() * 1080, y: rnd() * 1920, v: 20 + rnd() * 70, a: .15 + rnd() * .5, ph: rnd() * 6 });
    }
    // scenes
    const host = $("#scenes");
    ep.scenes.forEach(sc => {
      const root = div("scene", null, host);
      const b = sc.type === "intro" ? buildIntro(sc, root) : sc.type === "outro" ? buildOutro(sc, root) : buildNews(sc, root);
      scenes.push({ sc, root, ...b });
      if (sc.type === "news") newsScenes.push(sc);
    });
    // progress segments for news items
    const pg = $(".progress");
    newsScenes.forEach(() => { const s = div("seg", "<b></b>", pg); segs.push(s.firstChild); });
    // anchors
    for (const id in ep.anchors) {
      const a = makeAnchor(Object.assign({ preset: id }, ep.anchors[id]));
      $("#anchor-dock").appendChild(a.el);
      anchors[id] = a;
    }
    capEl = $("#captions .cap");
    scenes.forEach(s => { s.root.style.visibility = "visible"; s.fit(); s.root.style.visibility = "hidden"; });
    return true;
  };

  function sceneAt(t) {
    for (let i = scenes.length - 1; i >= 0; i--) if (t >= scenes[i].sc.start) return i;
    return 0;
  }

  function mouthVal(id, t) {
    const arr = EP.mouth && EP.mouth[id];
    if (!arr || !arr.length) return 0;
    const f = t * (EP.fps || 30);
    const i = Math.floor(f), k = f - i;
    return lerp(arr[Math.min(i, arr.length - 1)] || 0, arr[Math.min(i + 1, arr.length - 1)] || 0, k);
  }

  // ---------- per-frame ----------
  window.__seek = function (t) {
    const idx = sceneAt(t);
    const cur = scenes[idx], sc = cur.sc;
    const lt = t - sc.start, dur = sc.end - sc.start;
    scenes.forEach((s, i) => (s.root.style.visibility = i === idx ? "visible" : "hidden"));
    cur.update(lt, dur);

    // theme
    const th = THEMES[sc.category] || THEMES[sc.type === "news" ? "default" : "사회"] || THEMES.default;
    const fr = $("#frame");
    fr.style.setProperty("--c1", th[0]); fr.style.setProperty("--c2", th[1]);

    // background motion
    $(".bg-stripes").style.backgroundPosition = `${t * 60}px 0`;
    $(".bg-floor .grid").style.backgroundPosition = `0 ${t * 160}px`;
    document.querySelectorAll(".bg-beams i").forEach((b, i) => {
      b.style.transform = `translateX(-50%) rotate(${Math.sin(t * .6 + i * 2.1) * 28 + (i - 1) * 22}deg)`;
      b.style.opacity = .5 + .3 * Math.sin(t * 1.3 + i);
    });
    particles.forEach(p => {
      const y = ((p.y - t * p.v) % 1920 + 1920) % 1920;
      p.el.style.transform = `translate(${p.x + Math.sin(t + p.ph) * 20}px, ${y}px)`;
      p.el.style.opacity = p.a * (.6 + .4 * Math.sin(t * 2 + p.ph));
    });

    // HUD
    const lk = E.outBack(prog(t, 0, .45));
    $(".brand").style.transform = `translateX(${(1 - lk) * -700}px)`;
    $(".live i").style.opacity = .35 + .65 * (Math.sin(t * 6) > 0 ? 1 : 0);
    newsScenes.forEach((ns, i) => { segs[i].style.width = (prog(t, ns.start, ns.end - ns.start) * 100) + "%"; });
    $(".progress").style.opacity = prog(t, .3, .3);

    // anchors placement
    for (const id in anchors) {
      const a = anchors[id], el = a.el;
      let vis = false, x = 24, y = 1060, s = 1, enter = 1;
      if (sc.type === "outro") {
        vis = true; s = 1.05; y = 1050; x = id === Object.keys(anchors)[0] ? 170 : 590;
        enter = E.outBack(prog(lt, .1 + (x > 300 ? .12 : 0), .45));
      } else if (sc.speaker === id) {
        vis = true;
        const prev = scenes[idx - 1];
        const changed = !prev || prev.sc.speaker !== id || prev.sc.type === "outro";
        enter = changed ? E.outBack(prog(lt, .05, .45)) : 1;
      }
      el.style.display = vis ? "block" : "none";
      if (!vis) continue;
      const bob = Math.sin(t * 1.7 + (id === "M" ? 1 : 0)) * 4;
      el.style.left = x + "px"; el.style.top = y + "px";
      el.style.transform = `translateY(${(1 - enter) * 520 + bob}px) scale(${s}) rotate(${(1 - enter) * -12}deg)`;
      const talking = sc.speaker === id || (sc.type === "outro" && capSpeaker(t) === id) ? 1 : 0;
      a.update(t, mouthVal(id, t), talking);
    }

    // captions
    const cap = $("#captions");
    cap.classList.toggle("full", sc.type === "outro");
    if (sc.type === "outro") { cap.style.top = "960px"; cap.style.height = "150px"; } else { cap.style.top = ""; cap.style.height = ""; }
    const ci = captionAt(t);
    if (ci !== capIdx) {
      capIdx = ci;
      if (ci < 0) { capEl.innerHTML = ""; capWords = []; }
      else {
        capEl.innerHTML = EP.captions[ci].words.map(w => `<span class="w">${esc(w.w)}</span>`).join(" ");
        capWords = [...capEl.children];
      }
    }
    if (ci >= 0) {
      const c = EP.captions[ci];
      c.words.forEach((w, i) => {
        capWords[i].classList.toggle("on", t >= w.s - .05);
        capWords[i].classList.toggle("now", t >= w.s - .05 && t < w.e + .02);
      });
      const pk = E.outBack(prog(t, c.start, .18));
      capEl.style.transform = `scale(${lerp(.85, 1, pk)})`;
    }

    // transitions: diagonal colour bars sweep across every scene boundary
    const bars = document.querySelectorAll("#wipe i");
    let wk = -1;
    for (let i = 1; i < scenes.length; i++) {
      const b = scenes[i].sc.start;
      if (t > b - .28 && t < b + .32) wk = (t - (b - .28)) / .6;
    }
    bars.forEach((bar, i) => {
      if (wk < 0) { bar.style.transform = "skewX(-20deg) translateX(-2600px)"; return; }
      const k = E.inOut(clamp(wk * 1.25 - i * .07));
      bar.style.transform = `skewX(-20deg) translateX(${lerp(-2600, 1900, k)}px)`;
    });
    // impact flash at the very start + on stamp hits
    let fl = Math.max(0, 1 - t / .18) * .9;
    if (sc.type === "news" && sc.viz && sc.viz.kind === "stamp") fl = Math.max(fl, .55 * (1 - prog(lt, .97, .2)) * (lt > .97 ? 1 : 0));
    $("#flash").style.opacity = fl;
    return true;
  };

  function captionAt(t) {
    const cs = EP.captions || [];
    for (let i = cs.length - 1; i >= 0; i--) {
      if (t >= cs[i].start - .04) {
        const next = cs[i + 1];
        if (t <= cs[i].end + .5 || (next && t < next.start)) return t <= cs[i].end + .5 ? i : -1;
        return -1;
      }
    }
    return -1;
  }
  function capSpeaker(t) { const i = captionAt(t); return i >= 0 ? EP.captions[i].speaker : null; }
})();
