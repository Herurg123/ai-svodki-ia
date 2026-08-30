"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const browserSession = require("./browser-session");
const duplicateGuard = require("./dzen-duplicate-guard");
const { classifyBlockingError } = require("./dzen-error-log");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const FALLBACK_ERROR_LOG = path.join(ROOT, "dzen-bootstrap-errors.log");
const OPERATOR_WINDOW_MS = 10 * 60 * 1000;
const CHILD_OUTPUT_TAIL_LIMIT = 16_000;
const POST_CLICK_CHALLENGE_PROBE_MS = 4_000;
const POST_CLICK_CHALLENGE_WAIT_MS = 120_000;
const POST_CLICK_CHALLENGE_POLL_MS = 500;

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

function textLooksLikeManualAntiBotChallenge(value) {
  const text = String(value || "")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
    .replace(/[\u00A0\u202F]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .toLocaleLowerCase("ru-RU");
  return text.includes("подтвердите, что вы не робот") ||
    (text.includes("подтвердите") && text.includes("я не робот"));
}

async function findAntiBotChallengePage(browser) {
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.isClosed()) continue;
      const texts = [];
      for (const frame of page.frames()) {
        const body = await frame.locator("body").innerText({ timeout: 1000 }).catch(() => "");
        if (body) texts.push(body);
      }
      if (textLooksLikeManualAntiBotChallenge(texts.join("\n"))) return page;
    }
  }
  return null;
}

function encodePowerShellCommand(command) {
  return Buffer.from(command, "utf16le").toString("base64");
}

function quotePowerShellLiteral(value) {
  return `'${String(value || "").replace(/'/g, "''")}'`;
}

async function restoreRobotBrowserWindow(config) {
  if (process.platform !== "win32" || !config.browserExecutable) {
    return { ok: false, skipped: true };
  }

  const processName = path.parse(config.browserExecutable).name;
  const command = [
    "$ErrorActionPreference = 'Stop'",
    "Add-Type -TypeDefinition @'",
    "using System;",
    "using System.Runtime.InteropServices;",
    "public static class AiSvodkiWindowApi {",
    "  [DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);",
    "  [DllImport(\"user32.dll\")] public static extern bool SetForegroundWindow(IntPtr hWnd);",
    "}",
    "'@",
    `$name = ${quotePowerShellLiteral(processName)}`,
    "$windows = @(Get-Process -Name $name -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowHandle -ne 0 })",
    "foreach ($p in $windows) {",
    "  [AiSvodkiWindowApi]::ShowWindowAsync($p.MainWindowHandle, 9) | Out-Null",
    "  [AiSvodkiWindowApi]::SetForegroundWindow($p.MainWindowHandle) | Out-Null",
    "}",
    "Write-Output $windows.Count",
  ].join("\r\n");

  return new Promise((resolve) => {
    let settled = false;
    let stdout = "";
    let stderr = "";
    let timer = null;
    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };
    const child = spawn(
      "powershell.exe",
      [
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encodePowerShellCommand(command),
      ],
      { windowsHide: true, stdio: ["ignore", "pipe", "pipe"] }
    );
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });
    child.once("error", (error) => finish({ ok: false, error: error.message }));
    child.once("close", (code) => finish({
      ok: code === 0,
      code,
      stdout: stdout.trim(),
      error: code === 0 ? null : stderr.trim() || `PowerShell завершился с кодом ${code}`,
    }));
    timer = setTimeout(() => {
      try { child.kill(); } catch {}
      finish({ ok: false, error: "Не удалось восстановить окно браузера за 10 секунд." });
    }, 10_000);
  });
}

async function waitForOptionalPostClickChallenge() {
  if (!fs.existsSync(CONFIG_PATH)) return { seen: false, resolved: false, reason: "no-config" };
  const config = loadJson(CONFIG_PATH);
  const endpoint = `http://${config.browserDebugHost}:${config.browserDebugPort}`;
  let browser = null;

  try {
    const { chromium } = require("playwright");
    browser = await chromium.connectOverCDP(endpoint, { timeout: 3000 });
  } catch (error) {
    warn(
      config,
      `post-click антибот-проверку не удалось проверить через ${endpoint}: ${error.message}. ` +
        "Продолжаю штатную verification-only защиту без дополнительных кликов."
    );
    return { seen: false, resolved: false, reason: "cdp-unavailable" };
  }

  const probeDeadline = Date.now() + POST_CLICK_CHALLENGE_PROBE_MS;
  let challengePage = null;
  while (Date.now() < probeDeadline) {
    challengePage = await findAntiBotChallengePage(browser);
    if (challengePage) break;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  if (!challengePage) {
    log(
      config,
      `post-click антибот-проверка не обнаружена за ${POST_CLICK_CHALLENGE_PROBE_MS} мс.`
    );
    return { seen: false, resolved: true };
  }

  warn(
    config,
    "ПОСЛЕ PUBLISH ПОЯВИЛАСЬ АНТИБОТ-ПРОВЕРКА «Я НЕ РОБОТ». " +
      "Автоматизация НЕ нажимает checkbox и НЕ выполняет других кликов. " +
      `Ожидаю ручного подтверждения до ${POST_CLICK_CHALLENGE_WAIT_MS} мс.`
  );

  const restored = await restoreRobotBrowserWindow(config);
  if (restored.ok) {
    log(config, "Окно Яндекс.Браузера восстановлено для ручного подтверждения антибот-проверки.");
  } else if (!restored.skipped) {
    warn(config, `Не удалось восстановить окно Яндекс.Браузера: ${restored.error || "неизвестная ошибка"}.`);
  }
  await challengePage.bringToFront().catch(() => {});

  const deadline = Date.now() + POST_CLICK_CHALLENGE_WAIT_MS;
  while (Date.now() < deadline) {
    challengePage = await findAntiBotChallengePage(browser);
    if (!challengePage) {
      log(
        config,
        "Антибот-проверка исчезла. Автоматизация не взаимодействовала с ней; " +
          "продолжаю обычный post-click путь без дополнительных кликов."
      );
      await new Promise((resolve) => setTimeout(resolve, 2000));
      return { seen: true, resolved: true };
    }
    await new Promise((resolve) => setTimeout(resolve, POST_CLICK_CHALLENGE_POLL_MS));
  }

  throw new Error(
    `После publish click антибот-проверка «Я не робот» не исчезла за ` +
      `${POST_CLICK_CHALLENGE_WAIT_MS} мс. Publish click уже выполнен; ` +
      "повторный click запрещён, дальнейшие запуски должны остаться verification-only."
  );
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
    child.once("exit", async (code, signal) => {
      if (code === 0) {
        clearTimeout(timer);
        try {
          if (scriptName === "dzen-publish-direct.js") {
            await waitForOptionalPostClickChallenge();
          }
          finish();
        } catch (error) {
          finish(error);
        }
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

    log(config, `готовлю ${target} через browser bootstrap рабочего worker.js.`);
    if (mode === "publish") {
      log(
        config,
        "до live child выполняется pre-upload duplicate guard во вкладке «Видео»; " +
        "при совпадении заголовка upload не начинается."
      );
    } else {
      log(config, "diagnostic dry-run выполняется одним child-проходом без recovery/retry loop.");
    }

    session = await browserSession.launchRobotBrowser(config, {
      log: (message) => log(config, message),
    });

    if (mode === "publish") {
      const duplicate = await duplicateGuard.checkBeforeUpload(
        session.primaryPage,
        config,
        childArgs,
        (message) => log(config, message)
      );

      if (duplicate.existing) {
        log(
          config,
          `live child не запускается: Видео «${duplicate.titlePrefix}» уже существует.`
        );
        return;
      }

      log(
        config,
        "live publish выполняется одним child-проходом без автоматического повторного запуска; " +
        "inter-run resume отключён."
      );
    }

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
  POST_CLICK_CHALLENGE_PROBE_MS,
  POST_CLICK_CHALLENGE_WAIT_MS,
  main,
  parseArgs,
  runNodeScript,
  textLooksLikeManualAntiBotChallenge,
};
