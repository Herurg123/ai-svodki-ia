"use strict";

const fs = require("fs");
const path = require("path");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const PUBLICATIONS_URL = "https://dzen.ru/profile/editor/rybv/publications";
const COLLECTION_CARD_TIMEOUT_MS = 15_000;
const COLLECTION_CARD_POLL_MS = 300;
const MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const MONTHS_SHORT = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"];

const TARGETS = [
  {
    key: "video",
    label: "видео",
    collectionName: "Видеосводки по ИИ",
    collectionUrl: "https://dzen.ru/suite/a899d818-52b3-4f87-8e49-4a4bac375244",
    isVideo: true,
  },
  {
    key: "digest",
    label: "ежедневная сводка",
    collectionName: "Сводки по ИИ",
    collectionUrl: "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1",
    isVideo: false,
  },
];

function stripBom(value) { return String(value || "").replace(/^\uFEFF/, ""); }
function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}
function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.collections-${process.pid}-${Date.now()}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
}
function normalizeText(value) {
  return String(value || "").normalize("NFKC")
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
    .replace(/[\u00A0\u202F]/g, " ").replace(/\s+/g, " ").trim();
}
function parseDateKey(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) throw new Error(`Некорректная дата: ${value}`);
  const year = Number(match[1]), month = Number(match[2]), day = Number(match[3]);
  const d = new Date(Date.UTC(year, month - 1, day));
  if (d.getUTCFullYear() !== year || d.getUTCMonth() !== month - 1 || d.getUTCDate() !== day) {
    throw new Error(`Некорректная дата: ${value}`);
  }
  return { year, month, day };
}
function formatRussianLongDate(dateKey) {
  const { year, month, day } = parseDateKey(dateKey);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}
function shortDateLabel(dateKey) {
  const { month, day } = parseDateKey(dateKey);
  return `${day} ${MONTHS_SHORT[month - 1]}`;
}
function formatDateKey(date, timeZone) {
  const parts = new Intl.DateTimeFormat("en-CA", { timeZone, year: "numeric", month: "2-digit", day: "2-digit" }).formatToParts(date);
  const v = {}; for (const p of parts) if (["year", "month", "day"].includes(p.type)) v[p.type] = p.value;
  return `${v.year}-${v.month}-${v.day}`;
}
function formatTime(timeZone) {
  return new Intl.DateTimeFormat("ru-RU", { timeZone, year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit", second: "2-digit" }).format(new Date());
}
function appendLine(filePath, line) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${line}\r\n`, "utf8");
}
function createLogger(config) {
  const write = (prefix, message, error = null) => {
    const suffix = error?.stack ? `\r\n${error.stack}` : "";
    const line = `[${formatTime(config.timeZone || "Europe/Moscow")}] ${prefix}${message}${suffix}`;
    if (prefix.includes("!!!")) console.error(line); else console.log(line);
    appendLine(config.regularLog, line);
    if (prefix.includes("!!!") && config.errorLog !== config.regularLog) appendLine(config.errorLog, line);
  };
  return { log: (m) => write("DZEN-COLLECTIONS: ", m), warn: (m) => write("DZEN-COLLECTIONS WARN: ", m), fatal: (m, e) => write("DZEN-COLLECTIONS !!!: ", m, e) };
}
function parseArgs(argv) {
  const args = { date: null, apply: false, visible: false, selfTest: false };
  for (const arg of argv) {
    if (arg === "--apply") args.apply = true;
    else if (arg === "--visible") args.visible = true;
    else if (arg === "--self-test") args.selfTest = true;
    else if (arg.startsWith("--date=")) { args.date = arg.slice(7).trim(); parseDateKey(args.date); }
    else throw new Error(`Неизвестный параметр: ${arg}`);
  }
  return args;
}
function titleFor(target, dateKey) {
  const prefix = `ИИ-Сводка на ${formatRussianLongDate(dateKey)}`;
  return target.isVideo ? `${prefix} | Подпишись, чтоб получать свежее!` : prefix;
}
function findJobForDate(state, dateKey) {
  const jobs = Object.values(state?.jobs || {}).filter((job) => job?.date === dateKey);
  jobs.sort((a, b) => String(b.updatedAt || b.downloadedAt || "").localeCompare(String(a.updatedAt || a.downloadedAt || "")));
  return jobs[0] || null;
}
function targetIsAdded(job, key) { return String(job?.dzenCollections?.[key]?.status || "") === "ADDED"; }
function collectionsStatus(job) {
  const n = TARGETS.filter((t) => targetIsAdded(job, t.key)).length;
  return n === 2 ? "COMPLETE" : n === 1 ? "PARTIAL" : "PENDING";
}
function collectionsComplete(job) { return collectionsStatus(job) === "COMPLETE"; }
function updateCollectionTarget(config, state, job, target, fields) {
  const now = new Date().toISOString();
  job.dzenCollections = {
    ...(job.dzenCollections || {}),
    [target.key]: { ...(job.dzenCollections?.[target.key] || {}), collectionName: target.collectionName, collectionUrl: target.collectionUrl, ...fields, updatedAt: now },
    updatedAt: now,
  };
  job.dzenCollections.status = collectionsStatus(job);
  if (job.dzenCollections.status === "COMPLETE") job.dzenCollections.completedAt ||= now;
  job.updatedAt = now;
  saveJsonAtomic(config.stateFile, state);
  return job.dzenCollections.status;
}
function classifyCollectionCardLookup(visibleCount, timedOut) {
  if (!Number.isInteger(visibleCount) || visibleCount < 0) throw new Error(`Некорректное число видимых подборок: ${visibleCount}`);
  if (visibleCount === 1) return "FOUND";
  if (visibleCount > 1) return "AMBIGUOUS";
  return timedOut ? "TIMEOUT" : "WAIT";
}
function isLoginUrl(url) {
  const v = String(url || "").toLowerCase();
  return ["passport.yandex", "sso.dzen.ru", "dzen.ru/login", "oauth.yandex", "auth?retpath"].some((x) => v.includes(x));
}
async function screenshot(page, config, dateKey, label) {
  const dir = config.screenshotsDir || path.join(ROOT, "screenshots");
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const file = path.join(dir, `dzen-collections-${dateKey}-${label}-${stamp}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => {});
  return file;
}
async function openPublications(page) {
  await page.goto(PUBLICATIONS_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (isLoginUrl(page.url())) throw new Error(`Дзен перенаправил на URL авторизации: ${page.url()}`);
    const text = normalizeText(await page.locator("body").innerText().catch(() => ""));
    if (text.includes("Публикации") && text.includes("Опубликованные")) return;
    await page.waitForTimeout(500);
  }
  throw new Error("Не подтверждена Studio -> Публикации.");
}
async function ensureAllFilter(page) {
  const radio = page.locator('input[type="radio"][aria-label="Все"]').first();
  if (await radio.count().catch(() => 0)) {
    if (!(await radio.isChecked().catch(() => false))) await radio.evaluate((el) => el.click());
    await page.waitForTimeout(700);
  }
}
async function findPublicationRow(page, target, dateKey, logger) {
  const prefix = `ИИ-Сводка на ${formatRussianLongDate(dateKey)}`;
  const dayLabel = shortDateLabel(dateKey);
  const deadline = Date.now() + 15_000;
  while (Date.now() < deadline) {
    const rows = await page.evaluate(({ prefix, dayLabel }) => {
      const norm = (v) => String(v || "").replace(/\s+/g, " ").trim();
      const visible = (e) => { const r = e.getBoundingClientRect(), s = getComputedStyle(e); return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden"; };
      const out = [], seen = new Set();
      for (const el of [...document.querySelectorAll("a,div,span,p,h1,h2,h3")]) {
        if (!visible(el)) continue;
        const txt = norm(el.innerText || el.textContent); if (!txt.includes(prefix) || txt.length > 260) continue;
        let node = el;
        for (let d = 0; node && d < 15; d += 1, node = node.parentElement) {
          if (!visible(node)) continue;
          const r = node.getBoundingClientRect(), rowText = norm(node.innerText || node.textContent);
          if (r.width < 650 || r.height < 45 || r.height > 220 || !rowText.includes(prefix) || !rowText.includes(dayLabel)) continue;
          const controls = [...node.querySelectorAll('button,[role="button"]')].filter(visible).filter((c) => c.getBoundingClientRect().left >= r.left + r.width * 0.65);
          if (!controls.length || seen.has(node)) continue;
          seen.add(node);
          const titles = [...node.querySelectorAll("a,div,span,p,h1,h2,h3")].filter(visible).map((x) => norm(x.innerText || x.textContent)).filter((x) => x.startsWith(prefix) && x.length <= 180).sort((a,b)=>a.length-b.length);
          const title = titles[0] || txt;
          const marker = `ai-svodki-row-${out.length}-${Date.now()}`; node.setAttribute("data-ai-svodki-row", marker);
          out.push({ marker, title, videoLike: rowText.includes(`${prefix} |`) || title.includes("|") }); break;
        }
      }
      return out;
    }, { prefix, dayLabel });
    const matches = rows.filter((r) => r.videoLike === target.isVideo);
    if (matches.length === 1) { logger.log(`Найдена ${target.label}: «${matches[0].title}».`); return page.locator(`[data-ai-svodki-row="${matches[0].marker}"]`).first(); }
    if (matches.length > 1) throw new Error(`Для ${target.label} найдено несколько строк текущей даты.`);
    await page.waitForTimeout(500);
  }
  logger.log(`За дату выпуска не найдена ${target.label}: «${titleFor(target, dateKey)}». Это допустимо.`);
  return null;
}
async function getVisibleExactText(pageOrLocator, text) {
  const matches = pageOrLocator.getByText(text, { exact: true });
  for (let i = 0; i < await matches.count().catch(() => 0); i += 1) {
    const item = matches.nth(i);
    if (await item.isVisible().catch(() => false)) return item;
  }
  return null;
}
async function findCollectionsModal(page, heading) {
  const dialogs = page.locator('[role="dialog"]');
  for (let i = 0; i < await dialogs.count().catch(() => 0); i += 1) {
    const dialog = dialogs.nth(i);
    if (!(await dialog.isVisible().catch(() => false))) continue;
    if ((await dialog.getByText("Добавление публикации в подборку", { exact: true }).count().catch(() => 0)) > 0) return dialog;
  }
  const marker = `ai-svodki-modal-${Date.now()}`;
  const ok = await heading.evaluate((el, markerValue) => {
    let node = el;
    for (let depth = 0; node && depth < 12; depth += 1, node = node.parentElement) {
      const r = node.getBoundingClientRect();
      const style = getComputedStyle(node);
      if (r.width >= 480 && r.height >= 220 && style.visibility !== "hidden" && style.display !== "none") {
        node.setAttribute("data-ai-svodki-modal", markerValue);
        return true;
      }
    }
    return false;
  }, marker).catch(() => false);
  if (!ok) throw new Error("Окно «Добавление публикации в подборку» открыто, но контейнер модалки не определён.");
  return page.locator(`[data-ai-svodki-modal="${marker}"]`).first();
}
async function openCollectionModal(page, row, title) {
  const buttons = row.locator('button,[role="button"]');
  let chosen = null, maxX = -1;
  for (let i = 0; i < await buttons.count().catch(() => 0); i += 1) {
    const b = buttons.nth(i); if (!(await b.isVisible().catch(() => false))) continue;
    const box = await b.boundingBox().catch(() => null); if (box && box.x > maxX) { chosen = b; maxX = box.x; }
  }
  if (!chosen) throw new Error(`Для «${title}» не найдено меню «…».`);
  await chosen.click({ force: true, timeout: 10_000 });
  const addDeadline = Date.now() + 10_000;
  let add = null;
  while (Date.now() < addDeadline && !add) {
    add = await getVisibleExactText(page, "Добавить в подборку");
    if (!add) await page.waitForTimeout(250);
  }
  if (!add) throw new Error("В меню публикации не найден видимый пункт «Добавить в подборку».");
  await add.click({ timeout: 10_000 });
  const headingDeadline = Date.now() + 10_000;
  let heading = null;
  while (Date.now() < headingDeadline && !heading) {
    heading = await getVisibleExactText(page, "Добавление публикации в подборку");
    if (!heading) await page.waitForTimeout(250);
  }
  if (!heading) throw new Error("После выбора действия не открылось окно «Добавление публикации в подборку».");
  return findCollectionsModal(page, heading);
}
async function findCollectionCard(page, modal, name, logger, timeoutMs = COLLECTION_CARD_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let waitLogged = false;

  while (true) {
    if (!(await modal.isVisible().catch(() => false))) {
      throw new Error(`Окно подборок закрылось до появления «${name}».`);
    }

    const text = modal.getByText(name, { exact: true });
    const visible = [];
    for (let i = 0; i < await text.count().catch(() => 0); i += 1) {
      if (await text.nth(i).isVisible().catch(() => false)) visible.push(text.nth(i));
    }

    const lookupState = classifyCollectionCardLookup(visible.length, Date.now() >= deadline);
    if (lookupState === "AMBIGUOUS") {
      throw new Error(`Ожидалась одна видимая подборка «${name}», найдено ${visible.length}.`);
    }
    if (lookupState === "TIMEOUT") {
      throw new Error(`Не дождался загрузки подборки «${name}» за ${timeoutMs} мс: видимых точных совпадений 0.`);
    }
    if (lookupState === "WAIT") {
      if (!waitLogged) {
        logger.log(`Окно подборок открыто; жду загрузку плашки «${name}» до ${timeoutMs} мс.`);
        waitLogged = true;
      }
      await page.waitForTimeout(COLLECTION_CARD_POLL_MS);
      continue;
    }

    const marker = `ai-svodki-card-${Date.now()}`;
    const ok = await visible[0].evaluate((el, markerValue) => {
      let node = el, best = null;
      for (let d = 0; node && d < 8; d += 1, node = node.parentElement) {
        const r = node.getBoundingClientRect();
        if (r.width >= 280 && r.height >= 45 && r.height <= 145) { best = node; break; }
      }
      if (!best) return false; best.setAttribute("data-ai-svodki-card", markerValue); return true;
    }, marker);
    if (!ok) throw new Error(`Не определена плашка «${name}».`);
    if (waitLogged) logger.log(`Плашка «${name}» загрузилась; продолжаю.`);
    return modal.locator(`[data-ai-svodki-card="${marker}"]`).first();
  }
}
async function alreadyAdded(card, name) {
  return card.evaluate((el, expected) => {
    const norm = (v) => String(v || "").replace(/\s+/g, " ").trim();
    let title = null, area = Infinity;
    for (const candidate of [el, ...el.querySelectorAll("*")]) {
      if (norm(candidate.innerText) !== norm(expected)) continue;
      const r = candidate.getBoundingClientRect(), a = r.width * r.height; if (r.width > 0 && r.height > 0 && a < area) { title = candidate; area = a; }
    }
    const color = title ? getComputedStyle(title).color : "";
    const m = /rgba?\([^,]+,[^,]+,[^,]+(?:,\s*([0-9.]+))?\)/i.exec(color);
    const alpha = m?.[1] === undefined ? 1 : Number(m[1]);
    const explicit = Boolean(el.querySelector('[aria-checked="true"],[aria-selected="true"],[aria-pressed="true"],[data-state="checked"],input:checked'));
    // Live-verified 2026-08-29: already-added Dzen tile title is rgba(6, 6, 15, 0.6).
    return { selected: explicit || (Number.isFinite(alpha) && alpha <= 0.70), explicit, alpha, color };
  }, name);
}
async function waitAccepted(page, card, name, before) {
  const deadline = Date.now() + 8_000;
  while (Date.now() < deadline) {
    const body = normalizeText(await page.locator("body").innerText().catch(() => ""));
    if (/добавлен[ао]? в подборку|публикаци[яи].*добавлен/i.test(body)) return "success-text";
    const after = await alreadyAdded(card, name).catch(() => null);
    if (after?.selected && !before.selected) return "muted-tile";
    await page.waitForTimeout(300);
  }
  return null;
}
async function closeOverlay(page) { await page.keyboard.press("Escape").catch(() => {}); await page.waitForTimeout(250); }
async function processTarget(page, config, dateKey, target, apply, logger) {
  await openPublications(page); await ensureAllFilter(page);
  const title = titleFor(target, dateKey); const row = await findPublicationRow(page, target, dateKey, logger);
  if (!row) return { status: "missing", title };
  const modal = await openCollectionModal(page, row, title);
  const card = await findCollectionCard(page, modal, target.collectionName, logger);
  const before = await alreadyAdded(card, target.collectionName);
  logger.log(`Подборка «${target.collectionName}»: already-selected=${before.selected}; title-color=${before.color}; title-alpha=${before.alpha}.`);
  if (!apply) { await closeOverlay(page); return { status: "dry-run", title }; }
  if (before.selected) { logger.log(`Уже в «${target.collectionName}». Повторный клик НЕ выполняю.`); await closeOverlay(page); return { status: "already-added", title }; }
  const box = await card.boundingBox(); if (!box) throw new Error(`Нет геометрии плашки «${target.collectionName}».`);
  const x = box.x + box.width * 0.72, y = box.y + box.height * 0.50;
  logger.log(`APPLY: один клик по плашке «${target.collectionName}»: x=${Math.round(x)}, y=${Math.round(y)}.`);
  await page.mouse.click(x, y);
  const signal = await waitAccepted(page, card, target.collectionName, before);
  if (!signal) throw new Error(`После единственного клика по «${target.collectionName}» нет подтверждения успеха. Повторный клик запрещён.`);
  logger.log(`Добавление подтверждено: «${title}» -> «${target.collectionName}», signal=${signal}.`);
  await closeOverlay(page); return { status: "added", title, signal };
}
function runSelfTest() {
  const date = "2026-08-29";
  if (titleFor(TARGETS[0], date) !== "ИИ-Сводка на 29 августа 2026 | Подпишись, чтоб получать свежее!") throw new Error("video title");
  if (titleFor(TARGETS[1], date) !== "ИИ-Сводка на 29 августа 2026") throw new Error("digest title");
  const job = { dzenCollections: { video: { status: "ADDED" }, digest: { status: "PENDING" } } };
  if (collectionsStatus(job) !== "PARTIAL" || collectionsComplete(job)) throw new Error("partial state");
  job.dzenCollections.digest.status = "ADDED"; if (!collectionsComplete(job)) throw new Error("complete state");
  if (classifyCollectionCardLookup(0, false) !== "WAIT") throw new Error("loading modal must wait");
  if (classifyCollectionCardLookup(1, false) !== "FOUND") throw new Error("one collection must be found");
  if (classifyCollectionCardLookup(0, true) !== "TIMEOUT") throw new Error("empty modal after deadline must time out");
  if (classifyCollectionCardLookup(2, false) !== "AMBIGUOUS") throw new Error("duplicate collection matches must fail closed");
  console.log("Dzen collections contract self-test: OK");
}
async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv); if (args.selfTest) return runSelfTest();
  if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  const config = loadJson(CONFIG_PATH); if (args.visible) config.minimizeBrowserWindow = false;
  if (!config.stateFile) throw new Error("В config.json не задан stateFile.");
  const logger = createLogger(config), dateKey = args.date || formatDateKey(new Date(), config.timeZone || "Europe/Moscow");
  const state = loadJson(config.stateFile, { jobs: {} }), job = findJobForDate(state, dateKey);
  if (!job) { logger.log(`Нет job за ${dateKey}. Браузер НЕ открываю.`); return; }
  const pending = TARGETS.filter((t) => !targetIsAdded(job, t.key));
  if (!pending.length) { logger.log(`dzenCollections=COMPLETE за ${dateKey}. Браузер НЕ открываю.`); return; }
  logger.log(`=== START collections date=${dateKey}; pending=${pending.map((t) => t.key).join(",")} ===`);
  const browserSession = require("./browser-session"); let session = null;
  try {
    session = await browserSession.launchRobotBrowser(config, { log: (m) => logger.log(m) });
    for (const target of pending) {
      try {
        const result = await processTarget(session.primaryPage, config, dateKey, target, args.apply, logger);
        if (!args.apply) continue;
        if (["added", "already-added"].includes(result.status)) {
          const status = updateCollectionTarget(config, state, job, target, { status: "ADDED", title: result.title, confirmedAt: new Date().toISOString(), confirmedBy: result.status === "added" ? "ui-success-after-click" : "existing-muted-tile", lastResult: result.status, lastAttemptAt: new Date().toISOString(), lastError: null, lastErrorAt: null });
          logger.log(`STATE: ${target.key}=ADDED; dzenCollections=${status}.`);
        } else if (result.status === "missing") {
          const status = updateCollectionTarget(config, state, job, target, { status: "PENDING", title: result.title, lastResult: "missing", lastAttemptAt: new Date().toISOString(), lastError: null, lastErrorAt: null });
          logger.log(`STATE: ${target.key}=PENDING; dzenCollections=${status}.`);
        }
      } catch (error) {
        if (args.apply) updateCollectionTarget(config, state, job, target, { status: "PENDING", lastResult: "error", lastAttemptAt: new Date().toISOString(), lastError: error.message, lastErrorAt: new Date().toISOString() });
        throw error;
      }
    }
    logger.log(`=== END collections SUCCESS date=${dateKey}; state=${args.apply ? collectionsStatus(job) : "DRY-RUN"} ===`);
  } catch (error) {
    const shot = session?.primaryPage ? await screenshot(session.primaryPage, config, dateKey, "ERROR") : null;
    logger.fatal(`Этап остановлен: ${error.message}${shot ? `. Скриншот: ${shot}` : ""}`, error); process.exitCode = 1;
  } finally {
    if (session) { await browserSession.closeRobotBrowser(session, config).catch((e) => { logger.fatal(`Не удалось закрыть браузер: ${e.message}`, e); process.exitCode = 1; }); logger.log("Роботизированный Яндекс.Браузер закрыт."); }
  }
}

module.exports = { COLLECTION_CARD_TIMEOUT_MS, TARGETS, classifyCollectionCardLookup, collectionsComplete, collectionsStatus, findJobForDate, main, parseDateKey, targetIsAdded, titleFor, updateCollectionTarget };
if (require.main === module) main().catch((e) => { console.error(e.stack || e.message); process.exitCode = 1; });
