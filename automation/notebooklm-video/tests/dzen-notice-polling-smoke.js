"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const direct = require("../dzen-publish-direct");
const notices = require("../dzen-safe-notices");

const runnerSrc = fs.readFileSync(path.join(__dirname, "../dzen-browser-runner.js"), "utf8");
const directSrc = fs.readFileSync(path.join(__dirname, "../dzen-publish-direct.js"), "utf8");
for (const marker of [
  "waitForOptionalPostClickChallenge",
  "findAntiBotChallengePage",
  "textLooksLikeManualAntiBotChallenge",
  "POST_CLICK_CHALLENGE",
  "restoreRobotBrowserWindow",
  "Я не робот",
  "Я не против",
]) {
  assert(!runnerSrc.includes(marker), `Runner must have no modal-specific wait: ${marker}`);
}
assert(directSrc.includes("safeNotices.processKnownDzenNotices(noticeBrowser"),
  "Published direct child must watch allowlisted notifications within observation");
assert(directSrc.includes("await observeAfterPublishClick(page,config,dateKey,draftId,{noticeBrowser:connection.browser})"));
const block = directSrc.slice(directSrc.indexOf("async function observeAfterPublishClick("),
  directSrc.indexOf("async function findEnabledPublishButton("));
assert(!block.includes("if(sample.challenge)"), "No early stop for manual challenges");
assert(!block.includes(".goto("), "No navigation while observing");
assert(!block.includes(".click("), "No direct post-click UI clicking");
assert(block.includes("if(!page.isClosed())"), "Monitor must continue when editor is closed");

(async () => {
  const notice = "Видео загружено за 4 сек\nБольше не показывать такие сообщения";
  let checked = false;
  let clicks = 0;
  let noticeChecks = 0;
  const checkbox = {
    count:async()=>1,
    isChecked:async()=>checked,
    check:async()=>{checked=true; clicks++;},
  };
  const title = {isVisible:async()=>true};
  const label = {isVisible:async()=>true,locator:()=>({locator:()=>({first:()=>checkbox})})};
  const frame={
    locator:()=>({innerText:async()=>{noticeChecks++;return notice;}}),
    getByText:(t)=>({first:()=>t instanceof RegExp?title:label}),
    getByRole:()=>({first:()=>checkbox}),
  };
  const browser={contexts:()=>[{pages:()=>[{isClosed:()=>false,frames:()=>[frame]}]}]};
  const fakePage={
    isClosed:()=>false,
    url:()=> "https://dzen.ru/profile/editor/rybv/publications",
    locator:()=>({innerText:async()=> "Видео опубликовано"}),
    waitForTimeout:async(ms)=>new Promise(resolve=>setTimeout(resolve,ms)),
    screenshot:async()=>{},
  };
  const originalDispatcher = notices.processKnownDzenNotices;
  let dispatchCalls = 0;
  notices.processKnownDzenNotices = async (...args) => {
    dispatchCalls += 1;
    return originalDispatcher(...args);
  };
  const start=Date.now();
  try {
    await direct.observeAfterPublishClick(fakePage,{}, "2026-10-26",
      "6adec50a38340e44edf6119c",{durationMs:35,intervalMs:5,noticeBrowser:browser});
  } finally {
    notices.processKnownDzenNotices = originalDispatcher;
  }
  assert(Date.now()-start>=30, "Observer must retain bounded observation window");
  assert(dispatchCalls>=2, "Generic dispatcher must run each post-click tick");
  assert.equal(noticeChecks,1, "Known already-attempted preference must not be repeatedly scanned");
  assert.equal(clicks,1, "Exact informational checkbox must be selected no more than once");
  assert.equal(checked,true);

  // A different, user-operated popup is not a condition for prolonging,
  // terminating early, or mutating the post-click flow.
  const unknownPage = {
    ...fakePage,
    url:()=>"https://dzen.ru/profile/editor/rybv/publications?state=draft",
    locator:()=>({innerText:async()=> "Подтвердите, что вы человек"}),
  };
  const startOther=Date.now();
  await direct.observeAfterPublishClick(unknownPage,{}, "2026-10-26",
    "6adec50a38340e44edf6119c",{durationMs:30,intervalMs:5,noticeBrowser:browser});
  assert(Date.now()-startOther>=24, "Unknown popup must not trigger special wait or early abort");
  assert.equal(clicks,1);

  // Dzen may close the editor after publish; notice polling continues in the
  // browser, without waiting on any particular popup.
  let closedPolls=0;
  const closedBrowser={contexts:()=>[{pages:()=>[{isClosed:()=>false,frames:()=>[{
    locator:()=>({innerText:async()=>{closedPolls++;return "";}}),
  }]}]}]};
  await direct.observeAfterPublishClick({
    ...fakePage,isClosed:()=>true
  },{}, "2026-10-26","6adec50a38340e44edf6119c",
  {durationMs:20,intervalMs:5,noticeBrowser:closedBrowser});
  assert(closedPolls>=2,"Closed editor must not stop observation of browser notices");

  assert.equal((await notices.processKnownDzenNotices(null)).status,"absent");
  console.log("PASS: generic Dzen notice polling is timely, bounded and leaves other prompts to user.");
})().catch((e)=>{console.error(e);process.exitCode=1});
