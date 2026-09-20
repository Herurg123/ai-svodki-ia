"use strict";

const fs = require("fs");
const path = require("path");

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp-${process.pid}-${Date.now()}`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
}

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

function stateFilePath(config) {
  return path.join(getRotationConfig(config).archiveDir, ".rotation-state.json");
}

function loadRotationState(config) {
  const filePath = stateFilePath(config);
  if (!fs.existsSync(filePath)) return { version: 1 };
  try {
    const parsed = JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
    return parsed && typeof parsed === "object" && !Array.isArray(parsed)
      ? { version: 1, ...parsed }
      : { version: 1 };
  } catch {
    return { version: 1 };
  }
}

function saveRotationState(config, state) {
  saveJsonAtomic(stateFilePath(config), { version: 1, ...state });
}

function embeddedDateKeys(filePath) {
  if (!fs.existsSync(filePath)) return [];
  let text = "";
  try {
    text = fs.readFileSync(filePath, "utf8");
  } catch {
    return [];
  }
  const out = [];
  const seen = new Set();
  const re = /\[(\d{2})\.(\d{2})\.(\d{4}),/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    const key = `${match[3]}-${match[2]}-${match[1]}`;
    if (!seen.has(key)) {
      seen.add(key);
      out.push(key);
    }
  }
  return out.sort();
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

function prepareLogForAppend(config, filePath, kind, now = new Date()) {
  const rotation = getRotationConfig(config);
  if (!rotation.enabled || !filePath) {
    return { rotated: false, enabled: rotation.enabled };
  }

  fs.mkdirSync(rotation.archiveDir, { recursive: true });
  fs.mkdirSync(path.dirname(filePath), { recursive: true });

  const today = formatDateKey(now, config.timeZone || "Europe/Moscow");
  const state = loadRotationState(config);
  const stateKey = kind === "error" ? "errorDate" : "workerDate";

  if (!fs.existsSync(filePath) || fs.statSync(filePath).size === 0) {
    state[stateKey] = today;
    saveRotationState(config, state);
    return { rotated: false, enabled: true };
  }

  const stats = fs.statSync(filePath);
  const dates = embeddedDateKeys(filePath);
  let recordedDate = state[stateKey] || null;
  let initialMixed = false;

  if (!recordedDate) {
    if (dates.length) {
      recordedDate = dates[dates.length - 1];
      initialMixed = dates.some((dateKey) => dateKey !== today);
    } else {
      recordedDate = dateKeyFromMtime(filePath, config.timeZone || "Europe/Moscow");
    }
  }

  const crossedDay = recordedDate !== today || initialMixed;
  const exceededSize = stats.size >= rotation.maxFileSizeMb * 1024 * 1024;

  if (!crossedDay && !exceededSize) {
    if (state[stateKey] !== today) {
      state[stateKey] = today;
      saveRotationState(config, state);
    }
    return { rotated: false, enabled: true };
  }

  // For a pre-existing mixed file from the old broken rotation, use the latest
  // embedded date so the migrated archive is not immediately aged out.
  const sourceDateKey = initialMixed && dates.length
    ? dates[dates.length - 1]
    : (recordedDate || today);
  const archivePath = nextArchivePath(config, kind, sourceDateKey);
  fs.renameSync(filePath, archivePath);

  state[stateKey] = today;
  saveRotationState(config, state);

  return {
    rotated: true,
    enabled: true,
    archivePath,
    sizeBytes: stats.size,
    reason: exceededSize && !crossedDay
      ? "превышение размера"
      : initialMixed
        ? "миграция смешанного журнала"
        : "смена даты",
  };
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
