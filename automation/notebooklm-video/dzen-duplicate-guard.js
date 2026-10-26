"use strict";

const helpers = require("./dzen-publish.js");

const PUBLICATIONS_URL = "https://dzen.ru/profile/editor/rybv/publications";
const VIDEO_FILTER_SELECTOR = 'input[type="radio"][aria-label="Видео"]';
const VIDEO_FILTER_TIMEOUT_MS = 20_000;
const TITLE_SEARCH_TIMEOUT_MS = 10_000;

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

function resolveDateKey(childArgs, timeZone) {
  const dateArg = (childArgs || []).find((arg) => String(arg).startsWith("--date="));
  const dateKey = dateArg
    ? String(dateArg).slice("--date=".length).trim()
    : formatDateKey(new Date(), timeZone || "Europe/Moscow");
  helpers.formatRussianNumericDate(dateKey);
  return dateKey;
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

function titlePrefixForDuplicateCheck(title) {
  return String(title || "").split(" | ")[0].trim();
}

function extractPublishedVideoId(url) {
  const match = /^https:\/\/dzen\.ru\/video\/watch\/([a-f0-9]{24})(?:[/?#]|$)/i.exec(String(url || ""));
  return match ? match[1].toLowerCase() : null;
}

function pinnedPublishedIdentity(result, expectedId) {
  if (!result || !result.existing || !/^[a-f0-9]{24}$/i.test(String(expectedId || ""))) {
    return "UNKNOWN";
  }
  const actualId = extractPublishedVideoId(result.publishedVideoUrl);
  if (!actualId) return "UNKNOWN";
  return actualId === String(expectedId).toLowerCase() ? "MATCH" : "MISMATCH";
}

// The published row already contains a public /video/watch/<ID> link in the
// Studio UI (observed by dzen-article-video.js in the same pipeline).
// Extract ONLY from the matching title's small, visible row. Never scrape
// arbitrary links from the page or accept a same-title row without identity.
async function findVisiblePublishedVideo(page, titlePrefix) {
  const matches = page.getByText(titlePrefix, { exact: false });
  const count = await matches.count().catch(() => 0);
  for (let i = 0; i < count; i += 1) {
    const candidate = matches.nth(i);
    if (!(await candidate.isVisible().catch(() => false))) continue;
    const text = String(
      await candidate.innerText().catch(async () => candidate.textContent().catch(() => ""))
    ).replace(/\s+/g, " ").trim();
    if (!text.includes(titlePrefix)) continue;
    const publicVideoUrl = await candidate.evaluate((element, expectedPrefix) => {
      for (let row = element, depth = 0; row && depth < 16; row = row.parentElement, depth += 1) {
        const bounds = row.getBoundingClientRect();
        const rowText = String(row.innerText || row.textContent || "").replace(/\s+/g, " ").trim();
        if (bounds.width < 300 || bounds.height < 35 || bounds.height > 280 ||
            !rowText.includes(expectedPrefix) || rowText.length > 650) continue;
        const links = new Set();
        for (const node of [row, ...row.querySelectorAll("a[href], [href], [data-href]")]) {
          for (const raw of [node.href, node.getAttribute?.("href"), node.getAttribute?.("data-href")]) {
            if (!raw) continue;
            try {
              const href = new URL(String(raw), location.href).href;
              if (/^https:\/\/dzen\.ru\/video\/watch\/[a-f0-9]{24}(?:[/?#]|$)/i.test(href)) links.add(href);
            } catch {}
          }
        }
        // A row with several different video identities is ambiguous.
        const ids = new Set([...links].map((href) => href.match(/\/video\/watch\/([a-f0-9]{24})/i)?.[1]?.toLowerCase()));
        if (ids.size === 1 && links.size > 0) return [...links][0];
      }
      return null;
    }, titlePrefix).catch(() => null);
    return { foundText: text, publishedVideoUrl: publicVideoUrl,
      publishedVideoId: extractPublishedVideoId(publicVideoUrl) };
  }
  return null;
}

async function findVisibleTitlePrefix(page, titlePrefix) {
  const result = await findVisiblePublishedVideo(page, titlePrefix);
  return result ? result.foundText : null;
}

async function checkBeforeUpload(page, config, childArgs, log = () => {}) {
  const dateKey = resolveDateKey(childArgs, config && config.timeZone);
  const fullTitle = helpers.buildDzenTitle(dateKey);
  const titlePrefix = titlePrefixForDuplicateCheck(fullTitle);

  log(`до upload проверяю существующее Видео по prefix: «${titlePrefix}».`);
  log(`открываю список публикаций: ${PUBLICATIONS_URL}`);

  await page.goto(PUBLICATIONS_URL, {
    waitUntil: "domcontentloaded",
    timeout: 60_000,
  });

  if (isLoginUrl(page.url())) {
    throw new Error(
      `ОШИБКА АВТОРИЗАЦИИ: Дзен перенаправил на URL авторизации при duplicate-check: ${page.url()}`
    );
  }

  const videoRadioDeadline = Date.now() + VIDEO_FILTER_TIMEOUT_MS;
  let videoRadio = null;

  while (Date.now() < videoRadioDeadline) {
    if (isLoginUrl(page.url())) {
      throw new Error(
        `ОШИБКА АВТОРИЗАЦИИ: Дзен перенаправил на URL авторизации при duplicate-check: ${page.url()}`
      );
    }

    const candidate = page.locator(VIDEO_FILTER_SELECTOR).first();
    if ((await candidate.count().catch(() => 0)) > 0) {
      videoRadio = candidate;
      break;
    }
    await page.waitForTimeout(500);
  }

  if (!videoRadio) {
    throw new Error(
      "Перед upload не найден radio-фильтр «Видео» " +
      `(selector=${VIDEO_FILTER_SELECTOR}); duplicate-check не подтверждён.`
    );
  }

  log("нашёл radio-фильтр «Видео»; переключаю его напрямую, без клика по текстовому div.");

  // В подтверждённом Dzen UI pointer events принимает именно radio-input,
  // лежащий поверх визуального <div>Видео</div>. Клик по текстовому слою приводит
  // к повторным scrollIntoView/retry и 30-секундному Playwright timeout.
  await videoRadio.evaluate((element) => element.click());

  const checkedDeadline = Date.now() + 5_000;
  while (Date.now() < checkedDeadline) {
    if (await videoRadio.isChecked().catch(() => false)) break;
    await page.waitForTimeout(250);
  }

  if (!(await videoRadio.isChecked().catch(() => false))) {
    throw new Error(
      "Radio-фильтр «Видео» найден и нажат, но состояние checked=true не подтвердилось; " +
      "upload запрещён."
    );
  }

  log("фильтр «Видео» подтверждён: checked=true. Проверяю видимые заголовки.");
  await page.waitForTimeout(800);

  const titleDeadline = Date.now() + TITLE_SEARCH_TIMEOUT_MS;
  while (Date.now() < titleDeadline) {
    if (isLoginUrl(page.url())) {
      throw new Error(
        `ОШИБКА АВТОРИЗАЦИИ: Дзен перенаправил на URL авторизации при duplicate-check: ${page.url()}`
      );
    }

    const found = await findVisiblePublishedVideo(page, titlePrefix);
    if (found) {
      const { foundText, publishedVideoUrl, publishedVideoId } = found;
      log(`ВИДЕО УЖЕ ЕСТЬ: найден заголовок «${foundText}».`);
      if (publishedVideoId) log(`В строке опубликованного видео подтверждён public ID=${publishedVideoId}.`);
      else log("Публичный video ID в строке не получен; заголовок сам по себе не подтверждает pinned draft.");
      log("новый upload, draft и publish click не выполняю.");
      log(`=== DZEN SKIP existing-video=true date=${dateKey} ===`);
      return {
        existing: true,
        dateKey,
        fullTitle,
        titlePrefix,
        foundText,
        publishedVideoUrl,
        publishedVideoId,
      };
    }
    await page.waitForTimeout(500);
  }

  log(`в видимой части списка «Видео» prefix «${titlePrefix}» не найден; разрешаю новый upload.`);
  return {
    existing: false,
    dateKey,
    fullTitle,
    titlePrefix,
    foundText: null,
    publishedVideoUrl: null,
    publishedVideoId: null,
  };
}


function summarizeDraftInspection({ url, bodyText, draftId, titleText, expectedTitle, modalVisible }) {
  const address = String(url || "");
  const query = new URL(address, PUBLICATIONS_URL).searchParams;
  const correctId = query.get("videoEditorPublicationId") === draftId;
  const expected = String(expectedTitle || "").trim();
  const actual = String(titleText || "").replace(/\s+/g, " ").trim();
  if (correctId && modalVisible && actual === expected) return "PRESENT";
  // Absence is NOT inferred from a failed selector or network/partial load.
  if (!modalVisible && !correctId &&
      query.get("state") === "draft" && /Черновики/.test(bodyText || "")) {
    return "ABSENT";
  }
  return "UNKNOWN";
}

async function inspectPinnedDraft(page, draftId, expectedTitle, log = () => {}) {
  if (!/^[0-9a-f]{24}$/i.test(String(draftId || ""))) {
    throw new Error("Для проверки черновика необходим подтверждённый 24-символьный draftId.");
  }
  const url = `${PUBLICATIONS_URL}?state=draft&videoEditorPublicationId=${draftId}`;
  log(`Проверяю именно черновик id=${draftId} (read-only).`);
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 60_000 });
  if (isLoginUrl(page.url())) throw new Error("Дзен требует авторизацию при проверке черновика.");
  const modal = page.getByText("Публикация видео", { exact: true }).first();
  const deadline = Date.now() + 12_000;
  let observed = "UNKNOWN";
  while (Date.now() < deadline) {
    const modalVisible = await modal.isVisible().catch(() => false);
    let titleText = "";
    if (modalVisible) {
      const title = page.locator('textarea[maxlength="140"],input[maxlength="140"]').first();
      titleText = await title.inputValue().catch(() => "");
    }
    const bodyText = await page.locator("body").innerText({ timeout: 1500 }).catch(() => "");
    observed = summarizeDraftInspection({
      url: page.url(), bodyText, draftId, titleText, expectedTitle, modalVisible,
    });
    if (observed === "PRESENT") break;
    if (observed === "ABSENT") {
      // A secondary read after the UI settles avoids treating hydration as absence.
      await page.waitForTimeout(1200);
      const repeatedModal = await modal.isVisible().catch(() => false);
      if (!repeatedModal && page.url().includes("state=draft") &&
          !page.url().includes(`videoEditorPublicationId=${draftId}`)) break;
      observed = "UNKNOWN";
    }
    await page.waitForTimeout(500);
  }
  log(`Черновик id=${draftId}: read-only статус=${observed}.`);
  return observed;
}

module.exports = {
  PUBLICATIONS_URL,
  TITLE_SEARCH_TIMEOUT_MS,
  VIDEO_FILTER_SELECTOR,
  VIDEO_FILTER_TIMEOUT_MS,
  checkBeforeUpload,
  extractPublishedVideoId,
  pinnedPublishedIdentity,
  findVisiblePublishedVideo,
  inspectPinnedDraft,
  summarizeDraftInspection,
  findVisibleTitlePrefix,
  isLoginUrl,
  resolveDateKey,
  titlePrefixForDuplicateCheck,
};
