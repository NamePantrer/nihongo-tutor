/* KanjiVG stroke playback (CC BY-SA). */
(function (root) {
  const VIEW = 109;
  const cache = new Map();
  let inflight = 0;
  const queued = [];
  let observer = null;

  function reduced() {
    return !!(root.matchMedia && root.matchMedia("(prefers-reduced-motion: reduce)").matches);
  }

  function creditLine(meta) {
    return (meta && meta.attribution) || "KanjiVG — http://kanjivg.tagaini.net";
  }

  async function loadLevel(level) {
    const lv = (level || "N5").toUpperCase();
    if (cache.has("lv:" + lv)) return cache.get("lv:" + lv);
    const data = await fetch("/api/strokes?level=" + encodeURIComponent(lv)).then((r) => r.json());
    const by = data.by_char || {};
    Object.keys(by).forEach((ch) => cache.set(ch, { paths: by[ch], meta: data }));
    cache.set("lv:" + lv, data);
    return data;
  }

  async function loadChar(ch) {
    if (cache.has(ch) && cache.get(ch).paths) return cache.get(ch);
    const data = await fetch("/api/strokes?c=" + encodeURIComponent(ch)).then((r) => r.json());
    const pack = { paths: data.paths || [], parts: data.parts || [], meta: data };
    cache.set(ch, pack);
    return pack;
  }

  function explodeParts(svg, parts) {
    const ns = "http://www.w3.org/2000/svg";
    const ink = svg.querySelector(".ks-ink");
    if (!ink || !parts.length) return;
    const paths = [...ink.querySelectorAll(":scope > path")];
    const n = parts.length;
    parts.forEach((part, pi) => {
      const g = document.createElementNS(ns, "g");
      g.setAttribute("class", "ks-part");
      const dx = (pi - (n - 1) / 2) * 22;
      const dy = pi % 2 === 0 ? -3 : 7;
      g.style.setProperty("--dx", `${dx}px`);
      g.style.setProperty("--dy", `${dy}px`);
      (part.i || []).forEach((ix) => {
        if (paths[ix]) g.appendChild(paths[ix]);
      });
      const glyph = part.glyph || part.original || part.element || "";
      if (glyph) {
        g.setAttribute("data-open-radical", glyph);
        g.setAttribute("tabindex", "0");
        g.style.cursor = "pointer";
      }
      ink.appendChild(g);
    });
    const split = () => svg.classList.add("ks-split");
    if (reduced()) split();
    else requestAnimationFrame(split);
  }

  function fillPartChips(host, parts) {
    const slot = host.parentNode && host.parentNode.querySelector("[data-dict-parts]");
    if (!slot) return;
    slot.replaceChildren();
    parts.forEach((part) => {
      const glyph = part.glyph || part.original || part.element || "";
      if (!glyph) return;
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "dict-chip";
      btn.dataset.openRadical = glyph;
      const ja = document.createElement("span");
      ja.className = "dict-chip-ja";
      ja.textContent = glyph;
      const ru = document.createElement("span");
      ru.className = "dict-chip-ru";
      ru.textContent = part.ru || "";
      btn.append(ja, ru);
      slot.appendChild(btn);
    });
  }

  function makeSvg(paths, { ghost = true, wide = false } = {}) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("viewBox", `0 0 ${VIEW} ${VIEW}`);
    svg.setAttribute("aria-hidden", "true");
    svg.classList.add("kanji-strokes");
    if (wide) svg.classList.add("kanji-strokes-xl");
    const ns = "http://www.w3.org/2000/svg";
    const gGhost = document.createElementNS(ns, "g");
    gGhost.setAttribute("class", "ks-ghost");
    const gInk = document.createElementNS(ns, "g");
    gInk.setAttribute("class", "ks-ink");
    (paths || []).forEach((d) => {
      if (ghost) {
        const p = document.createElementNS(ns, "path");
        p.setAttribute("d", d);
        gGhost.appendChild(p);
      }
      const ink = document.createElementNS(ns, "path");
      ink.setAttribute("d", d);
      gInk.appendChild(ink);
    });
    svg.appendChild(gGhost);
    svg.appendChild(gInk);
    return svg;
  }

  function finish(svg) {
    svg.querySelectorAll(".ks-ink path").forEach((p) => {
      p.style.strokeDasharray = "none";
      p.style.strokeDashoffset = "0";
    });
  }

  function playSvg(svg, onStroke) {
    const paths = [...svg.querySelectorAll(".ks-ink path")];
    if (!paths.length) return Promise.resolve();
    if (onStroke) onStroke(0, paths.length);
    if (reduced()) {
      finish(svg);
      if (onStroke) onStroke(paths.length, paths.length);
      return Promise.resolve();
    }
    paths.forEach((p) => {
      const len = Math.max(p.getTotalLength(), 1);
      p.style.strokeDasharray = String(len);
      p.style.strokeDashoffset = String(len);
    });
    let chain = Promise.resolve();
    paths.forEach((p, i) => {
      chain = chain.then(
        () =>
          new Promise((resolve) => {
            if (onStroke) onStroke(i + 1, paths.length);
            const len = Math.max(p.getTotalLength(), 1);
            const ms = Math.min(820, 220 + len * 3.4);
            const anim = p.animate(
              [{ strokeDashoffset: len }, { strokeDashoffset: 0 }],
              { duration: ms, easing: "cubic-bezier(0.22, 0.61, 0.36, 1)", fill: "forwards" }
            );
            anim.onfinish = () => setTimeout(resolve, 55);
            anim.oncancel = () => resolve();
          })
      );
    });
    return chain;
  }

  function numberStrokes(svg) {
    svg.querySelector(".ks-nums")?.remove();
    const ns = "http://www.w3.org/2000/svg";
    const g = document.createElementNS(ns, "g");
    g.setAttribute("class", "ks-nums");
    svg.querySelectorAll(".ks-ink path").forEach((p, i) => {
      let pt;
      try {
        pt = p.getPointAtLength(0);
      } catch (err) {
        return;
      }
      const c = document.createElementNS(ns, "circle");
      c.setAttribute("cx", String(pt.x));
      c.setAttribute("cy", String(pt.y));
      c.setAttribute("r", "8");
      c.setAttribute("class", "ks-num-dot");
      const t = document.createElementNS(ns, "text");
      t.setAttribute("x", String(pt.x));
      t.setAttribute("y", String(pt.y + 0.6));
      t.setAttribute("class", "ks-num-text");
      t.textContent = String(i + 1);
      g.appendChild(c);
      g.appendChild(t);
    });
    svg.appendChild(g);
  }

  function enqueue(fn) {
    return new Promise((resolve) => {
      const run = () => {
        inflight += 1;
        Promise.resolve(fn())
          .catch(() => {})
          .finally(() => {
            inflight -= 1;
            if (queued.length) queued.shift()();
            resolve();
          });
      };
      if (inflight < 3) run();
      else queued.push(run);
    });
  }

  function disconnectGrid() {
    if (observer) {
      observer.disconnect();
      observer = null;
    }
  }

  function attachGrid(root, level, opts) {
    disconnectGrid();
    const autoplay = !opts || opts.autoplay !== false;
    const cells = [...(root.querySelectorAll(".kanji-cell[data-c]") || [])];
    if (!cells.length) return;
    loadLevel(level).then((data) => {
      const by = (data && data.by_char) || {};
      cells.forEach((btn) => {
        const ch = btn.dataset.c;
        const paths = by[ch];
        if (!paths || !paths.length) return;
        const slot = btn.querySelector(".kanji-write");
        if (!slot) return;
        const svg = makeSvg(paths, { ghost: true, wide: false });
        slot.replaceChildren(svg);
        btn.classList.add("has-strokes");
        btn.dataset.written = "";
      });
      if (!autoplay) {
        cells.forEach((btn) => {
          const svg = btn.querySelector("svg.kanji-strokes");
          if (!svg) return;
          finish(svg);
          btn.dataset.written = "1";
          btn.classList.add("is-written");
        });
        return;
      }
      observer = new IntersectionObserver(
        (entries) => {
          entries.forEach((entry) => {
            if (!entry.isIntersecting) return;
            const btn = entry.target;
            observer.unobserve(btn);
            if (btn.dataset.written === "1") return;
            const svg = btn.querySelector("svg.kanji-strokes");
            if (!svg) return;
            btn.dataset.written = "1";
            btn.classList.add("is-writing");
            enqueue(() => playSvg(svg)).then(() => btn.classList.add("is-written"));
          });
        },
        { root: root.querySelector(".kanji-koushi") || null, threshold: 0.35 }
      );
      cells.forEach((btn) => {
        if (btn.querySelector("svg.kanji-strokes")) observer.observe(btn);
      });
    });
  }

  function stopPlate(host) {
    if (host && host._ksLoop) {
      clearTimeout(host._ksLoop);
      host._ksLoop = 0;
    }
  }

  function stopPlates() {
    document.querySelectorAll("[data-stroke-host]").forEach(stopPlate);
  }

  async function playPlate(host, ch, extra) {
    const pack = await loadChar(ch);
    if (!host) return pack;
    stopPlate(host);
    const gen = (host._ksGen = (host._ksGen || 0) + 1);
    const parent = host.parentNode;
    parent?.querySelectorAll("[data-stroke-ix]").forEach((n) => n.remove());
    if (!pack.paths.length) {
      host.textContent = ch;
      return pack;
    }
    const svg = makeSvg(pack.paths, { ghost: true, wide: true });
    host.replaceChildren(svg);
    numberStrokes(svg);
    const compact = host.classList.contains("kanji-stage-sm");
    const parts = (extra && extra.parts) || pack.parts || [];
    const split = host.hasAttribute("data-dict-split") && parts.length >= 2;
    let onStroke;
    if (!compact && parent) {
      const ix = document.createElement("p");
      ix.className = "dict-stroke";
      ix.dataset.strokeIx = "1";
      ix.textContent = pack.paths.length ? `черта 0 / ${pack.paths.length}` : "";
      onStroke = (n, total) => {
        ix.textContent = n ? `черта ${n} / ${total}` : `черт ${total}`;
      };
      const chromeAt = parent.querySelector("[data-stroke-chrome]");
      if (chromeAt) chromeAt.replaceChildren(ix);
      else host.after(ix);
    }
    const afterDraw = () => {
      if (host._ksGen !== gen) return;
      if (split) {
        svg.querySelector(".ks-nums")?.remove();
        explodeParts(svg, parts);
        fillPartChips(host, parts);
      }
      if (compact || reduced()) return;
      host._ksLoop = setTimeout(() => {
        if (host._ksGen !== gen || !host.isConnected) return;
        playPlate(host, ch, extra);
      }, 5200);
    };
    playSvg(svg, onStroke).then(afterDraw);
    return pack;
  }

  async function replayCell(btn) {
    const svg = btn && btn.querySelector("svg.kanji-strokes");
    if (!svg) return;
    btn.classList.add("is-writing");
    await playSvg(svg);
  }

  root.ProbaStrokes = {
    loadLevel,
    loadChar,
    attachGrid,
    disconnectGrid,
    playPlate,
    replayCell,
    stopPlates,
    creditLine,
  };
})(window);
