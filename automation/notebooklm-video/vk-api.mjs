/* VK API transport. Only the existing protected Yandex CDP profile is used.
 * VK Video endpoints below are observed, non-public VK Video web API.
 * Do not change their client_id/version without a new controlled live test.
 */
import { open, stat } from "node:fs/promises";
import { basename } from "node:path";

const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
const VIDEO_BASE = "https://api.vkvideo.ru";
const VK_BASE = "https://api.vk.com";
const DASHBOARD = "https://cabinet.vkvideo.ru/";
const CHUNK = 4 * 1024 * 1024;

export class VkApiError extends Error {
  constructor(method, code) {
    super(method + ": VK API error " + code);
    this.code = code;
  }
}
export async function methodRequest({method, token, params = {}, video = false, fetchImpl = fetch}) {
  const base = video ? VIDEO_BASE : VK_BASE;
  const url = new URL("/method/" + method, base);
  url.searchParams.set("v", video ? "5.289" : "5.199");
  if (video) url.searchParams.set("client_id", "52461373");
  const res = await fetchImpl(url, {
    method:"POST", redirect:"error",
    headers:{"Content-Type":"application/x-www-form-urlencoded"},
    body:new URLSearchParams({...params,access_token:token}),
    signal:AbortSignal.timeout(30000)
  });
  let json;
  try { json = await res.json(); } catch { throw new Error(method + ": ответ не JSON, HTTP " + res.status); }
  if (json?.error) throw new VkApiError(method, Number(json.error.error_code));
  if (!res.ok || json?.response == null) throw new Error(method + ": ответ не подтверждён, HTTP " + res.status);
  return json.response;
}
class Cdp {
  constructor(ws) {
    this.ws=ws; this.seq=1; this.pending=new Map(); this.onEvent=()=>{};
    ws.addEventListener("message", e=>{
      let d; try {d=JSON.parse(e.data);} catch {return;}
      if (typeof d.id === "number") {
        const p=this.pending.get(d.id); if(!p)return;
        this.pending.delete(d.id);clearTimeout(p.timer);
        if(d.error)p.reject(new Error("CDP command failed"));else p.resolve(d.result||{});
      } else if(d.method) this.onEvent(d);
    });
    ws.addEventListener("close",()=>{
      for(const p of this.pending.values()){clearTimeout(p.timer);p.reject(new Error("CDP disconnected"));}
      this.pending.clear();
    });
  }
  call(method,params={},sessionId=null,timeout=12000){
    const id=this.seq++;
    return new Promise((resolve,reject)=>{
      const timer=setTimeout(()=>{this.pending.delete(id);reject(new Error("CDP timeout: "+method));},timeout);
      this.pending.set(id,{resolve,reject,timer});
      try {this.ws.send(JSON.stringify({id,method,params,...(sessionId?{sessionId}:{})}));}
      catch(e){clearTimeout(timer);this.pending.delete(id);reject(new Error("CDP send failed"));}
    });
  }
}
function tokenRequest(url) {
  try {
    const u=new URL(url);
    return u.protocol==="https:" &&
      ["cabinet.vkvideo.ru","vkvideo.ru","vk.com","vk.ru"].includes(u.hostname) &&
      u.pathname==="/al_video.php" && u.searchParams.get("act")==="web_token";
  }catch{return false;}
}
export async function acquireVideoToken({port=9222,fetchImpl=fetch,timeoutMs=60000}={}){
  if(!Number.isSafeInteger(Number(port))||Number(port)<1||Number(port)>65535)throw new Error("Некорректный CDP port");
  const metaRes=await fetchImpl("http://127.0.0.1:"+port+"/json/version",{signal:AbortSignal.timeout(7000)});
  if(!metaRes.ok)throw new Error("CDP недоступен");
  const meta=await metaRes.json();
  const wsUrl=meta.webSocketDebuggerUrl;
  if(!new RegExp("^ws://(?:127\\.0\\.0\\.1|localhost):"+port+"/").test(String(wsUrl)))throw new Error("CDP вернул внешний адрес");
  const ws=new WebSocket(wsUrl);
  await new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error("CDP WebSocket timeout")),10000);
    ws.addEventListener("open",()=>{clearTimeout(timer);resolve();},{once:true});
    ws.addEventListener("error",()=>{clearTimeout(timer);reject(new Error("CDP WebSocket failed"));},{once:true});
  });
  const cdp=new Cdp(ws);
  let targetId;
  try{
    const target=await cdp.call("Target.createTarget",{url:"about:blank"});targetId=target.targetId;
    const attached=await cdp.call("Target.attachToTarget",{targetId,flatten:true});
    const session=attached.sessionId;if(!session)throw new Error("CDP session unavailable");
    const requests=new Set();
    let resolveToken;
    const tokenPromise=new Promise(resolve=>resolveToken=resolve);
    let accepted=false;
    cdp.onEvent=async e=>{
      if(accepted||e.sessionId!==session)return;
      const p=e.params||{};
      if(e.method==="Network.responseReceived"){
        if(p.response?.status===200&&tokenRequest(p.response.url))requests.add(p.requestId);
      }else if(e.method==="Network.loadingFinished"&&requests.delete(p.requestId)){
        try{
          const r=await cdp.call("Network.getResponseBody",{requestId:p.requestId},session);
          const raw=r.base64Encoded?Buffer.from(r.body,"base64").toString("utf8"):r.body;
          const json=JSON.parse(raw.replace(/^for\s*\(\s*;\s*;\s*\)\s*;?\s*/,""));
          const data=Array.isArray(json)?json[0]:(json?.response||json);
          if(typeof data?.access_token==="string"&&data.access_token.length>25){
            accepted=true;resolveToken({token:data.access_token,expiresAt:Number(data.expires)*1000});
          }
        }catch{/* never log token-containing responses */}
      }
    };
    await cdp.call("Network.enable",{},session);
    await cdp.call("Page.enable",{},session);
    await cdp.call("Page.navigate",{url:DASHBOARD},session);
    const reply=await Promise.race([tokenPromise,sleep(timeoutMs).then(()=>null)]);
    if(!reply?.token||reply.expiresAt<Date.now()+60000)throw new Error("VK Video web token не получен или истёк");
    return reply;
  }finally{
    if(targetId)try{await cdp.call("Target.closeTarget",{targetId},null,5000);}catch{}
    try{ws.close();}catch{}
  }
}
export class VideoClient {
  constructor({groupId,port=9222,fetchImpl=fetch,logger=()=>{}}={}){
    if(!/^[1-9]\d*$/.test(String(groupId)))throw new Error("Некорректный VK_GROUP_ID");
    this.groupId=String(groupId);this.ownerId="-"+groupId;this.port=port;
    this.fetchImpl=fetchImpl;this.logger=logger;this.token=null;
  }
  async call(method,params={},retryAuth=true){
    if(!this.token||this.token.expiresAt<Date.now()+120000)
      this.token=await acquireVideoToken({port:this.port,fetchImpl:this.fetchImpl});
    try{return await methodRequest({method,params,token:this.token.token,video:true,fetchImpl:this.fetchImpl});}
    catch(e){
      if(retryAuth&&e instanceof VkApiError&&e.code===5){
        this.token=await acquireVideoToken({port:this.port,fetchImpl:this.fetchImpl});
        return methodRequest({method,params,token:this.token.token,video:true,fetchImpl:this.fetchImpl});
      }
      throw e;
    }
  }
}
export async function uploadVideoChunks({url,file,size,fetchImpl=fetch,logger=()=>{}}){
  const u=new URL(url);
  if(u.protocol!=="https:"||!["mycdn.me","okcdn.ru"].some(x=>u.hostname===x||u.hostname.endsWith("."+x)))
    throw new Error("Недопустимый сервер загрузки видео");
  const handle=await open(file,"r");let coverage="";
  try{
    const total=Math.ceil(size/CHUNK);
    for(let i=0;i<total;i++){
      const start=i*CHUNK, end=Math.min(size-1,start+CHUNK-1);
      const buf=Buffer.alloc(end-start+1);
      let off=0;
      while(off<buf.length){
        const {bytesRead}=await handle.read(buf,off,buf.length-off,start+off);
        if(!bytesRead)throw new Error("MP4 стал недоступен");
        off+=bytesRead;
      }
      let ok=false;
      for(let attempt=0;attempt<3&&!ok;attempt++){
        try{
          const res=await fetchImpl(u,{
            method:"POST",redirect:"error",
            headers:{"Content-Type":"video/mp4","Content-Range":"bytes "+start+"-"+end+"/"+size,
              "Content-Disposition":"attachment; filename="+encodeURIComponent(basename(file)),
              "Origin":"https://cabinet.vkvideo.ru"},
            body:buf,signal:AbortSignal.timeout(90000)
          });
          const body=await res.text();
          if(![200,201,202,204].includes(res.status))throw new Error("HTTP "+res.status);
          coverage=body+","+String(res.headers.get("range")||"");
          logger("MP4 блок "+(i+1)+"/"+total+" HTTP "+res.status);
          ok=true;
        }catch(e){
          if(attempt===2)throw new Error("Загрузка блока "+(i+1)+" не подтверждена");
          await sleep(1500*(attempt+1));
        }
      }
    }
  }finally{await handle.close();}
  const ranges=[...coverage.matchAll(/(\d+)-(\d+)\/(\d+)/g)].map(m=>m.slice(1).map(Number))
    .filter(r=>r[2]===size).sort((a,b)=>a[0]-b[0]);
  let cursor=0;
  for(const [start,end] of ranges){if(start>cursor)break;cursor=Math.max(cursor,end+1);}
  if(cursor!==size)throw new Error("Сервер не подтвердил полный диапазон MP4");
}
function parseId(v){const x=String(v??"");if(!/^[1-9]\d*$/.test(x))throw new Error("VK ID отсутствует");return x;}
export async function confirmVideo(client,videoId){
  const id=parseId(videoId);
  const result=await client.call("video.get",{videos:client.ownerId+"_"+id});
  const items=Array.isArray(result)?result:result?.items;
  if(!Array.isArray(items)||!items.some(x=>String(x.owner_id)===client.ownerId&&String(x.id??x.video_id)===id))
    throw new Error("video.get не подтвердил видео");
  return true;
}
export async function listAlbums(client){
  const res=await client.call("video.getAlbums",{owner_id:client.ownerId,count:"100"});
  if(!Array.isArray(res?.items)||!Number.isInteger(Number(res.count))||Number(res.count)>res.items.length)
    throw new Error("Список плейлистов неполон или неверен");
  return res.items;
}
export async function membership(client,videoId){
  const res=await client.call("video.getAlbumsByVideo",{
    target_id:client.ownerId,owner_id:client.ownerId,video_id:parseId(videoId),extended:"0"
  });
  if(!Array.isArray(res))throw new Error("Неизвестная форма списка плейлистов");
  return res.map(x=>{
    if(!Number.isSafeInteger(x))throw new Error("Неверный ID плейлиста");
    return String(x);
  });
}
export async function addToAlbum(client,videoId,albumId){
  const id=parseId(albumId);
  return client.call("video.addToAlbum",{
    target_id:client.ownerId,owner_id:client.ownerId,video_id:parseId(videoId),album_id:id
  },false);
}
export async function publishVideo(client,{videoId,title,description,wait=45000}){
  await sleep(wait);
  for(let i=0;i<6;i++){
    try{return await client.call("video.publish",{
      video_id:parseId(videoId),owner_id:client.ownerId,title,description,
      hide_auto_subs:"0",add_to_wall:"0",check_content_id:"0"
    },false);}
    catch(e){
      // Only an explicit processing response can be retried. All ambiguous failures block.
      if(!(e instanceof VkApiError&&[10,29].includes(e.code))||i===5)throw e;
      await sleep(30000);
    }
  }
}
export function makePostSticker(groupId,postId){
  const owner=-Number(parseId(groupId));
  return JSON.stringify({original_width:1080,original_height:1920,
    clickable_stickers:[{id:1,type:"post",post_owner_id:owner,post_id:Number(parseId(postId)),
      clickable_area:[{x:120,y:600},{x:960,y:600},{x:960,y:1320},{x:120,y:1320}]}]});
}
export async function uploadStoryPng(uploadUrl,png,fetchImpl=fetch){
  const u=new URL(uploadUrl);
  const permitted=["vk.com","vk.ru","vkuser.net","userapi.com","vk-cdn.net","vk-cdn.com","vkvideo.ru"];
  if(u.protocol!=="https:"||!permitted.some(x=>u.hostname===x||u.hostname.endsWith("."+x)))
    throw new Error("Недопустимый сервер VK Stories");
  const form=new FormData();
  form.append("file",new Blob([png],{type:"image/png"}),"story.png");
  const res=await fetchImpl(u,{method:"POST",body:form,redirect:"error",signal:AbortSignal.timeout(60000)});
  let json;try{json=await res.json();}catch{throw new Error("PNG upload: ответ не JSON");}
  const signed=json?.response?.upload_result;
  if(!res.ok||typeof signed!=="string"||signed.length<10||signed.length>65536)
    throw new Error("VK не подтвердил загрузку PNG");
  return signed;
}
