"use strict";

// Единственное разрешённое действие: клик по точному тексту настройки
// «Больше не показывать такие сообщения» внутри информационного уведомления
// «Видео загружено за N сек». Никаких generic checkbox action или force.
const SPEED_MESSAGE = /Видео\s+загружено\s+за\s+\d+\s+сек(?:унд[ыу]?)?/iu;
const PREFERENCE_LABEL = "Больше не показывать такие сообщения";

function mayAcknowledgeSpeedNotice(text) {
  const body = String(text || "").replace(/\s+/g, " ").trim();
  return SPEED_MESSAGE.test(body) && body.includes(PREFERENCE_LABEL);
}

// Только одна попытка на объект браузера, даже если сервер не подтвердил действие.
const attemptedSpeedPreference = new WeakSet();

async function dismissUploadSpeedNotice(browser, logger = () => {}) {
  if (browser && attemptedSpeedPreference.has(browser)) return { status: "previously-attempted" };
  if (!browser || typeof browser.contexts !== "function") return { status: "unavailable" };
  for (const context of browser.contexts()) {
    for (const page of context.pages()) {
      if (page.isClosed()) continue;
      for (const frame of page.frames()) {
        const body = await frame.locator("body").innerText({ timeout: 1200 }).catch(() => "");
        if (!mayAcknowledgeSpeedNotice(body)) continue;
        const title = frame.getByText(SPEED_MESSAGE).first();
        const label = frame.getByText(PREFERENCE_LABEL, { exact: true }).first();
        if (!(await title.isVisible().catch(() => false)) ||
            !(await label.isVisible().catch(() => false))) continue;

        // Никогда не выбираем цель по роли checkbox: динамический DOM Дзена
        // может переопределить такой локатор на посторонний input.
        // Контроль рядом с точной подписью используется ТОЛЬКО для чтения.
        const nearbyControl = label.locator("xpath=..")
          .locator('input[type="checkbox"],[role="checkbox"]').first();
        const hasNearbyControl = (await nearbyControl.count().catch(() => 0)) > 0;
        attemptedSpeedPreference.add(browser);
        logger("Уведомление о скорости загрузки: найдена точная подпись разрешённого флажка.");
        if (hasNearbyControl && await nearbyControl.isChecked().catch(() => false)) {
          logger("Разрешённый флажок уже установлен; повторный клик пропущен.");
          return { status: "already-checked" };
        }
        try {
          // Кликаем ТОЛЬКО по видимой точной подписи, без force и обхода
          // перекрывающих окон. Перекрытие приводит к отказу без иных действий.
          await label.click({ timeout: 1500 });
        } catch {
          logger("Разрешённый флажок недоступен для обычного клика; ничего другого не нажимаю.");
          return { status: "blocked" };
        }

        const hidden = !(await title.isVisible().catch(() => false));
        const checked = hasNearbyControl
          ? await nearbyControl.isChecked().catch(() => false)
          : false;
        if (!hidden && !checked) {
          logger("Флажок уведомления нажат, но результат не подтверждён. Повторных кликов не будет.");
          return { status: "unverified" };
        }
        logger("Информационное уведомление о скорости загрузки подавлено/флажок подтверждён.");
        return { status: "acknowledged" };
      }
    }
  }
  return { status: "absent" };
}

// Добавлять поддержку новых известных безопасных уведомлений Дзена нужно только
// в этот список разрешённых обработчиков. Оркестратор не знает подробностей
// текстов и селекторов и не ожидает конкретные окна. Если подходящего окна нет,
// функция сразу возвращает результат без дополнительных ожиданий.
const KNOWN_NOTICE_HANDLERS = Object.freeze([dismissUploadSpeedNotice]);

async function processKnownDzenNotices(browser, logger = () => {}) {
  for (const handler of KNOWN_NOTICE_HANDLERS) {
    const result = await handler(browser, logger);
    if (result && !["absent", "unavailable"].includes(result.status)) return result;
  }
  return { status: "absent" };
}

module.exports = {
  SPEED_MESSAGE,
  PREFERENCE_LABEL,
  mayAcknowledgeSpeedNotice,
  dismissUploadSpeedNotice,
  processKnownDzenNotices,
};
