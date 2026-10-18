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
  const {makePostSticker,methodRequest,findExistingVideoByTitle}=await import(
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
