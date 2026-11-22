"use strict";
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");

const worker = fs.readFileSync(path.join(__dirname, "..", "worker.js"), "utf8");
const a = worker.indexOf("function permanentNotebookUrl(");
const b = worker.indexOf("async function fillPromptField(", a);
assert(a > 0 && b > a, "Worker recovery functions must be found");
const snippet = worker.slice(a, b);

let fakeMs = Date.parse("2026-11-22T07:20:00Z");
class FakeDate extends Date {
  constructor(...args) { super(...(args.length ? args : [fakeMs])); }
  static now() { fakeMs += 100; return fakeMs; }
}

const url = "https://notebook.google.com/notebook/11111111-2222-4333-a444-555555555555";

async function scenario({ retryArmed = false, hasUuidAfterClick = true, ambiguous = false } = {}) {
  let createClicks = 0;
  let writes = 0;
  let submits = 0;
  const job = {
    date: "2026-11-22", status: "NEW", notebookUrl: null,
    notebookCreateArmedAt: "2026-11-22T06:10:09.759Z",
  };
  if (retryArmed) job.notebookCreateRetryArmedAt = "2026-11-22T06:11:09.759Z";
  const state = { jobs: { release: job } };
  let pageUrl = "https://notebook.google.com/";
  const candidates = ambiguous ? [
    {title:"Блокнот без названия", detail:"Блокнот без названия 22 нояб. 2026 г. · 0 источников",url},
    {title:"Блокнот без названия", detail:"Блокнот без названия 22 нояб. 2026 г. · 0 источников",url:"https://notebook.google.com/notebook/aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee"},
  ] : [];
  const scope = {
    URL, Date: FakeDate, Intl, log: () => {}, stage: "", activePage: null,
    getRobotPage: async () => ({
      goto: async (next) => { pageUrl = next; },
      url: () => pageUrl,
      waitForTimeout: async () => {},
      locator: () => ({first: () => ({isVisible: async () => false})}),
      evaluate: async () => candidates,
    }),
    waitNotebookHome: async () => {},
    confirmNotebookPage: async () => {},
    clickAnyVisible: async () => {
      assert(job.notebookCreateRetryArmedAt, "Retry checkpoint is durable before remote click");
      createClicks += 1;
      if (hasUuidAfterClick) pageUrl = url;
    },
    notebookCreateLocators: () => [],
    saveState: () => { writes += 1; },
    sourceUi: {openWebsiteSourceInput: async () => ({})},
    describeVisibleButtons: async () => [],
    fillWebsiteSourceUrl: async () => ({}),
    submitWebsiteSourceUrl: async () => { submits += 1; },
    waitForSourceImportReady: async () => { throw Error("source_ready_mock"); },
    renameCurrentNotebook: async () => {},
  };
  const create = vm.runInNewContext(snippet + "\ncreateNotebookAndAddSource", scope);
  const run = () => create(
    {notebookUrl:"https://notebook.google.com/",uiTimeoutMs:800,timeZone:"Europe/Moscow"},
    {},{url:"https://rybalka.one/posts/2026-11-22/",date:"2026-11-22"},job,state
  );
  if (hasUuidAfterClick && !retryArmed && !ambiguous) {
    await assert.rejects(run(), /source_ready_mock/);
    assert.equal(createClicks, 1);
    assert.equal(job.notebookUrl, url);
    assert(job.notebookCreateRetryArmedAt);
    assert.equal(submits, 1);
    assert(writes >= 3);
    await assert.rejects(run(), /source_ready_mock/);
    assert.equal(createClicks, 1, "Second run must not create another notebook");
    assert.equal(submits, 1, "Second run must not resubmit source");
  } else if (retryArmed) {
    await assert.rejects(run(), /Не найден подходящий пустой блокнот/);
    assert.equal(createClicks, 0, "Retry was already armed");
  } else if (ambiguous) {
    await assert.rejects(run(), /несколько подходящих/);
    assert.equal(createClicks, 0, "Multiple candidates block create");
  } else {
    await assert.rejects(run(), /Не найден подходящий пустой блокнот/);
    assert.equal(createClicks, 1);
    assert(job.notebookCreateRetryArmedAt);
    await assert.rejects(run(), /Не найден подходящий пустой блокнот/);
    assert.equal(createClicks, 1, "Uncertain retry must never be repeated");
  }
}

(async () => {
  await scenario();
  await scenario({retryArmed:true});
  await scenario({ambiguous:true});
  await scenario({hasUuidAfterClick:false});
  console.log("Gemini once-only new notebook retry: 4 scenarios passed");
})().catch((error) => {console.error(error);process.exitCode = 1;});
