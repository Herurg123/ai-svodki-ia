"use strict";

// Operator-assisted recovery of an already-uploaded Dzen video.
// This script NEVER uploads, edits metadata, clicks Publish, or interacts with CAPTCHA.
const fs = require("node:fs");
const path = require("node:path");
const readline = require("node:readline/promises");
const history = require("./history-utils");
const dzen = require("./dzen-publish");
const duplicate = require("./dzen-duplicate-guard");
const browserSession = require("./browser-session");
const fullWorker = require("./full-worker");
const scheduled = require("./scheduled-worker");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const DRAFT_ID = /^[0-9a-f]{24}$/i;

function parseArgs(argv) {
  let date = null;
  let mode = "status";
  for (const arg of argv) {
    if (arg.startsWith("--date=")) {
      if (date !== null) throw new Error("Параметр --date задан дважды.");
      date = arg.slice(7);
    } else if (arg === "--assist") {
      mode = "assist";
    } else if (arg === "--status") {
      mode = "status";
    } else {
      throw new Error(`Неизвестный параметр: ${arg}`);
    }
  }
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date || "")) {
    throw new Error("Нужна точная дата: --date=YYYY-MM-DD.");
  }
  history.parseDateKey(date);
  return { date, mode };
}

function pinnedJob(config, date) {
  const state = history.loadActiveState(config);
  const found = history.findJobForDateIncludingArchive(config, state, date);
  if (!found) throw new Error(`В state/archive нет выпуска ${date}.`);
  const job = dzen.findJobForDate(state, date);
  const saved = job.dzenAutomation || {};
  const draftId = String(saved.draftId || "");
  if (!DRAFT_ID.test(draftId)) throw new Error("В выпуске нет подтверждённого draftId; восстановление запрещено.");
  if (!["CLICKED_UNVERIFIED", "PUBLISHED"].includes(saved.status)) {
    throw new Error(`Неподходящий checkpoint ${saved.status || "PENDING"}; скрипт работает только с CLICKED_UNVERIFIED/PUBLISHED.`);
  }
  return { state, job, status: saved.status, draftId, source: found.source,
    editorUrl: `${duplicate.PUBLICATIONS_URL}?state=draft&videoEditorPublicationId=${draftId}` };
}

function checkIdentity(check, draftId) {
  if (!check || !check.existing) return "ABSENT";
  return duplicate.pinnedPublishedIdentity(check, draftId);
}

function markVerifiedPublished(config, date, draftId, check) {
  if (checkIdentity(check, draftId) !== "MATCH" ||
      duplicate.extractPublishedVideoId(check.publishedVideoUrl) !== draftId.toLowerCase()) {
    throw new Error("Публичный URL не подтверждает точный draftId; состояние не изменено.");
  }
  // Fresh reload protects concurrent state updates and archive rehydration.
  const latest = pinnedJob(config, date);
  if (latest.draftId.toLowerCase() !== draftId.toLowerCase()) {
    throw new Error("draftId в state.json изменился во время проверки. Запись запрещена.");
  }
  if (latest.status === "PUBLISHED") return "already-published";
  const now = new Date().toISOString();
  latest.job.dzenAutomation = {
    ...latest.job.dzenAutomation,
    status: "PUBLISHED",
    publishedVideoUrl: check.publishedVideoUrl,
    foundTitle: check.foundText || null,
    titlePrefix: check.titlePrefix || duplicate.titlePrefixForDuplicateCheck(dzen.buildDzenTitle(date)),
    confirmedBy: "manual-recovery-exact-public-video-id",
    confirmedAt: now,
    lastError: null,
    lastErrorAt: null,
    updatedAt: now,
  };
  latest.job.updatedAt = now;
  history.saveStateWithRetention(config, latest.state);
  return "published";
}

async function awaitOperatorEnter() {
  const prompt = readline.createInterface({ input: process.stdin, output: process.stdout });
  const controller = new AbortController();
  const abort = () => controller.abort();
  process.once("SIGINT", abort);
  try {
    await prompt.question(
      "Заверши публикацию вручную в браузере (и проверку человека, если есть). Затем нажми Enter для проверки: ",
      { signal: controller.signal }
    );
  } finally {
    process.off("SIGINT", abort);
    prompt.close();
  }
}

async function main(argv = process.argv.slice(2)) {
  const { date, mode } = parseArgs(argv);
  if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  const config = JSON.parse(fs.readFileSync(CONFIG_PATH, "utf8").replace(/^\uFEFF/, ""));
  const target = pinnedJob(config, date);
  console.log(JSON.stringify({ date, status: target.status, draftId: target.draftId,
    source: target.source, editorUrl: target.editorUrl, mode }, null, 2));
  if (mode === "status") return { status: target.status, draftId: target.draftId };
  if (target.status === "PUBLISHED") {
    console.log("Состояние уже PUBLISHED. Дополнительные действия не нужны.");
    return { status: "already-published" };
  }

  // The normal scheduler holds full-worker.lock. Reserve that lock so a new
  // scheduled flow cannot start between operator inspection and verification.
  // A second guard covers direct scheduled-worker invocations as well.
  if (fs.existsSync(scheduled.ORCHESTRATOR_LOCK_PATH)) {
    throw new Error("scheduled-worker.lock существует: сначала останови комбайн и дождись завершения процесса.");
  }
  const fullLock = fullWorker.acquireFullWorkerLock();
  if (fullLock === null) throw new Error("full-worker.lock занят: другой комбайн уже выполняется.");
  let innerLock = null;
  let session = null;
  try {
    try {
      innerLock = fs.openSync(scheduled.ORCHESTRATOR_LOCK_PATH, "wx");
      fs.writeFileSync(innerLock, JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }));
    } catch (err) {
      if (err.code === "EEXIST") throw new Error("scheduled-worker.lock занят: восстановление запрещено.");
      throw err;
    }

    session = await browserSession.launchRobotBrowser({ ...config, minimizeBrowserWindow: false }, {
      log: (message) => console.log(`DZEN recovery: ${message}`),
    });
    const log = (message) => console.log(`DZEN recovery: ${message}`);
    const before = await duplicate.checkBeforeUpload(session.primaryPage, config, [`--date=${date}`], log);
    const beforeIdentity = checkIdentity(before, target.draftId);
    if (beforeIdentity === "MATCH") {
      markVerifiedPublished(config, date, target.draftId, before);
      console.log("Опубликованное видео уже найдено по точному ID, checkpoint подтверждён.");
      return { status: "published" };
    }
    if (beforeIdentity !== "ABSENT") {
      throw new Error(`Найден одноимённый опубликованный материал, но identity=${beforeIdentity}; не открываю черновик.`);
    }

    const title = dzen.buildDzenTitle(date);
    const inspection = await duplicate.inspectPinnedDraft(session.primaryPage, target.draftId, title, log);
    if (inspection !== "PRESENT") {
      throw new Error(`Существующий черновик не подтверждён по ID/названию (${inspection}). Никаких действий не выполнено.`);
    }
    await session.primaryPage.bringToFront();
    console.log("Открыт только исходный черновик. Автоматика НЕ нажимает публикацию и НЕ трогает проверку человека.");
    await awaitOperatorEnter();

    const after = await duplicate.checkBeforeUpload(session.primaryPage, config, [`--date=${date}`], log);
    const afterIdentity = checkIdentity(after, target.draftId);
    if (afterIdentity !== "MATCH") {
      throw new Error(`Публикация не подтверждена точным публичным ID (identity=${afterIdentity}). `+
        "CLICKED_UNVERIFIED сохранён, никаких повторных кликов или загрузок не будет.");
    }
    markVerifiedPublished(config, date, target.draftId, after);
    console.log(`PUBLISHED подтверждён: ${after.publishedVideoUrl}`);
    return { status: "published", url: after.publishedVideoUrl };
  } finally {
    if (session) await browserSession.closeRobotBrowser(session, config).catch((e) => {
      console.warn(`Не удалось закрыть роботизированный браузер: ${e.message}`);
    });
    if (innerLock !== null) {
      try { fs.closeSync(innerLock); } catch {}
      try { fs.rmSync(scheduled.ORCHESTRATOR_LOCK_PATH, { force: true }); } catch {}
    }
    fullWorker.releaseFullWorkerLock(fullLock);
  }
}

if (require.main === module) {
  main().catch((error) => { console.error("DZEN RECOVERY: " + error.message); process.exitCode = 1; });
}
module.exports = { parseArgs, pinnedJob, checkIdentity, markVerifiedPublished, main };
