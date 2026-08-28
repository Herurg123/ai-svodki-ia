"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const guard = require(path.join(ROOT, "dzen-duplicate-guard.js"));
const runnerSource = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");
const guardSource = fs.readFileSync(path.join(ROOT, "dzen-duplicate-guard.js"), "utf8");

assert.strictEqual(
  guard.titlePrefixForDuplicateCheck(
    "ИИ-Сводка на 27 августа 2026 | Подпишись, чтоб получать свежее!"
  ),
  "ИИ-Сводка на 27 августа 2026"
);
assert.strictEqual(
  guard.resolveDateKey(["--date=2026-08-27"], "Europe/Moscow"),
  "2026-08-27"
);
assert.strictEqual(guard.isLoginUrl("https://passport.yandex.ru/auth?origin=dzen"), true);
assert.strictEqual(
  guard.isLoginUrl("https://dzen.ru/profile/editor/rybv/publications"),
  false
);
assert.strictEqual(
  guard.PUBLICATIONS_URL,
  "https://dzen.ru/profile/editor/rybv/publications"
);
assert.strictEqual(
  guard.VIDEO_FILTER_SELECTOR,
  'input[type="radio"][aria-label="Видео"]'
);

for (const marker of [
  "ВИДЕО УЖЕ ЕСТЬ",
  "новый upload, draft и publish click не выполняю",
  "element.click()",
  "isChecked()",
  "checked=true",
  "видимой части списка «Видео»",
]) {
  assert(guardSource.includes(marker), `Missing duplicate-guard marker: ${marker}`);
}

assert(
  !guardSource.includes('getByText("Видео", { exact: true }).click'),
  "Duplicate guard must not click the visual text layer for the Video radio control"
);

const guardCall = runnerSource.indexOf("duplicateGuard.checkBeforeUpload");
const childCall = runnerSource.indexOf("await runNodeScript", guardCall);
assert(guardCall >= 0, "Runner must invoke the duplicate guard");
assert(childCall > guardCall, "Duplicate guard must execute before the live child");
assert(
  runnerSource.includes("live child не запускается"),
  "Existing video must short-circuit before upload child"
);
assert(
  runnerSource.includes("live publish выполняется одним child-проходом без автоматического повторного запуска"),
  "Non-duplicate live path must preserve the validated single-child publish contract"
);

async function runExistingVideoMock() {
  let checked = false;
  const logs = [];

  const radio = {
    count: async () => 1,
    evaluate: async (callback) => {
      callback({ click: () => { checked = true; } });
    },
    isChecked: async () => checked,
  };

  const titleCandidate = {
    isVisible: async () => true,
    innerText: async () =>
      "ИИ-Сводка на 27 августа 2026 | Подпишись, чтоб получать свежее!",
    textContent: async () => "",
  };

  const page = {
    _url: guard.PUBLICATIONS_URL,
    goto: async (url) => { page._url = url; },
    url: () => page._url,
    waitForTimeout: async () => {},
    locator: (selector) => {
      assert.strictEqual(selector, guard.VIDEO_FILTER_SELECTOR);
      return { first: () => radio };
    },
    getByText: (text, options) => {
      assert.strictEqual(text, "ИИ-Сводка на 27 августа 2026");
      assert.deepStrictEqual(options, { exact: false });
      return {
        count: async () => 1,
        nth: () => titleCandidate,
      };
    },
  };

  const result = await guard.checkBeforeUpload(
    page,
    { timeZone: "Europe/Moscow" },
    ["--date=2026-08-27"],
    (message) => logs.push(message)
  );

  assert.strictEqual(result.existing, true);
  assert.strictEqual(result.dateKey, "2026-08-27");
  assert.strictEqual(result.titlePrefix, "ИИ-Сводка на 27 августа 2026");
  assert.strictEqual(checked, true, "Video radio must be activated through the real control");
  assert(logs.some((line) => line.includes("ВИДЕО УЖЕ ЕСТЬ")));
  assert(logs.some((line) => line.includes("upload, draft и publish click не выполняю")));
}

runExistingVideoMock()
  .then(() => console.log("Dzen pre-upload duplicate guard smoke: OK"))
  .catch((error) => {
    console.error(error.stack || error.message);
    process.exit(1);
  });
