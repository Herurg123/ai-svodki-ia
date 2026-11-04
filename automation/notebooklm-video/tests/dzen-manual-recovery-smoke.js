"use strict";
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const {spawnSync} = require("node:child_process");

const SOURCE = path.join(__dirname, "..", "dzen-manual-draft-recovery.js");
const DATE = "2026-11-04";
const ID = "6aeaa5486692192b6b893776";

function simulate(mode = "success", args = ["--date=" + DATE, "--assist"], busy = false) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dzen-manual-recovery-"));
  try {
    fs.copyFileSync(SOURCE, path.join(dir, "dzen-manual-draft-recovery.js"));
    const config = {stateFile:path.join(dir,"state.json"),timeZone:"Europe/Moscow"};
    fs.writeFileSync(path.join(dir, "config.json"), JSON.stringify(config));
    fs.writeFileSync(config.stateFile, JSON.stringify({jobs:{old:{
      date:DATE, status:"DONE", dzenAutomation:{
        status:"CLICKED_UNVERIFIED",draftId:ID,clickAttemptedAt:"2026-11-04T03:26:08Z"
      }
    }}}));
    const stubs = {
      "history-utils.js": [
        'const fs=require("fs");',
        'module.exports={parseDateKey:d=>{if(isNaN(Date.parse(d)))throw Error("date");},',
        'loadActiveState:c=>JSON.parse(fs.readFileSync(c.stateFile,"utf8")),',
        'findJobForDateIncludingArchive:(c,s,d)=>({job:s.jobs.old,key:"old",source:"active"}),',
        'saveStateWithRetention:(c,s)=>fs.writeFileSync(c.stateFile,JSON.stringify(s))};'
      ].join(""),
      "dzen-publish.js": 'module.exports={findJobForDate:(s,d)=>s.jobs.old,buildDzenTitle:d=>"ИИ-Сводка на 4 ноября 2026 | Подпишись, чтоб получать свежее!"};',
      "dzen-duplicate-guard.js": [
        'const ID="' + ID + '";let n=0;',
        'module.exports={PUBLICATIONS_URL:"https://dzen.ru/profile/editor/rybv/publications",',
        'titlePrefixForDuplicateCheck:s=>s.split(" | ")[0],',
        'extractPublishedVideoId:u=>(/\\/video\\/watch\\/([a-f0-9]{24})/.exec(u||"")||[])[1]||null,',
        'pinnedPublishedIdentity:(r,id)=>r.existing?(r.publishedVideoUrl.endsWith(id)?"MATCH":"MISMATCH"):"UNKNOWN",',
        'checkBeforeUpload:async()=>{n++;if(process.env.SCENARIO==="success"&&n>1)return {existing:true,publishedVideoUrl:"https://dzen.ru/video/watch/"+ID,foundText:"ИИ-Сводка на 4 ноября 2026"};',
        'if(process.env.SCENARIO==="mismatch")return {existing:true,publishedVideoUrl:"https://dzen.ru/video/watch/aaaaaaaaaaaaaaaaaaaaaaaa"};',
        'return {existing:false};},',
        'inspectPinnedDraft:async()=>process.env.SCENARIO==="unknown"?"UNKNOWN":"PRESENT"};'
      ].join(""),
      "browser-session.js": 'module.exports={launchRobotBrowser:async()=>({primaryPage:{bringToFront:async()=>{}}}),closeRobotBrowser:async()=>{}};',
      "full-worker.js": [
        'const fs=require("fs"),p=require("path").join(__dirname,"full-worker.lock");',
        'module.exports={FULL_WORKER_LOCK_PATH:p,acquireFullWorkerLock:()=>fs.openSync(p,"wx"),',
        'releaseFullWorkerLock:h=>{fs.closeSync(h);fs.unlinkSync(p);}};'
      ].join(""),
      "scheduled-worker.js": 'module.exports={ORCHESTRATOR_LOCK_PATH:require("path").join(__dirname,"scheduled-worker.lock")};',
    };
    for (const [file, body] of Object.entries(stubs)) fs.writeFileSync(path.join(dir,file),body);
    if(busy)fs.writeFileSync(path.join(dir,"scheduled-worker.lock"),"busy");
    const p = spawnSync(process.execPath, [path.join(dir,"dzen-manual-draft-recovery.js"),...args],{
      input:"\n",encoding:"utf8",timeout:12000,env:{...process.env,SCENARIO:mode}
    });
    if(p.error)throw p.error;
    return {status:p.status,stdout:p.stdout,stderr:p.stderr,
      job:JSON.parse(fs.readFileSync(config.stateFile,"utf8")).jobs.old,
      fullLock:fs.existsSync(path.join(dir,"full-worker.lock")),
      scheduledLock:fs.existsSync(path.join(dir,"scheduled-worker.lock"))};
  } finally {fs.rmSync(dir,{recursive:true,force:true});}
}

const readOnly=simulate("success",["--date="+DATE,"--status"]);
assert.equal(readOnly.status,0,readOnly.stderr);
assert.equal(readOnly.job.dzenAutomation.status,"CLICKED_UNVERIFIED");
assert.equal(readOnly.fullLock,false);

const success=simulate();
assert.equal(success.status,0,success.stderr);
assert.match(success.stdout,/PUBLISHED подтверждён/);
assert.equal(success.job.dzenAutomation.status,"PUBLISHED");
assert.equal(success.job.dzenAutomation.draftId,ID);
assert.equal(success.job.dzenAutomation.publishedVideoUrl,"https://dzen.ru/video/watch/"+ID);
assert.equal(success.job.dzenAutomation.confirmedBy,"manual-recovery-exact-public-video-id");
assert.equal(success.fullLock,false);
assert.equal(success.scheduledLock,false);

for(const mode of ["absent","mismatch","unknown"]){
  const failed=simulate(mode);
  assert.notEqual(failed.status,0,mode);
  assert.equal(failed.job.dzenAutomation.status,"CLICKED_UNVERIFIED",mode);
  assert.equal(failed.fullLock,false,mode);
  assert.equal(failed.scheduledLock,false,mode);
}
const blocked=simulate("success",["--date="+DATE,"--assist"],true);
assert.notEqual(blocked.status,0);
assert.equal(blocked.job.dzenAutomation.status,"CLICKED_UNVERIFIED");
assert.equal(blocked.fullLock,false);
const invalid=simulate("success",["--date=garbage","--assist"]);
assert.notEqual(invalid.status,0);
assert.equal(invalid.job.dzenAutomation.status,"CLICKED_UNVERIFIED");

const source=fs.readFileSync(SOURCE,"utf8");
assert(!source.includes(".button.click("),"Recovery must never click Publish");
assert(!source.includes(".check("),"Recovery must never interact with checkbox");
assert(!source.includes("uploadVideoFile("),"Recovery must never upload again");
console.log("PASS: operator-assisted pinned-Dzen recovery; full CLI preflight, exact ID, locks, fail-closed");
