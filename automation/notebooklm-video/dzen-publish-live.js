"use strict";

const fs = require("fs");
const path = require("path");
const helpers = require("./dzen-publish.js");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(stripBom(fs.readFileSync(filePath, "utf8")));
}

function saveJsonAtomic(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  const tmp = `${filePath}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(value, null, 2), "utf8");
  fs.rmSync(filePath, { force: true });
  fs.renameSync(tmp, filePath);
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
    if (["year", "month", "day"].includes(part.type)) values[part.type] = part.value;
  }
  return `${values.year}-${values.month}-${values.day}`;
}

function appendLine(filePath, line) {
  if (!filePath) return;
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${line}\r\n`, "utf8");
}

function log(config, message) {
  const line = `[${formatTime(config.timeZone)}] ${message}`;
  console.log(line);
  appendLine(config.regularLog, line);
}

function fatalLog(config, message, error = null) {
  const suffix = error && error.stack ? `\r\n${error.stack}` : "";
  const line = `[${formatTime(config.timeZone)}] !!! DZEN: ${message}${suffix}`;
  console.error(line);
  appendLine(config.regularLog, line);
  appendLine(config.errorLog, line);
}

function parseArgs(argv) {
  const args = { date: null };
  for (const arg of argv) {
    if (arg.startsWith("--date=")) {
      args.date = arg.slice("--date=".length).trim();
      continue;
    }
    throw new Error(`Неизвестный параметр: ${arg}`);
  }
  if (args.date) helpers.formatRussianNumericDate(args.date);
  return args;
}

async function getVisible(locator) {
  const count = await locator.count();
  for (let i = 0; i < count; i += 1) {
    const candidate = locator.nth(i);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  return null;
}

function publicationsUrlFromDraft(draftUrl) {
  const parsed = new URL(draftUrl);
  const match = /^\/profile\/editor\/([^/?#]+)/.exec(parsed.pathname);
  if (!match) return null;
  return `${parsed.origin}/profile/editor/${match[1]}/publications`;
}

async function openVideoTab(page, publicationsUrl) {
  await page.goto(publicationsUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
  await page.waitForTimeout(1200);
  const videoTab = await getVisible(page.getByText("Видео", { exact: true }));
  if (!videoTab) throw new Error("На странице публикаций не найдена вкладка «Видео».");
  await videoTab.click();
  await page.waitForTimeout(1000);
}

async function countMatchingVideoRows(page, title) {
  const matches = page.getByText(title, { exact: true });
  let visibleCount = 0;
  const count = await matches.count();
  for (let i = 0; i < count; i += 1) {
    if (await matches.nth(i).isVisible().catch(() => false)) visibleCount += 1;
  }
  return visibleCount;
}

async function findNewestMatchingHref(page, title) {
  const matches = page.getByText(title, { exact: true });
  const count = await matches.count();
  for (let i = 0; i < count; i += 1) {
    const item = matches.nth(i);
    if (!(await item.isVisible().catch(() => false))) continue;
    const href = await item.evaluate((el) => {
      const anchor = el.closest("a") || el.querySelector("a") || el.parentElement?.closest("a");
      return anchor && anchor.href ? anchor.href : null;
    }).catch(() => null);
    if (href) return href;
  }
  return null;
}

async function saveScreenshot(page, config, dateKey, label) {
  fs.mkdirSync(config.screenshotsDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filePath = path.join(config.screenshotsDir, `${label}-${dateKey}-${stamp}.png`);
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

async function waitForActivePublishButton(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const body = await page.locator("body").innerText().catch(() => "");
    const ready = body.includes("Загрузили и обработали видео")
      || body.includes("Готово: можно публиковать и смотреть")
      || body.includes("Уже можно публиковать");
    const buttons = page.getByRole("button", { name: "Опубликовать", exact: true });
    const count = await buttons.count();
    for (let i = 0; i < count; i += 1) {
      const button = buttons.nth(i);
      if (ready && await button.isVisible().catch(() => false) && !(await button.isDisabled().catch(() => true))) {
        return button;
      }
    }
    await page.waitForTimeout(1500);
  }
  throw new Error("Перед финальной публикацией кнопка «Опубликовать» не стала активной.");
}

async function verifyPublishedVideo(browserSession, config, job, dateKey) {
  const dzen = job.dzenVideo || {};
  const publicationsUrl = dzen.editorPublicationsUrl || publicationsUrlFromDraft(dzen.draftUrl);
  if (!publicationsUrl) throw new Error("Не удалось построить URL списка публикаций из draft URL.");

  const page = await browserSession.newPage();
  const deadline = Date.now() + 90000;
  let lastCount = 0;
  try {
    while (Date.now() < deadline) {
      await openVideoTab(page, publicationsUrl);
      lastCount = await countMatchingVideoRows(page, dzen.title);
      if (lastCount > Number(dzen.baselineSameTitleVideoCount || 0)) {
        const publishedUrl = await findNewestMatchingHref(page, dzen.title);
        const screenshotPath = await saveScreenshot(page, config, dateKey, "dzen-published-video");
        return { verified: true, count: lastCount, publicationsUrl, publishedUrl, screenshotPath };
      }
      await page.waitForTimeout(3000);
    }
    const screenshotPath = await saveScreenshot(page, config, dateKey, "dzen-publish-unverified");
    return { verified: false, count: lastCount, publicationsUrl, publishedUrl: null, screenshotPath };
  } finally {
    await page.close().catch(() => {});
  }
}

async function publishPreparedDraft(
  config,
  state,
  job,
  dateKey,
  browserSession
) {
  const dzen = job.dzenVideo || {};
  if (!dzen.draftUrl || !dzen.title) {
    throw new Error("В state.json нет подготовленного Dzen video draft.");
  }

  log(config, `DZEN: финальная публикация через общий browser session ${browserSession.endpoint}.`);

  if (["PUBLISHING", "PUBLISH_CLICKED_UNVERIFIED"].includes(dzen.status)) {
    log(config, `DZEN: повторный клик запрещён, ранее уже начата публикация статуса ${dzen.status}. Проверяю результат.`);
    const verification = await verifyPublishedVideo(browserSession, config, job, dateKey);
    if (!verification.verified) {
      throw new Error("Ранее кнопка публикации уже могла быть нажата, но новая запись во вкладке «Видео» пока не подтверждена. Повторный клик не выполняется.");
    }
    Object.assign(job.dzenVideo, {
      status: "PUBLISHED",
      publishedAt: new Date().toISOString(),
      publishedUrl: verification.publishedUrl,
      editorPublicationsUrl: verification.publicationsUrl,
      verifiedSameTitleVideoCount: verification.count,
      publishedScreenshot: verification.screenshotPath,
      videoTabVerified: true,
      updatedAt: new Date().toISOString(),
    });
    saveJsonAtomic(config.stateFile, state);
    return verification;
  }

  const draftPage = await browserSession.newPage();
  const verifyPage = await browserSession.newPage();
  try {
    await draftPage.goto(dzen.draftUrl, { waitUntil: "domcontentloaded", timeout: 60000 });
    await draftPage.waitForTimeout(1000);
    if (!draftPage.url().includes("videoEditorPublicationId")) {
      throw new Error(`Draft URL больше не открыт как video draft: ${draftPage.url()}`);
    }

    const publicationsUrl = publicationsUrlFromDraft(dzen.draftUrl);
    if (!publicationsUrl) throw new Error("Не удалось построить URL списка публикаций.");
    await openVideoTab(verifyPage, publicationsUrl);
    const baselineCount = await countMatchingVideoRows(verifyPage, dzen.title);

    Object.assign(job.dzenVideo, {
      status: "PUBLISHING",
      editorPublicationsUrl: publicationsUrl,
      baselineSameTitleVideoCount: baselineCount,
      publishAttemptStartedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      dryRun: false,
    });
    saveJsonAtomic(config.stateFile, state);

    const publishButton = await waitForActivePublishButton(
      draftPage,
      config.dzenUpload.processingTimeoutMs || 300000
    );
    log(config, `DZEN: перед кликом во вкладке «Видео» уже найдено публикаций с тем же заголовком: ${baselineCount}.`);
    await publishButton.click();
    job.dzenVideo.publishClickedAt = new Date().toISOString();
    job.dzenVideo.status = "PUBLISH_CLICKED_UNVERIFIED";
    job.dzenVideo.updatedAt = new Date().toISOString();
    saveJsonAtomic(config.stateFile, state);
    log(config, "DZEN: кнопка «Опубликовать» нажата. Проверяю появление новой записи именно во вкладке «Видео».");
  } finally {
    await verifyPage.close().catch(() => {});
    await draftPage.close().catch(() => {});
  }

  const verification = await verifyPublishedVideo(browserSession, config, job, dateKey);
  if (!verification.verified) {
    job.dzenVideo.status = "PUBLISH_CLICKED_UNVERIFIED";
    job.dzenVideo.publishVerificationError = "Не подтверждено увеличение числа одноимённых записей во вкладке Видео за 90 секунд.";
    job.dzenVideo.publishVerificationScreenshot = verification.screenshotPath;
    job.dzenVideo.updatedAt = new Date().toISOString();
    saveJsonAtomic(config.stateFile, state);
    throw new Error("Кнопка «Опубликовать» была нажата, но новая запись во вкладке «Видео» не подтверждена за 90 секунд. Повторный клик автоматически не выполняется.");
  }

  Object.assign(job.dzenVideo, {
    status: "PUBLISHED",
    publishedAt: new Date().toISOString(),
    publishedUrl: verification.publishedUrl,
    editorPublicationsUrl: verification.publicationsUrl,
    verifiedSameTitleVideoCount: verification.count,
    publishedScreenshot: verification.screenshotPath,
    videoTabVerified: true,
    publishVerificationError: null,
    updatedAt: new Date().toISOString(),
  });
  saveJsonAtomic(config.stateFile, state);
  log(config, `DZEN: публикация подтверждена во вкладке «Видео». Совпадений заголовка: ${verification.count}.`);
  if (verification.publishedUrl) log(config, `DZEN: URL опубликованной записи: ${verification.publishedUrl}`);
  log(config, `DZEN: контрольный скриншот: ${verification.screenshotPath}`);
  return verification;
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  const config = helpers.applyDzenConfigDefaults(loadJson(CONFIG_PATH));
  const dateKey = args.date || formatDateKey(new Date(), config.timeZone);
  let state = loadJson(config.stateFile, { jobs: {} });
  let job = helpers.findJobForDate(state, dateKey);

  if (job.dzenVideo?.status === "PUBLISHED") {
    log(config, `DZEN: выпуск ${dateKey} уже помечен PUBLISHED, повторная публикация не выполняется.`);
    return job.dzenVideo;
  }

  const browserSession = helpers.createDzenBrowserSession(config);
  try {
    await browserSession.open();

    if (!["PUBLISHING", "PUBLISH_CLICKED_UNVERIFIED"].includes(job.dzenVideo?.status)) {
      log(config, `DZEN: готовлю и публикую видео за ${dateKey}. Явный операторский запуск, Планировщик не затрагивается.`);
      await helpers.prepareDzenVideoDryRun(
        config,
        state,
        job,
        dateKey,
        browserSession
      );
      state = loadJson(config.stateFile, { jobs: {} });
      job = helpers.findJobForDate(state, dateKey);
      if (job.dzenVideo?.status !== "READY_TO_PUBLISH") {
        throw new Error(`После подготовки ожидался READY_TO_PUBLISH, получено: ${job.dzenVideo?.status || "нет статуса"}`);
      }
    }

    return await publishPreparedDraft(
      config,
      state,
      job,
      dateKey,
      browserSession
    );
  } finally {
    await browserSession.close().catch(() => {});
  }
}

module.exports = {
  parseArgs,
  publicationsUrlFromDraft,
};

if (require.main === module) {
  main()
    .then(() => setTimeout(() => process.exit(0), 50))
    .catch((error) => {
      const config = fs.existsSync(CONFIG_PATH)
        ? helpers.applyDzenConfigDefaults(loadJson(CONFIG_PATH))
        : { timeZone: "Europe/Moscow", regularLog: null, errorLog: null };
      fatalLog(config, `финальная публикация завершилась ошибкой: ${error.message}`, error);
      setTimeout(() => process.exit(1), 50);
    });
}
