"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

const scheduled = require("./scheduled-worker");
const collections = require("./dzen-collections");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const FULL_WORKER_LOCK_PATH = path.join(ROOT, "full-worker.lock");

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
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
  const line = `[${formatTime(config && config.timeZone)}] FULL-WORKER: ${message}`;
  console.log(line);
  appendLine(config && config.regularLog, line);
}

function fatalLog(config, message, error = null) {
  const suffix = error && error.stack ? `\r\n${error.stack}` : "";
  const line = `[${formatTime(config && config.timeZone)}] !!! FULL-WORKER: ${message}${suffix}`;
  console.error(line);
  appendLine(config && config.regularLog, line);
  if (config && config.errorLog && config.errorLog !== config.regularLog) {
    appendLine(config.errorLog, line);
  }
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

function acquireFullWorkerLock() {
  for (let attempt = 0; attempt < 2; attempt += 1) {
    try {
      const handle = fs.openSync(FULL_WORKER_LOCK_PATH, "wx");
      fs.writeFileSync(
        handle,
        JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }),
        "utf8"
      );
      return handle;
    } catch (error) {
      if (!error || error.code !== "EEXIST") throw error;
      const previous = loadJson(FULL_WORKER_LOCK_PATH, {});
      if (processIsAlive(Number(previous && previous.pid))) return null;
      fs.rmSync(FULL_WORKER_LOCK_PATH, { force: true });
    }
  }
  return null;
}

function releaseFullWorkerLock(handle) {
  if (handle === null || handle === undefined) return;
  try { fs.closeSync(handle); } catch {}
  try { fs.rmSync(FULL_WORKER_LOCK_PATH, { force: true }); } catch {}
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
      if (code === 0) return resolve({ code: 0, signal: signal || null });
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

function selectCollectionsJob(state, currentDateKey, phasesError = null) {
  // On a failed phases-1/2 attempt, prefer today's job even when it has not
  // reached DONE. That lets the independent collections stage still process the
  // same-day digest while the video side remains broken/retryable.
  if (phasesError) {
    const sameDayJob = collections.findJobForDate(state, currentDateKey);
    if (sameDayJob) return sameDayJob;
  }
  return scheduled.findLatestDoneJob(state, currentDateKey);
}

function articleVideoStatus(job) {
  return String(job && job.dzenArticleVideo && job.dzenArticleVideo.status || "PENDING");
}

function articleVideoPhase(job) {
  return String(job && job.dzenArticleVideo && job.dzenArticleVideo.phase || "PENDING");
}

async function main() {
  let config = null;
  let lockHandle = null;
  let phasesError = null;
  let collectionsError = null;
  let articleVideoError = null;

  try {
    if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
    config = loadJson(CONFIG_PATH);

    lockHandle = acquireFullWorkerLock();
    if (lockHandle === null) {
      log(config, "Другой full-worker.js уже работает. Новый экземпляр завершён без запуска браузера/дочерних процессов.");
      return;
    }

    log(config, "=== START full scheduled flow ===");
    log(config, "Фазы 1-2/4: запускаю существующий scheduled-worker.js (NotebookLM/FTP -> Dzen publish).");
    try {
      await runNodeScript("scheduled-worker.js");
    } catch (error) {
      phasesError = error;
      fatalLog(
        config,
        `Фазы 1-2 завершились ошибкой: ${error.message}. ` +
          "Третья фаза всё равно проверит доступные same-day публикации; фаза 4 при этом НЕ запускается.",
        error
      );
    }

    let state = loadJson(config.stateFile, { jobs: {} });
    const currentDateKey = scheduled.formatDateKey(new Date(), config.timeZone || "Europe/Moscow");
    const job = selectCollectionsJob(state, currentDateKey, phasesError);

    if (!job) {
      log(config, `Фаза 3/4: нет подходящего локального job с датой не позже ${currentDateKey}; подборки не запускаю.`);
    } else if (collections.collectionsComplete(job)) {
      log(
        config,
        `Фаза 3/4: обе подборки за ${job.date} уже подтверждены в state.json ` +
          `(video=ADDED, digest=ADDED). Браузер для подборок НЕ открываю.`
      );
    } else {
      log(
        config,
        `Фаза 3/4: запускаю отдельный этап подборок за ${job.date}; ` +
          `state=${collections.collectionsStatus(job)}; ` +
          `dzenVideo=${scheduled.getAutomationStatus(job)}.`
      );
      try {
        await runNodeScript("dzen-collections.js", ["--apply", `--date=${job.date}`]);
        const refreshed = loadJson(config.stateFile, { jobs: {} });
        const refreshedJob = collections.findJobForDate(refreshed, job.date);
        log(
          config,
          `Фаза 3/4 завершена: dzenCollections.status=${collections.collectionsStatus(refreshedJob)}.`
        );
      } catch (error) {
        collectionsError = error;
        fatalLog(config, `Фаза 3/4 завершилась ошибкой: ${error.message}`, error);
      }
    }

    if (!job) {
      log(config, "Фаза 4/4: нет выбранного job; article-video этап не запускаю.");
    } else if (phasesError || collectionsError) {
      log(
        config,
        "Фаза 4/4 НЕ запускается: она разрешена только после полного успеха всех предыдущих фаз."
      );
    } else {
      state = loadJson(config.stateFile, { jobs: {} });
      const refreshedJob = collections.findJobForDate(state, job.date);
      const dzenStatus = scheduled.getAutomationStatus(refreshedJob);
      const collectionStatus = collections.collectionsStatus(refreshedJob);
      const avStatus = articleVideoStatus(refreshedJob);
      const avPhase = articleVideoPhase(refreshedJob);

      if (dzenStatus !== "PUBLISHED" || collectionStatus !== "COMPLETE") {
        log(
          config,
          `Фаза 4/4 НЕ запускается: gate не выполнен ` +
          `(dzenAutomation=${dzenStatus}; dzenCollections=${collectionStatus}).`
        );
      } else if (["COMPLETE", "SKIPPED_EXISTING"].includes(avStatus)) {
        log(
          config,
          `Фаза 4/4: dzenArticleVideo.status=${avStatus}; terminal success/skip, браузер НЕ открываю.`
        );
      } else if (avStatus === "ERROR") {
        articleVideoError = new Error(
          `dzenArticleVideo.status=ERROR; автоматический retry запрещён ` +
          `(phase=${avPhase}). Требуется явный incident recovery.`
        );
        fatalLog(config, `Фаза 4/4 заблокирована: ${articleVideoError.message}`, articleVideoError);
      } else {
        log(
          config,
          `Фаза 4/4: запускаю article-video за ${job.date}; status=${avStatus}; phase=${avPhase}.`
        );
        try {
          await runNodeScript("dzen-article-video.js", ["--apply", `--date=${job.date}`]);
          const after = loadJson(config.stateFile, { jobs: {} });
          const afterJob = collections.findJobForDate(after, job.date);
          log(
            config,
            `Фаза 4/4 завершена: dzenArticleVideo.status=${articleVideoStatus(afterJob)}; ` +
            `phase=${articleVideoPhase(afterJob)}.`
          );
        } catch (error) {
          articleVideoError = error;
          fatalLog(config, `Фаза 4/4 завершилась ошибкой: ${error.message}`, error);
        }
      }
    }

    if (phasesError || collectionsError || articleVideoError) {
      const parts = [];
      if (phasesError) parts.push(`фазы 1-2: ${phasesError.message}`);
      if (collectionsError) parts.push(`фаза 3: ${collectionsError.message}`);
      if (articleVideoError) parts.push(`фаза 4: ${articleVideoError.message}`);
      throw new Error(`Полный scheduled flow завершён с ошибкой (${parts.join("; ")}).`);
    }

    log(config, "=== END full scheduled flow SUCCESS ===");
  } catch (error) {
    if (error !== phasesError && error !== collectionsError && error !== articleVideoError) {
      fatalLog(config, error.message, error);
    }
    process.exitCode = process.exitCode || 1;
  } finally {
    releaseFullWorkerLock(lockHandle);
  }
}

module.exports = {
  FULL_WORKER_LOCK_PATH,
  acquireFullWorkerLock,
  articleVideoPhase,
  articleVideoStatus,
  main,
  releaseFullWorkerLock,
  runNodeScript,
  selectCollectionsJob,
};

if (require.main === module) main();
