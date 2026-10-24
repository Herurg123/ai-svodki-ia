/* Fifth local downstream stage. No browser UI automation: CDP is used only to
 * obtain the ephemeral VK Video token from the EXISTING Yandex profile.
 * State transitions are persisted before each external mutation.
 */
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { createHash } from "node:crypto";
import { createRequire } from "node:module";
import { renderVkTemplate } from "./vk-text.mjs";
import { buildVkStoryImage } from "./vk-story-image.mjs";
import { fileURLToPath } from "node:url";
import { VideoClient, methodRequest, uploadVideoChunks, confirmVideo, listAlbums,
  membership, addToAlbum, publishVideo, makePostSticker, uploadStoryPng, findExistingVideoByTitle } from "./vk-api.mjs";

const ROOT=path.dirname(fileURLToPath(import.meta.url));
const require=createRequire(import.meta.url);
const history=require("./history-utils.js");
const logUtils=require("./log-utils.js");

export function validateInput(config,job,date,{manual=false}={}){
  const vk=config.vkPublish||{};
  if(vk.enabled!==true||(vk.automaticEnabled!==true&&!manual))throw new Error("VK не включён в config.json для выбранного режима");
  if(!/^[1-9]\d*$/.test(String(vk.groupId)))throw new Error("VK groupId не задан");
  if(!/^[1-9]\d*$/.test(String(vk.playlistId)))throw new Error("VK playlistId не задан");
  if(typeof vk.playlistTitle!=="string"||!vk.playlistTitle.trim())throw new Error("VK playlistTitle не задан");
  if(!vk.accessFile)throw new Error("VK accessFile не задан");
  if(!vk.templateFile||!path.isAbsolute(vk.templateFile))throw new Error("VK templateFile не задан или не абсолютный");
  if(!fs.existsSync(vk.templateFile)||!fs.statSync(vk.templateFile).isFile())
    throw new Error("VK файл шаблона не найден");
  if(fs.existsSync(config.descriptionFile||"")&&
    fs.realpathSync(vk.templateFile)===fs.realpathSync(config.descriptionFile))
    throw new Error("VK шаблон не должен совпадать с изменяемым файлом описания Дзена");
  if(!job||job.date!==date)throw new Error("VK: нет задания текущей даты");
  // The only permitted VK URL is the independently verified same-day
  // published Dzen ARTICLE, not the origin digest or Dzen video. A previous
  // checkpoint pins exactly that URL and may never be silently rewritten.
  const verified=job.dzenPublishedArticle;
  const article=verified?.status==="VERIFIED" ? verified.url : null;
  if(!/^https:\/\/dzen\.ru\/a\/[A-Za-z0-9_-]+$/.test(article||""))
    throw new Error("VK ожидает проверенный URL опубликованной статьи Дзена за этот день");
  const pinned=job.vkPublication?.articleUrl;
  if(pinned && pinned!==article)
    throw new Error("VK checkpoint закреплён за другой статьёй: повторный запуск запрещён");
  const dzenVideo=job.dzenArticleVideo?.videoUrl||null;
  const videoFile=job.downloadedFile;
  if(!videoFile||path.extname(videoFile).toLowerCase()!==".mp4"||
    !fs.existsSync(videoFile)||fs.statSync(videoFile).size<=0)throw new Error("Локальный MP4 не найден");
  if(!path.basename(videoFile).includes(date))throw new Error("MP4 не соответствует дате выпуска");
  const mp4Stat=fs.statSync(videoFile);
  if(!mp4Stat.isFile())throw new Error("MP4 не является обычным файлом");
  if(job.downloadedSizeBytes!=null&&Number(job.downloadedSizeBytes)!==mp4Stat.size)
    throw new Error("Размер MP4 не совпадает с сохранённым результатом предыдущего этапа");
  const fd=fs.openSync(videoFile,"r");
  try {
    const header=Buffer.alloc(12);const read=fs.readSync(fd,header,0,12,0);
    if(read!==12||header.toString("ascii",4,8)!=="ftyp")
      throw new Error("MP4 не прошёл проверку читаемости и контейнера");
  }finally{fs.closeSync(fd);}
  if(job.downloadedSha256){
    const expected=String(job.downloadedSha256).toLowerCase();
    if(!/^[0-9a-f]{64}$/.test(expected))throw new Error("SHA256 предыдущего этапа некорректен");
    const h=createHash("sha256");
    const fd2=fs.openSync(videoFile,"r");const buffer=Buffer.alloc(1024*1024);
    try {
      let bytes;while((bytes=fs.readSync(fd2,buffer,0,buffer.length,null))>0)
        h.update(buffer.subarray(0,bytes));
    }finally{fs.closeSync(fd2);}
    if(h.digest("hex")!==expected)
      throw new Error("MP4 не совпадает с контрольной SHA256 предыдущего этапа");
  }
  const cover=job.previewFile&&fs.existsSync(job.previewFile)?job.previewFile:
    path.join(path.dirname(videoFile),path.parse(videoFile).name+".png");
  if(!fs.existsSync(cover)||fs.statSync(cover).size<=24||!fs.statSync(cover).isFile())
    throw new Error("Локальный PNG не найден");
  if(path.parse(cover).name!==path.parse(videoFile).name)
    throw new Error("PNG не соответствует текущему MP4");
  const header=fs.readFileSync(cover).subarray(0,24);
  if(!header.subarray(0,8).equals(Buffer.from("89504e470d0a1a0a","hex")))throw new Error("Некорректный PNG");
  const rendered=renderVkTemplate(fs.readFileSync(vk.templateFile,"utf8"),
    {date,articleUrl:article,publicationUrl:job.publicationUrl});
  const {title,description,postText,storyLinkCaption}=rendered;
  const templateHash=createHash("sha256").update([title,description,postText,storyLinkCaption].join("\n")).digest("hex");
  return {groupId:String(vk.groupId),playlistId:String(vk.playlistId),playlistTitle:vk.playlistTitle,
    article,dzenVideo,videoFile,cover,title,description,postText,storyLinkCaption,
    templateHash,date,videoSize:fs.statSync(videoFile).size,accessFile:vk.accessFile};
}
export function ensureSameJob(prior,args){
  if(!prior||!prior.phase)return;
  for(const [key,value] of Object.entries({groupId:args.groupId,playlistId:args.playlistId,
    articleUrl:args.article,videoFile:args.videoFile,date:args.date,templateHash:args.templateHash})){
    if(String(prior[key])!==String(value))throw new Error("VK checkpoint несовместим с данными выпуска: "+key);
  }
}
export function terminalStatus(p){return p?.status==="COMPLETE"&&p.phase==="COMPLETE";}
export function storyVerdict(s,groupId,postId,articleUrl){
  if(!s||Number(s.owner_id)!==-Number(groupId)||!Number.isSafeInteger(Number(s.id)))return {found:false};
  const stickers=s.clickable_stickers?.clickable_stickers||s.clickable_stickers||[];
  const post=Array.isArray(stickers)&&stickers.some(x=>x?.type==="post"&&
    Number(x.post_owner_id)===-Number(groupId)&&Number(x.post_id)===Number(postId));
  const link=s.link?.url===articleUrl||
    (Array.isArray(stickers)&&stickers.some(x=>x?.type==="link"&&x.link_object?.url===articleUrl));
  return {found:true,post,link};
}
function cleanError(err){
  return String(err?.message||err||"Неизвестная ошибка")
    .replace(/(access_token|token|sig|key|hash|upload_result)=([^\s&]+)/gi,"$1=[REDACTED]")
    .replace(/vk\d+\.[A-Za-z0-9_-]+/gi,"[TOKEN]").slice(0,300);
}
function logger(config,text,error=false){
  const line="["+logUtils.formatTime(config.timeZone)+"] VK: "+text;
  (error?console.error:console.log)(line);
  logUtils.appendRegularLine(config,line);
  if(error&&config.errorLog!==config.regularLog)logUtils.appendErrorLine(config,line);
}
async function unprotectToken(file){
  const data=JSON.parse(fs.readFileSync(file,"utf8").replace(/^\uFEFF/,""));
  if(data.protocol!==1||typeof data.tokenDpapi!=="string"||!data.tokenDpapi)throw new Error("Нужен защищённый vk-access.json protocol=1");
  if(process.platform!=="win32")throw new Error("VK token DPAPI доступен только на Windows");
  const code=[
    "$ErrorActionPreference='Stop'",
    "Add-Type -AssemblyName System.Security",
    "$raw=[Console]::In.ReadToEnd().Trim()",
    "$plain=[Security.Cryptography.ProtectedData]::Unprotect([Convert]::FromBase64String($raw),$null,[Security.Cryptography.DataProtectionScope]::CurrentUser)",
    "[Console]::Out.Write([Text.Encoding]::UTF8.GetString($plain))"
  ].join(";");
  return new Promise((resolve,reject)=>{
    const child=spawn("powershell.exe",["-NoLogo","-NoProfile","-NonInteractive","-EncodedCommand",Buffer.from(code,"utf16le").toString("base64")],
      {stdio:["pipe","pipe","pipe"],windowsHide:true});
    let stdout="",stderr="";
    child.stdout.on("data",x=>{stdout+=x.toString();if(stdout.length>4096)child.kill();});
    child.stderr.on("data",x=>{stderr+=x.toString();});
    child.once("error",()=>reject(new Error("DPAPI PowerShell не запущен")));
    child.once("close",status=>{
      if(status!==0||stdout.length<20)reject(new Error("DPAPI: не удалось прочитать VK token"));
      else resolve(stdout.trim());
    });
    child.stdin.end(data.tokenDpapi);
  });
}
async function runStage(config,job,state,args,dependencies={}){
  let p=job.vkPublication||{};
  ensureSameJob(p,args);
  if(terminalStatus(p))return {status:"COMPLETE",videoId:p.videoId,postId:p.postId,storyId:p.storyId};
  const save=(phase,extra={})=>{
    p={...p,status:"PARTIAL",date:args.date,groupId:args.groupId,playlistId:args.playlistId,
      articleUrl:args.article,videoFile:args.videoFile,templateHash:args.templateHash,phase,...extra,updatedAt:new Date().toISOString()};
    job.vkPublication=p;job.updatedAt=p.updatedAt;
    history.saveStateWithRetention(config,state);
    logger(config,"5: phase="+phase+(p.videoId?" videoId="+p.videoId:"")+
      (p.postId?" postId="+p.postId:"")+(p.storyId?" storyId="+p.storyId:""));
  };
  const log=message=>logger(config,message);
  const client=dependencies.client||new VideoClient({groupId:args.groupId,
    port:Number(config.browserDebugPort),logger:log});
  const vk=dependencies.callVk||((method,params)=>methodRequest({method,params,token:dependencies.token}));
  if(!p.phase)save("PREPARED");
  if(p.phase==="PREPARED"){
    const duplicate=await (dependencies.findDuplicate||findExistingVideoByTitle)(client,args.title);
    if(duplicate)throw new Error("VK: такое название уже опубликовано, videoId="+duplicate+"; новый upload запрещён");
    save("VIDEO_SAVE_REQUESTED");
    const created=await client.call("video.save",{
      group_id:args.groupId,file_size:String(args.videoSize),batch_id:"-"+args.groupId+"_"+Date.now(),
      preview:"1",thumb_upload:"1",toggles:"1",source_file_name:path.basename(args.videoFile)
    },false);
    if(!/^[1-9]\d*$/.test(String(created?.video_id))||String(created.owner_id)!=="-"+args.groupId||
      !created.upload_url)throw new Error("video.save не подтвердил создание видео");
    save("VIDEO_CREATED",{videoId:String(created.video_id)});
    await (dependencies.upload||uploadVideoChunks)({
      url:created.upload_url,file:args.videoFile,size:args.videoSize,logger:log
    });
    save("VIDEO_UPLOADED");
  }
  if(p.phase==="VIDEO_UPLOADED"){
    save("VIDEO_PUBLISH_REQUESTED");
    await (dependencies.publishVideo||publishVideo)(client,{videoId:p.videoId,title:args.title,description:args.description});
    save("VIDEO_PUBLISHED");
  }
  if(p.phase==="VIDEO_PUBLISHED"||p.phase==="ALBUM_ADD_REQUESTED"||p.phase==="ALBUM_ADD_ACK"){
    await (dependencies.confirmVideo||confirmVideo)(client,p.videoId);
    const albums=await (dependencies.listAlbums||listAlbums)(client);
    const exact=albums.find(x=>String(x.id)===args.playlistId&&String(x.title)===args.playlistTitle);
    if(!exact)throw new Error("Не найден точный плейлист: "+args.playlistTitle);
    const ids=await (dependencies.membership||membership)(client,p.videoId);
    if(ids.includes(args.playlistId)) save("ALBUM_VERIFIED");
    else if(p.phase==="VIDEO_PUBLISHED"){
      save("ALBUM_ADD_REQUESTED");
      await (dependencies.addToAlbum||addToAlbum)(client,p.videoId,args.playlistId);
      save("ALBUM_ADD_ACK");
      const after=await (dependencies.membership||membership)(client,p.videoId);
      if(!after.includes(args.playlistId))throw new Error("video.addToAlbum не подтверждён повторным чтением");
      save("ALBUM_VERIFIED");
    }else throw new Error("Результат добавления в плейлист неизвестен; повтор запрещён");
  }
  if(p.phase==="ALBUM_VERIFIED"){
    const guid="svodki-vk-"+args.groupId+"-"+args.date;
    save("POST_REQUESTED",{postGuid:guid});
    const ack=await vk("wall.post",{owner_id:"-"+args.groupId,from_group:"1",message:args.postText,
      attachments:"video-"+args.groupId+"_"+p.videoId,guid});
    if(!/^[1-9]\d*$/.test(String(ack?.post_id)))throw new Error("wall.post не вернул post_id; повтор запрещён");
    save("POST_ACK",{postId:String(ack.post_id)});
  }
  if(["POST_ACK","STORY_UPLOAD_REQUESTED","STORY_UPLOAD_ACK"].includes(p.phase)){
    // Only staged PNG uploads may be retried. stories.save MUST remain at-most-once.
    // A retry obtains a new signed upload_result; do not persist the signed value.
    const uploadAttempts=p.storyUploadAttempts===undefined?0:p.storyUploadAttempts;
    if(!Number.isSafeInteger(uploadAttempts)||uploadAttempts<0||uploadAttempts>3)
      throw new Error("VK: некорректный счётчик загрузок PNG");
    if(uploadAttempts===3)
      throw new Error("VK: исчерпаны 3 попытки загрузки PNG; stories.save не вызывался");
    // Derivative ONLY for VK Story: sharp full original over a blurred portrait backdrop.
    // The source cover stays untouched for NotebookLM, FTP and Dzen.
    const storyCover=await (dependencies.buildVkStoryImage||buildVkStoryImage)(args.cover);
    const png=fs.readFileSync(storyCover);
    if(!png.length||png.length>10*1024*1024)throw new Error("PNG истории пустой или слишком большой");
    log("5: PNG истории: вертикальный файл "+storyCover+" ("+png.length+" байт), исходный PNG не изменён");
    const stickers=makePostSticker(args.groupId,p.postId);
    const reply=await vk("stories.getPhotoUploadServer",{
      group_id:args.groupId,add_to_news:"1",clickable_stickers:stickers,
      link_text:"read",link_url:args.article
    });
    if(!reply?.upload_url)throw new Error("VK Stories не выдал upload_url");
    save("STORY_UPLOAD_REQUESTED",{storyUploadAttempts:uploadAttempts+1});
    const signed=await (dependencies.uploadStoryPng||uploadStoryPng)(reply.upload_url,png);
    save("STORY_UPLOAD_ACK");
    save("STORY_SAVE_REQUESTED");
    const response=await vk("stories.save",{upload_results:signed});
    const item=response?.items?.find(x=>String(x?.owner_id)==="-"+args.groupId&&
      Number.isSafeInteger(x.id)&&x.id>0);
    if(!item)throw new Error("stories.save не подтвердил storyId; повтор запрещён");
    save("STORY_SAVE_ACK",{storyId:item.id});
  }
  if(p.phase==="STORY_SAVE_ACK"){
    const reply=await vk("stories.getById",{stories:"-"+args.groupId+"_"+p.storyId});
    const story=reply?.items?.find(x=>String(x?.owner_id)==="-"+args.groupId&&x.id===p.storyId);
    const result=storyVerdict(story,args.groupId,p.postId,args.article);
    if(!result.found||!result.post||!result.link)
      throw new Error("VK Stories: пост/ссылка не подтверждены API, нужна ручная проверка, повтор запрещён");
    save("COMPLETE",{status:"COMPLETE",verification:result});
    log("5: VK COMPLETE video="+p.videoId+" post="+p.postId+" story="+p.storyId);
  }
  if(p.phase!=="COMPLETE")
    throw new Error("VK остановлен в фазе "+p.phase+"; небезопасный retry запрещён");
  return {status:"COMPLETE",videoId:p.videoId,postId:p.postId,storyId:p.storyId};
}
export {runStage};
export async function main(){
  const configPath=path.join(ROOT,"config.json");
  const config=JSON.parse(fs.readFileSync(configPath,"utf8").replace(/^\uFEFF/,""));
  const dateArg=process.argv.find(x=>x.startsWith("--date="));
  const date=dateArg?.slice(7);
  const apply=process.argv.includes("--apply");
  if(!/^\d{4}-\d{2}-\d{2}$/.test(date||""))throw new Error("Нужен --date=YYYY-MM-DD");
  const state=history.loadActiveState(config);
  const match=history.findJobForDateIncludingArchive(config,state,date);
  if(!match?.job)throw new Error("VK: задание не найдено");
  const job=match.job;
  if(!apply){
    const stateOnly=process.argv.includes("--status");
    if(stateOnly){
      console.log(JSON.stringify(job.vkPublication||{phase:"NOT_STARTED"},null,2));return;
    }
    const args=validateInput(config,job,date,{manual:process.argv.includes("--manual")||!apply});
    ensureSameJob(job.vkPublication,args);
    await unprotectToken(args.accessFile);
    const sourcePng=fs.readFileSync(args.cover);
    if(sourcePng.length>10*1024*1024)throw new Error("PNG истории слишком большой");
    console.log("=== VK ПРЕДПРОСМОТР БЕЗ СЕТИ ===");
    console.log("DPAPI VK-токен: успешно расшифрован; значение не выводится.");
    console.log("История: отдельный портретный -vk.png из исходного PNG.");
    console.log("Дата:",date,"Группа:",args.groupId,"Плейлист:",args.playlistTitle);
    console.log("MP4:",args.videoFile,"байт:",args.videoSize);
    console.log("PNG:",args.cover);
    console.log("Ссылка для VK (заморожена в checkpoint после старта):",args.article);
    console.log("Название видео:\n"+args.title);
    console.log("Описание видео:\n"+args.description);
    console.log("Текст поста:\n"+args.postText);
    console.log("Кнопка ссылки VK: Читать");
    console.log("Статус:",job.vkPublication?.phase||"NOT_STARTED");
    console.log("Это чтение локальных данных. Публикаций нет.");
    return;
  }
  if(process.argv.includes("--manual")&&
    !process.argv.includes("--confirm=VK-LIVE-"+date))
    throw new Error("Для ручной публикации нужен --confirm=VK-LIVE-"+date);
  const today=new Intl.DateTimeFormat("en-CA",{timeZone:config.timeZone||"Europe/Moscow",year:"numeric",month:"2-digit",day:"2-digit"}).format(new Date());
  if(date!==today)throw new Error("VK: прошедшие выпуски не публикуем автоматически");
  const args=validateInput(config,job,date,{manual:process.argv.includes("--manual")||!apply});
  ensureSameJob(job.vkPublication,args);
  if(terminalStatus(job.vkPublication)){logger(config,"5: VK уже COMPLETE; пропуск");return;}
  const lockedPhases=["VIDEO_SAVE_REQUESTED","VIDEO_CREATED","VIDEO_PUBLISH_REQUESTED",
    "POST_REQUESTED","STORY_SAVE_REQUESTED"];
  if(lockedPhases.includes(job.vkPublication?.phase))throw new Error(
    "VK: неопределённая предыдущая мутация "+job.vkPublication.phase+"; автоматическое повторение запрещено"
  );
  const browserSession=require("./browser-session.js");
  const browser=config.browserDebugHost;
  if(browser!=="127.0.0.1"&&browser!=="localhost")throw new Error("VK CDP должен быть локальным");
  const token=await unprotectToken(args.accessFile);
  let session=null;
  try{
    if(!(await browserSession.cdpIsAvailable(config))){
      session=await browserSession.launchRobotBrowser(config,{log:x=>logger(config,x)});
    }
    try {
      await runStage(config,job,state,args,{token});
    } catch (error) {
      // Keep the exact phase, but make the failure visible through shared state.
      if (job.vkPublication) {
        job.vkPublication.status="ERROR";
        job.vkPublication.lastError=cleanError(error);
        job.vkPublication.updatedAt=new Date().toISOString();
        history.saveStateWithRetention(config,state);
      }
      logger(config,"5: остановка: "+cleanError(error),true);
      throw error;
    }
  }finally{
    if(session)await browserSession.closeRobotBrowser(session,config);
  }
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  main().catch(error=>{
    // full-worker.js catches exit != 0 and logs through shared errorLog.
    console.error("VK stage: "+cleanError(error));
    process.exitCode=1;
  });
}
