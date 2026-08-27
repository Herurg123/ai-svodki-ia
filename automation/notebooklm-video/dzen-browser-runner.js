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

function parseArgs(argv) {
  const args = [...argv];
  let mode = "publish";
  if (args[0] === "--dry-run") {
    mode = "dry-run";
    args.shift();
  }
  return { mode, childArgs: args };
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

async function main(argv = process.argv.slice(2)) {
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }

  const config = loadJson(CONFIG_PATH);
  const { mode, childArgs } = parseArgs(argv);
  const target = mode === "dry-run" ? "dzen-publish.js" : "dzen-publish-live.js";
  const targetArgs = mode === "dry-run" ? ["--dry-run", ...childArgs] : childArgs;

  log(config, `запускаю ${target} через browser bootstrap рабочего worker.js.`);
  const session = await browserSession.launchRobotBrowser(config, {
    log: (message) => log(config, message),
  });

  try {
    await runNodeScript(target, targetArgs);
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

module.exports = { main, parseArgs };
