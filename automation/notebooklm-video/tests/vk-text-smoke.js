"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const {pathToFileURL}=require("node:url");
(async()=>{
 const root=path.join(__dirname,"..");
 const {dateTokens,substituteDate,renderVkTemplate}=await import(pathToFileURL(path.join(root,"vk-text.mjs")).href);
 const source=fs.readFileSync(path.join(root,"vk-publication-template.txt"),"utf8");
 const url="https://dzen.ru/a/articleABC";
 const origin="https://rybalka.one/posts/2026-10-17/";
 const result=renderVkTemplate(source,{date:"2026-10-17",articleUrl:url,publicationUrl:origin});
 assert.equal(result.title,"ИИ-Сводка на 17 октября 2026 | Подпишись, чтоб получать свежее!");
 assert.ok(result.description.includes(origin));
 assert.ok(result.description.includes(url));
 const fallback=renderVkTemplate(source,{date:"2026-10-17",articleUrl:origin,publicationUrl:origin});
 assert.ok(fallback.description.includes(origin));
 assert.equal(fallback.description.split(origin).length-1,1,"fallback cannot duplicate the digest link");
 assert.ok(!fallback.description.includes("% URL сводки этого дня в Дзен %"));
 assert.equal(fallback.storyLinkCaption,result.storyLinkCaption);
 assert.throws(()=>renderVkTemplate(source,{date:"2026-10-17",articleUrl:"https://example.org/a",
   publicationUrl:origin}),/VK ссылка/);
 assert.ok(result.description.includes("#AI #ИИ #НовостиИИ"));
 assert.equal(result.postText,result.title+"\n\n"+result.description);
 assert.equal(result.storyLinkCaption,"ИИ-Сводка на 17 октября 2026");
 for(const text of [result.title,result.description,result.postText])
   assert.doesNotMatch(text,/\+\+\+|YYYY-MM-DD|% URL сводки этого дня в Дзен %/);
 assert.deepEqual(dateTokens("2026-10-17"),{
    "YYYY-MM-DD":"2026-10-17","YYYY":"2026","YY":"26","MMMM":"октября","MM":"10","DD":"17"
 });
 assert.equal(substituteDate("DD MM MMMM YY YYYY YYYY-MM-DD","2026-10-17"),
   "17 10 октября 26 2026 2026-10-17");
 assert.equal(renderVkTemplate(source,{date:"2026-01-03",articleUrl:url,
    publicationUrl:"https://rybalka.one/posts/2026-01-03/"}).storyLinkCaption,
   "ИИ-Сводка на 03 января 2026");
 assert.throws(()=>dateTokens("2026-02-30"),/Несуществующая дата/);
 assert.throws(()=>renderVkTemplate(source,{date:"2026-10-17",articleUrl:url,
    publicationUrl:"https://rybalka.one/posts/2026-10-16/"}),/не соответствует/);
 assert.throws(()=>renderVkTemplate(source.replace("+++ Описание:","+++ NOPE:"),{date:"2026-10-17",
    articleUrl:url,publicationUrl:origin}),/ровно два маркера/);
 assert.throws(()=>renderVkTemplate(source.replace("% URL сводки этого дня в Дзен %",""),{date:"2026-10-17",
    articleUrl:url,publicationUrl:origin}),/ссылка-заглушка|ссылка/);
 console.log("VK text template renderer regression smoke: OK");
})().catch(error=>{console.error(error);process.exitCode=1;});
