"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish-live.js"), "utf8");
const direct = fs.readFileSync(path.join(ROOT, "dzen-publish-direct.js"), "utf8");
const runner = fs.readFileSync(path.join(ROOT, "dzen-browser-runner.js"), "utf8");
const launcher = fs.readFileSync(path.join(ROOT, "run-dzen-publish.cmd"), "utf8");

for (const marker of [
  '"PUBLISHING"',
  '"PUBLISH_CLICKED_UNVERIFIED"',
  '"PUBLISHED"',
  'button", { name: "Опубликовать", exact: true }',
  'await publishButton.click()',
  'getByText("Видео", { exact: true })',
  'baselineSameTitleVideoCount',
  'videoTabVerified: true',
  'Повторный клик не выполняется',
]) {
  assert(source.includes(marker), `В legacy dzen-publish-live.js отсутствует safety-маркер: ${marker}`);
}

assert(source.includes('dzen-publish.js"), "--dry-run"'), "Legacy live helper должен сохранять прежний prepare-контракт как диагностический fallback");
assert(source.includes("lastCount > Number(dzen.baselineSameTitleVideoCount || 0)"), "Legacy verification должна требовать новую запись, а не наличие старого одноимённого видео");
assert(launcher.includes("dzen-browser-runner.js"), "Live launcher должен запускать browser runner");
assert(runner.includes('"dzen-publish-direct.js"'), "Browser runner должен запускать канонический direct live flow");
assert(runner.includes('require("./browser-session")'), "Browser runner должен использовать worker-compatible browser bootstrap");
assert(direct.includes("Загрузили и обработали видео"), "Direct live flow должен ждать финальную обработку видео");
assert(direct.includes("Готово: можно публиковать и смотреть"), "Direct live flow должен ждать видимый финальный статус Готово");
assert(direct.includes("PUBLISH_CLICKED_UNVERIFIED"), "Direct live flow должен сохранять защиту от повторного клика");

console.log("Dzen live publish contract smoke: OK");
