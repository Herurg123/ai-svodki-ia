"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const browserSession = require("./browser-session");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const OPERATOR_WINDOW_MS = 10 * 60 * 1000;
const RETRY_DELAY_MS = 5 * 1000;
const EMPTY_DRAFT_MIN_AGE_MS = 60 * 1000;
const DRAFT_PROBE_TIMEOUT_MS = 15 * 1000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}

function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
}

function appendLine(filePath, line) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${line}\r\n`, "utf8");
}

function formatTime(timeZone) {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
}

function formatDateKey(date, timeZone) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const values = {};
  for (const part of parts) {
    if (["year", "month", "day"].includes(part.type)) values[part.type] = part.value;
  }
  return `${values.year}-${values.month}-${values.day}`;
}

function log(config, message) {
  const line = `[${formatTime(config.timeZone)}] DZEN: ${message}`;
  console.log(line);
  appendLine(config.regularLog, line);
}

function warn(config, message) {
  const line = `[${formatTime(config.timeZone)}] !!! DZEN: ${message}`;
  console.warn(line);
  appendLine(config.regularLog, line);
}

function parseArgs(argv) {
  const args = [...argv];
  let mode = "publish";
  if (args[0] === "--dry-run") {
    mode = "dry-run";
    args.shift();
  }
  const dateArg = args.find((arg) => arg.startsWith("--date="));
  return {
    mode,
    childArgs: args,
    date: dateArg ? dateArg.slice("--date=".length).trim() : null,
  };
}

function terminateChildTree(child) {
  if (!child || !child.pid) return;

  if (process.platform === "win32") {
    const killer = spawn(
      "taskkill.exe",
      ["/PID", String(child.pid), "/T", "/F"],
      { windowsHide: true, stdio: "ignore" }
    );
    killer.unref();
    return;
  }

  try {
    child.kill("SIGTERM");
  } catch {}
}

function runNodeScript(scriptName, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    let settled = false;
    const child = spawn(process.execPath, [path.join(ROOT, scriptName), ...args], {
      cwd: ROOT,
      stdio: "inherit",
      windowsHide: false,
    });

    let timer = null;
    const finish = (error = null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) reject(error);
      else resolve();
    };

    child.once("error", (error) => finish(error));
    child.once("exit", (code, signal) => {
      if (code === 0) {
        finish();
        return;
      }
      finish(new Error(
        `${scriptName} завершился с кодом ${code === null ? "null" : code}` +
        (signal ? `, signal=${signal}` : "")
      ));
    });

    timer = setTimeout(() => {
      terminateChildTree(child);
      finish(new Error(
        `${scriptName} не завершился за оставшееся операторское окно ${timeoutMs} мс.`
      ));
    }, Math.max(1_000, timeoutMs));
  });
}

function findJobForDate(state, dateKey) {
  const jobs = Object.values((state && state.jobs) || {}).filter(
    (job) => job && job.date === dateKey
  );
  jobs.sort((a, b) => String(b.downloadedAt || b.updatedAt || "").localeCompare(
    String(a.downloadedAt || a.updatedAt || "")
  ));
  return jobs[0] || null;
}

async function recoverDraftCreatedBeforeChildExit(session, config, dateKey) {
  const state = loadJson(config.stateFile, { jobs: {} });
  const job = findJobForDate(state, dateKey);
  if (!job) return false;

  if (job.dzenVideo?.draftUrl) {
    return false;
  }

  const pages = session.context.pages().filter((page) => !page.isClosed());
  const draftPage = pages.find((page) => {
    try {
      return new URL(page.url()).searchParams.has("videoEditorPublicationId");
    } catch {
      return false;
    }
  });
  if (!draftPage) return false;

  const draftUrl = draftPage.url();
  const draftId = new URL(draftUrl).searchParams.get("videoEditorPublicationId");
  if (!draftId) return false;

  job.dzenVideo = {
    ...(job.dzenVideo || {}),
    status: "DRAFT_CREATED",
    draftId,
    draftUrl,
    videoFile: job.downloadedFile || null,
    recoveredAfterUploadTimeout: true,
    recoveredAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  };
  saveJsonAtomic(config.stateFile, state);
  warn(
    config,
    `Playwright-процесс завершился до сохранения draft, но Дзен уже создал videoEditorPublicationId=${draftId}. Draft сохранён в state.json; следующий явный запуск сможет решить, безопасно ли продолжать его без нового upload.`
  );
  return true;
}

function draftCreatedAtMs(dzenVideo) {
  const raw = dzenVideo?.createdAt || dzenVideo?.recoveredAt || dzenVideo?.updatedAt;
  const parsed = raw ? Date.parse(raw) : NaN;
  return Number.isFinite(parsed) ? parsed : 0;
}

async function hasVideoEditorUi(page) {
  const metadataSelectors = [
    'textarea[maxlength="140"]',
    'input[maxlength="140"]',
    'textarea[maxlength="5000"]',
    'textarea[placeholder*="Описание"]',
    'textarea[placeholder*="описание"]',
    '.ql-editor',
  ];
  for (const selector of metadataSelectors) {
    const locator = page.locator(selector);
    const count = await locator.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      if (await locator.nth(i).isVisible().catch(() => false)) return true;
    }
  }

  for (const text of [
    "Добавить обложку",
    "Теги через запятую",
    "Кто может комментировать",
    "Загрузили и обработали видео",
  ]) {
    const locator = page.getByText(text, { exact: true });
    const count = await locator.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      if (await locator.nth(i).isVisible().catch(() => false)) return true;
    }
  }

  return false;
}

async function isStudioDashboard(page) {
  const bodyText = await page.locator("body").innerText().catch(() => "");
  const markers = [
    "Статистика",
    "Последние публикации",
    "Последние комментарии",
    "Важное",
  ];
  return markers.filter((marker) => bodyText.includes(marker)).length >= 2;
}

async function isClearlyEmptyRemoteDraft(session, dzenVideo) {
  if (!dzenVideo?.draftUrl || dzenVideo.status !== "DRAFT_CREATED") {
    return false;
  }

  const createdAtMs = draftCreatedAtMs(dzenVideo);
  if (createdAtMs && Date.now() - createdAtMs < EMPTY_DRAFT_MIN_AGE_MS) {
    return false;
  }

  const page = await session.context.newPage();
  try {
    await page.goto(dzenVideo.draftUrl, {
      waitUntil: "domcontentloaded",
      timeout: 60_000,
    });

    const probeDeadline = Date.now() + DRAFT_PROBE_TIMEOUT_MS;
    while (Date.now() < probeDeadline) {
      let currentUrlHasDraftId = false;
      try {
        currentUrlHasDraftId = new URL(page.url()).searchParams.has("videoEditorPublicationId");
      } catch {}

      if (!currentUrlHasDraftId) {
        return true;
      }

      if (await hasVideoEditorUi(page)) {
        return false;
      }

      const chooseVideo = page.getByRole("button", {
        name: "Выбрать видео",
        exact: true,
      });
      if (
        (await chooseVideo.count().catch(() => 0)) > 0 &&
        (await chooseVideo.first().isVisible().catch(() => false))
      ) {
        await page.waitForTimeout(2_000);
        if (await chooseVideo.first().isVisible().catch(() => false)) {
          return true;
        }
      }

      if (await isStudioDashboard(page)) {
        await page.waitForTimeout(2_000);
        if (!(await hasVideoEditorUi(page)) && await isStudioDashboard(page)) {
          return true;
        }
      }

      await page.waitForTimeout(500);
    }

    return false;
  } catch {
    return false;
  } finally {
    await page.close().catch(() => {});
  }
}

async function resetClearlyEmptyDraft(session, config, dateKey) {
  const state = loadJson(config.stateFile, { jobs: {} });
  const job = findJobForDate(state, dateKey);
  const dzenVideo = job?.dzenVideo;

  if (!job || !dzenVideo || [
    "READY_TO_PUBLISH",
    "PUBLISHING",
    "PUBLISH_CLICKED_UNVERIFIED",
    "PUBLISHED",
  ].includes(dzenVideo.status)) {
    return false;
  }

  if (!(await isClearlyEmptyRemoteDraft(session, dzenVideo))) {
    return false;
  }

  const previousDrafts = Array.isArray(dzenVideo.previousDrafts)
    ? [...dzenVideo.previousDrafts]
    : [];
  previousDrafts.push({
    draftId: dzenVideo.draftId || null,
    draftUrl: dzenVideo.draftUrl || null,
    status: dzenVideo.status || null,
    abandonedReason: "remote draft did not resolve to a usable video editor",
    abandonedAt: new Date().toISOString(),
  });

  job.dzenVideo = {
    previousDrafts,
    status: "RETRY_NEW_DRAFT",
    updatedAt: new Date().toISOString(),
  };
  saveJsonAtomic(config.stateFile, state);

  warn(
    config,
    `сохранённый draft ${dzenVideo.draftId || dzenVideo.draftUrl} не открыл пригодный видеоредактор Дзена. Не переиспользую его и не удаляю удалённый draft; следующий проход создаст новый video draft.`
  );
  return true;
}

async function runDryRunWithRecovery(session, config, dateKey, target, targetArgs, deadline) {
  let lastError = null;
  while (Date.now() < deadline) {
    await resetClearlyEmptyDraft(session, config, dateKey);

    const remainingMs = Math.max(1_000, deadline - Date.now());
    try {
      await runNodeScript(target, targetArgs, remainingMs);
      return;
    } catch (error) {
      lastError = error;
      await recoverDraftCreatedBeforeChildExit(session, config, dateKey);

      const stillRemainingMs = deadline - Date.now();
      if (stillRemainingMs <= 0) break;

      warn(
        config,
        `${target} завершился промежуточной диагностической ошибкой: ${error.message}. Для dry-run повторяю flow через ${Math.min(RETRY_DELAY_MS, stillRemainingMs)} мс.`
      );
      await sleep(Math.min(RETRY_DELAY_MS, stillRemainingMs));
    }
  }

  throw new Error(
    `Dzen dry-run не завершился за максимальное операторское окно 10 минут.` +
    (lastError ? ` Последняя ошибка: ${lastError.message}` : "")
  );
}

async function main(argv = process.argv.slice(2)) {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }

  const config = loadJson(CONFIG_PATH);
  const { mode, childArgs, date } = parseArgs(argv);
  const dateKey = date || formatDateKey(new Date(), config.timeZone);
  const target = mode === "dry-run" ? "dzen-publish.js" : "dzen-publish-direct.js";
  const targetArgs = mode === "dry-run" ? ["--dry-run", ...childArgs] : childArgs;
  const deadline = Date.now() + OPERATOR_WINDOW_MS;

  log(config, `запускаю ${target} через browser bootstrap рабочего worker.js.`);
  if (mode === "publish") {
    log(config, "live publish выполняется одним child-проходом без автоматического повторного запуска; при ошибке состояние сохраняется для следующего явного операторского запуска.");
  } else {
    log(config, "diagnostic dry-run сохраняет операторское окно восстановления до 10 минут.");
  }

  const session = await browserSession.launchRobotBrowser(config, {
    log: (message) => log(config, message),
  });

  try {
    if (mode === "publish") {
      try {
        await runNodeScript(target, targetArgs, OPERATOR_WINDOW_MS);
        return;
      } catch (error) {
        await recoverDraftCreatedBeforeChildExit(session, config, dateKey);
        warn(
          config,
          `${target} завершился ошибкой: ${error.message}. Автоматический повтор live-flow в этом запуске отключён; повтор возможен только новой явной операторской командой.`
        );
        throw error;
      }
    }

    return await runDryRunWithRecovery(
      session,
      config,
      dateKey,
      target,
      targetArgs,
      deadline
    );
  } finally {
    await browserSession.closeRobotBrowser(session, config);
  }
}

if (require.main === module) {
  main().catch((error) => {
    console.error("");
    console.error("ОШИБКА DZEN BROWSER BOOTSTRAP:");
    console.error(error.stack || error.message);
    process.exitCode = 1;
  });
}

module.exports = {
  DRAFT_PROBE_TIMEOUT_MS,
  EMPTY_DRAFT_MIN_AGE_MS,
  OPERATOR_WINDOW_MS,
  RETRY_DELAY_MS,
  findJobForDate,
  hasVideoEditorUi,
  isClearlyEmptyRemoteDraft,
  isStudioDashboard,
  main,
  parseArgs,
  recoverDraftCreatedBeforeChildExit,
  resetClearlyEmptyDraft,
  runDryRunWithRecovery,
};
