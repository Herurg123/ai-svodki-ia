"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const duplicateGuard = require("./dzen-duplicate-guard");
const dzenHelpers = require("./dzen-publish");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const ORCHESTRATOR_LOCK_PATH = path.join(ROOT, "scheduled-worker.lock");
const DEFAULT_VERIFY_TIMEOUT_MS = 90_000;
const VERIFY_RETRY_DELAY_MS = 5_000;

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}

function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.scheduled-${process.pid}-${Date.now()}.tmp`;
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
    timeZone: timeZone || "Europe/Moscow",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
}

function log(config, message) {
  const line = `[${formatTime(config && config.timeZone)}] AUTO-WORKER: ${message}`;
  console.log(line);
  appendLine(config && config.regularLog, line);
}

function fatalLog(config, message, error = null) {
  const suffix = error && error.stack ? `\r\n${error.stack}` : "";
  const line = `[${formatTime(config && config.timeZone)}] !!! AUTO-WORKER: ${message}${suffix}`;
  console.error(line);
  appendLine(config && config.regularLog, line);
  if (config && config.errorLog && config.errorLog !== config.regularLog) {
    appendLine(config.errorLog, line);
  }
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

function processIsAlive(pid) {
  if (!Number.isInteger(pid) || pid <= 0) return false;
  try {
    process.kill(pid, 0);
    return true;
  } catch (error) {
    return error && error.code === "EPERM";
  }
}

function acquireOrchestratorLock() {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const handle = fs.openSync(ORCHESTRATOR_LOCK_PATH, "wx");
      fs.writeFileSync(
        handle,
        JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }),
        "utf8"
      );
      return handle;
    } catch (error) {
      if (!error || error.code !== "EEXIST") throw error;

      const previous = loadJson(ORCHESTRATOR_LOCK_PATH, {});
      if (processIsAlive(Number(previous && previous.pid))) {
        return null;
      }

      fs.rmSync(ORCHESTRATOR_LOCK_PATH, { force: true });
    }
  }
  return null;
}

function releaseOrchestratorLock(handle) {
  if (handle === null || handle === undefined) return;
  try { fs.closeSync(handle); } catch {}
  try { fs.rmSync(ORCHESTRATOR_LOCK_PATH, { force: true }); } catch {}
}

function runNodeScript(scriptName, args = []) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [path.join(ROOT, scriptName), ...args], {
      cwd: ROOT,
      stdio: "inherit",
      windowsHide: false,
    });

    child.once("error", reject);
    child.once("exit", (code, signal) => {
      if (code === 0) {
        resolve({ code: 0, signal: signal || null });
        return;
      }
      const error = new Error(
        `${scriptName} завершился с кодом ${code === null ? "null" : code}` +
          (signal ? `, signal=${signal}` : "")
      );
      error.exitCode = code;
      error.signal = signal || null;
      reject(error);
    });
  });
}

function findLatestDoneJob(state, maxDateKey) {
  const jobs = Object.values((state && state.jobs) || {}).filter(
    (job) =>
      job &&
      job.status === "DONE" &&
      typeof job.date === "string" &&
      job.date <= maxDateKey
  );

  jobs.sort((a, b) => {
    const byDate = String(b.date).localeCompare(String(a.date));
    if (byDate !== 0) return byDate;
    return String(b.downloadedAt || b.updatedAt || "").localeCompare(
      String(a.downloadedAt || a.updatedAt || "")
    );
  });

  return jobs[0] || null;
}

function normalizeAutomaticDzenConfig(rawConfig) {
  const config = dzenHelpers.applyDzenConfigDefaults(rawConfig);
  const rawDzen = rawConfig && rawConfig.dzenUpload && typeof rawConfig.dzenUpload === "object"
    ? rawConfig.dzenUpload
    : {};

  if (
    rawDzen.automaticEnabled !== undefined &&
    typeof rawDzen.automaticEnabled !== "boolean"
  ) {
    throw new Error("dzenUpload.automaticEnabled должен быть true или false.");
  }

  config.dzenUpload.automaticEnabled = rawDzen.automaticEnabled !== false;
  if (config.dzenUpload.automaticEnabled) {
    // automaticEnabled is the production scheduler switch. Legacy `enabled`
    // existed while Dzen was operator-only and must not silently disable the
    // promoted scheduled path in an existing config.json.
    config.dzenUpload.enabled = true;
  }

  const verifyTimeout = Number(rawDzen.verificationTimeoutMs);
  config.dzenUpload.verificationTimeoutMs =
    Number.isInteger(verifyTimeout) && verifyTimeout >= 30_000
      ? verifyTimeout
      : DEFAULT_VERIFY_TIMEOUT_MS;

  return config;
}

function dzenAutomationEnabled(config) {
  return Boolean(config && config.dzenUpload && config.dzenUpload.automaticEnabled !== false);
}

function getAutomationStatus(job) {
  return String(job && job.dzenAutomation && job.dzenAutomation.status || "PENDING");
}

function shouldRunFreshUpload(status) {
  return ["PENDING", "RETRYABLE_PRE_CLICK"].includes(String(status || "PENDING"));
}

function isVerificationOnlyStatus(status) {
  return [
    "PUBLISH_ARMED",
    "CLICKED_UNVERIFIED",
    "BLOCKED_AMBIGUOUS",
  ].includes(String(status || ""));
}

function classifyDzenFailureOutput(output) {
  const text = String(output || "");
  if (/publishClicked=false/i.test(text)) return "PRE_CLICK_RETRYABLE";
  if (/publishClicked=true/i.test(text) || /КЛИК ПУБЛИКАЦИИ ВЫПОЛНЕН ОДИН РАЗ/i.test(text)) {
    return "POST_CLICK_OR_AMBIGUOUS";
  }
  return "AMBIGUOUS";
}

function updateDzenAutomation(config, state, job, status, fields = {}) {
  const now = new Date().toISOString();
  job.dzenAutomation = {
    ...(job.dzenAutomation || {}),
    ...fields,
    status,
    updatedAt: now,
  };
  job.updatedAt = now;
  saveJsonAtomic(config.stateFile, state);
}

async function verifyPublished(session, config, dateArg, logFn) {
  const deadline = Date.now() + config.dzenUpload.verificationTimeoutMs;
  let last = null;
  let attempt = 0;

  while (Date.now() < deadline) {
    attempt += 1;
    last = await duplicateGuard.checkBeforeUpload(
      session.primaryPage,
      config,
      [dateArg],
      logFn
    );

    if (last.existing) return last;

    logFn(
      `verification-only: попытка ${attempt} не нашла опубликованное Видео; ` +
        `новый upload всё равно запрещён.`
    );

    const remaining = deadline - Date.now();
    if (remaining <= 0) break;
    await new Promise((resolve) =>
      setTimeout(resolve, Math.min(VERIFY_RETRY_DELAY_MS, remaining))
    );
  }

  return null;
}

async function runAutomaticDzen(config, state, job, dateKey) {
  if (!dzenAutomationEnabled(config)) {
    log(config, "Автоматическая публикация в Дзен отключена dzenUpload.automaticEnabled=false.");
    return { skipped: true, reason: "disabled" };
  }

  if (!job.downloadedFile || !fs.existsSync(job.downloadedFile)) {
    throw new Error(
      `Dzen-фаза не может стартовать: локальный MP4 отсутствует: ${job.downloadedFile || "путь не задан"}`
    );
  }

  const status = getAutomationStatus(job);
  if (status === "PUBLISHED") {
    log(config, `Дзен уже подтверждён как опубликованный для ${dateKey}.`);
    return { skipped: true, reason: "already-published" };
  }

  const browserSession = require("./browser-session");
  const dzenRunner = require("./dzen-browser-runner");

  const dateArg = `--date=${dateKey}`;
  let session = null;

  try {
    session = await browserSession.launchRobotBrowser(config, {
      log: (message) => log(config, `DZEN: ${message}`),
    });

    const precheck = await duplicateGuard.checkBeforeUpload(
      session.primaryPage,
      config,
      [dateArg],
      (message) => log(config, `DZEN: ${message}`)
    );

    if (precheck.existing) {
      updateDzenAutomation(config, state, job, "PUBLISHED", {
        confirmedAt: new Date().toISOString(),
        confirmedBy: "duplicate-guard",
        foundTitle: precheck.foundText,
        titlePrefix: precheck.titlePrefix,
        lastError: null,
        lastErrorAt: null,
      });
      log(config, `Dzen-фаза завершена: опубликованное Видео подтверждено duplicate guard.`);
      return { published: true, existing: true };
    }

    if (isVerificationOnlyStatus(status)) {
      log(
        config,
        `Dzen status=${status}: разрешена только проверка публикации, новый upload и второй publish click запрещены.`
      );

      const verified = await verifyPublished(
        session,
        config,
        dateArg,
        (message) => log(config, `DZEN: ${message}`)
      );

      if (verified) {
        updateDzenAutomation(config, state, job, "PUBLISHED", {
          confirmedAt: new Date().toISOString(),
          confirmedBy: "verification-only",
          foundTitle: verified.foundText,
          titlePrefix: verified.titlePrefix,
          lastError: null,
          lastErrorAt: null,
        });
        return { published: true, existing: true };
      }

      const error = new Error(
        `После publish-неопределённости Видео за ${dateKey} не подтверждено во вкладке «Видео». ` +
          `Новый upload заблокирован до подтверждения.`
      );
      updateDzenAutomation(config, state, job, status, {
        lastVerifiedAt: new Date().toISOString(),
        lastError: error.message,
        lastErrorAt: new Date().toISOString(),
      });
      throw error;
    }

    if (!shouldRunFreshUpload(status)) {
      throw new Error(`Неизвестный dzenAutomation.status: ${status}`);
    }

    updateDzenAutomation(config, state, job, "PUBLISH_ARMED", {
      armedAt: new Date().toISOString(),
      lastError: null,
      lastErrorAt: null,
    });

    log(
      config,
      "Duplicate guard чист. Перед запуском live child сохранён PUBLISH_ARMED; " +
        "при неоднозначном падении следующий scheduled run не сможет сделать второй click."
    );

    const childTimeoutMs = Math.max(
      dzenRunner.OPERATOR_WINDOW_MS,
      Number(config.dzenUpload.processingTimeoutMs || 600_000) + 120_000
    );

    try {
      await dzenRunner.runNodeScript(
        "dzen-publish-direct.js",
        [dateArg],
        childTimeoutMs
      );
    } catch (error) {
      const classification = classifyDzenFailureOutput(error.childOutput);

      if (classification === "PRE_CLICK_RETRYABLE") {
        updateDzenAutomation(config, state, job, "RETRYABLE_PRE_CLICK", {
          lastError: error.message,
          lastErrorAt: new Date().toISOString(),
        });
        log(
          config,
          "Live child явно сообщил publishClicked=false. Следующий scheduled run сможет начать новый fresh upload после duplicate guard."
        );
      } else {
        updateDzenAutomation(config, state, job, "BLOCKED_AMBIGUOUS", {
          lastError: error.message,
          lastErrorAt: new Date().toISOString(),
        });
        log(
          config,
          "Live child завершился неоднозначно после PUBLISH_ARMED. Следующие запуски только проверяют вкладку «Видео»; второй click запрещён."
        );
      }

      throw error;
    }

    updateDzenAutomation(config, state, job, "CLICKED_UNVERIFIED", {
      clickedAt: new Date().toISOString(),
      lastError: null,
      lastErrorAt: null,
    });

    log(
      config,
      "Live child завершился успешно. Состояние CLICKED_UNVERIFIED сохранено; начинаю post-click verification без второго click."
    );

    const verified = await verifyPublished(
      session,
      config,
      dateArg,
      (message) => log(config, `DZEN: ${message}`)
    );

    if (!verified) {
      const error = new Error(
        `Publish child завершился, но Видео за ${dateKey} не появилось во вкладке «Видео» ` +
          `за ${config.dzenUpload.verificationTimeoutMs} мс. Состояние оставлено CLICKED_UNVERIFIED; новый upload запрещён.`
      );
      updateDzenAutomation(config, state, job, "CLICKED_UNVERIFIED", {
        lastVerifiedAt: new Date().toISOString(),
        lastError: error.message,
        lastErrorAt: new Date().toISOString(),
      });
      throw error;
    }

    updateDzenAutomation(config, state, job, "PUBLISHED", {
      confirmedAt: new Date().toISOString(),
      confirmedBy: "post-click-verification",
      foundTitle: verified.foundText,
      titlePrefix: verified.titlePrefix,
      lastError: null,
      lastErrorAt: null,
    });

    log(config, `Dzen-фаза полностью подтверждена: Видео за ${dateKey} опубликовано.`);
    return { published: true, existing: false };
  } finally {
    if (session) {
      await browserSession.closeRobotBrowser(session, config);
    }
  }
}

async function main() {
  let config = null;
  let lockHandle = null;

  try {
    if (!fs.existsSync(CONFIG_PATH)) {
      throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
    }

    const rawConfig = loadJson(CONFIG_PATH);
    config = normalizeAutomaticDzenConfig(rawConfig);

    lockHandle = acquireOrchestratorLock();
    if (lockHandle === null) {
      log(config, "Другой scheduled-worker.js уже работает. Новый экземпляр завершён без запуска дочерних процессов.");
      return;
    }

    log(config, "=== START scheduled full worker ===");
    log(config, "Фаза 1/2: запускаю существующий NotebookLM worker.js.");

    try {
      await runNodeScript("worker.js");
    } catch (error) {
      if (error.exitCode === 3) {
        process.exitCode = 3;
        log(config, "NotebookLM worker остановлен защитой IP. Dzen-фаза не запускается.");
        return;
      }
      throw error;
    }

    const state = loadJson(config.stateFile, { jobs: {} });
    const currentDateKey = formatDateKey(new Date(), config.timeZone);
    const job = findLatestDoneJob(state, currentDateKey);

    if (!job) {
      log(
        config,
        `Фаза 2/2: нет локального DONE job с датой не позже ${currentDateKey}. ` +
          "Dzen-фаза пока не нужна."
      );
      return;
    }

    const dateKey = job.date;
    if (dateKey !== currentDateKey) {
      log(
        config,
        `Фаза 2/2: catch-up режим, самый свежий DONE job имеет дату ${dateKey}, ` +
          `текущая локальная дата ${currentDateKey}.`
      );
    }

    log(config, `Фаза 2/2: локальный job DONE. Запускаю автоматическую Dzen-фазу за ${dateKey}.`);
    await runAutomaticDzen(config, state, job, dateKey);
    log(config, "=== END scheduled full worker SUCCESS ===");
  } catch (error) {
    fatalLog(config, error.message, error);
    process.exitCode = process.exitCode || 1;
  } finally {
    releaseOrchestratorLock(lockHandle);
  }
}

module.exports = {
  DEFAULT_VERIFY_TIMEOUT_MS,
  ORCHESTRATOR_LOCK_PATH,
  VERIFY_RETRY_DELAY_MS,
  classifyDzenFailureOutput,
  dzenAutomationEnabled,
  findLatestDoneJob,
  formatDateKey,
  getAutomationStatus,
  isVerificationOnlyStatus,
  normalizeAutomaticDzenConfig,
  shouldRunFreshUpload,
};

if (require.main === module) {
  main();
}
