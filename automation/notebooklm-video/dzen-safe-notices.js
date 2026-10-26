"use strict";

// Разрешаем только информационное уведомление Дзена, не связанное с проверкой безопасности:
// «Видео загружено за 4 сек» + «Больше не показывать такие сообщения».
// Не нажимаем проверки человека, флажки согласия, произвольные флажки и неизвестные окна.
const SPEED_MESSAGE = /Видео\s+загружено\s+за\s+\d+\s+сек(?:унд[ыу]?)?/iu;
const PREFERENCE_LABEL = "Больше не показывать такие сообщения";
// Если на той же видимой странице есть проверка человека, ничего не нажимаем.
const HUMAN_CHALLENGE = /подтвердите\s*,?\s*что\s*вы\s*не\s*(?:робот|против)|я\s+не\s+робот|я\s+не\s+против/iu;

function mayAcknowledgeSpeedNotice(text) {
  const body = String(text || "").replace(/\s+/g, " ").trim();
  return SPEED_MESSAGE.test(body) && body.includes(PREFERENCE_LABEL) &&
    !HUMAN_CHALLENGE.test(body);
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

        // Подходит только флажок, связанный с ТОЧНЫМ текстом разрешённой подписи.
        // Если отдельный доступный флажок не найден, можно один раз нажать
        // видимую подпись. Если результат не подтвердился, повторной попытки нет.
        const namedCheckbox = frame.getByRole("checkbox", { name: PREFERENCE_LABEL, exact: true }).first();
        const localCheckbox = label.locator("xpath=..")
          .locator('input[type="checkbox"],[role="checkbox"]').first();
        const control = (await namedCheckbox.count().catch(() => 0)) > 0
          ? namedCheckbox
          : ((await localCheckbox.count().catch(() => 0)) > 0 ? localCheckbox : null);
        attemptedSpeedPreference.add(browser);
        logger("Безопасное уведомление Дзен о скорости загрузки: найден точный флажок «Больше не показывать такие сообщения».");
        if (control) {
          if (await control.isChecked().catch(() => false)) {
            logger("Флажок информационных уведомлений уже установлен; повторный клик пропущен.");
            return { status: "already-checked" };
          }
          await control.check({ timeout: 3000 });
        } else {
          await label.click({ timeout: 3000 });
        }

        const hidden = !(await title.isVisible().catch(() => false));
        const checked = control ? await control.isChecked().catch(() => false) : false;
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
