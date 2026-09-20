"use strict";

const fs = require("fs");
const path = require("path");

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!filePath || !fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
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

function parseDateKey(dateKey) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateKey || ""));
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const stamp = Date.UTC(year, month - 1, day);
  const date = new Date(stamp);
  if (
    date.getUTCFullYear() !== year ||
    date.getUTCMonth() !== month - 1 ||
    date.getUTCDate() !== day
  ) return null;
  return { year, month, day, stamp };
}

function subtractDays(dateKey, days) {
  const parsed = parseDateKey(dateKey);
  if (!parsed) throw new Error(`Некорректная дата: ${dateKey}`);
  const date = new Date(parsed.stamp - days * 86400000);
  return date.toISOString().slice(0, 10);
}

function getHistoryConfig(config = {}) {
  const raw = config.historyRetention && typeof config.historyRetention === "object"
    ? config.historyRetention
    : {};
  const baseDir = config.workDir || (config.stateFile ? path.dirname(config.stateFile) : __dirname);
  return {
    enabled: raw.enabled !== false,
    activeDays: Number.isInteger(raw.activeDays) && raw.activeDays >= 1
      ? raw.activeDays
      : 14,
    archiveDir: raw.archiveDir || path.join(baseDir, "archive"),
  };
}

function cutoffDateKey(config, now = new Date()) {
  const history = getHistoryConfig(config);
  const today = formatDateKey(now, config.timeZone || "Europe/Moscow");
  return subtractDays(today, history.activeDays - 1);
}

function stateArchivePath(config, dateKey) {
  const parsed = parseDateKey(dateKey);
  if (!parsed) throw new Error(`Некорректная дата job для архива: ${dateKey}`);
  return path.join(getHistoryConfig(config).archiveDir, `state-${dateKey.slice(0, 7)}.json`);
}

function registryArchivePath(config, dateKey) {
  const parsed = parseDateKey(dateKey);
  if (!parsed) throw new Error(`Некорректная дата registry для архива: ${dateKey}`);
  return path.join(getHistoryConfig(config).archiveDir, `downloaded-videos-${dateKey.slice(0, 7)}.json`);
}

function jobHasExplicitPendingState(job) {
  if (!job || typeof job !== "object") return true;
  if (String(job.status || "") !== "DONE") return true;

  if (job.ftpLastError && !job.ftpUploadedAt) return true;

  if (job.dzenAutomation && typeof job.dzenAutomation === "object") {
    if (String(job.dzenAutomation.status || "") !== "PUBLISHED") return true;
  }

  if (job.dzenCollections && typeof job.dzenCollections === "object") {
    if (String(job.dzenCollections.status || "") !== "COMPLETE") return true;
  }

  if (job.dzenArticleVideo && typeof job.dzenArticleVideo === "object") {
    const status = String(job.dzenArticleVideo.status || "");
    if (!["COMPLETE", "SKIPPED_EXISTING"].includes(status)) return true;
  }

  return false;
}

function loadActiveState(config) {
  const state = loadJson(config.stateFile, { version: 1, jobs: {} });
  if (!state || typeof state !== "object" || Array.isArray(state)) {
    throw new Error(`Некорректный state.json: ${config.stateFile}`);
  }
  if (!state.jobs || typeof state.jobs !== "object" || Array.isArray(state.jobs)) {
    state.jobs = {};
  }
  state.version ||= 1;
  return state;
}

function mergeStateArchive(config, dateKey, entries, now = new Date()) {
  const filePath = stateArchivePath(config, dateKey);
  const archive = loadJson(filePath, { version: 1, jobs: {} }) || { version: 1, jobs: {} };
  if (!archive.jobs || typeof archive.jobs !== "object" || Array.isArray(archive.jobs)) {
    throw new Error(`Повреждён архив state: ${filePath}`);
  }
  for (const [key, job] of entries) archive.jobs[key] = job;
  archive.version ||= 1;
  archive.updatedAt = now.toISOString();
  saveJsonAtomic(filePath, archive);
  return filePath;
}

function saveStateWithRetention(config, state, now = new Date()) {
  const history = getHistoryConfig(config);
  if (!history.enabled) {
    saveJsonAtomic(config.stateFile, state);
    return { archivedJobs: 0, archiveFiles: [] };
  }

  const cutoff = cutoffDateKey(config, now);
  const activeJobs = {};
  const groups = new Map();

  for (const [key, job] of Object.entries((state && state.jobs) || {})) {
    const dateKey = job && job.date;
    const parsed = parseDateKey(dateKey);
    const eligible = parsed && dateKey < cutoff && !jobHasExplicitPendingState(job);
    if (!eligible) {
      activeJobs[key] = job;
      continue;
    }
    const month = dateKey.slice(0, 7);
    if (!groups.has(month)) groups.set(month, []);
    groups.get(month).push([key, job]);
  }

  const archiveFiles = [];
  let archivedJobs = 0;
  for (const entries of groups.values()) {
    const filePath = mergeStateArchive(config, entries[0][1].date, entries, now);
    archiveFiles.push(filePath);
    archivedJobs += entries.length;
  }

  const activeState = {
    ...(state || {}),
    version: (state && state.version) || 1,
    jobs: activeJobs,
  };
  saveJsonAtomic(config.stateFile, activeState);

  state.version = activeState.version;
  state.jobs = activeJobs;

  return { archivedJobs, archiveFiles };
}

function findJobForDateInState(state, dateKey) {
  const jobs = Object.entries((state && state.jobs) || {})
    .filter(([, job]) => job && job.date === dateKey)
    .sort((a, b) => String(b[1].updatedAt || b[1].downloadedAt || "")
      .localeCompare(String(a[1].updatedAt || a[1].downloadedAt || "")));
  if (!jobs.length) return null;
  return { key: jobs[0][0], job: jobs[0][1] };
}

function findJobForDateIncludingArchive(config, state, dateKey) {
  const active = findJobForDateInState(state, dateKey);
  if (active) return { ...active, source: "active" };

  const filePath = stateArchivePath(config, dateKey);
  const archive = loadJson(filePath, null);
  if (!archive) return null;
  const found = findJobForDateInState(archive, dateKey);
  if (!found) return null;

  state.jobs ||= {};
  state.jobs[found.key] = found.job;
  return { ...found, source: "archive", archivePath: filePath };
}

function loadActiveRegistry(config) {
  const fallback = { version: 1, videos: [] };
  const registry = loadJson(config.successRegistryFile, fallback) || fallback;
  if (!registry || typeof registry !== "object" || Array.isArray(registry)) {
    throw new Error(`Некорректный реестр скачиваний: ${config.successRegistryFile}`);
  }
  if (!Array.isArray(registry.videos)) registry.videos = [];
  registry.version ||= 1;
  return registry;
}

function mergeRegistryArchive(config, dateKey, records, now = new Date()) {
  const filePath = registryArchivePath(config, dateKey);
  const archive = loadJson(filePath, { version: 1, videos: [] }) || { version: 1, videos: [] };
  if (!Array.isArray(archive.videos)) {
    throw new Error(`Повреждён архив реестра скачиваний: ${filePath}`);
  }

  const byUrl = new Map();
  for (const record of archive.videos) {
    if (record && record.publicationUrl) byUrl.set(record.publicationUrl, record);
  }
  for (const record of records) {
    if (record && record.publicationUrl) byUrl.set(record.publicationUrl, record);
  }
  archive.version ||= 1;
  archive.videos = [...byUrl.values()];
  archive.updatedAt = now.toISOString();
  saveJsonAtomic(filePath, archive);
  return filePath;
}

function saveRegistryWithRetention(config, registry, now = new Date()) {
  const history = getHistoryConfig(config);
  if (!history.enabled) {
    saveJsonAtomic(config.successRegistryFile, registry);
    return { archivedRecords: 0, archiveFiles: [] };
  }

  const cutoff = cutoffDateKey(config, now);
  const active = [];
  const groups = new Map();

  for (const record of registry.videos || []) {
    const dateKey = record && record.publicationDate;
    const parsed = parseDateKey(dateKey);
    if (!parsed || dateKey >= cutoff) {
      active.push(record);
      continue;
    }
    const month = dateKey.slice(0, 7);
    if (!groups.has(month)) groups.set(month, []);
    groups.get(month).push(record);
  }

  const archiveFiles = [];
  let archivedRecords = 0;
  for (const records of groups.values()) {
    const filePath = mergeRegistryArchive(config, records[0].publicationDate, records, now);
    archiveFiles.push(filePath);
    archivedRecords += records.length;
  }

  registry.videos = active;
  saveJsonAtomic(config.successRegistryFile, registry);
  return { archivedRecords, archiveFiles };
}

function listRegistryArchiveFiles(config) {
  const dir = getHistoryConfig(config).archiveDir;
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter((name) => /^downloaded-videos-\d{4}-\d{2}\.json$/.test(name))
    .sort()
    .map((name) => path.join(dir, name));
}

function findRegistryRecord(config, activeRegistry, publicationUrl) {
  const activeIndex = (activeRegistry.videos || [])
    .findIndex((record) => record && record.publicationUrl === publicationUrl);
  if (activeIndex >= 0) {
    return {
      record: activeRegistry.videos[activeIndex],
      source: "active",
      registry: activeRegistry,
      index: activeIndex,
      filePath: config.successRegistryFile,
    };
  }

  for (const filePath of listRegistryArchiveFiles(config)) {
    const archive = loadJson(filePath, { version: 1, videos: [] });
    if (!archive || !Array.isArray(archive.videos)) continue;
    const index = archive.videos.findIndex(
      (record) => record && record.publicationUrl === publicationUrl
    );
    if (index >= 0) {
      return {
        record: archive.videos[index],
        source: "archive",
        registry: archive,
        index,
        filePath,
      };
    }
  }
  return null;
}

function saveRegistryLocation(location) {
  if (!location || !location.filePath || !location.registry) {
    throw new Error("Некорректное место хранения записи реестра.");
  }
  saveJsonAtomic(location.filePath, location.registry);
}

function compactJsonHistory(config, now = new Date()) {
  const history = getHistoryConfig(config);
  if (!history.enabled) {
    return {
      enabled: false,
      archivedJobs: 0,
      archivedRecords: 0,
      archiveDir: history.archiveDir,
    };
  }
  fs.mkdirSync(history.archiveDir, { recursive: true });

  const state = loadActiveState(config);
  const stateResult = saveStateWithRetention(config, state, now);

  let registryResult = { archivedRecords: 0, archiveFiles: [] };
  if (config.successRegistryFile && fs.existsSync(config.successRegistryFile)) {
    const registry = loadActiveRegistry(config);
    registryResult = saveRegistryWithRetention(config, registry, now);
  }

  return {
    enabled: true,
    activeDays: history.activeDays,
    archiveDir: history.archiveDir,
    archivedJobs: stateResult.archivedJobs,
    archivedRecords: registryResult.archivedRecords,
    stateArchiveFiles: stateResult.archiveFiles,
    registryArchiveFiles: registryResult.archiveFiles,
  };
}

module.exports = {
  compactJsonHistory,
  cutoffDateKey,
  findJobForDateIncludingArchive,
  findJobForDateInState,
  findRegistryRecord,
  formatDateKey,
  getHistoryConfig,
  jobHasExplicitPendingState,
  loadActiveRegistry,
  loadActiveState,
  parseDateKey,
  saveJsonAtomic,
  saveRegistryLocation,
  saveRegistryWithRetention,
  saveStateWithRetention,
  stateArchivePath,
  registryArchivePath,
};
