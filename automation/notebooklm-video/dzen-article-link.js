"use strict";

// Read-only Dzen article discovery. Does not publish, edit, upload or touch
// dzenArticleVideo state; it persists a verified same-day article URL for VK.
const fs = require("fs");
const path = require("path");
const articleVideo = require("./dzen-article-video");
// Load Playwright only for the live browser path; offline contracts need no browser.
const history = require("./history-utils");
const scheduled = require("./scheduled-worker");
const logUtils = require("./log-utils");

const ROOT = __dirname;
function validArticleUrl(value) {
  return /^https:\/\/dzen\.ru\/a\/[A-Za-z0-9_-]+$/.test(String(value || ""));
}
function verifiedArticleUrl(job) {
  const record = job && job.dzenPublishedArticle;
  return record && record.status === "VERIFIED" && validArticleUrl(record.url)
    ? record.url : null;
}
function persistVerifiedArticle(config, state, job, dateKey, articleUrl) {
  if (!job || job.date !== dateKey || !validArticleUrl(articleUrl)) {
    throw new Error("Dzen article: verified URL/date не соответствуют заданию");
  }
  const existing = verifiedArticleUrl(job);
  if (existing && existing !== articleUrl) {
    throw new Error("Dzen article: подтверждённый URL изменился; нужен ручной аудит");
  }
  const pinned = job.vkPublication && job.vkPublication.articleUrl;
  if (pinned && pinned !== articleUrl) {
    throw new Error("Dzen article: URL VK checkpoint отличается; автоматическая замена запрещена");
  }
  const now = new Date().toISOString();
  job.dzenPublishedArticle = {
    ...(job.dzenPublishedArticle || {}),
    status: "VERIFIED", url: articleUrl, verifiedAt: now,
    source: "published-studio-row-and-public-page"
  };
  job.updatedAt = now;
  history.saveStateWithRetention(config, state);
}
function getDateArg(argv) {
  if (argv.length !== 1 || !/^--date=\d{4}-\d{2}-\d{2}$/.test(argv[0])) {
    throw new Error("Использование: node dzen-article-link.js --date=YYYY-MM-DD");
  }
  const key = argv[0].slice("--date=".length);
  articleVideo.parseDateKey(key);
  return key;
}
async function main(argv = process.argv.slice(2)) {
  const dateKey = getDateArg(argv);
  const configPath = path.join(ROOT, "config.json");
  if (!fs.existsSync(configPath)) throw new Error("Не найден config.json");
  const config = JSON.parse(fs.readFileSync(configPath, "utf8").replace(/^\uFEFF/, ""));
  const today = scheduled.formatDateKey(new Date(), config.timeZone || "Europe/Moscow");
  if (dateKey !== today) throw new Error("Автоматический поиск статьи разрешён только за текущий день");
  const state = history.loadActiveState(config);
  const job = articleVideo.findJobForDate(state, dateKey);
  if (!job) throw new Error("Не найден same-day job для опубликованной статьи");
  const existing = verifiedArticleUrl(job);
  if (existing) {
    logUtils.appendRegularLine(config, "[DZEN-ARTICLE-LINK] Verified URL уже сохранён; браузер не нужен");
    return;
  }
  const logger = {
    log: value => logUtils.appendRegularLine(config, "[DZEN-ARTICLE-LINK] "+value)
  };
  let session = null;
  try {
    const browserSession = require("./browser-session");
    session = await browserSession.launchRobotBrowser(config, {log: logger.log});
    const url = await articleVideo.resolvePublishedArticleUrl(session.primaryPage, dateKey, logger);
    persistVerifiedArticle(config, state, job, dateKey, url);
    logger.log("Опубликованная статья текущего дня подтверждена: "+url);
  } finally {
    if (session) await require("./browser-session").closeRobotBrowser(session, config);
  }
}
module.exports = {validArticleUrl, verifiedArticleUrl, persistVerifiedArticle, getDateArg, main};
if (require.main === module) {
  main().catch(error => {
    console.error("DZEN-ARTICLE-LINK: "+String(error && error.message || error));
    process.exitCode = 1;
  });
}
