"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ROOT = path.resolve(__dirname, "..");

function read(name) {
  return fs.readFileSync(path.join(ROOT, name), "utf8");
}

const config = JSON.parse(read("config.example.json"));
assert.strictEqual(config.ftpUpload.enabled, false, "FTP must stay disabled by default");
assert.strictEqual(config.ftpUpload.remoteDir, "video", "FTP root must stay confined to video");
assert.strictEqual(
  config.ftpUpload.remoteFilenamePrefix,
  "ai-svodka",
  "published media names must use the expected prefix"
);

const worker = read("worker.js");
assert.strictEqual(
  Object.prototype.hasOwnProperty.call(config, "tempDir"),
  false,
  "unused tempDir must not be provisioned in fresh config"
);
assert.strictEqual(
  Object.prototype.hasOwnProperty.call(config, "tracesDir"),
  false,
  "unused tracesDir must not be provisioned in fresh config"
);

assert.match(
  worker,
  /config\.ftpUpload\.remoteDir\s*!==\s*["']video["']/,
  "worker must reject any configured FTP directory other than video"
);
assert.match(
  worker,
  /ensureDir\(\s*["']video["']\s*\)/,
  "worker must explicitly enter/create only the video FTP directory"
);
assert.match(
  worker,
  /ai-svodka|remoteFilenamePrefix/,
  "worker must keep deterministic remote media naming"
);
assert.doesNotMatch(
  worker,
  /config\.tempDir|config\.tracesDir/,
  "worker startup must not create unused temp/traces directories"
);

const generateButtonPattern = /^Сгенерировать(?: сейчас)?$/i;
assert.ok(
  worker.includes(
    "const VIDEO_GENERATE_BUTTON_PATTERN = /^Сгенерировать(?: сейчас)?$/i;"
  ),
  "worker must keep exact backward-compatible NotebookLM generate-button labels"
);
assert.strictEqual(
  generateButtonPattern.test("Сгенерировать"),
  true,
  "legacy NotebookLM generate label must remain supported"
);
assert.strictEqual(
  generateButtonPattern.test("Сгенерировать сейчас"),
  true,
  "current NotebookLM generate-now label must be supported"
);
assert.strictEqual(
  generateButtonPattern.test("Сгенерировать позже"),
  false,
  "the adjacent generate-later action must never match the start-generation selector"
);
assert.strictEqual(
  (worker.match(/VIDEO_GENERATE_BUTTON_PATTERN/g) || []).length,
  4,
  "generate-button compatibility pattern must be defined once and used by all three start locators"
);

assert.ok(
  worker.includes(
    "const NOTEBOOK_CREATE_BUTTON_PATTERN = /^\\+?\\s*(?:Новый блокнот|Создать)$/i;"
  ),
  "worker must support the current NotebookLM 'Новый блокнот' button and legacy 'Создать'"
);
assert.match(
  worker,
  /getByText\(\/Недавние блокноты\/i\)/,
  "current NotebookLM home marker 'Недавние блокноты' must be accepted"
);
assert.match(
  worker,
  /notebookCreateLocators\(activePage\)/,
  "new notebook creation must reuse the compatibility locator set"
);

assert.match(
  worker,
  /function sourceImportContentReady\(snapshot, minimumContentChars\)/,
  "source readiness must have a compatibility oracle for the new NotebookLM center summary UI"
);
assert.match(
  worker,
  /generatedTitleReady/,
  "auto-generated notebook title must be accepted as the new-UI content readiness signal"
);
assert.match(
  worker,
  /Блокнот без названия\|Без названия\|Untitled/,
  "untitled notebook placeholders must never satisfy source readiness"
);
assert.match(
  worker,
  /contentReady\.ready/,
  "source-import wait must use the compatibility content readiness result instead of requiring legacy chat text only"
);

const ignore = read(".gitignore");
for (const required of [
  "config.json",
  "ftp-access.json",
  "state.json",
  "worker.log",
  "downloads/",
  "yandex-profile/",
  "node_modules/",
]) {
  assert.ok(ignore.includes(required), `local runtime asset must stay ignored: ${required}`);
}

const agents = read("AGENTS.md");
assert.match(agents, /Video CI/i, "subproject rules must name the dedicated Video CI boundary");
assert.match(
  agents,
  /Main CI/i,
  "subproject rules must explicitly distinguish Video CI from Main CI"
);


function functionFromWorker(start, end, functionName, context = {}) {
  const a = worker.indexOf(start);
  const b = worker.indexOf(end, a + start.length);
  assert(a !== -1 && b > a, `Missing worker function ${functionName}`);
  return vm.runInNewContext(
    `${worker.slice(a, b)}\n${functionName}`,
    context
  );
}

const readiness = functionFromWorker(
  "function sourceImportContentReady(",
  "async function waitForSourceImportReady(",
  "sourceImportContentReady"
);

const screenshotState = {
  headerTitle: "Блокнот без названия",
  chatContentLength: 0,
  centralOverviewLength: 475,
  centralOverviewLongestTextChars: 162,
};
assert.strictEqual(readiness(screenshotState, 220).signal, "central-overview");
assert.strictEqual(
  readiness({ ...screenshotState, centralOverviewLength: 0 }, 220).ready,
  false,
  "One source and an enabled video button alone must not imply readiness"
);
assert.strictEqual(
  readiness({ ...screenshotState, centralOverviewLongestTextChars: 15 }, 220).ready,
  false,
  "Short interface hints must not mimic an imported summary"
);
assert.strictEqual(
  readiness({ headerTitle: "Блокнот без названия", chatContentLength: 250 }, 220).signal,
  "chat-content",
  "Legacy chat content must remain supported"
);
assert.strictEqual(
  readiness({ headerTitle: "Сводка: модели и инфраструктура", chatContentLength: 0 }, 220).signal,
  "generated-title",
  "Legacy automatic title readiness must remain supported"
);

async function verifyResumeState() {
  const createFnSource = worker.slice(
    worker.indexOf("async function createNotebookAndAddSource("),
    worker.indexOf("async function fillPromptField(")
  );
  async function exerciseCreate(initialUrl, createdUrl) {
    let pageUrl = initialUrl;
    const snapshots = [];
    const page = {
      goto: async () => {},
      url: () => pageUrl,
      locator: () => ({ filter: () => ({}) }),
      getByRole: () => ({}),
      getByText: () => ({}),
    };
    const context = {
      stage: "",
      activePage: null,
      getRobotPage: async () => page,
      waitNotebookHome: async () => {},
      notebookCreateLocators: () => [],
      clickAnyVisible: async () => { pageUrl = createdUrl; },
      waitForAnyEnabledVisible: async () => ({ click: async () => {} }),
      fillWebsiteSourceUrl: async () => ({}),
      submitWebsiteSourceUrl: async () => {},
      waitForSourceImportReady: async () => { throw Error("source timeout"); },
      saveState: (_config, state) => snapshots.push(JSON.parse(JSON.stringify(state))),
      renameCurrentNotebook: async () => {},
      log: () => {},
    };
    const fn = vm.runInNewContext(
      `${createFnSource}\ncreateNotebookAndAddSource`,
      context
    );
    const publication = { url: "https://rybalka.one/posts/2026-10-16/" };
    const job = { status: "NEW", notebookUrl: null, notebookTitleHint: "ИИ-2026-10-16" };
    const state = { jobs: { today: job } };
    return {
      invoke: () => fn({ notebookUrl: "https://notebook.google.com/", uiTimeoutMs: 30000 }, {}, publication, job, state),
      job,
      snapshots,
    };
  }

  const valid = await exerciseCreate(
    "https://notebook.google.com/",
    "https://notebook.google.com/notebook/fixture-uuid"
  );
  await assert.rejects(valid.invoke(), /source timeout/);
  assert.strictEqual(valid.job.status, "CREATING_VIDEO");
  assert.strictEqual(valid.job.notebookUrl, "https://notebook.google.com/notebook/fixture-uuid");
  assert(
    valid.snapshots.some((snapshot) =>
      snapshot.jobs.today.status === "CREATING_VIDEO" &&
      snapshot.jobs.today.notebookUrl.endsWith("/fixture-uuid")
    ),
    "Pending notebook URL must be saved before source readiness timeout"
  );

  const invalid = await exerciseCreate("https://notebook.google.com/", "https://notebook.google.com/");
  await assert.rejects(invalid.invoke(), /Невозможно сохранить URL/);
  assert.strictEqual(invalid.job.status, "NEW");
  assert.strictEqual(invalid.snapshots.length, 0);

  const calls = [];
  const resumeContext = {
    stage: "",
    activePage: null,
    openNotebookWithFallback: async () => { calls.push("open-uuid"); return {}; },
    waitForSourceImportReady: async () => { calls.push("verify-source"); },
    renameCurrentNotebook: async () => { calls.push("rename"); },
    startVideoGeneration: async () => { calls.push("generate"); },
  };
  const resume = functionFromWorker(
    "async function continueCreatingVideo(",
    "async function findVideoArtifactContainer(",
    "continueCreatingVideo",
    resumeContext
  );
  await resume({}, {}, {}, { status: "CREATING_VIDEO", notebookUrl: valid.job.notebookUrl }, {});
  assert.deepStrictEqual(calls, ["open-uuid", "verify-source", "rename", "generate"]);
}

verifyResumeState().then(() => {
  console.log("Video runtime boundary smoke test: OK");
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
