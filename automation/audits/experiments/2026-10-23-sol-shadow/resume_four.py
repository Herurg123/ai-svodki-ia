#!/usr/bin/env python3
"""Resume Oct-23 Sol Primary: eight verified saved passes and only four new paid calls."""
import hashlib, json, os, shutil, subprocess, sys
from pathlib import Path
from datetime import datetime
ROOT=Path(__file__).resolve().parents[4]
sys.path[:0]=[str(ROOT/"automation/scripts"),str(Path(__file__).resolve().parent)]
import primary_recall_search as primary
import verify_saved_primary as frozen
import run_primary as initial
from ensure_story_coverage_policy import build_audit_api_metadata
from openai import OpenAI
from openai.resources.responses import Responses
SRC=Path(os.environ.get("SOL_SAVED_ROOT","/nonexistent"))
OUT=ROOT/"automation/preview/sol-shadow-2026-10-23/resume-four"
STATE=OUT/"execution.json"
S={"status":"preflight","model":"gpt-6.1-sol","publication_date":"2026-10-23",
   "prior_run":39891725068,"prior_artifact":12475775291,
   "prior_usage_estimate_usd":0.903998,"limit_new_responses":4,
   "owner_removed_cost_guard":True,"new_requests":[],"new_count":0,
   "new_searches":0,"new_standard_estimate_usd":0.,
   "new_tier_estimate_usd":0.,"cost_not_provider_invoice":True}
def save():
    OUT.mkdir(parents=True,exist_ok=True)
    p=STATE.with_suffix(".tmp")
    p.write_text(json.dumps(S,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    p.replace(STATE)
def run():
    if os.getenv("SOL_SHADOW_RESUME_APPROVED")!="FOUR_ONLY":
        raise RuntimeError("Owner authorization marker missing")
    if os.getenv("GITHUB_RUN_ATTEMPT","1")!="1" or STATE.exists():
        raise RuntimeError("Repeated paid run prohibited")
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("No API key")
    source_exec=SRC/"sol-shadow-2026-10-23/execution.json"
    old=json.loads(frozen.verified_bytes(source_exec,frozen.EXPECTED_EXEC_SHA))
    partial=json.loads(frozen.verified_bytes(
        SRC/"production-daily/primary-recall-2026-10-23.json",
        frozen.EXPECTED_PARTIAL_SHA))
    archive=subprocess.check_output([
        "git","show",frozen.FROZEN_COMMIT+":automation/archive/index.json"],cwd=ROOT)
    if hashlib.sha256(archive).hexdigest()!=frozen.ARCHIVE_SHA:
        raise RuntimeError("Pre-publication archive checksum mismatch")
    directions=[d["id"] for d in primary.PRIMARY_DIRECTIONS]
    rows=old["completed_passes"]
    if (old["api_request_count"]!=8 or old["search_actions_completed"]!=8
        or len(rows)!=8 or len(directions)!=12
        or [r["direction"] for r in rows]!=directions[:8]
        or len(partial["directions"])!=8 or old["model"]!="gpt-6.1-sol"
        or old["search_window"]!={"start_at":frozen.START,"end_at":frozen.END}):
        raise RuntimeError("Incomplete or mismatched original provenance")
    for i,row in enumerate(rows):
        direction=row["direction"]
        saved_raw=json.loads(frozen.verified_bytes(
            SRC/"sol-shadow-2026-10-23/raw-responses"/(direction+".json"),
            frozen.EXPECTED_RAW[direction]))
        api=row["api"]
        if (saved_raw["response_id"]!=api["response_id"]
            or old["requests"][i]["response_id"]!=api["response_id"]
            or old["requests"][i]["status"]!="response_saved"
            or api["web_search_calls_completed"]!=1
            or row["payload"]["candidates"]!=partial["directions"][i]["raw_candidates"]
            or row["payload"]["rejections"]!=partial["directions"][i]["model_rejections"]):
            raise RuntimeError("Frozen saved response changed: "+direction)
    original=OUT/"original-frozen"
    original.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source_exec,original/"execution.json")
    shutil.copy2(SRC/"production-daily/primary-recall-2026-10-23.json",
                 original/"primary-recall.json")
    (ROOT/"automation/archive/index.json").write_bytes(archive)
    S.update({"status":"running","frozen_eight_sha256":frozen.EXPECTED_EXEC_SHA,
              "frozen_primary_sha256":frozen.EXPECTED_PARTIAL_SHA,
              "frozen_archive_sha256":frozen.ARCHIVE_SHA,
              "old_standard_estimate_usd":old["standard_price_estimate_usd"],
              "old_tier_estimate_usd":old["tier_adjusted_estimate_usd"]})
    save()
    ctx={"idx":0,"active":None,"prompt_sha":None}
    old_init,old_create=OpenAI.__init__,Responses.create
    old_matrix=primary._BASE_RUN_MATRIX
    actual_search=primary._base.run_search_request
    def no_retry(self,*a,**kw):
        kw["max_retries"]=0
        return old_init(self,*a,**kw)
    def tracked(self,*a,**kw):
        if (ctx["active"] not in directions[8:] or kw.get("model")!="gpt-6.1-sol"
            or (kw.get("reasoning") or {}).get("effort")!="medium"
            or kw.get("store") is not False
            or kw.get("max_tool_calls")!=primary.PRIMARY_MAX_TOOL_CALLS_PER_PASS
            or not 1<=kw.get("max_output_tokens",0)<=6000):
            raise RuntimeError("Unexpected request forbidden before API")
        if S["new_count"]>=4:
            raise RuntimeError("New request count cap: four")
        req={"number":S["new_count"]+1,"direction":ctx["active"],
             "prompt_sha256":ctx["prompt_sha"],"status":"started"}
        S["new_count"]+=1
        S["new_requests"].append(req)
        save()
        try:
            response=old_create(self,*a,**kw)
        except Exception as exc:
            req["status"]="unknown_after_exception"
            req["error_type"]=type(exc).__name__
            S["status"]="ambiguous_api_spend"
            save()
            raise
        meta=build_audit_api_metadata(response,maximum_web_search_calls=1)
        rid=getattr(response,"id",None)
        tier=str(getattr(response,"service_tier",None) or "unknown")
        raw_dir=OUT/"raw-responses"
        raw_dir.mkdir(parents=True,exist_ok=True)
        (raw_dir/(ctx["active"]+".json")).write_text(
            json.dumps({"direction":ctx["active"],"response_id":rid,
                        "service_tier":tier,"output_text":getattr(response,"output_text",None),
                        "api":meta},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        req.update({"response_id":rid,"service_tier":tier,
                    "metadata":meta,"status":"response_saved"})
        count=int(meta.get("web_search_calls_completed",0))
        S["new_searches"]+=count
        save()
        standard,adjusted,reported=initial.cost(response,count)
        req.update({"standard_estimate_usd":standard,
                    "tier_estimate_usd":adjusted,"service_tier":reported,
                    "status":"usage_saved"})
        S["new_standard_estimate_usd"]=round(S["new_standard_estimate_usd"]+standard,9)
        S["new_tier_estimate_usd"]=round(S["new_tier_estimate_usd"]+adjusted,9)
        S["cumulative_estimate_usd"]=round(
            S["old_tier_estimate_usd"]+S["new_tier_estimate_usd"],9)
        save()
        return response
    def replay(*,direction_id,prompt,**kw):
        idx=ctx["idx"]
        if idx>=12 or directions[idx]!=direction_id:
            raise RuntimeError("Primary direction order mismatch")
        ctx["idx"]+=1
        digest=hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        if idx<8:
            if digest!=old["requests"][idx]["prompt_sha256"]:
                raise RuntimeError("Original prompt SHA changed: "+direction_id)
            return rows[idx]["payload"],rows[idx]["api"]
        ctx.update({"active":direction_id,"prompt_sha":digest})
        try:
            payload,api=actual_search(direction_id=direction_id,prompt=prompt,**kw)
            S.setdefault("completed_new_passes",[]).append({
                "direction":direction_id,"payload":payload,"api":api})
            save()
            return payload,api
        finally:
            ctx.update({"active":None,"prompt_sha":None})
    def wrapped(*a,**kw):
        kw["search_runner"]=replay
        return old_matrix(*a,**kw)
    OpenAI.__init__,Responses.create=no_retry,tracked
    primary._BASE_RUN_MATRIX=wrapped
    try:
        path,report=primary.run_primary_recall_search(
            publication_date="2026-10-23",api_key=os.environ["OPENAI_API_KEY"],
            model="gpt-6.1-sol",maximum_candidates=20,
            cutoff_at=datetime.fromisoformat(frozen.END))
        if (report.get("status")!="complete" or len(report["directions"])!=12
            or ctx["idx"]!=12 or S["new_count"]!=4 or S["new_searches"]!=4):
            raise RuntimeError("Not exactly 8 frozen + 4 new completed Sol passes")
        for i,prior in enumerate(partial["directions"]):
            current=report["directions"][i]
            for key in ("direction_id","raw_candidates","model_rejections","accepted_count"):
                if current.get(key)!=prior.get(key):
                    raise RuntimeError("Frozen validator mismatch: "+key)
        S.update({"status":"complete","research_path":str(path),
                  "candidate_count":report.get("final_candidate_count")})
        save()
    finally:
        OpenAI.__init__,Responses.create=old_init,old_create
        primary._BASE_RUN_MATRIX=old_matrix
if __name__=="__main__":
    try: run()
    except Exception as exc:
        if S.get("status")!="ambiguous_api_spend": S["status"]="incomplete"
        S["error"]=type(exc).__name__+": "+str(exc)
        save()
        print("Sol continuation error:",S["error"],file=sys.stderr)
        raise SystemExit(1)
