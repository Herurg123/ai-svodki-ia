"use strict";
// Production-shaped saved state from the 2026-10-25 Dzen incident:
// a remote draft exists before processing completes. A new upload is forbidden.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const history = require("../history-utils");
const direct = require("../dzen-publish-direct");
const guard = require("../dzen-duplicate-guard");
const scheduled = require("../scheduled-worker");

const firstId = "6adda98499791f7d2cf2804d";
const secondId = "6addadd21796c105c2a4d11a";
const title = "ИИ-Сводка на 25 октября 2026 | Подпишись, чтоб получать свежее!";
const pub = "https://rybalka.one/posts/2026-10-25/";
assert.equal(direct.draftEditorUrl(firstId),
  "https://dzen.ru/profile/editor/rybv/publications?state=draft&videoEditorPublicationId=" + firstId);
assert.throws(() => direct.draftEditorUrl("../bad"), /Неверный ID/);
assert.deepEqual(direct.parseArgs(["--date=2026-10-25","--resume-draft="+firstId]),
  {date:"2026-10-25",resumeDraft:firstId});
assert.throws(() => direct.parseArgs(["--resume-draft=bad"]), /Некорректный ID/);

assert.equal(scheduled.shouldRunFreshUpload("PENDING"), true);
for (const status of ["UPLOAD_ARMED","DRAFT_CREATED","DRAFT_PROCESSING",
 "RETRYABLE_PRE_CLICK","PUBLISH_ARMED","CLICKED_UNVERIFIED","BLOCKED_AMBIGUOUS"]) {
  assert.equal(scheduled.shouldRunFreshUpload(status), false, status);
}
assert.equal(scheduled.shouldResumeDraft("DRAFT_PROCESSING",firstId), true);
assert.equal(scheduled.shouldResumeDraft("CLICKED_UNVERIFIED",firstId), false);
assert.equal(scheduled.shouldResumeDraft("DRAFT_PROCESSING",""), false);

const dir = fs.mkdtempSync(path.join(os.tmpdir(),"dzen-draft-resume-"));
try {
  const mp4Path = path.join(dir,"ИИ-Сводка 2026-10-25.mp4");
  fs.writeFileSync(mp4Path, "offline fixture: only existence is needed for the durable state boundary");
  const config = {stateFile:path.join(dir,"state.json"),workDir:dir,
    timeZone:"Europe/Moscow",history:{enabled:false}};
  const initial = {version:1,jobs:{[pub]:{
    date:"2026-10-25",publicationUrl:pub,status:"DONE",downloadedFile:mp4Path,
    dzenAutomation:{status:"UPLOAD_ARMED"},
  }}};
  fs.writeFileSync(config.stateFile,JSON.stringify(initial));
  // The remote ID is committed before metadata and before any processing wait.
  direct.persistDraftTransition(config,"2026-10-25",firstId,
    ["UPLOAD_ARMED"],"DRAFT_CREATED");
  let current = history.loadActiveState(config);
  assert.equal(current.jobs[pub].dzenAutomation.draftId,firstId);
  assert.equal(current.jobs[pub].dzenAutomation.status,"DRAFT_CREATED");
  assert.throws(() => direct.persistDraftTransition(config,"2026-10-25",secondId,
    ["DRAFT_CREATED"],"DRAFT_PROCESSING"), /заменить закреплённый/);
  direct.persistDraftTransition(config,"2026-10-25",firstId,
    ["DRAFT_CREATED"],"DRAFT_PROCESSING");
  assert.equal(scheduled.shouldResumeDraft(
    history.loadActiveState(config).jobs[pub].dzenAutomation.status,firstId),true);
  // Simulate next scheduled worker run: no new MP4 upload, same draft ID.
  const job = history.loadActiveState(config).jobs[pub];
  const fromDisk = scheduled.syncChildDzenState(config,job);
  assert.equal(fromDisk.draftId,firstId);
  assert.equal(fromDisk.status,"DRAFT_PROCESSING");
  direct.persistDraftTransition(config,"2026-10-25",firstId,
    ["DRAFT_PROCESSING"],"CLICKED_UNVERIFIED",{clickAttemptedAt:"2026-10-25T10:21:07Z"});
  assert.equal(history.loadActiveState(config).jobs[pub].dzenAutomation.status,"CLICKED_UNVERIFIED");
  assert.throws(() => direct.persistDraftTransition(config,"2026-10-25",firstId,
    ["DRAFT_PROCESSING"],"CLICKED_UNVERIFIED"),/Небезопасный переход/);
  assert.equal(scheduled.shouldResumeDraft(
    history.loadActiveState(config).jobs[pub].dzenAutomation.status,firstId),false);
} finally { fs.rmSync(dir,{recursive:true,force:true}); }

// Identity from user's real Studio draft links. A same title is not identity.
const draftUrl = direct.draftEditorUrl(secondId);
assert.equal(guard.summarizeDraftInspection({
  url:draftUrl,bodyText:"Черновики",draftId:secondId,
  titleText:title,expectedTitle:title,modalVisible:true,
}),"PRESENT");
assert.equal(guard.summarizeDraftInspection({
  url:direct.draftEditorUrl(firstId),bodyText:"Черновики",draftId:secondId,
  titleText:title,expectedTitle:title,modalVisible:true,
}),"UNKNOWN");
assert.equal(guard.summarizeDraftInspection({
  url:draftUrl,bodyText:"Черновики",draftId:secondId,
  titleText:"Чужое видео",expectedTitle:title,modalVisible:true,
}),"UNKNOWN");
assert.equal(guard.summarizeDraftInspection({
  url:"https://dzen.ru/profile/editor/rybv/publications?state=draft",
  bodyText:"Черновики",draftId:secondId,titleText:"",expectedTitle:title,
  modalVisible:false,
}),"ABSENT");
assert.equal(guard.summarizeDraftInspection({
  url:"https://dzen.ru/profile/editor/rybv/publications?state=draft",
  bodyText:"Загрузка...",draftId:secondId,titleText:"",expectedTitle:title,
  modalVisible:false,
}),"UNKNOWN");

// The public entrypoint must contain the check BEFORE any publication claim
// and suppress a new upload if a draft is already saved.
const source = fs.readFileSync(path.join(__dirname,"../scheduled-worker.js"),"utf8");
const directSource = fs.readFileSync(path.join(__dirname,"../dzen-publish-direct.js"),"utf8");
const firstArm = source.indexOf('updateDzenAutomation(config, state, job, "UPLOAD_ARMED"');
const freshChild = source.indexOf('dzenRunner.runNodeScript("dzen-publish-direct.js"');
assert(firstArm > 0 && firstArm < freshChild);
const created = directSource.indexOf('"DRAFT_CREATED"');
const metadata = directSource.indexOf("await fillMetadataOnce(page");
assert(created >= 0 && created < metadata);
const armed = directSource.indexOf('persistDraftTransition(config, dateKey, draftId, ["DRAFT_PROCESSING"], "CLICKED_UNVERIFIED"');
const click = directSource.indexOf("await publish.button.click()");
assert(armed >= 0 && armed < click);
assert(directSource.includes("if (resumeDraft) {"));
assert(directSource.includes("await openPinnedDraft(page, config, draftId, title, description)"));
assert(directSource.includes("return { pending: true, draftId };"));
assert(!directSource.includes("Опубликовать после обработки"));
console.log("PASS: Dzen same-draft processing, exact ID check, at-most-once publishing.");
