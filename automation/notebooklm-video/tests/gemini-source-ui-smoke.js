"use strict";
const assert=require("node:assert/strict");
const fs=require("node:fs");
const path=require("node:path");
const ui=require("../notebooklm-source-ui");

function surface(mode){
  const state={chooser:mode==="legacy",input:false,clicks:[]};
  const names=()=>{
    if(state.input)return [];
    if(state.chooser)return mode==="legacy"?["Сайты"]:mode==="gemini"?["Сайты"]:["Другое"];
    return ["+ Источники","Добавить источники"];
  };
  const targets=(type,pattern)=>{
    if(type==="input-scoped")return state.input?["URL textarea in exact dialog"]:[];
    if(type==="input"||type==="textbox")return state.input&&mode!=="gemini"?["URL input"]:[];
    return names().filter(x=>pattern.test(x));
  };
  class Loc{
    constructor(type,pattern){this.type=type;this.pattern=pattern;}
    filter({hasText}){return new Loc(this.type,hasText);}
    locator(sel){return new Loc(/textarea/.test(sel)?"input-scoped":"input",/./);}
    count(){return Promise.resolve(targets(this.type,this.pattern).length);}
    nth(n){const name=targets(this.type,this.pattern)[n];return {
      isVisible:async()=>Boolean(name),isEnabled:async()=>Boolean(name),
      getAttribute:async()=>null,click:async()=>{
        state.clicks.push(name);
        if(["+ Источники","Добавить источники"].includes(name)){
          state.chooser=true;
          if(mode==="direct")state.input=true;
        }
        if(["Сайты","Ссылки"].includes(name))state.input=true;
      }
    };}
  }
  const page={
    locator:s=>new Loc(/input|textarea|formcontrolname/.test(s)?"input":"button",/./),
    getByRole:(role,{name}={})=>new Loc(role==="textbox"?"textbox":role==="dialog"?"dialog":"button",name||/$^/),
    getByText:p=>new Loc("button",p),
  };
  return {page,state};
}

(async()=>{
  for(const [mode,expected] of [
    ["legacy",["Сайты"]],
    ["gemini",["+ Источники","Сайты"]],
    ["direct",["+ Источники"]]
  ]){
    const x=surface(mode);
    await ui.openWebsiteSourceInput(x.page,50);
    assert.deepEqual(x.state.clicks,expected,mode);
    assert.equal(x.state.input,true,mode);
  }
  const invalid=surface("unknown");
  await assert.rejects(ui.openWebsiteSourceInput(invalid.page,50),/нет выбора веб-сайта или URL/);
  assert(!invalid.state.clicks.includes("Другое"),"Unrelated source controls never clicked");
  assert(ui.WEBSITE_URL_DIALOG_TITLE.test("Ссылки на видео YouTube и сайты"));
  assert(ui.urlInputLocators(surface("gemini").page).length>=4,
    "Exact modal textarea must be searched before unscoped web-search inputs");

  const worker=fs.readFileSync(path.join(__dirname,"..","worker.js"),"utf8");
  const segment=worker.slice(worker.indexOf("async function createNotebookAndAddSource("),
    worker.indexOf("async function fillPromptField("));
  assert(segment.includes("job.notebookCreateArmedAt = new Date().toISOString();"),
    "Notebook creation must be armed before clicking");
  assert(segment.indexOf("job.notebookCreateArmedAt =")<segment.indexOf("await clickAnyVisible("));
  assert(segment.indexOf("job.notebookUrl = await waitForNewNotebookIdentity(")<
    segment.indexOf("await sourceUi.openWebsiteSourceInput("));
  assert(segment.indexOf("job.sourceSubmitArmedAt =")<
    segment.indexOf("await submitWebsiteSourceUrl("));
  assert(segment.includes("if (job.notebookUrl)"),
    "NEW job with notebook URL must resume same notebook, not create another");
  assert(segment.includes("if (!job.sourceSubmitArmedAt)"),
    "Previously attempted source submit must not be retried blindly");
  assert(segment.includes("verifiedSourceBox"),"Exact source textbox from modal must be reused");
  const submitFn=worker.slice(worker.indexOf("async function submitWebsiteSourceUrl("),
    worker.indexOf("function notebookCreateLocators("));
  assert(!submitFn.includes('sourceBox.press("Enter")'),
    "Enter in the new multiline URL field must never be used as submit");
  assert(!submitFn.includes('button[type="submit"]'),
    "Only exact named Add button is allowed in the verified source dialog");
  assert(!segment.includes('siteSourceLocators'),
    "Legacy Sites-only transition must be removed");

  console.log("Gemini source UI/at-most-once notebook contract: OK");
})().catch(e=>{console.error(e);process.exitCode=1;});