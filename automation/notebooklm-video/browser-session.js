"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function buildCdpEndpoint(config) {
  return `http://${config.browserDebugHost}:${config.browserDebugPort}`;
}

function buildBrowserArgs(config) {
  return [
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
}

function clearSessionRestoreFiles(config) {
  if (!config.clearSessionRestore) return;

  const defaultDir = path.join(config.browserProfile, "Default");
  const sessionsDir = path.join(defaultDir, "Sessions");
  fs.rmSync(sessionsDir, { recursive: true, force: true });

  for (const fileName of [
    "Current Session",
    "Current Tabs",
    "Last Session",
    "Last Tabs",
  ]) {
    fs.rmSync(path.join(defaultDir, fileName), { force: true });
  }
}

async function cdpIsAvailable(config) {
  try {
    const response = await fetch(`${buildCdpEndpoint(config)}/json/version`, {
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
  if (!/[\s"]/.test(text)) return text;

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
      {
        windowsHide: true,
        stdio: ["ignore", "pipe", "pipe"],
      }
    );

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });

    child.once("error", (error) => {
      finish({ ok: false, error: error.message, stdout, stderr });
    });

    child.once("close", (code) => {
      finish({
        ok: code === 0,
        code,
        stdout: stdout.trim(),
        stderr: stderr.trim(),
        error:
          code === 0
            ? null
            : stderr.trim() || `PowerShell завершился с кодом ${code}`,
      });
    });

    timer = setTimeout(() => {
      try {
        child.kill();
      } catch {}
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

async function minimizeRobotBrowserWindows(
  config,
  requestedWaitMs = null,
  holdForFullDuration = false
) {
  if (process.platform !== "win32" || config.minimizeBrowserWindow === false) {
    return { ok: false, skipped: true };
  }

  const executableName = path.basename(config.browserExecutable);
  const waitMs =
    requestedWaitMs === null
      ? Math.max(
          5_000,
          Math.min(config.browserStartupTimeoutMs || 45_000, 30_000)
        )
      : Math.max(
          1_500,
          Math.min(Number(requestedWaitMs) || 8_000, 30_000)
        );

  const command = `
$ErrorActionPreference = 'Stop'
$profile = ${quotePowerShellLiteral(config.browserProfile)}
$exeName = ${quotePowerShellLiteral(executableName)}
$debugPort = ${Number(config.browserDebugPort)}
$holdForFullDuration = ${holdForFullDuration ? "$true" : "$false"}
$deadline = [DateTime]::UtcNow.AddMilliseconds(${waitMs})

Add-Type -TypeDefinition @'
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Threading;

public static class NotebookLMBotWindowControl
{
    private delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern bool EnumWindows(EnumWindowsProc callback, IntPtr lParam);

    [DllImport("user32.dll")]
    private static extern uint GetWindowThreadProcessId(IntPtr hWnd, out uint processId);

    [DllImport("user32.dll")]
    private static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool IsIconic(IntPtr hWnd);

    [DllImport("user32.dll")]
    private static extern bool ShowWindowAsync(IntPtr hWnd, int command);

    [DllImport("user32.dll")]
    private static extern bool PostMessage(IntPtr hWnd, uint msg, IntPtr wParam, IntPtr lParam);

    public static int MinimizeAndCountIconic(int[] processIds)
    {
        var targets = new HashSet<int>(processIds);
        var windows = new List<IntPtr>();

        EnumWindows((hWnd, lParam) =>
        {
            uint processId;
            GetWindowThreadProcessId(hWnd, out processId);

            if (IsWindowVisible(hWnd) && targets.Contains((int)processId))
            {
                windows.Add(hWnd);
            }

            return true;
        }, IntPtr.Zero);

        foreach (var hWnd in windows)
        {
            ShowWindowAsync(hWnd, 7);
            PostMessage(hWnd, 0x0112, new IntPtr(0xF020), IntPtr.Zero);
        }

        Thread.Sleep(150);

        var iconic = 0;
        foreach (var hWnd in windows)
        {
            if (IsIconic(hWnd))
            {
                iconic++;
            }
        }

        return iconic;
    }
}
'@

function Get-RobotBrowserProcessIds {
    $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
    $seeds = New-Object 'System.Collections.Generic.HashSet[int]'

    try {
        @(Get-NetTCPConnection -State Listen -LocalPort $debugPort -ErrorAction Stop |
            ForEach-Object { [int]$_.OwningProcess }) |
            ForEach-Object { [void]$seeds.Add($_) }
    } catch {
        $pattern = ':+' + [regex]::Escape([string]$debugPort) + '\\s+.*LISTENING\\s+(\\d+)\\s*$'
        @(netstat -ano -p tcp 2>$null) | ForEach-Object {
            if ($_ -match $pattern) {
                [void]$seeds.Add([int]$matches[1])
            }
        }
    }

    foreach ($proc in $all) {
        if ($proc.Name -ne $exeName -or -not $proc.CommandLine) {
            continue
        }

        if (
            $proc.CommandLine.IndexOf($profile, [StringComparison]::OrdinalIgnoreCase) -ge 0 -or
            $proc.CommandLine -match ('--remote-debugging-port[= ]' + [regex]::Escape([string]$debugPort) + '(?:\\s|$)')
        ) {
            [void]$seeds.Add([int]$proc.ProcessId)
        }
    }

    if ($seeds.Count -eq 0) {
        return @()
    }

    $targets = New-Object 'System.Collections.Generic.HashSet[int]'
    foreach ($pidValue in $seeds) {
        [void]$targets.Add($pidValue)
    }

    $changed = $true
    while ($changed) {
        $changed = $false
        foreach ($proc in $all) {
            if ($targets.Contains([int]$proc.ParentProcessId) -and -not $targets.Contains([int]$proc.ProcessId)) {
                [void]$targets.Add([int]$proc.ProcessId)
                $changed = $true
            }
        }
    }

    return @($targets)
}

$bestIconicCount = 0
$stablePasses = 0

while ([DateTime]::UtcNow -lt $deadline) {
    $processIds = @(Get-RobotBrowserProcessIds)

    if ($processIds.Count -gt 0) {
        $iconicCount = [NotebookLMBotWindowControl]::MinimizeAndCountIconic($processIds)

        if ($iconicCount -gt 0) {
            $bestIconicCount = [Math]::Max($bestIconicCount, $iconicCount)
            $stablePasses += 1
        } else {
            $stablePasses = 0
        }

        if (-not $holdForFullDuration -and $stablePasses -ge 5) {
            Write-Output "MINIMIZED:$bestIconicCount"
            exit 0
        }
    }

    Start-Sleep -Milliseconds 250
}

if ($bestIconicCount -gt 0) {
    Write-Output "MINIMIZED:$bestIconicCount"
    exit 0
}

Write-Error "Не удалось подтвердить свёрнутое состояние окна роботизированного Яндекс.Браузера."
exit 2
`;

  return runPowerShellCommand(command, waitMs + 5_000);
}

function createBrowserSession(config, options = {}) {
  const allowExisting = options.allowExisting === true;
  const closeAttachedBrowser = options.closeAttachedBrowser === true;
  const log = typeof options.log === "function" ? options.log : () => {};
  const onActivePage =
    typeof options.onActivePage === "function" ? options.onActivePage : () => {};

  let browser = null;
  let browserProcess = null;
  let context = null;
  let activePage = null;
  let ownsBrowser = false;
  let opened = false;

  function setActivePage(page) {
    activePage = page || null;
    onActivePage(activePage);
    return activePage;
  }

  async function connect() {
    const { chromium } = require("playwright");
    return chromium.connectOverCDP(buildCdpEndpoint(config));
  }

  async function prepareContext({ attachedExisting }) {
    context = browser.contexts()[0];
    if (!context) {
      throw new Error("Не найден основной контекст Яндекс.Браузера.");
    }

    const pages = context.pages().filter((page) => !page.isClosed());
    let primaryPage = pages[0] || null;
    if (!primaryPage) {
      primaryPage = await context.newPage();
    }
    setActivePage(primaryPage);

    if (!attachedExisting) {
      for (const page of pages.slice(1)) {
        try {
          await page.close();
        } catch {}
      }
    }
  }

  async function open() {
    if (opened && browser && context) {
      return {
        browser,
        context,
        endpoint: buildCdpEndpoint(config),
        attachedExisting: !ownsBrowser,
      };
    }

    const endpoint = buildCdpEndpoint(config);
    const alreadyAvailable = await cdpIsAvailable(config);

    if (alreadyAvailable) {
      if (!allowExisting) {
        throw new Error(
          `Порт ${config.browserDebugPort} уже занят. Закройте роботизированный Яндекс.Браузер и повторите запуск.`
        );
      }

      browser = await connect();
      ownsBrowser = false;
      opened = true;
      await prepareContext({ attachedExisting: true });
      log(`Подключение к уже запущенному роботизированному Яндекс.Браузеру: ${endpoint}.`);
      return { browser, context, endpoint, attachedExisting: true };
    }

    if (!config.browserExecutable || !fs.existsSync(config.browserExecutable)) {
      throw new Error(`Яндекс.Браузер не найден: ${config.browserExecutable || "путь не задан"}`);
    }

    log(
      config.minimizeBrowserWindow !== false
        ? "Режим окна Яндекс.Браузера: сворачивать."
        : "Режим окна Яндекс.Браузера: оставлять видимым."
    );

    clearSessionRestoreFiles(config);
    const args = buildBrowserArgs(config);
    let launchedMinimized = false;

    if (process.platform === "win32" && config.minimizeBrowserWindow !== false) {
      const launchResult = await launchWindowsProcessMinimized(
        config.browserExecutable,
        args
      );
      launchedMinimized = launchResult.ok;

      if (!launchedMinimized) {
        log(
          `Не удалось запустить Яндекс.Браузер сразу свёрнутым: ${
            launchResult.error || "неизвестная ошибка"
          }. Используется обычный запуск с последующим сворачиванием.`
        );
      }
    }

    if (!launchedMinimized) {
      browserProcess = spawn(config.browserExecutable, args, {
        detached: true,
        stdio: "ignore",
        windowsHide: false,
      });
      browserProcess.unref();
    }

    const earlyMinimizePromise =
      process.platform === "win32" && config.minimizeBrowserWindow !== false
        ? minimizeRobotBrowserWindows(config)
        : Promise.resolve({ ok: false, skipped: true });

    await waitForCdp(config);
    browser = await connect();
    ownsBrowser = true;
    opened = true;
    await prepareContext({ attachedExisting: false });

    await earlyMinimizePromise;
    const finalMinimizeResult =
      process.platform === "win32" && config.minimizeBrowserWindow !== false
        ? await minimizeRobotBrowserWindows(config, 10_000)
        : { ok: false, skipped: true };

    if (finalMinimizeResult.ok) {
      log(
        "Окно роботизированного Яндекс.Браузера свёрнуто и состояние подтверждено после создания рабочей вкладки."
      );
    } else if (!finalMinimizeResult.skipped) {
      log(
        `Не удалось подтвердить сворачивание окна Яндекс.Браузера: ${
          finalMinimizeResult.error || "неизвестная ошибка"
        }. Работа продолжается в обычном видимом режиме.`
      );
    }

    return { browser, context, endpoint, attachedExisting: false };
  }

  async function getPage() {
    if (!opened || !context) {
      await open();
    }

    if (activePage && !activePage.isClosed()) {
      return activePage;
    }

    const existing = context.pages().find((page) => !page.isClosed());
    if (existing) {
      return setActivePage(existing);
    }

    const page = await context.newPage();
    setActivePage(page);

    if (process.platform === "win32" && config.minimizeBrowserWindow !== false) {
      const result = await minimizeRobotBrowserWindows(config, 8_000);
      if (!result.ok && !result.skipped) {
        log(
          `После создания новой вкладки не удалось подтвердить сворачивание окна: ${
            result.error || "неизвестная ошибка"
          }.`
        );
      }
    }

    return page;
  }

  async function newPage() {
    if (!opened || !context) {
      await open();
    }

    const page = await context.newPage();
    setActivePage(page);

    if (process.platform === "win32" && config.minimizeBrowserWindow !== false) {
      const result = await minimizeRobotBrowserWindows(config, 8_000);
      if (!result.ok && !result.skipped) {
        log(
          `После создания новой вкладки не удалось подтвердить сворачивание окна: ${
            result.error || "неизвестная ошибка"
          }.`
        );
      }
    }

    return page;
  }

  async function minimize(requestedWaitMs = null, holdForFullDuration = false) {
    return minimizeRobotBrowserWindows(
      config,
      requestedWaitMs,
      holdForFullDuration
    );
  }

  async function close() {
    if (!browser) {
      setActivePage(null);
      return;
    }

    const shouldCloseBrowser = ownsBrowser || closeAttachedBrowser;
    if (shouldCloseBrowser) {
      try {
        const session = await browser.newBrowserCDPSession();
        await session.send("Browser.close");
      } catch {
        try {
          await browser.close();
        } catch {}
      }

      if (config.closeBrowserAfterRun !== false) {
        const deadline = Date.now() + 10_000;
        while (Date.now() < deadline && (await cdpIsAvailable(config))) {
          await sleep(500);
        }
      }
    }

    browser = null;
    browserProcess = null;
    context = null;
    ownsBrowser = false;
    opened = false;
    setActivePage(null);
  }

  return {
    open,
    close,
    getPage,
    newPage,
    minimize,
    endpoint: buildCdpEndpoint(config),
    get browser() {
      return browser;
    },
    get context() {
      return context;
    },
    get ownsBrowser() {
      return ownsBrowser;
    },
  };
}

module.exports = {
  buildBrowserArgs,
  buildCdpEndpoint,
  cdpIsAvailable,
  createBrowserSession,
  waitForCdp,
};
