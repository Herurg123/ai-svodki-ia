"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { chromium } = require("playwright");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function endpointFor(config) {
  return `http://${config.browserDebugHost}:${config.browserDebugPort}`;
}

async function cdpIsAvailable(config) {
  try {
    const response = await fetch(`${endpointFor(config)}/json/version`, {
      signal: AbortSignal.timeout(1500),
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForCdp(config) {
  const deadline = Date.now() + (config.browserStartupTimeoutMs || 45_000);
  while (Date.now() < deadline) {
    if (await cdpIsAvailable(config)) return;
    await sleep(750);
  }
  throw new Error("Яндекс.Браузер не открыл CDP-порт за отведённое время.");
}

function encodePowerShellCommand(command) {
  return Buffer.from(command, "utf16le").toString("base64");
}

function quotePowerShellLiteral(value) {
  return `'${String(value).replace(/'/g, "''")}'`;
}

function quoteWindowsCommandLineArgument(value) {
  const text = String(value);
  if (!/[\s\"]/.test(text)) return text;

  let result = '"';
  let backslashes = 0;
  for (const char of text) {
    if (char === "\\") {
      backslashes += 1;
      continue;
    }
    if (char === '"') {
      result += "\\".repeat(backslashes * 2 + 1) + '"';
      backslashes = 0;
      continue;
    }
    result += "\\".repeat(backslashes) + char;
    backslashes = 0;
  }
  result += "\\".repeat(backslashes * 2) + '"';
  return result;
}

async function runPowerShellCommand(command, timeoutMs = 20_000) {
  if (process.platform !== "win32") {
    return { ok: false, skipped: true, error: "Windows API недоступен." };
  }

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
    child.once("error", (error) => finish({ ok: false, error: error.message, stdout, stderr }));
    child.once("close", (code) => finish({
      ok: code === 0,
      code,
      stdout: stdout.trim(),
      stderr: stderr.trim(),
      error: code === 0 ? null : stderr.trim() || `PowerShell завершился с кодом ${code}`,
    }));

    timer = setTimeout(() => {
      try { child.kill(); } catch {}
      finish({
        ok: false,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        error: `PowerShell не завершился за ${timeoutMs} мс.`,
      });
    }, timeoutMs);
  });
}

async function launchWindowsProcessMinimized(executable, args) {
  const argumentLine = args.map(quoteWindowsCommandLineArgument).join(" ");
  const command = [
    "$ErrorActionPreference = 'Stop'",
    `$exe = ${quotePowerShellLiteral(executable)}`,
    `$argumentLine = ${quotePowerShellLiteral(argumentLine)}`,
    "Start-Process -FilePath $exe -ArgumentList $argumentLine -WindowStyle Minimized | Out-Null",
    "Write-Output 'STARTED'",
  ].join("\r\n");
  return runPowerShellCommand(command, 15_000);
}

async function launchRobotBrowser(config, options = {}) {
  const log = typeof options.log === "function" ? options.log : () => {};

  if (!config.browserExecutable || !fs.existsSync(config.browserExecutable)) {
    throw new Error(`Яндекс.Браузер не найден: ${config.browserExecutable || "путь не задан"}`);
  }
  if (!config.browserProfile) {
    throw new Error("В config.json не задан browserProfile.");
  }

  if (await cdpIsAvailable(config)) {
    throw new Error(
      `Порт ${config.browserDebugPort} уже занят. Закройте роботизированный Яндекс.Браузер и повторите запуск.`
    );
  }

  const args = [
    `--user-data-dir=${config.browserProfile}`,
    `--remote-debugging-address=${config.browserDebugHost}`,
    `--remote-debugging-port=${config.browserDebugPort}`,
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-session-crashed-bubble",
    "--disable-background-mode",
    "--disable-backgrounding-occluded-windows",
    "--disable-renderer-backgrounding",
    "--disable-background-timer-throttling",
    "about:blank",
  ];

  let launchedMinimized = false;
  if (process.platform === "win32" && config.minimizeBrowserWindow !== false) {
    const result = await launchWindowsProcessMinimized(config.browserExecutable, args);
    launchedMinimized = result.ok;
    if (!result.ok) {
      log(`Не удалось запустить Яндекс.Браузер сразу свёрнутым: ${result.error || "неизвестная ошибка"}. Используется обычный запуск.`);
    }
  }

  let browserProcess = null;
  if (!launchedMinimized) {
    browserProcess = spawn(config.browserExecutable, args, {
      detached: true,
      stdio: "ignore",
      windowsHide: false,
    });
    browserProcess.unref();
  }

  await waitForCdp(config);
  const endpoint = endpointFor(config);
  const browser = await chromium.connectOverCDP(endpoint);
  const context = browser.contexts()[0];
  if (!context) {
    throw new Error("Не найден основной контекст Яндекс.Браузера.");
  }

  const pages = context.pages().filter((page) => !page.isClosed());
  let primaryPage = pages[0] || null;
  if (!primaryPage) primaryPage = await context.newPage();
  for (const page of pages.slice(1)) {
    try { await page.close(); } catch {}
  }

  log(`Роботизированный Яндекс.Браузер готов, CDP=${endpoint}.`);
  return { browser, context, primaryPage, endpoint, browserProcess };
}

async function closeRobotBrowser(session, config) {
  if (!session || !session.browser) return;
  try {
    const cdp = await session.browser.newBrowserCDPSession();
    await cdp.send("Browser.close");
  } catch {
    try { await session.browser.close(); } catch {}
  }

  if (config && config.closeBrowserAfterRun !== false) {
    const deadline = Date.now() + 10_000;
    while (Date.now() < deadline && (await cdpIsAvailable(config))) {
      await sleep(500);
    }
  }
}

module.exports = {
  cdpIsAvailable,
  closeRobotBrowser,
  endpointFor,
  launchRobotBrowser,
  waitForCdp,
};
