"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(ROOT, "dzen-publish-live.js"), "utf8");
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
  assert(source.includes(marker), `В dzen-publish-live.js отсутствует контрактный маркер: ${marker}`);
}

assert(source.includes('dzen-publish.js"), "--dry-run"'), "Live publish должен сначала переиспользовать проверенную подготовку draft");
assert(source.includes("lastCount > Number(dzen.baselineSameTitleVideoCount || 0)"), "Проверка должна требовать новую запись, а не наличие старого одноимённого видео");
assert(launcher.includes("dzen-publish-live.js"), "Live launcher должен запускать dzen-publish-live.js");

console.log("Dzen live publish contract smoke: OK");
