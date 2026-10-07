/** 星合わせ */
(function () {
  let raf = 0;
  let running = false;

  function project(x, y, z, yaw, pitch, dist, w, h) {
    const cy = Math.cos(yaw);
    const sy = Math.sin(yaw);
    const cp = Math.cos(pitch);
    const sp = Math.sin(pitch);
    let X = x * cy - z * sy;
    let Z = x * sy + z * cy;
    const Y = y * cp - Z * sp;
    Z = y * sp + Z * cp;
    const f = dist / (dist + Z + 2.2);
    const scale = Math.min(w, h) * 0.42;
    return {
      px: w / 2 + X * f * scale,
      py: h / 2 + Y * f * scale,
      f,
      z: Z,
    };
  }

  function stop() {
    running = false;
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
  }

  function mount(canvas, plate, data) {
    stop();
    const stars = (data && data.stars) || [];
    const edges = (data && data.edges) || [];
    if (!canvas || !stars.length) return stop;
    const ctx = canvas.getContext("2d");
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    let yaw = 0.55;
    let pitch = 0.28;
    let dist = 2.8;
    let drag = false;
    let moved = false;
    let lx = 0;
    let ly = 0;
    let hover = null;
    running = true;

    function resize() {
      const wrap = canvas.parentElement;
      const w = Math.max(320, wrap.clientWidth);
      const h = Math.max(380, Math.min(620, Math.round(w * 0.64)));
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      canvas.style.width = w + "px";
      canvas.style.height = h + "px";
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    function drawHanko(x, y, r, alpha) {
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate(-0.18);
      ctx.strokeStyle = `rgba(196, 92, 120, ${alpha})`;
      ctx.lineWidth = Math.max(1.2, r * 0.18);
      ctx.strokeRect(-r, -r, r * 2, r * 2);
      ctx.restore();
    }

    function frame(now) {
      if (!running) return;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      ctx.clearRect(0, 0, w, h);

      const g = ctx.createRadialGradient(w * 0.5, h * 0.42, 16, w * 0.5, h * 0.52, h * 0.9);
      g.addColorStop(0, "#241820");
      g.addColorStop(0.52, "#161018");
      g.addColorStop(1, "#0c080c");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      const neb = ctx.createRadialGradient(w * 0.74, h * 0.26, 8, w * 0.74, h * 0.26, h * 0.42);
      neb.addColorStop(0, "rgba(196, 92, 120, 0.16)");
      neb.addColorStop(1, "rgba(22, 16, 24, 0)");
      ctx.fillStyle = neb;
      ctx.fillRect(0, 0, w, h);

      ctx.fillStyle = "rgba(232, 164, 180, 0.07)";
      const drift = reduce ? 0 : (yaw * 14) % 40;
      for (let i = 0; i < 22; i++) {
        ctx.beginPath();
        ctx.arc(((i * 97) % w) + drift, (i * 53) % h, 0.65, 0, Math.PI * 2);
        ctx.fill();
      }

      ctx.globalAlpha = 0.05;
      for (let i = 0; i < 90; i++) {
        ctx.fillStyle = i % 3 ? "#e8a4b4" : "#d4b48c";
        ctx.fillRect((i * 47) % w, (i * 31) % h, 1, 1);
      }
      ctx.globalAlpha = 1;

      ctx.strokeStyle = "rgba(212, 180, 140, 0.22)";
      ctx.lineWidth = 1;
      ctx.strokeRect(10.5, 10.5, w - 21, h - 21);
      canvas.dataset.orbit = `${yaw.toFixed(3)},${pitch.toFixed(3)},${dist.toFixed(3)}`;

      const proj = {};
      stars.forEach((s) => {
        proj[s.id] = project(s.x, s.y, s.z, yaw, pitch, dist, w, h);
      });

      edges.forEach((e) => {
        const a = proj[e.from];
        const b = proj[e.to];
        if (!a || !b) return;
        const alpha = 0.16 + 0.22 * ((a.f + b.f) / 2);
        const mx = (a.px + b.px) / 2 + (a.py - b.py) * 0.06;
        const my = (a.py + b.py) / 2 + (b.px - a.px) * 0.06;
        ctx.strokeStyle = `rgba(232, 164, 180, ${alpha})`;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(a.px, a.py);
        ctx.quadraticCurveTo(mx, my, b.px, b.py);
        ctx.stroke();
      });

      const t = reduce ? 0 : now / 740;
      const order = stars.slice().sort((a, b) => proj[a.id].z - proj[b.id].z);
      order.forEach((s) => {
        const p = proj[s.id];
        const need = Number(s.need) || 0;
        const pulse = need >= 4 && !reduce ? 0.88 + 0.12 * Math.sin(t + need) : 1;
        const mag = 0.12 + need / 12;
        const r = (2.2 + need * 1.35) * p.f * pulse;
        const alpha = (0.18 + mag * 0.82) * Math.min(1, 0.45 + p.f);
        const teacher = s.provenance === "teacher";
        const core =
          need >= 4
            ? teacher
              ? `rgba(243, 207, 214, ${alpha})`
              : `rgba(232, 164, 180, ${alpha})`
            : `rgba(212, 180, 140, ${alpha * 0.5})`;
        const glow =
          need >= 4 ? `rgba(196, 92, 120, ${alpha * 0.55})` : `rgba(90, 72, 80, ${alpha * 0.32})`;
        const grd = ctx.createRadialGradient(p.px, p.py, 0, p.px, p.py, r * 4.2);
        grd.addColorStop(0, core);
        grd.addColorStop(0.35, glow);
        grd.addColorStop(1, "rgba(22, 16, 24, 0)");
        ctx.fillStyle = grd;
        ctx.beginPath();
        ctx.arc(p.px, p.py, r * 4.2, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(p.px, p.py, Math.max(1.2, r), 0, Math.PI * 2);
        ctx.fill();
        if (need >= 4) drawHanko(p.px, p.py, r * 1.55, alpha * 0.9);
        if (hover && hover.id === s.id) {
          ctx.strokeStyle = "rgba(212, 180, 140, 0.9)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(p.px, p.py, r * 5, 0, Math.PI * 2);
          ctx.stroke();
        }
      });

      raf = requestAnimationFrame(frame);
    }

    function hit(mx, my) {
      let best = null;
      let bestD = 56;
      stars.forEach((s) => {
        const p = project(s.x, s.y, s.z, yaw, pitch, dist, canvas.clientWidth, canvas.clientHeight);
        const d = Math.hypot(p.px - mx, p.py - my);
        if (d < bestD) {
          bestD = d;
          best = s;
        }
      });
      return best;
    }

    function showPlate(s) {
      if (!plate) return;
      if (!s) {
        plate.hidden = true;
        plate.innerHTML = "";
        return;
      }
      plate.hidden = false;
      const why = (s.reasons || []).join(" · ") || "сейчас не ждёт";
      plate.innerHTML = `<p class="sky-kana">${escapePlate(s.label)}</p>
        <p>${escapePlate(s.hint || "")}</p>
        <p class="meta">${escapePlate(why)}</p>`;
    }

    function escapePlate(t) {
      return String(t ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;");
    }

    function onPointerDown(e) {
      drag = true;
      moved = false;
      lx = e.clientX;
      ly = e.clientY;
      canvas.setPointerCapture(e.pointerId);
    }

    function onPointerUp() {
      drag = false;
    }

    function onPointerMove(e) {
      const rect = canvas.getBoundingClientRect();
      const mx = e.clientX - rect.left;
      const my = e.clientY - rect.top;
      if (drag) {
        const dx = e.clientX - lx;
        const dy = e.clientY - ly;
        if (Math.hypot(dx, dy) > 3) moved = true;
        yaw += dx * 0.008;
        pitch = Math.max(-1.15, Math.min(1.15, pitch + dy * 0.008));
        lx = e.clientX;
        ly = e.clientY;
      } else {
        hover = hit(mx, my);
        canvas.style.cursor = hover ? "pointer" : "grab";
      }
    }

    function onClick(e) {
      if (moved) {
        moved = false;
        return;
      }
      const rect = canvas.getBoundingClientRect();
      showPlate(hit(e.clientX - rect.left, e.clientY - rect.top));
    }

    function onWheel(e) {
      e.preventDefault();
      dist = Math.max(1.6, Math.min(5.2, dist + (e.deltaY > 0 ? 0.18 : -0.18)));
    }

    function onKey(e) {
      const step = 0.09;
      if (e.key === "ArrowLeft") yaw -= step;
      else if (e.key === "ArrowRight") yaw += step;
      else if (e.key === "ArrowUp") pitch = Math.max(-1.15, pitch - step);
      else if (e.key === "ArrowDown") pitch = Math.min(1.15, pitch + step);
      else if (e.key === "Escape") showPlate(null);
      else return;
      e.preventDefault();
    }

    canvas.tabIndex = 0;
    canvas.addEventListener("pointerdown", onPointerDown);
    canvas.addEventListener("pointerup", onPointerUp);
    canvas.addEventListener("pointercancel", onPointerUp);
    canvas.addEventListener("pointermove", onPointerMove);
    canvas.addEventListener("click", onClick);
    canvas.addEventListener("wheel", onWheel, { passive: false });
    canvas.addEventListener("keydown", onKey);
    canvas.addEventListener("pointerleave", () => {
      hover = null;
    });

    resize();
    window.addEventListener("resize", resize);
    raf = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("pointerdown", onPointerDown);
      canvas.removeEventListener("pointerup", onPointerUp);
      canvas.removeEventListener("pointercancel", onPointerUp);
      canvas.removeEventListener("pointermove", onPointerMove);
      canvas.removeEventListener("click", onClick);
      canvas.removeEventListener("wheel", onWheel);
      canvas.removeEventListener("keydown", onKey);
      stop();
    };
  }

  window.ProbaSky = { mount, stop };
})();
