const stage = document.getElementById("stage");
const railStats = document.getElementById("rail-stats");
const OPEN_WHILE_DIAG = new Set(["diagnostic", "dict", "shot"]);
const LEGACY = {
  "/import": "/settings?s=text",
  "/text": "/settings?s=text",
  "/lesson": "/settings?s=lesson",
  "/queue": "/settings?s=queue",
  "/dict": "/settings?s=dict",
  "/gaps": "/settings?s=gaps",
  "/pack": "/settings?s=pack",
  "/growth": "/settings?s=growth",
  "/diagnostic": "/settings?s=diagnostic",
  "/shot": "/settings?s=shot",
};
const SETTINGS_CHILD = {
  text: () => renderImport(),
  shot: () => renderShot("/settings?s=shot"),
  lesson: () => renderLesson(),
  queue: () => renderQueue(),
  dict: () => renderDict("/settings?s=dict"),
  gaps: () => renderGaps(),
  pack: () => renderPack(),
  growth: () => renderGrowth(),
  diagnostic: () => renderDiagnostic(),
};

let snapshot = null;
let meta = { atlas: false, flavor: "tutor", app_name: "日本語学習アシスタント", brand_sub: "", rails: [] };
let captureTimer = null;
let skyOff = null;
let viewGen = 0;
let activeRoute = "/";
let catalogLevel = "N5";
let shotPasteOff = null;

const STATUS_RU = {
  tonight: "на этот вечер",
  queued: "в очереди — не сегодня",
  known: "уже умею",
  proposed: "черновик, пока не принято",
};

const PROV_RU = {
  teacher: "учитель",
  model: "разбор",
  self: "вы",
  dictionary: "словарь",
  textbook: "учебник",
  auto: "сверка",
};

function crumb(title) {
  return `<p class="crumb"><a href="#/settings" data-go="/settings">Настройки</a> · ${escapeHtml(title)}</p>`;
}

function setActive(dest) {
  let next = String(dest || "/").replace(/^#/, "");
  if (!next.startsWith("/")) next = "/" + next;
  const path = next.split("?")[0] || "/";
  if (meta.atlas) {
    if (path === "/settings" || path === "/zoom") next = "/dict";
    activeRoute = next;
    return;
  }
  if (LEGACY[next]) next = LEGACY[next];
  activeRoute = next;
}

function routePath() {
  return (activeRoute.split("?")[0] || "/") || "/";
}

function routeQuery(name) {
  const q = activeRoute.includes("?") ? activeRoute.slice(activeRoute.indexOf("?") + 1) : "";
  return new URLSearchParams(q).get(name);
}

function railKey() {
  const p = routePath();
  if (p === "/zoom") return "/zoom";
  if (p === "/giongo") return "/giongo";
  if (p === "/dict") return "/dict";
  if (p === "/settings") return "/settings";
  return "/";
}

function markRail() {
  const key = railKey();
  document.querySelectorAll(".rail nav a").forEach((a) => {
    a.classList.toggle("active", a.dataset.route === key);
  });
}

function syncUrl() {
  const want = "#" + activeRoute;
  try {
    history.replaceState(null, "", "/" + want);
  } catch (err) {
    location.hash = want;
  }
}

function go(dest) {
  setActive(dest);
  syncUrl();
  render();
}

function bootLocation() {
  const pathName = (location.pathname || "/").replace(/\/+$/, "") || "/";
  let hash = (location.hash || "").replace(/^#/, "");
  if (pathName !== "/" && pathName !== "/index.html" && !hash) {
    hash = LEGACY[pathName] || pathName;
  }
  setActive(hash || "/");
  syncUrl();
  markRail();
}

function route() {
  markRail();
  return routePath();
}

function applyChrome() {
  const brand = document.querySelector(".brand");
  const sub = document.querySelector(".brand-sub");
  if (brand) brand.textContent = meta.app_name || "";
  if (sub) sub.textContent = meta.brand_sub || "";
  document.title = meta.app_name || document.title;
  document.body.classList.toggle("atlas", Boolean(meta.atlas));
  const nav = document.querySelector(".rail nav");
  if (nav && meta.rails && meta.rails.length) {
    nav.innerHTML = meta.rails
      .map(
        (r) =>
          `<a href="#${escapeHtml(r.href || r.route)}" data-route="${escapeHtml(r.route)}" title="${escapeHtml(r.title || "")}">${escapeHtml(r.label)}</a>`
      )
      .join("");
  }
  markRail();
}

async function api(path, opts) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(opts && opts.headers) },
    ...opts,
  });
  if (!res.ok) throw new Error((await res.text()) || res.statusText);
  return res.json();
}

async function refresh() {
  snapshot = await api("/api/snapshot");
  if (meta.atlas) {
    railStats.textContent = "";
    return;
  }
  const h = snapshot.headline;
  const rate =
    h.pass_rate == null
      ? "после паузы ряда ещё нет"
      : `${Math.round(h.pass_rate * 100)}% с первой попытки после паузы`;
  const cap = snapshot.capture?.state || "idle";
  const analyzing = snapshot.capture?.analysis?.state === "running";
  const lines = [
    `Вечер: ${snapshot.tonight} проб · очередь ${snapshot.queued}`,
    rate,
  ];
  if (cap !== "idle" || analyzing) {
    const device = snapshot.compute?.device === "cuda" ? "GPU" : "CPU";
    lines.push(`Zoom: ${cap} · разбор ${device}`);
  }
  railStats.textContent = lines.join("\n");
}

function escapeHtml(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function glossLead(text) {
  return String(text || "").split(/\s*[·•・⋅]\s*/)[0];
}

function glossParagraphs(text) {
  const raw = String(text || "").trim();
  if (!raw) return "";
  const parts = raw.split(/\s*[·•・⋅]\s*/).map((s) => s.trim()).filter(Boolean);
  return (parts.length ? parts : [raw])
    .map((p) => `<p class="dict-gloss">${escapeHtml(p)}</p>`)
    .join("");
}

function stopSky() {
  if (skyOff) {
    skyOff();
    skyOff = null;
  } else if (window.ProbaSky) {
    window.ProbaSky.stop();
  }
}

function still(gen, path) {
  if (gen !== viewGen) return false;
  if (!path) return true;
  if (path === "/") return routePath() === "/";
  if (path === "/zoom") return routePath() === "/zoom";
  if (path === "/giongo") return routePath() === "/giongo";
  if (path === "/dict") return routePath() === "/dict";
  if (path === "/drill") return routePath() === "/drill";
  return activeRoute === path;
}

function render() {
  viewGen += 1;
  if (captureTimer) {
    clearInterval(captureTimer);
    captureTimer = null;
  }
  if (shotPasteOff) {
    shotPasteOff();
    shotPasteOff = null;
  }
  stopSky();
  stage.classList.remove("stage-ledger");
  markRail();
  const p = routePath();
  const s = routeQuery("s") || "";
  if (!meta.atlas && snapshot?.diagnostic_pending) {
    const allowed =
      (p === "/settings" && OPEN_WHILE_DIAG.has(s)) || p === "/giongo" || p === "/dict";
    if (!allowed) {
      if (activeRoute !== "/settings?s=diagnostic") go("/settings?s=diagnostic");
      return;
    }
  }
  if (p === "/giongo") {
    renderGiongo();
    return;
  }
  if (p === "/drill") {
    renderDrill();
    return;
  }
  if (p === "/dict") {
    renderDict("/dict");
    return;
  }
  if (p === "/zoom") {
    if (meta.atlas) {
      go("/");
      return;
    }
    renderZoom();
    return;
  }
  if (p === "/settings") {
    if (meta.atlas) {
      go("/dict");
      return;
    }
    const child = SETTINGS_CHILD[s];
    if (child) child();
    else renderSettingsHub();
    return;
  }
  renderNow();
}

function renderNow() {
  const nxt = snapshot?.next;
  if (nxt) {
    renderProbe(nxt);
    mountCatalogDrawer();
    return;
  }
  renderCatalog();
}

const BOOK_TO_LEVEL = {
  manabou1: "N5",
  manabou2: "N4",
  pea: "N5",
  giongo: "N4",
  kaiwa: "N3",
  pointo: "N3",
  kikitori: "N3",
  teksty: "N3",
  kanji: "N5",
};

function catalogLevelFromRoute() {
  const lv = (routeQuery("lv") || "").toUpperCase();
  if (["N5", "N4", "N3", "N2", "N1"].includes(lv)) return lv;
  const mapped = BOOK_TO_LEVEL[routeQuery("b") || ""];
  if (mapped) return mapped;
  return catalogLevel || "N5";
}

function pathMarkup(plan, compact) {
  if (meta.atlas) return "";
  const stones = (plan.path || [])
    .map((s) => {
      const cov =
        s.coverage === "pending" ? " pending" : s.coverage === "draft" ? " draft" : "";
      return `<button type="button" class="path-stone${cov}" data-topic="${escapeHtml(s.id)}" title="${escapeHtml(s.title)}">
          <span class="path-lv">${escapeHtml(s.level)}</span>
          <span class="path-title">${escapeHtml(s.title)}</span>
        </button>`;
    })
    .join("");
  if (!stones) {
    return `<p class="meta">На этой тропе нет пустых форм.</p>`;
  }
  const fill = compact
    ? ""
    : `<div class="row">
        <button class="btn" id="fill-path" type="button">Дополнить тропу (до ${plan.fill_cap || 7} черновиков)</button>
        <p class="meta" id="fill-ok"></p>
      </div>`;
  return `
    <div class="path-panel">
      <p class="col-label">Тропа</p>
      <div class="path-trail">${stones}</div>
      ${fill}
    </div>`;
}

function catalogHitLine(t) {
  if (meta.atlas) return "";
  const kind = t.kind || "grammar";
  if (kind === "listening") return `<p class="meta topic-kind">слух</p>`;
  if (kind === "conversation") return `<p class="meta topic-kind">разговор</p>`;
  if (kind === "vocab") return `<p class="meta topic-kind">連語</p>`;
  if (kind === "mimetics") return `<p class="meta topic-kind">擬音</p>`;
  if (kind === "reading") return `<p class="meta topic-kind">чтение</p>`;
  if (t.hits && t.hits.length) {
    return `<p class="meta">${t.hits
      .map((h) => `${escapeHtml(h.prompt_ja)} (${escapeHtml(STATUS_RU[h.status] || h.status)})`)
      .join(" · ")}</p>`;
  }
  return "";
}

const STATION_KIND = {
  listening: "слух",
  conversation: "разговор",
  mimetics: "擬音",
  reading: "чтение",
  vocab: "連語",
  grammar: "",
};

function stationMarkup(s) {
  const kindNote = STATION_KIND[s.kind] || STATION_KIND.grammar;
  const origin =
    s.example && s.example.origin === "course"
      ? "полка"
      : s.example
        ? "открытый пример"
        : "";
  const ex =
    s.example && !meta.atlas
      ? `<p class="ja-sm">${escapeHtml(s.example.prompt_ja)}</p>
       <p class="meta">${escapeHtml(s.example.prompt_hint)} · ${escapeHtml(s.example.gloss_ru)}</p>
       ${origin ? `<p class="meta">${escapeHtml(origin)}</p>` : ""}
       <form class="form-grid" id="station-drill">
         <label>Ответ
           <input id="station-answer" name="response" autocomplete="off" spellcheck="false" lang="ja" placeholder="латиница или кана" />
         </label>
         <button class="btn" type="submit">Проверить</button>
       </form>
       <p class="meta" id="station-verdict"></p>`
      : s.example
        ? `<p class="ja-sm">${escapeHtml(s.example.prompt_ja)}</p>
           <p class="meta">${escapeHtml(s.example.gloss_ru || "")}</p>`
        : kindNote
          ? `<p class="meta">${escapeHtml(kindNote)}</p>`
          : "";
  const giongo = s.giongo
    ? `<p class="col-label">擬音 в словаре</p>
       <div class="dict-chips">${(s.giongo.samples || []).map(dictChipWord).join("")}</div>
       <div class="row"><button type="button" class="btn" data-go="/giongo">Открыть 擬音</button></div>`
    : "";
  const yours = meta.atlas
    ? ""
    : (s.your_pairs || [])
        .map(
          (p) =>
            `${escapeHtml(STATUS_RU[p.status] || p.status)} · ${escapeHtml(PROV_RU[p.provenance] || p.provenance)}`
        )
        .join(" · ");
  const dueNote = "";
  const hits =
    meta.atlas || !(s.hits || []).length
      ? ""
      : `<p class="meta">${s.hits
          .map((h) => `${escapeHtml(h.prompt_ja)} (${escapeHtml(STATUS_RU[h.status] || h.status)})`)
          .join(" · ")}</p>`;
  const lex = (s.lexicon || [])
    .map((h) => {
      if (h.kind === "kanji") {
        return `<article class="item"><div class="kanji-stage kanji-stage-sm" data-stroke="${escapeHtml(h.head)}"></div>
          <p class="ja-sm">${escapeHtml(h.head)}</p>
          <p class="meta">${escapeHtml(h.gloss_ru || "")}</p></article>`;
      }
      return `<article class="item"><p class="ja-sm">${escapeHtml(h.head)} · ${escapeHtml(h.kana || "")}</p>
        <p class="meta">${escapeHtml(h.gloss_ru || "")}</p></article>`;
    })
    .join("");
  return `
    ${dueNote}
    <p>${escapeHtml(s.blurb || "")}</p>
    ${kindNote ? `<p class="meta">${escapeHtml(kindNote)}</p>` : ""}
    ${s.from_book ? `<p class="meta">${escapeHtml(s.from_book)}</p>` : ""}
    ${s.example ? `<p class="col-label">Пример</p>` : ""}
    ${ex}
    ${yours ? `<p class="meta">${yours}</p>` : ""}
    ${hits}
    ${lex ? `<p class="col-label">Лексика</p><div class="list">${lex}</div>` : ""}
    ${giongo}`;
}

async function openStation(id) {
  if (!id) return;
  try {
    const s = await api("/api/station?id=" + encodeURIComponent(id));
    openSheet({
      stamp: s.level || "記",
      title: s.title || "Стоянка",
      html: stationMarkup(s),
      action: snapshot?.next ? "К форме" : "Закрыть",
      onAction: () => {
        if (snapshot?.next) document.getElementById("answer")?.focus();
      },
    });
    const drill = document.getElementById("station-drill");
    if (drill) {
      wireIme(document.getElementById("sheet-body"));
      document.getElementById("station-answer")?.focus();
      drill.onsubmit = async (e) => {
        e.preventDefault();
        const note = document.getElementById("station-verdict");
        try {
          const r = await api("/api/station/check", {
            method: "POST",
            body: JSON.stringify({
              id: s.id,
              response: commitKana(document.getElementById("station-answer")?.value || ""),
            }),
          });
          if (!note) return;
          if (r.outcome === "pass") {
            note.textContent = `совпало · ${r.expected}`;
          } else {
            note.textContent = `не совпало · ${r.expected || "—"}`;
          }
        } catch (err) {
          if (note) note.textContent = "сверка не открылась";
        }
      };
    }
    if (window.ProbaStrokes) {
      document.querySelectorAll("#sheet-body [data-stroke]").forEach((el) => {
        window.ProbaStrokes.playPlate(el, el.dataset.stroke);
      });
    }
  } catch (err) {
    openSheet({
      stamp: "記",
      title: "Стоянка",
      html: "<p>Справочник не открылся.</p>",
      action: "Закрыть",
    });
  }
}

function inkWell(label, done, total, seen) {
  const t = Number(total) || 0;
  const d = Number(done) || 0;
  const s = Number(seen) || 0;
  const pct = t ? Math.min(100, Math.round((Math.max(d, s) / t) * 100)) : 0;
  return `<div class="ink-well" title="${escapeHtml(label)}: отлично ${d} из ${t}">
    <span class="ink-fill" style="height:${pct}%"></span>
    <span class="ink-label">${escapeHtml(label)}</span>
    <span class="ink-count">${d}/${t}</span>
  </div>`;
}

function notebookMarkup(st) {
  if (!st || !st.level) {
    return `
      <section class="notebook notebook-pick" aria-label="Уровень закрепления">
        <p class="col-label">тетрадь</p>
        <h2 class="notebook-title">Какой уровень закреплять?</h2>
        <p class="lede">Один раз. Задания не выше этой отметки. Справочник N5–N1 по-прежнему можно смотреть любой. Это не экзамен JLPT.</p>
        <div class="level-pick">
          ${(st && st.levels ? st.levels : ["N5", "N4", "N3", "N2", "N1"])
            .map((lv) => `<button type="button" class="level-pick-stamp" data-drill-lv="${lv}">${lv}</button>`)
            .join("")}
        </div>
      </section>`;
  }
  const p = st.progress || {};
  const offer = st.offer
    ? `<div class="offer-plate">
        <p class="ja-sm">手帳 ${escapeHtml(st.level)}</p>
        <p>Тетрадь этого уровня закрыта. Это справочник приложения, не сертификат. Открыть ${escapeHtml(st.offer)}?</p>
        <div class="row">
          <button type="button" class="btn btn-shu" data-drill-lv="${escapeHtml(st.offer)}" data-drill-confirm="1">Открыть ${escapeHtml(st.offer)}</button>
          <button type="button" class="btn" data-go="/drill">Остаться</button>
        </div>
      </div>`
    : "";
  return `
    <section class="notebook" aria-label="Тетрадь ${escapeHtml(st.level)}">
      <div class="notebook-head">
        <div>
          <p class="col-label">тетрадь ${escapeHtml(st.level)}</p>
          <p class="meta">${escapeHtml(st.lede || "")}</p>
        </div>
        <button type="button" class="btn btn-shu" data-go="/drill">Открыть тетрадь</button>
      </div>
      <div class="ink-row">
        ${inkWell("слова", p.words && p.words.done, p.words && p.words.total, p.words && p.words.seen)}
        ${inkWell("грамматика", p.grammar && p.grammar.done, p.grammar && p.grammar.total, p.grammar && p.grammar.seen)}
        ${inkWell("кандзи", p.kanji && p.kanji.done, p.kanji && p.kanji.total, p.kanji && p.kanji.seen)}
      </div>
      ${offer}
    </section>`;
}

async function pickDrillLevel(lv, confirm) {
  try {
    const r = await api("/api/drill/level", {
      method: "POST",
      body: JSON.stringify({ level: lv, confirm: Boolean(confirm) }),
    });
    if (r.need_confirm) {
      openSheet({
        stamp: "級",
        title: "Сменить тетрадь?",
        html: `<p>${escapeHtml(r.message || "")}</p>`,
        action: "Сменить",
        onAction: () => pickDrillLevel(lv, true),
      });
      return r;
    }
    catalogLevel = lv;
    if (routePath() === "/drill") renderDrill();
    else go("/?lv=" + lv);
    return r;
  } catch (err) {
    return null;
  }
}

function bindNotebook(root) {
  root.querySelectorAll("[data-drill-lv]").forEach((btn) => {
    btn.onclick = (e) => {
      e.preventDefault();
      pickDrillLevel(btn.dataset.drillLv, btn.dataset.drillConfirm === "1");
    };
  });
}

function fudaBoard(task) {
  const left = (task.left || [])
    .map((x) => `<button type="button" class="fuda fuda-ja" data-fuda="L" data-id="${escapeHtml(x.id)}">${escapeHtml(x.text)}</button>`)
    .join("");
  const right = (task.right || [])
    .map((x) => `<button type="button" class="fuda fuda-ru" data-fuda="R" data-id="${escapeHtml(x.id)}">${escapeHtml(x.text)}</button>`)
    .join("");
  return `
    <div class="fuda-board" data-sid="${escapeHtml(task.id)}">
      <div class="fuda-col" data-side="L">${left}</div>
      <div class="fuda-thread" aria-hidden="true"></div>
      <div class="fuda-col" data-side="R">${right}</div>
    </div>
    <div class="row"><button type="button" class="btn btn-shu" id="fuda-check">Проверить</button></div>
    <p class="meta" id="fuda-note">Нажмите слева, затем справа. Проверка — когда все пары собраны.</p>`;
}

function bindFuda(root, task) {
  const pairs = {};
  let left = null;
  const board = root.querySelector(".fuda-board");
  const note = root.querySelector("#fuda-note");
  const mark = () => {
    root.querySelectorAll(".fuda").forEach((el) => {
      const side = el.dataset.fuda;
      const id = el.dataset.id;
      el.classList.toggle("on", side === "L" ? left === id : false);
      el.classList.toggle("lock", side === "L" ? Boolean(pairs[id]) : Object.values(pairs).includes(id));
    });
  };
  board?.addEventListener("click", (e) => {
    const btn = e.target.closest(".fuda");
    if (!btn || btn.classList.contains("ok") || btn.classList.contains("miss")) return;
    if (btn.dataset.fuda === "L") {
      left = btn.dataset.id;
      mark();
      return;
    }
    if (!left) {
      if (note) note.textContent = "Сначала знак или слово слева.";
      return;
    }
    Object.keys(pairs).forEach((k) => {
      if (pairs[k] === btn.dataset.id) delete pairs[k];
    });
    pairs[left] = btn.dataset.id;
    left = null;
    mark();
    if (note) note.textContent = `собрано ${Object.keys(pairs).length} из ${(task.left || []).length}`;
  });
  root.querySelector("#fuda-check")?.addEventListener("click", async () => {
    const need = (task.left || []).length;
    if (Object.keys(pairs).length < need) {
      if (note) note.textContent = "Соберите все пары, затем проверьте.";
      return;
    }
    const r = await api("/api/drill/check", {
      method: "POST",
      body: JSON.stringify({ id: task.id, pairs }),
    });
    paintDrillVerdict(r, task);
  });
}

function paintDrillVerdict(r, task) {
  const stamp = r.passed === r.total ? "通" : "不";
  if (task.kind === "read_word") {
    const one = (r.results || [])[0] || {};
    openSheet({
      stamp,
      fail: r.passed !== r.total,
      title: r.passed === r.total ? "Чтение совпало" : "Не совпало",
      html: `<p class="ja-sm">${escapeHtml(task.surface || "")}</p>
        <p>Ваш звук «${escapeHtml(one.reading || "∅")}» · ключ «${escapeHtml(one.expected || "")}»</p>
        <p class="meta">Это тетрадь справочника, не проба с урока.</p>`,
      action: "Дальше",
      onAction: () => renderDrill(),
    });
    return;
  }
  const byLeft = Object.fromEntries((r.results || []).map((x) => [x.left, x]));
  document.querySelectorAll(".fuda-ja").forEach((el) => {
    const row = byLeft[el.dataset.id];
    if (!row) return;
    el.classList.add(row.outcome === "pass" ? "ok" : "miss");
    el.classList.remove("on");
  });
  document.querySelectorAll(".fuda-ru").forEach((el) => {
    const hit = (r.results || []).find((x) => x.right === el.dataset.id || x.got === el.dataset.id);
    if (!hit) return;
    if (hit.right === el.dataset.id) el.classList.add(hit.outcome === "pass" ? "ok" : "key");
    if (hit.got === el.dataset.id && hit.outcome === "fail") el.classList.add("miss");
  });
  const check = document.getElementById("fuda-check");
  if (check) {
    check.textContent = "Дальше";
    check.onclick = () => renderDrill();
  }
  const note = document.getElementById("fuda-note");
  if (note) {
    note.textContent =
      r.passed === r.total
        ? `все ${r.total} · отлично зачтётся после паузы`
        : `совпало ${r.passed} из ${r.total}`;
  }
}

async function renderDrill() {
  const gen = viewGen;
  if (!meta.atlas && snapshot?.next) {
    stage.innerHTML = `
      <h1>Тетрадь</h1>
      <p class="lede">Сначала форма с занятия. Закрепление подождёт.</p>
      <div class="row"><a class="btn btn-shu" data-go="/" href="#/">К пробе</a></div>`;
    return;
  }
  stage.classList.add("stage-ledger");
  stage.innerHTML = `<p class="empty">Загрузка…</p>`;
  let st;
  try {
    st = await api("/api/drill");
  } catch (err) {
    if (!still(gen, "/drill")) return;
    stage.innerHTML = `<p class="err">Тетрадь не открылась.</p>`;
    return;
  }
  if (!still(gen, "/drill")) return;
  if (!st.level) {
    stage.innerHTML = `<h1>Тетрадь</h1>${notebookMarkup(st)}`;
    bindNotebook(stage);
    return;
  }
  if (st.complete) {
    stage.innerHTML = `<h1>Тетрадь ${escapeHtml(st.level)}</h1>${notebookMarkup(st)}
      <p class="meta"><a data-go="/" href="#/">К темам</a></p>`;
    bindNotebook(stage);
    return;
  }
  let nxt;
  try {
    nxt = await api("/api/drill/next", { method: "POST", body: "{}" });
  } catch (err) {
    if (!still(gen, "/drill")) return;
    stage.innerHTML = `<p class="err">Задание не собралось.</p>`;
    return;
  }
  if (!still(gen, "/drill")) return;
  if (nxt.need_level) {
    stage.innerHTML = `<h1>Тетрадь</h1>${notebookMarkup(nxt.status || st)}`;
    bindNotebook(stage);
    return;
  }
  if (nxt.idle || !nxt.task) {
    stage.innerHTML = `
      <h1>Тетрадь ${escapeHtml(st.level)}</h1>
      ${notebookMarkup(nxt.status || st)}
      <p class="lede">Сейчас спрашивать нечего — пауза ещё держит. Придёт уведомление.</p>
      <p class="meta"><a data-go="/" href="#/">К темам</a></p>`;
    bindNotebook(stage);
    return;
  }
  const task = nxt.task;
  const body =
    task.kind === "read_word"
      ? `<section class="yoshi" aria-label="чтение">
          <p class="ja">${escapeHtml(task.surface || "")}</p>
          <input id="drill-answer" type="text" autocomplete="off" spellcheck="false" lang="ja" aria-label="чтение" />
          <p class="ime-hint">itte → いって</p>
        </section>
        <div class="row"><button type="button" class="btn btn-shu" id="drill-read">Проверить</button></div>`
      : fudaBoard(task);
  stage.innerHTML = `
    <p class="crumb"><a data-go="/" href="#/">Темы</a> · тетрадь ${escapeHtml(st.level)}</p>
    <h1>${escapeHtml(task.prompt || "Закрепление")}</h1>
    <p class="lede">Не выше ${escapeHtml(st.level)}. Не проба с урока.</p>
    ${body}`;
  if (task.kind === "read_word") {
    wireIme(stage);
    document.getElementById("drill-answer")?.focus();
    const run = async () => {
      const r = await api("/api/drill/check", {
        method: "POST",
        body: JSON.stringify({
          id: task.id,
          response: commitKana(document.getElementById("drill-answer")?.value || ""),
        }),
      });
      paintDrillVerdict(r, task);
    };
    document.getElementById("drill-read").onclick = run;
    document.getElementById("drill-answer")?.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        run();
      }
    });
  } else {
    bindFuda(stage, task);
  }
}

function catalogMarkup(data, { pullBtn = "", banners = "", compact = false, plan = {}, notebook = "" } = {}) {
  const topics = (data.topics || [])
    .map(
      (t) => `
      <button type="button" class="topic-slip topic-${escapeHtml(t.kind || "grammar")}" data-topic="${escapeHtml(t.id)}">
        <p class="topic-title">${escapeHtml(t.title)}</p>
        <p class="meta">${escapeHtml(t.blurb)}</p>
        ${t.from_book ? `<p class="meta">${escapeHtml(t.from_book)}</p>` : ""}
        ${catalogHitLine(t)}
      </button>`
    )
    .join("");
  const kanji = (data.kanji || [])
    .map(
      (k) =>
        `<button type="button" class="kanji-cell${k.in_claims ? " in-claim" : ""}" data-c="${escapeHtml(k.c)}" aria-label="${escapeHtml(k.c)}">
          <span class="kanji-glyph">${escapeHtml(k.c)}</span>
          <span class="kanji-write" aria-hidden="true"></span>
        </button>`
    )
    .join("");
  return `
    ${banners}
    <div class="ledger-head">
      <div>
        ${compact ? "" : "<h1>Темы</h1>"}
        ${compact || !data.lede ? "" : `<p class="lede">${escapeHtml(data.lede)}</p>`}
      </div>
      <div class="level-stamps" role="tablist" aria-label="Уровень">
        ${(data.levels || ["N5", "N4", "N3", "N2", "N1"])
          .map(
            (lv) =>
              `<button type="button" role="tab" class="level-stamp${lv === data.level ? " on" : ""}${lv === (notebook && notebook.level) ? " study" : ""}" data-lv="${lv}" aria-selected="${lv === data.level}">${lv}</button>`
          )
          .join("")}
      </div>
    </div>
    ${compact ? "" : notebookMarkup(notebook)}
    ${pathMarkup(plan, compact)}
    ${pullBtn ? `<div class="row">${pullBtn}</div>` : ""}
    <div class="ledger">
      <div class="topic-col">
        <p class="col-label">Грамматика ${escapeHtml(data.level || "")}</p>
        <div class="topic-list">${topics}</div>
      </div>
      <aside class="kanji-col">
        <p class="col-label">Кандзи ${escapeHtml(data.level || "")}</p>
        <div class="kanji-koushi">${kanji}</div>
        <aside class="kanji-plate" id="kanji-plate" hidden></aside>
      </aside>
    </div>`;
}

function bindCatalog(root, data) {
  root.querySelectorAll("[data-lv]").forEach((btn) => {
    btn.onclick = () => {
      catalogLevel = btn.dataset.lv;
      if (snapshot?.next) paintCatalog(root, { full: false });
      else go("/?lv=" + catalogLevel);
    };
  });
  const byChar = Object.fromEntries((data.kanji || []).map((k) => [k.c, k]));
  root.querySelectorAll(".kanji-cell").forEach((btn) => {
    btn.onclick = () => {
      const k = byChar[btn.dataset.c];
      if (!k) return;
      openDictKanji(k.c);
    };
  });
  root.querySelectorAll("[data-topic]").forEach((btn) => {
    btn.onclick = () => openStation(btn.dataset.topic);
  });
  root.querySelector("#fill-path")?.addEventListener("click", async () => {
    const note = root.querySelector("#fill-ok");
    try {
      const r = await api("/api/plan/fill", {
        method: "POST",
        body: JSON.stringify({ text: "", level: catalogLevelFromRoute() }),
      });
      if (note) note.textContent = `черновиков ${r.count}. Примите в Настройки → Черновики.`;
      await paintCatalog(root, { full: !snapshot?.next });
    } catch (err) {
      if (note) note.textContent = "тропа не дополнилась";
    }
  });
  root.querySelector("#ack")?.addEventListener("click", ackNudge);
  root.querySelector("#accept-zoom")?.addEventListener("click", acceptZoomForms);
  root.querySelector("#pull-queued")?.addEventListener("click", pullQueued);
}

async function paintCatalog(root, { full }) {
  const gen = viewGen;
  const level = (catalogLevel || "N5").toUpperCase();
  catalogLevel = level;
  let data;
  let plan = {};
  let notebook = {};
  try {
    data = await api("/api/jlpt?level=" + encodeURIComponent(level));
    plan = await api("/api/plan?level=" + encodeURIComponent(level));
  } catch (err) {
    if (!still(gen, "/")) return;
    root.insertAdjacentHTML("beforeend", `<p class="err">Справочник не открылся.</p>`);
    return;
  }
  try {
    notebook = await api("/api/drill");
  } catch (err) {
    notebook = {};
  }
  if (!still(gen, "/")) return;
  const queued = meta.atlas ? 0 : snapshot?.queued || 0;
  const pulled = snapshot?.early_pull_used;
  const pullBtn =
    full && !meta.atlas
      ? queued && !pulled
        ? `<button class="btn" id="pull-queued" type="button">Одну раньше срока (раз за вечер)</button>`
        : queued && pulled
          ? `<p class="meta">На сегодня уже одну раньше срока. Остальное — когда наступит срок.</p>`
          : ""
      : "";
  const banners =
    full && !meta.atlas
      ? `${snapshot?.capture?.nudge
          ? `<div class="banner">Zoom уже кончился.
              <button class="btn" id="ack">Понял</button></div>`
          : ""}
        ${zoomAcceptBanner()}`
      : "";
  if (full) {
    stage.classList.add("stage-ledger");
    root.innerHTML = catalogMarkup(data, { pullBtn, banners, plan, notebook });
  } else {
    root.innerHTML = catalogMarkup(data, { compact: true, plan, notebook });
  }
  bindCatalog(root, data);
  bindNotebook(root);
  if (window.ProbaStrokes) {
    window.ProbaStrokes.attachGrid(root, data.level);
  }
}

function mountCatalogDrawer() {
  const drawer = document.createElement("details");
  drawer.className = "how catalog-drawer";
  drawer.innerHTML = `<summary>Справочник N5–N1</summary><div class="catalog-mount" id="catalog-root"></div>`;
  stage.appendChild(drawer);
  drawer.addEventListener("toggle", () => {
    if (drawer.open && !drawer.dataset.loaded) {
      drawer.dataset.loaded = "1";
      paintCatalog(document.getElementById("catalog-root"), { full: false });
    }
  });
}

async function renderCatalog() {
  const gen = viewGen;
  catalogLevel = catalogLevelFromRoute();
  stage.classList.add("stage-ledger");
  stage.innerHTML = `<p class="empty">Загрузка…</p>`;
  await paintCatalog(stage, { full: true });
  if (!still(gen, "/")) return;
}

function renderSettingsHub() {
  stage.innerHTML = `
    <h1>Настройки</h1>
    <div class="settings-list">
      ${[
        ["diagnostic", "Срез", ""],
        ["text", "Текст или PDF", ""],
        ["shot", "Снимок", ""],
        ["lesson", "Занятие вручную", ""],
        ["queue", "Очередь", ""],
        ["dict", "Словарь", ""],
        ["gaps", "Черновики", ""],
        ["pack", "К учителю", ""],
        ["growth", "После паузы", ""],
      ]
        .map(
          ([id, title, note]) =>
            `<button type="button" class="settings-item" data-go="/settings?s=${id}">
              <span>${title}</span>
              ${note ? `<span class="meta">${note}</span>` : ""}
            </button>`
        )
        .join("")}
    </div>`;
}

async function acceptZoomForms() {
  const zp = snapshot?.zoom_proposed;
  if (!zp?.source_event_id) return;
  await api("/api/proposed/accept-source", {
    method: "POST",
    body: JSON.stringify({ id: zp.source_event_id, accept: true }),
  });
  await refresh();
  go("/");
}

function zoomAcceptBanner() {
  const zp = snapshot?.zoom_proposed;
  if (!zp) return "";
  return `<div class="banner">С последнего Zoom: ${zp.proposed} форм.
    <button class="btn btn-shu" id="accept-zoom">В пробы</button></div>`;
}

async function ackNudge() {
  await api("/api/capture", {
    method: "POST",
    body: JSON.stringify({ action: "nudge-ack" }),
  });
  await refresh();
  render();
}

async function pullQueued() {
  try {
    await api("/api/probes/pull-queued", { method: "POST", body: "{}" });
    await refresh();
    go("/");
  } catch (err) {
    stage.insertAdjacentHTML(
      "afterbegin",
      `<p class="err">На сегодня уже одну раньше срока — или в очереди пусто.</p>`
    );
  }
}

let sheetOnClose = null;

function dismissSheet() {
  if (document.getElementById("veil")?.hidden) return;
  const btn = document.querySelector("#sheet-actions .btn-shu");
  if (btn) {
    btn.click();
    return;
  }
  const fn = sheetOnClose;
  closeSheet();
  if (typeof fn === "function") fn();
}

function closeSheet() {
  if (window.ProbaStrokes && window.ProbaStrokes.stopPlates) {
    window.ProbaStrokes.stopPlates();
  }
  sheetOnClose = null;
  const veil = document.getElementById("veil");
  if (veil) veil.hidden = true;
  const sheet = document.querySelector("#veil .sheet");
  sheet?.classList.remove("sheet-dict");
}

function openSheet({ stamp, title, html, action, onAction, fail, wide, back }) {
  const veil = document.getElementById("veil");
  const sheet = document.querySelector("#veil .sheet");
  sheet?.classList.toggle("sheet-dict", Boolean(wide));
  sheetOnClose = onAction || null;
  const stampEl = document.getElementById("sheet-stamp");
  stampEl.textContent = stamp || "";
  stampEl.classList.toggle("fail", Boolean(fail));
  document.getElementById("sheet-title").textContent = title || "";
  document.getElementById("sheet-body").innerHTML = html || "";
  const actions = document.getElementById("sheet-actions");
  actions.innerHTML = "";
  if (typeof back === "function") {
    const backBtn = document.createElement("button");
    backBtn.className = "btn";
    backBtn.type = "button";
    backBtn.textContent = "Назад";
    backBtn.onclick = () => back();
    actions.appendChild(backBtn);
  }
  if (action) {
    const btn = document.createElement("button");
    btn.className = "btn btn-shu";
    btn.type = "button";
    btn.textContent = action;
    btn.onclick = () => {
      closeSheet();
      if (typeof onAction === "function") onAction();
    };
    actions.appendChild(btn);
  }
  actions.hidden = !actions.childElementCount;
  veil.hidden = false;
  const focusBtn = actions.querySelector(".btn-shu") || actions.querySelector(".btn");
  if (focusBtn) focusBtn.focus();
  else sheet?.focus();
}

let dictStack = [];

function dictCloseLabel() {
  return snapshot?.next ? "К форме" : "Закрыть";
}

function dictOnClose() {
  if (snapshot?.next) document.getElementById("answer")?.focus();
}

function dictChipKanji(card) {
  return `<button type="button" class="dict-chip" data-open-kanji="${escapeHtml(card.head)}">
    <span class="dict-chip-ja">${escapeHtml(card.head)}</span>
    <span class="dict-chip-ru">${escapeHtml(glossLead(card.gloss_ru || ""))}</span>
  </button>`;
}

function dictChipWord(w) {
  return `<button type="button" class="dict-chip" data-open-word="${escapeHtml(w.head)}">
    <span class="dict-chip-ja">${escapeHtml(w.head)}</span>
    <span class="dict-chip-kana">${escapeHtml(w.kana || "")}</span>
    <span class="dict-chip-ru">${escapeHtml(glossLead(w.gloss_ru || w.gloss || ""))}</span>
  </button>`;
}

function dictReadings(page) {
  return `<div class="dict-read">
    ${page.on ? `<p class="dict-on"><span class="dict-lbl">音</span>${escapeHtml(page.on)}</p>` : ""}
    ${page.kun ? `<p class="dict-kun"><span class="dict-lbl">訓</span>${escapeHtml(page.kun)}</p>` : ""}
    ${glossParagraphs(page.gloss_ru || "")}
  </div>`;
}

function bindDictNav() {
  const body = document.getElementById("sheet-body");
  if (!body) return;
  body.onclick = (e) => {
    const k = e.target.closest("[data-open-kanji]");
    if (k) {
      e.preventDefault();
      showDict({ kind: "kanji", id: k.dataset.openKanji });
      return;
    }
    const r = e.target.closest("[data-open-radical]");
    if (r) {
      e.preventDefault();
      showDict({ kind: "radical", id: r.dataset.openRadical });
      return;
    }
    const w = e.target.closest("[data-open-word]");
    if (w) {
      e.preventDefault();
      showDict({ kind: "word", id: w.dataset.openWord });
    }
  };
}

function paintDictPage(page) {
  let html = "";
  let stamp = "記";
  let title = page.head || "";
  if (page.kind === "kanji") {
    stamp = page.head || "字";
    const compounds = page.compounds || [];
    const siblings = page.siblings || [];
    html = `
      <div class="kanji-stage" data-stroke-host data-dict-split></div>
      ${dictReadings(page)}
      <div data-stroke-chrome></div>
      ${
        page.radical
          ? `<p class="dict-bushu">部首
              <button type="button" class="dict-inline" data-open-radical="${escapeHtml(page.radical)}">${escapeHtml(page.radical)}</button>
              ${page.radical_ru ? " · " + escapeHtml(page.radical_ru) : ""}</p>`
          : ""
      }
      <div class="dict-chips" data-dict-parts></div>
      <p class="col-label">слова</p>
      <div class="dict-chips">${compounds.map(dictChipWord).join("") || `<p class="meta">в этом словаре нет составных с этим знаком</p>`}</div>
      ${page.compounds_more ? `<p class="meta">ещё ${page.compounds_more}</p>` : ""}
      <p class="col-label">тот же 部首</p>
      <div class="dict-chips">${siblings.map(dictChipKanji).join("") || `<p class="meta">нет соседних знаков в справочнике</p>`}</div>`;
  } else if (page.kind === "radical") {
    stamp = "部";
    title = `部首 ${page.head || ""}`;
    const kanji = page.kanji || [];
    html = `
      <div class="kanji-stage" data-stroke-host></div>
      <p class="dict-gloss">${escapeHtml(page.gloss_ru || "")}</p>
      <div data-stroke-chrome></div>
      <p class="col-label">знаки с этим 部首</p>
      <div class="dict-chips">${kanji.map(dictChipKanji).join("") || `<p class="meta">в справочнике N5–N1 пусто</p>`}</div>`;
  } else if (page.kind === "word") {
    stamp = "語";
    const forms = page.forms || [];
    const kanji = page.kanji || [];
    html = `
      <p class="dict-kana">${escapeHtml(page.kana || "")}</p>
      ${glossParagraphs(page.gloss_ru || "")}
      ${
        kanji.length
          ? `<p class="col-label">знаки</p><div class="dict-chips">${kanji.map(dictChipKanji).join("")}</div>`
          : ""
      }
      ${
        forms.length
          ? `<p class="col-label">формы</p>
             <div class="dict-forms">${forms
               .map(
                 (f) => `<article class="dict-form">
                   <p class="dict-form-ja">${escapeHtml(f.surface)}${f.kana ? ` · ${escapeHtml(f.kana)}` : ""}</p>
                   <p class="dict-form-ru">${escapeHtml(f.gloss_ru || f.hint || "")}</p>
                 </article>`
               )
               .join("")}</div>`
          : ""
      }`;
  } else if (page.kind === "mimetic") {
    stamp = "擬";
    const neighbors = page.neighbors || [];
    const gloss = page.gloss_ru || page.gloss || "";
    html = `
      <p class="dict-kana">${escapeHtml(page.kana || page.head || "")}</p>
      ${glossParagraphs(gloss)}
      ${
        neighbors.length
          ? `<p class="col-label">тот же ряд</p><div class="dict-chips">${neighbors.map(dictChipWord).join("")}</div>`
          : ""
      }`;
  }
  openSheet({
    stamp,
    title,
    html,
    wide: true,
    onAction: dictOnClose,
    back: dictStack.length > 1 ? dictBack : null,
  });
  bindDictNav();
  if (window.ProbaStrokes) {
    const host = document.querySelector("#sheet-body [data-stroke-host]");
    if (host && page.head) {
      window.ProbaStrokes.playPlate(host, page.head, { parts: page.parts || [] });
    }
  }
}

function dictBack() {
  dictStack.pop();
  const prev = dictStack[dictStack.length - 1];
  if (!prev) {
    closeSheet();
    dictOnClose();
    return;
  }
  showDict(prev, { push: false });
}

async function showDict(ref, { push = true } = {}) {
  if (!ref || !ref.kind || !ref.id) return;
  if (push) dictStack.push(ref);
  try {
    let page;
    if (ref.kind === "kanji") {
      page = await api("/api/kanji?c=" + encodeURIComponent(ref.id));
    } else if (ref.kind === "radical") {
      page = await api("/api/radical?r=" + encodeURIComponent(ref.id));
    } else {
      page = await api("/api/word?q=" + encodeURIComponent(ref.id));
    }
    paintDictPage(page);
  } catch (err) {
    openSheet({
      stamp: "記",
      title: "Справочник",
      html: "<p>Карточка не открылась.</p>",
      action: dictCloseLabel(),
      onAction: dictOnClose,
      wide: true,
      back: dictStack.length > 1 ? dictBack : null,
    });
  }
}

function openDictKanji(ch) {
  dictStack = [];
  return showDict({ kind: "kanji", id: ch });
}

function openDictWord(head) {
  dictStack = [];
  return showDict({ kind: "word", id: head });
}

function probeCue(claim) {
  if (claim.cue_leaks_key) {
    return {
      ja: "___",
      hint: claim.prompt_hint || "произведите форму, как на уроке",
    };
  }
  return { ja: claim.prompt_ja, hint: claim.prompt_hint };
}

function commitKana(value) {
  if (window.ProbaRomaji && window.ProbaRomaji.romajiToHiragana) {
    return window.ProbaRomaji.romajiToHiragana(value || "", true);
  }
  return value || "";
}

function wireIme(root) {
  if (!window.ProbaRomaji) return;
  (root || document).querySelectorAll("#answer, input[name='ja'], input[name='ex'], input[name='q']").forEach((el) => {
    window.ProbaRomaji.bind(el);
  });
}

function renderProbe(claim, revealed = false, stamp = "", draft = "", verdict = null) {
  const cue = probeCue(claim);
  const key = revealed
    ? `<div class="key">
        <p><strong>${verdict && verdict.outcome === "pass" ? "Совпало по чтению" : "Не совпало"}</strong></p>
        <p class="ja-sm">${escapeHtml(claim.expected)}</p>
        <p>${escapeHtml(claim.gloss_ru || "")}</p>
        <p class="grade-help">Ваш звук «${escapeHtml(verdict?.reading || "∅")}» · ключ «${escapeHtml(verdict?.expected_reading || "")}».</p>
      </div>`
    : "";
  const hanko = stamp ? `<div class="hanko" aria-hidden="true">${stamp}</div>` : "";
  const grade = revealed
    ? `<p class="meta">Записано как ${escapeHtml(verdict?.outcome || "")}. Дальше — следующая проба.</p>`
    : "";

  const banner = [
    snapshot?.capture?.nudge
      ? `<div class="banner">После Zoom сначала эта форма.</div>`
      : "",
    zoomAcceptBanner(),
  ].join("");
  const nextBtn = revealed
    ? `<div class="row"><button class="btn btn-shu" id="next-form" type="button">Следующая форма</button></div>`
    : "";

  stage.innerHTML = `
    ${banner}
    <h1>Напишите форму</h1>
    <p class="lede">Латиница станет каной.</p>
    <section class="yoshi" aria-label="日本語学習アシスタント">
      <p class="ja">${escapeHtml(cue.ja)}</p>
      <p class="hint">${escapeHtml(cue.hint || "")}</p>
      <input id="answer" type="text" autocomplete="off" spellcheck="false" lang="ja" aria-label="Ваш ответ латиницей или каной" ${revealed ? "readonly" : ""} />
      <p class="ime-hint">itte → いって · ha → は</p>
      ${key}
      ${hanko}
    </section>
    ${
      revealed
        ? grade
        : `<div class="confidence" role="group" aria-label="Уверенность">
        <button type="button" class="btn" data-conf="0">Не уверен</button>
        <button type="button" class="btn btn-shu" data-conf="0.5">Так себе</button>
        <button type="button" class="btn" data-conf="1">Уверен</button>
      </div>`
    }
    ${nextBtn}`;

  const input = document.getElementById("answer");
  if (input) {
    input.value = draft;
    if (!revealed) {
      wireIme(stage);
      input.focus();
    }
  }
  let busy = false;
  const runCheck = async (confidence) => {
    if (busy || revealed) return;
    if (typeof confidence !== "number") return;
    busy = true;
    stage.querySelectorAll("[data-conf]").forEach((b) => {
      b.disabled = true;
    });
    const raw = commitKana(document.getElementById("answer")?.value || "");
    const result = await api("/api/probes", {
      method: "POST",
      body: JSON.stringify({
        claim_id: claim.id,
        response: raw,
        confidence,
        kind: "production",
      }),
    });
    openSheet({
      stamp: result.outcome === "pass" ? "通" : "不",
      fail: result.outcome !== "pass",
      title: result.outcome === "pass" ? "Совпало по чтению" : "Не совпало",
      html: `<p class="ja-sm">${escapeHtml(claim.expected)}</p>
        <p>Ваш звук «${escapeHtml(result.reading || "∅")}» · ключ «${escapeHtml(result.expected_reading || "")}».</p>
        <p>${escapeHtml(claim.gloss_ru || "")}</p>
        <p class="meta">Enter — дальше</p>`,
      action: "Следующая форма",
      onAction: async () => {
        await refresh();
        render();
      },
    });
    await refresh();
  };
  document.querySelectorAll("[data-conf]").forEach((btn) => {
    btn.addEventListener("click", () => runCheck(Number(btn.dataset.conf)));
  });
  document.getElementById("accept-zoom")?.addEventListener("click", acceptZoomForms);
  document.getElementById("next-form")?.addEventListener("click", async () => {
    closeSheet();
    await refresh();
    render();
  });
  input?.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !revealed) {
      e.preventDefault();
    }
  });
}

async function renderDiagnostic() {
  const gen = viewGen;
  const data = await api("/api/diagnostic");
  if (!still(gen, "/settings?s=diagnostic")) return;
  const items = data.items;
  if (!items.length) {
    stage.innerHTML = `
      ${crumb("Срез")}
      <h1>Срез закрыт</h1>
      <a class="btn btn-shu" data-go="/" href="#/">К пробе</a>`;
    return;
  }
  const cur = items[0];
  stage.innerHTML = `
    ${crumb("Срез")}
    <h1>Уже произнесёте — или нет</h1>
    <p class="lede">Осталось ${items.length}.</p>
    <section class="yoshi">
      <p class="ja">${escapeHtml(cur.prompt_ja)}</p>
      <p class="hint">${escapeHtml(cur.prompt_hint)}</p>
    </section>
    <div class="row">
      <button class="btn btn-shu" id="know">Произведу без карточки</button>
      <button class="btn" id="unk">Не уверен / не умею</button>
    </div>`;
  document.getElementById("know").onclick = () => diag(cur.id, true);
  document.getElementById("unk").onclick = () => diag(cur.id, false);
}

async function diag(id, knows) {
  await api("/api/diagnostic", {
    method: "POST",
    body: JSON.stringify({ claim_id: id, knows }),
  });
  await refresh();
  render();
}

function renderLesson() {
  stage.innerHTML = `
    ${crumb("Занятие")}
    <h1>С занятия</h1>
    <form class="form-grid" id="lesson">
      <label>Название <input name="title" placeholder="29 августа, Zoom 40+40+10" /></label>
      <label>Заметка <input name="notes" placeholder="учитель поправил причину на から" /></label>
      <div id="blocks"></div>
      <div class="row">
        <button type="button" class="btn" id="add">Ещё утверждение</button>
        <button type="submit" class="btn btn-shu">Положить в пробы</button>
      </div>
      <p class="err" id="ferr" hidden></p>
    </form>`;
  const blocks = document.getElementById("blocks");
  const samples = [
    {
      ja: "行く",
      hint: "て-форма, как просил учитель сегодня",
      ex: "行って",
      gloss: "как принял учитель",
    },
    {
      ja: "友達が本を___。 (мне дали)",
      hint: "направление «ко мне», прошедшее",
      ex: "くれた",
      gloss: "как на уроке: дали мне, не я дал",
    },
    {
      ja: "疲れた___、早く寝ます。",
      hint: "причина, как на этом Zoom",
      ex: "から",
      gloss: "если учитель сказал иначе — пишите его форму",
    },
  ];
  const addBlock = (sample) => {
    const wrap = document.createElement("div");
    wrap.className = "claim-block";
    const n = blocks.children.length + 1;
    const s = sample || {
      ja: "行く",
      hint: "произведите форму, как на уроке",
      ex: "行って",
      gloss: "правка учителя",
    };
    wrap.innerHTML = `
      <p class="meta">Утверждение ${n}</p>
      <label>Японский (задание себе) <input name="ja" placeholder="${escapeHtml(s.ja)}" value="" /></label>
      <label>Что произвести <input name="hint" placeholder="${escapeHtml(s.hint)}" value="" /></label>
      <label>Ключ (как сказал учитель) <input name="ex" placeholder="${escapeHtml(s.ex)}" value="" /></label>
      <label>Пояснение к правке <input name="gloss" placeholder="${escapeHtml(s.gloss)}" value="" /></label>`;
    blocks.appendChild(wrap);
    wireIme(wrap);
  };
  addBlock(samples[0]);
  document.getElementById("add").onclick = () => {
    if (blocks.children.length < 12) {
      addBlock(samples[blocks.children.length % samples.length]);
    }
  };
  document.getElementById("lesson").onsubmit = async (e) => {
    e.preventDefault();
    const ferr = document.getElementById("ferr");
    const items = [...blocks.children]
      .map((b) => ({
        prompt_ja: b.querySelector('[name="ja"]').value,
        prompt_hint: b.querySelector('[name="hint"]').value,
        expected: b.querySelector('[name="ex"]').value,
        gloss_ru: b.querySelector('[name="gloss"]').value,
        provenance: "teacher",
      }))
      .filter((x) => x.prompt_ja && x.expected);
    try {
      await api("/api/lessons", {
        method: "POST",
        body: JSON.stringify({
          title: e.target.title.value,
          notes: e.target.notes.value,
          items,
        }),
      });
      await refresh();
      go("/");
    } catch (err) {
      ferr.hidden = false;
      ferr.textContent = "Нужны японский и ключ хотя бы у одной строки. Пустые примеры можно стереть.";
    }
  };
}

async function renderQueue() {
  const gen = viewGen;
  const data = await api("/api/claims");
  if (!still(gen, "/settings?s=queue")) return;
  const claims = data.claims.filter((c) =>
    ["tonight", "queued", "known"].includes(c.status)
  );
  const conflicts = await api("/api/conflicts");
  if (!still(gen, "/settings?s=queue")) return;
  const confHtml = (conflicts.conflicts || [])
    .map(
      (c) =>
        `<article class="item"><p class="ja-sm">${escapeHtml(c.prompt_ja)}</p>
         <p class="meta">«${escapeHtml(c.expected_a)}» / «${escapeHtml(c.expected_b)}»</p></article>`
    )
    .join("");
  if (!claims.length) {
    stage.innerHTML = `${crumb("Очередь")}<h1>Очередь пуста</h1>${confHtml}`;
    return;
  }
  stage.innerHTML = `
    ${crumb("Очередь")}
    <h1>Очередь</h1>
    <div class="list">
      ${claims
        .map(
          (c) => `
        <article class="item">
          <p class="ja-sm">${escapeHtml(c.prompt_ja)}</p>
          <p class="meta">${escapeHtml(STATUS_RU[c.status] || c.status)} · ${escapeHtml(PROV_RU[c.provenance] || c.provenance)} · ${escapeHtml(c.prompt_hint)}</p>
        </article>`
        )
        .join("")}
    </div>
    ${confHtml ? `<h1>Конфликты</h1>${confHtml}` : ""}`;
}

function spark(points) {
  if (!points.length) return "";
  const w = 640;
  const h = 160;
  const pad = 12;
  const xs = points.map((_, i) => pad + (i * (w - pad * 2)) / Math.max(points.length - 1, 1));
  const ys = points.map((p) => pad + (1 - p.rate) * (h - pad * 2));
  const d = xs.map((x, i) => `${i ? "L" : "M"}${x},${ys[i]}`).join(" ");
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" role="img" aria-label="Первая попытка после паузы">
    <path d="${d}" fill="none" stroke="#e8a4b4" stroke-width="2" /></svg>`;
}

async function renderGrowth() {
  const gen = viewGen;
  const g = await api("/api/growth");
  if (!still(gen, "/settings?s=growth")) return;
  const h = g.headline;
  const rate = h.pass_rate == null ? "—" : `${Math.round(h.pass_rate * 100)}%`;
  const field = g.stars || { stars: [], edges: [] };
  const hasStars = (field.stars || []).length > 0;
  const rows = (g.delayed_first || [])
    .slice(-12)
    .reverse()
    .map(
      (a) =>
        `<article class="item"><p class="ja-sm">${escapeHtml(a.prompt_ja)}</p>
         <p class="meta">${escapeHtml(a.outcome)} · пауза ${Number(a.delay_hours).toFixed(1)} ч · ${escapeHtml(a.provenance)}</p></article>`
    )
    .join("");
  const sky = hasStars
    ? `<details class="how" id="sky-details">
        <summary>Небо форм</summary>
        <div class="sky-wrap">
          <p class="sky-title">星合わせ</p>
          <span class="sky-hanko" aria-hidden="true">要</span>
          <canvas id="sky" role="img" aria-label="Небо форм"></canvas>
        </div>
        <aside class="sky-plate" id="sky-plate" hidden></aside>
      </details>`
    : "";
  stage.innerHTML = `
    ${crumb("После паузы")}
    <h1>После паузы</h1>
    <p class="lede">${escapeHtml(h.note)} ${rate}, n=${h.n}.</p>
    ${g.delayed_curve.length ? spark(g.delayed_curve) : ""}
    <div class="list">${rows || ""}</div>
    ${sky}`;
  const box = document.getElementById("sky-details");
  if (hasStars && box && window.ProbaSky) {
    box.addEventListener("toggle", () => {
      if (!box.open) {
        stopSky();
        return;
      }
      skyOff = window.ProbaSky.mount(
        document.getElementById("sky"),
        document.getElementById("sky-plate"),
        field
      );
    });
  }
}

async function renderZoom() {
  const gen = viewGen;
  const live = () => still(gen, "/zoom");
  const paint = async () => {
    if (!live()) return;
    const s = await api("/api/capture");
    if (!live()) return;
    const zoom = s.zoom_running ? "окно Zoom на компьютере есть" : "процесс Zoom не найден";
    const lang = s.language_hint
      ? `После расшифровки язык: ${s.language_hint}.`
      : "Язык появится после расшифровки.";
    const an = s.analysis || {};
    const anLine =
      an.state === "running"
        ? `Разбор на ${an.device === "cuda" ? "видеокарте" : "процессоре"} (${an.model}).`
        : an.state === "done"
          ? `Разобрано форм: ${an.proposed}. ${an.device === "cuda" ? "GPU" : "CPU"} · ${an.model}`
          : an.state === "error"
            ? an.error || "разбор не удался"
            : "После «Конец занятия» звук разбирается сам.";
    stage.innerHTML = `
      <h1>Звук Zoom</h1>
      <p class="lede">Звук урока. На ~40-й минуте Zoom часто обрывается — «Пауза», после переподключения «Продолжить».</p>
      <p><span class="status-dot ${s.state === "recording" ? "on" : ""}"></span>${escapeHtml(s.state)} · ${zoom}</p>
      <p class="meta">${escapeHtml(lang)}</p>
      <p class="meta">${escapeHtml(anLine)}</p>
      ${s.last_error ? `<p class="err">${escapeHtml(s.last_error)}</p>` : ""}
      <div class="row">
        <button class="btn btn-shu" data-a="start">Занятие началось</button>
        <button class="btn" data-a="pause">Пауза (обрыв 40 мин)</button>
        <button class="btn" data-a="resume">Продолжить после переподключения</button>
        <button class="btn" data-a="stop">Конец занятия</button>
      </div>`;
    stage.querySelectorAll("[data-a]").forEach((btn) => {
      btn.onclick = async () => {
        await api("/api/capture", {
          method: "POST",
          body: JSON.stringify({ action: btn.dataset.a, title: "Zoom" }),
        });
        await refresh();
        if (!live()) return;
        paint();
      };
    });
  };
  await paint();
  if (!live()) return;
  captureTimer = setInterval(paint, 4000);
}

function shotPanelHtml() {
  return `
    <div class="shot-drop" id="shot-drop" tabindex="0">
      <p>Снимок: Ctrl+V даже в строке поиска, либо перетащите файл сюда.</p>
      <p class="meta">Перенос слова на следующую строку склеивается до перевода. Это не урок.</p>
      <input type="file" id="shot-file" accept="image/png,image/jpeg,image/webp,image/bmp,image/gif" />
    </div>
    <p class="err" id="shot-err" hidden></p>
    <article class="shot-out" id="shot-out" hidden>
      <p class="shot-src" id="shot-src"></p>
      <p class="shot-ru" id="shot-ru"></p>
      <p class="meta" id="shot-note"></p>
    </article>`;
}

function imageFromClipboard(dt) {
  if (!dt) return null;
  for (const it of dt.items || []) {
    if (it.type && it.type.startsWith("image/")) return it.getAsFile();
  }
  for (const f of dt.files || []) {
    if (f.type && f.type.startsWith("image/")) return f;
  }
  return null;
}

function clipboardPlainText(dt) {
  if (!dt || !dt.getData) return "";
  const raw = (dt.getData("text") || dt.getData("text/plain") || "").trim();
  if (!raw) return "";
  if (/^<(!doctype|html|head|body|img|meta|svg)\b/i.test(raw)) return "";
  return raw;
}

function wireShot(gen, livePath) {
  const drop = document.getElementById("shot-drop");
  const file = document.getElementById("shot-file");
  if (!drop || !file) return;
  const paintShot = async (work) => {
    const err = document.getElementById("shot-err");
    const out = document.getElementById("shot-out");
    const src = document.getElementById("shot-src");
    const ru = document.getElementById("shot-ru");
    const note = document.getElementById("shot-note");
    if (err) {
      err.hidden = true;
      err.textContent = "";
    }
    if (note) note.textContent = "Читаю снимок…";
    if (out) {
      out.hidden = false;
      out.scrollIntoView({ block: "nearest" });
    }
    if (src) src.textContent = "";
    if (ru) ru.textContent = "";
    drop.classList.add("on");
    let res;
    let body = {};
    try {
      res = await work();
      try {
        body = await res.json();
      } catch (e) {
        body = {};
      }
    } catch (e) {
      if (!still(gen, livePath)) return;
      drop.classList.remove("on");
      if (err) {
        err.hidden = false;
        err.textContent = "Снимок не отправился.";
      }
      if (note) note.textContent = "";
      return;
    }
    drop.classList.remove("on");
    if (!still(gen, livePath)) return;
    if (!res.ok) {
      const detail = typeof body.detail === "string" ? body.detail : "Текст не прочитался.";
      if (err) {
        err.hidden = false;
        err.textContent = detail;
      }
      if (out) out.hidden = true;
      return;
    }
    if (src) src.textContent = body.source || "";
    if (ru) ru.textContent = body.gloss_ru || "";
    if (note) note.textContent = body.note || "";
  };
  const send = (blob) => {
    if (!blob) return;
    const fd = new FormData();
    fd.append("file", blob, blob.name || "shot.png");
    return paintShot(() => fetch("/api/shot", { method: "POST", body: fd }));
  };
  const sendClip = () => paintShot(() => fetch("/api/shot/clip", { method: "POST" }));
  drop.ondragover = (e) => {
    e.preventDefault();
    drop.classList.add("on");
  };
  drop.ondragleave = () => drop.classList.remove("on");
  drop.ondrop = (e) => {
    e.preventDefault();
    drop.classList.remove("on");
    const blob = imageFromClipboard(e.dataTransfer) || e.dataTransfer?.files?.[0];
    if (blob && String(blob.type || "").startsWith("image/")) send(blob);
  };
  drop.onclick = (e) => {
    if (e.target === file) return;
    file.click();
  };
  file.onchange = () => {
    const blob = file.files && file.files[0];
    send(blob);
    file.value = "";
  };
  const onPaste = (e) => {
    const blob = imageFromClipboard(e.clipboardData);
    if (blob) {
      e.preventDefault();
      send(blob);
      return;
    }
    if (clipboardPlainText(e.clipboardData)) return;
    e.preventDefault();
    sendClip();
  };
  document.addEventListener("paste", onPaste, true);
  shotPasteOff = () => document.removeEventListener("paste", onPaste, true);
}

function renderShot(livePath) {
  const path = livePath || "/settings?s=shot";
  stage.innerHTML = `
    ${crumb("Снимок")}
    <h1>Снимок</h1>
    ${shotPanelHtml()}`;
  wireShot(viewGen, path);
}

function renderImport() {
  const gen = viewGen;
  stage.innerHTML = `
    ${crumb("Текст")}
    <h1>Текст или PDF</h1>
    <form class="form-grid" id="paste">
      <label>Название <input name="title" placeholder="чат Zoom 29 августа" /></label>
      <label>Текст <textarea name="text" placeholder="Вставьте реплики или оглавление."></textarea></label>
      <div class="row">
        <button class="btn btn-shu" type="submit">Разобрать текст</button>
        <button class="btn" type="button" id="analyze-path">Сопоставить с тропой</button>
      </div>
    </form>
    <p class="meta">PDF</p>
    <input type="file" id="pdf" accept="application/pdf" />
    <p class="err" id="ierr" hidden></p>
    <p id="iok" class="meta"></p>`;
  document.getElementById("paste").onsubmit = async (e) => {
    e.preventDefault();
    try {
      const r = await api("/api/import/text", {
        method: "POST",
        body: JSON.stringify({
          title: e.target.title.value,
          text: e.target.text.value,
        }),
      });
      if (!still(gen, "/settings?s=text")) return;
      document.getElementById("iok").textContent =
        `Черновиков из текста: ${r.proposed.length}. Откройте Настройки → Черновики. Страница запомнена для тропы.`;
    } catch (err) {
      document.getElementById("ierr").hidden = false;
      document.getElementById("ierr").textContent = "Нужен непустой текст.";
    }
  };
  document.getElementById("analyze-path").onclick = async () => {
    const text = document.querySelector("#paste textarea")?.value || "";
    try {
      const a = await api("/api/plan/analyze", { method: "POST", body: JSON.stringify({ text }) });
      const f = await api("/api/plan/fill", { method: "POST", body: JSON.stringify({ text, level: catalogLevelFromRoute() }) });
      if (!still(gen, "/settings?s=text")) return;
      const names = (a.matched || []).map((m) => m.title).slice(0, 8).join(" · ");
      const unmatched = !(a.matched || []).some((m) => m.fillable);
      document.getElementById("iok").textContent =
        `Сопоставление (lexicon): ${a.matched.length} тем. Черновиков тропы: ${f.count}. ${
          names || (unmatched ? "названия тем не найдены — открытые примеры." : "")
        } Примите в Черновиках.`;
    } catch (err) {
      document.getElementById("ierr").hidden = false;
      document.getElementById("ierr").textContent = "Сопоставить не удалось.";
    }
  };
  document.getElementById("pdf").onchange = async (e) => {
    const f = e.target.files[0];
    if (!f) return;
    const fd = new FormData();
    fd.append("file", f);
    const res = await fetch("/api/import/pdf", { method: "POST", body: fd });
    const r = await res.json();
    if (!still(gen, "/settings?s=text")) return;
    document.getElementById("iok").textContent = res.ok
      ? `PDF: черновиков ${r.proposed?.length || 0}. Примите в черновиках.`
      : r.detail || "ошибка PDF";
  };
}

async function renderDict(livePath) {
  const gen = viewGen;
  const path = livePath || (meta.atlas ? "/dict" : "/settings?s=dict");
  const crumbHtml = meta.atlas ? "" : crumb("Словарь");
  stage.innerHTML = `
    ${crumbHtml}
    <h1>Словарь</h1>
    <form class="form-grid" id="ds">
      <label>Поиск <input name="q" placeholder="itte, 行く, вода — или Ctrl+V снимок" /></label>
      <button class="btn" type="submit">Найти</button>
    </form>
    <p class="lede"><a href="#/giongo" data-go="/giongo">擬音語・擬態語</a></p>
    ${shotPanelHtml()}
    <div class="list" id="dhits"></div>`;
  const paint = (hits) => {
    document.getElementById("dhits").innerHTML = hits
      .map((h) => {
        if (h.kind === "kanji") {
          return `<button type="button" class="item dict-hit" data-open-kanji="${escapeHtml(h.head)}">
           <div class="kanji-stage kanji-stage-sm" data-stroke="${escapeHtml(h.head)}"></div>
           <p class="ja-sm">${escapeHtml(h.head)} · 部首 ${escapeHtml(h.radical || "")}</p>
           <p class="dict-on">${escapeHtml(h.on || "—")}</p>
           <p class="dict-kun">${escapeHtml(h.kun || "—")}</p>
           ${glossParagraphs(h.gloss_ru || "")}
           </button>`;
        }
        return `<button type="button" class="item dict-hit" data-open-word="${escapeHtml(h.head)}">
           <p class="ja-sm">${escapeHtml(h.head)} · ${escapeHtml(h.kana || "")}${h.kind === "mimetic" ? " · 擬音" : ""}</p>
           ${h.kind === "mimetic" ? glossParagraphs(h.gloss_ru || h.gloss || "") : `<p class="dict-gloss">${escapeHtml(h.gloss_ru || h.gloss || "")}</p>`}
           </button>`;
      })
      .join("");
    document.querySelectorAll("#dhits [data-open-kanji], #dhits [data-open-word]").forEach((el) => {
      el.onclick = () => {
        if (el.dataset.openKanji) openDictKanji(el.dataset.openKanji);
        else openDictWord(el.dataset.openWord);
      };
    });
    if (window.ProbaStrokes) {
      document.querySelectorAll("#dhits [data-stroke]").forEach((el) => {
        window.ProbaStrokes.playPlate(el, el.dataset.stroke);
      });
    }
  };
  const data = await api("/api/dict");
  if (!still(gen, path)) return;
  paint(data.hits);
  wireIme(document.getElementById("ds"));
  wireShot(gen, path);
  document.getElementById("ds").onsubmit = async (e) => {
    e.preventDefault();
    const r = await api("/api/dict?q=" + encodeURIComponent(e.target.q.value));
    paint(r.hits);
  };
}

function gojuonMarkup(idx, current) {
  const rows = (idx.rows || [])
    .map((row) => {
      const cells = row
        .map((cell) => {
          if (!cell.kana) return '<span class="gojuon-gap"></span>';
          const on = cell.kana === current ? " on" : "";
          const dis = cell.n ? "" : " disabled";
          return (
            `<button type="button" class="gojuon-cell${on}" data-mora="${escapeHtml(cell.kana)}"${dis}>` +
            `<span class="gojuon-kana">${escapeHtml(cell.kana)}</span>` +
            `<span class="gojuon-n">${cell.n || ""}</span></button>`
          );
        })
        .join("");
      return `<div class="gojuon-row">${cells}</div>`;
    })
    .join("");
  return `<div class="gojuon" role="tablist" aria-label="五十音">${rows}</div>`;
}

async function renderGiongo() {
  const gen = viewGen;
  const mora = routeQuery("m") || "あ";
  const crumbHtml = meta.atlas ? "" : crumb("擬音");
  stage.innerHTML = `${crumbHtml}<p class="empty">Загрузка…</p>`;
  let idx;
  try {
    idx = await api("/api/giongo");
  } catch (err) {
    if (!still(gen, "/giongo")) return;
    stage.innerHTML = `<p class="err">擬音 не открылся.</p>`;
    return;
  }
  if (!still(gen, "/giongo")) return;
  const data = await api("/api/giongo?mora=" + encodeURIComponent(mora));
  if (!still(gen, "/giongo")) return;
  const hits = data.hits || [];
  stage.innerHTML = `
    ${crumbHtml}
    <h1>擬音語・擬態語</h1>
    <p class="lede">${idx.count || 0} статей.</p>
    <form class="form-grid" id="gs">
      <label>Поиск <input name="q" placeholder="wakuwaku, どきどき, сердце" /></label>
      <button class="btn" type="submit">Найти</button>
    </form>
    ${gojuonMarkup(idx, mora)}
    <div class="list" id="ghits">
      ${
        hits
          .map(
            (h) => `<button type="button" class="item dict-hit" data-open-word="${escapeHtml(h.head)}">
              <p class="ja-sm">${escapeHtml(h.head)}</p>
              ${glossParagraphs(h.gloss_ru || h.gloss || "")}
            </button>`
          )
          .join("") || `<p class="empty">В этом ряду пусто.</p>`
      }
    </div>`;
  stage.querySelectorAll("[data-mora]").forEach((btn) => {
    btn.onclick = () => go("/giongo?m=" + encodeURIComponent(btn.dataset.mora));
  });
  stage.querySelectorAll("[data-open-word]").forEach((el) => {
    el.onclick = () => openDictWord(el.dataset.openWord);
  });
  wireIme(document.getElementById("gs"));
  document.getElementById("gs").onsubmit = async (e) => {
    e.preventDefault();
    const q = e.target.q.value;
    const r = await api("/api/giongo?q=" + encodeURIComponent(q));
    const box = document.getElementById("ghits");
    if (!box) return;
    box.innerHTML = (r.hits || [])
      .map(
        (h) => `<button type="button" class="item dict-hit" data-open-word="${escapeHtml(h.head)}">
          <p class="ja-sm">${escapeHtml(h.head)}</p>
          ${glossParagraphs(h.gloss_ru || h.gloss || "")}
        </button>`
      )
      .join("") || `<p class="empty">Нет совпадений.</p>`;
    box.querySelectorAll("[data-open-word]").forEach((el) => {
      el.onclick = () => openDictWord(el.dataset.openWord);
    });
  };
}

async function renderGaps() {
  const gen = viewGen;
  const g = await api("/api/gaps");
  const proposed = (await api("/api/claims?status=proposed")).claims || [];
  if (!still(gen, "/settings?s=gaps")) return;
  const gapHtml = (g.gaps || [])
    .map(
      (x) => `
      <article class="item" data-g="${x.id}">
        <p class="ja-sm">${escapeHtml(x.prompt_ja)}</p>
        <p class="meta">${escapeHtml(x.reason)} · произвести: ${escapeHtml(x.prompt_hint)}</p>
        <div class="row">
          <button class="btn btn-shu" data-ok="1">В пробы</button>
          <button class="btn" data-ok="0">Не сейчас</button>
        </div>
      </article>`
    )
    .join("");
  const propHtml = proposed
    .map(
      (c) => `
      <article class="item" data-p="${c.id}">
        <p class="ja-sm">${escapeHtml(c.prompt_ja)}</p>
        <p class="meta">из текста/аудио · ${escapeHtml(c.provenance)}</p>
        <div class="row">
          <button class="btn btn-shu" data-ok="1">Принять в пробы</button>
          <button class="btn" data-ok="0">Отклонить</button>
        </div>
      </article>`
    )
    .join("");
  const zp = snapshot?.zoom_proposed;
  stage.innerHTML = `
    ${crumb("Черновики")}
    <h1>Предложения</h1>
    ${
      zp
        ? `<div class="row"><button class="btn btn-shu" id="accept-zoom">Все формы с последнего Zoom — в пробы</button></div>`
        : ""
    }
    <div class="list">${gapHtml || `<p class="empty">Нет соседних черновиков с этого занятия.</p>`}</div>
    <h1>Из расшифровки / текста</h1>
    <div class="list">${propHtml || `<p class="empty">Нет черновиков. Если Whisper нет — вставьте чат урока в Настройки → Текст.</p>`}</div>`;
  document.getElementById("accept-zoom")?.addEventListener("click", acceptZoomForms);
  stage.querySelectorAll("[data-g]").forEach((el) => {
    el.querySelectorAll("[data-ok]").forEach((btn) => {
      btn.onclick = async () => {
        await api("/api/gaps", {
          method: "POST",
          body: JSON.stringify({ id: el.dataset.g, accept: btn.dataset.ok === "1" }),
        });
        await refresh();
        render();
      };
    });
  });
  stage.querySelectorAll("[data-p]").forEach((el) => {
    el.querySelectorAll("[data-ok]").forEach((btn) => {
      btn.onclick = async () => {
        await api("/api/proposed", {
          method: "POST",
          body: JSON.stringify({ id: el.dataset.p, accept: btn.dataset.ok === "1" }),
        });
        await refresh();
        render();
      };
    });
  });
}

async function renderPack() {
  const gen = viewGen;
  const p = await api("/api/pack");
  if (!still(gen, "/settings?s=pack")) return;
  stage.innerHTML = `
    ${crumb("К учителю")}
    <h1>Три формы к учителю</h1>
    <p class="lede">На следующем Zoom. Ключ — кнопка ниже.</p>
    <div class="list">
      ${(p.items || [])
        .map(
          (c) =>
            `<article class="item"><p class="ja-sm">${escapeHtml(c.prompt_ja)}</p>
             <p class="meta">${escapeHtml(c.prompt_hint)}</p>
             <button type="button" class="btn" data-show-key="${escapeHtml(c.expected)}">Показать ключ</button></article>`
        )
        .join("") || `<p class="empty">Пока нечего нести. Пройдите пробы после занятия.</p>`}
    </div>
    <p class="lede">${(p.questions || []).map(escapeHtml).join("<br/>")}</p>`;
  stage.querySelectorAll("[data-show-key]").forEach((btn) => {
    btn.onclick = () => {
      const key = btn.getAttribute("data-show-key") || "";
      const p = document.createElement("p");
      p.className = "meta";
      p.textContent = `ключ ${key}`;
      btn.replaceWith(p);
    };
  });
}

window.probaOpen = function (dest) {
  const next = String(dest || "/").replace(/^#/, "") || "/";
  refresh().then(() => go(next));
};
window.probaShowHome = function () {
  window.probaOpen("/");
};
window.go = go;
window.addEventListener("hashchange", () => {
  setActive((location.hash || "").replace(/^#/, "") || "/");
  render();
});
window.addEventListener("popstate", () => {
  setActive((location.hash || "").replace(/^#/, "") || "/");
  render();
});
document.addEventListener("click", (e) => {
  const goEl = e.target.closest("[data-go]");
  if (goEl) {
    e.preventDefault();
    closeSheet();
    document.querySelector(".rail")?.classList.remove("rail-open");
    go(goEl.getAttribute("data-go"));
    return;
  }
  const a = e.target.closest(".rail nav a[data-route]");
  if (!a) return;
  e.preventDefault();
  document.querySelector(".rail")?.classList.remove("rail-open");
  go(a.dataset.route);
});
document.getElementById("rail-more")?.addEventListener("click", () => {
  const rail = document.querySelector(".rail");
  const open = rail.classList.toggle("rail-open");
  document.getElementById("rail-more").setAttribute("aria-expanded", String(open));
});
document.getElementById("veil")?.addEventListener("click", (e) => {
  if (e.target !== e.currentTarget) return;
  dismissSheet();
});
document.addEventListener("keydown", (e) => {
  if (e.key !== "Escape") return;
  if (document.getElementById("veil")?.hidden) return;
  e.preventDefault();
  dismissSheet();
});
document.getElementById("veil")?.addEventListener("keydown", (e) => {
  if (e.key !== "Enter" || document.getElementById("veil")?.hidden) return;
  if (e.target && (e.target.id === "station-answer" || e.target.closest("#station-drill"))) return;
  const btn = document.querySelector("#sheet-actions .btn-shu");
  if (!btn) return;
  e.preventDefault();
  btn.click();
});
if (window.pywebview) document.body.classList.add("native");
bootLocation();
(async () => {
  try {
    meta = await api("/api/meta");
    applyChrome();
    await refresh();
    render();
  } catch (e) {
    stage.innerHTML =
      `<p class="err">${escapeHtml(meta.app_name || "日本語学習アシスタント")} не отвечает. Закройте её в трее (правый нижний угол) и откройте снова.</p>`;
  }
})();
