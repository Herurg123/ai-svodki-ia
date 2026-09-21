"use strict";

const fs = require("fs");
const path = require("path");

function formatDateKey(date, timeZone = "Europe/Moscow") {
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

function formatTime(timeZone = "Europe/Moscow") {
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

function getRotationConfig(config = {}) {
  const regularLog = config.regularLog || path.join(config.workDir || __dirname, "worker.log");
  const raw = config.logRotation && typeof config.logRotation === "object"
    ? config.logRotation
    : {};
  return {
    enabled: raw.enabled !== false,
    archiveDir: raw.archiveDir || path.join(path.dirname(regularLog), "logs"),
    workerRetentionDays: Number.isInteger(raw.workerRetentionDays) && raw.workerRetentionDays > 0
      ? raw.workerRetentionDays
      : 7,
    errorRetentionDays: Number.isInteger(raw.errorRetentionDays) && raw.errorRetentionDays > 0
      ? raw.errorRetentionDays
      : 30,
    maxFileSizeMb: typeof raw.maxFileSizeMb === "number" && Number.isFinite(raw.maxFileSizeMb) && raw.maxFileSizeMb > 0
      ? raw.maxFileSizeMb
      : 25,
  };
}

function embeddedDateEntries(filePath) {
  if (!fs.existsSync(filePath)) return [];
  let text = "";
  try {
    text = fs.readFileSync(filePath, "utf8");
  } catch {
    return [];
  }

  const out = [];
  const re = /^\[(\d{2})\.(\d{2})\.(\d{4}),/gm;
  let match;
  while ((match = re.exec(text)) !== null) {
    out.push({
      key: `${match[3]}-${match[2]}-${match[1]}`,
      index: match.index,
    });
  }
  return out;
}

function nextArchivePath(config, kind, sourceDateKey) {
  const rotation = getRotationConfig(config);
  const prefix = kind === "error" ? "error" : "worker";
  let sequence = 1;
  while (true) {
    const suffix = sequence === 1 ? "" : `-${sequence}`;
    const candidate = path.join(rotation.archiveDir, `${prefix}-${sourceDateKey}${suffix}.log`);
    if (!fs.existsSync(candidate)) return candidate;
    sequence += 1;
  }
}

function dateKeyFromMtime(filePath, timeZone) {
  return formatDateKey(fs.statSync(filePath).mtime, timeZone);
}

function replaceFileAtomic(filePath, content) {
  const tmp = `${filePath}.rotation-${process.pid}-${Date.now()}.tmp`;
  fs.writeFileSync(tmp, content, "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
}

function prepareLogForAppend(config, filePath, kind, now = new Date()) {
  const rotation = getRotationConfig(config);
  if (!rotation.enabled || !filePath) {
    return { rotated: false, enabled: rotation.enabled };
  }

  fs.mkdirSync(rotation.archiveDir, { recursive: true });
  fs.mkdirSync(path.dirname(filePath), { recursive: true });

  if (!fs.existsSync(filePath) || fs.statSync(filePath).size === 0) {
    return { rotated: false, enabled: true };
  }

  const today = formatDateKey(now, config.timeZone || "Europe/Moscow");
  const stats = fs.statSync(filePath);
  const entries = embeddedDateEntries(filePath);
  const dateKeys = entries.map((entry) => entry.key);
  const uniqueDateKeys = [...new Set(dateKeys)];
  const firstDateKey = dateKeys[0] || dateKeyFromMtime(filePath, config.timeZone || "Europe/Moscow");
  const firstTodayEntry = entries.find((entry) => entry.key === today) || null;
  const hasPast = uniqueDateKeys.some((dateKey) => dateKey < today);
  const hasToday = uniqueDateKeys.includes(today);

  const exceededSize = stats.size >= rotation.maxFileSizeMb * 1024 * 1024;

  // Day-boundary rotation is derived from timestamps already written into the
  // log, never from a mutable sidecar and never from mtime once timestamps are
  // available. This makes the operation idempotent across repeated same-day
  // scheduled runs.
  if (hasPast || (!entries.length && firstDateKey < today)) {
    // If an intentionally untouched direct writer (currently
    // dzen-browser-runner.js) has already appended one or more current-day
    // lines into yesterday's active file, keep those current-day lines active.
    // Only the prefix that belongs to older dates is archived.
    if (hasToday && firstTodayEntry && firstTodayEntry.index > 0) {
      const text = fs.readFileSync(filePath, "utf8");
      const archiveText = text.slice(0, firstTodayEntry.index);
      const activeText = text.slice(firstTodayEntry.index);
      const oldKeys = entries
        .filter((entry) => entry.index < firstTodayEntry.index && entry.key < today)
        .map((entry) => entry.key);
      const sourceDateKey = oldKeys.length
        ? oldKeys[oldKeys.length - 1]
        : firstDateKey;
      const archivePath = nextArchivePath(config, kind, sourceDateKey);
      fs.writeFileSync(archivePath, archiveText, "utf8");
      replaceFileAtomic(filePath, activeText);

      return {
        rotated: true,
        enabled: true,
        archivePath,
        sizeBytes: Buffer.byteLength(archiveText, "utf8"),
        reason: "смена даты",
        preservedCurrentDayPrefix: true,
      };
    }

    // Normal case: all parseable entries belong to an older day. Rename the
    // whole active file and start a fresh current-day log.
    const sourceDateKey = uniqueDateKeys.length
      ? uniqueDateKeys[uniqueDateKeys.length - 1]
      : firstDateKey;
    const archivePath = nextArchivePath(config, kind, sourceDateKey);
    fs.renameSync(filePath, archivePath);
    return {
      rotated: true,
      enabled: true,
      archivePath,
      sizeBytes: stats.size,
      reason: "смена даты",
    };
  }

  if (exceededSize) {
    const sourceDateKey = hasToday
      ? today
      : (uniqueDateKeys[uniqueDateKeys.length - 1] || firstDateKey || today);
    const archivePath = nextArchivePath(config, kind, sourceDateKey);
    fs.renameSync(filePath, archivePath);
    return {
      rotated: true,
      enabled: true,
      archivePath,
      sizeBytes: stats.size,
      reason: "превышение размера",
    };
  }

  return { rotated: false, enabled: true };
}

function appendLine(config, kind, line) {
  const filePath = kind === "error" ? config && config.errorLog : config && config.regularLog;
  if (!filePath) return null;
  const rotation = prepareLogForAppend(config, filePath, kind);
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  if (rotation && rotation.rotated) {
    const marker =
      `[${formatTime(config.timeZone || "Europe/Moscow")}] LOG-ROTATION: ` +
      `${rotation.reason}; архив=${rotation.archivePath}; размер=${rotation.sizeBytes} Б.`;
    fs.appendFileSync(filePath, `${marker}\r\n`, "utf8");
  }
  fs.appendFileSync(filePath, `${line}\r\n`, "utf8");
  return rotation;
}

function appendRegularLine(config, line) {
  return appendLine(config, "worker", line);
}

function appendErrorLine(config, line) {
  return appendLine(config, "error", line);
}

function archiveDateToUtc(dateKey) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateKey || ""));
  if (!match) return null;
  const value = Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  return Number.isFinite(value) ? value : null;
}

function cleanupOldLogArchives(config, now = new Date()) {
  const rotation = getRotationConfig(config);
  const result = { deletedFiles: 0, deletedBytes: 0 };
  if (!rotation.enabled || !fs.existsSync(rotation.archiveDir)) return result;

  const todayKey = formatDateKey(now, config.timeZone || "Europe/Moscow");
  const todayUtc = archiveDateToUtc(todayKey);
  const pattern = /^(worker|error)-(\d{4}-\d{2}-\d{2})(?:-\d+)?\.log$/i;

  for (const entry of fs.readdirSync(rotation.archiveDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const match = pattern.exec(entry.name);
    if (!match) continue;
    const archiveUtc = archiveDateToUtc(match[2]);
    if (archiveUtc === null || archiveUtc > todayUtc) continue;
    const retentionDays = match[1].toLowerCase() === "error"
      ? rotation.errorRetentionDays
      : rotation.workerRetentionDays;
    const ageDays = Math.floor((todayUtc - archiveUtc) / 86400000);
    if (ageDays < retentionDays) continue;
    const filePath = path.join(rotation.archiveDir, entry.name);
    const sizeBytes = fs.statSync(filePath).size;
    fs.rmSync(filePath, { force: true });
    result.deletedFiles += 1;
    result.deletedBytes += sizeBytes;
  }
  return result;
}

function performLogMaintenance(config, now = new Date()) {
  const rotation = getRotationConfig(config);
  const result = {
    enabled: rotation.enabled,
    rotated: [],
    deletedFiles: 0,
    deletedBytes: 0,
  };
  if (!rotation.enabled) return result;

  for (const [kind, filePath] of [
    ["worker", config.regularLog],
    ["error", config.errorLog],
  ]) {
    const value = prepareLogForAppend(config, filePath, kind, now);
    if (value && value.rotated) result.rotated.push(value);
  }

  const cleanup = cleanupOldLogArchives(config, now);
  result.deletedFiles = cleanup.deletedFiles;
  result.deletedBytes = cleanup.deletedBytes;
  return result;
}

module.exports = {
  appendErrorLine,
  appendRegularLine,
  cleanupOldLogArchives,
  formatDateKey,
  formatTime,
  getRotationConfig,
  performLogMaintenance,
  prepareLogForAppend,
};
