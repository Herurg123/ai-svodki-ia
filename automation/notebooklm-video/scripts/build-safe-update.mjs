#!/usr/bin/env node
// Run only from an authenticated checkout (CI) of the merged main commit.
// Produces a minimal ZIP. It never reads or packages local runtime state.
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import crypto from "node:crypto";
import {execFileSync} from "node:child_process";
import {fileURLToPath} from "node:url";

const here=path.dirname(fileURLToPath(import.meta.url));
const root=path.resolve(here,"../../..");
const sourceDir=path.join(root,"automation/notebooklm-video");
const output=process.argv[2]&&path.resolve(process.argv[2]);
if(!output||!output.endsWith(".zip"))throw Error("Required ZIP output path");
const current=execFileSync("git",["rev-parse","HEAD"],{cwd:root,encoding:"utf8"}).trim();
const expected=process.env.GITHUB_SHA;
if(expected && current!==expected)throw Error("Checkout does not match GitHub workflow SHA");
const baselines=[
  "44de0939c929c9a169be419c6aaf9052a071c8db",
  "b6eebb2e86606c35316a1421b410607297eec355",
];
// Explicit allowlist; intentionally excludes _bak, config/state, secrets,
// browser data, MP4/PNG, logs, Task Scheduler, and operator templates.
const files=[
  "dzen-article-link.js",
  "dzen-article-video.js",
  "dzen-publish-direct.js",
  "full-worker.js",
  "vk-stage.mjs",
  "vk-text.mjs",
  "setup-local.ps1",
  "package.json",
];
const sha256=v=>crypto.createHash("sha256").update(v).digest("hex");
const gitBlob=v=>crypto.createHash("sha1")
 .update(Buffer.from("blob "+v.length+"\0")).update(v).digest("hex");
function baselineBytes(commit,name){
 try{return execFileSync("git",["show",commit+":automation/notebooklm-video/"+name],
  {cwd:root,stdio:["ignore","pipe","ignore"],maxBuffer:3_000_000});}
 catch{return null;}
}
const stage=fs.mkdtempSync(path.join(os.tmpdir(),"notebooklm-safe-update-"));
try{
 const payload=path.join(stage,"payload");
 fs.mkdirSync(payload);
 const entries=[];
 for(const name of files){
  const bytes=fs.readFileSync(path.join(sourceDir,name));
  const fromCommit=execFileSync("git",["show",current+":automation/notebooklm-video/"+name],
   {cwd:root,maxBuffer:3_000_000});
  if(!bytes.equals(fromCommit))throw Error("Worktree differs from HEAD: "+name);
  const old=baselines.map(sha=>baselineBytes(sha,name)).filter(Boolean);
  entries.push({
   file:name,
   newSha256:sha256(bytes),
   newGitBlobSha:gitBlob(bytes),
   allowedOldSha256:[...new Set(old.map(sha256))],
   allowedOldGitBlobShas:[...new Set(old.map(gitBlob))],
   allowAbsent:old.length===0
  });
  fs.writeFileSync(path.join(payload,name),bytes);
 }
 const manifest={
  schema:1,repository:"Herurg123/ai-svodki-ia",
  sourcePath:"automation/notebooklm-video",
  targetSha:current,approvedBaseShas:baselines,
  createdAt:new Date().toISOString(),files:entries,
  safety:"Only explicit code paths; no operator state, tokens, _bak, scheduler or media."
 };
 fs.writeFileSync(path.join(stage,"manifest.json"),JSON.stringify(manifest,null,2)+"\n");
 fs.copyFileSync(path.join(here,"install-safe-update.ps1"),
  path.join(stage,"install-safe-update.ps1"));
 fs.mkdirSync(path.dirname(output),{recursive:true});
 execFileSync("zip",["-q","-r",output,"install-safe-update.ps1","manifest.json","payload"],
  {cwd:stage});
 execFileSync("unzip",["-tq",output],{stdio:"pipe"});
 console.log("SAFE_UPDATE="+output);
 console.log("TARGET_SHA="+current);
 console.log("ZIP_SHA256="+sha256(fs.readFileSync(output)));
 console.log("FILES="+entries.map(e=>e.file).join(","));
}finally{fs.rmSync(stage,{recursive:true,force:true});}
