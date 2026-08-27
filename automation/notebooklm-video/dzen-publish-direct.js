"use strict";

const fs = require("fs");
const path = require("path");
const { spawn } = require("child_process");
const helpers = require("./dzen-publish.js");

const ROOT = __dirname;
const CONFIG_PATH = path.join(ROOT, "config.json");
const POLL_MS = 1500;
const PUBLISH_VERIFY_TIMEOUT_MS = 90_000;
const DIRECT_FLOW_REVISION = 2;
const RESUME_PROBE_TIMEOUT_MS = 15_000;

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
  const processed = text.includes("Загрузили и обработали видео")
    && text.includes("Готово: можно публиковать и смотреть");
  if (processed) return "ready";
  if (text.includes("Загрузили видео") && /Обрабатыва(?:ем|ется|ют)|Обработка/.test(text)) {
    return "processing";
  }
  if (/Загружаем видео|не закрывайте Дзен/i.test(text)) return "uploading";
  if (text.includes("Уже можно публиковать")) return "publish-early";
  return "waiting";
}

function publicationsUrlFromDraft(draftUrl) {
  const parsed = new URL(draftUrl);
  const match = /^\/profile\/editor\/([^/?#]+)/.exec(parsed.pathname);
  if (!match) return null;
  return `${parsed.origin}/profile/editor/${match[1]}/publications`;
}

function draftIdFromUrl(value) {
  try {
    return new URL(String(value || "")).searchParams.get("videoEditorPublicationId");
  } catch {
    return null;
  }
}

function findOpenDraftPage(context, draftUrl) {
  const wantedId = draftIdFromUrl(draftUrl);
  if (!wantedId) return null;
  return context.pages().find((page) => !page.isClosed() && draftIdFromUrl(page.url()) === wantedId) || null;
}

async function getVisible(locator) {
  const count = await locator.count();
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
  return ["passport.yandex", "sso.dzen.ru", "dzen.ru/login", "oauth.yandex", "auth?retpath"]
    .some((part) => value.includes(part));
}

async function isLoginPage(page) {
  if (isLoginUrl(page.url())) return true;
  return (await page.locator('input[id="passp-field-login"], input[name="login"], input[type="password"]').count()) > 0;
}

async function openStudio(page, config) {
  log(config, `открываю Студию: ${config.dzenUpload.studioUrl}`);
  await page.goto(config.dzenUpload.studioUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForTimeout(1200);
  if (await isLoginPage(page)) throw new Error("Сессия Дзена в роботизированном профиле отсутствует или истекла.");
  const body = await page.locator("body").innerText().catch(() => "");
  if (!body.includes(config.dzenUpload.channelName)) {
    throw new Error(`Не подтверждён нужный канал Дзена: ${config.dzenUpload.channelName}.`);
  }
  log(config, `подтверждён канал «${config.dzenUpload.channelName}».`);
}

async function openVideoUpload(page, config) {
  const addButton = page.locator('[data-testid="add-publication-button"]').first();
  await addButton.waitFor({ state: "visible", timeout: 15_000 });
  await addButton.click();
  const menuItem = await getVisible(page.getByText("Загрузить видео", { exact: true }));
  if (!menuItem) throw new Error("В меню создания не найден пункт «Загрузить видео».");
  await menuItem.click();
  await page.getByText("Публикация видео", { exact: true }).first().waitFor({ state: "visible", timeout: 15_000 });
  log(config, "открыта форма «Публикация видео». ");
}

async function uploadVideoFile(page, config, videoPath) {
  log(config, `передаю локальный MP4: ${videoPath}`);
  const timeoutMs = config.dzenUpload.processingTimeoutMs || 600_000;
  let transferError = null;

  const fileInput = page.locator('input[type="file"]').first();
  if ((await fileInput.count().catch(() => 0)) > 0) {
    log(config, "MP4 передаю напрямую через input[type=file].");
    try {
      await fileInput.setInputFiles(videoPath, { timeout: timeoutMs });
    } catch (error) {
      transferError = error;
      warn(config, `setInputFiles завершился ошибкой: ${error.message}. Продолжаю ждать videoEditorPublicationId.`);
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
      warn(config, `filechooser завершился ошибкой: ${error.message}. Продолжаю ждать videoEditorPublicationId.`);
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
      (transferError ? ` Ошибка передачи файла: ${transferError.message}` : "")
    );
  }

  const draftUrl = page.url();
  const draftId = new URL(draftUrl).searchParams.get("videoEditorPublicationId");
  log(config, `создан video draft id=${draftId}.`);
  return { draftUrl, draftId };
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
    '.ql-editor',
  ];

  let titleInput = null;
  for (const selector of titleSelectors) {
    titleInput = await getVisible(page.locator(selector));
    if (titleInput) break;
  }
  if (!titleInput) {
    const all = page.locator("textarea");
    for (let i = 0; i < await all.count(); i += 1) {
      if (await all.nth(i).isVisible().catch(() => false)) {
        titleInput = all.nth(i);
        break;
      }
    }
  }

  let descriptionInput = null;
  for (const selector of descriptionSelectors) {
    descriptionInput = await getVisible(page.locator(selector));
    if (descriptionInput) break;
  }
  if (!descriptionInput) {
    const all = page.locator("textarea");
    for (let i = 0; i < await all.count(); i += 1) {
      const candidate = all.nth(i);
      if (!(await candidate.isVisible().catch(() => false))) continue;
      if (i === 0 && titleInput) continue;
      descriptionInput = candidate;
      break;
    }
  }
  return { titleInput, descriptionInput };
}

async function waitForMetadataInputs(page, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const inputs = await findMetadataInputs(page);
    if (inputs.titleInput && inputs.descriptionInput) return inputs;
    await sleep(750);
  }
  throw new Error("Не появились поля названия и описания video draft.");
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
  const { titleInput, descriptionInput } = await waitForMetadataInputs(page, 60_000);
  let metadataChanged = false;

  const currentTitle = await readEditableText(titleInput);
  if (normalizeComparableText(currentTitle) !== normalizeComparableText(title)) {
    await setEditableOnce(titleInput, title);
    metadataChanged = true;
  }

  const currentDescription = await readEditableText(descriptionInput);
  if (!descriptionMatchesIgnoringWhitespace(currentDescription, description)) {
    await setEditableOnce(descriptionInput, description);
    metadataChanged = true;
  }

  if (metadataChanged) {
    await descriptionInput.evaluate((element) => element.blur()).catch(() => {});
    await page.waitForTimeout(1200);
  } else {
    await page.waitForTimeout(250);
  }

  const refreshed = await findMetadataInputs(page);
  const actualTitle = refreshed.titleInput ? await readEditableText(refreshed.titleInput) : "";
  const actualDescription = refreshed.descriptionInput ? await readEditableText(refreshed.descriptionInput) : "";

  if (normalizeComparableText(actualTitle) !== normalizeComparableText(title)) {
    throw new Error("Название не сохранилось после однократного заполнения формы.");
  }

  if (!descriptionMatchesIgnoringWhitespace(actualDescription, description)) {
    throw new Error(
      `Описание изменилось не только по пробелам после однократного заполнения: ` +
      `${compactComparableText(actualDescription).length}/${compactComparableText(description).length} непробельных символов.`
    );
  }

  if (normalizeComparableText(actualDescription) !== normalizeComparableText(description)) {
    warn(config, "Дзен изменил только пробельное форматирование описания. Поле больше не переписываю и не трогаю клавиатурой; продолжаю flow.");
  } else if (metadataChanged) {
    log(config, "название и описание заполнены однократно. Повторных циклов переписывания metadata нет.");
  } else {
    log(config, "название и описание уже совпадают. При resume поля не трогаю.");
  }
}

function runProcess(executable, args, timeoutMs) {
  return new Promise((resolve, reject) => {
    const child = spawn(executable, args, { windowsHide: true, stdio: ["ignore", "ignore", "pipe"] });
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
  const candidates = [job.previewFile, path.join(path.dirname(videoPath), `${path.parse(videoPath).name}.png`)].filter(Boolean);
  for (const candidate of candidates) {
    if (fs.existsSync(candidate) && fs.statSync(candidate).size > 0) return candidate;
  }

  const ffmpegPath = require("ffmpeg-static");
  if (!ffmpegPath || !fs.existsSync(ffmpegPath)) throw new Error("PNG-превью отсутствует, а ffmpeg-static недоступен.");
  const previewPath = path.join(path.dirname(videoPath), `${path.parse(videoPath).name}.png`);
  log(config, `создаю PNG-превью: ${previewPath}`);
  await runProcess(ffmpegPath, ["-y", "-ss", "0.5", "-i", videoPath, "-frames:v", "1", previewPath], 120_000);
  if (!fs.existsSync(previewPath) || fs.statSync(previewPath).size <= 0) throw new Error("ffmpeg завершился без пригодного PNG-превью.");
  job.previewFile = previewPath;
  return previewPath;
}

async function uploadCoverIfNeeded(page, config, previewPath) {
  const addCover = await getVisible(page.getByText("Добавить обложку", { exact: true }));
  if (!addCover) {
    log(config, "кнопка «Добавить обложку» не видна; считаю обложку уже установленной или недоступной в текущем состоянии формы.");
    return;
  }
  log(config, `загружаю PNG-обложку: ${previewPath}`);
  const chooserPromise = page.waitForEvent("filechooser", { timeout: 15_000 });
  await addCover.click();
  const chooser = await chooserPromise;
  await chooser.setFiles(previewPath);
  await page.waitForTimeout(1800);
}

async function findTagInput(page) {
  const candidates = [page.getByPlaceholder(/Добавьте теги/i), page.locator('input[placeholder*="тег"]'), page.locator('input[placeholder*="Тег"]')];
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
    for (let i = 0; i < await matches.count(); i += 1) {
      const candidate = matches.nth(i);
      if (!(await candidate.isVisible().catch(() => false))) continue;
      const isPopupOption = await candidate.evaluate((element) => Boolean(
        element.closest('[role="listbox"], [role="option"]')
      )).catch(() => false);
      if (!isPopupOption) {
        selected.push(tag);
        break;
      }
    }
  }
  return selected;
}

async function collectSelectedTags(page, tagInput, expectedTags) {
  if (!tagInput) return collectVisibleConfiguredTags(page, expectedTags);
  return tagInput.evaluate((input, tags) => {
    let root = input.parentElement;
    for (let i = 0; i < 8 && root; i += 1, root = root.parentElement) {
      const text = root.innerText || "";
      if (text.includes("Теги через запятую") && text.includes("Кто может комментировать")) break;
    }
    root ||= document.body;
    const lower = (value) => String(value || "").trim().toLocaleLowerCase("ru-RU");
    return tags.filter((tag) => {
      const wanted = lower(tag);
      return Array.from(root.querySelectorAll("span, div, button")).some((el) => {
        if (el === input || el.closest('[role="listbox"], [role="option"]')) return false;
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

async function ensureFiveTags(page, config, tags) {
  let tagInput = await findTagInput(page);
  let selected = await collectSelectedTags(page, tagInput, tags);

  if (tagSetComplete(selected, tags)) {
    log(config, `все 5 тегов уже подтверждены как плашки: ${tags.join(", ")}. При resume теги не трогаю.`);
    return;
  }

  if (!tagInput) {
    throw new Error(`Поле тегов не найдено и подтверждено только ${selected.length}/5 ожидаемых tag-chip.`);
  }

  for (const tag of tags) {
    if (selected.includes(tag)) continue;
    await tagInput.click();
    await tagInput.fill("");
    await tagInput.fill(tag);
    await page.waitForTimeout(250);
    await tagInput.press("Enter").catch(() => {});
    await page.waitForTimeout(400);
    selected = await collectSelectedTags(page, tagInput, tags);
    if (!selected.includes(tag)) {
      const clicked = await clickNearestTagSuggestion(page, tagInput, tag).catch(() => false);
      if (clicked) await page.waitForTimeout(400);
    }
    selected = await collectSelectedTags(page, tagInput, tags);
    if (!selected.includes(tag)) throw new Error(`Тег «${tag}» не подтвердился как отдельная плашка.`);
    log(config, `подтверждён тег: ${tag}`);
  }

  tagInput = await findTagInput(page);
  selected = await collectSelectedTags(page, tagInput, tags);
  const missing = tags.filter((tag) => !selected.includes(tag));
  if (!tagSetComplete(selected, tags) || missing.length) {
    throw new Error(`После ввода тегов подтверждено ${selected.length}/5; отсутствуют: ${missing.join(", ") || "не определено"}`);
  }
  log(config, `подтверждены все 5 тегов: ${tags.join(", ")}.`);
}

async function setCommentsBestEffort(page, config) {
  const target = config.dzenUpload.commentsAudience;
  const currentOptions = ["Все пользователи", "Подписчики", "Никто"];
  try {
    const visibleOptions = [];
    for (const text of currentOptions) {
      const locator = page.getByText(text, { exact: true });
      for (let i = 0; i < await locator.count(); i += 1) {
        if (await locator.nth(i).isVisible().catch(() => false)) visibleOptions.push({ text, locator: locator.nth(i) });
      }
    }
    if (visibleOptions.length === 1 && visibleOptions[0].text === target) {
      log(config, `комментарии уже выставлены «${target}».`);
      return true;
    }
    const opener = visibleOptions[0]?.locator;
    if (!opener) throw new Error("не найден dropdown комментариев");
    await opener.click();
    await page.waitForTimeout(250);
    const wanted = await getVisible(page.getByText(target, { exact: true }));
    if (!wanted) throw new Error(`в меню нет «${target}»`);
    await wanted.click();
    await page.waitForTimeout(300);
    log(config, `«Кто может комментировать» = «${target}».`);
    return true;
  } catch (error) {
    warn(config, `не удалось подтвердить комментарии = «${target}»: ${error.message}. Продолжаю публикацию.`);
    return false;
  }
}

async function waitForRightBottomReady(page, config, timeoutMs) {
  const deadline = Date.now() + timeoutMs;
  let lastStage = null;
  while (Date.now() < deadline) {
    const body = await page.locator("body").innerText().catch(() => "");
    const stage = processingStageFromText(body);
    if (stage !== lastStage) {
      const labels = {
        uploading: "правый нижний статус: видео загружается",
        processing: "правый нижний статус: видео загружено, идёт обработка",
        "publish-early": "Дзен уже разрешает публикацию до конца обработки; жду финальное «Готово»",
        ready: "правый нижний статус: «Загрузили и обработали видео» / «Готово: можно публиковать и смотреть»",
        waiting: "жду статус загрузки/обработки видео",
      };
      log(config, labels[stage] || stage);
      lastStage = stage;
    }
    if (stage === "ready") {
      const button = await getVisible(page.getByRole("button", { name: "Опубликовать", exact: true }));
      if (button && !(await button.isDisabled().catch(() => true))) {
        log(config, "финальный статус «Готово» подтверждён, кнопка «Опубликовать» активна.");
        return button;
      }
    }
    await page.waitForTimeout(POLL_MS);
  }
  throw new Error("За 10 минут не подтверждён финальный статус «Загрузили и обработали видео» / «Готово: можно публиковать и смотреть» с активной кнопкой «Опубликовать».");
}

async function openVideoTab(page, publicationsUrl) {
  await page.goto(publicationsUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
  await page.waitForTimeout(1200);
  const videoTab = await getVisible(page.getByText("Видео", { exact: true }));
  if (!videoTab) throw new Error("На странице публикаций не найдена вкладка «Видео».");
  await videoTab.click();
  await page.waitForTimeout(900);
}

async function countMatchingVideoRows(page, title) {
  const matches = page.getByText(title, { exact: true });
  let visibleCount = 0;
  for (let i = 0; i < await matches.count(); i += 1) {
    if (await matches.nth(i).isVisible().catch(() => false)) visibleCount += 1;
  }
  return visibleCount;
}

async function findNewestMatchingHref(page, title) {
  const matches = page.getByText(title, { exact: true });
  for (let i = 0; i < await matches.count(); i += 1) {
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

async function verifyPublishedVideo(context, config, job, dateKey) {
  const dzen = job.dzenVideo || {};
  const publicationsUrl = dzen.editorPublicationsUrl || publicationsUrlFromDraft(dzen.draftUrl);
  if (!publicationsUrl) throw new Error("Не удалось построить URL списка публикаций из draft URL.");
  const page = await context.newPage();
  const deadline = Date.now() + PUBLISH_VERIFY_TIMEOUT_MS;
  let lastCount = 0;
  try {
    while (Date.now() < deadline) {
      await openVideoTab(page, publicationsUrl);
      lastCount = await countMatchingVideoRows(page, dzen.title);
      if (lastCount > Number(dzen.baselineSameTitleVideoCount || 0)) {
        return {
          verified: true,
          count: lastCount,
          publicationsUrl,
          publishedUrl: await findNewestMatchingHref(page, dzen.title),
          screenshotPath: await saveScreenshot(page, config, dateKey, "dzen-published-video"),
        };
      }
      await page.waitForTimeout(3000);
    }
    return {
      verified: false,
      count: lastCount,
      publicationsUrl,
      publishedUrl: null,
      screenshotPath: await saveScreenshot(page, config, dateKey, "dzen-publish-unverified"),
    };
  } finally {
    await page.close().catch(() => {});
  }
}

async function archiveUnusableDraft(config, state, job, reason) {
  const dzen = job.dzenVideo || {};
  const previousDrafts = Array.isArray(dzen.previousDrafts) ? [...dzen.previousDrafts] : [];
  if (dzen.draftUrl || dzen.draftId) {
    previousDrafts.push({
      draftId: dzen.draftId || null,
      draftUrl: dzen.draftUrl || null,
      status: dzen.status || null,
      directFlowRevision: dzen.directFlowRevision || null,
      abandonedReason: reason,
      abandonedAt: new Date().toISOString(),
    });
  }
  job.dzenVideo = { previousDrafts, status: "RETRY_NEW_DRAFT", updatedAt: new Date().toISOString() };
  saveJsonAtomic(config.stateFile, state);
  warn(config, `старый draft не пригоден для продолжения (${reason}); создаю новый upload.`);
}

async function tryOpenUsableDraft(context, config, state, job) {
  const dzen = job.dzenVideo || {};
  if (!dzen.draftUrl) return null;

  if (dzen.directFlowRevision !== DIRECT_FLOW_REVISION) {
    await archiveUnusableDraft(
      config,
      state,
      job,
      `draft создан до direct-flow revision ${DIRECT_FLOW_REVISION}; безопасный resume запрещён`
    );
    return null;
  }

  const existingPage = findOpenDraftPage(context, dzen.draftUrl);
  const page = existingPage || await context.newPage();
  const createdPage = !existingPage;

  try {
    if (draftIdFromUrl(page.url()) !== dzen.draftId) {
      await page.goto(dzen.draftUrl, { waitUntil: "domcontentloaded", timeout: 60_000 });
    } else {
      await page.bringToFront();
    }

    const deadline = Date.now() + RESUME_PROBE_TIMEOUT_MS;
    while (Date.now() < deadline) {
      const chooseVideo = await getVisible(page.getByRole("button", { name: "Выбрать видео", exact: true }));
      const inputs = await findMetadataInputs(page);
      const body = await page.locator("body").innerText().catch(() => "");
      const usable = !chooseVideo && !!inputs.titleInput && !!inputs.descriptionInput && body.includes("Публикация видео");
      if (usable) {
        log(config, `продолжаю существующий video draft без новой вкладки: ${dzen.draftUrl}`);
        return page;
      }
      await page.waitForTimeout(500);
    }
  } catch {}

  if (createdPage) await page.close().catch(() => {});
  await archiveUnusableDraft(config, state, job, "saved URL did not open a populated video editor after 15-second probe");
  return null;
}

async function prepareDraftInSamePage(context, config, state, job, dateKey) {
  let page = await tryOpenUsableDraft(context, config, state, job);
  const previewPath = await ensurePreview(config, job);
  const title = helpers.buildDzenTitle(dateKey);
  const description = helpers.buildDzenDescription(dateKey, job.publicationUrl, config.dzenUpload.seriesUrl);
  const tags = helpers.normalizeTags(config.dzenUpload.tags);

  if (!page) {
    page = await context.newPage();
    await page.bringToFront();
    await openStudio(page, config);
    await openVideoUpload(page, config);
    const draft = await uploadVideoFile(page, config, job.downloadedFile);
    job.dzenVideo = {
      ...(job.dzenVideo || {}),
      status: "DRAFT_CREATED",
      directFlowRevision: DIRECT_FLOW_REVISION,
      draftId: draft.draftId,
      draftUrl: draft.draftUrl,
      videoFile: job.downloadedFile,
      coverFile: previewPath,
      title,
      description,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    };
    saveJsonAtomic(config.stateFile, state);
  }

  if (await isLoginPage(page)) throw new Error("Сессия Дзена истекла после открытия video draft.");
  await fillMetadataOnce(page, config, title, description);
  await uploadCoverIfNeeded(page, config, previewPath);
  await ensureFiveTags(page, config, tags);
  const commentsVerified = await setCommentsBestEffort(page, config);

  Object.assign(job.dzenVideo, {
    status: "FORM_FILLED",
    directFlowRevision: DIRECT_FLOW_REVISION,
    title,
    description,
    tags,
    commentsAudienceExpected: config.dzenUpload.commentsAudience,
    commentsAudienceVerified: commentsVerified,
    updatedAt: new Date().toISOString(),
  });
  saveJsonAtomic(config.stateFile, state);
  log(config, "все поля формы заполнены. Больше metadata не меняю; жду только финальный статус обработки справа внизу.");

  const publishButton = await waitForRightBottomReady(page, config, config.dzenUpload.processingTimeoutMs || 600_000);
  Object.assign(job.dzenVideo, {
    status: "READY_TO_PUBLISH",
    readyAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
  });
  saveJsonAtomic(config.stateFile, state);
  return { page, publishButton };
}

async function publishFromSamePage(context, config, state, job, dateKey, page, publishButton) {
  const publicationsUrl = publicationsUrlFromDraft(job.dzenVideo.draftUrl);
  if (!publicationsUrl) throw new Error("Не удалось построить URL страницы публикаций.");
  const verifyPage = await context.newPage();
  try {
    await openVideoTab(verifyPage, publicationsUrl);
    const baselineCount = await countMatchingVideoRows(verifyPage, job.dzenVideo.title);
    Object.assign(job.dzenVideo, {
      status: "READY_TO_PUBLISH",
      editorPublicationsUrl: publicationsUrl,
      baselineSameTitleVideoCount: baselineCount,
      publishAttemptStartedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      dryRun: false,
    });
    saveJsonAtomic(config.stateFile, state);
    log(config, `перед кликом во вкладке «Видео» найдено одноимённых публикаций: ${baselineCount}.`);

    if (!(await publishButton.isVisible().catch(() => false)) || await publishButton.isDisabled().catch(() => true)) {
      publishButton = await waitForRightBottomReady(page, config, 60_000);
    }
    await page.bringToFront();
    await publishButton.click();
    Object.assign(job.dzenVideo, {
      status: "PUBLISH_CLICKED_UNVERIFIED",
      publishClickedAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    });
    saveJsonAtomic(config.stateFile, state);
    log(config, "кнопка «Опубликовать» нажата один раз после финального статуса «Готово». Проверяю вкладку «Видео». ");
  } finally {
    await verifyPage.close().catch(() => {});
  }

  const verification = await verifyPublishedVideo(context, config, job, dateKey);
  if (!verification.verified) {
    job.dzenVideo.status = "PUBLISH_CLICKED_UNVERIFIED";
    job.dzenVideo.publishVerificationError = "Не подтверждено увеличение количества одноимённых записей во вкладке Видео за 90 секунд.";
    job.dzenVideo.publishVerificationScreenshot = verification.screenshotPath;
    job.dzenVideo.updatedAt = new Date().toISOString();
    saveJsonAtomic(config.stateFile, state);
    throw new Error("Кнопка публикации была нажата, но новая запись во вкладке «Видео» не подтверждена. Повторный клик запрещён.");
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
  log(config, `публикация подтверждена во вкладке «Видео». Совпадений заголовка: ${verification.count}.`);
  if (verification.publishedUrl) log(config, `URL опубликованной записи: ${verification.publishedUrl}`);
  return verification;
}

async function main(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (!fs.existsSync(CONFIG_PATH)) throw new Error(`Не найден config.json: ${CONFIG_PATH}`);
  const config = helpers.applyDzenConfigDefaults(loadJson(CONFIG_PATH));
  const dateKey = args.date || formatDateKey(new Date(), config.timeZone);
  const state = loadJson(config.stateFile, { jobs: {} });
  const job = helpers.findJobForDate(state, dateKey);

  if (job.dzenVideo?.status === "PUBLISHED") {
    log(config, `выпуск ${dateKey} уже PUBLISHED; повторная публикация не выполняется.`);
    return job.dzenVideo;
  }

  const connection = await connectBrowser(config);
  log(config, `прямой операторский flow подключён через ${connection.endpoint}.`);
  const context = connection.browser.contexts()[0] || await connection.browser.newContext();

  if (["PUBLISHING", "PUBLISH_CLICKED_UNVERIFIED"].includes(job.dzenVideo?.status)) {
    log(config, `повторный клик запрещён для статуса ${job.dzenVideo.status}; только перепроверяю результат.`);
    const verification = await verifyPublishedVideo(context, config, job, dateKey);
    if (!verification.verified) throw new Error("Публикация ранее могла быть нажата, но новая запись пока не подтверждена. Повторный клик не выполняется.");
    Object.assign(job.dzenVideo, {
      status: "PUBLISHED",
      publishedAt: new Date().toISOString(),
      publishedUrl: verification.publishedUrl,
      verifiedSameTitleVideoCount: verification.count,
      publishedScreenshot: verification.screenshotPath,
      videoTabVerified: true,
      updatedAt: new Date().toISOString(),
    });
    saveJsonAtomic(config.stateFile, state);
    return verification;
  }

  const prepared = await prepareDraftInSamePage(context, config, state, job, dateKey);
  return publishFromSamePage(context, config, state, job, dateKey, prepared.page, prepared.publishButton);
}

module.exports = {
  DIRECT_FLOW_REVISION,
  compactComparableText,
  descriptionMatchesIgnoringWhitespace,
  draftIdFromUrl,
  normalizeComparableText,
  parseArgs,
  processingStageFromText,
  publicationsUrlFromDraft,
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
