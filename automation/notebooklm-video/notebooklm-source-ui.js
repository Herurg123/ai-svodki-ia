"use strict";

// Read-only recognition of source surfaces plus one click on a named source
// control. Never use the research/search field for direct URL import.
const WEBSITE_SOURCE_LABEL = /^(?:Сайты|Веб[\s-]?сайты|Веб[\s-]?сайт|Ссылки|Ссылка(?: на (?:сайт|веб[\s-]?страницу))?|Веб[\s-]?страниц(?:а|ы)|Website(?:s)?|Web\s*links?|Links?|URL(?:s)?)$/i;
const SOURCE_OPEN_LABEL = /^(?:\+\s*)?(?:Источники|Добавить источники|Add sources|Sources)$/i;

function urlInputLocators(page) {
  return [
    page.locator('[formcontrolname="newUrl"]:visible'),
    page.locator('input[type="url"]:visible'),
    page.getByRole("textbox", { name: /(?:url|ссылк|адрес|web\s*link)/i }),
    page.locator('input[placeholder*="URL" i]:visible, textarea[placeholder*="URL" i]:visible, input[aria-label*="URL" i]:visible, textarea[aria-label*="URL" i]:visible, input[placeholder*="ссылк" i]:visible, textarea[placeholder*="ссылк" i]:visible'),
  ];
}

function websiteOptionLocators(page) {
  return [
    page.getByRole("button", { name: WEBSITE_SOURCE_LABEL }),
    page.locator('button:visible').filter({ hasText: WEBSITE_SOURCE_LABEL }),
    page.locator('[role="button"]:visible').filter({ hasText: WEBSITE_SOURCE_LABEL }),
    page.getByText(WEBSITE_SOURCE_LABEL),
  ];
}

function sourceOpenLocators(page) {
  return [
    // Gemini Notebook 2026: + Источники in the left sources panel.
    page.getByRole("button", { name: /^\+?\s*Источники$/i }),
    page.locator('button:visible').filter({ hasText: /^\s*\+?\s*Источники\s*$/i }),
    page.getByRole("button", { name: /^(?:Добавить источники|Add sources)$/i }),
    page.locator('button:visible').filter({ hasText: /^(?:Добавить источники|Add sources)$/i }),
    page.locator('[role="button"]:visible').filter({ hasText: /^(?:Добавить источники|Add sources)$/i }),
    page.getByText(/^(?:Добавить источники|Add sources)$/i),
  ];
}

async function firstActionable(locators) {
  for (const locator of locators) {
    const count = await locator.count().catch(() => 0);
    for (let i = 0; i < count; i += 1) {
      const candidate = locator.nth(i);
      if ((await candidate.isVisible().catch(() => false)) &&
          (await candidate.isEnabled().catch(() => false)) &&
          (await candidate.getAttribute("aria-disabled").catch(() => null)) !== "true") {
        return candidate;
      }
    }
  }
  return null;
}

async function findSourceSurface(page, waitMs) {
  const deadline = Date.now() + waitMs;
  do {
    const input = await firstActionable(urlInputLocators(page));
    if (input) return { kind: "url-input", control: input };
    const option = await firstActionable(websiteOptionLocators(page));
    if (option) return { kind: "website-option", control: option };
    if (Date.now() < deadline) await new Promise((r) => setTimeout(r, 200));
  } while (Date.now() < deadline);
  return null;
}

async function openWebsiteSourceInput(page, timeout, { log = () => {}, describeVisibleButtons = async () => [] } = {}) {
  // Some older NotebookLM versions open the source chooser automatically.
  let surface = await findSourceSurface(page, 750);
  if (!surface) {
    const triggers = sourceOpenLocators(page);
    let triggered = false;
    for (const locator of triggers) {
      const count = await locator.count().catch(() => 0);
      for (let i = 0; i < count; i += 1) {
        const candidate = locator.nth(i);
        if (!(await candidate.isVisible().catch(() => false)) ||
            !(await candidate.isEnabled().catch(() => false))) continue;
        try {
          await candidate.click({ timeout: Math.min(timeout, 5000) });
        } catch (error) {
          log(`Открытие панели источников не удалось: ${error.message}`);
          continue;
        }
        triggered = true;
        log('Нажата кнопка открытия источников (Gemini "+ Источники" или NotebookLM "Добавить источники").');
        surface = await findSourceSurface(page, Math.min(timeout, 4500));
        if (surface) break;
      }
      if (surface) break;
    }
    if (!surface) {
      const buttons = await describeVisibleButtons(page);
      throw new Error(
        `Панель источников ${triggered ? "открыта, но нет выбора веб-сайта или URL" : "не открылась"}. ` +
        `Доступные кнопки: ${JSON.stringify(buttons)}`
      );
    }
  }

  if (surface.kind === "website-option") {
    await surface.control.click({ timeout: Math.min(timeout, 5000) });
    log('Выбран источник типа «Сайты/Ссылки/Website».');
    // Only URL input is accepted; never enter the target URL into web search.
    const deadline = Date.now() + Math.min(timeout, 12000);
    while (Date.now() < deadline) {
      const input = await firstActionable(urlInputLocators(page));
      if (input) return input;
      await new Promise((r) => setTimeout(r, 200));
    }
    const buttons = await describeVisibleButtons(page);
    throw new Error(`После выбора «Сайты/Ссылки» не появилось поле URL. Кнопки: ${JSON.stringify(buttons)}`);
  }
  log("Поле URL источника открыто напрямую; отдельная кнопка «Сайты» не требуется.");
  return surface.control;
}

module.exports = {
  WEBSITE_SOURCE_LABEL,
  SOURCE_OPEN_LABEL,
  urlInputLocators,
  websiteOptionLocators,
  sourceOpenLocators,
  firstActionable,
  findSourceSurface,
  openWebsiteSourceInput,
};
