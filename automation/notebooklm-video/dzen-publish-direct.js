"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const helpers = require("./dzen-publish.js");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const POLL_MS = 1500;
const STUDIO_CHANNEL_TIMEOUT_MS = 30_000;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
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

function log(config, message) {
  const line = `[${formatTime(config.timeZone)}] DZEN: ${message}`;
  console.log(line);
  appendLine(config.regularLog, line);
}

function warn(config, message) {
  const line = `[${formatTime(config.timeZone)}] !!! DZEN: ${message}`;
  console.warn(line);
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

function buildLiveDescription(dateKey, publicationUrl, seriesUrl) {
  return [
    "Что происходит в мире Искусственного Интеллекта (ИИ, AI) и Нейросетей на текущий момент - коротенько о самом главном",
    "",
    `Без рекламы и воды на ${helpers.formatRussianNumericDate(dateKey)}:`,
    "- Глобальные новости",
    "- Новости ИИ России",
    "- Выводы и тренды",
    "",
    "Этот выпуск:",
    "",
    `- ${publicationUrl}`,
    `- ${seriesUrl}`,
  ].join("\n");
}

function normalizeComparableText(value) {
  return String(value || "")
    .normalize("NFKC")
    .replace(/[\u200B-\u200D\u2060\uFEFF]/g, "")
    .replace(/[\u00A0\u202F]/g, " ")
    .replace(/[‐‑‒–—―−]/g, "-")
    .replace(/\r\n?/g, "\n")
    .trim();
}

function compactComparableText(value) {
  return normalizeComparableText(value).replace(/\s+/g, "");
}

function descriptionMatchesIgnoringWhitespace(actual, expected) {
  return compactComparableText(actual) === compactComparableText(expected);
}

function normalizeTag(value) {
  return String(value || "").trim().toLocaleLowerCase("ru-RU");
}

function tagSetComplete(selected, expected) {
  const selectedSet = new Set((selected || []).map(normalizeTag));
  return expected.length === 5 && expected.every((tag) => selectedSet.has(normalizeTag(tag)));
}

function processingStageFromText(bodyText) {
  const text = String(bodyText || "");
  if (
    text.includes("Загрузили и обработали видео") &&
    text.includes("Готово: можно публиковать и смотреть")
  ) {
    return "ready";
  }
  if (text.includes("Загрузили видео") && /Обрабатыва(?:ем|ется|ют)|Обработка/.test(text)) {
    return "processing";
  }
  if (/Загружаем видео|не закрывайте Дзен/i.test(text)) return "uploading";
  if (text.includes("Уже можно публиковать")) return "publish-early";
  return "waiting";
}

async function getVisible(locator) {
  const count = await locator.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const candidate = locator.nth(i);
    if (await candidate.isVisible().catch(() => false)) return candidate;
  }
  return null;
}

async function connectBrowser(config) {
  const { chromium } = require("playwright");
  const endpoint = `http://${config.browserDebugHost}:${config.browserDebugPort}`;
  const deadline = Date.now() + (config.browserStartupTimeoutMs || 45_000);
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const browser = await chromium.connectOverCDP(endpoint, { timeout: 3000 });
      return { browser, endpoint };
    } catch (error) {
      lastError = error;
      await sleep(1000);
    }
  }
  throw new Error(`Не удалось подключиться к браузеру по ${endpoint}: ${lastError?.message || "CDP недоступен"}`);
}

function isLoginUrl(url) {
  const value = String(url || "").toLowerCase();
  return [
    "passport.yandex",
    "sso.dzen.ru",
    "dzen.ru/login",
    "oauth.yandex",
    "auth?retpath",
  ].some((part) => value.includes(part));
}

async function waitForExpectedStudioChannel(page, config, timeoutMs = STUDIO_CHANNEL_TIMEOUT_MS) {
  const deadline = Date.now() + timeoutMs;
  let lastBody = "";
  while (Date.now() < deadline) {
    if (isLoginUrl(page.url())) {
      throw new Error(`Дзен перенаправил на URL авторизации: ${page.url()}`);
    }
    lastBody = await page.locator("body").innerText().catch(() => "");
    if (lastBody.includes(config.dzenUpload.channelName)) return;
    await page.waitForTimeout(500);
  }
  throw new Error(
    `За ${Math.round(timeoutMs / 1000)} секунд не подтверждён канал «${config.dzenUpload.channelName}». ` +
    `URL=${page.url()}, bodyTextLength=${lastBody.length}`
  );
}

async function openStudio(page, config) {
  log(config, `открываю Студию: ${config.dzenUpload.studioUrl}`);
  await page.goto(config.dzenUpload.studioUrl, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });
  await waitForExpectedStudioChannel(page, config);
  log(config, `подтверждён канал «${config.dzenUpload.channelName}».`);
}

async function openVideoUpload(page, config) {
  const addButton = page.locator('[data-testid="add-publication-button"]').first();
  await addButton.waitFor({ state: "visible", timeout: 15_000 });
  await addButton.click();
  const uploadMenu = await getVisible(page.getByText("Загрузить видео", { exact: true }));
  if (!uploadMenu) throw new Error("Не найден пункт «Загрузить видео».");
  await uploadMenu.click();
  await page.getByText("Публикация видео", { exact: true }).first()
    .waitFor({ state: "visible", timeout: 15_000 });
  log(config, "открыта форма «Публикация видео».");
}

async function uploadVideoFile(page, config, videoPath) {
  log(config, `передаю MP4: ${videoPath}`);
  const timeoutMs = config.dzenUpload.processingTimeoutMs || 600_000;
  let transferError = null;

  const fileInput = page.locator('input[type="file"]').first();
  if ((await fileInput.count().catch(() => 0)) > 0) {
    try {
      await fileInput.setInputFiles(videoPath, { timeout: timeoutMs });
    } catch (error) {
      transferError = error;
      warn(config, `setInputFiles вернул ошибку: ${error.message}. Продолжаю ждать draft id.`);
    }
  } else {
    const button = await getVisible(page.getByRole("button", { name: "Выбрать видео", exact: true }));
    if (!button) throw new Error("Не найден input[type=file] или кнопка «Выбрать видео».");
    const chooserPromise = page.waitForEvent("filechooser", { timeout: 60_000 });
    await button.click();
    const chooser = await chooserPromise;
    try {
      await chooser.setFiles(videoPath, { timeout: timeoutMs });
    } catch (error) {
      transferError = error;
      warn(config, `filechooser вернул ошибку: ${error.message}. Продолжаю ждать draft id.`);
    }
  }

  try {
    await page.waitForFunction(
      () => new URL(window.location.href).searchParams.has("videoEditorPublicationId"),
      null,
      { timeout: timeoutMs }
    );
  } catch {
    throw new Error(
      `Дзен не создал videoEditorPublicationId за ${Math.round(timeoutMs / 1000)} секунд.` +
      (transferError ? ` Первичная ошибка передачи: ${transferError.message}` : "")
    );
  }

  const draftUrl = page.url();
  const draftId = new URL(draftUrl).searchParams.get("videoEditorPublicationId");
  log(config, `создан video draft id=${draftId}. Этот URL не используется для resume.`);
  return { draftId, draftUrl };
}

async function findMetadataInputs(page) {
  const titleSelectors = [
    'textarea[maxlength="140"]',
    'input[maxlength="140"]',
    'textarea[placeholder*="назван"]',
    'input[placeholder*="назван"]',
  ];
  const descriptionSelectors = [
    'textarea[maxlength="5000"]',
    'textarea[placeholder*="Описание"]',
    'textarea[placeholder*="описание"]',
    ".ql-editor",
  ];

  let titleInput = null;
  for (const selector of titleSelectors) {
    titleInput = await getVisible(page.locator(selector));
    if (titleInput) break;
  }

  let descriptionInput = null;
  for (const selector of descriptionSelectors) {
    descriptionInput = await getVisible(page.locator(selector));
    if (descriptionInput) break;
  }

  return { titleInput, descriptionInput };
}

async function waitForMetadataInputs(page) {
  const deadline = Date.now() + 60_000;
  while (Date.now() < deadline) {
    const inputs = await findMetadataInputs(page);
    if (inputs.titleInput && inputs.descriptionInput) return inputs;
    await page.waitForTimeout(750);
  }
  throw new Error("За 60 секунд не появились поля названия и описания.");
}

async function readEditableText(locator) {
  return locator.inputValue().catch(async () =>
    locator.innerText().catch(async () => locator.textContent().catch(() => ""))
  );
}

async function setEditableOnce(locator, value) {
  try {
    await locator.fill(value);
    return;
  } catch {}
  await locator.click({ force: true });
  await locator.press("Control+a").catch(() => {});
  await locator.press("Backspace").catch(() => {});
  await locator.pressSequentially(value, { delay: 1 });
}

async function fillMetadataOnce(page, config, title, description) {
  const { titleInput, descriptionInput } = await waitForMetadataInputs(page);

  const beforeTitle = await readEditableText(titleInput);
  const beforeDescription = await readEditableText(descriptionInput);

  if (normalizeComparableText(beforeTitle) !== normalizeComparableText(title)) {
    await setEditableOnce(titleInput, title);
  }
  if (!descriptionMatchesIgnoringWhitespace(beforeDescription, description)) {
    await setEditableOnce(descriptionInput, description);
  }

  await descriptionInput.evaluate((element) => element.blur()).catch(() => {});
  await page.waitForTimeout(1200);

  const refreshed = await findMetadataInputs(page);
  const actualTitle = refreshed.titleInput ? await readEditableText(refreshed.titleInput) : "";
  const actualDescription = refreshed.descriptionInput
    ? await readEditableText(refreshed.descriptionInput)
    : "";

  if (normalizeComparableText(actualTitle) !== normalizeComparableText(title)) {
    throw new Error("Название не подтвердилось после единственного заполнения.");
  }
  if (!descriptionMatchesIgnoringWhitespace(actualDescription, description)) {
    throw new Error("Описание после единственного заполнения отличается по непробельному содержанию.");
  }

  log(
    config,
    `metadata заполнены один раз: title=${actualTitle.length} символов, ` +
    `description=${actualDescription.length} символов. Повторного fill не будет.`
  );
}

function runProcess(executable, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, {
      windowsHide: true,
      stdio: ["ignore", "ignore", "pipe"],
    });
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`Процесс превысил тайм-аут ${timeoutMs} мс.`));
    }, timeoutMs);
    child.stderr.on("data", (chunk) => { stderr += chunk.toString("utf8"); });
    child.once("error", (error) => { clearTimeout(timer); reject(error); });
    child.once("exit", (code) => {
      clearTimeout(timer);
      if (code === 0) resolve();
      else reject(new Error(`Процесс завершился с кодом ${code}: ${stderr.slice(-1200)}`));
    });
  });
}

async function ensurePreview(config, job) {
  const videoPath = job.downloadedFile;
  const candidates = [
    job.previewFile,
    path.join(path.dirname(videoPath), `${path.parse(videoPath).name}.png`),
  ].filter(Boolean);

  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).size > 0) {
      log(config, `использую PNG-обложку: ${candidate}`);
      return candidate;
    }
  }

  const ffmpegPath = require("ffmpeg-static");
  if (!ffmpegPath || !fs.existsSync(ffmpegPath)) {
    throw new Error("PNG-обложка отсутствует, ffmpeg-static недоступен.");
  }

  const previewPath = path.join(path.dirname(videoPath), `${path.parse(videoPath).name}.png`);
  log(config, `создаю PNG-обложку: ${previewPath}`);
  await runProcess(
    ffmpegPath,
    ["-y", "-ss", "0.5", "-i", videoPath, "-frames:v", "1", previewPath],
    120_000
  );
  if (!fs.existsSync(previewPath) || fs.statSync(previewPath).size <= 0) {
    throw new Error("ffmpeg завершился без пригодной PNG-обложки.");
  }
  return previewPath;
}

async function uploadCoverOnce(page, config, previewPath) {
  const addCover = await getVisible(page.getByText("Добавить обложку", { exact: true }));
  if (!addCover) throw new Error("Не найдена кнопка «Добавить обложку».");
  const chooserPromise = page.waitForEvent("filechooser", { timeout: 15_000 });
  await addCover.click();
  const chooser = await chooserPromise;
  await chooser.setFiles(previewPath);
  await page.waitForTimeout(1800);
  log(config, "PNG-обложка передана один раз.");
}

async function findTagInput(page) {
  const candidates = [
    page.getByPlaceholder(/Добавьте теги/i),
    page.locator('input[placeholder*="тег"]'),
    page.locator('input[placeholder*="Тег"]'),
  ];
  for (const locator of candidates) {
    const visible = await getVisible(locator);
    if (visible) return visible;
  }
  return null;
}

async function collectVisibleConfiguredTags(page, expectedTags) {
  const selected = [];
  for (const tag of expectedTags) {
    const matches = page.getByText(tag, { exact: true });
    const count = await matches.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      const candidate = matches.nth(i);
      if (!(await candidate.isVisible().catch(() => false))) continue;
      const popup = await candidate.evaluate((element) => Boolean(
        element.closest('[role="listbox"], [role="option"]')
      )).catch(() => false);
      if (!popup) {
        selected.push(tag);
        break;
      }
    }
  }
  return selected;
}

async function clickNearestTagSuggestion(page, tagInput, tag) {
  const inputBox = await tagInput.boundingBox();
  if (!inputBox) return false;
  const exact = page.getByText(tag, { exact: true });
  const count = await exact.count().catch(() => 0);
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;

  for (let i = 0; i < count; i += 1) {
    const candidate = exact.nth(i);
    if (!(await candidate.isVisible().catch(() => false))) continue;
    const box = await candidate.boundingBox().catch(() => null);
    if (!box) continue;
    const distance = box.y - (inputBox.y + inputBox.height);
    if (distance >= -10 && distance <= 180 && Math.abs(distance) < bestDistance) {
      best = candidate;
      bestDistance = Math.abs(distance);
    }
  }

  if (!best) return false;
  await best.click();
  return true;
}

async function ensureFiveTagsOnce(page, config, tags) {
  let selected = await collectVisibleConfiguredTags(page, tags);

  for (const tag of tags) {
    if (selected.includes(tag)) continue;

    let tagInput = await findTagInput(page);
    if (!tagInput) {
      selected = await collectVisibleConfiguredTags(page, tags);
      if (tagSetComplete(selected, tags)) break;
      throw new Error(`Поле тегов исчезло после ${selected.length}/5 подтверждённых тегов.`);
    }

    await tagInput.click();
    await tagInput.fill("");
    await tagInput.fill(tag);
    await page.waitForTimeout(250);
    await tagInput.press("Enter").catch(() => {});
    await page.waitForTimeout(400);

    selected = await collectVisibleConfiguredTags(page, tags);
    if (!selected.includes(tag)) {
      tagInput = await findTagInput(page);
      if (tagInput) {
        const clicked = await clickNearestTagSuggestion(page, tagInput, tag).catch(() => false);
        if (clicked) await page.waitForTimeout(400);
      }
      selected = await collectVisibleConfiguredTags(page, tags);
    }

    if (!selected.includes(tag)) {
      throw new Error(`Тег «${tag}» не подтвердился как отдельная плашка.`);
    }
    log(config, `подтверждён тег: ${tag}`);
  }

  selected = await collectVisibleConfiguredTags(page, tags);
  if (!tagSetComplete(selected, tags)) {
    const missing = tags.filter((tag) => !selected.includes(tag));
    throw new Error(`Подтверждено ${selected.length}/5 тегов; отсутствуют: ${missing.join(", ")}`);
  }

  log(config, `подтверждены все 5 тегов: ${tags.join(", ")}.`);
}

async function findEnabledPublishButton(page) {
  for (const label of ["Отправить", "Опубликовать"]) {
    const button = await getVisible(page.getByRole("button", { name: label, exact: true }));
    if (button && !(await button.isDisabled().catch(() => true))) {
      return { button, label };
    }
  }
  return null;
}

async function waitUntilVideoReady(page, config, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastStage = null;

  while (Date.now() < deadline) {
    const body = await page.locator("body").innerText().catch(() => "");
    const stage = processingStageFromText(body);

    if (stage !== lastStage) {
      const messages = {
        waiting: "жду правый нижний статус загрузки видео",
        uploading: "правый нижний статус: видео загружается",
        processing: "правый нижний статус: видео загружено, идёт обработка",
        "publish-early": "Дзен уже показывает раннюю публикацию, но жду финальное «Готово»",
        ready: "правый нижний статус: «Загрузили и обработали видео» / «Готово: можно публиковать и смотреть»",
      };
      log(config, messages[stage] || stage);
      lastStage = stage;
    }

    if (stage === "ready") {
      const publish = await findEnabledPublishButton(page);
      if (publish) {
        log(config, `финальная кнопка «${publish.label}» активна.`);
        return publish;
      }
    }

    await page.waitForTimeout(POLL_MS);
  }

  throw new Error(
    `За ${Math.round(timeoutMs / 1000)} секунд не подтверждён финальный статус обработки ` +
    `с активной кнопкой публикации.`
  );
}

async function setCommentsToEveryone(page, config) {
  const target = config.dzenUpload.commentsAudience || "Все пользователи";

  const targetVisible = await getVisible(page.getByText(target, { exact: true }));
  if (targetVisible) {
    const otherVisible = [];
    for (const label of ["Подписчики", "Никто"]) {
      if (await getVisible(page.getByText(label, { exact: true }))) otherVisible.push(label);
    }
    if (otherVisible.length === 0) {
      log(config, `«Кто может комментировать» уже = «${target}».`);
      return;
    }
  }

  let opener = null;
  const label = await getVisible(page.getByText("Кто может комментировать", { exact: true }));
  if (label) {
    const candidate = label.locator("xpath=..").locator("button").first();
    if (await candidate.isVisible().catch(() => false)) opener = candidate;
  }
  if (!opener) {
    for (const current of ["Все пользователи", "Подписчики", "Никто"]) {
      const visible = await getVisible(page.getByText(current, { exact: true }));
      if (visible) {
        opener = visible;
        break;
      }
    }
  }
  if (!opener) throw new Error("Не найден selector «Кто может комментировать».");

  await opener.click();
  await page.waitForTimeout(250);
  const wanted = await getVisible(page.getByText(target, { exact: true }));
  if (!wanted) throw new Error(`После открытия dropdown не найдено «${target}».`);
  await wanted.click();
  await page.waitForTimeout(350);
  log(config, `«Кто может комментировать» выставлено = «${target}».`);
}

async function main(argv = process.argv.slice(2)) {
  const { date } = parseArgs(argv);
  if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);

  const config = helpers.applyDzenConfigDefaults(loadJson(CONFIG_PATH));
  const dateKey = date || formatDateKey(new Date(), config.timeZone);
  const state = loadJson(config.stateFile, { jobs: {} });
  const job = helpers.findJobForDate(state, dateKey);

  if (!job.downloadedFile || !fs.existsSync(job.downloadedFile)) {
    throw new Error(`Не найден локальный MP4: ${job.downloadedFile || "путь пуст"}`);
  }

  const title = helpers.buildDzenTitle(dateKey);
  const description = buildLiveDescription(
    dateKey,
    job.publicationUrl,
    config.dzenUpload.seriesUrl
  );
  const tags = helpers.normalizeTags(config.dzenUpload.tags);
  if (tags.length !== 5) throw new Error(`Требуется ровно 5 тегов, сейчас ${tags.length}.`);

  log(config, `=== START DIRECT MVP date=${dateKey} ===`);
  log(config, "режим: только новый upload; previous drafts/state resume полностью игнорируются.");
  log(config, `MP4: ${job.downloadedFile}`);

  const previewPath = await ensurePreview(config, job);
  const connection = await connectBrowser(config);
  log(config, `прямой операторский flow подключён через ${connection.endpoint}.`);

  const context = connection.browser.contexts()[0] || await connection.browser.newContext();
  const pages = context.pages().filter((page) => !page.isClosed());
  const page = pages[0] || await context.newPage();
  await page.bringToFront();

  let publishClicked = false;
  let draftId = null;

  try {
    await openStudio(page, config);
    await openVideoUpload(page, config);

    const draft = await uploadVideoFile(page, config, job.downloadedFile);
    draftId = draft.draftId;

    await fillMetadataOnce(page, config, title, description);
    await uploadCoverOnce(page, config, previewPath);
    await ensureFiveTagsOnce(page, config, tags);

    log(config, "форма подготовлена. Metadata/cover/tags больше не трогаю.");

    await waitUntilVideoReady(
      page,
      config,
      config.dzenUpload.processingTimeoutMs || 600_000
    );

    await setCommentsToEveryone(page, config);

    const publish = await findEnabledPublishButton(page);
    if (!publish) {
      throw new Error("После выбора комментариев кнопка публикации перестала быть активной.");
    }

    await page.bringToFront();
    await publish.button.click();
    publishClicked = true;

    log(
      config,
      `КЛИК ПУБЛИКАЦИИ ВЫПОЛНЕН ОДИН РАЗ: «${publish.label}», draftId=${draftId}.`
    );
    log(config, "post-click verification и повторное открытие draft в этом MVP отсутствуют.");
    await page.waitForTimeout(2000);
    log(config, `=== END DIRECT MVP SUCCESS click=true draftId=${draftId} ===`);
  } catch (error) {
    warn(
      config,
      `direct MVP завершился ошибкой; publishClicked=${publishClicked}; ` +
      `draftId=${draftId || "не создан"}; ${error.message}`
    );
    throw error;
  }
}

module.exports = {
  STUDIO_CHANNEL_TIMEOUT_MS,
  buildLiveDescription,
  compactComparableText,
  descriptionMatchesIgnoringWhitespace,
  normalizeComparableText,
  parseArgs,
  processingStageFromText,
  tagSetComplete,
};

if (require.main === module) {
  main()
    .then(() => setTimeout(() => process.exit(0), 50))
    .catch((error) => {
      const config = fs.existsSync(CONFIG_PATH)
        ? helpers.applyDzenConfigDefaults(loadJson(CONFIG_PATH))
        : { timeZone: "Europe/Moscow", regularLog: null, errorLog: null };
      fatalLog(config, `прямой операторский flow завершился ошибкой: ${error.message}`, error);
      setTimeout(() => process.exit(1), 50);
    });
}
