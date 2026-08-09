from __future__ import annotations

import base64
import json
import urllib.error
import urllib.parse
import urllib.request


class ApiError(RuntimeError):
    pass


class GitHub:
    def __init__(self, repository: str, token: str, api_url: str) -> None:
        self.repository = repository
        self.api_url = api_url.rstrip("/")
        self.headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-svodki-repository-hygiene",
        }

    def request(self, method: str, path: str, expected=(200,)):
        request = urllib.request.Request(f"{self.api_url}{path}", headers=self.headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
                data = json.loads(raw.decode("utf-8")) if raw else None
                status = response.status
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code not in expected:
                raise ApiError(f"{method} {path}: HTTP {exc.code}: {raw[:500]}") from exc
            status = exc.code
            data = json.loads(raw) if raw else None
        except urllib.error.URLError as exc:
            raise ApiError(f"{method} {path}: {exc}") from exc
        if status not in expected:
            raise ApiError(f"{method} {path}: unexpected HTTP {status}")
        return status, data

    def pages(self, path: str):
        result = []
        page = 1
        joiner = "" if path.endswith(("?", "&")) else ("&" if "?" in path else "?")
        while True:
            _, batch = self.request("GET", f"{path}{joiner}per_page=100&page={page}")
            if not isinstance(batch, list):
                raise ApiError(f"Expected list from {path}")
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def repo(self):
        return self.request("GET", f"/repos/{self.repository}")[1]

    def branch(self, name: str):
        name = urllib.parse.quote(name, safe="")
        status, data = self.request("GET", f"/repos/{self.repository}/branches/{name}", (200, 404))
        return data if status == 200 else None

    def branches(self):
        return self.pages(f"/repos/{self.repository}/branches?")

    def prs(self, state: str, base: str | None = None):
        query = f"state={urllib.parse.quote(state, safe='')}"
        if base:
            query += f"&base={urllib.parse.quote(base, safe='')}"
        return self.pages(f"/repos/{self.repository}/pulls?{query}&")

    def workflows(self):
        data = self.request("GET", f"/repos/{self.repository}/actions/workflows?per_page=100")[1]
        return data.get("workflows", [])

    def workflow_runs(self, workflow_id: int, limit: int = 100):
        limit = max(1, min(int(limit), 100))
        data = self.request(
            "GET",
            f"/repos/{self.repository}/actions/workflows/{workflow_id}/runs?per_page={limit}",
        )[1]
        return list(data.get("workflow_runs", []))[:limit]

    def runs(self, status: str):
        result = []
        page = 1
        while True:
            data = self.request("GET", f"/repos/{self.repository}/actions/runs?status={status}&per_page=100&page={page}")[1]
            batch = data.get("workflow_runs", [])
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def artifacts(self):
        result = []
        page = 1
        while True:
            data = self.request("GET", f"/repos/{self.repository}/actions/artifacts?per_page=100&page={page}")[1]
            batch = data.get("artifacts", [])
            result.extend(batch)
            if len(batch) < 100:
                return result
            page += 1

    def jobs(self, run_id: int):
        data = self.request("GET", f"/repos/{self.repository}/actions/runs/{run_id}/jobs?per_page=100")[1]
        return data.get("jobs", [])

    def contents(self, path: str, ref: str):
        path = "/".join(urllib.parse.quote(part, safe="") for part in path.split("/"))
        ref = urllib.parse.quote(ref, safe="")
        return self.request("GET", f"/repos/{self.repository}/contents/{path}?ref={ref}")[1]

    def file_text(self, path: str, ref: str):
        data = self.contents(path, ref)
        if data.get("type") != "file" or data.get("encoding") != "base64":
            raise ApiError(f"Unexpected content response for {path}")
        return base64.b64decode(data.get("content", "")).decode("utf-8")

    def delete_branch(self, name: str):
        ref = "/".join(urllib.parse.quote(part, safe="") for part in ("heads", *name.split("/")))
        self.request("DELETE", f"/repos/{self.repository}/git/refs/{ref}", (204,))

    def delete_artifact(self, artifact_id: int):
        self.request("DELETE", f"/repos/{self.repository}/actions/artifacts/{artifact_id}", (204,))

    def disable_workflow(self, workflow_id: int):
        self.request("PUT", f"/repos/{self.repository}/actions/workflows/{workflow_id}/disable", (204,))

    def delete_run(self, run_id: int):
        self.request("DELETE", f"/repos/{self.repository}/actions/runs/{run_id}", (204,))
