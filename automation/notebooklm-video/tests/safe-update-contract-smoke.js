"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const root=path.join(__dirname,"..");
const script=fs.readFileSync(path.join(root,"scripts/install-safe-update.ps1"),"utf8");
const packer=fs.readFileSync(path.join(root,"scripts/build-safe-update.mjs"),"utf8");
const workflow=fs.readFileSync(path.join(root,"../../.github/workflows/video-ci.yml"),"utf8");
for(const n of ["dzen-article-link.js","dzen-article-video.js","dzen-publish-direct.js",
 "dzen-duplicate-guard.js","dzen-browser-runner.js","dzen-safe-notices.js","scheduled-worker.js",
 "full-worker.js","worker.js","video-footer.js","vk-stage.mjs","vk-text.mjs","setup-local.ps1","package.json"]){
 assert(script.includes("'"+n+"'"),"Installer must explicitly allow "+n);
 assert(packer.includes('"'+n+'"'),"Packer must explicitly include "+n);
}
for(const forbidden of ["config.json","state.json","vk-access.json","ftp-access.json",
 "downloads","_bak","browser-profile","worker.log"]){
 const fileList=packer.slice(packer.indexOf("const files=["),packer.indexOf("];",packer.indexOf("const files=["))+2);
 assert(!fileList.includes('"'+forbidden+'"'),"Never include protected operator data: "+forbidden);
}
assert.match(script,/if \(-not \$Apply\)/,"Dry-run must be default");
assert.match(script,/allowedNames/,"Installer must not blindly accept arbitrary filenames from manifest");
assert.match(script,/Get-FileHash.*SHA256/,"Installer must preflight SHA-256");
assert.match(script,/allowedOldSha256/,"Installer must require recognized production version");
assert.match(script,/NotebookLMBot-update-backups/,"Backup must be outside installed root");
assert.match(script,/Rollback|откат/,"Installer must attempt rollback after failure");
assert.match(script,/full-worker\.lock/);
assert.match(script,/scheduled-worker\.lock/);
assert.match(workflow,/package-safe-update:/);
assert.match(workflow,/if: github\.event_name == 'push' && github\.ref == 'refs\/heads\/main'/);
assert.match(workflow,/actions\/upload-artifact@v4/);
console.log("Safe Windows ZIP/update contract: OK");

const setup=fs.readFileSync(path.join(root,"setup-local.ps1"),"utf8");
for(const name of ["video-footer.js","dzen-safe-notices.js"]){
 assert(setup.includes('"'+name+'"'),"Fresh setup must include new runtime dependency "+name);
}
