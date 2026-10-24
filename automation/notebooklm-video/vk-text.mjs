// VK publication text is rendered solely from an operator-owned source template.
// Source template is distinct from downloads/_ИИ-Сводка.txt, which other stages rewrite.
export function dateTokens(dateKey){
  const m=/^(\d{4})-(\d{2})-(\d{2})$/.exec(String(dateKey||""));
  if(!m)throw new Error("Дата выпуска должна быть YYYY-MM-DD");
  const [,yyyy,mm,dd]=m;
  const year=Number(yyyy),month=Number(mm),day=Number(dd);
  const d=new Date(Date.UTC(year,month-1,day));
  if(d.getUTCFullYear()!==year||d.getUTCMonth()!==month-1||d.getUTCDate()!==day)
    throw new Error("Несуществующая дата выпуска: "+dateKey);
  const months=["января","февраля","марта","апреля","мая","июня","июля",
    "августа","сентября","октября","ноября","декабря"];
  return {"YYYY-MM-DD":dateKey,"YYYY":yyyy,"YY":yyyy.slice(-2),
    "MMMM":months[month-1],"MM":mm,"DD":dd};
}
export function substituteDate(text,dateKey){
  const values=dateTokens(dateKey);
  return String(text).replace(/YYYY-MM-DD|YYYY|MMMM|YY|MM|DD/g,k=>values[k]);
}
export function renderVkTemplate(source,{date,articleUrl,publicationUrl}){
  if(typeof source!=="string"||source.trim().length<50)throw new Error("Пустой VK шаблон");
  const d=dateTokens(date);
  const canonical="https://rybalka.one/posts/"+date+"/";
  if(!/^https:\/\/rybalka\.one\/posts\/\d{4}-\d{2}-\d{2}\/$/.test(publicationUrl||"")||
    publicationUrl!==canonical)throw new Error("Ссылка исходной сводки не соответствует дате");
  // Dzen is independent: before its article becomes available, link to the
  // already-existing canonical digest. Do not allow arbitrary fallback URLs.
  if(articleUrl!==canonical && !/^https:\/\/dzen\.ru\/a\/[A-Za-z0-9_-]+$/.test(articleUrl||""))
    throw new Error("VK ссылка должна быть статьёй Дзена или исходной сводкой текущей даты");
  const lines=source.replace(/^\uFEFF/,"").replace(/\r\n?/g,"\n").split("\n");
  const titleMarks=lines.map((s,i)=>s.trim()==="+++ Тема / Название:"?i:-1).filter(x=>x>=0);
  const descriptionMarks=lines.map((s,i)=>s.trim()==="+++ Описание:"?i:-1).filter(x=>x>=0);
  if(titleMarks.length!==1||descriptionMarks.length!==1||descriptionMarks[0]<=titleMarks[0])
    throw new Error("VK шаблон должен содержать ровно два маркера в правильном порядке");
  const titleBlock=lines.slice(titleMarks[0]+1,descriptionMarks[0]).join("\n").trim();
  const bodyBlock=lines.slice(descriptionMarks[0]+1).join("\n").trim();
  if(!titleBlock||titleBlock.includes("\n")||!bodyBlock)
    throw new Error("Заголовок/описание в шаблоне пусты или имеют неверный формат");
  if(!bodyBlock.includes("% URL сводки этого дня в Дзен %"))
    throw new Error("В шаблоне отсутствует ссылка-заглушка на Дзен");
  if(!bodyBlock.includes("https://rybalka.one/posts/YYYY-MM-DD/"))
    throw new Error("В шаблоне отсутствует URL исходной сводки с датой");
  const replace=(str)=>substituteDate(str,date)
    .replaceAll("https://rybalka.one/posts/"+date+"/",publicationUrl)
    .replaceAll("% URL сводки этого дня в Дзен %",articleUrl);
  const title=replace(titleBlock);
  // When Dzen is not ready, the template already contains the origin URL.
  // Do not print that same link twice in the "Этот выпуск" section.
  const vkBody=articleUrl===publicationUrl?
    bodyBlock.replace(/^\s*-\s*% URL сводки этого дня в Дзен %\s*\n?/m,""):bodyBlock;
  const description=replace(vkBody);
  const postText=title+"\n\n"+description;
  if(title.includes("+++")||description.includes("+++")||
    /(?:YYYY-MM-DD|YYYY|MMMM|YY|MM|DD|% URL сводки этого дня в Дзен %)/.test(title+"\n"+description))
    throw new Error("В VK тексте остались служебные метки");
  return {title,description,postText,
    storyLinkCaption:"ИИ-Сводка на "+d.DD+" "+d.MMMM+" "+d.YYYY};
}
