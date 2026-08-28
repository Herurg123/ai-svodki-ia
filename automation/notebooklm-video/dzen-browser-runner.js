"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const browserSession = require("./browser-session");
const { classifyBlockingError } = require("./dzen-error-log");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const FALLBACK_ERROR_LOG = path.join(ROOT, "dzen-bootstrap-errors.log");
const OPERATOR_WINDOW_MS = 10 * 60 * 1000;
const CHILD_OUTPUT_TAIL_LIMIT = 16_000;

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath) {
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
  const line = `[${formatTime(config && config.timeZone)}] DZEN: ${message}`;
  console.log(line);
  appendLine(config && config.regularLog, line);
}

function warn(config, message) {
  const line = `[${formatTime(config && config.timeZone)}] !!! DZEN: ${message}`;
  console.warn(line);
  appendLine((config && config.regularLog) || FALLBACK_ERROR_LOG, line);
}

function fatalLog(config, message, error = null) {
  const suffix = error && error.stack ? `\r\n${error.stack}` : "";
  const line = `[${formatTime(config && config.timeZone)}] !!! DZEN: ${message}${suffix}`;
  console.error(line);

  const regularTarget = (config && config.regularLog) || FALLBACK_ERROR_LOG;
  appendLine(regularTarget, line);

  const errorTarget = config && config.errorLog;
  if (errorTarget && errorTarget !== regularTarget) {
    appendLine(errorTarget, line);
  }
}

function parseArgs(argv) {
  const args = [...argv];
  let mode = "publish";
  if (args[0] === "--dry-run") {
    mode = "dry-run";
    args.shift();
  }
  return { mode, childArgs: args };
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
    let childOutput = "";

    const rememberOutput = (chunk) => {
      childOutput = `${childOutput}${chunk.toString("utf8")}`.slice(-CHILD_OUTPUT_TAIL_LIMIT);
    };

    const child = spawn(process.execPath, [path.join(ROOT, scriptName), ...args], {
      cwd: ROOT,
      stdio: ["inherit", "pipe", "pipe"],
      windowsHide: false,
    });

    child.stdout.on("data", (chunk) => {
      rememberOutput(chunk);
      process.stdout.write(chunk);
    });
    child.stderr.on("data", (chunk) => {
      rememberOutput(chunk);
      process.stderr.write(chunk);
    });

    let timer = null;
    const finish = (error = null) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (error) {
        error.childOutput = childOutput;
        reject(error);
      } else {
        resolve();
      }
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
      finish(new Error(`${scriptName} не завершился за операторское окно ${timeoutMs} мс.`));
    }, Math.max(1_000, timeoutMs));
  });
}

async function main(argv = process.argv.slice(2)) {
  let config = null;
  let session = null;
  let primaryError = null;

  try {
    if (!fs.existsSync(CONFIG_PATH)) {
      throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
    }

    config = loadJson(CONFIG_PATH);
    const { mode, childArgs } = parseArgs(argv);
    const target = mode === "dry-run" ? "dzen-publish.js" : "dzen-publish-direct.js";
    const targetArgs = mode === "dry-run" ? ["--dry-run", ...childArgs] : childArgs;

    log(config, `запускаю ${target} через browser bootstrap рабочего worker.js.`);
    if (mode === "publish") {
      log(config, "live publish выполняется одним child-проходом без автоматического повторного запуска; inter-run resume отключён.");
    } else {
      log(config, "diagnostic dry-run выполняется одним child-проходом без recovery/retry loop.");
    }

    session = await browserSession.launchRobotBrowser(config, {
      log: (message) => log(config, message),
    });

    await runNodeScript(target, targetArgs, OPERATOR_WINDOW_MS);
  } catch (error) {
    primaryError = error;
    fatalLog(config, classifyBlockingError(error), error);
    warn(
      config,
      "Задача остановлена. Новый child, reopen draft и автоматический retry не выполняются."
    );
    throw error;
  } finally {
    if (session) {
      try {
        await browserSession.closeRobotBrowser(session, config);
      } catch (closeError) {
        fatalLog(
          config,
          `ОШИБКА БРАУЗЕРА: не удалось штатно закрыть роботизированный Яндекс.Браузер: ${closeError.message}`,
          closeError
        );
        if (!primaryError) throw closeError;
      }
    }
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
  CHILD_OUTPUT_TAIL_LIMIT,
  FALLBACK_ERROR_LOG,
  OPERATOR_WINDOW_MS,
  main,
  parseArgs,
  runNodeScript,
};
