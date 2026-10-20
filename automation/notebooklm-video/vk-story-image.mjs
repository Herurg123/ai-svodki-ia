/** VK-only portrait Story derivative. The original NotebookLM PNG is never edited. */
import fs from 'node:fs';
import path from 'node:path';
import {spawn} from 'node:child_process';
import {createRequire} from 'node:module';
import {fileURLToPath} from 'node:url';
const require=createRequire(import.meta.url);
const PNG_MAGIC=Buffer.from('89504e470d0a1a0a','hex');
const W=1080,H=1920,MAX_SIZE=10*1024*1024;

export function pngDimensions(file){
  const data=Buffer.alloc(24);
  const handle=fs.openSync(file,'r');
  try {if(fs.readSync(handle,data,0,24,0)!==24)throw new Error('PNG слишком короткий');}
  finally {fs.closeSync(handle);}
  if(!data.subarray(0,8).equals(PNG_MAGIC)||data.toString('ascii',12,16)!=='IHDR')
    throw new Error('Невалидный PNG/IHDR');
  const width=data.readUInt32BE(16),height=data.readUInt32BE(20);
  if(width<2||height<2||width>20000||height>20000)throw new Error('Неверные размеры PNG');
  return {width,height};
}
export function storyImagePath(source){
  const file=path.parse(source);
  if(file.ext.toLowerCase()!=='.png'||file.name.endsWith('-vk'))
    throw new Error('Нужен исходный горизонтальный PNG, не -vk.png');
  return path.join(file.dir,file.name+'-vk.png');
}
function ffmpegBinary(){
  const binary=process.env.VK_STORY_FFMPEG_TEST_BIN||require('ffmpeg-static');
  if(typeof binary!=='string'||!fs.existsSync(binary))
    throw new Error('ffmpeg-static не найден (запустите npm ci в каталоге NotebookLMBot)');
  return binary;
}
function render(src,dst,binary){
  // The sharp original is fitted fully inside 1080x1920; only the backdrop crops.
  const filters='[0:v]split=2[bg][front];'+
    '[bg]scale=1080:1920:force_original_aspect_ratio=increase,'+
    'crop=1080:1920,boxblur=20:1,eq=brightness=-0.10:saturation=0.82[backdrop];'+
    '[front]scale=1080:1920:force_original_aspect_ratio=decrease[sharp];'+
    '[backdrop][sharp]overlay=(W-w)/2:(H-h)/2:format=auto,format=rgb24[out]';
  const args=['-hide_banner','-loglevel','error','-nostdin','-y','-i',src,
    '-filter_complex',filters,'-map','[out]','-frames:v','1','-f','image2','-c:v','png',dst];
  return new Promise((resolve,reject)=>{
    const child=spawn(binary,args,{windowsHide:true,stdio:['ignore','ignore','pipe']});
    let err='',finished=false;
    const timer=setTimeout(()=>{child.kill();},90000);
    child.stderr.on('data',x=>{if(err.length<4000)err+=String(x).slice(0,1000);});
    child.once('error',e=>{if(!finished){finished=true;clearTimeout(timer);reject(new Error('Не удалось запустить ffmpeg: '+e.code));}});
    child.once('close',code=>{if(finished)return;finished=true;clearTimeout(timer);
      if(code!==0)reject(new Error('ffmpeg завершился с кодом '+code+': '+err.slice(0,450)));
      else resolve();});
  });
}
/** Only reads src, creates/refreshes adjacent -vk.png after validation. */
export async function buildVkStoryImage(source){
  const src=path.resolve(source),dst=storyImagePath(src);
  if(!fs.existsSync(src)||!fs.statSync(src).isFile())throw new Error('Исходный PNG не найден');
  const sourceDim=pngDimensions(src);
  if(sourceDim.width<=sourceDim.height)throw new Error('Исходная картинка должна быть горизонтальной');
  if(fs.existsSync(dst)){
    try{
      const stat=fs.statSync(dst),dim=pngDimensions(dst);
      if(stat.size>100&&stat.size<=MAX_SIZE&&dim.width===W&&dim.height===H&&
          stat.mtimeMs>=fs.statSync(src).mtimeMs) return dst;
    }catch{} // Replace a broken/stale derivative, never the original.
  }
  const tmp=path.join(path.dirname(dst),'.'+path.basename(dst)+'.'+process.pid+'.tmp.png');
  try{
    await render(src,tmp,ffmpegBinary());
    const dims=pngDimensions(tmp),size=fs.statSync(tmp).size;
    if(dims.width!==W||dims.height!==H||size<=100||size>MAX_SIZE)
      throw new Error('VK story PNG не прошёл проверку 1080x1920/10MiB');
    // The destination is generated, not the original; replace only after validation.
    fs.copyFileSync(tmp,dst);
    const final=pngDimensions(dst);
    if(final.width!==W||final.height!==H)throw new Error('Ошибка записи итогового PNG');
    return dst;
  }finally{try{fs.rmSync(tmp,{force:true});}catch{}}
}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  const src=process.argv[2];
  if(!src) {console.error('Usage: node vk-story-image.mjs "<source PNG>"');process.exit(2);}
  buildVkStoryImage(src).then(dst=>console.log('VK STORY IMAGE OK:',dst,
    '1080x1920; bytes='+fs.statSync(dst).size),e=>{console.error(e.message);process.exitCode=1;});
}
