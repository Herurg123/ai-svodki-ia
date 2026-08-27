"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const browserSession = require("./browser-session");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");

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

function runNodeScript(scriptName, args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(ROOT, scriptName), ...args], {
      cwd: ROOT,
      stdio: "inherit",
      windowsHide: false,
    });
    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) {
        resolve();
        return;
      }
      reject(new Error(
        `${scriptName} завершился с кодом ${code === null ? "null" : code}` +
        (signal ? `, signal=${signal}` : "")
      ));
    });
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
    `Playwright-процесс завершился до сохранения draft, но Дзен уже создал videoEditorPublicationId=${draftId}. Draft сохранён в state.json; продолжаю тот же draft без создания нового.`
  );
  return true;
}

async function main(argv = process.argv.slice(2)) {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }

  const config = loadJson(CONFIG_PATH);
  const { mode, childArgs, date } = parseArgs(argv);
  const dateKey = date || formatDateKey(new Date(), config.timeZone);
  const target = mode === "dry-run" ? "dzen-publish.js" : "dzen-publish-live.js";
  const targetArgs = mode === "dry-run" ? ["--dry-run", ...childArgs] : childArgs;

  log(config, `запускаю ${target} через browser bootstrap рабочего worker.js.`);
  const session = await browserSession.launchRobotBrowser(config, {
    log: (message) => log(config, message),
  });

  try {
    try {
      await runNodeScript(target, targetArgs);
    } catch (error) {
      const recovered = await recoverDraftCreatedBeforeChildExit(
        session,
        config,
        dateKey
      );
      if (!recovered) throw error;

      log(config, "повторно запускаю Dzen flow после восстановления уже созданного draft.");
      await runNodeScript(target, targetArgs);
    }
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
  findJobForDate,
  main,
  parseArgs,
  recoverDraftCreatedBeforeChildExit,
};
