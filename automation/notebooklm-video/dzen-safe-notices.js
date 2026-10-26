"use strict";

// Whitelist a NON-security informational notification from Dzen:
// "Видео загружено за 4 сек" + "Больше не показывать такие сообщения".
// Never click robot/consent challenges, generic checkboxes, or unknown dialogs.
const SPEED_MESSAGE = /Видео\s+загружено\s+за\s+\d+\s+сек(?:унд[ыу]?)?/iu;
const PREFERENCE_LABEL = "Больше не показывать такие сообщения";
// Fail closed if a verification prompt shares the visible surface.
const HUMAN_CHALLENGE = /подтвердите\s*,?\s*что\s*вы\s*не\s*(?:робот|против)|я\s+не\s+робот|я\s+не\s+против/iu;

function mayAcknowledgeSpeedNotice(text) {
  const body = String(text || "").replace(/\s+/g, " ").trim();
  return SPEED_MESSAGE.test(body) && body.includes(PREFERENCE_LABEL) &&
    !HUMAN_CHALLENGE.test(body);
}

// One attempt per browser session, even if the server does not acknowledge it.
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

        // Only a control associated with the EXACT allowlisted label qualifies.
        // If the UI lacks an accessible checkbox, clicking the visible label
        // is permitted once, but lack of a verified result does not retry.
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

// Extend only this allowlist to support additional known, non-security Dzen
// notices. The orchestrator does not know selector/text details or wait for
// any specific popup. Returns immediately when nothing supported is visible.
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
