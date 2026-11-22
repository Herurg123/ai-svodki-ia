"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const worker = fs.readFileSync(path.join(__dirname, "..", "worker.js"), "utf8");
const start = worker.indexOf("function permanentNotebookUrl(");
const end = worker.indexOf("async function fillPromptField(", start);
assert(start > 0 && end > start, "Recovery function boundary must exist");
const snippet = worker.slice(start, end);
const id1 = "11111111-2222-4333-a444-555555555555";
const id2 = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const prefix = "https://notebook.google.com/notebook/";
const date = "2026-11-22";
const title = "Блокнот без названия";
function card(id, {day = "22 нояб. 2026 г.", sources = 0, name = title} = {}) {
  return {url: prefix + id, title: name,
    detail: name + " " + day + " · " + sources + " источников"};
}
const ctx = {URL, Intl, Date, log: () => {}, saveState: () => {},
  stage: "", document: null};
const fns = vm.runInNewContext(snippet +
  "\n({permanentNotebookUrl,chooseUnambiguousNewNotebook,notebookRecoveryDateLabels,scanNotebookHomeCards,waitForNewNotebookIdentity,recoverCreatedNotebookFromHome,createNotebookAndAddSource})",ctx);

assert.equal(fns.chooseUnambiguousNewNotebook([card(id1)], date), prefix + id1);
assert.equal(fns.chooseUnambiguousNewNotebook([card(id1),card(id2)], date), null,
  "Ambiguous same-day notebooks must never be selected");
assert.equal(fns.chooseUnambiguousNewNotebook([card(id1)], date,[prefix + id1]), null,
  "Already claimed notebook must not be selected");
assert.equal(fns.chooseUnambiguousNewNotebook([card(id1,{day:"21 нояб. 2026 г."})],date),null);
assert.equal(fns.chooseUnambiguousNewNotebook([card(id1,{sources:1})],date),null);
assert.equal(fns.chooseUnambiguousNewNotebook([card(id1,{name:"Личный блокнот"})],date),null);
assert.equal(fns.chooseUnambiguousNewNotebook([card("creating")],date),null);
assert(fns.notebookRecoveryDateLabels(date).includes("22 нояб. 2026 г."));

// The actual home card uses a transparent link and an aria-labelledby title.
// Ensure read-only extraction never broadens into a whole-page text match.
const titleNode = {innerText: title};
const cardContainer = {
  innerText: "Блокнот без названия 22 нояб. 2026 г. · 0 источников",
  querySelectorAll: () => [link],
  parentElement: null,
};
const link = {
  href: prefix + id1,
  parentElement: cardContainer,
  getAttribute: (key) => key === "aria-labelledby" ? "title-id" : null,
};
ctx.document = {
  querySelectorAll: () => [link],
  getElementById: (key) => key === "title-id" ? titleNode : null,
};

(async () => {
  const rawCards = await fns.scanNotebookHomeCards({evaluate: async fn => fn()});
  assert.equal(rawCards.length,1);
  assert.equal(fns.chooseUnambiguousNewNotebook(rawCards,date),prefix + id1);

  // A stalled create route may eventually acquire the real UUID. Persist it
  // immediately, independently from notebook shell readiness.
  let route = prefix + "creating";
  const captured = [];
  const parsed = await fns.waitForNewNotebookIdentity({
    url: () => route, waitForTimeout: async () => {route = prefix + id1;}
  }, 1000, async url => captured.push(url));
  assert.equal(parsed,prefix + id1);
  assert.deepEqual(captured,[prefix + id1]);

  // Recover a 2026-11-22 NEW job with an already armed remote create, without
  // another create click, another notebook, or a guessed source URL.
  const job = {date,status:"NEW",notebookUrl:null,
    notebookCreateArmedAt:"2026-11-22T06:10:09.759Z"};
  const state = {jobs:{release:job}};
  const snapshots = [];
  let createClicks = 0, sourceSubmits = 0, browserPage = prefix + "creating";
  const page = {
    goto: async url => {browserPage=url;},
    url: () => browserPage,
    evaluate: async fn => fn(),
    waitForTimeout: async () => {},
  };
  const recoverCtx = {
    URL,Intl,Date,document:ctx.document,stage:"",activePage:null,
    getRobotPage: async () => page,
    waitNotebookHome: async () => {},
    confirmNotebookPage: async () => {},
    sourceUi:{openWebsiteSourceInput:async()=>({})},
    fillWebsiteSourceUrl:async()=>({}),
    submitWebsiteSourceUrl:async()=>{sourceSubmits++;},
    waitForSourceImportReady:async()=>{throw Error("source readiness pending");},
    renameCurrentNotebook:async()=>{},
    clickAnyVisible:async()=>{createClicks++;},
    notebookCreateLocators:()=>[],
    saveState:(_config,value)=>snapshots.push(JSON.parse(JSON.stringify(value))),
    log:()=>{},
  };
  const create = vm.runInNewContext(snippet+"\ncreateNotebookAndAddSource",recoverCtx);
  await assert.rejects(create(
    {notebookUrl:"https://notebook.google.com/",uiTimeoutMs:1000,timeZone:"Europe/Moscow"},
    {},{url:"https://rybalka.one/posts/2026-11-22/",date},job,state
  ),/source readiness pending/);
  assert.equal(createClicks,0,"Already armed creation must never be clicked again");
  assert.equal(sourceSubmits,1,"Recovered empty notebook may receive its first source once");
  assert.equal(job.notebookUrl,prefix + id1);
  assert(snapshots.some(x=>x.jobs.release.notebookUrl===prefix+id1),
    "Recovered UUID must be durable before source submission");
  assert.equal(job.status,"CREATING_VIDEO");

  console.log("Gemini notebook same-day unique-card recovery: OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
