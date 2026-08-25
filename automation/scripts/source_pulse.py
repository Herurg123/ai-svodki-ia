#!/usr/bin/env python3
"""Research-only Source Pulse v1. Not wired into daily production."""
from __future__ import annotations

import argparse, hashlib, ipaddress, json, re, socket, time, urllib.error, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable, Iterable

VERSION=1; MAX_BYTES=1_500_000; TIMEOUT=10; ATTEMPTS=2; MAX_ITEMS=30; MAX_LEADS=120
UA="ai-svodki-source-pulse/1.0 research-only (+https://rybalka.one/posts/)"
WS=re.compile(r"\s+"); TOK=re.compile(r"[\w$€£¥₽.%+-]+",re.UNICODE)
GENERIC={"ai","artificial","intelligence","latest","news","release","releases","announces","announced","launches","launched","update","updated","company","group","inc","ltd","the","and","for","with","from","its","new","on","in","to","of","a","an"}

class SourcePulseError(RuntimeError): pass

@dataclass(frozen=True)
class SourceDefinition:
    id:str; tier:str; region:str; role:str; adapter:str; url:str; allowed_hosts:tuple[str,...]
    fallback_urls:tuple[str,...]=(); max_items:int=MAX_ITEMS; include_url_regex:str|None=None; include_title_regex:str|None=None
@dataclass(frozen=True)
class PulseLead:
    source_id:str; tier:str; region:str; role:str; title:str; url:str; published_date:str|None; published_at:str|None
    time_precision:str; cutoff_ambiguous:bool; source_item_id:str; event_fingerprint:str; exact_fingerprint:str; archive_url_duplicate:bool=False
@dataclass(frozen=True)
class FetchOutcome:
    requested_url:str; final_url:str|None; status:str; http_status:int|None; body:str|None; error:str|None; elapsed_ms:int
@dataclass(frozen=True)
class ParsedItem:
    title:str; url:str; published_date:date|None; published_at:datetime|None; time_precision:str; source_item_id:str


def safe_url(url:str, allowed_hosts:Iterable[str])->str:
    p=urllib.parse.urlsplit(str(url).strip())
    if p.scheme.lower()!="https" or not p.hostname: raise SourcePulseError("public HTTPS URL required")
    host=p.hostname.lower().strip("."); allowed={str(x).lower().strip(".") for x in allowed_hosts}
    if not allowed or not any(host==x or host.endswith("."+x) for x in allowed): raise SourcePulseError(f"host {host} not in fixed allowlist")
    if host=="localhost" or host.endswith(".local"): raise SourcePulseError("local host forbidden")
    try: addr=ipaddress.ip_address(host)
    except ValueError: addr=None
    if addr is not None and not addr.is_global: raise SourcePulseError("non-public IP forbidden")
    return p.geturl()

def ensure_public_dns(host:str)->None:
    try: rows=socket.getaddrinfo(host,443,type=socket.SOCK_STREAM)
    except socket.gaierror as e: raise SourcePulseError(f"DNS failed for {host}: {e}") from e
    addrs={r[4][0].split("%",1)[0] for r in rows if r and r[4]}
    if not addrs: raise SourcePulseError(f"DNS returned no addresses for {host}")
    for raw in addrs:
        if not ipaddress.ip_address(raw).is_global: raise SourcePulseError(f"host {host} resolves to non-public IP {raw}")

class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def __init__(self,hosts:tuple[str,...]): super().__init__(); self.hosts=hosts
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        u=safe_url(urllib.parse.urljoin(req.full_url,newurl),self.hosts); ensure_public_dns(urllib.parse.urlsplit(u).hostname or "")
        return super().redirect_request(req,fp,code,msg,headers,u)


def parse_date(raw:Any)->tuple[date|None,datetime|None,str]:
    if not isinstance(raw,str) or not raw.strip(): return None,None,"unknown"
    v=WS.sub(" ",raw.strip())
    try:
        x=datetime.fromisoformat(v.replace("Z","+00:00")); return (x.date(),x,"datetime") if x.tzinfo else (x.date(),None,"date")
    except ValueError: pass
    try:
        x=parsedate_to_datetime(v); return (x.date(),x,"datetime") if x.tzinfo else (x.date(),None,"date")
    except (TypeError,ValueError,OverflowError): pass
    for fmt in ("%Y-%m-%d","%Y/%m/%d","%Y.%m.%d","%B %d, %Y","%b %d, %Y","%Y年%m月%d日"):
        try: return datetime.strptime(v,fmt).date(),None,"date"
        except ValueError: pass
    return None,None,"unknown"

def norm_url(url:str)->str:
    p=urllib.parse.urlsplit(url); q=urllib.parse.parse_qsl(p.query,keep_blank_values=False)
    drop={"utm_source","utm_medium","utm_campaign","utm_term","utm_content","fbclid","gclid","mc_cid","mc_eid","ref","source"}
    q=[(k,v) for k,v in q if k.lower() not in drop]
    net=(p.hostname or "").lower()+((":"+str(p.port)) if p.port else "")
    return urllib.parse.urlunsplit((p.scheme.lower(),net,p.path.rstrip("/") or "/",urllib.parse.urlencode(q),""))
def norm_title(t:str)->str: return WS.sub(" ",t).strip()
def event_fp(title:str,d:date|None)->str:
    words=[]
    for t in TOK.findall(title):
        x=t.lower().strip("._-+")
        if len(x)>=3 and x not in GENERIC and x not in words: words.append(x)
    sig=" ".join(sorted(words)[:18]); day=d.isoformat() if d else "unknown-date"
    return hashlib.sha256(f"{day}|{sig}".encode()).hexdigest()[:24]
def exact_fp(title:str,url:str,d:date|None)->str:
    day=d.isoformat() if d else "unknown-date"; raw=f"{day}|{norm_title(title).lower()}|{norm_url(url)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]

class IndexParser(HTMLParser):
    def __init__(self,base:str): super().__init__(convert_charrefs=True); self.base=base; self.links=[]; self.cur=None; self.time=None; self.j=False; self.parts=[]; self.blocks=[]
    def handle_starttag(self,tag,attrs):
        a={k.lower():v for k,v in attrs if k}; t=tag.lower()
        if t=="a" and a.get("href"): self.cur={"href":urllib.parse.urljoin(self.base,str(a["href"])),"text":[],"datetime":self.time}
        elif t=="time": self.time=a.get("datetime")
        elif t=="script" and str(a.get("type") or "").split(";",1)[0].strip().lower()=="application/ld+json": self.j=True; self.parts=[]
    def handle_data(self,data):
        if self.cur is not None: self.cur["text"].append(data)
        if self.j: self.parts.append(data)
    def handle_endtag(self,tag):
        t=tag.lower()
        if t=="a" and self.cur is not None:
            self.links.append({"href":self.cur["href"],"text":norm_title("".join(self.cur["text"])),"datetime":self.cur.get("datetime") or self.time}); self.cur=None
        elif t=="time": self.time=None
        elif t=="script" and self.j: self.blocks.append("".join(self.parts)); self.j=False; self.parts=[]

def jsonld_items(v:Any,base:str)->list[ParsedItem]:
    out=[]
    if isinstance(v,dict):
        typ=v.get("@type"); types={str(typ).lower()} if isinstance(typ,str) else {str(x).lower() for x in typ} if isinstance(typ,list) else set()
        if types & {"newsarticle","article","blogposting","pressrelease"}:
            title=str(v.get("headline") or v.get("name") or "").strip(); u=v.get("url") or v.get("mainEntityOfPage")
            if isinstance(u,dict): u=u.get("@id") or u.get("url")
            url=urllib.parse.urljoin(base,str(u or "")); d,dt,p=parse_date(v.get("datePublished"))
            if title and url: out.append(ParsedItem(title,url,d,dt,p,str(v.get("@id") or url)))
        for x in v.values(): out.extend(jsonld_items(x,base))
    elif isinstance(v,list):
        for x in v: out.extend(jsonld_items(x,base))
    return out

def dedupe(items:list[ParsedItem])->list[ParsedItem]:
    out=[]; seen=set()
    for x in items:
        k=(norm_url(x.url),x.title.lower())
        if k not in seen: seen.add(k); out.append(x)
    return out

def parse_html(body:str,base:str)->list[ParsedItem]:
    p=IndexParser(base)
    try: p.feed(body); p.close()
    except Exception: pass
    out=[]
    for b in p.blocks:
        try: out.extend(jsonld_items(json.loads(b),base))
        except Exception: pass
    for a in p.links:
        if len(a["text"])<8 or not a["href"].startswith("https://"): continue
        d,dt,prec=parse_date(a.get("datetime")); out.append(ParsedItem(a["text"],a["href"],d,dt,prec,a["href"]))
    return dedupe(out)
def first_text(node:ET.Element,names:set[str])->str|None:
    for c in node.iter():
        if c.tag.split("}")[-1].lower() in names and c.text and c.text.strip(): return c.text.strip()
    return None
def parse_rss(body:str,base:str)->list[ParsedItem]:
    try: root=ET.fromstring(body)
    except ET.ParseError as e: raise SourcePulseError(f"malformed XML: {e}") from e
    out=[]
    for n in root.iter():
        if n.tag.split("}")[-1].lower() not in {"item","entry"}: continue
        title=first_text(n,{"title"}) or ""; raw=first_text(n,{"link","guid","id"}) or ""
        if not raw:
            for c in n:
                if c.tag.split("}")[-1].lower()=="link" and c.attrib.get("href"): raw=c.attrib["href"]; break
        u=urllib.parse.urljoin(base,raw); d,dt,p=parse_date(first_text(n,{"pubdate","published","updated","date"}))
        if title.strip() and u: out.append(ParsedItem(norm_title(title),u,d,dt,p,raw or u))
    return dedupe(out)
def parse_body(src:SourceDefinition,body:str,base:str)->list[ParsedItem]:
    prefix=body.lstrip()[:200].lower(); xml=prefix.startswith("<?xml") or prefix.startswith("<rss") or prefix.startswith("<feed")
    if xml: return parse_rss(body,base)
    if src.adapter=="rss_atom" and "<html" not in prefix and "<!doctype html" not in prefix: return parse_rss(body,base)
    return parse_html(body,base)


def within(x:ParsedItem,start:datetime,end:datetime)->tuple[bool,bool]:
    if x.published_at is not None:
        return (False,False) if x.published_at.tzinfo is None else (start<=x.published_at<=end,False)
    if x.published_date is None or not(start.date()<=x.published_date<=end.date()): return False,False
    return True,x.published_date==end.date()
def allowed_item(x:ParsedItem,s:SourceDefinition)->bool:
    if s.include_url_regex and not re.search(s.include_url_regex,x.url,re.I): return False
    if s.include_title_regex and not re.search(s.include_title_regex,x.title,re.I): return False
    try: safe_url(x.url,s.allowed_hosts)
    except SourcePulseError: return False
    return True

def archive_urls(a:dict[str,Any]|None)->set[str]:
    out=set()
    if not isinstance(a,dict): return out
    for row in a.get("items") or []:
        if not isinstance(row,dict): continue
        for u in row.get("source_urls") or []:
            if isinstance(u,str): out.add(norm_url(u))
        for st in row.get("stories") or []:
            for src in st.get("sources") or [] if isinstance(st,dict) else []:
                if isinstance(src,dict) and isinstance(src.get("url"),str): out.add(norm_url(src["url"]))
    return out

def load_registry(path:Path)->list[SourceDefinition]:
    p=json.loads(path.read_text(encoding="utf-8"))
    if p.get("version")!=VERSION or not isinstance(p.get("sources"),list): raise SourcePulseError("invalid registry")
    out=[]; ids=set()
    for r in p["sources"]:
        sid=str(r.get("id") or "").strip()
        if not sid or sid in ids: raise SourcePulseError("duplicate/empty source id")
        ids.add(sid); s=SourceDefinition(sid,str(r.get("tier")),str(r.get("region","global")),str(r.get("role","lead_only")),str(r.get("adapter","html_index")),str(r.get("url","")),tuple(r.get("allowed_hosts") or []),tuple(r.get("fallback_urls") or []),min(int(r.get("max_items",MAX_ITEMS)),MAX_ITEMS),r.get("include_url_regex"),r.get("include_title_regex"))
        if s.tier not in {"A","B"} or s.adapter not in {"rss_atom","html_index"}: raise SourcePulseError("invalid tier/adapter")
        safe_url(s.url,s.allowed_hosts); [safe_url(u,s.allowed_hosts) for u in s.fallback_urls]; out.append(s)
    return out

Fetcher=Callable[[str,tuple[str,...]],FetchOutcome]
def fetch_source(url:str,hosts:tuple[str,...])->FetchOutcome:
    safe=safe_url(url,hosts); host=urllib.parse.urlsplit(safe).hostname or ""
    try: ensure_public_dns(host)
    except SourcePulseError as e: return FetchOutcome(safe,None,"error",None,None,str(e),0)
    opener=urllib.request.build_opener(SafeRedirect(hosts)); started=time.monotonic(); last=None
    for i in range(ATTEMPTS):
        req=urllib.request.Request(safe,headers={"User-Agent":UA,"Accept":"application/rss+xml,application/atom+xml,text/html,*/*;q=0.1","Accept-Encoding":"identity","Cache-Control":"no-cache"})
        try:
            with opener.open(req,timeout=TIMEOUT) as r:
                final=safe_url(r.geturl(),hosts); raw=r.read(MAX_BYTES+1)
                if len(raw)>MAX_BYTES: raise SourcePulseError("response exceeds size cap")
                return FetchOutcome(safe,final,"ok",int(getattr(r,"status",200) or 200),raw.decode(r.headers.get_content_charset() or "utf-8",errors="replace"),None,int((time.monotonic()-started)*1000))
        except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError,SourcePulseError) as e:
            last=e
            if i+1<ATTEMPTS: time.sleep(.2)
    return FetchOutcome(safe,None,"error",getattr(last,"code",None),None,f"{type(last).__name__}: {last}",int((time.monotonic()-started)*1000))

def run_source_pulse(*,registry:list[SourceDefinition],start_at:datetime,end_at:datetime,archive:dict[str,Any]|None=None,fetcher:Fetcher=fetch_source,fetched_at:datetime|None=None)->dict[str,Any]:
    if start_at.tzinfo is None or end_at.tzinfo is None or end_at<start_at: raise SourcePulseError("invalid aware window")
    archived=archive_urls(archive); leads=[]; reports=[]
    for s in registry:
        attempts=[]; chosen=None
        for u in (s.url,*s.fallback_urls):
            o=fetcher(u,s.allowed_hosts); attempts.append({"url":u,"status":o.status,"http_status":o.http_status,"error":o.error,"elapsed_ms":o.elapsed_ms})
            if o.status=="ok" and o.body is not None: chosen=o; break
        if chosen is None:
            reports.append({"source_id":s.id,"tier":s.tier,"region":s.region,"status":"source_unavailable","attempts":attempts,"parsed_items":0,"window_items":0,"accepted_leads":0}); continue
        try: parsed=parse_body(s,chosen.body or "",chosen.final_url or chosen.requested_url)
        except Exception as e:
            reports.append({"source_id":s.id,"tier":s.tier,"region":s.region,"status":"parse_error","attempts":attempts,"parse_error":f"{type(e).__name__}: {e}","parsed_items":0,"window_items":0,"accepted_leads":0}); continue
        parsed=[x for x in parsed if allowed_item(x,s)][:s.max_items]; win=0; local=[]; seen=set()
        for x in parsed:
            ok,amb=within(x,start_at,end_at)
            if not ok: continue
            win+=1; ef=event_fp(x.title,x.published_date); xf=exact_fp(x.title,x.url,x.published_date)
            if xf in seen: continue
            seen.add(xf); local.append(PulseLead(s.id,s.tier,s.region,s.role,x.title,norm_url(x.url),x.published_date.isoformat() if x.published_date else None,x.published_at.isoformat() if x.published_at else None,x.time_precision,amb,x.source_item_id,ef,xf,norm_url(x.url) in archived))
            if len(leads)+len(local)>=MAX_LEADS: break
        leads.extend(local); reports.append({"source_id":s.id,"tier":s.tier,"region":s.region,"status":"ok","attempts":attempts,"selected_url":chosen.final_url or chosen.requested_url,"parsed_items":len(parsed),"window_items":win,"accepted_leads":len(local),"cutoff_ambiguous_leads":sum(x.cutoff_ambiguous for x in local),"archive_url_duplicates":sum(x.archive_url_duplicate for x in local)})
        if len(leads)>=MAX_LEADS: break
    out=[]; seen=set()
    for x in sorted(leads,key=lambda z:(z.published_at or z.published_date or "",z.source_id,z.title)):
        if x.exact_fingerprint not in seen: seen.add(x.exact_fingerprint); out.append(x)
    summary={"configured_sources":len(registry),"sources_ok":sum(r["status"]=="ok" for r in reports),"sources_unavailable":sum(r["status"]=="source_unavailable" for r in reports),"sources_parse_error":sum(r["status"]=="parse_error" for r in reports),"lead_count":len(out),"eligible_new_lead_count":sum(not x.cutoff_ambiguous and not x.archive_url_duplicate for x in out),"tier_a_leads":sum(x.tier=="A" for x in out),"tier_b_leads":sum(x.tier=="B" for x in out),"cutoff_ambiguous_leads":sum(x.cutoff_ambiguous for x in out),"archive_url_duplicates":sum(x.archive_url_duplicate for x in out)}
    core={"version":VERSION,"mode":"research_only","production_integration":False,"paid_api_calls":0,"web_search_operations":0,"window":{"start_at":start_at.isoformat(),"end_at":end_at.isoformat()},"sources":reports,"leads":[asdict(x) for x in out],"summary":summary}
    hs=[{"source_id":r.get("source_id"),"status":r.get("status"),"selected_url":r.get("selected_url"),"parsed_items":r.get("parsed_items"),"window_items":r.get("window_items"),"accepted_leads":r.get("accepted_leads"),"attempts":[{"url":a.get("url"),"status":a.get("status"),"http_status":a.get("http_status")} for a in r.get("attempts",[])]} for r in reports]
    canon=json.dumps({"version":VERSION,"window":core["window"],"sources":hs,"leads":core["leads"]},ensure_ascii=False,sort_keys=True,separators=(",",":"))
    return {**core,"fetched_at":(fetched_at or datetime.now(timezone.utc)).isoformat(),"snapshot_hash":hashlib.sha256(canon.encode()).hexdigest()}

def replay_fixture(path:Path)->dict[str,Any]:
    f=json.loads(path.read_text(encoding="utf-8")); reg=[SourceDefinition(r["id"],r["tier"],r.get("region","global"),r.get("role","lead_only"),r["adapter"],r["url"],tuple(r["allowed_hosts"]),tuple(r.get("fallback_urls") or []),int(r.get("max_items",MAX_ITEMS)),r.get("include_url_regex"),r.get("include_title_regex")) for r in f["registry"]]; snaps=f["snapshots"]
    def fake(u,hosts):
        safe_url(u,hosts); r=snaps.get(u)
        if r is None: return FetchOutcome(u,None,"error",404,None,"fixture_missing",1)
        if r.get("status")!="ok": return FetchOutcome(u,None,"error",r.get("http_status"),None,r.get("error","fixture_error"),1)
        return FetchOutcome(u,r.get("final_url") or u,"ok",int(r.get("http_status",200)),str(r.get("body") or ""),None,1)
    days=[]; hits=total=0
    for d in f["days"]:
        start=datetime.fromisoformat(d["start_at"].replace("Z","+00:00")); end=datetime.fromisoformat(d["end_at"].replace("Z","+00:00")); snap=run_source_pulse(registry=reg,start_at=start,end_at=end,archive=d.get("archive"),fetcher=fake,fetched_at=end); titles=[x["title"].lower() for x in snap["leads"]]; ctr=[]
        for c in d.get("controls") or []:
            total+=1; groups=c.get("all_token_groups") or []; hit=any(all(any(t.lower() in title for t in g) for g in groups) for title in titles); hits+=int(hit); ctr.append({"id":c["id"],"hit":hit})
        days.append({"date":d["date"],"lead_count":snap["summary"]["lead_count"],"sources_unavailable":snap["summary"]["sources_unavailable"],"sources_parse_error":snap["summary"]["sources_parse_error"],"controls":ctr,"snapshot_hash":snap["snapshot_hash"]})
    return {"version":1,"fixture":path.name,"production_api_used":False,"web_search_operations":0,"strict_instances":total,"strict_hits":hits,"recovery_rate":hits/total if total else None,"days":days}

_safe_public_url=safe_url
_normalized_url=norm_url
event_fingerprint=event_fp
parse_html_index=parse_html
parse_rss_atom=parse_rss
_parse_body=parse_body
_within_window=within

def aware(v:str)->datetime:
    x=datetime.fromisoformat(v.replace("Z","+00:00"))
    if x.tzinfo is None: raise SourcePulseError("timezone required")
    return x

def main()->int:
    p=argparse.ArgumentParser(); p.add_argument("--registry",type=Path); p.add_argument("--archive",type=Path); p.add_argument("--start-at"); p.add_argument("--end-at"); p.add_argument("--output",type=Path,required=True); p.add_argument("--replay-fixture",type=Path); a=p.parse_args()
    if a.replay_fixture: result=replay_fixture(a.replay_fixture)
    else:
        if not a.registry or not a.start_at or not a.end_at: p.error("live/manual mode requires registry/start/end")
        arc=json.loads(a.archive.read_text(encoding="utf-8")) if a.archive else None; result=run_source_pulse(registry=load_registry(a.registry),start_at=aware(a.start_at),end_at=aware(a.end_at),archive=arc)
    a.output.parent.mkdir(parents=True,exist_ok=True); a.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8"); print(json.dumps(result.get("summary") or {k:result.get(k) for k in ("strict_instances","strict_hits","recovery_rate")},ensure_ascii=False)); return 0
if __name__=="__main__": raise SystemExit(main())
