/* Stylized virtual anchors (flat vector, webtoon style).
 * Deliberately NOT photoreal: cartoon anchors never fall into the uncanny valley,
 * lip-sync reads naturally, and the look matches broadcast-style motion graphics.
 * makeAnchor(spec) -> { el, update(t, open, talking) }
 *   open    : 0..1 mouth openness for this frame (from the audio envelope)
 *   talking : 0..1 whether this anchor is the current speaker (smoothed)
 */
(function () {
  const NS = "http://www.w3.org/2000/svg";
  const S = (tag, attrs, parent) => {
    const e = document.createElementNS(NS, tag);
    for (const k in attrs) e.setAttribute(k, attrs[k]);
    if (parent) parent.appendChild(e);
    return e;
  };

  const PRESETS = {
    F: { skin: "#ffdcc8", skinShade: "#f4b9a0", hair: "#2b1a1f", hairHi: "#4a2c33", suit: "#ff2e63", suitShade: "#c81d4b",
         shirt: "#ffffff", lip: "#d2475c", style: "long", seed: 0.37 },
    M: { skin: "#f6d0b5", skinShade: "#e2ad8f", hair: "#16161f", hairHi: "#30304a", suit: "#1d2f7a", suitShade: "#121e52",
         shirt: "#ffffff", tie: "#ffe23d", lip: "#b8505a", style: "short", seed: 1.91 },
  };

  function makeAnchor(spec) {
    const p = Object.assign({}, PRESETS[spec.preset || "F"], spec.colors || {});
    const wrap = document.createElement("div");
    wrap.className = "anchor";
    const svg = S("svg", { viewBox: "0 0 320 430" });
    wrap.appendChild(svg);

    const body = S("g", {}, svg);
    // hair behind head (long style)
    if (p.style === "long") {
      S("path", { d: "M62 190 C50 90 110 52 160 52 C214 52 272 92 258 200 C268 270 262 320 238 350 L82 350 C58 318 52 268 62 190Z", fill: p.hair }, body);
    }
    // torso / suit
    S("path", { d: "M18 430 C22 360 60 318 120 304 L200 304 C262 318 300 360 304 430Z", fill: p.suit }, body);
    S("path", { d: "M18 430 C22 380 44 346 80 326 L104 430Z", fill: p.suitShade, opacity: .6 }, body);
    S("path", { d: "M128 304 L160 372 L192 304Z", fill: p.shirt }, body);
    if (p.tie) S("path", { d: "M152 318 L168 318 L174 330 L166 392 L160 402 L154 392 L146 330Z", fill: p.tie }, body);
    S("path", { d: "M120 304 L160 380 L140 430 L96 430 Z", fill: p.suitShade, opacity: .5 }, body);
    S("path", { d: "M200 304 L160 380 L180 430 L224 430 Z", fill: p.suitShade, opacity: .5 }, body);
    // mic pin
    S("circle", { cx: 214, cy: 350, r: 7, fill: "#111" }, body);
    // neck
    S("path", { d: "M136 250 L184 250 L186 310 C172 322 148 322 134 310Z", fill: p.skinShade }, body);

    const head = S("g", {}, svg);
    // ears
    S("ellipse", { cx: 72, cy: 186, rx: 14, ry: 22, fill: p.skinShade }, head);
    S("ellipse", { cx: 248, cy: 186, rx: 14, ry: 22, fill: p.skinShade }, head);
    if (p.style === "long") {
      S("circle", { cx: 72, cy: 212, r: 6, fill: "#ffe23d" }, head);
      S("circle", { cx: 248, cy: 212, r: 6, fill: "#ffe23d" }, head);
    }
    // face
    S("path", { d: "M74 160 C74 96 112 70 160 70 C208 70 246 96 246 160 C246 230 208 274 160 274 C112 274 74 230 74 160Z", fill: p.skin }, head);
    // blush
    const blushL = S("ellipse", { cx: 108, cy: 214, rx: 20, ry: 11, fill: "#ff7b93", opacity: .35 }, head);
    const blushR = S("ellipse", { cx: 212, cy: 214, rx: 20, ry: 11, fill: "#ff7b93", opacity: .35 }, head);

    // eyes
    const eyes = [];
    [[124, 182], [196, 182]].forEach(([x, y]) => {
      const g = S("g", {}, head);
      S("ellipse", { cx: x, cy: y, rx: 17, ry: 19, fill: "#fff" }, g);
      const iris = S("g", {}, g);
      S("circle", { cx: x, cy: y + 2, r: 13, fill: "#3a2418" }, iris);
      S("circle", { cx: x, cy: y + 2, r: 7, fill: "#120a06" }, iris);
      S("circle", { cx: x + 5, cy: y - 4, r: 4.5, fill: "#fff" }, iris);
      S("path", { d: `M${x - 20} ${y - 12} Q${x} ${y - 26} ${x + 20} ${y - 12}`, stroke: "#1a1014", "stroke-width": 5, fill: "none", "stroke-linecap": "round" }, g);
      eyes.push({ g, iris, x, y });
    });
    // brows
    const brows = [[124, 146], [196, 146]].map(([x, y], i) =>
      S("path", { d: `M${x - 20} ${y + (i ? -2 : 2)} Q${x} ${y - 8} ${x + 20} ${y + (i ? 2 : -2)}`, stroke: p.hair, "stroke-width": 7, fill: "none", "stroke-linecap": "round" }, head));
    // nose
    S("path", { d: "M160 196 Q156 218 150 222 Q158 226 166 222", stroke: p.skinShade, "stroke-width": 4, fill: "none", "stroke-linecap": "round" }, head);
    // mouth
    const mouth = S("g", {}, head);
    const mouthIn = S("path", { fill: "#5a1420" }, mouth);
    const teeth = S("rect", { x: 146, y: 236, width: 28, height: 7, rx: 3, fill: "#fff" }, mouth);
    const tongue = S("ellipse", { cx: 160, cy: 252, rx: 12, ry: 6, fill: "#ff6f86" }, mouth);
    const lips = S("path", { fill: "none", stroke: p.lip, "stroke-width": 4, "stroke-linecap": "round" }, mouth);

    // front hair
    if (p.style === "long") {
      S("path", { d: "M70 168 C64 92 112 56 164 58 C220 60 258 100 250 172 C236 130 214 112 196 104 C170 128 128 134 96 128 C84 140 76 154 70 168Z", fill: p.hair }, head);
      S("path", { d: "M120 82 C150 70 190 72 214 88", stroke: p.hairHi, "stroke-width": 8, fill: "none", "stroke-linecap": "round", opacity: .8 }, head);
    } else {
      S("path", { d: "M70 168 C60 84 112 50 168 54 C226 58 260 98 250 166 C244 140 232 120 214 108 C176 120 130 110 104 98 C88 116 76 138 70 168Z", fill: p.hair }, head);
      S("path", { d: "M104 98 C130 76 186 70 226 96", stroke: p.hairHi, "stroke-width": 8, fill: "none", "stroke-linecap": "round", opacity: .8 }, head);
    }

    if (spec.name) {
      const tag = document.createElement("div");
      tag.className = "tag";
      tag.innerHTML = `<b>${spec.role || "앵커"}</b>${spec.name}`;
      wrap.appendChild(tag);
    }

    let smoothOpen = 0;
    function update(t, open, talking) {
      // smooth mouth so it never flickers frame to frame
      smoothOpen += (open - smoothOpen) * 0.6;
      const o = Math.max(0, Math.min(1, smoothOpen)) * (0.35 + 0.65 * talking);
      const sd = p.seed;
      // head motion: slow sway + speech-driven nods
      const rot = Math.sin(t * 1.1 + sd) * 2.2 + talking * Math.sin(t * 5.3 + sd) * 1.6;
      const nod = talking * (Math.sin(t * 8.1 + sd) * 2.2 + o * 4);
      const tx = Math.sin(t * 0.7 + sd * 3) * 3;
      head.setAttribute("transform", `translate(${tx} ${nod}) rotate(${rot} 160 300)`);
      const breathe = 1 + Math.sin(t * 2.1 + sd) * 0.008;
      body.setAttribute("transform", `translate(160 430) scale(1 ${breathe}) translate(-160 -430) translate(${tx * 0.4} 0)`);
      // blink (deterministic pseudo-random rhythm)
      const ph = (t + sd * 2.3) % 3.4;
      const blink = ph < 0.13 ? Math.sin((ph / 0.13) * Math.PI) : 0;
      const look = Math.sin(t * 0.9 + sd) * 2.5;
      eyes.forEach(e => {
        e.g.setAttribute("transform", `translate(0 ${e.y}) scale(1 ${1 - 0.92 * blink}) translate(0 ${-e.y})`);
        e.iris.setAttribute("transform", `translate(${look} 0)`);
      });
      // brows lift on emphasis
      const lift = -talking * Math.max(0, Math.sin(t * 2.7 + sd)) * 6 - o * 3;
      brows.forEach(b => b.setAttribute("transform", `translate(0 ${lift})`));
      // mouth shape: smile line that opens with the envelope
      const w = 22 + o * 4, cy = 238, smile = 6 - o * 3, drop = 4 + o * 30;
      mouthIn.setAttribute("d", `M${160 - w} ${cy} Q160 ${cy + 2 - smile} ${160 + w} ${cy} Q160 ${cy + drop + smile} ${160 - w} ${cy}Z`);
      lips.setAttribute("d", `M${160 - w - 3} ${cy - 2} Q160 ${cy + 4 - smile} ${160 + w + 3} ${cy - 2}`);
      const showIn = o > 0.06 ? 1 : 0;
      mouthIn.setAttribute("opacity", showIn);
      teeth.setAttribute("opacity", o > 0.25 ? 1 : 0);
      tongue.setAttribute("cy", cy + drop * 0.62);
      tongue.setAttribute("opacity", o > 0.4 ? 1 : 0);
      blushL.setAttribute("opacity", 0.3 + 0.1 * talking);
      blushR.setAttribute("opacity", 0.3 + 0.1 * talking);
    }
    update(0, 0, 0);
    return { el: wrap, update };
  }

  window.makeAnchor = makeAnchor;
})();
