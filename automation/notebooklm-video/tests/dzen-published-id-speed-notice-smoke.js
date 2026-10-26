"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const duplicate = require("../dzen-duplicate-guard");
const notices = require("../dzen-safe-notices");

const goodId = "6adec50a38340e44edf6119c";
const otherId = "6adda98499791f7d2cf2804d";
const goodUrl = "https://dzen.ru/video/watch/" + goodId;
const title = "ИИ-Сводка на 26 октября 2026 | Подпишись, чтоб получать свежее!";

assert.equal(duplicate.extractPublishedVideoId(goodUrl), goodId);
assert.equal(duplicate.extractPublishedVideoId(goodUrl + "?x=1"), goodId);
assert.equal(duplicate.extractPublishedVideoId("https://dzen.ru/a/"+goodId), null);
assert.equal(duplicate.extractPublishedVideoId("https://other.site/video/watch/"+goodId), null);
assert.equal(duplicate.extractPublishedVideoId("https://dzen.ru/video/watch/"+goodId+"evil"), null);
assert.equal(duplicate.pinnedPublishedIdentity({existing:true,publishedVideoUrl:goodUrl},goodId),"MATCH");
assert.equal(duplicate.pinnedPublishedIdentity({existing:true,publishedVideoUrl:goodUrl},otherId),"MISMATCH");
assert.equal(duplicate.pinnedPublishedIdentity({existing:true,publishedVideoUrl:null},goodId),"UNKNOWN");
assert.equal(duplicate.pinnedPublishedIdentity({existing:false,publishedVideoUrl:goodUrl},goodId),"UNKNOWN");

(async () => {
  const candidate = {
    isVisible: async()=>true,
    innerText: async()=>title,
    evaluate: async()=>goodUrl,
  };
  const page = {getByText:()=>({count:async()=>1,nth:()=>candidate})};
  const result = await duplicate.findVisiblePublishedVideo(page,"ИИ-Сводка на 26 октября 2026");
  assert.equal(result.publishedVideoId,goodId);
  assert.equal(result.foundText,title);

  const info = "Видео загружено за 4 сек\nБольше не показывать такие сообщения";
  const robot = "Подтвердите, что вы не робот\nЯ не робот";
  const consent = "Подтвердите, что вы не против\nЯ не против";
  assert.equal(notices.mayAcknowledgeSpeedNotice(info),true);
  assert.equal(notices.mayAcknowledgeSpeedNotice(robot),false);
  assert.equal(notices.mayAcknowledgeSpeedNotice(consent),false);
  assert.equal(notices.mayAcknowledgeSpeedNotice(info+"\n"+robot),false);
  assert.equal(notices.mayAcknowledgeSpeedNotice("Видео загружено за 4 сек"),false);

  let checked=false;let clicks=0;
  const check = {count:async()=>1,isChecked:async()=>checked,
    check:async()=>{checked=true;clicks++;}};
  const titleLoc = {isVisible:async()=>true};
  const labelLoc = {isVisible:async()=>true,
    locator:()=>({locator:()=>check}),
    click:async()=>{clicks++;checked=true;}};
  function makeBrowser(body){
    const frame={
      locator:()=>({innerText:async()=>body}),
      getByText:(t)=>({first:()=>t instanceof RegExp?titleLoc:labelLoc}),
      getByRole:()=>({first:()=>check}),
    };
    return {contexts:()=>[{pages:()=>[{isClosed:()=>false,frames:()=>[frame]}]}]};
  }
  assert.equal((await notices.dismissUploadSpeedNotice(makeBrowser(info))).status,"acknowledged");
  assert.equal(checked,true);
  assert.equal(clicks,1);
  assert.equal((await notices.dismissUploadSpeedNotice(makeBrowser(info))).status,"already-checked");
  assert.equal(clicks,1);
  assert.equal((await notices.dismissUploadSpeedNotice(makeBrowser(robot))).status,"absent");
  assert.equal(clicks,1);
  assert.equal((await notices.dismissUploadSpeedNotice(makeBrowser(info+"\n"+consent))).status,"absent");
  assert.equal(clicks,1);

  const scheduled = fs.readFileSync(path.join(__dirname,"../scheduled-worker.js"),"utf8");
  assert(scheduled.includes("pinnedPublishedIdentity(precheck, pinnedId)"));
  assert(scheduled.includes("identity === \"MATCH\""));
  assert(!scheduled.includes("duplicateGuard.inspectPinnedDraft("),
    "Published result must not reopen draft editor and emit UNKNOWN loops");
  assert(scheduled.includes('status, {\n        lastVerifiedAt:'),
    "Any unknown ID must fail closed, not authorize fresh upload");

  const direct = fs.readFileSync(path.join(__dirname,"../dzen-publish-direct.js"),"utf8");
  assert(direct.includes("dismissUploadSpeedNotice(connection.browser"));
  const runner = fs.readFileSync(path.join(__dirname,"../dzen-browser-runner.js"),"utf8");
  assert(runner.includes("dismissUploadSpeedNotice(browser"));
  assert(runner.includes("findAntiBotChallengePage(browser)"),
    "Manual human verification must not be removed");

  console.log("PASS: 2026-10-26 exact published-video ID and narrow upload-speed preference.");
})().catch((err)=>{console.error(err);process.exitCode=1;});
