#!/usr/bin/env python3
from pathlib import Path
import argparse, json, re, urllib.parse, xml.etree.ElementTree as ET
from html.parser import HTMLParser
CONTENT="{http://purl.org/rss/1.0/modules/content/}encoded"
ALLOWED={"h2","h3","p","figure","img","figcaption","a","ul","ol","li","strong","em"}
class P(HTMLParser):
    def __init__(self): super().__init__(); self.tags=[]; self.urls=[]; self.images=[]
    def handle_starttag(self,t,a):
        self.tags.append(t); d=dict(a)
        if t=="a" and d.get("href"): self.urls.append(d["href"])
        if t=="img": self.urls.append(d.get("src","")); self.images.append(d)
def host_ok(u):
    p=urllib.parse.urlparse(u)
    return p.scheme=="https" and p.netloc=="rybalka.one" and p.path.startswith("/posts/dzen-test/")
def main():
    a=argparse.ArgumentParser(); a.add_argument("--root",required=True); a.add_argument("--report",required=True); ns=a.parse_args()
    root=Path(ns.root); errors=[]; rss=root/"rss.xml"
    tree=ET.parse(rss); ch=tree.getroot().find("channel"); items=ch.findall("item")
    if len(items)!=10: errors.append(f"expected 10 items, got {len(items)}")
    for n,it in enumerate(items,1):
        title=it.findtext("title",""); urls=[it.findtext("link",""),it.findtext("guid","")]
        enc=it.find("enclosure")
        if enc is None: errors.append(f"{title}: enclosure missing")
        else:
            urls.append(enc.get("url", ""))
            if int(enc.get("length","0") or 0)<=0: errors.append(f"{title}: enclosure length invalid")
        body=it.findtext(CONTENT,""); p=P(); p.feed(body); urls+=p.urls
        bad=set(p.tags)-ALLOWED
        if bad: errors.append(f"{title}: unsupported tags {sorted(bad)}")
        for req in ("h2","h3","p","figure","img","a","ul","ol","li","strong","em"):
            if req not in p.tags: errors.append(f"{title}: missing {req}")
        for u in urls:
            if not host_ok(u): errors.append(f"{title}: external or invalid URL {u}")
        for img in p.images:
            if img.get("width")!="1536" or img.get("height")!="864" or not img.get("alt"):
                errors.append(f"{title}: image dimensions/alt invalid")
        date=urllib.parse.urlparse(it.findtext("link","")).path.rstrip("/").split("/")[-1]
        if not (root/date/"index.html").exists(): errors.append(f"{title}: page missing")
        image_name=Path(urllib.parse.urlparse(enc.get("url","")).path).name if enc is not None else ""
        if not (root/"images"/image_name).exists(): errors.append(f"{title}: image file missing")
    for pth in root.rglob("*"):
        if pth.is_file() and pth.suffix.lower() in {".html",".xml",".json",".md",".py",".yml"}:
            text=pth.read_text(encoding="utf-8",errors="ignore").lower()
            for marker in ("blogspot","blogger.googleusercontent","rybv.blogspot"):
                if marker in text: errors.append(f"{pth}: forbidden Blogger marker {marker}")
    report={"status":"ok" if not errors else "error","items":len(items),"errors":errors}
    Path(ns.report).write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(report,ensure_ascii=False,indent=2))
    raise SystemExit(0 if not errors else 1)
if __name__=="__main__": main()
