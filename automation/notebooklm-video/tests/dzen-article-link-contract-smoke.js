"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const ROOT=path.join(__dirname,"..");
const link=require(path.join(ROOT,"dzen-article-link.js"));
const article=require(path.join(ROOT,"dzen-article-video.js"));
const flow=fs.readFileSync(path.join(ROOT,"full-worker.js"),"utf8");
const source=fs.readFileSync(path.join(ROOT,"dzen-article-video.js"),"utf8");
const url="https://dzen.ru/a/currentArticle";
const date="2026-10-24";
assert.equal(link.validArticleUrl(url),true);
for(const bad of [null,"https://rybalka.one/posts/2026-10-24/",
 "http://dzen.ru/a/currentArticle","https://dzen.ru/video/watch/x",
 "https://dzen.ru/a/x?other=1"])assert.equal(link.validArticleUrl(bad),false);
assert.equal(link.verifiedArticleUrl({dzenPublishedArticle:{status:"VERIFIED",url}}),url);
assert.equal(link.verifiedArticleUrl({dzenPublishedArticle:{status:"PENDING",url}}),null);
assert.equal(link.verifiedArticleUrl({dzenPublishedArticle:{status:"VERIFIED",
 url:"https://rybalka.one/posts/2026-10-24/"}}),null);
assert.equal(link.getDateArg(["--date="+date]),date);
assert.throws(()=>link.getDateArg(["--date=2026-02-30"]),/Некорректная дата/);
assert.throws(()=>link.getDateArg(["--date="+date,"--apply"]),/Использование/);

const dir=fs.mkdtempSync(path.join(os.tmpdir(),"dzen-article-link-"));
try{
 const config={stateFile:path.join(dir,"state.json"),historyRetention:{enabled:false}};
 const job={date,status:"DOWNLOADED",dzenAutomation:{status:"CLICKED_UNVERIFIED"},
  dzenCollections:{status:"PENDING"},dzenArticleVideo:{status:"PENDING"}};
 const state={version:1,jobs:{today:job}};
 assert.equal(link.verifiedArticleUrl(job),null);
 assert.throws(()=>link.persistVerifiedArticle(config,state,job,"2026-10-23",url),/URL\/date/);
 assert.throws(()=>link.persistVerifiedArticle(config,state,job,date,
  "https://rybalka.one/posts/2026-10-24/"),/URL\/date/);
 assert.equal(fs.existsSync(config.stateFile),false,"invalid links must never change state");
 link.persistVerifiedArticle(config,state,job,date,url);
 assert.equal(job.dzenPublishedArticle.status,"VERIFIED");
 assert.equal(job.dzenPublishedArticle.url,url);
 assert.equal(job.dzenAutomation.status,"CLICKED_UNVERIFIED");
 assert.equal(job.dzenArticleVideo.status,"PENDING","independent link resolution must not edit embed state");
 assert.equal(JSON.parse(fs.readFileSync(config.stateFile,"utf8")).jobs.today.dzenPublishedArticle.url,url);
 assert.throws(()=>link.persistVerifiedArticle(config,state,job,date,
  "https://dzen.ru/a/another"),/изменился/);
 job.vkPublication={phase:"STORY_UPLOAD_ACK",articleUrl:url};
 link.persistVerifiedArticle(config,state,job,date,url);
 job.vkPublication.articleUrl="https://rybalka.one/posts/2026-10-24/";
 assert.throws(()=>link.persistVerifiedArticle(config,state,job,date,url),/checkpoint отличается/);
}finally{fs.rmSync(dir,{recursive:true,force:true});}
assert.equal(typeof article.resolvePublishedArticleUrl,"function");
const readOnlyStart=source.indexOf("async function resolvePublishedArticleUrl");
const readOnlyEnd=source.indexOf("async function resolveLinks",readOnlyStart);
assert(readOnlyStart>0&&readOnlyEnd>readOnlyStart);
const body=source.slice(readOnlyStart,readOnlyEnd);
assert.match(body,/Опубликованные/);
assert.match(body,/ensurePublicationFilter\(page, "Статьи"\)/);
assert.match(body,/findPublicationRow\(page, dateKey, "article"/);
assert.match(body,/copyPublicationUrl\(page, row, "article"/);
assert.match(body,/publicPage\.goto\(url/);
assert.match(body,/text\.includes\(expected\) \|\| title\.includes\(expected\)/);
for(const forbidden of ["setInputFiles(", "updateArticleVideo(", "runApply(", "page.fill("])
 assert(!body.includes(forbidden),"read-only finder cannot mutate content: "+forbidden);
assert.match(flow,/runNodeScript\("dzen-article-link\.js"/);
assert.match(flow,/articleLink\.verifiedArticleUrl\(verifiedJob\)/);
assert(!flow.includes("vkPublish.automaticEnabled !== true"),"VK config must stay unchanged");
console.log("Published Dzen article URL contract: OK");
