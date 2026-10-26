#!/usr/bin/env python3
"""Verify eight original 23-Oct Sol Responses offline; simulate missing four.

No OpenAI API request. The downloaded Actions artifact is trusted ONLY after
content SHA-256, request IDs, direction sequence and validator replay checks.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT/"automation/scripts"))
import primary_recall_search as primary

DATE="2026-10-23"
MODEL="gpt-6.1-sol"
FROZEN_COMMIT="071c1d6c2777de461d5e74b33d851e64a1d5f473"
ARCHIVE_SHA="5ae1c40efed23557c01465300a1630f418ddb028fae43a15c60093ea973af03b"
EXPECTED_EXEC_SHA="99077a0c76f811ca469ca5d5c2021a08e8a82813c3883af47e1570a9bb26f0b6"
EXPECTED_PARTIAL_SHA="3b26650c3f3e039c20b21e2b3c1f9a24a7ebb5a01e7e6396593560cc53261e18"
START="2026-10-21T04:32:02+03:00"
END="2026-10-23T04:31:19+03:00"
EXPECTED_RAW={
 "business_investment_partnerships":"a1453af2fd1c8d1160c868bafe01b3d26ddbee2fad383d5a7150ca27ce8084af",
 "china_asia_integrations":"facc9b33c7c2e2c425eec796491bb34fb336f299e82358a441ae7d56897624f1",
 "china_asia_models":"b20a379780499d1b69cd41222b764c79ce519640d3159e762be781d39cb99042",
 "global_breaking":"595699f697e1b3145e0dd31d4250c214e027e3f6563f9a6418d7958500825e94",
 "infrastructure_chips_cloud":"a37b8dd5982c32d7243cebad9fbad5384b01a413badeec9ea8fa9e10f6c2e1ae",
 "major_agencies":"adfc659a4f425e6c9bcca88c82d50c4d18561f3c188c1d14e34457ac48ed88fb",
 "models_products_agents":"c43561279593f678c03745462dc38870129f682c777fa2106b1413200c0be7c3",
 "russia":"b18f2be8babc4d9e459b94d3f0db80a78ef2deca4b301782dadc37213b6d9193",
}
def verified_bytes(path, sha):
    b=path.read_bytes()
    actual=hashlib.sha256(b).hexdigest()
    if actual!=sha:
        raise RuntimeError("Original evidence mismatch: "+str(path)+" expected "+sha+" got "+actual)
    return b

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--root", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=ROOT/"automation/preview/sol-shadow-2026-10-23/offline-8plus4.json")
    args=ap.parse_args()
    root=args.root
    execution=json.loads(verified_bytes(root/"sol-shadow-2026-10-23/execution.json",EXPECTED_EXEC_SHA))
    prior=json.loads(verified_bytes(root/"production-daily/primary-recall-2026-10-23.json",EXPECTED_PARTIAL_SHA))
    for direction, sha in EXPECTED_RAW.items():
        raw=json.loads(verified_bytes(root/"sol-shadow-2026-10-23/raw-responses"/(direction+".json"),sha))
        if raw.get("direction")!=direction or not isinstance(raw.get("api"),dict):
            raise RuntimeError("Invalid raw response provenance "+direction)
    if (execution.get("model")!=MODEL or execution.get("reasoning")!="medium"
        or execution.get("publication_date")!=DATE
        or execution.get("frozen_archive_sha256")!=ARCHIVE_SHA
        or execution.get("api_request_count")!=8
        or execution.get("search_actions_completed")!=8
        or execution.get("status")!="incomplete"
        or execution.get("search_window")!={"start_at":START,"end_at":END}
        or prior.get("publication_date")!=DATE
        or prior.get("status")!="error"):
        raise RuntimeError("Saved Sol execution identity mismatch")
    archive_raw=subprocess.check_output(["git","show",FROZEN_COMMIT+":automation/archive/index.json"],cwd=ROOT)
    if hashlib.sha256(archive_raw).hexdigest()!=ARCHIVE_SHA:
        raise RuntimeError("The original pre-publication archive changed")
    archive=json.loads(archive_raw)
    rows=execution["completed_passes"]
    saved_ids=[row["direction"] for row in rows]
    expected=[direction["id"] for direction in primary.PRIMARY_DIRECTIONS]
    if len(expected)!=12 or saved_ids!=expected[:8] or len(execution["requests"])!=8:
        raise RuntimeError("Expected exact eight original Primary directions, ordered")
    old=prior["directions"]
    if len(old)!=8 or [row["direction_id"] for row in old]!=saved_ids:
        raise RuntimeError("Partial validator report mismatch")
    for i,(row,req) in enumerate(zip(rows,execution["requests"])):
        api=row["api"]
        raw=json.loads((root/"sol-shadow-2026-10-23/raw-responses"/(row["direction"]+".json")).read_text())
        if (req["direction"]!=row["direction"]
            or req["status"]!="response_saved"
            or req.get("service_tier")!="default"
            or req["response_id"]!=api.get("response_id")
            or raw.get("response_id")!=req["response_id"]
            or api.get("model")!=MODEL or api.get("status")!="completed"
            or api.get("web_search_calls_completed")!=1
            or (api.get("usage") or {}).get("input_tokens") is None
            or (api.get("usage") or {}).get("output_tokens") is None
            or row["payload"].get("direction_id")!=row["direction"]
            or row["payload"].get("candidates")!=old[i].get("raw_candidates")
            or row["payload"].get("rejections")!=old[i].get("model_rejections")):
            raise RuntimeError("Incomplete original Primary response "+row["direction"])
    used={"replayed":0,"mocked":[]}
    def zero_api_runner(*,direction_id, **kwargs):
        if used["replayed"]<8:
            row=rows[used["replayed"]]
            if row["direction"]!=direction_id:
                raise RuntimeError("Direction mismatch during exact replay")
            used["replayed"]+=1
            return row["payload"],row["api"]
        used["mocked"].append(direction_id)
        return ({"direction_id":direction_id,"status":"complete_with_gaps",
                 "notes":"Offline no-op, NOT a real Sol result",
                 "candidates":[],"rejections":[]},
                {"model":MODEL,"status":"completed","web_search_calls_completed":1,
                 "usage":{"input_tokens":0,"output_tokens":0}})
    window=prior["search_window"]
    if window.get("start_at")!=START or window.get("end_at")!=END:
        raise RuntimeError("Partial report window mismatch")
    _,report=primary.run_primary_recall_matrix(
        publication_date=DATE,search_window=window,archive=archive,
        api_key="OFFLINE_NO_API",model=MODEL,maximum_candidates=20,
        search_runner=zero_api_runner)
    if len(report.get("directions",[]))!=12 or used["replayed"]!=8 or used["mocked"]!=expected[8:]:
        raise RuntimeError("8 frozen + 4 mocked was not followed")
    for i in range(8):
        a,b=report["directions"][i],old[i]
        for k in ("direction_id","raw_candidates","model_rejections","accepted_count"):
            if a.get(k)!=b.get(k):
                raise RuntimeError(f"Production validator changed replay direction {i+1}: {k}")
    proof={"status":"offline_pass","real_api_requests":0,"reused_saved_responses":8,
           "simulated_not_real_directions":used["mocked"],
           "frozen_archive_sha256":ARCHIVE_SHA,
           "original_execution_sha256":EXPECTED_EXEC_SHA,
           "original_partial_primary_sha256":EXPECTED_PARTIAL_SHA,
           "first_eight_raw_candidates":sum(len(x["payload"].get("candidates",[])) for x in rows),
           "first_eight_accepted_candidates":sum(int(x.get("accepted_count",0)) for x in old),
           "observed_initial_client_estimate_usd":execution["tier_adjusted_estimate_usd"],
           "notes":"Next four are mock no-ops, not executed Sol. Do not reuse full 12/12 outcome as scientific evidence."}
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(proof,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(proof,ensure_ascii=False,indent=2))
if __name__=="__main__":
    main()
