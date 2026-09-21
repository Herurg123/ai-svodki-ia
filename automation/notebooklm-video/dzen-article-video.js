"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const logUtils = require("./log-utils");
const history = require("./history-utils");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const PUBLICATIONS_URL = "https://dzen.ru/profile/editor/rybv/publications";
const HEADING_TEXT = "Видеосводка";
const ANCHOR_TEXT = "Мировые лидеры ИИ";
const MONTHS = [
  "января", "февраля", "марта", "апреля", "мая", "июня",
  "июля", "августа", "сентября", "октября", "ноября", "декабря",
];
const MONTHS_SHORT = [
  "янв", "фев", "мар", "апр", "мая", "июн",
  "июл", "авг", "сен", "окт", "ноя", "дек",
];
const TERMINAL_STATUSES = new Set(["COMPLETE", "SKIPPED_EXISTING", "ERROR"]);
const VERIFY_ONLY_PHASES = new Set(["PUBLISH_ARMED", "CONFIRMATION_ARMED", "CLICKED_UNVERIFIED"]);
const PREVIEW_TIMEOUT_MS = 60_000;
const EXISTING_PREVIEW_TIMEOUT_MS = 12_000;
const TOOLBAR_TIMEOUT_MS = 8_000;
const AUTOSAVE_TIMEOUT_MS = 60_000;
const AUTOSAVE_STABLE_MS = 8_000;
const POST_PUBLISH_MIN_HOLD_MS = 12_000;
const POST_PUBLISH_STABLE_MS = 5_000;
const POST_PUBLISH_TIMEOUT_MS = 60_000;
const PUBLISH_DIALOG_TIMEOUT_MS = 20_000;
const PUBLISH_DIALOG_GONE_TIMEOUT_MS = 30_000;
const PUBLIC_VERIFY_TIMEOUT_MS = 90_000;

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}

function normalizeText(value) {
  return String(value || "")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
    .replace(/[\u00A0\u202F]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function parseDateKey(value) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(value || ""));
  if (!match) throw new Error(`Некорректная дата: ${value}`);
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(Date.UTC(year, month - 1, day));
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) {
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
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: timeZone || "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const out = {};
  for (const part of parts) {
    if (["year", "month", "day"].includes(part.type)) out[part.type] = part.value;
  }
  return `${out.year}-${out.month}-${out.day}`;
}

function createLogger(config) {
  const write = (prefix, message, error = null) => {
    const suffix = error && error.stack ? `\r\n${error.stack}` : "";
    const line = `[${logUtils.formatTime(config.timeZone || "Europe/Moscow")}] ${prefix}${message}${suffix}`;
    if (prefix.includes("!!!")) console.error(line);
    else console.log(line);
    logUtils.appendRegularLine(config, line);
    if (prefix.includes("!!!") && config.errorLog && config.errorLog !== config.regularLog) {
      logUtils.appendErrorLine(config, line);
    }
  };
  return {
    log: (message) => write("DZEN-ARTICLE-VIDEO: ", message),
    warn: (message) => write("DZEN-ARTICLE-VIDEO WARN: ", message),
    fatal: (message, error = null) => write("DZEN-ARTICLE-VIDEO !!!: ", message, error),
  };
}

function parseArgs(argv) {
  const args = {
    date: null,
    apply: false,
    visible: false,
    selfTest: false,
    recoverPreEditLinkError: false,
  };
  for (const arg of argv) {
    if (arg === "--apply") args.apply = true;
    else if (arg === "--visible") args.visible = true;
    else if (arg === "--self-test") args.selfTest = true;
    else if (arg === "--recover-pre-edit-link-error") args.recoverPreEditLinkError = true;
    else if (arg.startsWith("--date=")) {
      args.date = arg.slice("--date=".length).trim();
      parseDateKey(args.date);
    } else {
      throw new Error(`Неизвестный параметр: ${arg}`);
    }
  }
  return args;
}

function findJobForDate(state, dateKey) {
  const jobs = Object.values((state && state.jobs) || {}).filter(
    (job) => job && job.date === dateKey
  );
  jobs.sort((a, b) =>
    String(b.updatedAt || b.downloadedAt || "").localeCompare(
      String(a.updatedAt || a.downloadedAt || "")
    )
  );
  return jobs[0] || null;
}

function ensureArticleVideoState(job) {
  if (!job.dzenArticleVideo || typeof job.dzenArticleVideo !== "object") {
    job.dzenArticleVideo = { status: "PENDING", phase: "PENDING" };
  }
  if (!job.dzenArticleVideo.status) job.dzenArticleVideo.status = "PENDING";
  if (!job.dzenArticleVideo.phase) job.dzenArticleVideo.phase = "PENDING";
  return job.dzenArticleVideo;
}

function updateArticleVideo(config, state, job, fields) {
  const now = new Date().toISOString();
  job.dzenArticleVideo = {
    ...(job.dzenArticleVideo || {}),
    ...fields,
    updatedAt: now,
  };
  job.updatedAt = now;
  history.saveStateWithRetention(config, state);
  return job.dzenArticleVideo;
}

function markPrePublishError(config, state, job, error) {
  const now = new Date().toISOString();
  return updateArticleVideo(config, state, job, {
    status: "ERROR",
    phase: "ERROR",
    lastError: error.message,
    lastErrorAt: now,
    lastAttemptAt: now,
  });
}

function isLoginUrl(url) {
  const value = String(url || "").toLowerCase();
  return [
    "passport.yandex",
    "sso.dzen.ru",
    "dzen.ru/login",
    "oauth.yandex",
    "auth?retpath",
  ].some((part) => value.includes(part));
}

async function screenshot(page, config, dateKey, label) {
  const dir = config.screenshotsDir || path.join(ROOT, "screenshots");
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const file = path.join(dir, `dzen-article-video-${dateKey}-${label}-${stamp}.png`);
  await page.screenshot({ path: file, fullPage: true }).catch(() => {});
  return file;
}

function psEncoded(command) {
  return Buffer.from(command, "utf16le").toString("base64");
}

function runPowerShell(command, timeoutMs = 15_000) {
  if (process.platform !== "win32") {
    return Promise.reject(new Error("Clipboard flow доступен только в Windows."));
  }
  return new Promise((resolve, reject) => {
    let stdout = "";
    let stderr = "";
    let settled = false;
    const child = spawn(
      "powershell.exe",
      [
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        psEncoded(command),
      ],
      { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] }
    );
    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve(value);
    };
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.once("error", (error) => finish(error));
    child.once("close", (code) => {
      if (code !== 0) {
        finish(new Error(stderr.trim() || `PowerShell завершился с кодом ${code}`));
      } else {
        finish(null, stdout.trim());
      }
    });
    const timer = setTimeout(() => {
      try { child.kill(); } catch {}
      finish(new Error(`PowerShell clipboard operation не завершилась за ${timeoutMs} мс.`));
    }, timeoutMs);
  });
}

async function readClipboardText() {
  const command = [
    "$ErrorActionPreference = 'Stop'",
    "$v = Get-Clipboard -Raw -Format Text",
    "$bytes = [System.Text.Encoding]::UTF8.GetBytes([string]$v)",
    "[Convert]::ToBase64String($bytes)",
  ].join("\r\n");
  const encoded = await runPowerShell(command);
  return Buffer.from(encoded || "", "base64").toString("utf8");
}

async function writeClipboardText(value) {
  const encoded = Buffer.from(String(value), "utf8").toString("base64");
  const command = [
    "$ErrorActionPreference = 'Stop'",
    `$b64 = '${encoded}'`,
    "$bytes = [Convert]::FromBase64String($b64)",
    "$v = [System.Text.Encoding]::UTF8.GetString($bytes)",
    "Set-Clipboard -Value $v",
    "Write-Output 'OK'",
  ].join("\r\n");
  await runPowerShell(command);
}

function expectedPublicationUrlPattern(kind) {
  return kind === "video"
    ? /^https:\/\/dzen\.ru\/video\/watch\/[A-Za-z0-9_-]+(?:[?#].*)?$/
    : /^https:\/\/dzen\.ru\/a\/[A-Za-z0-9_-]+(?:[?#].*)?$/;
}

function expectedPublicationUrlFromCandidates(candidates, kind) {
  const pattern = expectedPublicationUrlPattern(kind);
  for (const candidate of candidates || []) {
    const value = String(
      candidate && candidate.value !== undefined ? candidate.value : candidate || ""
    ).trim();
    if (pattern.test(value)) {
      return {
        value,
        source: candidate && candidate.source ? String(candidate.source) : "candidate",
      };
    }
  }
  return null;
}

async function collectPublicationRowUrlCandidates(row) {
  return row.evaluate((root) => {
    const out = [];
    const seen = new Set();
    const add = (value, source) => {
      const text = String(value || "").trim();
      if (!text || seen.has(`${source}\n${text}`)) return;
      seen.add(`${source}\n${text}`);
      out.push({ value: text, source });
    };

    for (const node of [root, ...root.querySelectorAll("*")]) {
      if (node.tagName === "A" && node.href) add(node.href, "row-anchor-href");
      for (const attr of [...(node.attributes || [])]) {
        if (!attr || !attr.value) continue;
        if (/dzen\.ru\/(?:a\/|video\/watch\/)/i.test(attr.value)) {
          try {
            add(new URL(attr.value, location.href).href, `row-attr:${attr.name}`);
          } catch {
            add(attr.value, `row-attr:${attr.name}`);
          }
        }
      }
    }
    return out.slice(0, 40);
  });
}

async function armPageClipboardCapture(page) {
  return page.evaluate(() => {
    const KEY = "__AI_AV_CLIPBOARD_CAPTURE__";
    const prior = window[KEY];
    if (prior && prior.armed) {
      prior.values = [];
      prior.errors = [];
      prior.armedAt = Date.now();
      return { ok: true, reused: true, errors: prior.errors };
    }

    const state = { armed: true, armedAt: Date.now(), values: [], errors: [] };
    window[KEY] = state;
    const record = (value, source) => {
      const text = String(value || "").trim();
      if (!text) return;
      state.values.push({ value: text, source, at: Date.now() });
      if (state.values.length > 30) state.values.splice(0, state.values.length - 30);
    };

    document.addEventListener("copy", (event) => {
      try {
        const direct = event && event.clipboardData
          ? event.clipboardData.getData("text/plain")
          : "";
        record(
          direct || String(window.getSelection ? window.getSelection() : ""),
          "copy-event"
        );
      } catch (error) {
        state.errors.push(
          `copy-event:${error && error.message ? error.message : error}`
        );
      }
    }, true);

    const clipboard = navigator.clipboard;
    if (clipboard) {
      try {
        if (typeof clipboard.writeText === "function") {
          const originalWriteText = clipboard.writeText.bind(clipboard);
          const wrappedWriteText = (value) => {
            record(value, "navigator.clipboard.writeText");
            return originalWriteText(value);
          };
          try {
            Object.defineProperty(clipboard, "writeText", {
              configurable: true,
              value: wrappedWriteText,
            });
          } catch {
            clipboard.writeText = wrappedWriteText;
          }
        }
      } catch (error) {
        state.errors.push(
          `writeText-hook:${error && error.message ? error.message : error}`
        );
      }

      try {
        if (typeof clipboard.write === "function") {
          const originalWrite = clipboard.write.bind(clipboard);
          const wrappedWrite = (items) => {
            try {
              for (const item of Array.from(items || [])) {
                if (!item || !Array.from(item.types || []).includes("text/plain")) continue;
                Promise.resolve(item.getType("text/plain"))
                  .then((blob) => blob.text())
                  .then((text) => record(text, "navigator.clipboard.write:text/plain"))
                  .catch((error) => state.errors.push(
                    `clipboard-item:${error && error.message ? error.message : error}`
                  ));
              }
            } catch (error) {
              state.errors.push(
                `write-hook-capture:${error && error.message ? error.message : error}`
              );
            }
            return originalWrite(items);
          };
          try {
            Object.defineProperty(clipboard, "write", {
              configurable: true,
              value: wrappedWrite,
            });
          } catch {
            clipboard.write = wrappedWrite;
          }
        }
      } catch (error) {
        state.errors.push(
          `write-hook:${error && error.message ? error.message : error}`
        );
      }
    }

    return { ok: true, reused: false, errors: state.errors.slice() };
  });
}

async function readPageClipboardCapture(page) {
  return page.evaluate(() => {
    const state = window.__AI_AV_CLIPBOARD_CAPTURE__;
    if (!state) return { values: [], errors: ["capture-not-armed"] };
    return {
      values: Array.isArray(state.values) ? state.values.slice(-30) : [],
      errors: Array.isArray(state.errors) ? state.errors.slice(-20) : [],
    };
  });
}

async function openPublications(page) {
  await page.goto(PUBLICATIONS_URL, { waitUntil: "domcontentloaded", timeout: 60_000 });
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (isLoginUrl(page.url())) {
      throw new Error(`Дзен перенаправил на URL авторизации: ${page.url()}`);
    }
    const body = normalizeText(await page.locator("body").innerText().catch(() => ""));
    if (body.includes("Публикации") && body.includes("Опубликованные")) return;
    await page.waitForTimeout(400);
  }
  throw new Error("Не подтверждена Studio -> Публикации.");
}

async function ensurePublicationFilter(page, label) {
  const radio = page.locator(`input[type="radio"][aria-label="${label}"]`).first();
  if (!(await radio.count().catch(() => 0))) {
    throw new Error(`Не найден реальный radio filter «${label}».`);
  }
  if (!(await radio.isChecked().catch(() => false))) {
    await radio.evaluate((el) => el.click());
    await page.waitForTimeout(600);
  }
  if (!(await radio.isChecked().catch(() => false))) {
    throw new Error(`Фильтр «${label}» не перешёл в checked=true.`);
  }
}

async function findPublicationRow(page, dateKey, kind, logger) {
  const prefix = `ИИ-Сводка на ${formatRussianLongDate(dateKey)}`;
  const dayLabel = shortDateLabel(dateKey);
  const wantVideo = kind === "video";
  const deadline = Date.now() + 15_000;

  while (Date.now() < deadline) {
    const rows = await page.evaluate(({ prefix, dayLabel }) => {
      const norm = (v) => String(v || "").replace(/\s+/g, " ").trim();
      const visible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
      };
      const out = [];
      const seen = new Set();
      for (const el of [...document.querySelectorAll("a,div,span,p,h1,h2,h3")]) {
        if (!visible(el)) continue;
        const txt = norm(el.innerText || el.textContent);
        if (!txt.includes(prefix) || txt.length > 280) continue;
        let node = el;
        for (let depth = 0; node && depth < 15; depth += 1, node = node.parentElement) {
          if (!visible(node)) continue;
          const r = node.getBoundingClientRect();
          const rowText = norm(node.innerText || node.textContent);
          if (
            r.width < 650 ||
            r.height < 45 ||
            r.height > 240 ||
            !rowText.includes(prefix) ||
            !rowText.includes(dayLabel)
          ) continue;
          const controls = [...node.querySelectorAll('button,[role="button"]')]
            .filter(visible)
            .filter((control) => control.getBoundingClientRect().left >= r.left + r.width * 0.62);
          if (!controls.length || seen.has(node)) continue;
          seen.add(node);
          const titles = [...node.querySelectorAll("a,div,span,p,h1,h2,h3")]
            .filter(visible)
            .map((item) => norm(item.innerText || item.textContent))
            .filter((item) => item.startsWith(prefix) && item.length <= 190)
            .sort((a, b) => a.length - b.length);
          const title = titles[0] || txt;
          const marker = `ai-av-row-${out.length}-${Date.now()}`;
          node.setAttribute("data-ai-av-row", marker);
          out.push({
            marker,
            title,
            videoLike: rowText.includes(`${prefix} |`) || title.includes("|"),
          });
          break;
        }
      }
      return out;
    }, { prefix, dayLabel });

    const matches = rows.filter((row) => row.videoLike === wantVideo);
    if (matches.length === 1) {
      logger.log(`Найдена публикация текущей даты: «${matches[0].title}».`);
      return page.locator(`[data-ai-av-row="${matches[0].marker}"]`).first();
    }
    if (matches.length > 1) {
      throw new Error(`Для ${kind === "video" ? "видео" : "статьи"} найдено несколько строк текущей даты.`);
    }
    await page.waitForTimeout(400);
  }

  throw new Error(
    `Не найдена same-day ${kind === "video" ? "видеопубликация" : "статья"} «${prefix}${wantVideo ? " | …" : ""}».`
  );
}

async function rightmostMenuButton(row) {
  const controls = row.locator('button,[role="button"]');
  let chosen = null;
  let maxX = -Infinity;
  for (let i = 0; i < await controls.count().catch(() => 0); i += 1) {
    const item = controls.nth(i);
    if (!(await item.isVisible().catch(() => false))) continue;
    const box = await item.boundingBox().catch(() => null);
    if (box && box.x > maxX) {
      maxX = box.x;
      chosen = item;
    }
  }
  if (!chosen) throw new Error("У строки публикации не найдено меню «…».");
  return chosen;
}

async function visibleExactText(page, text) {
  const matches = page.getByText(text, { exact: true });
  const visible = [];
  for (let i = 0; i < await matches.count().catch(() => 0); i += 1) {
    const item = matches.nth(i);
    if (await item.isVisible().catch(() => false)) visible.push(item);
  }
  if (visible.length === 1) return visible[0];
  if (visible.length > 1) {
    throw new Error(`Найдено несколько видимых exact элементов «${text}».`);
  }
  return null;
}

async function openRowMenuAction(page, row, actionText, options = {}) {
  const menuButton = await rightmostMenuButton(row);
  await menuButton.click({ timeout: 10_000 });
  const deadline = Date.now() + 10_000;
  let action = null;
  while (Date.now() < deadline && !action) {
    action = await visibleExactText(page, actionText).catch(() => null);
    if (!action) await page.waitForTimeout(200);
  }
  if (!action) throw new Error(`В меню публикации не найден пункт «${actionText}».`);

  if (!options.expectNewPage) {
    await action.click({ timeout: 10_000 });
    return page;
  }

  const context = page.context();
  const before = new Set(context.pages());
  await action.click({ timeout: 10_000 });
  const newPage = await context.waitForEvent("page", { timeout: 4_000 }).catch(() => null);
  if (newPage) {
    await newPage.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {});
    return newPage;
  }
  await page.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {});
  const after = context.pages().filter((p) => !before.has(p) && !p.isClosed());
  return after[0] || page;
}

async function copyPublicationUrl(page, row, kind, logger) {
  const directCandidates = await collectPublicationRowUrlCandidates(row).catch(() => []);
  const direct = expectedPublicationUrlFromCandidates(directCandidates, kind);
  if (direct) {
    if (logger) {
      logger.log(
        `Public ${kind} URL получен напрямую из same-day Studio row (${direct.source}), clipboard не требуется.`
      );
    }
    return direct.value;
  }

  const captureArm = await armPageClipboardCapture(page).catch((error) => ({
    ok: false,
    errors: [`capture-arm:${error && error.message ? error.message : error}`],
  }));

  let before = "";
  let beforeReadError = null;
  try {
    before = (await readClipboardText()).trim();
  } catch (error) {
    beforeReadError = error && error.message ? error.message : String(error);
  }

  await openRowMenuAction(page, row, "Скопировать ссылку");
  const pattern = expectedPublicationUrlPattern(kind);
  const deadline = Date.now() + 8_000;
  let lastPageCapture = { values: [], errors: captureArm.errors || [] };
  let lastClipboard = before;
  let lastClipboardError = beforeReadError;

  while (Date.now() < deadline) {
    lastPageCapture = await readPageClipboardCapture(page).catch((error) => ({
      values: [],
      errors: [`capture-read:${error && error.message ? error.message : error}`],
    }));
    const captured = expectedPublicationUrlFromCandidates(lastPageCapture.values, kind);
    if (captured) {
      if (logger) {
        logger.log(
          `Public ${kind} URL перехвачен в browser page (${captured.source}); OS clipboard не используется как источник истины.`
        );
      }
      return captured.value;
    }

    try {
      const value = (await readClipboardText()).trim();
      lastClipboard = value;
      lastClipboardError = null;
      if (pattern.test(value) && (!pattern.test(before) || value !== before)) {
        if (logger) logger.log(`Public ${kind} URL подтверждён через Windows clipboard.`);
        return value;
      }
    } catch (error) {
      lastClipboardError = error && error.message ? error.message : String(error);
    }

    await page.waitForTimeout(200);
  }

  throw new Error(
    `«Скопировать ссылку» не дало ожидаемый ${kind} URL ни через Studio DOM/page-capture, ни через Windows clipboard. ` +
    `clipboardBefore=${JSON.stringify(before.slice(0, 80))}; clipboardAfter=${JSON.stringify(lastClipboard.slice(0, 120))}; ` +
    `clipboardError=${JSON.stringify(lastClipboardError)}; pageCaptureErrors=${JSON.stringify((lastPageCapture.errors || []).slice(-5))}`
  );
}

async function articleOnboardingState(page) {
  return page.evaluate(() => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
    };

    const candidates = [...document.querySelectorAll("div,section,aside,[role='dialog']")]
      .filter(visible)
      .map((el) => ({ el, box: el.getBoundingClientRect(), text: norm(el.innerText || el.textContent) }))
      .filter(({ box, text }) =>
        box.width >= 420 &&
        box.width <= Math.max(1100, window.innerWidth * 0.95) &&
        box.height >= 180 &&
        box.height <= Math.max(720, window.innerHeight * 0.90) &&
        text.includes("Пример статьи") &&
        (text.includes("Статья — это") || text.includes("Статья - это") || text.startsWith("Статья "))
      )
      .sort((a, b) => (a.box.width * a.box.height) - (b.box.width * b.box.height));

    if (!candidates.length) return { visible: false };

    const target = candidates[0];
    const marker = `ai-av-onboarding-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    target.el.setAttribute("data-ai-av-onboarding", marker);

    const descendants = [...target.el.querySelectorAll("*")].filter(visible);
    const closeCandidates = descendants.map((el) => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      const name = norm([
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
        el.innerText,
        el.textContent,
      ].filter(Boolean).join(" "));
      const interactive =
        el.tagName === "BUTTON" ||
        el.getAttribute("role") === "button" ||
        style.cursor === "pointer";
      const nearTopRight =
        box.width > 0 &&
        box.height > 0 &&
        box.width <= 80 &&
        box.height <= 80 &&
        box.left >= target.box.left + target.box.width * 0.72 &&
        box.top <= target.box.top + target.box.height * 0.25;
      const namedClose = /^(×|✕|✖|x)$/i.test(name) || /закрыть|close/i.test(name);
      return { el, box, interactive, nearTopRight, namedClose };
    }).filter((item) => item.nearTopRight && (item.interactive || item.namedClose));

    closeCandidates.sort((a, b) => {
      if (a.namedClose !== b.namedClose) return a.namedClose ? -1 : 1;
      return (b.box.left + b.box.width) - (a.box.left + a.box.width);
    });

    let closeMarker = null;
    if (closeCandidates.length) {
      closeMarker = `ai-av-onboarding-close-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      closeCandidates[0].el.setAttribute("data-ai-av-onboarding-close", closeMarker);
    }

    return {
      visible: true,
      marker,
      closeMarker,
      box: {
        x: target.box.x,
        y: target.box.y,
        width: target.box.width,
        height: target.box.height,
      },
    };
  });
}

async function closeArticleOnboardingIfPresent(page, logger) {
  let state = await articleOnboardingState(page);
  if (!state.visible) return;

  // Dzen's guide behaved like a modal in the 20.09.2026 live editor. Escape is
  // the least invasive first attempt because it does not touch article content.
  await page.keyboard.press("Escape").catch(() => {});
  await page.waitForTimeout(350);
  state = await articleOnboardingState(page);
  if (!state.visible) {
    logger.log("Onboarding редактора «Пример статьи» закрыт клавишей Escape.");
    return;
  }

  if (!state.closeMarker) {
    throw new Error(
      "Виден onboarding «Пример статьи», но безопасный close-control не найден. " +
      "Редактор не трогаю."
    );
  }

  const close = page.locator(`[data-ai-av-onboarding-close="${state.closeMarker}"]`).first();
  await physicalClickVerified(page, close, "Onboarding close");
  await page.waitForTimeout(350);

  state = await articleOnboardingState(page);
  if (state.visible) {
    throw new Error("После одного подтверждённого close-click onboarding «Пример статьи» остался открыт.");
  }
  logger.log("Закрыт onboarding редактора «Пример статьи» одним подтверждённым click.");
}

async function waitForEditor(page) {
  const deadline = Date.now() + 30_000;
  while (Date.now() < deadline) {
    if (isLoginUrl(page.url())) throw new Error(`Дзен перенаправил на URL авторизации: ${page.url()}`);
    const content = page.locator('div[contenteditable="true"].public-DraftEditor-content');
    if (await content.count().catch(() => 0)) {
      for (let i = 0; i < await content.count(); i += 1) {
        if (await content.nth(i).isVisible().catch(() => false)) return content.nth(i);
      }
    }
    await page.waitForTimeout(300);
  }
  throw new Error("Не найден видимый Draft.js editor content.");
}

async function markExactDraftBlock(page, text, markerPrefix) {
  return page.evaluate(({ text, markerPrefix }) => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    };

    // Dzen can keep more than one visible Draft.js root in the DOM (for example,
    // article guide/onboarding + the real editor). Editor count is therefore not
    // an identity proof. Resolve by the unique exact block across all visible roots.
    const editors = [...document.querySelectorAll('div[contenteditable="true"].public-DraftEditor-content')].filter(visible);
    const matches = [];
    let totalBlocks = 0;
    for (let editorIndex = 0; editorIndex < editors.length; editorIndex += 1) {
      const blocks = [...editors[editorIndex].querySelectorAll('[data-block="true"]')].filter(visible);
      totalBlocks += blocks.length;
      for (const block of blocks) {
        if (norm(block.innerText || block.textContent) === text) {
          matches.push({ editorIndex, block });
        }
      }
    }

    if (matches.length !== 1) {
      return {
        ok: false,
        reason: `block-count=${matches.length};editor-count=${editors.length}`,
        totalBlocks,
      };
    }

    const marker = `${markerPrefix}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    matches[0].block.setAttribute("data-ai-av-block", marker);
    return {
      ok: true,
      marker,
      editorCount: editors.length,
      editorIndex: matches[0].editorIndex,
      totalBlocks,
    };
  }, { text, markerPrefix });
}

async function exactDraftBlock(page, text, markerPrefix = "block") {
  const result = await markExactDraftBlock(page, text, markerPrefix);
  if (!result.ok) {
    throw new Error(`Не удалось однозначно найти Draft.js block «${text}» (${result.reason}).`);
  }
  return page.locator(`[data-ai-av-block="${result.marker}"]`).first();
}

async function maybeExactDraftBlock(page, text, markerPrefix = "maybe") {
  const result = await markExactDraftBlock(page, text, markerPrefix);
  if (!result.ok) {
    if (/block-count=0/.test(result.reason || "")) return null;
    throw new Error(`Неоднозначный Draft.js block «${text}» (${result.reason}).`);
  }
  return page.locator(`[data-ai-av-block="${result.marker}"]`).first();
}

async function blockStyleSnapshot(block) {
  return block.evaluate((blockEl) => {
    const norm = (v) => String(v || "").replace(/\s+/g, " ").trim();
    const attrs = (el) => {
      const out = {};
      for (const attr of [...el.attributes]) {
        if (
          attr.name === "class" ||
          attr.name === "role" ||
          attr.name === "aria-level" ||
          attr.name.includes("block") ||
          attr.name.includes("type")
        ) out[attr.name] = attr.value;
      }
      return out;
    };
    let target = blockEl.querySelector("[data-text='true']") || blockEl;
    const style = getComputedStyle(target);
    const semantic = Boolean(
      target.closest("h2") ||
      blockEl.querySelector("h2") ||
      target.closest('[role="heading"][aria-level="2"]') ||
      blockEl.querySelector('[role="heading"][aria-level="2"]')
    );
    const all = [blockEl, ...blockEl.querySelectorAll("*")];
    const explicitType = all.some((el) => {
      const text = [
        el.tagName,
        el.className,
        ...[...el.attributes].map((a) => `${a.name}=${a.value}`),
      ].join(" ");
      return /\b(h2|header-two|heading-2|heading2|level-2)\b/i.test(text);
    });
    return {
      text: norm(blockEl.innerText || blockEl.textContent),
      semantic,
      explicitType,
      tag: blockEl.tagName,
      blockAttrs: attrs(blockEl),
      targetTag: target.tagName,
      fontSize: parseFloat(style.fontSize) || 0,
      fontWeight: parseInt(style.fontWeight, 10) || 0,
      lineHeight: parseFloat(style.lineHeight) || 0,
      marginTop: parseFloat(style.marginTop) || 0,
      marginBottom: parseFloat(style.marginBottom) || 0,
    };
  });
}

function headingMatchesOracle(candidate, oracle, before = null) {
  if (!candidate || !oracle) return false;
  if (oracle.semantic && !candidate.semantic) return false;
  if (oracle.explicitType && !candidate.explicitType && !candidate.semantic) return false;

  const fontClose =
    oracle.fontSize > 0 &&
    candidate.fontSize > 0 &&
    Math.abs(candidate.fontSize - oracle.fontSize) <= 1.5;
  const weightClose =
    !oracle.fontWeight ||
    !candidate.fontWeight ||
    Math.abs(candidate.fontWeight - oracle.fontWeight) <= 150;
  const changedFromPlain =
    !before ||
    candidate.semantic ||
    candidate.explicitType ||
    Math.abs(candidate.fontSize - before.fontSize) >= 3 ||
    Math.abs(candidate.fontWeight - before.fontWeight) >= 150;

  return fontClose && weightClose && changedFromPlain;
}

async function getEditorDiagnostics(page) {
  return page.evaluate(() => {
    const items = [...document.querySelectorAll('[contenteditable="true"]')].filter((el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    });
    return items.map((el) => ({
      tag: el.tagName,
      role: el.getAttribute("role"),
      className: String(el.className || ""),
      prosemirror: el.classList.contains("ProseMirror"),
      tiptap: el.classList.contains("tiptap"),
    }));
  });
}

async function detectOrphanZenVideoNearAnchor(page) {
  return page.evaluate(({ anchorText }) => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    };

    const editors = [...document.querySelectorAll('div[contenteditable="true"].public-DraftEditor-content')].filter(visible);
    const matches = [];
    for (let editorIndex = 0; editorIndex < editors.length; editorIndex += 1) {
      const editor = editors[editorIndex];
      const blocks = [...editor.querySelectorAll('[data-block="true"]')].filter(visible);
      const anchors = blocks.filter((block) => norm(block.innerText || block.textContent) === anchorText);
      if (anchors.length !== 1) continue;
      const anchor = anchors[0];
      const a = anchor.getBoundingClientRect();

      const videoLike = [...editor.querySelectorAll("*")].filter((el) => {
        if (!visible(el)) return false;
        const r = el.getBoundingClientRect();
        if (!(r.bottom <= a.top + 2 && a.top - r.bottom <= 180)) return false;
        if (r.width < 280 || r.height < 120) return false;
        const signature = [
          el.tagName,
          el.className,
          el.getAttribute("data-testid"),
          el.getAttribute("aria-label"),
          el.getAttribute("title"),
        ].filter(Boolean).join(" ");
        return /(typeYandexZenVideo|YandexZenVideo|zenEditorBlockEmbed|video|player|embed)/i.test(signature);
      });

      if (videoLike.length) {
        matches.push({
          editorIndex,
          count: videoLike.length,
          signatures: videoLike.slice(0, 5).map((el) => {
            const r = el.getBoundingClientRect();
            return {
              tag: el.tagName,
              className: String(el.className || "").slice(0, 180),
              width: r.width,
              height: r.height,
              distanceToAnchor: Math.round(a.top - r.bottom),
            };
          }),
        });
      }
    }

    return {
      found: matches.length > 0,
      matches,
    };
  }, { anchorText: ANCHOR_TEXT });
}

async function waitForExistingPreviewBetween(page, videoUrl) {
  const deadline = Date.now() + EXISTING_PREVIEW_TIMEOUT_MS;
  let last = null;
  while (Date.now() < deadline) {
    last = await detectVideoPreviewBetween(page, videoUrl);
    if (last.ok) return last;
    await page.waitForTimeout(400);
  }
  return last || { ok: false, reason: "existing-preview-timeout" };
}

async function inspectArticleVideoDraft(page, videoUrl, logger) {
  const anchor = await exactDraftBlock(page, ANCHOR_TEXT, "anchor-inspect");
  const oracle = await blockStyleSnapshot(anchor);
  const existing = await maybeExactDraftBlock(page, HEADING_TEXT, "existing");

  if (!existing) {
    const orphan = await detectOrphanZenVideoNearAnchor(page);
    if (orphan.found) {
      throw new Error(
        `Перед «${ANCHOR_TEXT}» найден video-like embed без exact текста «${HEADING_TEXT}». ` +
        `Состояние неоднозначно; новую вставку запрещаю. details=${JSON.stringify(orphan.matches.slice(0, 2))}`
      );
    }
    return { mode: "CLEAN", oracle };
  }

  const snapshot = await blockStyleSnapshot(existing);
  if (headingMatchesOracle(snapshot, oracle)) {
    logger.warn(`Exact H2 «${HEADING_TEXT}» уже существует. Ничего не меняю и не публикую.`);
    return {
      mode: "EXISTING_H2",
      exists: true,
      isHeading: true,
      oracle,
      snapshot,
    };
  }

  const preview = await waitForExistingPreviewBetween(page, videoUrl);
  if (preview && preview.ok) {
    logger.warn(
      `Обнаружен безопасно возобновляемый частичный draft: обычный текст «${HEADING_TEXT}» -> ` +
      `подтверждённый Dzen video preview -> «${ANCHOR_TEXT}». Повторная вставка запрещена; продолжаю только с форматирования H2.`
    );
    return {
      mode: "RESUMABLE_PARTIAL",
      oracle,
      snapshot,
      preview,
    };
  }

  throw new Error(
    `Найден exact текст «${HEADING_TEXT}», но он не H2 и подтверждённого Dzen video preview ` +
    `между ним и «${ANCHOR_TEXT}» нет (last=${JSON.stringify(preview)}). ` +
    "Состояние неоднозначно; повторная вставка и публикация запрещены."
  );
}

async function setCaretAtEnd(block) {
  await block.evaluate((el) => {
    const selection = window.getSelection();
    const range = document.createRange();
    range.selectNodeContents(el);
    range.collapse(false);
    selection.removeAllRanges();
    selection.addRange(range);
    el.scrollIntoView({ block: "center", inline: "nearest" });
  });
}

async function blockImmediatelyBeforeAnchor(page) {
  const result = await page.evaluate(({ anchorText }) => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    };

    const editors = [...document.querySelectorAll('div[contenteditable="true"].public-DraftEditor-content')].filter(visible);
    const anchors = [];
    for (let editorIndex = 0; editorIndex < editors.length; editorIndex += 1) {
      const blocks = [...editors[editorIndex].querySelectorAll('[data-block="true"]')].filter(visible);
      for (let index = 0; index < blocks.length; index += 1) {
        if (norm(blocks[index].innerText || blocks[index].textContent) === anchorText) {
          anchors.push({ editorIndex, blocks, index });
        }
      }
    }

    if (anchors.length !== 1) {
      return { ok: false, reason: `anchor-count=${anchors.length};editor-count=${editors.length}` };
    }

    const match = anchors[0];
    if (match.index <= 0) return { ok: false, reason: `anchor-index=${match.index}` };
    const prev = match.blocks[match.index - 1];
    const marker = `ai-av-prev-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    prev.setAttribute("data-ai-av-block", marker);
    return {
      ok: true,
      marker,
      text: norm(prev.innerText || prev.textContent),
      editorIndex: match.editorIndex,
    };
  }, { anchorText: ANCHOR_TEXT });
  if (!result.ok) throw new Error(`Не найден block непосредственно перед anchor (${result.reason}).`);
  return { locator: page.locator(`[data-ai-av-block="${result.marker}"]`).first(), text: result.text };
}

async function createPlainHeadingBeforeAnchor(page, logger) {
  let previous = await blockImmediatelyBeforeAnchor(page);

  if (previous.text) {
    logger.log("Ставлю caret в конец текстового блока непосредственно перед anchor и нажимаю Enter.");
    await setCaretAtEnd(previous.locator);
    await page.keyboard.press("Enter");
    await page.waitForTimeout(250);
    previous = await blockImmediatelyBeforeAnchor(page);
    if (previous.text) {
      throw new Error(
        `После Enter строка перед «${ANCHOR_TEXT}» не стала пустой (text=${JSON.stringify(previous.text)}).`
      );
    }
  } else {
    logger.log("Перед anchor уже есть пустая обычная строка; использую её и не создаю ещё одну.");
    await setCaretAtEnd(previous.locator);
  }

  await page.keyboard.insertText(HEADING_TEXT);
  await page.waitForTimeout(200);
  const heading = await exactDraftBlock(page, HEADING_TEXT, "plain-heading");
  const snapshot = await blockStyleSnapshot(heading);
  logger.log(`Обычный текст «${HEADING_TEXT}» создан перед anchor (tag=${snapshot.tag}, font=${snapshot.fontSize}px).`);

  await setCaretAtEnd(heading);
  await page.keyboard.press("Enter");
  await page.waitForTimeout(250);
  const blank = await blockImmediatelyBeforeAnchor(page);
  if (blank.text) {
    throw new Error(`После heading+Enter строка перед anchor не пустая: ${JSON.stringify(blank.text)}.`);
  }
  await setCaretAtEnd(blank.locator);
  return { heading, beforeStyle: snapshot };
}

async function detectVideoPreviewBetween(page, videoUrl) {
  return page.evaluate(({ headingText, anchorText, videoUrl }) => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    };
    const editors = [...document.querySelectorAll('div[contenteditable="true"].public-DraftEditor-content')].filter(visible);
    const matches = [];
    for (let editorIndex = 0; editorIndex < editors.length; editorIndex += 1) {
      const blocks = [...editors[editorIndex].querySelectorAll('[data-block="true"]')].filter(visible);
      const headings = blocks.filter((b) => norm(b.innerText || b.textContent) === headingText);
      const anchors = blocks.filter((b) => norm(b.innerText || b.textContent) === anchorText);
      if (headings.length === 1 && anchors.length === 1) {
        matches.push({ editor: editors[editorIndex], heading: headings[0], anchor: anchors[0], editorIndex });
      }
    }
    if (matches.length !== 1) {
      return { ok: false, reason: `editor-pair-count=${matches.length};editor-count=${editors.length}` };
    }
    const { editor, heading, anchor } = matches[0];

    const h = heading.getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    const top = h.bottom - 2;
    const bottom = a.top + 2;
    if (!(bottom > top)) return { ok: false, reason: "invalid-order" };

    const between = (el) => {
      const r = el.getBoundingClientRect();
      const cy = r.top + r.height / 2;
      return visible(el) && cy > top && cy < bottom;
    };

    const strong = [];
    for (const el of [...editor.querySelectorAll("video,iframe")].filter(between)) {
      const r = el.getBoundingClientRect();
      strong.push({ kind: el.tagName.toLowerCase(), width: r.width, height: r.height });
    }
    for (const el of [...editor.querySelectorAll('[contenteditable="false"],[data-block="true"]')].filter(between)) {
      const r = el.getBoundingClientRect();
      const txt = norm(el.innerText || el.textContent);
      if (r.width >= 280 && r.height >= 120 && txt !== headingText && txt !== anchorText && txt !== videoUrl) {
        strong.push({ kind: "atomic-large", width: r.width, height: r.height, text: txt.slice(0, 80) });
      }
    }
    for (const el of [...editor.querySelectorAll("*")].filter(between)) {
      const r = el.getBoundingClientRect();
      if (r.width < 280 || r.height < 120) continue;
      const signature = [
        el.tagName,
        el.className,
        el.getAttribute("data-testid"),
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
      ].filter(Boolean).join(" ");
      if (/(video|player|embed|preview)/i.test(signature)) {
        strong.push({ kind: "video-signature", width: r.width, height: r.height, signature: signature.slice(0, 120) });
      }
    }

    const editorText = norm(editor.innerText || editor.textContent);
    const urlStillPlain = editorText.includes(videoUrl);
    return {
      ok: strong.length > 0 && !urlStillPlain,
      reason: strong.length ? (urlStillPlain ? "url-still-plain" : "preview") : "no-strong-preview-signal",
      signals: strong.slice(0, 8),
      headingY: h.top,
      anchorY: a.top,
    };
  }, { headingText: HEADING_TEXT, anchorText: ANCHOR_TEXT, videoUrl });
}

async function prepareVideoClipboard(videoUrl, logger) {
  await writeClipboardText(videoUrl);
  const readBack = (await readClipboardText()).trim();
  if (readBack !== videoUrl) {
    throw new Error(
      `Windows clipboard не подтвердил video URL до изменения статьи. ` +
      `expected=${JSON.stringify(videoUrl)}; actual=${JSON.stringify(readBack.slice(0, 160))}`
    );
  }
  logger.log("Windows clipboard заранее подтверждён для video paste; editor ещё не изменён.");
}

async function pasteVideoAndWaitForPreview(page, videoUrl, logger, options = {}) {
  if (!options.clipboardPrepared) {
    await prepareVideoClipboard(videoUrl, logger);
  }
  logger.log("Выполняю реальный Ctrl+V подтверждённого video URL.");
  await page.keyboard.press("Control+V");

  const deadline = Date.now() + PREVIEW_TIMEOUT_MS;
  let last = null;
  while (Date.now() < deadline) {
    last = await detectVideoPreviewBetween(page, videoUrl);
    if (last.ok) {
      logger.log(`Dzen video preview/embed подтверждён между heading и anchor: ${JSON.stringify(last.signals.slice(0, 3))}.`);
      return last;
    }
    await page.waitForTimeout(500);
  }
  throw new Error(
    `URL не превратился в подтверждённый Dzen video preview/embed за ${PREVIEW_TIMEOUT_MS} мс ` +
    `(last=${JSON.stringify(last)}).`
  );
}

async function selectHeadingText(page) {
  const heading = await exactDraftBlock(page, HEADING_TEXT, "format-heading");
  await heading.scrollIntoViewIfNeeded({ timeout: 10_000 });
  await heading.click({ timeout: 10_000 });
  await page.keyboard.press("End");
  await page.keyboard.down("Shift");
  await page.keyboard.press("Home");
  await page.keyboard.up("Shift");
  await page.waitForTimeout(250);

  const selected = await page.evaluate(() => {
    const selection = window.getSelection();
    return selection ? String(selection.toString() || "").replace(/\s+/g, " ").trim() : "";
  });
  if (selected !== HEADING_TEXT) {
    throw new Error(`Не удалось выделить ровно «${HEADING_TEXT}»: selection=${JSON.stringify(selected)}.`);
  }
  return heading;
}

async function probeToolbarH2Control(page) {
  return page.evaluate(() => {
    const norm = (v) => String(v || "")
      .replace(/^["']|["']$/g, "")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 &&
        s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
    };
    const pseudoText = (el, pseudo) => {
      try {
        const value = getComputedStyle(el, pseudo).content;
        return value && value !== "none" && value !== "normal" ? norm(value) : "";
      } catch {
        return "";
      }
    };
    const signature = (el) => norm([
      el.getAttribute && el.getAttribute("aria-label"),
      el.getAttribute && el.getAttribute("title"),
      el.getAttribute && el.getAttribute("data-tooltip"),
      el.getAttribute && el.getAttribute("data-testid"),
      el.innerText,
      el.textContent,
      pseudoText(el, "::before"),
      pseudoText(el, "::after"),
    ].filter(Boolean).join(" "));

    const selection = window.getSelection();
    if (!selection || !selection.rangeCount) return { ok: false, reason: "selection-missing" };
    const range = selection.getRangeAt(0);
    const selected = norm(selection.toString());
    const selRect = range.getBoundingClientRect();
    if (!selRect || (!selRect.width && !selRect.height)) {
      return { ok: false, reason: `selection-rect-empty:${selected}` };
    }

    const sx = selRect.left + selRect.width / 2;
    const sy = selRect.top + selRect.height / 2;
    const candidates = [];
    const seen = new Set();

    const addCandidate = (element, rect, source) => {
      if (!element || !rect || rect.width <= 0 || rect.height <= 0) return;
      let chosen = element;
      let node = element;
      for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
        if (!visible(node)) continue;
        const r = node.getBoundingClientRect();
        const style = getComputedStyle(node);
        const interactive =
          node.tagName === "BUTTON" ||
          node.getAttribute("role") === "button" ||
          node.tabIndex >= 0 ||
          style.cursor === "pointer";
        if (interactive && r.width <= 160 && r.height <= 100) {
          chosen = node;
          break;
        }
      }
      if (!visible(chosen) || seen.has(chosen)) return;
      const cr = chosen.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const dist = Math.hypot(cx - sx, cy - sy);
      if (dist > 700) return;
      seen.add(chosen);
      candidates.push({ node: chosen, rect, controlRect: cr, dist, source });
    };

    // 1. Exact visible H2 text nodes. This catches toolbars whose clickable wrapper
    // does not itself expose innerText="H2".
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    let textNode = walker.nextNode();
    while (textNode) {
      if (norm(textNode.nodeValue) === "H2") {
        const textRange = document.createRange();
        textRange.selectNodeContents(textNode);
        const r = textRange.getBoundingClientRect();
        const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        if (hit && visible(hit)) addCandidate(hit, r, "text-node");
      }
      textNode = walker.nextNode();
    }

    // 2. Accessibility/attribute/text/pseudo-element signals.
    for (const el of [...document.querySelectorAll(
      "button,[role='button'],[aria-label],[title],[data-tooltip],div,span,label,a"
    )]) {
      if (!visible(el)) continue;
      const sig = signature(el);
      const aria = norm(el.getAttribute("aria-label") || "");
      const title = norm(el.getAttribute("title") || "");
      const tooltip = norm(el.getAttribute("data-tooltip") || "");
      const inner = norm(el.innerText || "");
      const text = norm(el.textContent || "");
      const before = pseudoText(el, "::before");
      const after = pseudoText(el, "::after");

      const h2Signals = [sig, aria, title, tooltip, inner, text, before, after];
      const isH2 = h2Signals.some((value) =>
        /^(?:H\s*2|Heading\s*2|Заголовок\s*2)$/i.test(norm(value))
      );

      if (isH2) {
        addCandidate(el, el.getBoundingClientRect(), "element-signal");
      }
    }

    candidates.sort((a, b) => a.dist - b.dist || a.controlRect.width - b.controlRect.width);
    if (candidates.length) {
      const best = candidates[0];
      const marker = `ai-av-toolbar-h2-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      best.node.setAttribute("data-ai-av-toolbar-h2", marker);
      return {
        ok: true,
        marker,
        source: best.source,
        selected,
        dist: Math.round(best.dist),
        box: {
          x: best.controlRect.x,
          y: best.controlRect.y,
          width: best.controlRect.width,
          height: best.controlRect.height,
        },
      };
    }

    // 3. Confirm whether the toolbar itself is visible even if H2 is rendered in
    // an unusual way. This is diagnostics only: we do not click by guessed position.
    const toolbarCandidates = [];
    for (const el of [...document.querySelectorAll("div,nav,section,[role='toolbar']")]) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      if (r.width < 180 || r.width > 760 || r.height < 28 || r.height > 150) continue;
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dist = Math.hypot(cx - sx, cy - sy);
      if (dist > 700) continue;
      const sig = signature(el);
      const hasH2 = /(?:\bH\s*2\b|\bHeading\s*2\b|\bЗаголовок\s*2\b)/i.test(sig);
      const hasH3 = /(?:\bH\s*3\b|\bHeading\s*3\b|\bЗаголовок\s*3\b)/i.test(sig);
      if (hasH2 && hasH3) {
        toolbarCandidates.push({
          tag: el.tagName,
          role: el.getAttribute("role"),
          className: String(el.className || "").slice(0, 180),
          text: norm(el.innerText || el.textContent).slice(0, 240),
          signature: sig.slice(0, 320),
          dist: Math.round(dist),
          box: { x: r.x, y: r.y, width: r.width, height: r.height },
        });
      }
    }

    toolbarCandidates.sort((a, b) => a.dist - b.dist);
    return {
      ok: false,
      reason: toolbarCandidates.length ? "toolbar-visible-h2-control-unresolved" : "toolbar-not-yet-visible",
      selected,
      toolbarCandidates: toolbarCandidates.slice(0, 5),
    };
  });
}

async function collectToolbarDiagnostics(page) {
  return page.evaluate(() => {
    const norm = (v) => String(v || "")
      .replace(/^["']|["']$/g, "")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      if (!el) return false;
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 &&
        s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
    };
    const pseudoText = (el, pseudo) => {
      try {
        const value = getComputedStyle(el, pseudo).content;
        return value && value !== "none" && value !== "normal" ? norm(value) : "";
      } catch {
        return "";
      }
    };

    const selection = window.getSelection();
    let selRect = null;
    let selected = "";
    if (selection && selection.rangeCount) {
      selected = norm(selection.toString());
      const r = selection.getRangeAt(0).getBoundingClientRect();
      selRect = { x: r.x, y: r.y, width: r.width, height: r.height };
    }
    const sx = selRect ? selRect.x + selRect.width / 2 : window.innerWidth / 2;
    const sy = selRect ? selRect.y + selRect.height / 2 : window.innerHeight / 2;

    const items = [];
    for (const el of [...document.querySelectorAll(
      "button,[role='button'],[role='toolbar'],[aria-label],[title],[data-tooltip],div,span,label,a"
    )]) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const cy = r.top + r.height / 2;
      const dist = Math.hypot(cx - sx, cy - sy);
      if (dist > 850) continue;
      const style = getComputedStyle(el);
      const inner = norm(el.innerText || "");
      const text = norm(el.textContent || "");
      const aria = norm(el.getAttribute("aria-label") || "");
      const title = norm(el.getAttribute("title") || "");
      const tooltip = norm(el.getAttribute("data-tooltip") || "");
      const before = pseudoText(el, "::before");
      const after = pseudoText(el, "::after");
      if (
        !inner && !text && !aria && !title && !tooltip && !before && !after &&
        el.getAttribute("role") !== "toolbar"
      ) continue;
      items.push({
        tag: el.tagName,
        role: el.getAttribute("role"),
        className: String(el.className || "").slice(0, 220),
        aria,
        title,
        tooltip,
        inner: inner.slice(0, 260),
        text: text.slice(0, 260),
        before,
        after,
        cursor: style.cursor,
        tabIndex: el.tabIndex,
        dist: Math.round(dist),
        box: {
          x: Math.round(r.x),
          y: Math.round(r.y),
          width: Math.round(r.width),
          height: Math.round(r.height),
        },
      });
    }
    items.sort((a, b) => a.dist - b.dist);
    return {
      capturedAt: new Date().toISOString(),
      url: location.href,
      selected,
      selectionRect: selRect,
      items: items.slice(0, 140),
    };
  });
}

function saveToolbarDiagnostics(diagnostics) {
  const dir = path.join(ROOT, "screenshots");
  fs.mkdirSync(dir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const file = path.join(dir, `dzen-article-video-toolbar-diag-${stamp}.json`);
  fs.writeFileSync(file, JSON.stringify(diagnostics, null, 2), "utf8");
  return file;
}

async function findToolbarH2Control(page, logger) {
  const deadline = Date.now() + TOOLBAR_TIMEOUT_MS;
  let last = null;
  while (Date.now() < deadline) {
    last = await probeToolbarH2Control(page);
    if (last.ok) {
      logger.log(
        `Floating toolbar H2 control найден: source=${last.source}; distance=${last.dist}px; ` +
        `box=${JSON.stringify(last.box)}.`
      );
      return {
        locator: page.locator(`[data-ai-av-toolbar-h2="${last.marker}"]`).first(),
        box: last.box,
      };
    }
    await page.waitForTimeout(200);
  }

  const diagnostics = await collectToolbarDiagnostics(page).catch((error) => ({
    captureError: error.message,
    lastProbe: last,
  }));
  diagnostics.lastProbe = last;
  const diagPath = saveToolbarDiagnostics(diagnostics);
  logger.warn(`Toolbar diagnostics сохранён: ${diagPath}`);

  throw new Error(
    `Не найден однозначный H2 control floating toolbar за ${TOOLBAR_TIMEOUT_MS} мс ` +
    `(last=${JSON.stringify(last)}; diagnostics=${diagPath}).`
  );
}

async function physicalClickVerified(page, locator, description) {
  await locator.scrollIntoViewIfNeeded({ timeout: 10_000 }).catch(() => {});
  const box = await locator.boundingBox();
  if (!box || box.width <= 0 || box.height <= 0) {
    throw new Error(`${description}: некорректная geometry; click запрещён.`);
  }
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  const hit = await locator.evaluate((el, point) => {
    const top = document.elementFromPoint(point.x, point.y);
    return Boolean(top && (top === el || el.contains(top) || top.contains(el)));
  }, { x, y }).catch(() => false);
  if (!hit) throw new Error(`${description}: elementFromPoint hit-test не подтверждён; click запрещён.`);
  await page.mouse.click(x, y);
  return { x, y };
}

async function formatHeadingThroughToolbar(page, oracle, beforeStyle, logger) {
  await selectHeadingText(page);
  const control = await findToolbarH2Control(page, logger);
  const point = await physicalClickVerified(page, control.locator, "H2 toolbar");
  logger.log(`Floating toolbar H2 clicked один раз: x=${Math.round(point.x)}, y=${Math.round(point.y)}.`);

  const deadline = Date.now() + 8_000;
  let last = null;
  while (Date.now() < deadline) {
    const heading = await exactDraftBlock(page, HEADING_TEXT, "formatted-heading").catch(() => null);
    if (heading) {
      last = await blockStyleSnapshot(heading);
      if (headingMatchesOracle(last, oracle, beforeStyle)) {
        logger.log(
          `H2 фактически подтверждён по oracle «${ANCHOR_TEXT}»: ` +
          `semantic=${last.semantic}; explicitType=${last.explicitType}; font=${last.fontSize}px/${last.fontWeight}.`
        );
        return last;
      }
    }
    await page.waitForTimeout(250);
  }
  throw new Error(
    `После клика H2 «${HEADING_TEXT}» не совпал с фактическим H2 oracle «${ANCHOR_TEXT}» ` +
    `(last=${JSON.stringify(last)}). Изменения не публикую.`
  );
}

async function readEditorSaveSignals(page) {
  return page.evaluate(() => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 &&
        s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
    };

    const texts = [];
    const seen = new Set();
    for (const el of [...document.querySelectorAll("body *")]) {
      if (!visible(el)) continue;
      const r = el.getBoundingClientRect();
      // Dzen save/publish state lives in the editor header.
      if (r.top > 150 || r.bottom < 0) continue;
      const text = norm(el.innerText || el.textContent || "");
      if (!text) continue;
      if (!/(Ид[её]т сохранение|Сохранено|Есть неопубликованные правки)/i.test(text)) continue;
      if (seen.has(text)) continue;
      seen.add(text);
      texts.push(text.slice(0, 260));
    }

    const joined = texts.join(" | ");
    return {
      saving: /Ид[её]т\s+сохранени[ея]/i.test(joined),
      saved: /Сохранено(?:\s|$)/i.test(joined),
      unpublished: /Есть неопубликованные правки/i.test(joined),
      texts: texts.slice(0, 12),
    };
  });
}

function autosaveSignalsReady(signals) {
  return Boolean(signals && signals.saved && signals.unpublished && !signals.saving);
}

async function waitForAutosaveSignals(page, logger) {
  const deadline = Date.now() + AUTOSAVE_TIMEOUT_MS;
  let stableSince = null;
  let lastKey = "";
  let last = null;

  while (Date.now() < deadline) {
    last = await readEditorSaveSignals(page);
    const key = JSON.stringify({
      saving: last.saving,
      saved: last.saved,
      unpublished: last.unpublished,
      texts: last.texts,
    });

    if (key !== lastKey) {
      logger.log(
        `AUTOSAVE status: saving=${last.saving}; saved=${last.saved}; ` +
        `unpublished=${last.unpublished}; texts=${JSON.stringify(last.texts)}.`
      );
      lastKey = key;
    }

    if (autosaveSignalsReady(last)) {
      if (stableSince === null) stableSince = Date.now();
      const stableFor = Date.now() - stableSince;
      if (stableFor >= AUTOSAVE_STABLE_MS) {
        logger.log(
          `Autosave стабилен ${Math.round(stableFor / 100) / 10} с: ` +
          `«Сохранено …» + «Есть неопубликованные правки», «Идёт сохранение» отсутствует.`
        );
        return last;
      }
    } else {
      stableSince = null;
    }

    await page.waitForTimeout(250);
  }

  throw new Error(
    `Не дождался стабильного autosave за ${AUTOSAVE_TIMEOUT_MS} мс: ` +
    `нужно ${AUTOSAVE_STABLE_MS} мс непрерывно видеть «Сохранено …» + ` +
    `«Есть неопубликованные правки» без «Идёт сохранение». last=${JSON.stringify(last)}. ` +
    "Изменения не публикую."
  );
}

async function assertAutosaveReadyImmediatelyBeforePublish(page) {
  const first = await readEditorSaveSignals(page);
  if (!autosaveSignalsReady(first)) {
    throw new Error(
      `Непосредственно перед publish autosave снова неготов: ${JSON.stringify(first)}. ` +
      "Publish click запрещён."
    );
  }

  // Small final guard against the status flipping back to "Идёт сохранение"
  // between the stable gate and the physical click.
  await page.waitForTimeout(750);
  const second = await readEditorSaveSignals(page);
  if (!autosaveSignalsReady(second)) {
    throw new Error(
      `Autosave изменился в последнюю секунду перед publish: ${JSON.stringify(second)}. ` +
      "Publish click запрещён."
    );
  }
  return second;
}

async function collectPostPublishUi(page) {
  return page.evaluate(() => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 &&
        s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
    };

    const interesting = [];
    const selectors = [
      "[role='dialog']",
      "[aria-modal='true']",
      "[class*='modal']",
      "[class*='toast']",
      "[class*='notification']",
      "[class*='editor-header']",
    ];
    for (const el of [...document.querySelectorAll(selectors.join(","))]) {
      if (!visible(el)) continue;
      const text = norm(el.innerText || el.textContent || "");
      if (!text) continue;
      if (!/(сохран|опублик|правк|готов|успеш)/i.test(text)) continue;
      interesting.push({
        tag: el.tagName,
        role: el.getAttribute("role"),
        className: String(el.className || "").slice(0, 180),
        text: text.slice(0, 320),
      });
    }

    return {
      url: location.href,
      bodySignals: norm(document.body.innerText || "").match(
        /(?:Ид[её]т сохранение|Сохранено[^.\n]{0,80}|Есть неопубликованные правки|Опубликовано[^.\n]{0,80})/gi
      ) || [],
      interesting: interesting.slice(0, 16),
    };
  });
}

async function waitForPostPublishSettle(page, logger) {
  const startedAt = Date.now();
  const deadline = startedAt + POST_PUBLISH_TIMEOUT_MS;
  let noSavingSince = null;
  let sawSaving = false;
  let lastKey = "";
  let last = null;

  while (Date.now() < deadline) {
    const save = await readEditorSaveSignals(page).catch(() => ({
      saving: false, saved: false, unpublished: false, texts: [],
    }));
    last = {
      save,
      ui: await collectPostPublishUi(page).catch(() => null),
    };

    if (save.saving) {
      sawSaving = true;
      noSavingSince = null;
    } else if (Date.now() - startedAt >= POST_PUBLISH_MIN_HOLD_MS) {
      if (noSavingSince === null) noSavingSince = Date.now();
      if (Date.now() - noSavingSince >= POST_PUBLISH_STABLE_MS) {
        logger.log(
          `POST-PUBLISH settle: editor оставался открытым минимум ` +
          `${POST_PUBLISH_MIN_HOLD_MS / 1000} с; «Идёт сохранение» отсутствует ` +
          `${POST_PUBLISH_STABLE_MS / 1000} с подряд; sawSaving=${sawSaving}.`
        );
        return { ok: true, sawSaving, last };
      }
    }

    const key = JSON.stringify({
      saving: save.saving,
      saved: save.saved,
      unpublished: save.unpublished,
      bodySignals: last.ui && last.ui.bodySignals,
    });
    if (key !== lastKey) {
      logger.log(`POST-PUBLISH UI: ${key}`);
      lastKey = key;
    }

    await page.waitForTimeout(250);
  }

  logger.warn(
    `POST-PUBLISH settle timeout ${POST_PUBLISH_TIMEOUT_MS} мс. ` +
    `Editor всё это время не навигировался; публичная verification будет открыта в отдельной вкладке. ` +
    `last=${JSON.stringify(last)}`
  );
  return { ok: false, sawSaving, last };
}

async function findExactPublishButton(page) {
  const candidates = page.getByText("Опубликовать", { exact: true });
  const visible = [];
  for (let i = 0; i < await candidates.count().catch(() => 0); i += 1) {
    const item = candidates.nth(i);
    if (!(await item.isVisible().catch(() => false))) continue;
    const interactive = item.locator("xpath=ancestor-or-self::button[1]");
    if (await interactive.count().catch(() => 0)) visible.push(interactive.first());
    else visible.push(item);
  }
  if (visible.length !== 1) {
    throw new Error(`Ожидалась одна видимая exact кнопка «Опубликовать», найдено ${visible.length}.`);
  }
  if (await visible[0].isDisabled().catch(() => false)) {
    throw new Error("Кнопка «Опубликовать» disabled.");
  }
  return visible[0];
}

async function findSaveChangesButtonInPublishDialog(page) {
  const deadline = Date.now() + PUBLISH_DIALOG_TIMEOUT_MS;
  let last = null;

  while (Date.now() < deadline) {
    last = await page.evaluate(() => {
      const norm = (v) => String(v || "")
        .normalize("NFKC")
        .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
        .replace(/[\u00A0\u202F]/g, " ")
        .replace(/\s+/g, " ")
        .trim();
      const visible = (el) => {
        if (!el) return false;
        const r = el.getBoundingClientRect();
        const s = getComputedStyle(el);
        return r.width > 0 && r.height > 0 &&
          s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
      };

      const titleEls = [...document.querySelectorAll("h1,h2,h3,div,span")]
        .filter(visible)
        .filter((el) => norm(el.innerText || el.textContent) === "Публикация");

      const textEls = [...document.querySelectorAll("button,[role='button'],div,span")]
        .filter(visible)
        .filter((el) => norm(el.innerText || el.textContent) === "Сохранить изменения");

      const candidates = [];
      const seen = new Set();

      for (const el of textEls) {
        let interactive = null;
        let node = el;
        for (let depth = 0; node && depth < 6; depth += 1, node = node.parentElement) {
          if (!visible(node)) continue;
          if (
            node.tagName === "BUTTON" ||
            node.getAttribute("role") === "button" ||
            node.tabIndex >= 0 ||
            getComputedStyle(node).cursor === "pointer"
          ) {
            interactive = node;
            break;
          }
        }
        interactive = interactive || el;
        if (seen.has(interactive) || !visible(interactive)) continue;
        seen.add(interactive);

        // Prove the button belongs to a visible publication dialog/modal-like container.
        let owner = interactive;
        let ownerFound = false;
        for (let depth = 0; owner && depth < 12; depth += 1, owner = owner.parentElement) {
          if (!visible(owner)) continue;
          const text = norm(owner.innerText || owner.textContent);
          const r = owner.getBoundingClientRect();
          if (
            text.includes("Публикация") &&
            text.includes("Сохранить изменения") &&
            r.width >= 300 &&
            r.height >= 180
          ) {
            ownerFound = true;
            break;
          }
        }
        if (!ownerFound) continue;

        const r = interactive.getBoundingClientRect();
        const x = r.left + r.width / 2;
        const y = r.top + r.height / 2;
        const hit = document.elementFromPoint(x, y);
        const hitOk = Boolean(hit && (hit === interactive || interactive.contains(hit) || hit.contains(interactive)));

        candidates.push({
          element: interactive,
          hitOk,
          box: { x: r.x, y: r.y, width: r.width, height: r.height },
          tag: interactive.tagName,
          role: interactive.getAttribute("role"),
          aria: interactive.getAttribute("aria-label"),
        });
      }

      if (titleEls.length < 1) {
        return { ok: false, reason: "publication-title-not-visible", titleCount: titleEls.length, candidateCount: candidates.length };
      }

      const hittable = candidates.filter((item) => item.hitOk);

      // Dzen renders nested clickable-looking nodes for the same visual control:
      // footer DIV -> wrapper DIV -> actual BUTTON -> SPAN.
      // v5.5 incorrectly required exactly one hittable node and therefore refused
      // to click even though the real BUTTON was unambiguous.
      let chosen = null;
      let selectionReason = null;

      const nativeButtons = hittable.filter((item) => item.tag === "BUTTON");
      if (nativeButtons.length === 1) {
        chosen = nativeButtons[0];
        selectionReason = "unique-native-button";
      } else if (nativeButtons.length > 1) {
        return {
          ok: false,
          reason: `multiple-native-buttons=${nativeButtons.length}`,
          titleCount: titleEls.length,
          candidates: candidates.map(({ element, ...rest }) => rest),
        };
      }

      if (!chosen) {
        const roleButtons = hittable.filter((item) => item.role === "button");
        if (roleButtons.length === 1) {
          chosen = roleButtons[0];
          selectionReason = "unique-role-button";
        } else if (roleButtons.length > 1) {
          return {
            ok: false,
            reason: `multiple-role-buttons=${roleButtons.length}`,
            titleCount: titleEls.length,
            candidates: candidates.map(({ element, ...rest }) => rest),
          };
        }
      }

      if (!chosen) {
        // Last fail-closed fallback: collapse exact-geometry duplicates and accept
        // only one visual rectangle.
        const visual = new Map();
        for (const item of hittable) {
          const key = [
            Math.round(item.box.x * 2) / 2,
            Math.round(item.box.y * 2) / 2,
            Math.round(item.box.width * 2) / 2,
            Math.round(item.box.height * 2) / 2,
          ].join(":");
          if (!visual.has(key)) visual.set(key, item);
        }
        if (visual.size === 1) {
          chosen = [...visual.values()][0];
          selectionReason = "unique-visual-control";
        } else {
          return {
            ok: false,
            reason: `ambiguous-visual-controls=${visual.size};hittable=${hittable.length}`,
            titleCount: titleEls.length,
            candidates: candidates.map(({ element, ...rest }) => rest),
          };
        }
      }
      const marker = `ai-av-save-changes-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      chosen.element.setAttribute("data-ai-av-save-changes", marker);
      return {
        ok: true,
        marker,
        titleCount: titleEls.length,
        box: chosen.box,
        tag: chosen.tag,
        role: chosen.role,
        aria: chosen.aria,
        selectionReason,
        hittableCount: hittable.length,
      };
    });

    if (last.ok) {
      return {
        locator: page.locator(`[data-ai-av-save-changes="${last.marker}"]`).first(),
        info: last,
      };
    }

    await page.waitForTimeout(200);
  }

  throw new Error(
    `Не дождался однозначной кнопки «Сохранить изменения» в модальном окне «Публикация» ` +
    `за ${PUBLISH_DIALOG_TIMEOUT_MS} мс. last=${JSON.stringify(last)}`
  );
}

function isExpectedNavigationContextError(error) {
  const message = String((error && error.message) || error || "");
  return (
    /Execution context was destroyed/i.test(message) ||
    /Cannot find context with specified id/i.test(message) ||
    /most likely because of a navigation/i.test(message)
  );
}

async function waitForPublishDialogGone(page, logger) {
  const deadline = Date.now() + PUBLISH_DIALOG_GONE_TIMEOUT_MS;
  let lastVisible = null;

  while (Date.now() < deadline) {
    try {
      lastVisible = await page.evaluate(() => {
        const norm = (v) => String(v || "")
          .normalize("NFKC")
          .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
          .replace(/[\u00A0\u202F]/g, " ")
          .replace(/\s+/g, " ")
          .trim();
        const visible = (el) => {
          const r = el.getBoundingClientRect();
          const s = getComputedStyle(el);
          return r.width > 0 && r.height > 0 &&
            s.display !== "none" && s.visibility !== "hidden" && s.opacity !== "0";
        };
        return [...document.querySelectorAll("button,[role='button'],div,span")]
          .filter(visible)
          .some((el) => norm(el.innerText || el.textContent) === "Сохранить изменения");
      });
    } catch (error) {
      if (!isExpectedNavigationContextError(error)) throw error;

      logger.log(
        "POST-CONFIRM: после «Сохранить изменения» началась навигация; " +
        "уничтожение старого execution context является ожидаемым success-path."
      );
      await page.waitForLoadState("domcontentloaded", { timeout: 30_000 }).catch(() => {});
      await page.waitForTimeout(1000);
      return true;
    }

    if (!lastVisible) {
      logger.log("POST-CONFIRM: окно «Публикация»/кнопка «Сохранить изменения» исчезли.");
      return true;
    }
    await page.waitForTimeout(250);
  }

  logger.warn(
    `После click «Сохранить изменения» кнопка всё ещё видима через ` +
    `${PUBLISH_DIALOG_GONE_TIMEOUT_MS} мс. Повторный click запрещён; продолжаю только наблюдение/verification.`
  );
  return false;
}

async function openPublishDialogAndClickSaveChanges(editorPage, config, state, job, logger) {
  await assertAutosaveReadyImmediatelyBeforePublish(editorPage);

  const publishButton = await findExactPublishButton(editorPage);
  const publishPoint = await physicalClickVerified(editorPage, publishButton, "Опубликовать");

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "PUBLISH_ARMED",
    publishButtonClickedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  logger.log(
    `Первый click «Опубликовать» выполнен: x=${Math.round(publishPoint.x)}, y=${Math.round(publishPoint.y)}. ` +
    "Жду модальное окно «Публикация»; это ещё НЕ финальная фиксация изменений."
  );

  const confirmation = await findSaveChangesButtonInPublishDialog(editorPage);
  logger.log(
    `Модальное окно «Публикация» подтверждено; exact «Сохранить изменения» найден: ` +
    `tag=${confirmation.info.tag}; reason=${confirmation.info.selectionReason}; ` +
    `hittable=${confirmation.info.hittableCount}; box=${JSON.stringify(confirmation.info.box)}.`
  );

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "CONFIRMATION_ARMED",
    confirmationArmedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  logger.log(
    "phase=CONFIRMATION_ARMED сохранён ДО финального click. " +
    "После этого повторный click «Сохранить изменения» при неопределённом результате запрещён."
  );

  const savePoint = await physicalClickVerified(
    editorPage,
    confirmation.locator,
    "Сохранить изменения"
  );

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "CLICKED_UNVERIFIED",
    publishClicked: true,
    publishClickedAt: new Date().toISOString(),
    saveChangesClickedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });

  logger.log(
    `ФИНАЛЬНЫЙ click «Сохранить изменения» выполнен ровно один раз: ` +
    `x=${Math.round(savePoint.x)}, y=${Math.round(savePoint.y)}; phase=CLICKED_UNVERIFIED.`
  );

  await waitForPublishDialogGone(editorPage, logger);
  await waitForPostPublishSettle(editorPage, logger);
}

async function detectPublicVideoBetween(page, articleUrl, videoUrl) {
  return page.evaluate(({ headingText, anchorText, videoUrl }) => {
    const norm = (v) => String(v || "")
      .normalize("NFKC")
      .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
      .replace(/[\u00A0\u202F]/g, " ")
      .replace(/\s+/g, " ")
      .trim();
    const visible = (el) => {
      const r = el.getBoundingClientRect();
      const s = getComputedStyle(el);
      return r.width > 0 && r.height > 0 && s.display !== "none" && s.visibility !== "hidden";
    };
    const exact = (text) => [...document.querySelectorAll("h1,h2,h3,[role='heading'],div,p,span")]
      .filter(visible)
      .filter((el) => norm(el.innerText || el.textContent) === text)
      .sort((a, b) => a.children.length - b.children.length);
    const headings = exact(headingText);
    const anchors = exact(anchorText);
    if (!headings.length || !anchors.length) {
      return { ok: false, reason: `heading=${headings.length};anchor=${anchors.length}` };
    }

    const heading = headings.find((el) =>
      el.tagName === "H2" ||
      (el.getAttribute("role") === "heading" && el.getAttribute("aria-level") === "2")
    ) || headings[0];
    const anchor = anchors.find((el) =>
      el.tagName === "H2" ||
      (el.getAttribute("role") === "heading" && el.getAttribute("aria-level") === "2")
    ) || anchors[0];

    const h = heading.getBoundingClientRect();
    const a = anchor.getBoundingClientRect();
    if (!(h.top < a.top)) return { ok: false, reason: "heading-not-before-anchor" };
    const isHeadingH2 =
      heading.tagName === "H2" ||
      (heading.getAttribute("role") === "heading" && heading.getAttribute("aria-level") === "2");
    const isAnchorH2 =
      anchor.tagName === "H2" ||
      (anchor.getAttribute("role") === "heading" && anchor.getAttribute("aria-level") === "2");
    if (!isHeadingH2 || !isAnchorH2) {
      return { ok: false, reason: `semantic-h2 heading=${isHeadingH2} anchor=${isAnchorH2}` };
    }

    const top = h.bottom - 2;
    const bottom = a.top + 2;
    const between = (el) => {
      const r = el.getBoundingClientRect();
      const cy = r.top + r.height / 2;
      return visible(el) && cy > top && cy < bottom;
    };
    const signals = [];
    for (const el of [...document.querySelectorAll("video,iframe")].filter(between)) {
      const r = el.getBoundingClientRect();
      signals.push({ kind: el.tagName.toLowerCase(), width: r.width, height: r.height });
    }
    for (const el of [...document.querySelectorAll("a")].filter(between)) {
      const href = String(el.href || "");
      const r = el.getBoundingClientRect();
      if (href.includes("/video/watch/") && r.width > 100 && r.height > 30) {
        signals.push({ kind: "video-link", href });
      }
    }
    for (const el of [...document.querySelectorAll("*")].filter(between)) {
      const r = el.getBoundingClientRect();
      if (r.width < 280 || r.height < 120) continue;
      const signature = [
        el.tagName,
        el.className,
        el.getAttribute("data-testid"),
        el.getAttribute("aria-label"),
        el.getAttribute("title"),
      ].filter(Boolean).join(" ");
      if (/(video|player|embed|preview)/i.test(signature)) {
        signals.push({ kind: "video-signature", signature: signature.slice(0, 120) });
      }
    }
    return {
      ok: signals.length > 0,
      reason: signals.length ? "verified" : "no-video-between",
      signals: signals.slice(0, 8),
      expectedVideoUrl: videoUrl,
    };
  }, { headingText: HEADING_TEXT, anchorText: ANCHOR_TEXT, videoUrl });
}

async function verifyPublicArticle(page, articleUrl, videoUrl, logger) {
  const deadline = Date.now() + PUBLIC_VERIFY_TIMEOUT_MS;
  let last = null;
  while (Date.now() < deadline) {
    await page.goto(articleUrl, { waitUntil: "domcontentloaded", timeout: 60_000 }).catch(() => {});
    if (isLoginUrl(page.url())) throw new Error(`Публичная статья перенаправила на авторизацию: ${page.url()}`);
    await page.waitForTimeout(1200);
    last = await detectPublicVideoBetween(page, articleUrl, videoUrl).catch((error) => ({
      ok: false,
      reason: error.message,
    }));
    if (last.ok) {
      logger.log(
        `Публичная verification подтверждена: H2 «${HEADING_TEXT}» -> video preview -> H2 «${ANCHOR_TEXT}».`
      );
      return last;
    }
    await page.waitForTimeout(2_000);
  }
  return last || { ok: false, reason: "verification-timeout" };
}

async function verifyPublicArticleSeparateFromEditor(editorPage, articleUrl, videoUrl, logger) {
  const verifyPage = await editorPage.context().newPage();
  logger.log("Публичная verification открыта в отдельной вкладке; editor page остаётся нетронутым.");
  try {
    return await verifyPublicArticle(verifyPage, articleUrl, videoUrl, logger);
  } finally {
    await verifyPage.close().catch(() => {});
  }
}

function normalizeComparableUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    url.hash = "";
    url.search = "";
    return url.href.replace(/\/?$/, "/");
  } catch {
    return String(value || "").trim().replace(/\/?$/, "/");
  }
}

function isFullHttpUrl(value) {
  try {
    const url = new URL(String(value || "").trim());
    return ["http:", "https:"].includes(url.protocol) && Boolean(url.hostname);
  } catch {
    return false;
  }
}

function planDescriptionArticleUrlUpdate(
  text,
  publicationUrl,
  articleUrl,
  placeholder = "https://"
) {
  const original = String(text || "");
  const newline = original.includes("\r\n") ? "\r\n" : "\n";
  const lines = original.replace(/\r\n/g, "\n").split("\n");
  const markerIndex = lines.findIndex((line) => line.trim() === "Этот выпуск:");

  if (markerIndex < 0) {
    return { changed: false, status: "PLACEHOLDER_ABSENT", text: original };
  }

  const bullets = [];
  for (let i = markerIndex + 1; i < lines.length && i <= markerIndex + 8; i += 1) {
    const trimmed = lines[i].trim();
    if (!trimmed) {
      if (bullets.length > 0) break;
      continue;
    }
    const match = trimmed.match(/^-\s*(\S+)\s*$/);
    if (!match) break;
    bullets.push({ index: i, value: match[1] });
    if (bullets.length === 2) break;
  }

  const placeholderValue = String(placeholder || "https://").trim();
  if (
    bullets.length < 2 ||
    bullets[1].value !== placeholderValue
  ) {
    // Project contract: absence of the exact placeholder means the operator
    // may have filled the second link manually. Never rewrite that file.
    return { changed: false, status: "PLACEHOLDER_ABSENT", text: original };
  }

  if (!isFullHttpUrl(articleUrl)) {
    throw new Error(`Некорректный Dzen article URL для файла описания: ${articleUrl}`);
  }

  if (
    publicationUrl &&
    normalizeComparableUrl(bullets[0].value) !== normalizeComparableUrl(publicationUrl)
  ) {
    throw new Error(
      `Заглушка найдена, но первая ссылка блока «Этот выпуск» относится к другому выпуску: ` +
      `${bullets[0].value} != ${publicationUrl}`
    );
  }

  const rawLine = lines[bullets[1].index];
  const indent = (rawLine.match(/^\s*/) || [""])[0];
  lines[bullets[1].index] = `${indent}- ${articleUrl}`;
  return {
    changed: true,
    status: "UPDATED",
    text: lines.join(newline),
  };
}

function updateDescriptionArticleUrl(config, job, articleUrl, logger) {
  const filePath = config.descriptionFile;
  if (!filePath || !fs.existsSync(filePath)) {
    throw new Error(`Не найден файл описания для записи Dzen article URL: ${filePath || "<не задан>"}`);
  }

  const current = fs.readFileSync(filePath, "utf8");
  const plan = planDescriptionArticleUrlUpdate(
    current,
    job && job.publicationUrl,
    articleUrl,
    config.descriptionSecondUrlPlaceholder || "https://"
  );

  if (!plan.changed) {
    logger.log(
      `Файл описания НЕ меняю: exact заглушка второй ссылки отсутствует ` +
      `(предполагается ручная ссылка): ${filePath}`
    );
    return plan.status;
  }

  const tmp = `${filePath}.article-url-${process.pid}-${Date.now()}.tmp`;
  fs.writeFileSync(tmp, plan.text, "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
  logger.log(`Dzen article URL записан вместо exact заглушки в ${filePath}: ${articleUrl}`);
  return plan.status;
}

function prerequisitesSatisfied(job) {
  return (
    String(job && job.dzenAutomation && job.dzenAutomation.status || "") === "PUBLISHED" &&
    String(job && job.dzenCollections && job.dzenCollections.status || "") === "COMPLETE"
  );
}

async function resolveLinks(page, dateKey, logger) {
  await openPublications(page);
  await ensurePublicationFilter(page, "Статьи");
  const articleRow = await findPublicationRow(page, dateKey, "article", logger);
  const articleUrl = await copyPublicationUrl(page, articleRow, "article", logger);
  logger.log(`Article URL получен через «Скопировать ссылку»: ${articleUrl}`);

  await openPublications(page);
  await ensurePublicationFilter(page, "Видео");
  const videoRow = await findPublicationRow(page, dateKey, "video", logger);
  const videoUrl = await copyPublicationUrl(page, videoRow, "video", logger);
  logger.log(`Video URL получен через «Скопировать ссылку»: ${videoUrl}`);

  return { articleUrl, videoUrl };
}

async function openArticleEditor(page, dateKey, logger) {
  await openPublications(page);
  await ensurePublicationFilter(page, "Статьи");
  const articleRow = await findPublicationRow(page, dateKey, "article", logger);
  const editorPage = await openRowMenuAction(page, articleRow, "Отредактировать", { expectNewPage: true });
  await waitForEditor(editorPage);
  await closeArticleOnboardingIfPresent(editorPage, logger);
  await exactDraftBlock(editorPage, ANCHOR_TEXT, "anchor-open");
  logger.log(`Редактор статьи открыт; anchor «${ANCHOR_TEXT}» виден.`);
  const diagnostics = await getEditorDiagnostics(editorPage);
  const primary = diagnostics[0] || {};
  logger.log(
    `EDITOR-DIAG: contenteditable=${diagnostics.length}; tag=${primary.tag || "?"}; role=${primary.role || "null"}; ` +
    `ProseMirror=${Boolean(primary.prosemirror)}; tiptap=${Boolean(primary.tiptap)}; class=${JSON.stringify(primary.className || "")}.`
  );
  return editorPage;
}

async function runDryRun(page, dateKey, logger) {
  const links = await resolveLinks(page, dateKey, logger);
  const editorPage = await openArticleEditor(page, dateKey, logger);
  const draft = await inspectArticleVideoDraft(editorPage, links.videoUrl, logger);

  if (draft.mode === "EXISTING_H2") {
    logger.log(`DRY-RUN: exact H2 «${HEADING_TEXT}» уже существует; apply должен завершиться SKIPPED_EXISTING.`);
  } else if (draft.mode === "RESUMABLE_PARTIAL") {
    logger.log(
      `DRY-RUN: подтверждён RESUMABLE_PARTIAL — обычный текст «${HEADING_TEXT}» + существующий Dzen video preview ` +
      `перед «${ANCHOR_TEXT}». Apply НЕ должен повторно создавать heading или вставлять видео; только H2-format -> autosave -> publish gate.`
    );
  } else {
    const prev = await blockImmediatelyBeforeAnchor(editorPage);
    logger.log(
      `DRY-RUN: CLEAN — exact «${HEADING_TEXT}» отсутствует; непосредственно перед anchor найден ` +
      `${prev.text ? "обычный текстовый block" : "пустой block"}. Никаких изменений не выполнено.`
    );
  }
  logger.log(`DRY-RUN links: article=${links.articleUrl}; video=${links.videoUrl}.`);
}

async function runVerificationOnly(page, config, state, job, logger) {
  const av = ensureArticleVideoState(job);
  if (!av.articleUrl || !av.videoUrl) {
    throw new Error(`phase=${av.phase} требует verification-only, но articleUrl/videoUrl отсутствуют.`);
  }
  logger.log(
    `phase=${av.phase}: разрешена только публичная verification. Редактор и publish click НЕ выполняются.`
  );
  const result = await verifyPublicArticle(page, av.articleUrl, av.videoUrl, logger);
  if (!result.ok) {
    updateArticleVideo(config, state, job, {
      status: "PENDING",
      phase: av.phase,
      lastError: `Verification-only не подтвердила публичный порядок (${result.reason}).`,
      lastErrorAt: new Date().toISOString(),
      lastAttemptAt: new Date().toISOString(),
    });
    throw new Error(
      `Публичная verification не подтверждена (${result.reason}). Состояние ${av.phase} сохранено; ` +
      "второе редактирование и второй publish click запрещены."
    );
  }
  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "VERIFIED",
    verifiedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  updateArticleVideo(config, state, job, {
    status: "COMPLETE",
    phase: "VERIFIED",
    completedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
}

function isSafePreEditLinkResolutionError(av) {
  if (!av || av.status !== "ERROR" || av.phase !== "ERROR") return false;
  const errorText = String(av.lastError || "");
  const linkFailure =
    errorText.includes("Скопировать ссылку") &&
    /(?:article|video) URL/i.test(errorText);
  if (!linkFailure) return false;

  const forbiddenMarkers = [
    "articleUrl",
    "videoUrl",
    "descriptionLinkCheckedAt",
    "publishArmedAt",
    "publishButtonClickedAt",
    "confirmationArmedAt",
    "publishClickedAt",
    "saveChangesClickedAt",
    "verifiedAt",
    "completedAt",
    "existingDetectedAt",
  ];
  if (forbiddenMarkers.some((key) => av[key])) return false;
  if (av.publishClicked === true) return false;
  return true;
}

function authorizePreEditLinkRecovery(config, state, job, logger) {
  const av = ensureArticleVideoState(job);
  if (!isSafePreEditLinkResolutionError(av)) {
    throw new Error(
      "--recover-pre-edit-link-error разрешён только для ERROR/ERROR, возникшего на pre-edit «Скопировать ссылку», " +
      "без articleUrl/videoUrl и без editor/publish markers. State не изменён."
    );
  }

  const recoveredAt = new Date().toISOString();
  const recoveryHistory = Array.isArray(av.recoveryHistory) ? av.recoveryHistory.slice() : [];
  recoveryHistory.push({
    recoveredAt,
    fromStatus: av.status,
    fromPhase: av.phase,
    lastError: av.lastError || null,
    lastErrorAt: av.lastErrorAt || null,
    reason: "pre-edit link-resolution recovery; fail-closed proof: no resolved links, editor markers or publish markers",
  });

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "PENDING",
    recoveryHistory,
    retryAuthorizedAt: recoveredAt,
    retryReason: "pre-edit link-resolution recovery",
    lastError: null,
    lastErrorAt: null,
  });
  if (logger) {
    logger.warn(
      "Recovery разрешён: предыдущий ERROR был до links/editor/publish. " +
      "State возвращён в PENDING; повторный publish click по старому инциденту невозможен."
    );
  }
  return ensureArticleVideoState(job);
}

async function runApply(page, config, state, job, dateKey, logger) {
  const av = ensureArticleVideoState(job);

  if (!prerequisitesSatisfied(job)) {
    throw new Error(
      `Article-video gate не выполнен: требуется dzenAutomation=PUBLISHED и ` +
      `dzenCollections=COMPLETE (сейчас dzenAutomation=${String(job?.dzenAutomation?.status || "PENDING")}; ` +
      `dzenCollections=${String(job?.dzenCollections?.status || "PENDING")}).`
    );
  }

  if (TERMINAL_STATUSES.has(av.status)) {
    if (av.status === "ERROR") {
      throw new Error(
        `dzenArticleVideo.status=ERROR является terminal. Автоматический retry запрещён; ` +
        `требуется отдельный явный incident recovery после проверки state/log/public article.`
      );
    }
    logger.log(`dzenArticleVideo.status=${av.status}; этап уже terminal, браузерные изменения не нужны.`);
    return;
  }

  if (VERIFY_ONLY_PHASES.has(av.phase)) {
    await runVerificationOnly(page, config, state, job, logger);
    return;
  }

  if (av.phase === "VERIFIED") {
    updateArticleVideo(config, state, job, {
      status: "COMPLETE",
      completedAt: av.completedAt || new Date().toISOString(),
      lastError: null,
      lastErrorAt: null,
    });
    return;
  }

  if (!["PENDING", "LINKS_RESOLVED", "EDITING"].includes(av.phase)) {
    throw new Error(`Неизвестный dzenArticleVideo.phase=${av.phase}.`);
  }

  const firstAttemptAt = av.firstAttemptAt || new Date().toISOString();
  const links = await resolveLinks(page, dateKey, logger);
  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "LINKS_RESOLVED",
    articleUrl: links.articleUrl,
    videoUrl: links.videoUrl,
    firstAttemptAt,
    lastAttemptAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });

  const descriptionLinkStatus = updateDescriptionArticleUrl(
    config,
    job,
    links.articleUrl,
    logger
  );
  updateArticleVideo(config, state, job, {
    descriptionLinkStatus,
    descriptionLinkCheckedAt: new Date().toISOString(),
  });

  let editorPage = await openArticleEditor(page, dateKey, logger);
  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "EDITING",
    lastAttemptAt: new Date().toISOString(),
  });

  const draft = await inspectArticleVideoDraft(editorPage, links.videoUrl, logger);
  if (draft.mode === "EXISTING_H2") {
    updateArticleVideo(config, state, job, {
      status: "SKIPPED_EXISTING",
      phase: "EXISTING_DETECTED",
      existingDetectedAt: new Date().toISOString(),
      lastError: null,
      lastErrorAt: null,
    });
    return;
  }

  let beforeStyle = null;
  let oracle = draft.oracle;

  if (draft.mode === "RESUMABLE_PARTIAL") {
    beforeStyle = draft.snapshot;
    logger.log(
      `RESUME: использую уже сохранённую связку «${HEADING_TEXT}» + Dzen video preview. ` +
      "Новый heading, Enter, clipboard paste и второй embed НЕ выполняются."
    );
  } else {
    // Fail before the first editor mutation if Windows clipboard cannot support
    // the real Ctrl+V required for Dzen to create a video embed.
    await prepareVideoClipboard(links.videoUrl, logger);
    const created = await createPlainHeadingBeforeAnchor(editorPage, logger);
    beforeStyle = created.beforeStyle;
    await pasteVideoAndWaitForPreview(
      editorPage,
      links.videoUrl,
      logger,
      { clipboardPrepared: true }
    );

    // Restore the operator clipboard as soon as the real video preview exists.
    // The outer finally block restores it again as a crash-safe fallback.
    const original = global.__AI_AV_ORIGINAL_CLIPBOARD__;
    if (typeof original === "string") {
      await writeClipboardText(original);
      logger.log("Исходный текст Windows clipboard восстановлен после подтверждения video preview.");
    }

    const anchor = await exactDraftBlock(editorPage, ANCHOR_TEXT, "oracle-anchor");
    oracle = await blockStyleSnapshot(anchor);
  }

  await formatHeadingThroughToolbar(editorPage, oracle, beforeStyle, logger);
  await waitForAutosaveSignals(editorPage, logger);

  // Re-check the live header immediately before arming/clicking. The previous
  // v5.3 run proved Dzen can flip back to "Идёт сохранение" after a momentary
  // "Сохранено" signal.
  await assertAutosaveReadyImmediatelyBeforePublish(editorPage);

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "PUBLISH_ARMED",
    publishArmedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  logger.log(
    "phase=PUBLISH_ARMED сохранён только после стабильного autosave. " +
    "Далее ожидается ДВУХЭТАПНАЯ фиксация: «Опубликовать» -> modal -> «Сохранить изменения»."
  );

  await openPublishDialogAndClickSaveChanges(editorPage, config, state, job, logger);

  const verification = await verifyPublicArticleSeparateFromEditor(
    editorPage,
    links.articleUrl,
    links.videoUrl,
    logger
  );
  if (!verification.ok) {
    updateArticleVideo(config, state, job, {
      status: "PENDING",
      phase: "CLICKED_UNVERIFIED",
      lastError: `После финального «Сохранить изменения» публичная verification не подтверждена (${verification.reason}).`,
      lastErrorAt: new Date().toISOString(),
      lastAttemptAt: new Date().toISOString(),
    });
    throw new Error(
      `После финального «Сохранить изменения» публичная статья не подтверждена (${verification.reason}). ` +
      "Состояние оставлено CLICKED_UNVERIFIED; дальнейшие запуски только verification-only."
    );
  }

  updateArticleVideo(config, state, job, {
    status: "PENDING",
    phase: "VERIFIED",
    verifiedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  updateArticleVideo(config, state, job, {
    status: "COMPLETE",
    phase: "VERIFIED",
    completedAt: new Date().toISOString(),
    lastError: null,
    lastErrorAt: null,
  });
  logger.log("STATE: dzenArticleVideo.status=COMPLETE; phase=VERIFIED.");
}

function runSelfTest() {
  const oracle = { semantic: false, explicitType: false, fontSize: 32, fontWeight: 700 };
  const before = { semantic: false, explicitType: false, fontSize: 18, fontWeight: 400 };
  const good = { semantic: false, explicitType: false, fontSize: 32, fontWeight: 700 };
  const bad = { semantic: false, explicitType: false, fontSize: 18, fontWeight: 400 };
  if (!headingMatchesOracle(good, oracle, before)) throw new Error("self-test: heading oracle positive failed");
  if (headingMatchesOracle(bad, oracle, before)) throw new Error("self-test: heading oracle negative failed");
  if (formatRussianLongDate("2027-01-03") !== "3 января 2027") throw new Error("self-test: generic date failed");
  const descriptionTemplate = [
    "Этот выпуск:",
    "- https://rybalka.one/posts/2027-01-03/",
    "- https://",
    "",
    "Все ИИ-сводки:",
  ].join("\r\n");
  const descriptionUpdated = planDescriptionArticleUrlUpdate(
    descriptionTemplate,
    "https://rybalka.one/posts/2027-01-03/",
    "https://dzen.ru/a/example-article"
  );
  if (!descriptionUpdated.changed || !descriptionUpdated.text.includes("- https://dzen.ru/a/example-article")) {
    throw new Error("self-test: description placeholder replacement failed");
  }
  const manualDescription = descriptionTemplate.replace("- https://\r\n", "- https://example.com/manual\r\n");
  const manualPreserved = planDescriptionArticleUrlUpdate(
    manualDescription,
    "https://rybalka.one/posts/2027-01-03/",
    "https://dzen.ru/a/must-not-overwrite"
  );
  if (manualPreserved.changed || manualPreserved.text !== manualDescription) {
    throw new Error("self-test: manual second URL must be preserved");
  }
  if (!TERMINAL_STATUSES.has("ERROR")) throw new Error("self-test: ERROR must remain terminal");
  const directArticle = expectedPublicationUrlFromCandidates(
    [{ value: "https://dzen.ru/a/article-test", source: "row-anchor-href" }],
    "article"
  );
  if (!directArticle || directArticle.value !== "https://dzen.ru/a/article-test") {
    throw new Error("self-test: direct article URL extraction failed");
  }
  if (expectedPublicationUrlFromCandidates([{ value: "https://dzen.ru/a/x" }], "video")) {
    throw new Error("self-test: article URL must not satisfy video pattern");
  }
  if (!isSafePreEditLinkResolutionError({
    status: "ERROR",
    phase: "ERROR",
    lastError: "«Скопировать ссылку» не положил в clipboard ожидаемый article URL.",
  })) {
    throw new Error("self-test: safe pre-edit link recovery classification failed");
  }
  if (isSafePreEditLinkResolutionError({
    status: "ERROR",
    phase: "ERROR",
    lastError: "«Скопировать ссылку» не положил в clipboard ожидаемый article URL.",
    publishArmedAt: "2026-01-01T00:00:00.000Z",
  })) {
    throw new Error("self-test: publish marker must block pre-edit link recovery");
  }
  if (!/^(?:H\s*2|Heading\s*2|Заголовок\s*2)$/i.test("Heading 2")) {
    throw new Error("self-test: live Dzen aria Heading 2 recognition failed");
  }
  if (!VERIFY_ONLY_PHASES.has("PUBLISH_ARMED") || !VERIFY_ONLY_PHASES.has("CONFIRMATION_ARMED") || !VERIFY_ONLY_PHASES.has("CLICKED_UNVERIFIED")) {
    throw new Error("self-test: publish phases must remain verification-only");
  }
  if (!autosaveSignalsReady({ saved: true, unpublished: true, saving: false })) {
    throw new Error("self-test: stable autosave positive failed");
  }
  if (autosaveSignalsReady({ saved: true, unpublished: true, saving: true })) {
    throw new Error("self-test: saving state must block publish");
  }

  // Exact semantic shape from the 11:08 live failure:
  // DIV footer, DIV wrapper, BUTTON, SPAN. The BUTTON must win.
  const liveCandidates = [
    { tag: "DIV", role: null, hitOk: true },
    { tag: "DIV", role: null, hitOk: true },
    { tag: "BUTTON", role: null, hitOk: true },
    { tag: "SPAN", role: null, hitOk: true },
  ];
  const liveButtons = liveCandidates.filter((item) => item.hitOk && item.tag === "BUTTON");
  if (liveButtons.length !== 1) {
    throw new Error("self-test: live Save Changes candidate set must resolve to one native BUTTON");
  }
  if (!isExpectedNavigationContextError(
    new Error("page.evaluate: Execution context was destroyed, most likely because of a navigation")
  )) {
    throw new Error("self-test: expected post-confirm navigation error classification failed");
  }

  console.log("SELF-TEST OK");
}

async function main() {
  const args = parseArgs(process.argv.slice(2));
  if (args.selfTest) {
    runSelfTest();
    return;
  }

  let config = null;
  let logger = null;
  let state = null;
  let job = null;
  let session = null;
  let browserSession = null;
  let originalClipboard = null;
  let dateKey = args.date;

  try {
    if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
    config = loadJson(CONFIG_PATH);
    if (args.visible) config.minimizeBrowserWindow = false;
    logger = createLogger(config);
    state = history.loadActiveState(config);

    if (!dateKey) dateKey = formatDateKey(new Date(), config.timeZone || "Europe/Moscow");
    parseDateKey(dateKey);
    const resolvedJob = history.findJobForDateIncludingArchive(config, state, dateKey);
    job = resolvedJob && resolvedJob.job;
    if (!job) throw new Error(`В active state или archive не найден job за ${dateKey}.`);
    if (resolvedJob.source === "archive") {
      logger.log(`Job за ${dateKey} загружен из JSON-архива для явной операторской операции.`);
    }
    if (args.visible) {
      logger.warn(
        "--visible: роботизированный Яндекс.Браузер будет запущен несвёрнутым для incident diagnostics/recovery."
      );
    }
    if (args.recoverPreEditLinkError) {
      if (!args.apply) {
        throw new Error(
          "--recover-pre-edit-link-error требует --apply: recovery является изменением state."
        );
      }
      authorizePreEditLinkRecovery(config, state, job, logger);
    }

    const av = ensureArticleVideoState(job);
    const runMode = args.apply ? "apply" : "dry-run";
    logger.log(
      `=== START article-video date=${dateKey}; status=${av.status}; phase=${av.phase}; ` +
      `mode=${runMode}; apply=${args.apply} ===`
    );

    if (!args.apply && TERMINAL_STATUSES.has(av.status)) {
      logger.log(`DRY-RUN разрешён при terminal state=${av.status}: state не изменяется.`);
    }

    originalClipboard = await readClipboardText();
    global.__AI_AV_ORIGINAL_CLIPBOARD__ = originalClipboard;

    browserSession = require("./browser-session");
    session = await browserSession.launchRobotBrowser(config, {
      log: (message) => logger.log(message),
    });

    if (args.apply) {
      try {
        await runApply(session.primaryPage, config, state, job, dateKey, logger);
      } catch (error) {
        const current = ensureArticleVideoState(job);
        if (
          !VERIFY_ONLY_PHASES.has(current.phase) &&
          current.phase !== "VERIFIED" &&
          current.status !== "COMPLETE" &&
          current.status !== "SKIPPED_EXISTING" &&
          current.status !== "ERROR"
        ) {
          markPrePublishError(config, state, job, error);
        }
        throw error;
      }
    } else {
      await runDryRun(session.primaryPage, dateKey, logger);
    }

    logger.log(`=== END article-video SUCCESS date=${dateKey}; apply=${args.apply} ===`);
  } catch (error) {
    if (!logger && config) logger = createLogger(config);
    if (logger) {
      const shot = session && session.primaryPage
        ? await screenshot(session.primaryPage, config, dateKey || "unknown", "ERROR")
        : null;
      logger.fatal(
        `Этап остановлен: ${error.message}${shot ? `. Скриншот: ${shot}` : ""}`,
        error
      );
    } else {
      console.error(error.stack || error.message);
    }
    process.exitCode = 1;
  } finally {
    if (originalClipboard !== null) {
      await writeClipboardText(originalClipboard).then(() => {
        if (logger) logger.log("Исходный текст Windows clipboard восстановлен.");
      }).catch((error) => {
        if (logger) logger.fatal(`Не удалось восстановить clipboard: ${error.message}`, error);
        process.exitCode = 1;
      });
    }
    delete global.__AI_AV_ORIGINAL_CLIPBOARD__;

    if (session) {
      await browserSession.closeRobotBrowser(session, config).catch((error) => {
        if (logger) logger.fatal(`Не удалось закрыть браузер: ${error.message}`, error);
        process.exitCode = 1;
      });
      if (logger) logger.log("Роботизированный Яндекс.Браузер закрыт.");
    }
  }
}

module.exports = {
  ANCHOR_TEXT,
  HEADING_TEXT,
  TERMINAL_STATUSES,
  VERIFY_ONLY_PHASES,
  findJobForDate,
  formatRussianLongDate,
  headingMatchesOracle,
  expectedPublicationUrlFromCandidates,
  isSafePreEditLinkResolutionError,
  main,
  parseDateKey,
  planDescriptionArticleUrlUpdate,
  prerequisitesSatisfied,
  updateArticleVideo,
};

if (require.main === module) {
  main().catch((error) => {
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}