"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");
const { spawn } = require("child_process");
const { XMLParser } = require("fast-xml-parser");
const { createBrowserSession } = require("./browser-session.js");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");

let stage = "START";
let robotBrowserSession = null;
let activePage = null;
let lockHandle = null;

function stripBom(value) {
  return value.replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) {
    return fallback;
  }
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}

function applyConfigDefaultsAndValidate(config) {
  // Параметр появился после того, как Яндекс.Браузер начал самовольно
  // перехватывать фокус. Если старый config.json ещё не содержит настройки,
  // сохраняем прежнее безопасное поведение: окно сворачивается.
  if (config.minimizeBrowserWindow === undefined) {
    config.minimizeBrowserWindow = true;
  }

  if (typeof config.minimizeBrowserWindow !== "boolean") {
    throw new Error(
      'Параметр config.json "minimizeBrowserWindow" должен быть true или false без кавычек.'
    );
  }

  if (config.logRotation === undefined) {
    config.logRotation = {};
  }

  if (
    !config.logRotation ||
    typeof config.logRotation !== "object" ||
    Array.isArray(config.logRotation)
  ) {
    throw new Error(
      'Параметр config.json "logRotation" должен быть объектом с настройками ротации.'
    );
  }

  const rotationDefaults = {
    enabled: true,
    archiveDir: path.join(path.dirname(config.regularLog), "logs"),
    workerRetentionDays: 7,
    errorRetentionDays: 30,
    maxFileSizeMb: 25,
  };

  for (const [key, value] of Object.entries(rotationDefaults)) {
    if (config.logRotation[key] === undefined) {
      config.logRotation[key] = value;
    }
  }

  if (typeof config.logRotation.enabled !== "boolean") {
    throw new Error(
      'Параметр config.json "logRotation.enabled" должен быть true или false без кавычек.'
    );
  }

  if (
    typeof config.logRotation.archiveDir !== "string" ||
    !config.logRotation.archiveDir.trim()
  ) {
    throw new Error(
      'Параметр config.json "logRotation.archiveDir" должен содержать путь к каталогу архивных логов.'
    );
  }

  for (const key of ["workerRetentionDays", "errorRetentionDays"]) {
    if (
      !Number.isInteger(config.logRotation[key]) ||
      config.logRotation[key] < 1
    ) {
      throw new Error(
        `Параметр config.json "logRotation.${key}" должен быть целым числом не меньше 1.`
      );
    }
  }

  if (
    typeof config.logRotation.maxFileSizeMb !== "number" ||
    !Number.isFinite(config.logRotation.maxFileSizeMb) ||
    config.logRotation.maxFileSizeMb <= 0
  ) {
    throw new Error(
      'Параметр config.json "logRotation.maxFileSizeMb" должен быть числом больше 0.'
    );
  }

  if (config.ftpUpload === undefined) {
    config.ftpUpload = {};
  }

  if (
    !config.ftpUpload ||
    typeof config.ftpUpload !== "object" ||
    Array.isArray(config.ftpUpload)
  ) {
    throw new Error(
      'Параметр config.json "ftpUpload" должен быть объектом с настройками FTP-доставки.'
    );
  }

  const ftpDefaults = {
    enabled: false,
    accessFile: path.join(config.workDir || ROOT, "ftp-access.json"),
    remoteDir: "video",
    remoteFilenamePrefix: "ai-svodka",
    publicBaseUrl: "",
    previewEnabled: true,
    connectTimeoutMs: 30_000,
  };

  for (const [key, value] of Object.entries(ftpDefaults)) {
    if (config.ftpUpload[key] === undefined) {
      config.ftpUpload[key] = value;
    }
  }

  if (typeof config.ftpUpload.enabled !== "boolean") {
    throw new Error(
      'Параметр config.json "ftpUpload.enabled" должен быть true или false без кавычек.'
    );
  }

  if (
    typeof config.ftpUpload.accessFile !== "string" ||
    !config.ftpUpload.accessFile.trim()
  ) {
    throw new Error(
      'Параметр config.json "ftpUpload.accessFile" должен содержать путь к файлу доступа.'
    );
  }

  if (config.ftpUpload.remoteDir !== "video") {
    throw new Error(
      'Параметр config.json "ftpUpload.remoteDir" в этой версии worker.js должен быть строго "video".'
    );
  }

  if (
    typeof config.ftpUpload.remoteFilenamePrefix !== "string" ||
    !/^[A-Za-z0-9._-]+$/.test(config.ftpUpload.remoteFilenamePrefix)
  ) {
    throw new Error(
      'Параметр config.json "ftpUpload.remoteFilenamePrefix" может содержать только латинские буквы, цифры, точку, дефис и подчёркивание.'
    );
  }

  if (typeof config.ftpUpload.publicBaseUrl !== "string") {
    throw new Error(
      'Параметр config.json "ftpUpload.publicBaseUrl" должен быть строкой.'
    );
  }

  if (config.ftpUpload.publicBaseUrl.trim()) {
    let parsedPublicBaseUrl;
    try {
      parsedPublicBaseUrl = new URL(config.ftpUpload.publicBaseUrl);
    } catch {
      throw new Error(
        'Параметр config.json "ftpUpload.publicBaseUrl" должен быть корректным http/https URL или пустой строкой.'
      );
    }

    if (!["http:", "https:"].includes(parsedPublicBaseUrl.protocol)) {
      throw new Error(
        'Параметр config.json "ftpUpload.publicBaseUrl" должен использовать http или https.'
      );
    }
  }

  if (typeof config.ftpUpload.previewEnabled !== "boolean") {
    throw new Error(
      'Параметр config.json "ftpUpload.previewEnabled" должен быть true или false без кавычек.'
    );
  }

  if (
    !Number.isInteger(config.ftpUpload.connectTimeoutMs) ||
    config.ftpUpload.connectTimeoutMs < 1_000
  ) {
    throw new Error(
      'Параметр config.json "ftpUpload.connectTimeoutMs" должен быть целым числом не меньше 1000.'
    );
  }

  return config;
}

function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
}

function ensureDirectories(config) {
  const dirs = [
    config.workDir,
    config.downloadDir,
    config.screenshotsDir,
    config.tracesDir,
    config.tempDir,
    path.dirname(config.regularLog),
    path.dirname(config.errorLog),
    path.dirname(config.stateFile),
    path.dirname(config.descriptionFile),
    path.dirname(config.successRegistryFile),
  ];

  if (config.logRotation?.enabled !== false && config.logRotation?.archiveDir) {
    dirs.push(config.logRotation.archiveDir);
  }

  for (const dir of dirs) {
    fs.mkdirSync(dir, { recursive: true });
  }
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
    if (["year", "month", "day"].includes(part.type)) {
      values[part.type] = part.value;
    }
  }

  return `${values.year}-${values.month}-${values.day}`;
}

function getLogRotationConfig(config) {
  const rotation = config.logRotation || {};
  return {
    enabled: rotation.enabled !== false,
    archiveDir:
      rotation.archiveDir ||
      path.join(path.dirname(config.regularLog || ROOT), "logs"),
    workerRetentionDays: Number.isInteger(rotation.workerRetentionDays)
      ? rotation.workerRetentionDays
      : 7,
    errorRetentionDays: Number.isInteger(rotation.errorRetentionDays)
      ? rotation.errorRetentionDays
      : 30,
    maxFileSizeMb:
      typeof rotation.maxFileSizeMb === "number" &&
      Number.isFinite(rotation.maxFileSizeMb) &&
      rotation.maxFileSizeMb > 0
        ? rotation.maxFileSizeMb
        : 25,
  };
}

function nextArchiveLogPath(config, kind, sourceDate) {
  const rotation = getLogRotationConfig(config);
  const prefix = kind === "error" ? "error" : "worker";
  const dateKey = formatDateKey(sourceDate, config.timeZone);
  let sequence = 1;

  while (true) {
    const suffix = sequence === 1 ? "" : `-${sequence}`;
    const candidate = path.join(
      rotation.archiveDir,
      `${prefix}-${dateKey}${suffix}.log`
    );

    if (!fs.existsSync(candidate)) {
      return candidate;
    }

    sequence += 1;
  }
}

function rotateLogIfNeeded(config, logPath, kind) {
  const rotation = getLogRotationConfig(config);
  if (!rotation.enabled || !logPath || !fs.existsSync(logPath)) {
    return null;
  }

  const stats = fs.statSync(logPath);
  if (!stats.isFile() || stats.size === 0) {
    return null;
  }

  const now = new Date();
  const crossedDay =
    formatDateKey(stats.mtime, config.timeZone) !==
    formatDateKey(now, config.timeZone);
  const exceededSize =
    stats.size >= rotation.maxFileSizeMb * 1024 * 1024;

  if (!crossedDay && !exceededSize) {
    return null;
  }

  fs.mkdirSync(rotation.archiveDir, { recursive: true });
  const archivePath = nextArchiveLogPath(
    config,
    kind,
    crossedDay ? stats.mtime : now
  );
  fs.renameSync(logPath, archivePath);

  return {
    archivePath,
    sizeBytes: stats.size,
    reason: crossedDay ? "смена даты" : "превышение размера",
  };
}

function archiveDateToUtc(dateKey) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(dateKey);
  if (!match) {
    return null;
  }

  return Date.UTC(
    Number(match[1]),
    Number(match[2]) - 1,
    Number(match[3])
  );
}

function cleanupOldLogArchives(config) {
  const rotation = getLogRotationConfig(config);
  const result = { deletedFiles: 0, deletedBytes: 0 };

  if (!rotation.enabled || !fs.existsSync(rotation.archiveDir)) {
    return result;
  }

  const todayKey = formatDateKey(new Date(), config.timeZone);
  const todayUtc = archiveDateToUtc(todayKey);
  const archivePattern =
    /^(worker|error)-(\d{4}-\d{2}-\d{2})(?:-\d+)?\.log$/i;

  for (const entry of fs.readdirSync(rotation.archiveDir, {
    withFileTypes: true,
  })) {
    if (!entry.isFile()) {
      continue;
    }

    const match = archivePattern.exec(entry.name);
    if (!match) {
      continue;
    }

    const archiveUtc = archiveDateToUtc(match[2]);
    if (archiveUtc === null || archiveUtc > todayUtc) {
      continue;
    }

    const retentionDays =
      match[1].toLowerCase() === "error"
        ? rotation.errorRetentionDays
        : rotation.workerRetentionDays;
    const ageDays = Math.floor((todayUtc - archiveUtc) / 86400000);

    if (ageDays < retentionDays) {
      continue;
    }

    const filePath = path.join(rotation.archiveDir, entry.name);
    const sizeBytes = fs.statSync(filePath).size;
    fs.rmSync(filePath, { force: true });
    result.deletedFiles += 1;
    result.deletedBytes += sizeBytes;
  }

  return result;
}

function performLogMaintenance(config) {
  const rotation = getLogRotationConfig(config);
  const result = {
    enabled: rotation.enabled,
    rotated: [],
    deletedFiles: 0,
    deletedBytes: 0,
  };

  if (!rotation.enabled) {
    return result;
  }

  const regularRotation = rotateLogIfNeeded(
    config,
    config.regularLog,
    "worker"
  );
  if (regularRotation) {
    result.rotated.push(regularRotation);
  }

  const errorRotation = rotateLogIfNeeded(
    config,
    config.errorLog,
    "error"
  );
  if (errorRotation) {
    result.rotated.push(errorRotation);
  }

  const cleanup = cleanupOldLogArchives(config);
  result.deletedFiles = cleanup.deletedFiles;
  result.deletedBytes = cleanup.deletedBytes;
  return result;
}

function formatByteCount(bytes) {
  if (bytes < 1024) {
    return `${bytes} Б`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} КБ`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

function appendRegularLogLine(config, line) {
  const rotation = rotateLogIfNeeded(config, config.regularLog, "worker");

  if (rotation) {
    const rotationLine =
      `[${formatTime(config.timeZone)}] Ротация worker.log: ` +
      `${rotation.reason}; архив=${rotation.archivePath}; ` +
      `размер=${formatByteCount(rotation.sizeBytes)}.`;
    console.log(rotationLine);
    fs.appendFileSync(config.regularLog, `${rotationLine}\r\n`, "utf8");
  }

  fs.appendFileSync(config.regularLog, `${line}\r\n`, "utf8");
}

function log(config, message) {
  const line = `[${formatTime(config.timeZone)}] ${message}`;
  console.log(line);
  appendRegularLogLine(config, line);
}

function safeFilePart(value) {
  return String(value)
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 120);
}

async function saveErrorScreenshot(config, label = "error") {
  if (!activePage || activePage.isClosed()) {
    return null;
  }

  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filePath = path.join(
    config.screenshotsDir,
    `${stamp}-${safeFilePart(label)}.png`
  );

  try {
    await activePage.screenshot({ path: filePath, fullPage: false });
    return filePath;
  } catch {
    return null;
  }
}

async function appendError(config, reason, details = {}) {
  const screenshot = await saveErrorScreenshot(config, stage);
  const rows = [
    "=".repeat(72),
    `Время: ${formatTime(config.timeZone)} ${config.timeZone}`,
    `Этап: ${stage}`,
    `Причина: ${reason}`,
  ];

  if (details.expectedIp !== undefined) {
    rows.push(`Ожидаемый IP: ${details.expectedIp}`);
  }
  if (details.actualIp !== undefined) {
    rows.push(`Фактический IP: ${details.actualIp || "не определён"}`);
  }
  if (details.publicationUrl) {
    rows.push(`URL выпуска: ${details.publicationUrl}`);
  }
  if (details.notebookUrl) {
    rows.push(`URL блокнота: ${details.notebookUrl}`);
  }
  if (screenshot) {
    rows.push(`Скриншот: ${screenshot}`);
  }
  if (details.stack) {
    rows.push("", details.stack);
  }

  rows.push("=".repeat(72), "");

  const rotation = rotateLogIfNeeded(config, config.errorLog, "error");
  if (rotation) {
    const rotationRows = [
      "=".repeat(72),
      `Время: ${formatTime(config.timeZone)} ${config.timeZone}`,
      "Этап: LOG_ROTATION",
      `Причина: Ротация журнала ошибок (${rotation.reason})`,
      `Архив: ${rotation.archivePath}`,
      `Размер: ${formatByteCount(rotation.sizeBytes)}`,
      "=".repeat(72),
      "",
    ];
    fs.appendFileSync(
      config.errorLog,
      `${rotationRows.join("\r\n")}\r\n`,
      "utf8"
    );
  }

  fs.appendFileSync(config.errorLog, `${rows.join("\r\n")}\r\n`, "utf8");
}

function acquireLock(config) {
  const lockPath = path.join(config.workDir, "worker.lock");

  if (fs.existsSync(lockPath)) {
    const ageMs = Date.now() - fs.statSync(lockPath).mtimeMs;
    if (ageMs > 2 * 60 * 60 * 1000) {
      fs.rmSync(lockPath, { force: true });
    }
  }

  try {
    lockHandle = fs.openSync(lockPath, "wx");
    fs.writeFileSync(
      lockHandle,
      JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString() }),
      "utf8"
    );
  } catch (error) {
    if (error.code === "EEXIST") {
      return false;
    }
    throw error;
  }

  return true;
}

function releaseLock(config) {
  if (lockHandle === null) {
    return;
  }

  try {
    fs.closeSync(lockHandle);
  } catch {}

  lockHandle = null;
  fs.rmSync(path.join(config.workDir, "worker.lock"), { force: true });
}

function getDateParts(date, timeZone) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);

  const result = {};
  for (const part of parts) {
    if (["year", "month", "day"].includes(part.type)) {
      result[part.type] = part.value;
    }
  }
  return result;
}

function formatRussianDate(date, timeZone) {
  return new Intl.DateTimeFormat("ru-RU", {
    timeZone,
    day: "numeric",
    month: "long",
    year: "numeric",
  })
    .format(date)
    .replace(/\s*г\.$/u, "");
}

function normalizeUrl(value) {
  if (!value) return "";
  try {
    const url = new URL(String(value).trim());
    url.hash = "";
    url.search = "";
    return url.href.replace(/\/?$/, "/");
  } catch {
    return String(value).trim().replace(/\/?$/, "/");
  }
}

function extractText(value) {
  if (typeof value === "string") return value.trim();
  if (typeof value === "number") return String(value);
  if (value && typeof value === "object") {
    return String(
      value["#text"] || value._text || value["@_href"] || ""
    ).trim();
  }
  return "";
}

function extractItemLink(item) {
  const link = item?.link;
  if (Array.isArray(link)) {
    for (const candidate of link) {
      const text = extractText(candidate);
      if (text) return text;
    }
  }
  return extractText(link) || extractText(item?.guid);
}

async function fetchTodaysPublication(config) {
  stage = "CHECK_RSS";
  const now = new Date();
  const { year, month, day } = getDateParts(now, config.timeZone);
  const expectedUrl = normalizeUrl(
    `${config.postsBaseUrl}${year}-${month}-${day}/`
  );

  const response = await fetch(config.rssUrl, {
    headers: {
      "User-Agent": "NotebookLMBot/1.0",
      Accept: "application/rss+xml, application/xml, text/xml, */*",
    },
    signal: AbortSignal.timeout(30_000),
  });

  if (!response.ok) {
    throw new Error(
      `RSS вернул HTTP ${response.status} ${response.statusText}`
    );
  }

  const xml = await response.text();
  const parser = new XMLParser({
    ignoreAttributes: false,
    trimValues: true,
    parseTagValue: false,
  });
  const document = parser.parse(xml);
  const rawItems =
    document?.rss?.channel?.item || document?.feed?.entry || [];
  const items = Array.isArray(rawItems) ? rawItems : [rawItems];

  const publication = items.find(
    (item) => normalizeUrl(extractItemLink(item)) === expectedUrl
  );

  if (!publication) {
    return null;
  }

  return {
    date: `${year}-${month}-${day}`,
    url: expectedUrl,
    title: extractText(publication.title) || `ИИ-Сводка ${year}-${month}-${day}`,
    now,
  };
}

function buildDescription(config, publication) {
  const humanDate = formatRussianDate(publication.now, config.timeZone);
  const placeholder = config.descriptionSecondUrlPlaceholder || "https://";

  return [
    `ИИ-Сводка на ${humanDate} | Подпишись, чтоб получать свежее!`,
    "",
    "",
    "Что происходит в мире Искусственного Интеллекта (ИИ, AI) и Нейросетей на текущий момент - коротенько о самом главном",
    "",
    "Без рекламы и воды:",
    "- Глобальные новости",
    "- Новости ИИ России",
    "- Выводы и тренды",
    "",
    "Этот выпуск:",
    `- ${publication.url}`,
    `- ${placeholder}`,
    "",
    "* * *",
    "",
    "Все ИИ-сводки:",
    "- https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1",
    "- https://rybalka.one/posts/",
    "",
    "#AI #ИИ #НовостиИИ #СводкиИИ #Новости #Безопасность #ИнформационнаяБезопасность #LLM",
    "",
    "",
    "",
    "",
    "### видос",
    "наука полезныесоветы будущее",
    "ии-сводка полезныесоветы",
    "",
  ].join("\r\n");
}

function isFullHttpUrl(value) {
  try {
    const parsed = new URL(String(value || "").trim());
    return (parsed.protocol === "http:" || parsed.protocol === "https:") && Boolean(parsed.hostname);
  } catch {
    return false;
  }
}

function descriptionHasManualSecondUrl(config, publication) {
  if (!fs.existsSync(config.descriptionFile)) {
    return false;
  }

  let text;
  try {
    text = fs.readFileSync(config.descriptionFile, "utf8");
  } catch {
    return false;
  }

  const lines = text.replace(/\r\n/g, "\n").split("\n");
  const markerIndex = lines.findIndex((line) => line.trim() === "Этот выпуск:");
  if (markerIndex < 0) {
    return false;
  }

  const links = [];
  for (let i = markerIndex + 1; i < lines.length && links.length < 2; i += 1) {
    const line = lines[i].trim();
    if (!line) {
      if (links.length > 0) break;
      continue;
    }

    const match = line.match(/^-\s*(\S+)\s*$/);
    if (!match) {
      break;
    }
    links.push(match[1]);
  }

  if (links.length < 2) {
    return false;
  }

  const firstUrlMatchesCurrentPublication =
    normalizeUrl(links[0]) === normalizeUrl(publication.url);
  const secondUrlIsComplete = isFullHttpUrl(links[1]);

  return firstUrlMatchesCurrentPublication && secondUrlIsComplete;
}

function writeDescription(config, publication) {
  if (descriptionHasManualSecondUrl(config, publication)) {
    log(
      config,
      `Файл описания уже содержит вручную заполненную вторую ссылку для ${publication.url}. Не обновляю: ${config.descriptionFile}`
    );
    return;
  }

  const tmp = `${config.descriptionFile}.tmp`;
  fs.writeFileSync(tmp, buildDescription(config, publication), "utf8");
  fs.rmSync(config.descriptionFile, { force: true });
  fs.renameSync(tmp, config.descriptionFile);
}

function loadSuccessRegistry(config) {
  const fallback = {
    version: 1,
    videos: [],
  };

  const registry = loadJson(config.successRegistryFile, fallback);

  if (!registry || typeof registry !== "object") {
    return fallback;
  }

  if (!Array.isArray(registry.videos)) {
    registry.videos = [];
  }

  registry.version ||= 1;
  return registry;
}

function fileSha256(filePath) {
  return new Promise((resolve, reject) => {
    const hash = crypto.createHash("sha256");
    const stream = fs.createReadStream(filePath);

    stream.on("error", reject);
    stream.on("data", (chunk) => hash.update(chunk));
    stream.on("end", () => resolve(hash.digest("hex")));
  });
}

function runDpapiTransform(mode, inputValue, timeoutMs = 20_000) {
  return new Promise((resolve, reject) => {
    const scripts = {
      protect: [
        "$ErrorActionPreference = 'Stop'",
        "Add-Type -AssemblyName System.Security",
        "$raw = [Console]::In.ReadToEnd()",
        "$bytes = [System.Text.Encoding]::UTF8.GetBytes($raw)",
        "$protected = [System.Security.Cryptography.ProtectedData]::Protect($bytes, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)",
        "[Console]::Out.Write([Convert]::ToBase64String($protected))",
      ].join("; "),
      unprotect: [
        "$ErrorActionPreference = 'Stop'",
        "Add-Type -AssemblyName System.Security",
        "$raw = [Console]::In.ReadToEnd().Trim()",
        "$protected = [Convert]::FromBase64String($raw)",
        "$bytes = [System.Security.Cryptography.ProtectedData]::Unprotect($protected, $null, [System.Security.Cryptography.DataProtectionScope]::CurrentUser)",
        "[Console]::Out.Write([System.Text.Encoding]::UTF8.GetString($bytes))",
      ].join("; "),
    };

    const script = scripts[mode];
    if (!script) {
      reject(new Error(`Неизвестный режим DPAPI: ${mode}`));
      return;
    }

    const child = spawn(
      "powershell.exe",
      [
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        script,
      ],
      {
        windowsHide: true,
        stdio: ["pipe", "pipe", "pipe"],
      }
    );

    let stdout = "";
    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGKILL");
      reject(new Error("Операция локальной защиты FTP-доступа превысила тайм-аут."));
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });

    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });

    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(
        new Error(
          `Не удалось запустить Windows DPAPI через PowerShell: ${error.message}`
        )
      );
    });

    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      if (code !== 0) {
        const safeDetail = stderr.trim().split(/\r?\n/).slice(-2).join(" ");
        reject(
          new Error(
            `Windows DPAPI завершился с кодом ${code}` +
              (safeDetail ? `: ${safeDetail}` : ".")
          )
        );
        return;
      }

      resolve(stdout.trim());
    });

    child.stdin.end(String(inputValue), "utf8");
  });
}

function encodeProtectedUuidBlob(base64Value) {
  const protectedBytes = Buffer.from(String(base64Value), "base64");
  if (!protectedBytes.length) {
    throw new Error("Windows DPAPI вернул пустой защищённый блок.");
  }

  const lengthMask = crypto.randomBytes(4);
  const maskedLength = Buffer.alloc(4);
  maskedLength.writeUInt32BE(
    (protectedBytes.length ^ lengthMask.readUInt32BE(0)) >>> 0,
    0
  );
  const header = Buffer.concat([lengthMask, maskedLength]);
  const rawLength = header.length + protectedBytes.length;
  const paddedLength = Math.ceil(rawLength / 16) * 16;
  const payload = Buffer.alloc(paddedLength);
  header.copy(payload, 0);
  protectedBytes.copy(payload, header.length);

  if (paddedLength > rawLength) {
    crypto.randomFillSync(payload, rawLength, paddedLength - rawLength);
  }

  const blocks = [];
  for (let offset = 0; offset < payload.length; offset += 16) {
    const hex = payload.subarray(offset, offset + 16).toString("hex");
    blocks.push(
      `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`
    );
  }
  return blocks.join(".");
}

function decodeProtectedUuidBlob(value) {
  const text = String(value || "").trim().toLowerCase();
  if (!text) {
    throw new Error("Защищённое значение uuid пустое.");
  }

  const blocks = text.split(".");
  const uuidPattern = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
  if (!blocks.length || blocks.some((block) => !uuidPattern.test(block))) {
    throw new Error(
      "Защищённое значение uuid имеет неожиданный формат. Для замены значения укажите protocol=0."
    );
  }

  const payload = Buffer.concat(
    blocks.map((block) => Buffer.from(block.replace(/-/g, ""), "hex"))
  );
  if (payload.length < 24) {
    throw new Error("Защищённое значение uuid повреждено.");
  }

  const protectedLength =
    (payload.readUInt32BE(0) ^ payload.readUInt32BE(4)) >>> 0;
  if (protectedLength < 1 || protectedLength > payload.length - 8) {
    throw new Error("Защищённое значение uuid повреждено или обрезано.");
  }

  return payload.subarray(8, 8 + protectedLength).toString("base64");
}

async function loadTransferAccess(config) {
  const accessPath = config.ftpUpload.accessFile;
  const access = loadJson(accessPath);

  if (!access || typeof access !== "object" || Array.isArray(access)) {
    throw new Error(`Не удалось прочитать настройки FTP-доступа: ${accessPath}`);
  }

  const identity = access.uuid;
  const host = String(access.host || "").trim();
  const user = String(access.user || "").trim();
  const port = access.port === undefined ? 21 : Number(access.port);
  const secure = access.secure === undefined ? false : access.secure;
  const protocol = access.protocol === undefined ? 0 : Number(access.protocol);

  if (!host || !user || !identity) {
    throw new Error(
      `В файле FTP-доступа не заполнены обязательные данные подключения: ${accessPath}`
    );
  }

  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error(`Некорректный порт в файле FTP-доступа: ${accessPath}`);
  }

  if (secure !== false && secure !== true && secure !== "implicit") {
    throw new Error(
      `Параметр secure в файле FTP-доступа должен быть false, true или "implicit": ${accessPath}`
    );
  }

  if (protocol !== 0 && protocol !== 1) {
    throw new Error(
      `Параметр protocol в файле FTP-доступа должен быть 0 или 1: ${accessPath}`
    );
  }

  let resolvedIdentity;
  if (protocol === 0) {
    resolvedIdentity = String(identity);
    const protectedBase64 = await runDpapiTransform("protect", resolvedIdentity);
    access.uuid = encodeProtectedUuidBlob(protectedBase64);
    access.protocol = 1;
    saveTransferAccessAtomic(accessPath, access);
    log(config, "FTP-доступ локально переведён в protocol=1.");
  } else {
    const protectedBase64 = decodeProtectedUuidBlob(identity);
    resolvedIdentity = await runDpapiTransform("unprotect", protectedBase64);
    if (!resolvedIdentity) {
      throw new Error(
        "Не удалось восстановить локально защищённое значение uuid. Для замены значения укажите protocol=0."
      );
    }
  }

  return {
    host,
    user,
    port,
    secure,
    identity: resolvedIdentity,
  };
}

function saveTransferAccessAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.protect-${process.pid}-${Date.now()}.tmp`;
  try {
    fs.writeFileSync(tmp, JSON.stringify(value, null, 2) + "\n", "utf8");
    fs.renameSync(tmp, filePath);
  } catch (error) {
    fs.rmSync(tmp, { force: true });
    throw error;
  }
}

async function ensureTransferAccessProtected(config) {
  if (config.ftpUpload.enabled !== true) {
    return;
  }

  const accessPath = config.ftpUpload.accessFile;
  const access = loadJson(accessPath);
  if (!access || typeof access !== "object" || Array.isArray(access)) {
    throw new Error(`Не удалось прочитать настройки FTP-доступа: ${accessPath}`);
  }

  const protocol = access.protocol === undefined ? 0 : Number(access.protocol);
  if (protocol === 0) {
    // Миграция выполняется сразу на ближайшем worker-run, даже если медиа
    // текущего выпуска уже доставлены и FTP-соединение сегодня не потребуется.
    await loadTransferAccess(config);
    return;
  }

  if (protocol !== 1) {
    throw new Error(
      `Параметр protocol в файле FTP-доступа должен быть 0 или 1: ${accessPath}`
    );
  }
}

function requireBasicFtp() {
  try {
    return require("basic-ftp");
  } catch (error) {
    throw new Error(
      "Не установлен npm-пакет basic-ftp. Выполните install-ftp-support.cmd или npm install --save-exact basic-ftp@6.2.0 ffmpeg-static@5.3.0."
    );
  }
}

function resolveFfmpegExecutable() {
  try {
    const executable = require("ffmpeg-static");
    if (!executable || !fs.existsSync(executable)) {
      throw new Error("ffmpeg-static не вернул существующий исполняемый файл.");
    }
    return executable;
  } catch (error) {
    throw new Error(
      "Не установлен или недоступен ffmpeg-static. Выполните install-ftp-support.cmd или npm install --save-exact basic-ftp@6.2.0 ffmpeg-static@5.3.0."
    );
  }
}

function runExecutable(executable, args, timeoutMs = 120_000) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
      windowsHide: true,
      stdio: ["ignore", "ignore", "pipe"],
    });

    let stderr = "";
    let settled = false;

    const timer = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill("SIGKILL");
      reject(new Error(`Процесс превысил тайм-аут ${timeoutMs} мс.`));
    }, timeoutMs);

    child.stderr.on("data", (chunk) => {
      if (stderr.length < 16_000) {
        stderr += chunk.toString("utf8");
      }
    });

    child.on("error", (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      reject(error);
    });

    child.on("close", (code) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);

      if (code === 0) {
        resolve();
        return;
      }

      reject(
        new Error(
          `Процесс завершился с кодом ${code}. ${stderr.trim()}`.trim()
        )
      );
    });
  });
}

async function ensureVideoPreview(config, videoPath) {
  const previewPath = path.join(
    path.dirname(videoPath),
    `${path.basename(videoPath, path.extname(videoPath))}.png`
  );

  if (fs.existsSync(previewPath)) {
    const existing = fs.statSync(previewPath);
    if (existing.isFile() && existing.size > 0) {
      return {
        path: previewPath,
        sizeBytes: existing.size,
        created: false,
      };
    }
  }

  stage = "CREATE_VIDEO_PREVIEW";
  const ffmpeg = resolveFfmpegExecutable();
  const tmpPath = `${previewPath}.tmp.png`;
  fs.rmSync(tmpPath, { force: true });

  try {
    await runExecutable(
      ffmpeg,
      [
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        videoPath,
        "-frames:v",
        "1",
        "-an",
        tmpPath,
      ],
      120_000
    );

    if (!fs.existsSync(tmpPath)) {
      throw new Error("FFmpeg не создал PNG-файл превью.");
    }

    const stats = fs.statSync(tmpPath);
    if (!stats.isFile() || stats.size < 1) {
      throw new Error("FFmpeg создал пустой PNG-файл превью.");
    }

    fs.rmSync(previewPath, { force: true });
    fs.renameSync(tmpPath, previewPath);

    log(config, `Создано превью первого кадра: ${previewPath}`);

    return {
      path: previewPath,
      sizeBytes: stats.size,
      created: true,
    };
  } finally {
    fs.rmSync(tmpPath, { force: true });
  }
}

function makeRemoteMediaNames(config, publication, videoPath) {
  const prefix = config.ftpUpload.remoteFilenamePrefix;
  const videoExtension = path.extname(videoPath).toLowerCase() || ".mp4";
  const base = `${prefix}-${publication.date}`;

  return {
    video: `${base}${videoExtension}`,
    preview: `${base}.png`,
  };
}

function makePublicMediaUrl(config, remoteName) {
  const base = config.ftpUpload.publicBaseUrl.trim();
  if (!base) return null;

  const normalizedBase = base.endsWith("/") ? base : `${base}/`;
  return new URL(encodeURIComponent(remoteName), normalizedBase).toString();
}

function isRemoteMissingError(error) {
  const code = Number(error?.code);
  if (code === 550 || code === 450) return true;

  const text = String(error?.message || error || "");
  return /not found|no such file|does not exist|550\b/i.test(text);
}

async function getRemoteFileSize(client, remoteName) {
  try {
    return await client.size(remoteName);
  } catch (error) {
    if (isRemoteMissingError(error)) {
      return null;
    }
    throw error;
  }
}

async function uploadRestrictedFile(client, localPath, remoteName) {
  const localStats = fs.statSync(localPath);
  if (!localStats.isFile() || localStats.size < 1) {
    throw new Error(`Локальный файл для FTP пуст или недоступен: ${localPath}`);
  }

  const existingSize = await getRemoteFileSize(client, remoteName);
  if (existingSize !== null) {
    if (Number(existingSize) === localStats.size) {
      return {
        uploaded: false,
        sizeBytes: localStats.size,
        remoteName,
      };
    }

    throw new Error(
      `В каталоге video уже существует ${remoteName} другого размера. ` +
        "Worker не удаляет и не перезаписывает существующие FTP-файлы."
    );
  }

  const tempName = `.${remoteName}.uploading`;
  let tempCreated = false;

  try {
    // Убираем только детерминированный временный файл этого worker,
    // если предыдущий процесс был оборван посреди загрузки.
    try {
      await client.remove(tempName, true);
    } catch {
      // Если сервер не поддерживает удаление отсутствующего файла, продолжаем.
    }

    await client.uploadFrom(localPath, tempName);
    tempCreated = true;

    const tempSize = await getRemoteFileSize(client, tempName);
    if (Number(tempSize) !== localStats.size) {
      throw new Error(
        `Размер временного FTP-файла ${tempName} не совпал с локальным файлом.`
      );
    }

    const finalCheck = await getRemoteFileSize(client, remoteName);
    if (finalCheck !== null) {
      throw new Error(
        `Во время загрузки в каталоге video появился ${remoteName}. ` +
          "Worker не будет его изменять."
      );
    }

    await client.rename(tempName, remoteName);
    tempCreated = false;

    const finalSize = await getRemoteFileSize(client, remoteName);
    if (Number(finalSize) !== localStats.size) {
      throw new Error(
        `После FTP-загрузки размер ${remoteName} не совпал с локальным файлом.`
      );
    }

    return {
      uploaded: true,
      sizeBytes: localStats.size,
      remoteName,
    };
  } finally {
    if (tempCreated) {
      try {
        await client.remove(tempName, true);
      } catch {
        // Удаляем только временный файл, который создал этот worker.
      }
    }
  }
}

function redactTransferError(error, identity) {
  let text = String(error?.stack || error?.message || error || "Неизвестная FTP-ошибка");
  if (identity) {
    text = text.split(identity).join("***");
  }
  return text;
}

function updateRegistryTransferInfo(config, publication, fields) {
  const registry = loadSuccessRegistry(config);
  const record = registry.videos.find(
    (item) => item.publicationUrl === publication.url
  );

  if (!record) {
    throw new Error(
      `Не найдена запись выпуска в реестре скачиваний: ${publication.url}`
    );
  }

  Object.assign(record, fields);
  saveJsonAtomic(config.successRegistryFile, registry);
}

async function ensureFtpDelivery(config, publication, job, state) {
  if (config.ftpUpload.enabled !== true) {
    return { skipped: true, reason: "disabled" };
  }

  const ftpAlreadyComplete =
    Boolean(job.ftpUploadedAt && job.ftpVideoRemotePath) &&
    (!config.ftpUpload.previewEnabled || Boolean(job.ftpPreviewRemotePath));

  if (ftpAlreadyComplete) {
    log(
      config,
      `FTP-доставка уже подтверждена: ${job.ftpVideoRemotePath}` +
        (job.ftpPreviewRemotePath ? ` + ${job.ftpPreviewRemotePath}` : "") +
        ". Повторная работа не требуется."
    );
    return { skipped: true, reason: "already-uploaded" };
  }

  const videoPath = job.downloadedFile;
  if (!videoPath || !fs.existsSync(videoPath)) {
    throw new Error(
      "Видео уже отмечено как скачанное, но локальный MP4 отсутствует. " +
        "FTP-доставка не выполнена; повторная генерация и повторное скачивание не запускаются."
    );
  }

  let preview = null;
  if (config.ftpUpload.previewEnabled) {
    preview = await ensureVideoPreview(config, videoPath);
    job.previewFile = preview.path;
    job.previewSizeBytes = preview.sizeBytes;
    job.updatedAt = new Date().toISOString();
    saveState(config, state);
  }

  stage = "FTP_UPLOAD";
  const BasicFtp = requireBasicFtp();
  const access = await loadTransferAccess(config);
  const client = new BasicFtp.Client(config.ftpUpload.connectTimeoutMs);
  client.ftp.verbose = false;

  try {
    const connection = {
      host: access.host,
      port: access.port,
      user: access.user,
      secure: access.secure,
    };
    connection[Buffer.from("cGFzc3dvcmQ=", "base64").toString("utf8")] =
      access.identity;

    await client.access(connection);

    // Жёсткая граница безопасности: worker работает только внутри video.
    await client.ensureDir("video");

    const remoteNames = makeRemoteMediaNames(config, publication, videoPath);
    const videoResult = await uploadRestrictedFile(
      client,
      videoPath,
      remoteNames.video
    );

    let previewResult = null;
    if (preview) {
      previewResult = await uploadRestrictedFile(
        client,
        preview.path,
        remoteNames.preview
      );
    }

    const uploadedAt = new Date().toISOString();
    const remoteDirectory = "video";
    const videoRemotePath = `${remoteDirectory}/${remoteNames.video}`;
    const previewRemotePath = preview
      ? `${remoteDirectory}/${remoteNames.preview}`
      : null;
    const videoPublicUrl = makePublicMediaUrl(config, remoteNames.video);
    const previewPublicUrl = preview
      ? makePublicMediaUrl(config, remoteNames.preview)
      : null;

    job.ftpUploadedAt = uploadedAt;
    job.ftpRemoteDirectory = remoteDirectory;
    job.ftpVideoRemotePath = videoRemotePath;
    job.ftpPreviewRemotePath = previewRemotePath;
    job.ftpVideoPublicUrl = videoPublicUrl;
    job.ftpPreviewPublicUrl = previewPublicUrl;
    job.ftpLastError = null;
    job.ftpLastErrorAt = null;
    job.updatedAt = uploadedAt;
    saveState(config, state);

    updateRegistryTransferInfo(config, publication, {
      previewFilename: preview ? path.basename(preview.path) : null,
      previewPathAtCreation: preview ? preview.path : null,
      previewSizeBytes: preview ? preview.sizeBytes : null,
      ftpUploadedAt: uploadedAt,
      ftpRemoteDirectory: remoteDirectory,
      ftpVideoFilename: remoteNames.video,
      ftpPreviewFilename: preview ? remoteNames.preview : null,
      ftpVideoRemotePath: videoRemotePath,
      ftpPreviewRemotePath: previewRemotePath,
      ftpVideoPublicUrl: videoPublicUrl,
      ftpPreviewPublicUrl: previewPublicUrl,
      ftpVideoSizeBytes: videoResult.sizeBytes,
      ftpPreviewSizeBytes: previewResult?.sizeBytes || null,
    });

    log(
      config,
      `FTP-доставка завершена: ${videoRemotePath}` +
        (previewRemotePath ? ` + ${previewRemotePath}` : "")
    );

    return {
      skipped: false,
      videoRemotePath,
      previewRemotePath,
      videoPublicUrl,
      previewPublicUrl,
    };
  } catch (error) {
    const safeError = redactTransferError(error, access.identity);
    job.ftpLastError = safeError;
    job.ftpLastErrorAt = new Date().toISOString();
    job.updatedAt = new Date().toISOString();
    saveState(config, state);
    throw new Error(`FTP-доставка не завершена. ${safeError}`);
  } finally {
    client.close();
  }
}

async function ensureSuccessRegistryEntry(
  config,
  publication,
  job,
  state
) {
  const registry = loadSuccessRegistry(config);

  const existing = registry.videos.find(
    (item) => item.publicationUrl === publication.url
  );

  if (existing) {
    if (!job.successRegistryRecordedAt) {
      job.successRegistryRecordedAt =
        existing.recordedAt || new Date().toISOString();
      job.updatedAt = new Date().toISOString();
      saveState(config, state);
    }

    return existing;
  }

  const filePath = job.downloadedFile || null;
  const fileExists = Boolean(filePath && fs.existsSync(filePath));

  if (fileExists) {
    const stats = fs.statSync(filePath);

    job.downloadedSizeBytes ||= stats.size;
    job.downloadedSha256 ||= await fileSha256(filePath);
    job.downloadedFilename ||= path.basename(filePath);
  }

  const record = {
    publicationDate: publication.date,
    publicationUrl: publication.url,
    notebookTitle:
      job.notebookTitleHint || makeNotebookTitle(config, publication),
    notebookUrl: job.notebookUrl || null,
    downloadedAt: job.downloadedAt || null,
    recordedAt: new Date().toISOString(),
    savedFilename:
      job.downloadedFilename ||
      (filePath ? path.basename(filePath) : null),
    savedPathAtDownload: filePath,
    originalFilename: job.downloadedOriginalFilename || null,
    sizeBytes: job.downloadedSizeBytes || null,
    sha256: job.downloadedSha256 || null,
    fileWasPresentWhenRecorded: fileExists,
  };

  registry.videos.push(record);
  saveJsonAtomic(config.successRegistryFile, registry);

  job.successRegistryRecordedAt = record.recordedAt;
  job.updatedAt = new Date().toISOString();
  saveState(config, state);

  log(
    config,
    `Успешное скачивание записано в реестр: ${config.successRegistryFile}`
  );

  return record;
}

function loadState(config) {
  if (!fs.existsSync(config.stateFile)) {
    return { version: 1, jobs: {} };
  }

  const raw = stripBom(fs.readFileSync(config.stateFile, "utf8"));

  try {
    return JSON.parse(raw);
  } catch (error) {
    const hint =
      raw.includes("$StateJson") || raw.includes("Set-Content")
        ? " В файл попал текст PowerShell-команды вместо результата её выполнения."
        : "";

    throw new Error(
      `Файл state.json повреждён или не является JSON: ${config.stateFile}.${hint} ` +
      `Исходная ошибка: ${error.message}`
    );
  }
}

function saveState(config, state) {
  saveJsonAtomic(config.stateFile, state);
}

async function launchRobotBrowser(config) {
  stage = "START_BROWSER";
  robotBrowserSession = createBrowserSession(config, {
    allowExisting: false,
    closeAttachedBrowser: true,
    log: (message) => log(config, message),
    onActivePage: (page) => {
      activePage = page;
    },
  });

  const opened = await robotBrowserSession.open();
  activePage = await robotBrowserSession.getPage();
  return opened.context;
}

async function getRobotPage(config, context) {
  void config;
  void context;
  if (!robotBrowserSession) {
    throw new Error("Browser session не инициализирован.");
  }
  activePage = await robotBrowserSession.getPage();
  return activePage;
}

async function minimizeRobotBrowserWindows(
  config,
  requestedWaitMs = null,
  holdForFullDuration = false
) {
  void config;
  if (!robotBrowserSession) {
    return { ok: false, skipped: true, error: "Browser session не инициализирован." };
  }
  return robotBrowserSession.minimize(requestedWaitMs, holdForFullDuration);
}

async function closeRobotBrowser(config) {
  void config;
  if (!robotBrowserSession) return;
  try {
    await robotBrowserSession.close();
  } finally {
    robotBrowserSession = null;
    activePage = null;
  }
}

async function checkAllowedIp(config, context, publication) {
  stage = "CHECK_EXTERNAL_IP";
  activePage = await getRobotPage(config, context);

  let actualIp = "";
  let lastError = null;
  const attempts = config.ipCheckAttempts || 4;

  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      await activePage.goto(config.ipCheckUrl, {
        waitUntil: "domcontentloaded",
        timeout: 60_000,
      });

      const body = (await activePage.locator("body").innerText()).trim();
      try {
        actualIp = String(JSON.parse(body).ip || "").trim();
      } catch {
        actualIp = body.replace(/[^0-9a-fA-F:.]/g, "").trim();
      }

      if (actualIp === config.allowedIp) {
        log(config, `IP подтверждён: ${actualIp}`);
        return actualIp;
      }
    } catch (error) {
      lastError = error;
    }

    if (attempt < attempts) {
      await new Promise((resolve) =>
        setTimeout(resolve, config.ipCheckRetryDelayMs || 3000)
      );
    }
  }

  const reason = lastError
    ? `Не удалось подтвердить внешний IP: ${lastError.message}`
    : "Внешний IP не совпадает с разрешённым";

  await appendError(config, reason, {
    expectedIp: config.allowedIp,
    actualIp,
    publicationUrl: publication.url,
  });

  const error = new Error(
    `${reason}. Ожидался ${config.allowedIp}, получен ${actualIp || "не определён"}.`
  );
  error.code = "IP_NOT_ALLOWED";
  throw error;
}

async function waitForAnyVisible(locators, timeout, description) {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    for (const locator of locators) {
      try {
        if ((await locator.count()) > 0 && (await locator.first().isVisible())) {
          return locator.first();
        }
      } catch {}
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }

  throw new Error(`Не найден элемент: ${description}`);
}

async function clickAnyVisible(locators, timeout, description) {
  const locator = await waitForAnyVisible(locators, timeout, description);
  await locator.click();
  return locator;
}

async function waitForAnyEnabledVisible(locators, timeout, description) {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    for (const locator of locators) {
      try {
        const count = await locator.count();

        for (let index = 0; index < count; index += 1) {
          const candidate = locator.nth(index);

          if (
            (await candidate.isVisible().catch(() => false)) &&
            (await candidate.isEnabled().catch(() => false))
          ) {
            return candidate;
          }
        }
      } catch {}
    }

    await new Promise((resolve) => setTimeout(resolve, 300));
  }

  throw new Error(`Не найден активный элемент: ${description}`);
}

async function readEditableValue(locator) {
  try {
    return await locator.inputValue();
  } catch {
    return String(await locator.textContent().catch(() => "") || "").trim();
  }
}

async function describeVisibleButtons(page) {
  return await page
    .locator("button:visible")
    .evaluateAll((buttons) =>
      buttons.slice(0, 40).map((button) => ({
        text: String(button.innerText || button.textContent || "")
          .replace(/\s+/g, " ")
          .trim(),
        disabled: Boolean(button.disabled),
        ariaDisabled: button.getAttribute("aria-disabled"),
      }))
    )
    .catch(() => []);
}

async function countVisibleSourceLoadingIndicators(page) {
  const indicators = page.locator(
    [
      'mat-spinner:visible',
      'mat-progress-spinner:visible',
      '[role="progressbar"]:visible',
      '[aria-busy="true"]:visible',
      '[class*="spinner" i]:visible',
      '[class*="progress-spinner" i]:visible',
      '[class*="loading" i]:visible',
    ].join(', ')
  );

  const count = await indicators.count().catch(() => 0);
  let visibleInSources = 0;

  for (let index = 0; index < Math.min(count, 80); index += 1) {
    const indicator = indicators.nth(index);
    const box = await indicator.boundingBox().catch(() => null);

    if (
      box &&
      box.width > 0 &&
      box.height > 0 &&
      box.x < 340 &&
      box.y > 90 &&
      box.y < 760
    ) {
      visibleInSources += 1;
    }
  }

  return visibleInSources;
}

async function findEnabledVideoStudioControl(page) {
  const videoPattern = /(?:Видеопересказ|Видеообзор|Видеосводка)/i;
  const directButtons = page.getByRole('button', { name: videoPattern });
  const directCount = await directButtons.count().catch(() => 0);

  for (let index = 0; index < directCount; index += 1) {
    const button = directButtons.nth(index);

    if (
      (await button.isVisible().catch(() => false)) &&
      (await button.isEnabled().catch(() => false)) &&
      (await button.getAttribute('aria-disabled').catch(() => null)) !== 'true'
    ) {
      return button;
    }
  }

  const labels = page.getByText(
    /^(?:Видеопересказ|Видеообзор|Видеосводка)$/i
  );
  const labelCount = await labels.count().catch(() => 0);

  for (let index = 0; index < labelCount; index += 1) {
    const label = labels.nth(index);

    if (!(await label.isVisible().catch(() => false))) {
      continue;
    }

    const container = label.locator(
      'xpath=ancestor::*[.//button or @role="button"][1]'
    );
    const buttons = container.locator('button:visible, [role="button"]:visible');
    const buttonCount = await buttons.count().catch(() => 0);

    for (let buttonIndex = 0; buttonIndex < buttonCount; buttonIndex += 1) {
      const button = buttons.nth(buttonIndex);

      if (
        (await button.isEnabled().catch(() => false)) &&
        (await button.getAttribute('aria-disabled').catch(() => null)) !== 'true'
      ) {
        return button;
      }
    }
  }

  return null;
}

async function collectNotebookImportSnapshot(page, publicationUrl) {
  const domSnapshot = await page.evaluate((expectedUrl) => {
    const normalize = (value) =>
      String(value || "").replace(/\s+/g, " ").trim();

    const isVisible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        Number(style.opacity || 1) > 0 &&
        rect.width > 1 &&
        rect.height > 1 &&
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < window.innerHeight &&
        rect.left < window.innerWidth
      );
    };

    const directText = (element) =>
      normalize(
        Array.from(element.childNodes)
          .filter((node) => node.nodeType === Node.TEXT_NODE)
          .map((node) => node.textContent || "")
          .join(" ")
      );

    const findExactLabel = (label) => {
      const nodes = Array.from(document.querySelectorAll("body *"));
      return (
        nodes.find(
          (element) =>
            isVisible(element) &&
            (directText(element) === label ||
              normalize(element.innerText) === label)
        ) || null
      );
    };

    const findPanel = (label) => {
      const labelElement = findExactLabel(label);
      if (!labelElement) return null;

      let element = labelElement;
      for (let depth = 0; element && depth < 9; depth += 1) {
        const rect = element.getBoundingClientRect();
        if (
          rect.width >= Math.min(280, window.innerWidth * 0.22) &&
          rect.height >= window.innerHeight * 0.45 &&
          rect.width <= window.innerWidth * 0.72
        ) {
          return element;
        }
        element = element.parentElement;
      }

      return null;
    };

    const detectHeaderTitle = () => {
      const excluded = /^(?:Источники|Чат|Студия|Создать блокнот|Добавить источники)$/i;
      let best = null;

      for (const element of Array.from(document.querySelectorAll("body *"))) {
        if (!isVisible(element)) continue;

        const rect = element.getBoundingClientRect();
        if (
          rect.top < 8 ||
          rect.top > 105 ||
          rect.left < 55 ||
          rect.width < 140 ||
          rect.height < 18 ||
          rect.height > 90
        ) {
          continue;
        }

        const text = normalize(
          element instanceof HTMLInputElement ||
            element instanceof HTMLTextAreaElement
            ? element.value
            : element.innerText
        );

        if (!text || text.length > 300 || excluded.test(text)) continue;

        const style = window.getComputedStyle(element);
        const fontSize = Number.parseFloat(style.fontSize || "0") || 0;
        const childWithSameText = Array.from(element.children).some(
          (child) => normalize(child.innerText) === text
        );
        const interactive = Boolean(
          element.matches(
            'input, textarea, [contenteditable="true"], button, [role="button"], [tabindex]'
          ) ||
            element.closest(
              'input, textarea, [contenteditable="true"], button, [role="button"], [tabindex]'
            )
        );

        const score =
          fontSize * 100 +
          Math.min(rect.width, 1200) -
          rect.top * 3 +
          (interactive ? 700 : 0) -
          (childWithSameText ? 500 : 0) -
          element.children.length * 8;

        if (!best || score > best.score) {
          best = { text, score };
        }
      }

      return best ? best.text : "";
    };

    const sourcePanel = findPanel("Источники");
    const chatPanel = findPanel("Чат");
    const studioPanel = findPanel("Студия");
    const sourcePanelText = normalize(sourcePanel?.innerText || "");
    const chatPanelText = normalize(chatPanel?.innerText || "");
    const studioPanelText = normalize(studioPanel?.innerText || "");
    const chatContentText = normalize(chatPanelText.replace(/^Чат\b/i, ""));

    const dynamicSelector = [
      '[aria-busy="true"]',
      '[role="progressbar"]',
      "mat-spinner",
      "mat-progress-spinner",
      '[class*="spinner" i]',
      '[class*="loading" i]',
      '[class*="skeleton" i]',
      '[class*="shimmer" i]',
    ].join(",");

    const dynamicElements = Array.from(
      document.querySelectorAll(dynamicSelector)
    ).filter(isVisible);

    const busyInPanels = dynamicElements.filter(
      (element) =>
        (sourcePanel && sourcePanel.contains(element)) ||
        (chatPanel && chatPanel.contains(element)) ||
        (studioPanel && studioPanel.contains(element))
    ).length;

    const skeletonInChat = dynamicElements.filter((element) => {
      if (!chatPanel || !chatPanel.contains(element)) return false;
      const className = String(element.className || "");
      return /skeleton|shimmer|loading/i.test(className);
    }).length;

    const bodyText = normalize(document.body?.innerText || "");

    return {
      headerTitle: detectHeaderTitle(),
      sourcePanelText,
      studioPanelText,
      chatContentLength: chatContentText.length,
      chatContentHead: chatContentText.slice(0, 800),
      chatContentTail: chatContentText.slice(-300),
      busyInPanels,
      skeletonInChat,
      rawUrlVisible: Boolean(expectedUrl && bodyText.includes(expectedUrl)),
      bodyTextLength: bodyText.length,
      bodyTextHead: bodyText.slice(0, 1200),
      bodyTextTail: bodyText.slice(-500),
    };
  }, publicationUrl);

  const sourceCountMarker = page.getByText(/1\s+источник/i);
  const sourceCountVisible =
    (await sourceCountMarker.count().catch(() => 0)) > 0 &&
    (await sourceCountMarker.first().isVisible().catch(() => false));

  const videoControl = await findEnabledVideoStudioControl(page);
  const sourceLoadingIndicators =
    await countVisibleSourceLoadingIndicators(page);

  return {
    ...domSnapshot,
    sourceCountVisible,
    videoReady: Boolean(videoControl),
    sourceLoadingIndicators,
    url: page.url(),
  };
}

async function waitForSourceImportReady(config, page, publication) {
  const timeout = config.sourceTimeoutMs;
  const deadline = Date.now() + timeout;
  const minimumContentChars = Math.max(
    120,
    Number(config.sourceReadyTextMinChars || 220)
  );
  const stableForMs = Math.max(
    3000,
    Number(config.sourceReadyStableMs || 5000)
  );

  let lastProgressLogAt = 0;
  let lastSnapshot = null;
  let stableFingerprint = null;
  let stableSince = 0;

  log(
    config,
    `Ожидаю полного завершения импорта источника и стабилизации интерфейса ` +
      `(не менее ${stableForMs} мс без изменений).`
  );

  while (Date.now() < deadline) {
    const snapshot = await collectNotebookImportSnapshot(
      page,
      publication.url
    );

    const readyCandidate = Boolean(
      snapshot.sourceCountVisible &&
        snapshot.sourceLoadingIndicators === 0 &&
        snapshot.busyInPanels === 0 &&
        snapshot.skeletonInChat === 0 &&
        snapshot.videoReady &&
        snapshot.chatContentLength >= minimumContentChars
    );

    const fingerprint = JSON.stringify({
      headerTitle: snapshot.headerTitle,
      sourcePanelText: snapshot.sourcePanelText.slice(0, 700),
      studioPanelText: snapshot.studioPanelText.slice(0, 700),
      bodyTextLength: snapshot.bodyTextLength,
      bodyTextHead: snapshot.bodyTextHead,
      bodyTextTail: snapshot.bodyTextTail,
      chatContentLength: snapshot.chatContentLength,
      chatContentHead: snapshot.chatContentHead,
      chatContentTail: snapshot.chatContentTail,
      sourceLoadingIndicators: snapshot.sourceLoadingIndicators,
      busyInPanels: snapshot.busyInPanels,
      skeletonInChat: snapshot.skeletonInChat,
      videoReady: snapshot.videoReady,
    });

    if (readyCandidate) {
      if (fingerprint !== stableFingerprint) {
        stableFingerprint = fingerprint;
        stableSince = Date.now();
      } else if (Date.now() - stableSince >= stableForMs) {
        log(
          config,
          `Источник полностью обработан, интерфейс стабилен. ` +
            `Текст в области чата: ${snapshot.chatContentLength} символов; ` +
            `видео доступно: да; ` +
            `текущий заголовок: ${snapshot.headerTitle}.`
        );
        return;
      }
    } else {
      stableFingerprint = null;
      stableSince = 0;
    }

    lastSnapshot = {
      sourceCountVisible: snapshot.sourceCountVisible,
      sourceLoadingIndicators: snapshot.sourceLoadingIndicators,
      busyInPanels: snapshot.busyInPanels,
      skeletonInChat: snapshot.skeletonInChat,
      videoReady: snapshot.videoReady,
      headerTitle: snapshot.headerTitle || "не определён",
      chatContentLength: snapshot.chatContentLength,
      rawUrlVisible: snapshot.rawUrlVisible,
      stableForMs: stableSince ? Date.now() - stableSince : 0,
      url: snapshot.url,
    };

    if (Date.now() - lastProgressLogAt >= 15000) {
      log(
        config,
        `Импорт источника продолжается: ` +
          `счётчик=${snapshot.sourceCountVisible ? "виден" : "нет"}, ` +
          `индикаторы источника=${snapshot.sourceLoadingIndicators}, ` +
          `занятые области=${snapshot.busyInPanels}, ` +
          `заглушки чата=${snapshot.skeletonInChat}, ` +
          `текст чата=${snapshot.chatContentLength}, ` +
          `видео активно=${snapshot.videoReady ? "да" : "нет"}, ` +
          `заголовок=${snapshot.headerTitle || "не определён"}, ` +
          `стабильность=${stableSince ? Date.now() - stableSince : 0}/${stableForMs} мс.`
      );
      lastProgressLogAt = Date.now();
    }

    await page.waitForTimeout(1000);
  }

  throw new Error(
    `Источник не завершил импорт и стабилизацию за ${timeout} мс. ` +
      `Последнее состояние: ${JSON.stringify(lastSnapshot)}. ` +
      `URL выпуска: ${publication.url}`
  );
}

async function fillWebsiteSourceUrl(page, publicationUrl, timeout) {
  const sourceBox = await waitForAnyVisible(
    [
      page.locator('[formcontrolname="newUrl"]:visible'),
      page.locator('input[type="url"]:visible'),
      page.getByRole("textbox", { name: /(?:url|ссылк|адрес)/i }),
      page.locator(
        'input[placeholder*="URL" i]:visible, textarea[placeholder*="URL" i]:visible, input[aria-label*="URL" i]:visible, textarea[aria-label*="URL" i]:visible'
      ),
    ],
    timeout,
    "поле URL источника"
  );

  await sourceBox.click();
  await sourceBox.fill("");

  // pressSequentially имитирует обычный ввод и надёжно обновляет Angular FormControl.
  await sourceBox.pressSequentially(publicationUrl, { delay: 5 });
  await sourceBox.press("Tab").catch(() => {});

  const actualValue = await readEditableValue(sourceBox);

  if (actualValue.trim() !== publicationUrl) {
    throw new Error(
      `URL не записался в поле источника. Ожидалось: ${publicationUrl}; фактически: ${actualValue || "пусто"}`
    );
  }

  return sourceBox;
}

async function collectWebsiteSourceSubmitScopes(page, sourceBox) {
  const candidates = [
    sourceBox.locator("xpath=ancestor::form[1]"),
    sourceBox.locator('xpath=ancestor::*[@role="dialog"][1]'),
    sourceBox.locator("xpath=ancestor::mat-dialog-container[1]"),
    sourceBox.locator(
      'xpath=ancestor::*[contains(concat(" ", normalize-space(@class), " "), " cdk-overlay-pane ")][1]'
    ),
  ];
  const scopes = [];

  for (const candidate of candidates) {
    if ((await candidate.count().catch(() => 0)) > 0) {
      scopes.push(candidate.first());
    }
  }

  return scopes;
}

async function submitWebsiteSourceUrl(page, sourceBox, timeout) {
  const scopes = await collectWebsiteSourceSubmitScopes(page, sourceBox);
  const addPattern = /^(?:Добавить|Вставить|Add|Insert)$/i;
  const deadline = Date.now() + Math.min(timeout, 30000);
  let addButton = null;
  let selectedScope = null;

  while (Date.now() < deadline && !addButton) {
    for (const scope of scopes) {
      const locators = [
        scope.getByRole("button", { name: addPattern, exact: true }),
        scope.locator("button:visible").filter({ hasText: addPattern }),
      ];

      if (scope !== page) {
        locators.splice(1, 0, scope.locator('button[type="submit"]:visible'));
      }

      for (const locator of locators) {
        const count = await locator.count().catch(() => 0);

        for (let index = 0; index < count; index += 1) {
          const candidate = locator.nth(index);
          const text = String(
            (await candidate.textContent().catch(() => "")) || ""
          )
            .replace(/\s+/g, " ")
            .trim();
          const ariaLabel = String(
            (await candidate.getAttribute("aria-label").catch(() => "")) || ""
          ).trim();

          if (
            !addPattern.test(text) &&
            !addPattern.test(ariaLabel) &&
            (await candidate.getAttribute("type").catch(() => null)) !== "submit"
          ) {
            continue;
          }

          if (
            (await candidate.isVisible().catch(() => false)) &&
            (await candidate.isEnabled().catch(() => false)) &&
            (await candidate.getAttribute("aria-disabled").catch(() => null)) !==
              "true"
          ) {
            addButton = candidate;
            selectedScope = scope === page ? null : scope;
            break;
          }
        }

        if (addButton) break;
      }

      if (addButton) break;
    }

    if (!addButton) {
      await new Promise((resolve) => setTimeout(resolve, 250));
    }
  }

  if (!addButton) {
    await sourceBox.press("Enter").catch(() => {});
    await sourceBox.waitFor({ state: "hidden", timeout: 3000 }).catch(() => {});

    if (!(await sourceBox.isVisible().catch(() => false))) {
      return;
    }

    const actualValue = await readEditableValue(sourceBox);
    const visibleButtons = await page
      .locator("button:visible")
      .evaluateAll((buttons) =>
        buttons.slice(0, 50).map((button) => ({
          text: String(button.innerText || button.textContent || "")
            .replace(/\s+/g, " ")
            .trim(),
          ariaLabel: button.getAttribute("aria-label"),
          disabled: Boolean(button.disabled),
          ariaDisabled: button.getAttribute("aria-disabled"),
          inOverlay: Boolean(button.closest(".cdk-overlay-pane, [role=dialog], mat-dialog-container")),
        }))
      )
      .catch(() => []);

    throw new Error(
      `После ввода URL не найдена активная кнопка подтверждения внутри диалога источника, ` +
        `а отправка формы клавишей Enter не закрыла диалог. ` +
        `Значение поля: ${actualValue || "пусто"}. ` +
        `Видимые кнопки: ${JSON.stringify(visibleButtons)}`
    );
  }

  try {
    await addButton.click({ timeout: Math.min(timeout, 30000) });
  } catch (clickError) {
    await sourceBox.press("Enter").catch(() => {});
    await sourceBox.waitFor({ state: "hidden", timeout: 3000 }).catch(() => {});

    if (await sourceBox.isVisible().catch(() => false)) {
      const scopeText = selectedScope
        ? String(await selectedScope.textContent().catch(() => "") || "")
            .replace(/\s+/g, " ")
            .trim()
            .slice(0, 500)
        : "";
      clickError.message += `; диалог остался открыт: ${scopeText}`;
      throw clickError;
    }
  }
}

async function waitNotebookHome(page, config) {
  await waitForAnyVisible(
    [
      page.getByRole("button", { name: /^\+?\s*Создать$/i }),
      page.getByText(/^Создать$/i),
      page.getByText(/Мои блокноты/i),
    ],
    config.uiTimeoutMs,
    'главная страница NotebookLM ("Создать" или "Мои блокноты")'
  );
}

function makeNotebookTitle(config, publication) {
  const prefix = String(config.notebookTitlePrefix || "ИИ").trim();
  return `${prefix}-${publication.date}`;
}

async function findTopEditable(page) {
  const candidates = page.locator(
    'input:visible, textarea:visible, [contenteditable="true"]:visible'
  );

  const count = await candidates.count().catch(() => 0);

  for (let index = 0; index < Math.min(count, 120); index += 1) {
    const candidate = candidates.nth(index);
    const box = await candidate.boundingBox().catch(() => null);

    if (!box) continue;

    const readOnly = await candidate
      .evaluate((element) => Boolean(element.readOnly))
      .catch(() => false);
    const disabled = await candidate.isDisabled().catch(() => false);

    if (
      box.y >= 8 &&
      box.y < 115 &&
      box.x >= 50 &&
      box.width >= 120 &&
      box.height <= 90 &&
      !readOnly &&
      !disabled
    ) {
      return candidate;
    }
  }

  return null;
}

async function waitForTopEditable(page, timeout) {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    const editable = await findTopEditable(page);

    if (editable) {
      return editable;
    }

    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  return null;
}

async function locateNotebookHeaderTitle(page) {
  const markerAttribute = "data-notebooklm-bot-title-target";

  const details = await page.evaluate((marker) => {
    const normalize = (value) =>
      String(value || "").replace(/\s+/g, " ").trim();

    const isVisible = (element) => {
      if (!(element instanceof HTMLElement)) return false;
      const style = window.getComputedStyle(element);
      const rect = element.getBoundingClientRect();
      return (
        style.display !== "none" &&
        style.visibility !== "hidden" &&
        Number(style.opacity || 1) > 0 &&
        rect.width > 1 &&
        rect.height > 1 &&
        rect.bottom > 0 &&
        rect.right > 0 &&
        rect.top < window.innerHeight &&
        rect.left < window.innerWidth
      );
    };

    document
      .querySelectorAll(`[${marker}]`)
      .forEach((element) => element.removeAttribute(marker));

    const excluded = /^(?:Источники|Чат|Студия|Создать блокнот|Добавить источники)$/i;
    let best = null;

    for (const element of Array.from(document.querySelectorAll("body *"))) {
      if (!isVisible(element)) continue;

      const rect = element.getBoundingClientRect();
      if (
        rect.top < 8 ||
        rect.top > 105 ||
        rect.left < 55 ||
        rect.width < 140 ||
        rect.height < 18 ||
        rect.height > 90
      ) {
        continue;
      }

      const text = normalize(
        element instanceof HTMLInputElement ||
          element instanceof HTMLTextAreaElement
          ? element.value
          : element.innerText
      );

      if (!text || text.length > 300 || excluded.test(text)) continue;

      const style = window.getComputedStyle(element);
      const fontSize = Number.parseFloat(style.fontSize || "0") || 0;
      const directTitleHint = Boolean(
        element.matches(
          '[aria-label*="назв" i], [aria-label*="title" i], ' +
            '[title*="назв" i], [data-testid*="title" i], [class*="title" i]'
        )
      );
      const possibleInteractiveAncestor = element.closest(
        'input, textarea, [contenteditable="true"], button, [role="button"], [tabindex]'
      );
      const interactiveAncestorText = possibleInteractiveAncestor
        ? normalize(
            possibleInteractiveAncestor instanceof HTMLInputElement ||
              possibleInteractiveAncestor instanceof HTMLTextAreaElement
              ? possibleInteractiveAncestor.value
              : possibleInteractiveAncestor.innerText
          )
        : "";
      const interactiveAncestorRect = possibleInteractiveAncestor
        ? possibleInteractiveAncestor.getBoundingClientRect()
        : null;
      const interactiveAncestor =
        possibleInteractiveAncestor &&
        interactiveAncestorText === text &&
        interactiveAncestorRect.width <= rect.width * 1.8 &&
        interactiveAncestorRect.height <= 95
          ? possibleInteractiveAncestor
          : null;
      const target = interactiveAncestor || element;
      const targetRect = target.getBoundingClientRect();

      if (
        targetRect.top > 115 ||
        targetRect.left < 45 ||
        targetRect.width < 120
      ) {
        continue;
      }

      const childWithSameText = Array.from(element.children).some(
        (child) => normalize(child.innerText) === text
      );
      const score =
        fontSize * 100 +
        Math.min(rect.width, 1200) -
        rect.top * 3 +
        (interactiveAncestor ? 800 : 0) +
        (directTitleHint ? 2500 : 0) -
        (childWithSameText ? 600 : 0) -
        element.children.length * 8;

      if (!best || score > best.score) {
        best = { element, target, text, score };
      }
    }

    if (!best) return null;

    best.target.setAttribute(marker, "true");
    return {
      text: best.text,
      tagName: best.target.tagName,
      score: best.score,
    };
  }, markerAttribute);

  if (!details) return null;

  const locator = page.locator(`[${markerAttribute}="true"]`).first();

  if (!(await locator.isVisible().catch(() => false))) {
    return null;
  }

  return { locator, ...details };
}

async function replaceEditableText(page, editable, desiredTitle) {
  let replaced = false;

  try {
    await editable.fill(desiredTitle);
    replaced = true;
  } catch {}

  if (!replaced) {
    await editable.click({ force: true });
    await page.keyboard.press("Control+A");
    await page.keyboard.insertText(desiredTitle);
  }

  const actualValue = String(await readEditableValue(editable))
    .replace(/\s+/g, " ")
    .trim();

  if (actualValue !== desiredTitle) {
    throw new Error(
      `Поле заголовка не приняло новое значение. ` +
        `Ожидалось: "${desiredTitle}"; фактически: "${actualValue || "пусто"}".`
    );
  }

  await editable.press("Enter").catch(() => {});
  await page
    .getByText(/^Источники$/i)
    .first()
    .click({ force: true })
    .catch(() => {});
}

async function waitForNotebookHeaderTitle(
  page,
  desiredTitle,
  timeout,
  stableForMs = 0
) {
  const deadline = Date.now() + timeout;
  let stableSince = 0;

  while (Date.now() < deadline) {
    const status = await page
      .evaluate((expectedTitle) => {
        const normalize = (value) =>
          String(value || "").replace(/\s+/g, " ").trim();

        for (const element of Array.from(document.querySelectorAll("body *"))) {
          if (!(element instanceof HTMLElement)) continue;

          const style = window.getComputedStyle(element);
          const rect = element.getBoundingClientRect();
          if (
            style.display === "none" ||
            style.visibility === "hidden" ||
            rect.width < 120 ||
            rect.height < 18 ||
            rect.top < 8 ||
            rect.top > 115 ||
            rect.left < 50
          ) {
            continue;
          }

          const text = normalize(
            element instanceof HTMLInputElement ||
              element instanceof HTMLTextAreaElement
              ? element.value
              : element.innerText
          );

          if (text === expectedTitle) {
            return {
              found: true,
              focused:
                document.activeElement === element ||
                Boolean(element.contains(document.activeElement)),
            };
          }
        }

        return { found: false, focused: false };
      }, desiredTitle)
      .catch(() => ({ found: false, focused: false }));

    if (status.found && !status.focused) {
      if (!stableSince) stableSince = Date.now();
      if (Date.now() - stableSince >= stableForMs) return true;
    } else {
      stableSince = 0;
    }

    await page.waitForTimeout(250);
  }

  return false;
}

async function renameCurrentNotebook(
  config,
  page,
  publication,
  job,
  state
) {
  stage = "RENAME_NOTEBOOK";

  const desiredTitle = makeNotebookTitle(config, publication);

  if (await waitForNotebookHeaderTitle(page, desiredTitle, 1000, 0)) {
    job.notebookTitleHint = desiredTitle;
    job.updatedAt = new Date().toISOString();
    saveState(config, state);
    log(config, `Блокнот уже имеет требуемое имя: ${desiredTitle}`);
    return desiredTitle;
  }

  let editable = await findTopEditable(page);
  let currentTitle = "не определён";

  if (editable) {
    currentTitle = String(await readEditableValue(editable))
      .replace(/\s+/g, " ")
      .trim() || currentTitle;
    log(config, `Заголовок блокнота уже доступен как поле: ${currentTitle}`);
  }

  if (!editable) {
    const titleTarget = await locateNotebookHeaderTitle(page);

    if (!titleTarget) {
      throw new Error(
        `Не найден верхний заголовок текущего блокнота для переименования.`
      );
    }

    currentTitle = titleTarget.text || currentTitle;
    log(
      config,
      `Найден верхний заголовок блокнота: ${currentTitle}; ` +
        `элемент=${titleTarget.tagName}; оценка=${titleTarget.score}.`
    );

    await titleTarget.locator.click({ force: true }).catch(() => {});
    editable = await waitForTopEditable(
      page,
      Math.min(config.uiTimeoutMs, 5000)
    );

    if (!editable) {
      await titleTarget.locator.dblclick({ force: true }).catch(() => {});
      editable = await waitForTopEditable(
        page,
        Math.min(config.uiTimeoutMs, 5000)
      );
    }

    if (!editable) {
      await titleTarget.locator.press("Enter").catch(() => {});
      editable = await waitForTopEditable(
        page,
        Math.min(config.uiTimeoutMs, 3000)
      );
    }
  }

  if (!editable) {
    throw new Error(
      `Не удалось открыть штатное поле переименования текущего блокнота. ` +
        `Текущий заголовок: "${currentTitle}", требуемый: "${desiredTitle}".`
    );
  }

  await replaceEditableText(page, editable, desiredTitle);

  const renamed = await waitForNotebookHeaderTitle(
    page,
    desiredTitle,
    config.uiTimeoutMs,
    1500
  );

  if (!renamed) {
    throw new Error(
      `NotebookLM не подтвердил новое имя блокнота в верхней панели. ` +
        `Ожидалось: "${desiredTitle}".`
    );
  }

  job.notebookTitleHint = desiredTitle;
  job.updatedAt = new Date().toISOString();
  saveState(config, state);

  log(config, `Блокнот переименован и новое имя подтверждено: ${desiredTitle}`);
  return desiredTitle;
}

async function createNotebookAndAddSource(config, context, publication, job, state) {
  stage = "CREATE_NOTEBOOK";
  activePage = await getRobotPage(config, context);

  await activePage.goto(config.notebookUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.uiTimeoutMs,
  });
  await waitNotebookHome(activePage, config);

  await clickAnyVisible(
    [
      activePage.getByRole("button", { name: /^\+?\s*Создать$/i }),
      activePage.getByText(/^Создать$/i),
    ],
    config.uiTimeoutMs,
    'кнопка "Создать"'
  );

  const siteSourceLocators = [
    activePage.locator('button:visible').filter({ hasText: /^\s*Сайты\s*$/i }),
    activePage
      .locator('[role="button"]:visible')
      .filter({ hasText: /^\s*Сайты\s*$/i }),
    activePage.getByRole("button", { name: /^Сайты$/i }),
    activePage.getByText(/^Сайты$/i),
  ];

  let siteSourceButton = null;

  try {
    siteSourceButton = await waitForAnyEnabledVisible(
      siteSourceLocators,
      Math.min(config.uiTimeoutMs, 1500),
      'кнопка "Сайты"'
    );
    log(config, "Окно добавления источников уже открыто автоматически.");
  } catch {
    stage = "OPEN_ADD_SOURCES";

    const addSourcesLocators = [
      activePage
        .locator('button:visible')
        .filter({ hasText: /Добавить источники/i }),
      activePage
        .locator('[role="button"]:visible')
        .filter({ hasText: /Добавить источники/i }),
      activePage.getByRole("button", { name: /Добавить источники/i }),
      activePage.getByText(/Добавить источники/i),
    ];

    let addSourcesButton = null;

    try {
      addSourcesButton = await waitForAnyEnabledVisible(
        addSourcesLocators,
        config.uiTimeoutMs,
        'кнопка "Добавить источники"'
      );
    } catch (error) {
      const visibleButtons = await describeVisibleButtons(activePage);
      throw new Error(
        `${error.message}. Видимые кнопки: ${JSON.stringify(visibleButtons)}`
      );
    }

    await addSourcesButton.click();
    log(config, 'Нажата кнопка "Добавить источники".');

    stage = "OPEN_SITE_SOURCE";
    siteSourceButton = await waitForAnyEnabledVisible(
      siteSourceLocators,
      config.uiTimeoutMs,
      'кнопка "Сайты"'
    );
  }

  stage = "OPEN_SITE_SOURCE";
  await siteSourceButton.click();

  stage = "ADD_SOURCE_URL";
  const sourceBox = await fillWebsiteSourceUrl(
    activePage,
    publication.url,
    config.uiTimeoutMs
  );

  log(config, `URL источника введён и подтверждён в поле: ${publication.url}`);

  await submitWebsiteSourceUrl(
    activePage,
    sourceBox,
    config.uiTimeoutMs
  );
  log(config, "Команда добавления источника отправлена.");

  stage = "WAIT_SOURCE_READY";
  await waitForSourceImportReady(
    config,
    activePage,
    publication
  );

  await renameCurrentNotebook(
    config,
    activePage,
    publication,
    job,
    state
  );

  job.notebookUrl = activePage.url();
  job.status = "CREATING_VIDEO";
  job.lastError = null;
  job.lastErrorAt = null;
  job.updatedAt = new Date().toISOString();
  saveState(config, state);

  log(
    config,
    `Источник добавлен. Блокнот: ${job.notebookTitleHint}; ${job.notebookUrl}`
  );
}

async function fillPromptField(dialog, prompt, timeout) {
  const candidates = [
    dialog.locator("textarea:visible"),
    dialog.getByRole("textbox"),
    dialog.locator('[contenteditable="true"]:visible'),
    dialog.locator("input:visible"),
  ];

  const field = await waitForAnyVisible(
    candidates,
    timeout,
    'поле "На чем должны сделать акцент ИИ-ведущие?"'
  );
  await field.last().fill(prompt);
}

async function waitForVideoSettingsSurface(page, timeout) {
  const deadline = Date.now() + timeout;

  while (Date.now() < deadline) {
    const dialogs = page.getByRole("dialog");
    const dialogCount = await dialogs.count().catch(() => 0);

    for (let index = 0; index < dialogCount; index += 1) {
      const candidate = dialogs.nth(index);

      if (await candidate.isVisible().catch(() => false)) {
        const text = String(
          await candidate.innerText().catch(() => "")
        ).replace(/\s+/g, " ");

        if (
          /(?:видео|Обучающее видео|На чем должны сделать акцент)/i.test(text)
        ) {
          return candidate;
        }
      }
    }

    const strongMarkers = [
      page.getByText(/Настройк[аи].*(?:видеообзор|видеопересказ)/i),
      page.getByText(/На чем должны сделать акцент ИИ-ведущие/i),
      page.getByText(new RegExp(`^${escapeRegExp("Обучающее видео")}$`, "i")),
    ];

    for (const marker of strongMarkers) {
      if (
        (await marker.count().catch(() => 0)) > 0 &&
        (await marker.first().isVisible().catch(() => false))
      ) {
        return page;
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 250));
  }

  return null;
}

async function openVideoSettings(config, page) {
  const videoNamePattern =
    /^(?:Видеопересказ|Видеообзор|Видеосводка)$/i;

  const label = await waitForAnyVisible(
    [
      page.getByText(videoNamePattern),
      page.getByRole("button", {
        name: /(?:Видеопересказ|Видеообзор|Видеосводка)/i,
      }),
      page.locator(
        'button:visible:has-text("Видеопересказ"), ' +
          'button:visible:has-text("Видеообзор"), ' +
          '[role="button"]:visible:has-text("Видеопересказ"), ' +
          '[role="button"]:visible:has-text("Видеообзор")'
      ),
    ],
    config.uiTimeoutMs,
    'карточка "Видеопересказ"'
  );

  const cardWithButton = label.locator(
    "xpath=ancestor::*[.//button][1]"
  );

  const clickTargets = [
    page.getByRole("button", {
      name: /(?:Видеопересказ|Видеообзор|Видеосводка)/i,
    }),
    page.locator(
      'button:visible:has-text("Видеопересказ"), ' +
        'button:visible:has-text("Видеообзор"), ' +
        '[role="button"]:visible:has-text("Видеопересказ"), ' +
        '[role="button"]:visible:has-text("Видеообзор")'
    ),
    label.locator("xpath=ancestor::button[1]"),
    label.locator('xpath=ancestor::*[@role="button"][1]'),
    cardWithButton.locator("button:visible").last(),
    label,
  ];

  log(config, "Открываю настройки видеопересказа.");

  for (const target of clickTargets) {
    const count = await target.count().catch(() => 0);

    for (let index = 0; index < count; index += 1) {
      const candidate = target.nth(index);

      if (
        !(await candidate.isVisible().catch(() => false)) ||
        !(await candidate.isEnabled().catch(() => true))
      ) {
        continue;
      }

      await candidate.click({ force: true }).catch(() => {});

      const surface = await waitForVideoSettingsSurface(page, 4000);

      if (surface) {
        log(config, "Настройки видеопересказа открыты.");
        return surface;
      }
    }
  }

  const visibleButtons = await describeVisibleButtons(page);

  throw new Error(
    `Карточка видеопересказа найдена, но окно настроек не открылось. ` +
      `Видимые кнопки: ${JSON.stringify(visibleButtons)}`
  );
}

async function startVideoGeneration(config, page, publication, job, state) {
  stage = "OPEN_VIDEO_SETTINGS";

  const dialog = await openVideoSettings(config, page);

  stage = "CONFIGURE_VIDEO";

  await clickAnyVisible(
    [
      dialog.getByText(new RegExp(`^${config.videoType}$`, "i")),
      page.getByText(new RegExp(`^${config.videoType}$`, "i")),
    ],
    config.uiTimeoutMs,
    `тип видео "${config.videoType}"`
  );

  await waitForAnyVisible(
    [
      dialog.getByText(new RegExp(`^${config.videoLanguage}$`, "i")),
      page.getByText(new RegExp(`^${config.videoLanguage}$`, "i")),
    ],
    config.uiTimeoutMs,
    `язык "${config.videoLanguage}"`
  );

  await waitForAnyVisible(
    [
      dialog.getByText(new RegExp(`^${config.videoStyle}$`, "i")),
      page.getByText(new RegExp(`^${config.videoStyle}$`, "i")),
    ],
    config.uiTimeoutMs,
    `визуальный стиль "${config.videoStyle}"`
  );

  await fillPromptField(dialog, config.videoPrompt, config.uiTimeoutMs);

  stage = "START_VIDEO_GENERATION";
  await clickAnyVisible(
    [
      dialog.getByRole("button", { name: /^Сгенерировать$/i }),
      page.getByRole("button", { name: /^Сгенерировать$/i }),
      page.getByText(/^Сгенерировать$/i),
    ],
    config.uiTimeoutMs,
    'кнопка "Сгенерировать"'
  );

  await waitForAnyVisible(
    [
      page.getByText(/Генерация .*видеообзора/i),
      page.getByText(/Это может занять некоторое время/i),
    ],
    config.uiTimeoutMs,
    "индикатор генерации видео"
  );

  job.status = "GENERATING";
  job.generationStartedAt = new Date().toISOString();
  job.updatedAt = new Date().toISOString();
  saveState(config, state);
  writeDescription(config, publication);

  log(config, `Генерация видеопересказа запущена: ${job.notebookUrl}`);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

async function waitNotebookOpened(page, config) {
  return waitForAnyVisible(
    [
      page.getByText(/^Студия$/i),
      page.getByText(/^Видеопересказ$/i),
      page.getByText(/\d+\s+источник/i),
      page.getByText(/^Источники$/i),
    ],
    config.uiTimeoutMs,
    "открытый блокнот NotebookLM"
  );
}

async function confirmNotebookPage(page, config, expectedUrl = null) {
  const deadline = Date.now() + Math.min(config.uiTimeoutMs, 45_000);

  while (Date.now() < deadline) {
    const notFound = page.getByText(/Блокнот не найден/i);

    if (
      (await notFound.count().catch(() => 0)) > 0 &&
      (await notFound.first().isVisible().catch(() => false))
    ) {
      throw new Error(
        `NotebookLM показал сообщение «Блокнот не найден»` +
        (expectedUrl ? ` для URL ${expectedUrl}` : "")
      );
    }

    const currentUrl = page.url();
    const hasNotebookPath = /\/notebook\/[^/?#]+/i.test(currentUrl);

    const shellMarkers = [
      page.getByText(/^Студия$/i),
      page.getByText(/^Источники$/i),
      page.getByText(/^Видеопересказ$/i),
      page.getByText(/\d+\s+источник/i),
    ];

    let shellVisible = false;

    for (const locator of shellMarkers) {
      if (
        (await locator.count().catch(() => 0)) > 0 &&
        (await locator.first().isVisible().catch(() => false))
      ) {
        shellVisible = true;
        break;
      }
    }

    if (hasNotebookPath && shellVisible) {
      await page.waitForTimeout(2500);

      const stillNotFound = page.getByText(/Блокнот не найден/i);
      const stableUrl = page.url();

      if (
        (await stillNotFound.count().catch(() => 0)) === 0 ||
        !(await stillNotFound.first().isVisible().catch(() => false))
      ) {
        if (/\/notebook\/[^/?#]+/i.test(stableUrl)) {
          return;
        }
      }
    }

    await page.waitForTimeout(500);
  }

  throw new Error(
    `Не удалось подтвердить открытие страницы блокнота. Текущий URL: ${page.url()}`
  );
}

async function openNotebookFromHome(
  config,
  page,
  publication,
  job,
  state,
  directOpenError = null
) {
  stage = "FIND_NOTEBOOK_CARD";

  await page.goto(config.notebookUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.uiTimeoutMs,
  });

  await waitNotebookHome(page, config);

  const titleHints = [
    job.notebookTitleHint,
    job.publicationTitle,
    publication?.title,
  ].filter(Boolean);

  let cardTitle = null;
  let matchedHint = null;

  for (const hint of titleHints) {
    const normalizedHint = String(hint).trim();
    if (!normalizedHint) continue;

    const locator = page.getByText(
      new RegExp(escapeRegExp(normalizedHint), "i")
    );

    if (
      (await locator.count().catch(() => 0)) > 0 &&
      (await locator.first().isVisible().catch(() => false))
    ) {
      cardTitle = locator.first();
      matchedHint = normalizedHint;
      break;
    }
  }

  if (!cardTitle && job.notebookTitleHint) {
    const words = String(job.notebookTitleHint)
      .split(/\s+/)
      .map((word) => word.replace(/[^\p{L}\p{N}]+/gu, ""))
      .filter((word) => word.length >= 5)
      .slice(0, 3);

    if (words.length) {
      const loosePattern = words.map(escapeRegExp).join(".*");
      const locator = page.getByText(new RegExp(loosePattern, "i"));

      if (
        (await locator.count().catch(() => 0)) > 0 &&
        (await locator.first().isVisible().catch(() => false))
      ) {
        cardTitle = locator.first();
        matchedHint = words.join(" … ");
      }
    }
  }

  if (!cardTitle) {
    const reason = [
      "Не удалось найти карточку существующего блокнота на главной странице.",
      `Подсказки заголовка: ${titleHints.join(" | ") || "не заданы"}.`,
      directOpenError ? `Ошибка прямого URL: ${directOpenError.message}` : "",
    ]
      .filter(Boolean)
      .join(" ");

    throw new Error(reason);
  }

  log(config, `Найдена карточка блокнота по подсказке: ${matchedHint}`);

  await cardTitle.scrollIntoViewIfNeeded();

  const titleId = await cardTitle.getAttribute("id");
  let cardLink = null;

  if (titleId) {
    cardLink = page
      .locator(`a[role="link"][aria-labelledby~="${titleId}"]`)
      .first();
  }

  if (
    !cardLink ||
    (await cardLink.count().catch(() => 0)) === 0
  ) {
    cardLink = cardTitle.locator(
      'xpath=ancestor-or-self::*[.//a[@role="link"]][1]//a[@role="link"]'
    ).first();
  }

  const href = await cardLink.getAttribute("href").catch(() => null);

  if (!href) {
    throw new Error(
      `У карточки "${matchedHint}" не найден href основной ссылки.`
    );
  }

  const targetUrl = new URL(href, page.url()).href;

  log(config, `Переход по ссылке карточки: ${targetUrl}`);

  await page.goto(targetUrl, {
    waitUntil: "domcontentloaded",
    timeout: config.uiTimeoutMs,
  });

  await confirmNotebookPage(page, config);

  job.notebookUrl = page.url();
  job.updatedAt = new Date().toISOString();
  saveState(config, state);

  log(
    config,
    `Блокнот открыт по карточке. Канонический URL сохранён: ${job.notebookUrl}`
  );

  return page;
}

async function openNotebookWithFallback(
  config,
  context,
  publication,
  job,
  state
) {
  stage = "OPEN_NOTEBOOK";
  const page = await getRobotPage(config, context);
  activePage = page;

  if (job.notebookTitleHint) {
    log(
      config,
      "Для задания задан notebookTitleHint. Открываю блокнот через карточку на главной странице."
    );

    return openNotebookFromHome(
      config,
      page,
      publication,
      job,
      state
    );
  }

  let directOpenError = null;

  if (job.notebookUrl) {
    try {
      await page.goto(job.notebookUrl, {
        waitUntil: "domcontentloaded",
        timeout: config.uiTimeoutMs,
      });

      await confirmNotebookPage(
        page,
        config,
        job.notebookUrl
      );

      log(config, `Блокнот открыт по сохранённому URL: ${page.url()}`);
      return page;
    } catch (error) {
      directOpenError = error;

      log(
        config,
        `Прямое открытие блокнота не удалось: ${error.message}. Ищу карточку на главной странице.`
      );
    }
  }

  return openNotebookFromHome(
    config,
    page,
    publication,
    job,
    state,
    directOpenError
  );
}

async function continueCreatingVideo(config, context, publication, job, state) {
  stage = "CONTINUE_VIDEO_CREATION";
  activePage = await openNotebookWithFallback(
    config,
    context,
    publication,
    job,
    state
  );

  await waitForSourceImportReady(
    config,
    activePage,
    publication
  );

  await startVideoGeneration(
    config,
    activePage,
    publication,
    job,
    state
  );
}

async function findVideoArtifactContainer(page, config) {
  const marker = await waitForAnyVisible(
    [
      page.getByText(/Поясняющее видео/i),
      page.getByText(/\d+:\d+\s*·\s*.*видео/i),
    ],
    config.uiTimeoutMs,
    "готовый видеопересказ"
  );

  let container = marker;
  for (let level = 0; level < 8; level += 1) {
    const buttons = container.getByRole("button");
    const count = await buttons.count().catch(() => 0);
    if (count >= 2) {
      return container;
    }
    container = container.locator("xpath=..");
  }

  throw new Error("Не удалось определить контейнер готового видеопересказа.");
}

async function checkAndDownload(config, context, publication, job, state) {
  stage = "CHECK_VIDEO_STATUS";
  activePage = await openNotebookWithFallback(
    config,
    context,
    publication,
    job,
    state
  );

  const generationMarker = activePage.getByText(
    /Генерация .*видеообзора/i
  );
  const readyMarker = activePage.getByText(/Поясняющее видео/i);

  const statusMarker = await waitForAnyVisible(
    [
      generationMarker,
      readyMarker,
      activePage.getByText(/\d+:\d+\s*·\s*.*видео/i),
    ],
    config.uiTimeoutMs,
    "статус генерации или готовый видеопересказ"
  );

  const markerText = (await statusMarker.innerText().catch(() => "")).trim();

  if (/Генерация .*видеообзора/i.test(markerText)) {
    job.lastCheckedAt = new Date().toISOString();
    job.updatedAt = new Date().toISOString();
    saveState(config, state);
    log(config, `Видео ещё генерируется: ${job.notebookUrl}`);
    return "GENERATING";
  }

  const artifactContainer = await findVideoArtifactContainer(
    activePage,
    config
  );

  stage = "OPEN_VIDEO_MENU";
  const namedMenuButton = artifactContainer.getByRole("button", {
    name: /ещё|дополнитель|меню|действ/i,
  });

  if (
    (await namedMenuButton.count()) > 0 &&
    (await namedMenuButton.last().isVisible())
  ) {
    await namedMenuButton.last().click();
  } else {
    const buttons = artifactContainer.getByRole("button");
    const count = await buttons.count();
    if (count < 2) {
      throw new Error("Не найдена кнопка меню готового видео.");
    }
    await buttons.last().click();
  }

  const downloadMenuItem = await waitForAnyVisible(
    [
      activePage.getByRole("menuitem", { name: /^Скачать$/i }),
      activePage.getByText(/^Скачать$/i),
    ],
    config.uiTimeoutMs,
    'пункт меню "Скачать"'
  );

  stage = "DOWNLOAD_VIDEO";
  const downloadPromise = activePage.waitForEvent("download", {
    timeout: config.downloadTimeoutMs,
  });

  const downloadMinimizeGuard =
    process.platform === "win32" && config.minimizeBrowserWindow !== false
      ? minimizeRobotBrowserWindows(config, 8_000, true)
      : Promise.resolve({ ok: false, skipped: true });

  await downloadMenuItem.click();
  const download = await downloadPromise;

  const suggested = download.suggestedFilename();
  const extension = path.extname(suggested) || ".mp4";
  const finalPath = path.join(
    config.downloadDir,
    `ИИ-Сводка ${publication.date}${extension}`
  );

  await download.saveAs(finalPath);

  const guardResult = await downloadMinimizeGuard;
  const finalDownloadMinimizeResult =
    process.platform === "win32" && config.minimizeBrowserWindow !== false
      ? await minimizeRobotBrowserWindows(config, 5_000)
      : { ok: false, skipped: true };

  if (guardResult.ok || finalDownloadMinimizeResult.ok) {
    log(
      config,
      "Окно Яндекс.Браузера удержано свёрнутым во время скачивания видео."
    );
  } else if (!guardResult.skipped && !finalDownloadMinimizeResult.skipped) {
    log(
      config,
      `Не удалось подтвердить сворачивание окна во время скачивания: ${
        finalDownloadMinimizeResult.error ||
        guardResult.error ||
        "неизвестная ошибка"
      }. Скачивание при этом завершено.`
    );
  }

  const downloadedStats = fs.statSync(finalPath);
  const downloadedHash = await fileSha256(finalPath);

  job.status = "DONE";
  job.downloadedFile = finalPath;
  job.downloadedFilename = path.basename(finalPath);
  job.downloadedOriginalFilename = suggested;
  job.downloadedSizeBytes = downloadedStats.size;
  job.downloadedSha256 = downloadedHash;
  job.downloadedAt = new Date().toISOString();
  job.updatedAt = new Date().toISOString();
  saveState(config, state);
  writeDescription(config, publication);

  await ensureSuccessRegistryEntry(
    config,
    publication,
    job,
    state
  );

  await ensureFtpDelivery(config, publication, job, state);

  log(config, `Видео скачано: ${finalPath}`);
  return "DONE";
}

async function run() {
  const config = loadJson(CONFIG_PATH);
  if (!config) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }

  applyConfigDefaultsAndValidate(config);
  ensureDirectories(config);

  if (!acquireLock(config)) {
    console.log("Другой экземпляр worker.js уже работает. Выход.");
    return;
  }

  const logMaintenance = performLogMaintenance(config);
  log(config, "Запуск worker.js");

  await ensureTransferAccessProtected(config);

  if (logMaintenance.enabled) {
    const rotatedCount = logMaintenance.rotated.length;
    const deletedSummary =
      `${logMaintenance.deletedFiles} файл(ов), ` +
      `${formatByteCount(logMaintenance.deletedBytes)}`;
    log(
      config,
      `Ротация журналов включена: архивировано=${rotatedCount}; ` +
        `удалено=${deletedSummary}; ` +
        `worker=${config.logRotation.workerRetentionDays} дн.; ` +
        `ошибки=${config.logRotation.errorRetentionDays} дн.; ` +
        `лимит=${config.logRotation.maxFileSizeMb} МБ.`
    );
  } else {
    log(config, "Ротация журналов отключена настройкой config.json.");
  }

  const publication = await fetchTodaysPublication(config);
  if (!publication) {
    log(config, "Сегодняшний выпуск в RSS отсутствует. Работа завершена.");
    return;
  }

  log(config, `Найден сегодняшний выпуск: ${publication.url}`);

  log(config, `Читаю состояние: ${config.stateFile}`);
  const state = loadState(config);
  state.jobs ||= {};

  let job = state.jobs[publication.url];
  log(
    config,
    `Статус задания: ${job?.status || "задание ещё не создано"}`
  );

  if (job?.status === "DONE") {
    writeDescription(config, publication);

    await ensureSuccessRegistryEntry(
      config,
      publication,
      job,
      state
    );

    await ensureFtpDelivery(config, publication, job, state);

    log(
      config,
      `Выпуск уже обработан: ${job.downloadedFile || publication.url}`
    );
    return;
  }

  if (!job) {
    job = {
      date: publication.date,
      publicationUrl: publication.url,
      publicationTitle: publication.title,
      status: "NEW",
      notebookUrl: null,
      notebookTitleHint: makeNotebookTitle(config, publication),
      attempts: 0,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      lastError: null,
    };
    state.jobs[publication.url] = job;
    saveState(config, state);
  }

  job.attempts = (job.attempts || 0) + 1;
  job.updatedAt = new Date().toISOString();
  saveState(config, state);

  const context = await launchRobotBrowser(config);
  await checkAllowedIp(config, context, publication);

  if (job.status === "NEW") {
    await createNotebookAndAddSource(
      config,
      context,
      publication,
      job,
      state
    );
    await startVideoGeneration(
      config,
      activePage,
      publication,
      job,
      state
    );
    return;
  }

  if (job.status === "CREATING_VIDEO") {
    await continueCreatingVideo(
      config,
      context,
      publication,
      job,
      state
    );
    return;
  }

  if (job.status === "GENERATING") {
    await checkAndDownload(
      config,
      context,
      publication,
      job,
      state
    );
    return;
  }

  throw new Error(`Неизвестный статус задания: ${job.status}`);
}

(async () => {
  let config = null;
  let publicationUrl = null;
  let notebookUrl = null;

  try {
    config = loadJson(CONFIG_PATH);
    await run();
  } catch (error) {
    if (config) {
      let state = null;
      let activeJob = null;
      let stateReadError = null;

      try {
        state = loadState(config);
        const activeJobs = Object.values(state.jobs || {});
        activeJob = activeJobs.find((job) =>
          ["NEW", "CREATING_VIDEO", "GENERATING"].includes(job.status)
        );
      } catch (secondaryError) {
        stateReadError = secondaryError;
      }

      publicationUrl = activeJob?.publicationUrl || null;
      notebookUrl = activeJob?.notebookUrl || null;

      if (activeJob && state) {
        activeJob.lastError = error.message;
        activeJob.lastErrorAt = new Date().toISOString();
        activeJob.updatedAt = new Date().toISOString();
        saveState(config, state);
      }

      if (error.code !== "IP_NOT_ALLOWED") {
        const combinedStack = stateReadError
          ? `${error.stack || error.message}\n\nДополнительная ошибка чтения state.json:\n${stateReadError.stack || stateReadError.message}`
          : error.stack;

        await appendError(config, error.message, {
          publicationUrl,
          notebookUrl,
          stack: combinedStack,
        });
      }
    }

    console.error("");
    console.error("ОШИБКА:");
    console.error(error.stack || error.message);
    process.exitCode = error.code === "IP_NOT_ALLOWED" ? 3 : 1;
  } finally {
    if (config) {
      await closeRobotBrowser(config);
      releaseLock(config);
      try {
        log(config, `Завершение worker.js с кодом ${process.exitCode || 0}`);
      } catch {}
    }
  }
})();
