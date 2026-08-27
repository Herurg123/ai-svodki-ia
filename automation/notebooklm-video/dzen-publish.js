"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const { createBrowserSession } = require("./browser-session.js");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const DZEN_FILE_TRANSFER_TIMEOUT_MS = 120000;
const DZEN_DRAFT_DISCOVERY_TIMEOUT_MS = 180000;
const MONTHS_RU_GENITIVE = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
];

function stripBom(value) {
  return String(value || "").replace(/^\uFEFF/, "");
}

function loadJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) {
    return fallback;
  }
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
    if (["year", "month", "day"].includes(part.type)) {
      values[part.type] = part.value;
    }
  }
  return `${values.year}-${values.month}-${values.day}`;
}

function parseDateKey(dateKey) {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateKey || ""));
  if (!match) {
    throw new Error(`Некорректная дата выпуска: ${dateKey}`);
  }
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (month < 1 || month > 12 || day < 1 || day > 31) {
    throw new Error(`Некорректная дата выпуска: ${dateKey}`);
  }
  return { year, month, day };
}

function formatRussianLongDate(dateKey) {
  const { year, month, day } = parseDateKey(dateKey);
  return `${day} ${MONTHS_RU_GENITIVE[month - 1]} ${year}`;
}

function formatRussianNumericDate(dateKey) {
  const { year, month, day } = parseDateKey(dateKey);
  return `${String(day).padStart(2, "0")}.${String(month).padStart(2, "0")}.${year}`;
}

function buildDzenTitle(dateKey) {
  return `ИИ-Сводка на ${formatRussianLongDate(dateKey)} | Подпишись, чтоб получать свежее!`;
}

function buildDzenDescription(dateKey, publicationUrl, seriesUrl) {
  return [
    "Что происходит в мире Искусственного Интеллекта (ИИ, AI) и Нейросетей на текущий момент - коротенько о самом главном",
    "",
    `Без рекламы и воды на ${formatRussianNumericDate(dateKey)}:`,
    "- Глобальные новости",
    "- Новости ИИ России",
    "- Выводы и тренды",
    "",
    "Этот выпуск:",
    publicationUrl,
    seriesUrl,
  ].join("\n");
}

function normalizeTags(tags) {
  if (!Array.isArray(tags)) {
    throw new Error('dzenUpload.tags должен быть массивом из пяти тегов.');
  }
  const normalized = tags.map((tag) => String(tag || "").trim().replace(/^#+/, ""));
  if (normalized.length !== 5 || normalized.some((tag) => !tag)) {
    throw new Error('dzenUpload.tags должен содержать ровно пять непустых тегов.');
  }
  if (new Set(normalized.map((tag) => tag.toLocaleLowerCase("ru-RU"))).size !== 5) {
    throw new Error('dzenUpload.tags должен содержать пять разных тегов.');
  }
  return normalized;
}

function applyDzenConfigDefaults(config) {
  const dzen = config.dzenUpload && typeof config.dzenUpload === "object"
    ? { ...config.dzenUpload }
    : {};

  const defaults = {
    enabled: false,
    studioUrl: "https://dzen.ru/profile/editor/create",
    channelName: "Заметки из подпространства",
    seriesUrl: "https://dzen.ru/suite/7971db4c-2a4e-449f-b8bf-c3907486d6f1",
    tags: ["ии", "ai", "полезныесоветы", "будущее", "лайфхак"],
    commentsAudience: "Все пользователи",
    processingTimeoutMs: 300000,
  };

  for (const [key, value] of Object.entries(defaults)) {
    if (dzen[key] === undefined) {
      dzen[key] = value;
    }
  }

  if (typeof dzen.enabled !== "boolean") {
    throw new Error('dzenUpload.enabled должен быть true или false.');
  }
  for (const key of ["studioUrl", "channelName", "seriesUrl", "commentsAudience"]) {
    if (typeof dzen[key] !== "string" || !dzen[key].trim()) {
      throw new Error(`dzenUpload.${key} должен быть непустой строкой.`);
    }
  }
  for (const key of ["studioUrl", "seriesUrl"]) {
    let parsed;
    try {
      parsed = new URL(dzen[key]);
    } catch {
      throw new Error(`dzenUpload.${key} должен быть корректным http/https URL.`);
    }
    if (!["http:", "https:"].includes(parsed.protocol)) {
      throw new Error(`dzenUpload.${key} должен использовать http или https.`);
    }
  }
  dzen.tags = normalizeTags(dzen.tags);
  if (!Number.isInteger(dzen.processingTimeoutMs) || dzen.processingTimeoutMs < 30000) {
    throw new Error('dzenUpload.processingTimeoutMs должен быть целым числом не меньше 30000.');
  }

  return { ...config, dzenUpload: dzen };
}

function appendLine(filePath, line) {
  if (!filePath) {
    return;
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.appendFileSync(filePath, `${line}\r\n`, "utf8");
}

function log(config, message) {
  const line = `[${formatTime(config.timeZone)}] ${message}`;
  console.log(line);
  appendLine(config.regularLog, line);
}

function warn(config, message) {
  log(config, `!!! DZEN: ${message}`);
}

function fatalLog(config, message, error = null) {
  const suffix = error && error.stack ? `\r\n${error.stack}` : "";
  const line = `[${formatTime(config.timeZone)}] !!! DZEN: ${message}${suffix}`;
  console.error(line);
  appendLine(config.regularLog, line);
  appendLine(config.errorLog, line);
}

function safeFilePart(value) {
  return String(value || "")
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "_")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 100);
}

function parseArgs(argv) {
  const args = { dryRun: false, date: null };
  for (const arg of argv) {
    if (arg === "--dry-run") {
      args.dryRun = true;
      continue;
    }
    if (arg.startsWith("--date=")) {
      args.date = arg.slice("--date=".length).trim();
      continue;
    }
    if (arg === "--publish") {
      throw new Error(
        "Финальный автоматический клик публикации ещё не включён. Используйте --dry-run."
      );
    }
    throw new Error(`Неизвестный параметр: ${arg}`);
  }
  if (!args.dryRun) {
    throw new Error(
      "На текущем этапе разрешён только безопасный запуск с --dry-run."
    );
  }
  if (args.date) {
    parseDateKey(args.date);
  }
  return args;
}

function findJobForDate(state, dateKey) {
  const jobs = Object.values((state && state.jobs) || {}).filter(
    (job) => job && job.date === dateKey
  );
  if (!jobs.length) {
    throw new Error(`В state.json не найдено задание выпуска ${dateKey}.`);
  }
  jobs.sort((a, b) => String(b.downloadedAt || b.updatedAt || "").localeCompare(
    String(a.downloadedAt || a.updatedAt || "")
  ));
  const job = jobs[0];
  if (!job.downloadedFile || !fs.existsSync(job.downloadedFile)) {
    throw new Error(
      `Для выпуска ${dateKey} не найден локальный MP4: ${job.downloadedFile || "путь отсутствует"}`
    );
  }
  return job;
}

function runProcess(executable, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });
    let stderr = "";
    const timer = setTimeout(() => {
      child.kill();
      reject(new Error(`Процесс превысил тайм-аут ${timeoutMs} мс.`));
    }, timeoutMs);
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.once("error", (error) => {
      clearTimeout(timer);
      reject(error);
    });
    child.once("exit", (code) => {
      clearTimeout(timer);
      if (code === 0) {
        resolve();
      } else {
        reject(new Error(`Процесс завершился с кодом ${code}: ${stderr.slice(-1200)}`));
      }
    });
  });
}

async function ensurePreview(config, job) {
  const videoPath = job.downloadedFile;
  const known = [
    job.previewFile,
    path.join(path.dirname(videoPath), `${path.parse(videoPath).name}.png`),
  ].filter(Boolean);
  for (const candidate of known) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).size > 0) {
      return candidate;
    }
  }

  const ffmpegPath = require("ffmpeg-static");
  if (!ffmpegPath || !fs.existsSync(ffmpegPath)) {
    throw new Error("PNG-превью отсутствует, а ffmpeg-static недоступен.");
  }
  const previewPath = path.join(
    path.dirname(videoPath),
    `${path.parse(videoPath).name}.png`
  );
  log(config, `DZEN: создаю PNG-превью для публикации: ${previewPath}`);
  await runProcess(
    ffmpegPath,
    ["-y", "-ss", "0.5", "-i", videoPath, "-frames:v", "1", previewPath],
    120000
  );
  if (!fs.existsSync(previewPath) || fs.statSync(previewPath).size <= 0) {
    throw new Error("ffmpeg завершился без пригодного PNG-превью.");
  }
  job.previewFile = previewPath;
  job.previewSizeBytes = fs.statSync(previewPath).size;
  return previewPath;
}

function readVideoDraftFromUrl(url) {
  try {
    const parsed = new URL(url);
    const draftId = parsed.searchParams.get("videoEditorPublicationId");
    return draftId ? { draftUrl: parsed.toString(), draftId } : null;
  } catch {
    return null;
  }
}

async function waitForVideoDraft(page, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const draft = readVideoDraftFromUrl(page.url());
    if (draft) return draft;
    await page.waitForTimeout(1000);
  }
  return null;
}

async function uploadVideoFile(page, config, videoPath) {
  log(config, `DZEN: передаю локальный MP4: ${videoPath}`);
  let transferError = null;
  const button = await getVisible(
    page.getByRole("button", { name: "Выбрать видео", exact: true })
  );

  try {
    if (button) {
      const chooserPromise = page.waitForEvent("filechooser", { timeout: 15000 });
      await button.click();
      const chooser = await chooserPromise;
      await chooser.setFiles(videoPath, { timeout: DZEN_FILE_TRANSFER_TIMEOUT_MS });
    } else {
      const fileInput = page.locator('input[type="file"]').first();
      if ((await fileInput.count()) === 0) {
        throw new Error("Не найден input для загрузки MP4.");
      }
      await fileInput.setInputFiles(videoPath, { timeout: DZEN_FILE_TRANSFER_TIMEOUT_MS });
    }
  } catch (error) {
    transferError = error;
    warn(
      config,
      `передача локального MP4 вернула ошибку/timeout: ${error.message}. Новый draft не создаю; проверяю, появился ли videoEditorPublicationId у уже начатой загрузки.`
    );
  }

  const draftTimeoutMs = Math.max(
    DZEN_DRAFT_DISCOVERY_TIMEOUT_MS,
    Number(config.dzenUpload.processingTimeoutMs) || 0
  );
  const draft = await waitForVideoDraft(page, draftTimeoutMs);
  if (!draft) {
    if (transferError) {
      throw new Error(
        `После ошибки передачи MP4 videoEditorPublicationId не появился за ${draftTimeoutMs} мс: ${transferError.message}`
      );
    }
    throw new Error(
      `После передачи MP4 videoEditorPublicationId не появился за ${draftTimeoutMs} мс.`
    );
  }

  if (transferError) {
    log(
      config,
      `DZEN: несмотря на timeout/ошибку setFiles, существующая загрузка создала video draft id=${draft.draftId}; продолжаю его, повторно MP4 не отправляю.`
    );
  } else {
    log(config, `DZEN: создан video draft id=${draft.draftId}.`);
  }
  return draft;
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

async function isLoginPage(page) {
  if (isLoginUrl(page.url())) {
    return true;
  }
  return (await page.locator('input[id="passp-field-login"], input[name="login"], input[type="password"]').count()) > 0;
}

async function getVisible(locator) {
  const count = await locator.count();
  for (let i = 0; i < count; i += 1) {
    const candidate = locator.nth(i);
    if (await candidate.isVisible().catch(() => false)) {
      return candidate;
    }
  }
  return null;
}

async function openStudio(page, config) {
  log(config, `DZEN: открываю Студию: ${config.dzenUpload.studioUrl}`);
  await page.goto(config.dzenUpload.studioUrl, {
    waitUntil: "domcontentloaded",
    timeout: 60000,
  });
  await page.waitForTimeout(1500);
  if (await isLoginPage(page)) {
    throw new Error("Сессия Дзена в роботизированном профиле отсутствует или истекла.");
  }
  const bodyText = await page.locator("body").innerText().catch(() => "");
  if (!bodyText.includes(config.dzenUpload.channelName)) {
    throw new Error(
      `Не подтверждён нужный канал Дзена: ${config.dzenUpload.channelName}. Текущий URL: ${page.url()}`
    );
  }
  log(config, `DZEN: подтверждён канал «${config.dzenUpload.channelName}».`);
}

async function openVideoUpload(page, config) {
  const addButton = page.locator('[data-testid="add-publication-button"]').first();
  await addButton.waitFor({ state: "visible", timeout: 15000 });
  await addButton.click();

  const menuItem = await getVisible(
    page.getByText("Загрузить видео", { exact: true })
  );
  if (!menuItem) {
    throw new Error("В меню создания не найден пункт «Загрузить видео».");
  }
  await menuItem.click();
  await page.getByText("Публикация видео", { exact: true }).first().waitFor({
    state: "visible",
    timeout: 15000,
  });
  log(config, "DZEN: открыта форма «Публикация видео». ");
}

async function findMetadataInputs(page) {
  const titleSelectors = [
    'textarea[maxlength="140"]',
    'input[maxlength="140"]',
    'textarea[placeholder*="назван"]',
    'input[placeholder*="назван"]',
  ];
  const descSelectors = [
    'textarea[maxlength="5000"]',
    'textarea[placeholder*="Описание"]',
    'textarea[placeholder*="описание"]',
    '.ql-editor',
  ];

  let titleInput = null;
  for (const selector of titleSelectors) {
    titleInput = await getVisible(page.locator(selector));
    if (titleInput) break;
  }
  if (!titleInput) {
    const visibleTextareas = [];
    const all = page.locator("textarea");
    for (let i = 0; i < await all.count(); i += 1) {
      const item = all.nth(i);
      if (await item.isVisible().catch(() => false)) visibleTextareas.push(item);
    }
    titleInput = visibleTextareas[0] || null;
  }

  let descInput = null;
  for (const selector of descSelectors) {
    const candidate = await getVisible(page.locator(selector));
    if (candidate && (!titleInput || (await candidate.evaluate((el) => el !== document.activeElement).catch(() => true)))) {
      descInput = candidate;
      break;
    }
  }
  if (!descInput) {
    const all = page.locator("textarea");
    for (let i = 0; i < await all.count(); i += 1) {
      const item = all.nth(i);
      if (!(await item.isVisible().catch(() => false))) continue;
      const maxLength = await item.getAttribute("maxlength");
      if (maxLength === "5000" || i > 0) {
        descInput = item;
        break;
      }
    }
  }
  return { titleInput, descInput };
}

async function waitForMetadataForm(page) {
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    const inputs = await findMetadataInputs(page);
    if (inputs.titleInput && inputs.descInput) {
      return inputs;
    }
    await page.waitForTimeout(1000);
  }
  throw new Error("Форма метаданных видео не появилась за 60 секунд.");
}

async function fillTextField(locator, value) {
  await locator.click({ force: true });
  await locator.press("Control+a").catch(() => {});
  await locator.fill("").catch(async () => {
    await locator.press("Backspace").catch(() => {});
  });
  await locator.fill(value).catch(async () => {
    await locator.pressSequentially(value, { delay: 2 });
  });
}

async function fillMetadata(page, config, title, description) {
  const { titleInput, descInput } = await waitForMetadataForm(page);
  await fillTextField(titleInput, title);
  await fillTextField(descInput, description);

  const actualTitle = await titleInput.inputValue().catch(() => "");
  const actualDescription = await descInput.inputValue().catch(async () =>
    descInput.innerText().catch(() => "")
  );
  if (actualTitle.trim() !== title.trim()) {
    throw new Error(`Название не записалось полностью. Фактически: ${actualTitle}`);
  }
  if (actualDescription.trim() !== description.trim()) {
    throw new Error("Описание не записалось полностью в форму Дзена.");
  }
  log(config, `DZEN: название и описание заполнены, ${description.length} символов описания.`);
}

async function uploadCover(page, config, previewPath) {
  const addCover = await getVisible(page.getByText("Добавить обложку", { exact: true }));
  if (!addCover) {
    throw new Error("Не найдена команда «Добавить обложку».");
  }
  log(config, `DZEN: загружаю PNG-обложку: ${previewPath}`);
  const chooserPromise = page.waitForEvent("filechooser", { timeout: 15000 });
  await addCover.click();
  const chooser = await chooserPromise;
  await chooser.setFiles(previewPath, { timeout: DZEN_FILE_TRANSFER_TIMEOUT_MS });
  await page.waitForTimeout(2500);
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

async function collectSelectedTags(page, tagInput, expectedTags) {
  return tagInput.evaluate((input, tags) => {
    let root = input.parentElement;
    for (let i = 0; i < 8 && root; i += 1, root = root.parentElement) {
      const text = root.innerText || "";
      if (text.includes("Теги через запятую") && text.includes("Кто может комментировать")) {
        break;
      }
    }
    root ||= document.body;
    const lower = (value) => String(value || "").trim().toLocaleLowerCase("ru-RU");
    return tags.filter((tag) => {
      const wanted = lower(tag);
      return Array.from(root.querySelectorAll("span, div, button")).some((el) => {
        if (el === input) return false;
        if (el.closest('[role="listbox"], [role="option"]')) return false;
        const style = window.getComputedStyle(el);
        if (style.display === "none" || style.visibility === "hidden") return false;
        return lower(el.textContent) === wanted;
      });
    });
  }, expectedTags);
}

async function clickNearestTagSuggestion(page, tagInput, tag) {
  const inputBox = await tagInput.boundingBox();
  if (!inputBox) return false;
  const exact = page.getByText(tag, { exact: true });
  const count = await exact.count();
  let best = null;
  let bestDistance = Number.POSITIVE_INFINITY;
  for (let i = 0; i < count; i += 1) {
    const candidate = exact.nth(i);
    if (!(await candidate.isVisible().catch(() => false))) continue;
    const box = await candidate.boundingBox().catch(() => null);
    if (!box) continue;
    const verticalDistance = box.y - (inputBox.y + inputBox.height);
    if (verticalDistance >= -10 && verticalDistance <= 180 && Math.abs(verticalDistance) < bestDistance) {
      best = candidate;
      bestDistance = Math.abs(verticalDistance);
    }
  }
  if (!best) return false;
  await best.click();
  return true;
}

async function ensureTag(page, tagInput, tag, expectedSoFar) {
  await tagInput.click();
  await tagInput.fill("");
  await tagInput.fill(tag);
  await page.waitForTimeout(400);
  await tagInput.press("Enter");
  await page.waitForTimeout(500);

  let selected = await collectSelectedTags(page, tagInput, expectedSoFar);
  let currentValue = await tagInput.inputValue().catch(() => "");
  if (selected.includes(tag) && !currentValue.trim()) {
    return;
  }

  const clicked = await clickNearestTagSuggestion(page, tagInput, tag).catch(() => false);
  if (clicked) {
    await page.waitForTimeout(500);
  } else {
    await tagInput.press("Enter").catch(() => {});
    await page.waitForTimeout(500);
  }

  selected = await collectSelectedTags(page, tagInput, expectedSoFar);
  currentValue = await tagInput.inputValue().catch(() => "");
  if (!selected.includes(tag) || currentValue.trim()) {
    throw new Error(`Тег «${tag}» не подтвердился как отдельная плашка.`);
  }
}

async function setFiveTags(page, config, tags) {
  const tagInput = await findTagInput(page);
  if (!tagInput) {
    throw new Error("Поле «Теги через запятую» не найдено.");
  }
  for (let i = 0; i < tags.length; i += 1) {
    const expectedSoFar = tags.slice(0, i + 1);
    await ensureTag(page, tagInput, tags[i], expectedSoFar);
    log(config, `DZEN: подтверждён тег ${i + 1}/5: ${tags[i]}`);
  }
  const selected = await collectSelectedTags(page, tagInput, tags);
  const missing = tags.filter((tag) => !selected.includes(tag));
  if (selected.length !== 5 || missing.length) {
    throw new Error(
      `После ввода тегов подтверждено ${selected.length}/5; отсутствуют: ${missing.join(", ") || "не определено"}`
    );
  }
  log(config, `DZEN: подтверждены все 5 тегов: ${tags.join(", ")}.`);
}

async function setCommentsAudience(page, config) {
  const target = config.dzenUpload.commentsAudience;
  const currentOptions = ["Все пользователи", "Подписчики", "Никто"];

  try {
    const currentLocators = [];
    for (const text of currentOptions) {
      const exact = page.getByText(text, { exact: true });
      const count = await exact.count();
      for (let i = 0; i < count; i += 1) {
        const candidate = exact.nth(i);
        if (await candidate.isVisible().catch(() => false)) {
          currentLocators.push({ text, candidate });
        }
      }
    }
    const already = currentLocators.find((item) => item.text === target);
    if (already && currentLocators.length === 1) {
      log(config, `DZEN: комментарии уже выставлены «${target}».`);
      return { ok: true, actual: target };
    }

    const opener = currentLocators[0]?.candidate || null;
    if (!opener) {
      throw new Error("не найден текущий dropdown комментариев");
    }
    await opener.click();
    await page.waitForTimeout(300);

    const wanted = await getVisible(page.getByText(target, { exact: true }));
    if (!wanted) {
      throw new Error(`в меню нет пункта «${target}»`);
    }
    await wanted.click();
    await page.waitForTimeout(400);

    const visibleTarget = await getVisible(page.getByText(target, { exact: true }));
    if (!visibleTarget) {
      throw new Error(`после выбора не видно значения «${target}»`);
    }
    log(config, `DZEN: «Кто может комментировать» = «${target}».`);
    return { ok: true, actual: target };
  } catch (error) {
    let actual = "не определено";
    for (const text of currentOptions) {
      if (await getVisible(page.getByText(text, { exact: true }))) {
        actual = text;
        break;
      }
    }
    warn(
      config,
      `не удалось выставить комментарии = «${target}»; текущее значение = «${actual}». Продолжаем подготовку публикации.`
    );
    return { ok: false, actual, error: error.message };
  }
}

async function waitForVideoReady(page, config) {
  const deadline = Date.now() + config.dzenUpload.processingTimeoutMs;
  while (Date.now() < deadline) {
    const bodyText = await page.locator("body").innerText().catch(() => "");
    const processed = bodyText.includes("Загрузили и обработали видео")
      || bodyText.includes("Готово: можно публиковать и смотреть")
      || bodyText.includes("Уже можно публиковать");
    const publishButtons = page.getByRole("button", { name: "Опубликовать", exact: true });
    const count = await publishButtons.count();
    for (let i = 0; i < count; i += 1) {
      const button = publishButtons.nth(i);
      if (
        processed
        && await button.isVisible().catch(() => false)
        && !(await button.isDisabled().catch(() => true))
      ) {
        log(config, "DZEN: видео обработано, кнопка «Опубликовать» активна.");
        return button;
      }
    }
    await page.waitForTimeout(2000);
  }
  throw new Error("Видео не перешло в готовое к публикации состояние за установленный тайм-аут.");
}

async function saveScreenshot(page, config, dateKey, label) {
  fs.mkdirSync(config.screenshotsDir, { recursive: true });
  const stamp = new Date().toISOString().replace(/[:.]/g, "-");
  const filePath = path.join(
    config.screenshotsDir,
    `${safeFilePart(label)}-${dateKey}-${stamp}.png`
  );
  await page.screenshot({ path: filePath, fullPage: true });
  return filePath;
}

function createDzenBrowserSession(config) {
  return createBrowserSession(config, {
    allowExisting: true,
    closeAttachedBrowser: false,
    log: (message) => log(config, `DZEN: ${message}`),
  });
}

async function prepareDzenVideoDryRun(
  config,
  state,
  job,
  dateKey,
  browserSession = null
) {
  const videoPath = job.downloadedFile;
  const previewPath = await ensurePreview(config, job);
  saveJsonAtomic(config.stateFile, state);

  const title = buildDzenTitle(dateKey);
  const description = buildDzenDescription(
    dateKey,
    job.publicationUrl,
    config.dzenUpload.seriesUrl
  );
  const tags = normalizeTags(config.dzenUpload.tags);

  const session = browserSession || createDzenBrowserSession(config);
  const ownsSession = !browserSession;
  let page;

  try {
    await session.open();
    const existingDraft = job.dzenVideo && job.dzenVideo.draftUrl;

    if (existingDraft && job.dzenVideo.status === "READY_TO_PUBLISH") {
      page = await session.newPage();
      await page.goto(existingDraft, { waitUntil: "domcontentloaded", timeout: 60000 });
      await waitForVideoReady(page, config);
      const screenshotPath = await saveScreenshot(page, config, dateKey, "dzen-ready-repeat");
      log(config, `DZEN: draft уже был подготовлен ранее, новый draft не создаю: ${existingDraft}`);
      log(config, `DZEN: повторный диагностический скриншот: ${screenshotPath}`);
      return {
        page,
        draftUrl: existingDraft,
        screenshotPath,
        comments: {
          ok: job.dzenVideo.commentsAudienceVerified === true,
          actual: job.dzenVideo.commentsAudienceActual || "не определено",
        },
      };
    }

    if (existingDraft && job.dzenVideo.status !== "PUBLISHED") {
      page = await session.newPage();
      await page.goto(existingDraft, { waitUntil: "domcontentloaded", timeout: 60000 });
      log(config, `DZEN: продолжаю существующий video draft: ${existingDraft}`);
    } else {
      page = await session.newPage();
      await openStudio(page, config);
      await openVideoUpload(page, config);
      const draft = await uploadVideoFile(page, config, videoPath);
      job.dzenVideo = {
        ...(job.dzenVideo || {}),
        status: "DRAFT_CREATED",
        draftId: draft.draftId,
        draftUrl: draft.draftUrl,
        videoFile: videoPath,
        coverFile: previewPath,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
      };
      saveJsonAtomic(config.stateFile, state);
    }

    if (await isLoginPage(page)) {
      throw new Error("Сессия Дзена истекла после открытия video draft.");
    }
    await fillMetadata(page, config, title, description);
    await uploadCover(page, config, previewPath);
    await setFiveTags(page, config, tags);
    const comments = await setCommentsAudience(page, config);
    await waitForVideoReady(page, config);

    const screenshotPath = await saveScreenshot(page, config, dateKey, "dzen-ready");
    const draftUrl = page.url();
    const draftId = new URL(draftUrl).searchParams.get("videoEditorPublicationId")
      || job.dzenVideo?.draftId
      || null;

    job.dzenVideo = {
      ...(job.dzenVideo || {}),
      status: "READY_TO_PUBLISH",
      draftId,
      draftUrl,
      videoFile: videoPath,
      coverFile: previewPath,
      title,
      description,
      tags,
      commentsAudienceExpected: config.dzenUpload.commentsAudience,
      commentsAudienceActual: comments.actual,
      commentsAudienceVerified: comments.ok,
      readyAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      dryRun: true,
      readyScreenshot: screenshotPath,
    };
    saveJsonAtomic(config.stateFile, state);

    log(config, `DZEN: dry-run готов. Финальная кнопка НЕ нажата. Draft: ${draftUrl}`);
    log(config, `DZEN: диагностический скриншот: ${screenshotPath}`);
    return { page, draftUrl, screenshotPath, comments };
  } finally {
    if (ownsSession) {
      await session.close().catch(() => {});
    }
  }
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (!fs.existsSync(CONFIG_PATH)) {
    throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  }
  const config = applyDzenConfigDefaults(loadJson(CONFIG_PATH));
  if (!config.stateFile || !config.timeZone || !config.regularLog || !config.errorLog) {
    throw new Error("В config.json отсутствуют обязательные общие пути/state/timeZone.");
  }
  const dateKey = args.date || formatDateKey(new Date(), config.timeZone);
  const state = loadJson(config.stateFile, { jobs: {} });
  const job = findJobForDate(state, dateKey);

  log(config, `DZEN: запускаю безопасную подготовку видео за ${dateKey}.`);
  if (config.dzenUpload.enabled !== true) {
    log(config, "DZEN: dzenUpload.enabled=false, но явный --dry-run разрешён как операторский тест; Планировщик не затрагивается.");
  }

  try {
    return await prepareDzenVideoDryRun(config, state, job, dateKey);
  } catch (error) {
    fatalLog(config, `dry-run завершился ошибкой: ${error.message}`, error);
    throw error;
  }
}

module.exports = {
  applyDzenConfigDefaults,
  buildDzenDescription,
  buildDzenTitle,
  createDzenBrowserSession,
  findJobForDate,
  formatRussianLongDate,
  formatRussianNumericDate,
  normalizeTags,
  parseArgs,
  prepareDzenVideoDryRun,
  readVideoDraftFromUrl,
};

if (require.main === module) {
  main()
    .then(() => {
      setTimeout(() => process.exit(0), 50);
    })
    .catch(() => {
      setTimeout(() => process.exit(1), 50);
    });
}
