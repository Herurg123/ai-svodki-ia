"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");

const ROOT = path.resolve(__dirname, "..");
const scriptPath = path.join(ROOT, "dzen-article-video.js");
const source = fs.readFileSync(scriptPath, "utf8");
assert.doesNotMatch(
  source,
  /__AI_AV_ORIGINAL_CLIPBOARD__|restoreOriginalClipboardBestEffort|originalClipboard\s*=\s*await\s+readClipboardText/,
  "article-video must not preserve or restore the operator clipboard"
);
const setupSource = fs.readFileSync(path.join(ROOT, "setup-local.ps1"), "utf8");
const fullWorkerSource = fs.readFileSync(path.join(ROOT, "full-worker.js"), "utf8");
const articleVideo = require(scriptPath);

assert.strictEqual(articleVideo.formatRussianLongDate("2027-01-03"), "3 января 2027");
assert.strictEqual(articleVideo.formatRussianLongDate("2028-12-31"), "31 декабря 2028");
assert.throws(() => articleVideo.parseDateKey("2027-02-30"), /Некорректная дата/);
assert.throws(() => articleVideo.parseDateKey("20.09.2026"), /Некорректная дата/);

assert.strictEqual(
  articleVideo.prerequisitesSatisfied({
    dzenAutomation: { status: "PUBLISHED" },
    dzenCollections: { status: "COMPLETE" },
  }),
  true
);
assert.strictEqual(
  articleVideo.prerequisitesSatisfied({
    dzenAutomation: { status: "PUBLISHED" },
    dzenCollections: { status: "PARTIAL" },
  }),
  false
);
assert.strictEqual(
  articleVideo.prerequisitesSatisfied({
    dzenAutomation: { status: "CLICKED_UNVERIFIED" },
    dzenCollections: { status: "COMPLETE" },
  }),
  false
);

for (const phase of ["PUBLISH_ARMED", "CONFIRMATION_ARMED", "CLICKED_UNVERIFIED"]) {
  assert(articleVideo.VERIFY_ONLY_PHASES.has(phase), `${phase} must be verification-only`);
}
for (const status of ["COMPLETE", "SKIPPED_EXISTING", "ERROR"]) {
  assert(articleVideo.TERMINAL_STATUSES.has(status), `${status} must be terminal`);
}

const directArticle = articleVideo.expectedPublicationUrlFromCandidates(
  [{ value: "https://dzen.ru/a/article-test", source: "row-anchor-href" }],
  "article"
);
assert.strictEqual(directArticle.value, "https://dzen.ru/a/article-test");
assert.strictEqual(
  articleVideo.expectedPublicationUrlFromCandidates(
    [{ value: "https://dzen.ru/a/not-video", source: "row-anchor-href" }],
    "video"
  ),
  null
);
assert.strictEqual(
  articleVideo.isSafePreEditLinkResolutionError({
    status: "ERROR",
    phase: "ERROR",
    lastError: "«Скопировать ссылку» не положил в clipboard ожидаемый article URL.",
  }),
  true
);
assert.strictEqual(
  articleVideo.isSafePreEditLinkResolutionError({
    status: "ERROR",
    phase: "ERROR",
    lastError: "«Скопировать ссылку» не положил в clipboard ожидаемый article URL.",
    saveChangesClickedAt: "2026-09-21T00:00:00.000Z",
  }),
  false
);

assert.throws(
  () => articleVideo.buildClipboardWriteCommand(""),
  /Пустое значение нельзя записывать в Windows clipboard/,
  "article-video no longer preserves/restores an empty operator clipboard"
);

const nonEmptyClipboardCommand = articleVideo.buildClipboardWriteCommand("abc");
assert.match(nonEmptyClipboardCommand, /Set-Clipboard -Value \$v/);

assert.strictEqual(
  articleVideo.isSafePrePublishClipboardError({
    status: "ERROR",
    phase: "ERROR",
    articleUrl: "https://dzen.ru/a/article-test",
    videoUrl: "https://dzen.ru/video/watch/video-test",
    lastError: "Set-Clipboard : Value cannot be null. ArgumentNullException",
  }),
  true
);
assert.strictEqual(
  articleVideo.isSafePrePublishClipboardError({
    status: "ERROR",
    phase: "ERROR",
    articleUrl: "https://dzen.ru/a/article-test",
    videoUrl: "https://dzen.ru/video/watch/video-test",
    lastError: "Set-Clipboard : Value cannot be null. ArgumentNullException",
    publishArmedAt: "2026-09-21T00:00:00.000Z",
  }),
  false
);

assert.strictEqual(
  articleVideo.isSafeBrowserPasteMigrationError({
    status: "ERROR",
    phase: "ERROR",
    articleUrl: "https://dzen.ru/a/article-test",
    videoUrl: "https://dzen.ru/video/watch/video-test",
    failedFromPhase: "EDITING",
    lastError: "Set-Clipboard : OpenClipboard Failed (ExternalException)",
  }),
  true
);
assert.strictEqual(
  articleVideo.isSafeBrowserPasteMigrationError({
    status: "ERROR",
    phase: "ERROR",
    articleUrl: "https://dzen.ru/a/article-test",
    videoUrl: "https://dzen.ru/video/watch/video-test",
    lastError: "Set-Clipboard : OpenClipboard Failed (ExternalException)",
    saveChangesClickedAt: "2026-09-21T00:00:00.000Z",
  }),
  false
);

const baseDescription = [
  "ИИ-Сводка на 3 января 2027 | Подпишись, чтоб получать свежее!",
  "",
  "Этот выпуск:",
  "- https://rybalka.one/posts/2027-01-03/",
  "- https://",
  "",
  "Все ИИ-сводки:",
  "- https://dzen.ru/suite/example",
  "",
].join("\r\n");

const replacement = articleVideo.planDescriptionArticleUrlUpdate(
  baseDescription,
  "https://rybalka.one/posts/2027-01-03/",
  "https://dzen.ru/a/article-2027"
);
assert.strictEqual(replacement.changed, true);
assert.strictEqual(replacement.status, "UPDATED");
assert.match(replacement.text, /- https:\/\/dzen\.ru\/a\/article-2027/);
assert.doesNotMatch(replacement.text, /^- https:\/\/$/m);

const manualDescription = baseDescription.replace(
  "- https://\r\n",
  "- https://dzen.ru/a/manual-link\r\n"
);
const manual = articleVideo.planDescriptionArticleUrlUpdate(
  manualDescription,
  "https://rybalka.one/posts/2027-01-03/",
  "https://dzen.ru/a/must-not-overwrite"
);
assert.strictEqual(manual.changed, false);
assert.strictEqual(manual.status, "PLACEHOLDER_ABSENT");
assert.strictEqual(manual.text, manualDescription);

const absentMarker = articleVideo.planDescriptionArticleUrlUpdate(
  "Этот текст оператор уже менял вручную\r\n- https://dzen.ru/a/manual",
  "https://rybalka.one/posts/2027-01-03/",
  "https://dzen.ru/a/must-not-write"
);
assert.strictEqual(absentMarker.changed, false);
assert.strictEqual(absentMarker.status, "PLACEHOLDER_ABSENT");

assert.throws(
  () => articleVideo.planDescriptionArticleUrlUpdate(
    baseDescription,
    "https://rybalka.one/posts/2027-01-04/",
    "https://dzen.ru/a/article-2027"
  ),
  /относится к другому выпуску/
);

const customPlaceholderDescription = baseDescription.replace(
  "- https://\r\n",
  "- INSERT_DZEN_URL\r\n"
);
const custom = articleVideo.planDescriptionArticleUrlUpdate(
  customPlaceholderDescription,
  "https://rybalka.one/posts/2027-01-03/",
  "https://dzen.ru/a/custom-placeholder",
  "INSERT_DZEN_URL"
);
assert.strictEqual(custom.changed, true);
assert.match(custom.text, /- https:\/\/dzen\.ru\/a\/custom-placeholder/);

for (const forbidden of [
  "aq81qx3cWgqrPBQp",
  "6aaf5d085f9262069ab338e6",
  'dateKey !== "2026-09-20"',
  "--retest-from-clean",
  "--recover-modal-candidate-failure",
  "--reset-clean-experiment",
  "--resume-save-changes",
  "__AI_AV_ORIGINAL_CLIPBOARD__",
  "restoreOriginalClipboardBestEffort",
]) {
  assert(!source.includes(forbidden), `production source must not retain incident-only marker: ${forbidden}`);
}

for (const required of [
  'const HEADING_TEXT = "Видеосводка"',
  'const ANCHOR_TEXT = "Мировые лидеры ИИ"',
  'descriptionSecondUrlPlaceholder || "https://"',
  "Файл описания НЕ меняю: exact заглушка второй ссылки отсутствует",
  "phase=PUBLISH_ARMED",
  "phase=CONFIRMATION_ARMED",
  "phase=CLICKED_UNVERIFIED",
  "Сохранить изменения",
  "AUTOSAVE_STABLE_MS = 8_000",
  "POST-CONFIRM: после «Сохранить изменения» началась навигация",
  "Публичная verification подтверждена",
  "Public ${kind} URL получен напрямую из same-day Studio row",
  "--recover-pre-edit-link-error",
  "--recover-prepublish-clipboard-error",
  "--recover-browser-paste-migration",
  "Browser-side paste dispatch:",
  "Windows clipboard не используется",
  "videoEmbedConfirmedAt",
]) {
  assert(source.includes(required), `missing article-video contract marker: ${required}`);
}

const selfTestOutput = execFileSync(
  process.execPath,
  [scriptPath, "--self-test"],
  { cwd: ROOT, encoding: "utf8" }
);
assert.match(selfTestOutput, /SELF-TEST OK/);


for (const deploymentMarker of [
  '"dzen-article-video.js"',
  '"run-dzen-article-video-dry-run.cmd"',
  '"run-dzen-article-video-apply.cmd"',
  '"DZEN_ARTICLE_VIDEO.md"',
  "node --check dzen-article-video.js",
]) {
  assert(
    setupSource.includes(deploymentMarker),
    `setup-local.ps1 must deploy/check article-video asset: ${deploymentMarker}`
  );
}

assert(
  fullWorkerSource.includes('runNodeScript("dzen-article-video.js", ["--apply"'),
  "full-worker must invoke the production article-video child"
);
assert(
  fullWorkerSource.includes('dzenStatus !== "PUBLISHED" || collectionStatus !== "COMPLETE"'),
  "full-worker must gate article-video on PUBLISHED + COMPLETE"
);

console.log("Dzen article-video contract smoke: OK");
