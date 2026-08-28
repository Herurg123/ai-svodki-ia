"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const browserSession = require("./browser-session");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const OPERATOR_WINDOW_MS = 10 * 60 * 1000;

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
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date());
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
      finish(new Error(`${scriptName} не завершился за операторское окно ${timeoutMs} мс.`));
    }, Math.max(1_000, timeoutMs));
  });
}

async function main(argv = process.argv.slice(2)) {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }

  const config = loadJson(CONFIG_PATH);
  const { mode, childArgs } = parseArgs(argv);
  const target = mode === "dry-run" ? "dzen-publish.js" : "dzen-publish-direct.js";
  const targetArgs = mode === "dry-run" ? ["--dry-run", ...childArgs] : childArgs;

  log(config, `запускаю ${target} через browser bootstrap рабочего worker.js.`);
  if (mode === "publish") {
    log(config, "live publish выполняется одним child-проходом без автоматического повторного запуска; inter-run resume отключён.");
  } else {
    log(config, "diagnostic dry-run выполняется одним child-проходом без recovery/retry loop.");
  }

  const session = await browserSession.launchRobotBrowser(config, {
    log: (message) => log(config, message),
  });

  try {
    await runNodeScript(target, targetArgs, OPERATOR_WINDOW_MS);
  } catch (error) {
    warn(
      config,
      `${target} завершился ошибкой: ${error.message}. Новый child, reopen draft и автоматический retry не выполняются.`
    );
    throw error;
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
  OPERATOR_WINDOW_MS,
  main,
  parseArgs,
  runNodeScript,
};
