"use strict";

// Whitelist a NON-security informational notification from Dzen:
// "Видео загружено за 4 сек" + "Больше не показывать такие сообщения".
// Never click robot/consent challenges, generic checkboxes, or unknown dialogs.
const SPEED_MESSAGE = /Видео\s+загружено\s+за\s+\d+\s+сек(?:унд[ыу]?)?/iu;
const PREFERENCE_LABEL = "Больше не показывать такие сообщения";
const HUMAN_CHALLENGE = /подтвердите\s*,?\s*что\s*вы\s*не\s*(?:робот|против)|я\s+не\s+робот|я\s+не\s+против/iu;

function mayAcknowledgeSpeedNotice(text) {
  const body = String(text || "").replace(/\s+/g, " ").trim();
  return SPEED_MESSAGE.test(body) && body.includes(PREFERENCE_LABEL) &&
    !HUMAN_CHALLENGE.test(body);
}

async function dismissUploadSpeedNotice(browser, logger = () => {}) {
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

        // Only a control associated with the EXACT allowlisted label qualifies.
        // If the UI lacks an accessible checkbox, clicking the visible label
        // is permitted once, but lack of a verified result does not retry.
        const namedCheckbox = frame.getByRole("checkbox", { name: PREFERENCE_LABEL, exact: true }).first();
        const localCheckbox = label.locator("xpath=..")
          .locator('input[type="checkbox"],[role="checkbox"]').first();
        const control = (await namedCheckbox.count().catch(() => 0)) > 0
          ? namedCheckbox
          : ((await localCheckbox.count().catch(() => 0)) > 0 ? localCheckbox : null);
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

module.exports = {
  SPEED_MESSAGE,
  PREFERENCE_LABEL,
  mayAcknowledgeSpeedNotice,
  dismissUploadSpeedNotice,
};
