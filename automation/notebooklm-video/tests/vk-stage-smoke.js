"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const os=require("node:os");
const path=require("node:path");
const {pathToFileURL}=require("node:url");

(async()=>{
  const root=path.resolve(__dirname,"..");
  const {validateInput,ensureSameJob,terminalStatus,storyVerdict,runStage}=
    await import(pathToFileURL(path.join(root,"vk-stage.mjs")).href);
  const {makePostSticker,methodRequest,findExistingVideoByTitle,uploadStoryPng}=await import(
    pathToFileURL(path.join(root,"vk-api.mjs")).href);
  const source=fs.readFileSync(path.join(root,"full-worker.js"),"utf8");
  const configExample=JSON.parse(fs.readFileSync(path.join(root,"config.example.json"),"utf8"));
  const deploy=fs.readFileSync(path.join(root,"setup-local.ps1"),"utf8");
  assert.equal(configExample.vkPublish.automaticEnabled,false,"safe default MUST disable live posting");
  assert.ok(source.indexOf('runNodeScript("vk-stage.mjs"')>source.indexOf('runNodeScript("dzen-article-video.js"'),
    "VK starts strictly after the fourth stage");
  assert.match(source,/candidate\.date === currentDateKey/,"no older-date replay");
  assert.match(source,/!phasesError && !collectionsError && !articleVideoError/,"four stages are the gate");
  assert.match(deploy,/vk-stage\.mjs/,"local installation must copy VK stage");
  assert.match(deploy,/configure-vk-access\.ps1/,"local setup must ship token migration");

  const dir=fs.mkdtempSync(path.join(os.tmpdir(),"vk-stage-contract-"));
  try{
    const video=path.join(dir,"ИИ-Сводка 2026-10-17.mp4"), png=path.join(dir,"ИИ-Сводка 2026-10-17.png");
    const mp4=Buffer.alloc(32);mp4.writeUInt32BE(24,0);mp4.write("ftyp",4,"ascii");mp4.write("isom",8,"ascii");fs.writeFileSync(video,mp4);
    const magic=Buffer.alloc(32);Buffer.from("89504e470d0a1a0a","hex").copy(magic);
    fs.writeFileSync(png,magic);
    const config={workDir:dir,stateFile:path.join(dir,"state.json"),
      regularLog:path.join(dir,"worker.log"),errorLog:path.join(dir,"error.log"),
      timeZone:"Europe/Moscow",historyRetention:{enabled:false},
      vkPublish:{enabled:true,automaticEnabled:true,groupId:240277058,playlistId:1,
        playlistTitle:"Сводки по ИИ",accessFile:path.join(dir,"vk-access.json"),
        templateFile:path.join(root,"vk-publication-template.txt")}};
    const date="2026-10-17";
    const job={date,status:"DONE",downloadedFile:video,previewFile:png,
      publicationUrl:"https://rybalka.one/posts/2026-10-17/",
      publicationTitle:"ИИ-Сводка 17 октября",
      dzenAutomation:{status:"PUBLISHED"},
      dzenCollections:{status:"COMPLETE"},
      dzenArticleVideo:{status:"COMPLETE",articleUrl:"https://dzen.ru/a/articleABC",
        videoUrl:"https://dzen.ru/video/watch/videoABC"}};
    const state={version:1,jobs:{today:job}};
    const args=validateInput(config,job,date);
    const automatic=config.vkPublish.automaticEnabled;
    config.vkPublish.automaticEnabled=false;
    assert.throws(()=>validateInput(config,job,date),/не включён/);
    const manual=validateInput(config,job,date,{manual:true});
    assert.equal(manual.title,args.title,"manual test reads same template with scheduler disabled");
    config.vkPublish.automaticEnabled=automatic;
    const stageSrc=fs.readFileSync(path.join(root,"vk-stage.mjs"),"utf8");
    assert.match(stageSrc,/--confirm=VK-LIVE-/,"manual live needs explicit date-bound confirmation");
    assert.match(stageSrc,/const png=fs\.readFileSync\(args\.cover\)/,"story must use original PNG");
    assert.doesNotMatch(stageSrc,/verticalStoryPng|VK_STORY_CAPTION_B64|ffmpeg-static/,"story image must not be transformed");
    assert.equal(args.cover,png);
    assert.equal(args.title,"ИИ-Сводка на 17 октября 2026 | Подпишись, чтоб получать свежее!");
    assert.ok(args.description.includes("https://dzen.ru/a/articleABC"));
    assert.ok(args.postText.startsWith(args.title+"\n\n"));
    assert.equal(args.storyLinkCaption,"ИИ-Сводка на 17 октября 2026");
    assert.ok(makePostSticker(config.vkPublish.groupId,204).includes('"type":"post"'));
    assert.deepEqual(storyVerdict({id:3,owner_id:-240277058,
      clickable_stickers:{clickable_stickers:[{type:"post",post_owner_id:-240277058,post_id:204}]},
      link:{url:args.article}},240277058,204,args.article),{found:true,post:true,link:true});
    assert.equal(terminalStatus({status:"COMPLETE",phase:"COMPLETE"}),true);
    assert.throws(()=>ensureSameJob({phase:"VIDEO_PUBLISHED",groupId:"1"},args));

    let saves=0,uploads=0,albumAdds=0,posts=0,stories=0,duplicateChecks=0,albumReads=0;
    const client={ownerId:"-240277058",async call(method){
      if(method==="video.save"){saves++;return {video_id:9001,owner_id:"-240277058",upload_url:"https://example.com/upload"};}
      throw Error("Unexpected video method "+method);
    }};
    const dependencies={
      client,token:"not-a-real-token",findDuplicate:async()=>{duplicateChecks++;return null;},
      upload:async()=>{uploads++;},publishVideo:async()=>true,
      confirmVideo:async()=>true,listAlbums:async()=>[{id:1,title:"Сводки по ИИ"}],
      membership:async()=>{albumReads++;return albumAdds?["-2","-1","1"]:["-2","-1"];},
      addToAlbum:async()=>{albumAdds++;return true;},
      uploadStoryPng:async(url,uploadedBytes)=>{
        assert.equal(url,"https://pu.vk.com/upload");
        assert.ok(Buffer.isBuffer(uploadedBytes));
        assert.deepEqual(uploadedBytes,fs.readFileSync(png),"story must upload original PNG bytes");
        return "fixture-upload-result";
      },
      callVk:async(method)=>{
        if(method==="wall.post"){posts++;return {post_id:204};}
        if(method==="stories.getPhotoUploadServer")return {upload_url:"https://pu.vk.com/upload"};
        if(method==="stories.save"){stories++;return {items:[{owner_id:-240277058,id:456239130}]};}
        if(method==="stories.getById")return {items:[{owner_id:-240277058,id:456239130,
          clickable_stickers:{clickable_stickers:[{type:"post",post_owner_id:-240277058,post_id:204}]},
          link:{url:args.article}}]};
        throw Error("unexpected VK method: "+method);
      }
    };
    const result=await runStage(config,job,state,args,dependencies);
    assert.equal(result.status,"COMPLETE");
    assert.equal(job.vkPublication.phase,"COMPLETE");
    assert.equal(job.vkPublication.status,"COMPLETE");
    assert.deepEqual([saves,uploads,albumAdds,posts,stories,duplicateChecks],[1,1,1,1,1,1]);
    const persisted=JSON.parse(fs.readFileSync(config.stateFile,"utf8"));
    assert.equal(persisted.jobs.today.vkPublication.storyId,456239130);
    await runStage(config,job,state,args,dependencies);
    assert.deepEqual([saves,uploads,albumAdds,posts,stories],[1,1,1,1,1],"complete rerun no-op");

    // 19 Oct 2026 incident: the staging upload returned an invalid/unconfirmed
    // response, while a separate diagnostic probe received HTTP 200 + upload_result.
    const pngBytes=fs.readFileSync(png);
    const mockResponse=(status,type,body)=>({
      ok:status>=200&&status<300,status,
      headers:{get:()=>type},text:async()=>body
    });
    const signedValue="a".repeat(502);
    const accepted=await uploadStoryPng("https://pu.vk.com/upload",pngBytes,async()=>mockResponse(
      200,"application/json",JSON.stringify({response:{upload_result:signedValue}})
    ));
    assert.equal(accepted,signedValue);
    await assert.rejects(uploadStoryPng("https://pu.vk.com/upload",pngBytes,
      async()=>mockResponse(200,"text/html","<html>intermittent</html>")),
      /PNG upload: ответ не JSON, HTTP 200, type=text\/html/);
    await assert.rejects(uploadStoryPng("https://pu.vk.com/upload",pngBytes,
      async()=>mockResponse(502,"text/html","bad gateway")),
      /PNG upload: ответ не JSON, HTTP 502/);
    const invalidSigned="SECRET_SIGNED_VALUE".repeat(4000);
    const invalidResult=await uploadStoryPng("https://pu.vk.com/upload",pngBytes,
      async()=>mockResponse(200,"application/json",JSON.stringify({
        response:{upload_result:invalidSigned}
      }))).then(()=>null,e=>e);
    assert.match(invalidResult.message,/signedLength=/);
    assert.ok(!invalidResult.message.includes("SECRET_SIGNED_VALUE"),
      "never write signed upload_result into logs");
    await assert.rejects(uploadStoryPng("https://invalid.example/upload",pngBytes,
      async()=>mockResponse(200,"application/json",'{}')),/Недопустимый сервер/);

    const checkpoint=phase=>({status:"ERROR",phase,date,groupId:args.groupId,
      playlistId:args.playlistId,articleUrl:args.article,videoFile:args.videoFile,
      templateHash:args.templateHash,videoId:"9001",postId:"204"});
    let stagedUploads=0,storySaves=0,storyServerReads=0;
    const replayDeps={...dependencies,
      uploadStoryPng:async(url,bytes)=>{
        stagedUploads++;
        assert.equal(url,"https://pu.vk.com/upload");
        assert.deepEqual(bytes,pngBytes,"recovery must keep exact PNG bytes");
        if(stagedUploads===1)throw new Error("PNG upload: ответ не JSON, HTTP 200");
        return "fixture-resumed-upload-result";
      },
      callVk:async method=>{
        if(method==="stories.getPhotoUploadServer"){storyServerReads++;return {upload_url:"https://pu.vk.com/upload"};}
        if(method==="stories.save"){storySaves++;return {items:[{owner_id:-240277058,id:456239132}]};}
        if(method==="stories.getById")return {items:[{owner_id:-240277058,id:456239132,
          clickable_stickers:{clickable_stickers:[{type:"post",post_owner_id:-240277058,post_id:204}]},
          link:{url:args.article}}]};
        throw Error("recovery must not call "+method);
      }};
    const oldVideoSaves=saves,oldPosts=posts;
    job.vkPublication={...checkpoint("STORY_UPLOAD_REQUESTED"),storyUploadAttempts:1};
    await assert.rejects(runStage(config,job,state,args,replayDeps),/PNG upload: ответ не JSON/);
    assert.equal(job.vkPublication.phase,"STORY_UPLOAD_REQUESTED");
    assert.equal(job.vkPublication.storyUploadAttempts,2);
    assert.equal(storySaves,0,"failed staging must never reach stories.save");
    job.vkPublication.status="ERROR"; // outer main marks a failed stage ERROR
    const replayed=await runStage(config,job,state,args,replayDeps);
    assert.equal(replayed.status,"COMPLETE");
    assert.equal(replayed.storyId,456239132);
    assert.equal(job.vkPublication.storyUploadAttempts,3);
    assert.equal(stagedUploads,2);
    assert.equal(storySaves,1,"stories.save is at most once");
    assert.equal(storyServerReads,2);
    assert.equal(saves,oldVideoSaves,"never create another video");
    assert.equal(posts,oldPosts,"never create another post");
    await runStage(config,job,state,args,replayDeps);
    assert.equal(storySaves,1,"COMPLETE replay must not create a story");
    job.vkPublication={...checkpoint("STORY_UPLOAD_ACK"),storyUploadAttempts:1};
    await runStage(config,job,state,args,replayDeps);
    assert.equal(storySaves,2,"ACK without durable signed result requires a fresh staged upload");
    job.vkPublication={...checkpoint("STORY_UPLOAD_REQUESTED"),storyUploadAttempts:3};
    const beforeExhausted=storyServerReads;
    await assert.rejects(runStage(config,job,state,args,replayDeps),/исчерпаны 3 попытки/);
    assert.equal(storyServerReads,beforeExhausted,"exhausted staging must be fail-closed before API");
    job.vkPublication={...checkpoint("STORY_SAVE_REQUESTED"),storyUploadAttempts:1};
    await assert.rejects(runStage(config,job,state,args,replayDeps),/небезопасный retry|остановлен/);
    assert.equal(storySaves,2,"unknown stories.save result must never be repeated");

    // A timeout AFTER wall.post was sent is not permission for a second post.
    job.vkPublication={status:"PARTIAL",phase:"ALBUM_VERIFIED",date,
      groupId:args.groupId,playlistId:args.playlistId,articleUrl:args.article,
      videoFile:args.videoFile,templateHash:args.templateHash,videoId:"9001"};
    const broken={...dependencies,callVk:async method=>{
      if(method==="wall.post"){posts++;throw Error("network timeout");}
      throw Error("unreachable");
    }};
    await assert.rejects(runStage(config,job,state,args,broken),/timeout/);
    assert.equal(job.vkPublication.phase,"POST_REQUESTED");
    await assert.rejects(runStage(config,job,state,args,broken),/небезопасный retry|остановлен/);
    assert.equal(posts,2,"wall.post must not be retried after a timeout");

    // An uncertain album mutation permits read-only reconciliation, not another mutation.
    job.vkPublication={status:"ERROR",phase:"ALBUM_ADD_REQUESTED",date,
      groupId:args.groupId,playlistId:args.playlistId,articleUrl:args.article,
      videoFile:args.videoFile,templateHash:args.templateHash,videoId:"9001"};
    const missing={...dependencies,membership:async()=>["-1"]};
    await assert.rejects(runStage(config,job,state,args,missing),/повтор запрещён/);
    assert.equal(albumAdds,1);
    // A confirmed existing exact title blocks new upload.
    const duplicate=await findExistingVideoByTitle({ownerId:"-240277058",call:async()=>({
      count:1,items:[{owner_id:-240277058,id:888,title:args.title}]
    })},args.title);
    assert.equal(duplicate,"888");
    const apiError=await methodRequest({method:"stories.get",token:"dummy",fetchImpl:async()=>({
      ok:true,status:200,json:async()=>({error:{error_code:27,error_msg:"Access denied"}})
    })}).then(()=>null,e=>e);
    assert.equal(apiError.code,27);
  }finally{fs.rmSync(dir,{recursive:true,force:true});}
  console.log("VK fifth-stage contract and offline replay smoke: OK");
})().catch(e=>{console.error(e);process.exitCode=1;});
